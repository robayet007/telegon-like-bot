import os
import asyncio
import re
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv
import aiohttp

# Load environment variables
load_dotenv()

# Get credentials from environment
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
API_KEY = os.getenv('API_KEY', 'BSMQ9T')  # Default API key

# Create Telegram client
client = TelegramClient('ff_like_bot', API_ID, API_HASH)

# =========================
# In-memory LIMIT SYSTEM
# =========================

# Default daily limit per user (if not overridden)
# 0 মানে: ডিফল্টভাবে কেউই request পাঠাতে পারবে না,
# admin যখন limit সেট করবে তখন থেকেই সেই user use করতে পারবে।
DEFAULT_DAILY_LIMIT = 0

# Per-user custom limits: user_id -> limit
USER_LIMITS = {}

# Daily usage: (user_id, date_str) -> count
USER_USAGE = {}


def _today_str():
    """Return today's date as YYYY-MM-DD in UTC."""
    return datetime.utcnow().strftime('%Y-%m-%d')


def _usage_key(user_id: int) -> tuple:
    """Build usage dict key for a user for today."""
    return (user_id, _today_str())


async def check_limit(event) -> bool:
    """
    Check if user still has quota today.
    NOTE: This does NOT increment usage. Increment only on success.
    """
    user_id = event.sender_id
    key = _usage_key(user_id)

    # Get user's custom limit or default
    limit = USER_LIMITS.get(user_id, DEFAULT_DAILY_LIMIT)
    count = USER_USAGE.get(key, 0)

    if count >= limit:
        await event.reply(
            f"⚠️ আজকের limit শেষ হয়ে গেছে!\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"📅 Date: `{_today_str()}`\n"
            f"📌 Daily limit: `{limit}` request"
        )
        return False
    return True


def increment_usage_for_user(user_id: int):
    """Increment today's usage counter for a specific user."""
    key = _usage_key(user_id)
    USER_USAGE[key] = USER_USAGE.get(key, 0) + 1


async def reset_today_usage_for_user(event, target_user_id: int):
    """Reset today's usage counter for a specific user."""
    key = _usage_key(target_user_id)
    if key in USER_USAGE:
        del USER_USAGE[key]
    await event.reply(
        f"✅ Today's usage reset for user `{target_user_id}` "
        f"on `{_today_str()}`"
    )


async def set_limit_for_user(event, target_user_id: int, limit: int):
    """Set custom daily limit for a specific user."""
    USER_LIMITS[target_user_id] = limit
    await event.reply(
        f"✅ Daily limit set to `{limit}` for user `{target_user_id}`"
    )


def format_response(data):
    """Format API response into a readable message"""
    likes_given = data.get('LikesGivenByAPI', 0)
    likes_before = data.get('LikesbeforeCommand', 0)
    likes_after = data.get('LikesafterCommand', 0)
    player_nickname = data.get('PlayerNickname', 'N/A')
    uid = data.get('UID', 'N/A')
    
    # Calculate total likes added
    total_likes_added = likes_after - likes_before
    if total_likes_added <= 0:
        total_likes_added = likes_given
    
    # Build simple formatted message
    message = f"""✅ **LIKE SENT SUCCESSFULLY**
━━━━━━━━━━━━━━━━━━━━
👤 Player Nickname: {player_nickname}
🆔 Player UID: {uid}

👍 Before Likes: {likes_before}
🔥 After Likes: {likes_after}
💎 Total Likes Added: {total_likes_added}
━━━━━━━━━━━━━━━━━━━━"""
    
    return message


def get_likes_added(data) -> int:
    """
    Calculate how many likes were actually added for limit logic.
    We use the max of (after - before) and LikesGivenByAPI,
    but DO NOT force non-zero like format_response does.
    """
    likes_given = data.get('LikesGivenByAPI', 0) or 0
    likes_before = data.get('LikesbeforeCommand', 0) or 0
    likes_after = data.get('LikesafterCommand', 0) or 0

    diff = likes_after - likes_before
    added = max(diff, likes_given, 0)
    return added


async def call_ff_api(uid):
    """Make GET request to FF API"""
    url = f"https://ff.api.emonaxc.com/like?key={API_KEY}&uid={uid}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    return {
                        'error': True,
                        'message': f'API returned status code {response.status}'
                    }
    except asyncio.TimeoutError:
        return {
            'error': True,
            'message': 'Request timeout - API took too long to respond'
        }
    except Exception as e:
        return {
            'error': True,
            'message': f'Error calling API: {str(e)}'
        }


@client.on(events.NewMessage(pattern=r'(?i)^/?like\s+(\d+)$'))
async def like_command_handler(event):
    """Handle like <uid> command - works in both groups and private, with or without /"""
    # Check daily limit for this user (increment only on success)
    if not await check_limit(event):
        return

    # Extract UID from command
    match = re.search(r'(\d+)', event.raw_text)
    if not match:
        await event.reply("❌ Invalid format. Use: `/like <uid>`")
        return
    
    uid = match.group(1)
    
    # Send processing message
    try:
        processing_msg = await event.reply(f"⏳ Processing like request for UID: {uid}...")
    except Exception as e:
        print(f"Error replying: {e}")
        return
    
    # Call API
    result = await call_ff_api(uid)
    
    # Handle response
    if result.get('error'):
        try:
            await processing_msg.edit(f"❌ **Error:**\n{result.get('message', 'Unknown error')}")
        except:
            await event.reply(f"❌ **Error:**\n{result.get('message', 'Unknown error')}")
    else:
        # Check how many likes were actually added
        likes_added = get_likes_added(result)

        # Threshold: যদি ৫০ বা তার বেশি like add হয়, তবেই limit কাটবে
        THRESHOLD = 50

        formatted_message = format_response(result)

        if likes_added >= THRESHOLD:
            # SUCCESS -> count this request
            increment_usage_for_user(event.sender_id)
        else:
            # Not enough likes added -> don't count towards limit, just a short note
            formatted_message += "\n\n✅ **Limit refunded**"

        try:
            await processing_msg.edit(formatted_message)
        except:
            await event.reply(formatted_message)

@client.on(events.NewMessage(pattern=r'(?i)^/?start$'))
async def start_command_handler(event):
    """Handle start command - works in both groups and private (with or without /)"""
    is_group = not event.is_private
    
    if is_group:
        help_message = """🤖 **Free Fire Like Bot**

Send likes to Free Fire players using their UID.

**Usage:**
`/like <uid>`

**Example:**
`/like 1711537287`

**Note:** This bot uses your Telegram account to send commands."""
    else:
        help_message = """🤖 **Free Fire Like Bot**

Send likes to Free Fire players using their UID.

**Usage:**
`/like <uid>` or `like <uid>`

**Example:**
`/like 1711537287`

**Note:** This bot uses your Telegram account to send commands."""
    
    await event.reply(help_message)


@client.on(events.NewMessage(pattern=r'(?i)^/?help$'))
async def help_command_handler(event):
    """Handle help command - works in both groups and private (with or without /)"""
    is_group = not event.is_private

    # ---------- User Commands ----------
    if is_group:
        user_cmds = """👥 **User Commands (Group & Private)**

- `like <uid>` – Free Fire UID-এ like পাঠাবে
- `start` – Bot সম্পর্কে basic তথ্য দেখাবে
- `help` – এই help message দেখাবে
- `mylimit` – আজকে কতবার use করেছেন ও আপনার daily limit কত তা দেখাবে

**Example:**
`like 1711537287`"""
    else:
        user_cmds = """👤 **User Commands (Private & Group)**

- `like <uid>` / `/like <uid>` – Free Fire UID-এ like পাঠাবে
- `start` / `/start` – Bot সম্পর্কে basic তথ্য
- `help` / `/help` – এই help message
- `mylimit` / `/mylimit` – আজকের ব্যবহার ও limit দেখাবে

**Example:**
`like 1711537287`"""

    # ---------- Admin / Owner Commands ----------
    # Note: এগুলো শুধু bot owner (যে account দিয়ে bot চালাচ্ছেন) use করতে পারবে
    admin_cmds = """

🛠 **Admin / Owner Commands**

- `setlimit <n>` / `/setlimit <n>`  
  ➤ নিজের daily limit `n` সেট করবে  
  উদাহরণ: `setlimit 10`

- `setlimit <n> @username`  
  ➤ নির্দিষ্ট user-এর daily limit সেট করবে  
  উদাহরণ: `setlimit 5 @testuser`

- `resetlimit` / `/resetlimit`  
  ➤ নিজের আজকের usage reset করবে

- `resetlimit @username`  
  ➤ ঐ user-এর আজকের usage reset করবে

- `alllimit` / `/alllimit`  
  ➤ আজকের জন্য সব user-এর used / limit / remaining list দেখাবে (owner only)
"""

    help_message = f"""📖 **Help**

{user_cmds}{admin_cmds}

⚙️ **Note:**
- Commands case-insensitive: `like`, `Like`, `LIKE` সব কাজ করবে
- Slash (`/`) সহ বা ছাড়া – দু’ভাবেই command দেওয়া যাবে
- Valid UID numeric হতে হবে
"""

    await event.reply(help_message)


# =========================
# LIMIT CONTROL COMMANDS
# =========================


@client.on(events.NewMessage(pattern=r'(?i)^/?setlimit\s+(\d+)(?:\s+(@?\w+))?$'))
async def setlimit_command_handler(event):
    """
    Set daily limit for a user.
    Usage:
      /setlimit 5           -> set your own daily limit to 5
      /setlimit 5 @username -> set limit for @username
    """
    # Only allow owner (self account) to change limits
    me = await client.get_me()
    if event.sender_id != me.id:
        await event.reply("❌ Only the bot owner can use /setlimit.")
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?setlimit\s+(\d+)(?:\s+(@?\w+))?$', text)
    if not match:
        await event.reply("❌ Invalid format.\nUsage: `/setlimit 5` or `/setlimit 5 @username`")
        return

    limit = int(match.group(1))
    username = match.group(2)

    # Determine target user
    if username:
        try:
            entity = await client.get_entity(username)
            target_user_id = entity.id
        except Exception as e:
            await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
            return
    else:
        target_user_id = event.sender_id

    await set_limit_for_user(event, target_user_id, limit)


@client.on(events.NewMessage(pattern=r'(?i)^/?resetlimit(?:\s+(@?\w+))?$'))
async def resetlimit_command_handler(event):
    """
    Reset today's usage counter for a user.
    Usage:
      /resetlimit           -> reset your own usage for today
      /resetlimit @username -> reset usage for @username today
    """
    # Only allow owner to reset limits
    me = await client.get_me()
    if event.sender_id != me.id:
        await event.reply("❌ Only the bot owner can use /resetlimit.")
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?resetlimit(?:\s+(@?\w+))?$', text)
    if not match:
        await event.reply("❌ Invalid format.\nUsage: `/resetlimit` or `/resetlimit @username`")
        return

    username = match.group(1)

    # Determine target user
    if username:
        try:
            entity = await client.get_entity(username)
            target_user_id = entity.id
        except Exception as e:
            await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
            return
    else:
        target_user_id = event.sender_id

    await reset_today_usage_for_user(event, target_user_id)


@client.on(events.NewMessage(pattern=r'(?i)^/?mylimit$'))
async def mylimit_command_handler(event):
    """
    Show current limit and today's usage for the caller.
    Usage: /mylimit
    """
    user_id = event.sender_id
    key = _usage_key(user_id)
    limit = USER_LIMITS.get(user_id, DEFAULT_DAILY_LIMIT)
    used = USER_USAGE.get(key, 0)

    await event.reply(
        f"📊 **Your Limit Status**\n\n"
        f"👤 User ID: `{user_id}`\n"
        f"📅 Date: `{_today_str()}`\n"
        f"✅ Used: `{used}` request(s)\n"
        f"📌 Daily Limit: `{limit}` request(s)\n"
        f"🔄 Remaining: `{max(limit - used, 0)}` request(s)"
    )


@client.on(events.NewMessage(pattern=r'(?i)^/?alllimit$'))
async def alllimit_command_handler(event):
    """
    Show today's usage & limits for all users (owner only).
    Usage: alllimit / /alllimit
    """
    # Only owner can see full list
    me = await client.get_me()
    if event.sender_id != me.id:
        await event.reply("❌ Only the bot owner can use `alllimit`.")
        return

    today = _today_str()

    # Collect all user_ids from limits and usage
    user_ids = set(USER_LIMITS.keys())
    for (uid, date_str), _ in USER_USAGE.items():
        if date_str == today:
            user_ids.add(uid)

    if not user_ids:
        await event.reply("📊 আজকে এখনও কেউ কোনো request পাঠায়নি।")
        return

    lines = [f"📊 **All Users Limit Status**\n📅 Date: `{today}`\n"]

    # Pre-fetch entities for better names (best-effort)
    name_cache = {}
    for uid in user_ids:
        try:
            entity = await client.get_entity(uid)
            if getattr(entity, 'username', None):
                display = f"@{entity.username}"
            else:
                # Use first + last name fallback
                first = getattr(entity, 'first_name', '') or ''
                last = getattr(entity, 'last_name', '') or ''
                full_name = (first + ' ' + last).strip() or 'Unknown'
                display = full_name
            name_cache[uid] = display
        except Exception:
            # Fallback to raw ID if we can't resolve
            name_cache[uid] = str(uid)

    for uid in sorted(user_ids):
        key = (uid, today)
        limit = USER_LIMITS.get(uid, DEFAULT_DAILY_LIMIT)
        used = USER_USAGE.get(key, 0)
        remaining = max(limit - used, 0)
        display_name = name_cache.get(uid, str(uid))

        lines.append(
            f"👤 User: **{display_name}** (`{uid}`)\n"
            f"   ✅ Used: `{used}` / `{limit}`\n"
            f"   🔄 Remaining: `{remaining}`\n"
        )

    msg = "\n".join(lines)
    await event.reply(msg)


async def main():
    """Main function to start the bot"""
    print("🚀 Starting Free Fire Like Bot...")
    
    # Start the client
    await client.start()
    
    # Check if we need to authenticate
    if not await client.is_user_authorized():
        print("📱 Please authorize this session:")
        phone = input("Enter your phone number: ")
        await client.send_code_request(phone)
        
        try:
            code = input("Enter the code you received: ")
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("Enter your 2FA password: ")
            await client.sign_in(password=password)
    
    print("✅ Bot is running! Send /start to begin.")
    print("Press Ctrl+C to stop.")
    
    # Keep the bot running
    await client.run_until_disconnected()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")

