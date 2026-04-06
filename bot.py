import os
import asyncio
import re
import json
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession
from dotenv import load_dotenv
import aiohttp
from aiohttp import web

# Load environment variables
load_dotenv()

# Get credentials from environment
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
API_KEY = os.getenv('API_KEY', 'BSMQ9T')  # Default API key
SESSION_STRING = os.getenv('SESSION_STRING')
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://127.0.0.1:27017')
MONGODB_DB = os.getenv('MONGODB_DB', 'ff_like_bot')
MONGODB_STATE_COLLECTION = os.getenv('MONGODB_STATE_COLLECTION', 'bot_state')

# Create Telegram client
if SESSION_STRING:
    # Render/Vercel এর মত environment এ SESSION_STRING থাকলে ওটাই use করবে
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    # লোকাল রান করার সময় পুরনো file-session ('ff_like_bot.session') use করবে
    client = TelegramClient('ff_like_bot', API_ID, API_HASH)

MAIN_CLIENT = client
SUPER_ADMIN_CLIENTS = {}

# =========================
# In-memory LIMIT SYSTEM
# =========================

# Default monthly limit per user (if not overridden)
# 0 মানে: ডিফল্টভাবে কেউই request পাঠাতে পারবে না,
# admin যখন limit সেট করবে তখন থেকেই সেই user use করতে পারবে।
DEFAULT_MONTHLY_LIMIT = 0

# Supported like packages / APIs
LIKE_TYPES = (100, 200)
# Per-user custom limits: user_id -> {100: limit, 200: limit}
USER_LIMITS = {}

# Monthly usage: (user_id, month_str, like_type) -> count
USER_USAGE = {}

# Extra admins promoted by the owner: user_id set
ADMIN_USERS = set()

# Super admins can do everything admins can, including creating admins/super admins
SUPER_ADMIN_USERS = set()

# Pending super admin verification: user_id -> invited_by_user_id
PENDING_SUPER_ADMINS = {}

# Verified super admin credentials kept in memory
SUPER_ADMIN_CREDENTIALS = {}

mongo_client = None
mongo_db = None
state_collection = None


def init_mongodb():
    """Initialize MongoDB client/collection."""
    global mongo_client, mongo_db, state_collection

    try:
        mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command('ping')
        mongo_db = mongo_client[MONGODB_DB]
        state_collection = mongo_db[MONGODB_STATE_COLLECTION]
        print(f"✅ MongoDB connected: {MONGODB_URI} / {MONGODB_DB}")
    except PyMongoError as e:
        mongo_client = None
        mongo_db = None
        state_collection = None
        print(f"⚠️ MongoDB connection failed: {e}")


def load_state():
    """Load persistent bot state from MongoDB."""
    global USER_LIMITS, USER_USAGE, ADMIN_USERS, SUPER_ADMIN_USERS, PENDING_SUPER_ADMINS, SUPER_ADMIN_CREDENTIALS

    if state_collection is None:
        return

    try:
        data = state_collection.find_one({'_id': 'global_state'})
        if not data:
            return

        USER_LIMITS = {
            int(user_id): {int(k): int(v) for k, v in limits.items()}
            for user_id, limits in data.get('user_limits', {}).items()
        }
        USER_USAGE = {
            (int(item['user_id']), item['month'], int(item['like_type'])): int(item['count'])
            for item in data.get('user_usage', [])
        }
        ADMIN_USERS = set(int(user_id) for user_id in data.get('admin_users', []))
        SUPER_ADMIN_USERS = set(int(user_id) for user_id in data.get('super_admin_users', []))
        PENDING_SUPER_ADMINS = {
            int(user_id): int(invited_by)
            for user_id, invited_by in data.get('pending_super_admins', {}).items()
        }
        SUPER_ADMIN_CREDENTIALS = {
            int(user_id): creds
            for user_id, creds in data.get('super_admin_credentials', {}).items()
        }
        SUPER_ADMIN_USERS.update(SUPER_ADMIN_CREDENTIALS.keys())
        for creds in SUPER_ADMIN_CREDENTIALS.values():
            verified_account_id = creds.get('verified_account_id')
            if verified_account_id is not None:
                SUPER_ADMIN_USERS.add(int(verified_account_id))
                ADMIN_USERS.add(int(verified_account_id))
    except Exception as e:
        print(f"⚠️ Failed to load state: {e}")


def save_state():
    """Save persistent bot state to MongoDB."""
    if state_collection is None:
        return

    try:
        data = {
            '_id': 'global_state',
            'user_limits': {
                str(user_id): {str(k): v for k, v in limits.items()}
                for user_id, limits in USER_LIMITS.items()
            },
            'user_usage': [
                {
                    'user_id': user_id,
                    'month': month,
                    'like_type': like_type,
                    'count': count,
                }
                for (user_id, month, like_type), count in USER_USAGE.items()
            ],
            'admin_users': sorted(ADMIN_USERS),
            'super_admin_users': sorted(SUPER_ADMIN_USERS),
            'pending_super_admins': {
                str(user_id): invited_by
                for user_id, invited_by in PENDING_SUPER_ADMINS.items()
            },
            'super_admin_credentials': {
                str(user_id): creds
                for user_id, creds in SUPER_ADMIN_CREDENTIALS.items()
            },
        }

        state_collection.replace_one({'_id': 'global_state'}, data, upsert=True)
    except Exception as e:
        print(f"⚠️ Failed to save state: {e}")


def _this_month_str():
    """Return current month as YYYY-MM in UTC."""
    return datetime.utcnow().strftime('%Y-%m')


def _usage_key(user_id: int, like_type: int) -> tuple:
    """Build usage dict key for a user, current month, and like type."""
    return (user_id, _this_month_str(), like_type)


def get_user_limit(user_id: int, like_type: int) -> int:
    """Get a user's configured limit for a specific like type."""
    limits = USER_LIMITS.get(user_id, {})
    return limits.get(like_type, DEFAULT_MONTHLY_LIMIT)


async def get_sender_identity(event):
    """Resolve sender id and username reliably."""
    sender_id = event.sender_id
    sender_username = None

    try:
        sender = await event.get_sender()
        if sender is not None:
            sender_id = getattr(sender, 'id', sender_id)
            sender_username = getattr(sender, 'username', None)
    except Exception:
        pass

    return sender_id, sender_username.lower() if sender_username else None


def get_event_client(event):
    """Return the active Telegram client for this event."""
    return getattr(event, 'client', MAIN_CLIENT)


def is_known_super_admin_identity(sender_id: int, sender_username: str | None) -> bool:
    """Check super admin access by stored id or verified credential identity."""
    if sender_id in SUPER_ADMIN_USERS:
        return True

    for stored_user_id, creds in SUPER_ADMIN_CREDENTIALS.items():
        verified_account_id = creds.get('verified_account_id')
        verified_username = creds.get('verified_account_username')

        if sender_id is not None and verified_account_id == sender_id:
            SUPER_ADMIN_USERS.add(stored_user_id)
            SUPER_ADMIN_USERS.add(sender_id)
            return True

        if sender_username and verified_username and verified_username.lower() == sender_username:
            if verified_account_id is not None:
                SUPER_ADMIN_USERS.add(int(verified_account_id))
            SUPER_ADMIN_USERS.add(stored_user_id)
            return True

    return False


async def is_owner(event) -> bool:
    """Return True if the sender is the account owner running the bot."""
    me = await MAIN_CLIENT.get_me()
    sender_id, _ = await get_sender_identity(event)
    return sender_id == me.id


async def is_super_admin(event) -> bool:
    """Return True for owner or verified super admins."""
    if await is_owner(event):
        return True

    sender_id, sender_username = await get_sender_identity(event)
    return is_known_super_admin_identity(sender_id, sender_username)


async def is_admin(event) -> bool:
    """Return True for owner, super admins, or delegated admins."""
    if await is_super_admin(event):
        return True

    sender_id, _ = await get_sender_identity(event)
    return sender_id in ADMIN_USERS


async def get_access_role(event) -> str:
    """Return the current access role label for the sender."""
    if await is_owner(event):
        return "Owner"
    if await is_super_admin(event):
        return "Super Admin"
    if await is_admin(event):
        return "Admin"
    return "User"


async def build_access_denied_message(event, required_role: str, command_name: str) -> str:
    """Build a detailed permission error for easier debugging."""
    sender_id, sender_username = await get_sender_identity(event)
    role = await get_access_role(event)

    return (
        f"❌ `{command_name}` command is not working for this account.\n\n"
        f"Required Role: `{required_role}`\n"
        f"Detected Role: `{role}`\n"
        f"Sender ID: `{sender_id}`\n"
        f"Username: `{('@' + sender_username) if sender_username else 'N/A'}`\n\n"
        "If this should be a super admin account, run `myaccess` first."
    )


async def log_access_check(event, command_name: str):
    """Print runtime access details for debugging permission issues."""
    sender_id, sender_username = await get_sender_identity(event)
    role = await get_access_role(event)
    print(
        f"[ACCESS] command={command_name} sender_id={sender_id} "
        f"username={sender_username or 'N/A'} role={role} "
        f"admins={sorted(ADMIN_USERS)} super_admins={sorted(SUPER_ADMIN_USERS)}"
    )


async def set_admin_for_user(event, target_user_id: int):
    """Promote a user to admin."""
    ADMIN_USERS.add(target_user_id)
    save_state()
    await event.reply(
        f"✅ Admin access granted to user `{target_user_id}`\n"
        "They can now use: `setlimit`, `resetlimit`, `alllimit`, and `mylimit`."
    )


async def remove_admin_for_user(event, target_user_id: int):
    """Remove a normal admin."""
    if target_user_id in SUPER_ADMIN_USERS:
        await event.reply(
            f"❌ User `{target_user_id}` is a super admin. Use a separate super-admin removal flow for that."
        )
        return

    if target_user_id not in ADMIN_USERS:
        await event.reply(f"❌ User `{target_user_id}` is not a normal admin.")
        return

    ADMIN_USERS.discard(target_user_id)
    save_state()
    await event.reply(f"✅ Admin access removed for user `{target_user_id}`")


async def start_super_admin_verification(event, target_user_id: int):
    """Start super admin verification flow for a user."""
    PENDING_SUPER_ADMINS[target_user_id] = event.sender_id
    save_state()
    await event.reply(
        f"✅ Super admin request started for user `{target_user_id}`\n"
        "Now that user must send:\n"
        "`superauth <api_id> <api_hash> <session_string>`"
    )


async def validate_super_admin_credentials(api_id: int, api_hash: str, session_string: str):
    """Validate Telegram credentials by opening a temporary client."""
    temp_client = TelegramClient(StringSession(session_string), api_id, api_hash)

    try:
        await temp_client.connect()
        if not await temp_client.is_user_authorized():
            return False, "Session string is not authorized.", None

        me = await temp_client.get_me()
        return True, None, me
    except Exception as e:
        return False, str(e), None
    finally:
        await temp_client.disconnect()


async def approve_super_admin(event, api_id: int, api_hash: str, session_string: str):
    """Approve a pending user as super admin if credentials validate."""
    user_id, sender_username = await get_sender_identity(event)
    if is_known_super_admin_identity(user_id, sender_username):
        await event.reply("✅ You are already a super admin.")
        return

    if user_id not in PENDING_SUPER_ADMINS:
        await event.reply("❌ আপনার জন্য কোনো pending super admin request নেই.")
        return

    ok, error_message, me = await validate_super_admin_credentials(api_id, api_hash, session_string)
    if not ok:
        await event.reply(f"❌ Super admin verification failed.\nError: `{error_message}`")
        return

    SUPER_ADMIN_USERS.add(user_id)
    ADMIN_USERS.add(user_id)
    SUPER_ADMIN_CREDENTIALS[user_id] = {
        'api_id': api_id,
        'api_hash': api_hash,
        'session_string': session_string,
        'verified_account_id': getattr(me, 'id', None),
        'verified_account_username': getattr(me, 'username', None),
    }
    del PENDING_SUPER_ADMINS[user_id]
    save_state()

    verified_label = f"@{me.username}" if getattr(me, 'username', None) else str(getattr(me, 'id', 'N/A'))
    await start_super_admin_clients()
    await event.reply(
        "✅ Super admin verification successful.\n"
        f"Verified account: `{verified_label}`\n"
        "You can now use all admin commands and also `setadmin` / `setsuperadmin`."
    )


async def check_limit(event, like_type: int) -> bool:
    """
    Check if user still has quota this month.
    NOTE: This does NOT increment usage. Increment only on success.
    """
    user_id = event.sender_id
    key = _usage_key(user_id, like_type)

    # Get user's custom limit or default
    limit = get_user_limit(user_id, like_type)
    count = USER_USAGE.get(key, 0)

    if count >= limit:
        await event.reply(
            f"⚠️ এই মাসের limit শেষ হয়ে গেছে!\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"📅 Month: `{_this_month_str()}`\n"
            f"🎯 Like Type: `{like_type}`\n"
            f"📌 Monthly limit: `{limit}` request"
        )
        return False
    return True


def increment_usage_for_user(user_id: int, like_type: int):
    """Increment this month's usage counter for a specific user and like type."""
    key = _usage_key(user_id, like_type)
    USER_USAGE[key] = USER_USAGE.get(key, 0) + 1
    save_state()


async def reset_monthly_usage_for_user(event, target_user_id: int):
    """Reset this month's usage counter for a specific user for all like types."""
    for like_type in LIKE_TYPES:
        key = _usage_key(target_user_id, like_type)
        if key in USER_USAGE:
            del USER_USAGE[key]
    save_state()
    await event.reply(
        f"✅ This month's usage reset for user `{target_user_id}` "
        f"for month `{_this_month_str()}`"
    )


async def set_limit_for_user(event, target_user_id: int, limit: int, like_type: int):
    """Set custom monthly limit for a specific user and like type."""
    user_limits = USER_LIMITS.setdefault(target_user_id, {})
    user_limits[like_type] = limit
    save_state()
    await event.reply(
        f"✅ Monthly limit set to `{limit}` for user `{target_user_id}`\n"
        f"🎯 Like type: `{like_type}`"
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


RESPONSE_FOOTER = "\n━━━━━━━━━━━━━━━━━━━━\n🤖 Powered by @Mohammadrobayet"


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


async def call_ff_api(uid, like_type: int):
    """Make GET request to the selected FF like API."""
    if like_type == 200:
        url = f"https://free-fire-like-api-bd12.vercel.app/like?uid={uid}&server_name=BD"
    else:
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


@client.on(events.NewMessage(pattern=r'(?i)^/?like\s+(\d+)\s+(100|200)$'))
async def like_command_handler(event):
    """Handle like <uid> <100|200> command."""
    match = re.match(r'(?i)^/?like\s+(\d+)\s+(100|200)$', event.raw_text.strip())
    if not match:
        await event.reply("❌ Invalid format. Use: `/like <uid> 100` or `/like <uid> 200`")
        return

    uid = match.group(1)
    like_type = int(match.group(2))

    if get_user_limit(event.sender_id, like_type) <= 0:
        await event.reply(
            f"❌ আপনার `{like_type}` like package limit set করা নেই.\n\n"
            "Admin example:\n"
            f"`setlimit 5 @username {like_type}`"
        )
        return

    # Check monthly limit for this user (increment only on success)
    if not await check_limit(event, like_type):
        return

    # Send processing message
    try:
        processing_msg = await event.reply(
            f"⏳ Processing `{like_type}` like request for UID: {uid}..."
        )
    except Exception as e:
        print(f"Error replying: {e}")
        return

    # Call API
    result = await call_ff_api(uid, like_type)

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

        formatted_message = format_response(result) + f"\n🎯 Like Type Used: {like_type}"

        if likes_added >= THRESHOLD:
            # SUCCESS -> count this request
            increment_usage_for_user(event.sender_id, like_type)
        else:
            # Not enough likes added -> don't count towards limit, just a short note
            formatted_message += "\n\n✅ **Limit refunded**"

        formatted_message += RESPONSE_FOOTER

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
`/like <uid> <100|200>`

**Example:**
`/like 1711537287 100`

**Note:** This bot uses your Telegram account to send commands."""
    else:
        help_message = """🤖 **Free Fire Like Bot**

Send likes to Free Fire players using their UID.

**Usage:**
`/like <uid> <100|200>` or `like <uid> <100|200>`

**Example:**
`/like 1711537287 200`

**Note:** This bot uses your Telegram account to send commands."""

    await event.reply(help_message)


@client.on(events.NewMessage(pattern=r'(?i)^/?help$'))
async def help_command_handler(event):
    """Handle help command - works in both groups and private (with or without /)"""
    is_group = not event.is_private
    
    can_manage = await is_admin(event)

    # ---------- User Commands ----------
    if is_group:
        user_cmds = """👥 **User Commands (Group & Private)**

- `like <uid> <100|200>` – Free Fire UID-এ selected package-এর like পাঠাবে
- `start` – Bot সম্পর্কে basic তথ্য দেখাবে
- `help` – এই help message দেখাবে
- `mylimit` – এই মাসে 100/200 package usage দেখাবে

**Example:**
`like 1711537287 100`"""
    else:
        user_cmds = """👤 **User Commands (Private & Group)**

- `like <uid> <100|200>` / `/like <uid> <100|200>` – Free Fire UID-এ selected package-এর like পাঠাবে
- `start` / `/start` – Bot সম্পর্কে basic তথ্য
- `help` / `/help` – এই help message
- `mylimit` / `/mylimit` – এই মাসের 100/200 package usage দেখাবে

**Example:**
`like 1711537287 200`"""

    # ---------- Admin / Owner Commands ----------
    # Note: এগুলো শুধু bot owner (যে account দিয়ে bot চালাচ্ছেন) use করতে পারবে
    admin_cmds = """
    
🛠 **Admin Commands**

- `setadmin @username`
  ➤ নতুন admin বানাবে
  উদাহরণ: `setadmin @testuser`

- `removeadmin @username`
  ➤ normal admin remove করবে
  উদাহরণ: `removeadmin @testuser`

- `setsuperadmin @username`
  ➤ pending super admin request শুরু করবে
  উদাহরণ: `setsuperadmin @testuser`

- `superauth <api_id> <api_hash> <session_string>`
  ➤ invited user নিজের credentials submit করে super admin verify করবে

- `setlimit <n> <100|200>`  
  ➤ নিজের monthly limit `n` set করবে selected like package-এর জন্য  
  উদাহরণ: `setlimit 10 100`

- `setlimit <n> @username <100|200>`  
  ➤ নির্দিষ্ট user-এর জন্য `100` বা `200` like package set করবে  
  উদাহরণ: `setlimit 5 @testuser 200`

- `resetlimit` / `/resetlimit`  
  ➤ নিজের এই মাসের usage reset করবে

- `resetlimit @username`  
  ➤ ঐ user-এর এই মাসের usage reset করবে

- `alllimit` / `/alllimit`  
  ➤ এই মাসের জন্য সব user-এর 100/200 used / limit / remaining list দেখাবে
"""

    # Owner/admin হলে full help, regular user হলে শুধু user commands
    if can_manage:
        help_message = f"""📖 **Help**

{user_cmds}{admin_cmds}

⚙️ **Note:**
- Commands case-insensitive: `like`, `Like`, `LIKE` সব কাজ করবে
- Slash (`/`) সহ বা ছাড়া – দু’ভাবেই command দেওয়া যাবে
- Valid UID numeric হতে হবে
- `setadmin` এবং `setsuperadmin` owner বা verified super admin use করতে পারবে
"""
    else:
        help_message = f"""📖 **Help**

{user_cmds}

⚙️ **Note:**
- Commands case-insensitive: `like`, `Like`, `LIKE` সব কাজ করবে
- Slash (`/`) সহ বা ছাড়া – দু’ভাবেই command দেওয়া যাবে
- Valid UID numeric হতে হবে
"""
    await event.reply(help_message)


# =========================
# LIMIT CONTROL COMMANDS
# =========================


@client.on(events.NewMessage(pattern=r'(?i)^/?setadmin\s+(@?\w+)$'))
async def setadmin_command_handler(event):
    """
    Promote a user to admin.
    Usage:
      /setadmin @username
    """
    await log_access_check(event, "setadmin")
    if not await is_super_admin(event):
        await event.reply(await build_access_denied_message(event, "Super Admin", "setadmin"))
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?setadmin\s+(@?\w+)$', text)
    if not match:
        await event.reply("❌ Invalid format.\nUsage: `/setadmin @username`")
        return

    username = match.group(1)
    active_client = get_event_client(event)

    try:
        entity = await active_client.get_entity(username)
        target_user_id = entity.id
    except Exception as e:
        await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
        return

    await set_admin_for_user(event, target_user_id)


@client.on(events.NewMessage(pattern=r'(?i)^/?removeadmin\s+(@?\w+)$'))
async def removeadmin_command_handler(event):
    """
    Remove a normal admin.
    Usage:
      /removeadmin @username
    """
    await log_access_check(event, "removeadmin")
    if not await is_super_admin(event):
        await event.reply(await build_access_denied_message(event, "Super Admin", "removeadmin"))
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?removeadmin\s+(@?\w+)$', text)
    if not match:
        await event.reply("❌ Invalid format.\nUsage: `/removeadmin @username`")
        return

    username = match.group(1)
    active_client = get_event_client(event)

    try:
        entity = await active_client.get_entity(username)
        target_user_id = entity.id
    except Exception as e:
        await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
        return

    await remove_admin_for_user(event, target_user_id)


@client.on(events.NewMessage(pattern=r'(?i)^/?setsuperadmin\s+(@?\w+)$'))
async def setsuperadmin_command_handler(event):
    """
    Start super admin verification for a user.
    Usage:
      /setsuperadmin @username
    """
    await log_access_check(event, "setsuperadmin")
    if not await is_super_admin(event):
        await event.reply(await build_access_denied_message(event, "Super Admin", "setsuperadmin"))
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?setsuperadmin\s+(@?\w+)$', text)
    if not match:
        await event.reply("❌ Invalid format.\nUsage: `/setsuperadmin @username`")
        return

    username = match.group(1)
    active_client = get_event_client(event)

    try:
        entity = await active_client.get_entity(username)
        target_user_id = entity.id
    except Exception as e:
        await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
        return

    await start_super_admin_verification(event, target_user_id)


@client.on(events.NewMessage(pattern=r'(?i)^/?superauth\s+(\d+)\s+([A-Za-z0-9]+)\s+(.+)$'))
async def superauth_command_handler(event):
    """
    Submit credentials for pending super admin verification.
    Usage:
      /superauth <api_id> <api_hash> <session_string>
    """
    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?superauth\s+(\d+)\s+([A-Za-z0-9]+)\s+(.+)$', text)
    if not match:
        await event.reply(
            "❌ Invalid format.\n"
            "Usage: `/superauth <api_id> <api_hash> <session_string>`"
        )
        return

    api_id = int(match.group(1))
    api_hash = match.group(2)
    session_string = match.group(3).strip()

    processing_msg = await event.reply("⏳ Verifying super admin credentials...")
    try:
        await approve_super_admin(event, api_id, api_hash, session_string)
        await processing_msg.delete()
    except Exception as e:
        try:
            await processing_msg.edit(f"❌ Super admin verification error.\nError: `{e}`")
        except Exception:
            await event.reply(f"❌ Super admin verification error.\nError: `{e}`")


@client.on(events.NewMessage(pattern=r'(?i)^/?setlimit\s+(\d+)(?:\s+(@?\w+))?\s+(100|200)$'))
async def setlimit_command_handler(event):
    """
    Set monthly limit for a user.
    Usage:
      /setlimit 5 100           -> set your own 100-like monthly limit
      /setlimit 5 @username 200 -> set 200-like monthly limit for @username
    """
    # Allow owner and delegated admins
    await log_access_check(event, "setlimit")
    if not await is_admin(event):
        await event.reply(await build_access_denied_message(event, "Admin", "setlimit"))
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?setlimit\s+(\d+)(?:\s+(@?\w+))?\s+(100|200)$', text)
    if not match:
        await event.reply(
            "❌ Invalid format.\n"
            "Usage: `/setlimit 5 100` or `/setlimit 5 @username 200`"
        )
        return

    limit = int(match.group(1))
    username = match.group(2)
    like_type = int(match.group(3))

    # Determine target user
    if username:
        active_client = get_event_client(event)
        try:
            entity = await active_client.get_entity(username)
            target_user_id = entity.id
        except Exception as e:
            await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
            return
    else:
        target_user_id, _ = await get_sender_identity(event)

    await set_limit_for_user(event, target_user_id, limit, like_type)


@client.on(events.NewMessage(pattern=r'(?i)^/?resetlimit(?:\s+(@?\w+))?$'))
async def resetlimit_command_handler(event):
    """
    Reset this month's usage counter for a user.
    Usage:
      /resetlimit           -> reset your own usage for this month
      /resetlimit @username -> reset usage for @username this month
    """
    # Allow owner and delegated admins
    await log_access_check(event, "resetlimit")
    if not await is_admin(event):
        await event.reply(await build_access_denied_message(event, "Admin", "resetlimit"))
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?resetlimit(?:\s+(@?\w+))?$', text)
    if not match:
        await event.reply("❌ Invalid format.\nUsage: `/resetlimit` or `/resetlimit @username`")
        return

    username = match.group(1)

    # Determine target user
    if username:
        active_client = get_event_client(event)
        try:
            entity = await active_client.get_entity(username)
            target_user_id = entity.id
        except Exception as e:
            await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
            return
    else:
        target_user_id, _ = await get_sender_identity(event)

    await reset_monthly_usage_for_user(event, target_user_id)


@client.on(events.NewMessage(pattern=r'(?i)^/?mylimit$'))
async def mylimit_command_handler(event):
    """
    Show current limit and this month's usage for the caller.
    Usage: /mylimit
    """
    user_id, _ = await get_sender_identity(event)
    lines = [
        "📊 **Your Limit Status**\n",
        f"👤 User ID: `{user_id}`",
        f"📅 Month: `{_this_month_str()}`",
        ""
    ]

    for like_type in LIKE_TYPES:
        key = _usage_key(user_id, like_type)
        limit = get_user_limit(user_id, like_type)
        used = USER_USAGE.get(key, 0)
        remaining = max(limit - used, 0)
        lines.append(
            f"🔥 `{like_type}` Like Package\n"
            f"✅ Used: `{used}` request(s)\n"
            f"📌 Monthly Limit: `{limit}` request(s)\n"
            f"🔄 Remaining: `{remaining}` request(s)\n"
        )

    await event.reply("\n".join(lines))


@client.on(events.NewMessage(pattern=r'(?i)^/?myaccess$'))
async def myaccess_command_handler(event):
    """Show the sender's current access level."""
    await log_access_check(event, "myaccess")
    sender_id, sender_username = await get_sender_identity(event)
    owner = await is_owner(event)
    super_admin = await is_super_admin(event)
    admin = await is_admin(event)

    if owner:
        role = "Owner"
    elif super_admin:
        role = "Super Admin"
    elif admin:
        role = "Admin"
    else:
        role = "User"

    await event.reply(
        f"🔐 **Your Access**\n\n"
        f"👤 User ID: `{sender_id}`\n"
        f"🏷 Username: `{('@' + sender_username) if sender_username else 'N/A'}`\n"
        f"🛡 Role: `{role}`"
    )


@client.on(events.NewMessage(pattern=r'(?i)^/?alllimit$'))
async def alllimit_command_handler(event):
    """
    Show this month's usage & limits for all users (owner only).
    Usage: alllimit / /alllimit
    """
    # Allow owner and delegated admins
    await log_access_check(event, "alllimit")
    if not await is_admin(event):
        await event.reply(await build_access_denied_message(event, "Admin", "alllimit"))
        return

    this_month = _this_month_str()

    # Collect all user_ids from limits and usage
    user_ids = set(USER_LIMITS.keys())
    for (uid, month_str), _ in USER_USAGE.items():
        if month_str == this_month:
            user_ids.add(uid)

    if not user_ids:
        await event.reply("📊 এই মাসে এখনও কেউ কোনো request পাঠায়নি।")
        return

    lines = [f"📊 **All Users Limit Status**\n📅 Month: `{this_month}`\n"]

    # Pre-fetch entities for better names (best-effort)
    name_cache = {}
    active_client = get_event_client(event)
    for uid in user_ids:
        try:
            entity = await active_client.get_entity(uid)
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
        display_name = name_cache.get(uid, str(uid))
        user_block = [
            f"👤 User: **{display_name}** (`{uid}`)"
        ]

        for like_type in LIKE_TYPES:
            key = (uid, this_month, like_type)
            limit = get_user_limit(uid, like_type)
            used = USER_USAGE.get(key, 0)
            remaining = max(limit - used, 0)
            user_block.append(
                f"🔥 `{like_type}` Like: used `{used}` / `{limit}` | remaining `{remaining}`"
            )

        lines.append("\n".join(user_block) + "\n")

    msg = "\n".join(lines)
    await event.reply(msg)


HANDLER_SPECS = [
    (like_command_handler, r'(?i)^/?like\s+(\d+)\s+(100|200)$'),
    (start_command_handler, r'(?i)^/?start$'),
    (help_command_handler, r'(?i)^/?help$'),
    (setadmin_command_handler, r'(?i)^/?setadmin\s+(@?\w+)$'),
    (removeadmin_command_handler, r'(?i)^/?removeadmin\s+(@?\w+)$'),
    (setsuperadmin_command_handler, r'(?i)^/?setsuperadmin\s+(@?\w+)$'),
    (superauth_command_handler, r'(?i)^/?superauth\s+(\d+)\s+([A-Za-z0-9]+)\s+(.+)$'),
    (setlimit_command_handler, r'(?i)^/?setlimit\s+(\d+)(?:\s+(@?\w+))?\s+(100|200)$'),
    (resetlimit_command_handler, r'(?i)^/?resetlimit(?:\s+(@?\w+))?$'),
    (mylimit_command_handler, r'(?i)^/?mylimit$'),
    (myaccess_command_handler, r'(?i)^/?myaccess$'),
    (alllimit_command_handler, r'(?i)^/?alllimit$'),
]


def register_handlers(target_client):
    """Attach all command handlers to a Telegram client."""
    for handler, pattern in HANDLER_SPECS:
        target_client.add_event_handler(handler, events.NewMessage(pattern=pattern))


async def start_super_admin_clients():
    """Start dedicated Telegram clients for verified super admins."""
    for user_id, creds in SUPER_ADMIN_CREDENTIALS.items():
        verified_account_id = creds.get('verified_account_id')
        api_id = creds.get('api_id')
        api_hash = creds.get('api_hash')
        session_string = creds.get('session_string')

        if not api_id or not api_hash or not session_string:
            print(f"⚠️ Skipping super admin {user_id}: incomplete credentials")
            continue

        if user_id in SUPER_ADMIN_CLIENTS:
            continue

        try:
            super_client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
            register_handlers(super_client)
            await super_client.start()

            me = await super_client.get_me()
            SUPER_ADMIN_CLIENTS[user_id] = super_client
            print(
                f"✅ Super admin client started: user_id={user_id} "
                f"account_id={getattr(me, 'id', 'N/A')} "
                f"username={getattr(me, 'username', 'N/A')}"
            )

            if verified_account_id is not None:
                SUPER_ADMIN_USERS.add(int(verified_account_id))
                ADMIN_USERS.add(int(verified_account_id))
        except Exception as e:
            print(f"⚠️ Failed to start super admin client for {user_id}: {e}")


async def main():
    """Main function to start the bot and a minimal web server (for Render Web Service)."""
    print("🚀 Starting Free Fire Like Bot...")
    init_mongodb()
    load_state()
    print(
        f"📦 Loaded state: {len(ADMIN_USERS)} admin(s), "
        f"{len(SUPER_ADMIN_USERS)} super admin(s)"
    )

    # Start the Telegram client
    await MAIN_CLIENT.start()

    # SESSION_STRING না থাকলে শুধু তখনই ফোন/কোড চাইবে (লোকাল চালানোর সময়)
    if not SESSION_STRING:
        if not await MAIN_CLIENT.is_user_authorized():
            print("📱 Please authorize this session:")
            phone = input("Enter your phone number: ")
            await MAIN_CLIENT.send_code_request(phone)

            try:
                code = input("Enter the code you received: ")
                await MAIN_CLIENT.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = input("Enter your 2FA password: ")
                await MAIN_CLIENT.sign_in(password=password)

    await start_super_admin_clients()

    # ----------------------
    # Minimal HTTP server (for Render Web Service port binding)
    # ----------------------
    async def health(request):
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    port = int(os.getenv("PORT", 8000))  # Render will set PORT
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"🌐 HTTP server running on port {port}")
    print("✅ Bot is running! Send /start to begin.")
    print("Press Ctrl+C to stop.")

    # Keep the bot running
    disconnect_tasks = [MAIN_CLIENT.run_until_disconnected()]
    disconnect_tasks.extend(
        super_client.run_until_disconnected()
        for super_client in SUPER_ADMIN_CLIENTS.values()
    )
    await asyncio.gather(*disconnect_tasks)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
