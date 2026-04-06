import os
import asyncio
import re
import json
from decimal import Decimal, InvalidOperation, getcontext
from datetime import datetime
from pathlib import Path
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

# Recent successful like activity for dashboard
REQUEST_ACTIVITY = []

# Cached user profile labels: user_id -> {username, name}
USER_PROFILES = {}

# Hierarchy ownership: child_user_id -> manager_user_id
USER_MANAGERS = {}

# Extra admins promoted by the owner: user_id set
ADMIN_USERS = set()

# Super admins can create admins inside their own branch
SUPER_ADMIN_USERS = set()

# Pending super admin verification: user_id -> invited_by_user_id
PENDING_SUPER_ADMINS = {}

# Verified super admin credentials kept in memory
SUPER_ADMIN_CREDENTIALS = {}

mongo_client = None
mongo_db = None
state_collection = None
DASHBOARD_DIR = Path(__file__).resolve().parent
getcontext().prec = 28

CALCULATOR_ALLOWED_PATTERN = re.compile(r'^[\d\s+\-*/().%]+$')
CALCULATOR_TOKEN_PATTERN = re.compile(r'\d+(?:\.\d+)?|[()+\-*/%]')


class CalculatorError(Exception):
    """Raised when a calculator expression cannot be parsed safely."""


class CalculatorValue:
    """Stores a numeric value and whether it came from a percent literal."""

    def __init__(self, value: Decimal, is_percent: bool = False):
        self.value = value
        self.is_percent = is_percent


class CalculatorParser:
    """Minimal safe parser for +, -, *, /, (), and postfix %."""

    def __init__(self, expression: str):
        self.tokens = CALCULATOR_TOKEN_PATTERN.findall(expression.replace(' ', ''))
        self.index = 0

    def parse(self) -> Decimal:
        if not self.tokens:
            raise CalculatorError("Empty expression")

        result = self.parse_expression()
        if self.index != len(self.tokens):
            raise CalculatorError("Unexpected token")
        return result.value

    def current_token(self) -> str | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def consume_token(self) -> str | None:
        token = self.current_token()
        if token is not None:
            self.index += 1
        return token

    def parse_expression(self) -> CalculatorValue:
        left = self.parse_term()

        while self.current_token() in {'+', '-'}:
            operator = self.consume_token()
            right = self.parse_term()

            if operator == '+':
                if right.is_percent:
                    left = CalculatorValue(left.value + (left.value * right.value))
                else:
                    left = CalculatorValue(left.value + right.value)
            else:
                if right.is_percent:
                    left = CalculatorValue(left.value - (left.value * right.value))
                else:
                    left = CalculatorValue(left.value - right.value)

        return left

    def parse_term(self) -> CalculatorValue:
        left = self.parse_factor()

        while self.current_token() in {'*', '/'}:
            operator = self.consume_token()
            right = self.parse_factor()

            if operator == '*':
                left = CalculatorValue(left.value * right.value)
            else:
                if right.value == 0:
                    raise CalculatorError("Division by zero")
                left = CalculatorValue(left.value / right.value)

        return left

    def parse_factor(self) -> CalculatorValue:
        token = self.current_token()

        if token in {'+', '-'}:
            operator = self.consume_token()
            value = self.parse_factor()
            if operator == '-':
                return CalculatorValue(-value.value, is_percent=value.is_percent)
            return value

        if token == '(':
            self.consume_token()
            value = self.parse_expression()
            if self.consume_token() != ')':
                raise CalculatorError("Missing closing parenthesis")
        else:
            if token is None:
                raise CalculatorError("Unexpected end of expression")

            self.consume_token()
            try:
                value = CalculatorValue(Decimal(token))
            except InvalidOperation as exc:
                raise CalculatorError("Invalid number") from exc

        while self.current_token() == '%':
            self.consume_token()
            value = CalculatorValue(value.value / Decimal('100'), is_percent=True)

        return value


def is_calculator_expression(text: str) -> bool:
    """Return True when the message looks like a plain arithmetic expression."""
    candidate = text.strip()
    if not candidate or candidate.startswith('/'):
        return False
    if '\n' in candidate or '\r' in candidate:
        return False
    if not any(ch.isdigit() for ch in candidate):
        return False
    if not CALCULATOR_ALLOWED_PATTERN.fullmatch(candidate):
        return False
    return any(op in candidate for op in ('+', '-', '*', '/', '%', '(', ')'))


def evaluate_calculator_expression(expression: str) -> Decimal:
    """Safely evaluate a calculator expression."""
    parser = CalculatorParser(expression)
    return parser.parse()


def format_calculator_result(value: Decimal) -> str:
    """Render Decimal results without unnecessary trailing zeroes."""
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal('1')))
    return format(normalized, 'f').rstrip('0').rstrip('.')


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
    global USER_LIMITS, USER_USAGE, USER_MANAGERS, ADMIN_USERS, SUPER_ADMIN_USERS
    global PENDING_SUPER_ADMINS, SUPER_ADMIN_CREDENTIALS, REQUEST_ACTIVITY, USER_PROFILES

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
        REQUEST_ACTIVITY = list(data.get('request_activity', []))
        USER_PROFILES = {
            int(user_id): profile
            for user_id, profile in data.get('user_profiles', {}).items()
        }
        USER_MANAGERS = {
            int(user_id): int(manager_id)
            for user_id, manager_id in data.get('user_managers', {}).items()
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
            'user_managers': {
                str(user_id): manager_id
                for user_id, manager_id in USER_MANAGERS.items()
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
            'request_activity': REQUEST_ACTIVITY[-200:],
            'user_profiles': {
                str(user_id): profile
                for user_id, profile in USER_PROFILES.items()
            },
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


def _utc_timestamp_str():
    """Return UTC timestamp for activity history."""
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')


def _usage_key(user_id: int, like_type: int) -> tuple:
    """Build usage dict key for a user, current month, and like type."""
    return (user_id, _this_month_str(), like_type)


def get_user_limit(user_id: int, like_type: int) -> int:
    """Get a user's configured limit for a specific like type."""
    limits = USER_LIMITS.get(user_id, {})
    return limits.get(like_type, DEFAULT_MONTHLY_LIMIT)


def get_manager_id(user_id: int) -> int | None:
    """Return direct manager id for a user if assigned."""
    return USER_MANAGERS.get(user_id)


def set_manager_for_user(target_user_id: int, manager_user_id: int | None):
    """Assign or clear a user's direct manager."""
    if manager_user_id is None:
        USER_MANAGERS.pop(target_user_id, None)
    else:
        USER_MANAGERS[target_user_id] = manager_user_id


def get_direct_children(manager_user_id: int) -> set[int]:
    """Return direct child users managed by a specific account."""
    return {
        user_id
        for user_id, parent_id in USER_MANAGERS.items()
        if parent_id == manager_user_id
    }


def get_descendant_user_ids(manager_user_id: int) -> set[int]:
    """Return all users nested below a specific manager."""
    descendants = set()
    queue = list(get_direct_children(manager_user_id))

    while queue:
        user_id = queue.pop(0)
        if user_id in descendants:
            continue
        descendants.add(user_id)
        queue.extend(get_direct_children(user_id))

    return descendants


def is_managed_by(manager_user_id: int, target_user_id: int) -> bool:
    """Return True if target exists inside manager's hierarchy."""
    current_user_id = get_manager_id(target_user_id)
    visited = set()

    while current_user_id is not None and current_user_id not in visited:
        if current_user_id == manager_user_id:
            return True
        visited.add(current_user_id)
        current_user_id = get_manager_id(current_user_id)

    return False


def get_direct_child_limit_sum(manager_user_id: int, like_type: int, exclude_user_id: int | None = None) -> int:
    """Return total limit assigned to direct children for one package."""
    total = 0
    for child_user_id in get_direct_children(manager_user_id):
        if exclude_user_id is not None and child_user_id == exclude_user_id:
            continue
        total += get_user_limit(child_user_id, like_type)
    return total


def get_user_used_count(user_id: int, like_type: int) -> int:
    """Return current month's usage count for a user and package."""
    return USER_USAGE.get(_usage_key(user_id, like_type), 0)


def get_available_self_usage_limit(user_id: int, like_type: int) -> int:
    """Return how much of a manager's assigned pool is still available for self-use."""
    own_limit = get_user_limit(user_id, like_type)
    distributed = get_direct_child_limit_sum(user_id, like_type)
    return max(own_limit - distributed, 0)


def get_remaining_distributable_limit(manager_user_id: int, like_type: int) -> int:
    """Return how much of the manager's own quota is still free to distribute."""
    own_limit = get_user_limit(manager_user_id, like_type)
    own_used = get_user_used_count(manager_user_id, like_type)
    distributed = get_direct_child_limit_sum(manager_user_id, like_type)
    return max(own_limit - own_used - distributed, 0)


def cache_user_profile(user_id: int, username: str | None = None, name: str | None = None):
    """Persist a friendly label for a user so reports can show usernames later."""
    profile = USER_PROFILES.get(user_id, {}).copy()

    if username:
        clean_username = username.lower().lstrip('@')
        if clean_username:
            profile['username'] = clean_username

    if name:
        clean_name = name.strip()
        if clean_name:
            profile['name'] = clean_name

    if profile:
        USER_PROFILES[user_id] = profile


def cache_entity_profile(entity):
    """Cache username and display name from a Telethon entity."""
    if entity is None:
        return

    user_id = getattr(entity, 'id', None)
    if user_id is None:
        return

    username = getattr(entity, 'username', None)
    first = getattr(entity, 'first_name', '') or ''
    last = getattr(entity, 'last_name', '') or ''
    full_name = (first + ' ' + last).strip()
    cache_user_profile(user_id, username=username, name=full_name)


def get_cached_display_label(user_id: int) -> str | None:
    """Return best saved label for a user."""
    profile = USER_PROFILES.get(user_id, {})
    username = profile.get('username')
    if username:
        return f"@{username}"

    name = profile.get('name')
    if name:
        return name

    return None


async def get_sender_identity(event):
    """Resolve sender id and username reliably."""
    sender_id = event.sender_id
    sender_username = None

    try:
        sender = await event.get_sender()
        if sender is not None:
            cache_entity_profile(sender)
            sender_id = getattr(sender, 'id', sender_id)
            sender_username = getattr(sender, 'username', None)
    except Exception:
        pass

    return sender_id, sender_username.lower() if sender_username else None


async def get_sender_display_name(event) -> str:
    """Resolve a readable sender display name."""
    try:
        sender = await event.get_sender()
        if sender is not None:
            username = getattr(sender, 'username', None)
            if username:
                return f"@{username}"

            first = getattr(sender, 'first_name', '') or ''
            last = getattr(sender, 'last_name', '') or ''
            full_name = (first + ' ' + last).strip()
            if full_name:
                return full_name
    except Exception:
        pass

    sender_id, sender_username = await get_sender_identity(event)
    return f"@{sender_username}" if sender_username else str(sender_id)


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


async def can_create_super_admin(event) -> bool:
    """Only the main owner can create super admins."""
    return await is_owner(event)


async def can_create_admin(event) -> bool:
    """Owner and super admins can create normal admins."""
    return await is_super_admin(event)


async def can_manage_target_user(event, target_user_id: int, allow_self: bool = False) -> bool:
    """Check whether the sender can manage the target based on hierarchy."""
    actor_user_id, _ = await get_sender_identity(event)

    if allow_self and actor_user_id == target_user_id:
        return True

    if await is_owner(event):
        return True

    if await is_super_admin(event):
        if target_user_id in SUPER_ADMIN_USERS:
            return False
        return is_managed_by(actor_user_id, target_user_id)

    if await is_admin(event):
        if target_user_id in ADMIN_USERS or target_user_id in SUPER_ADMIN_USERS:
            return False
        return is_managed_by(actor_user_id, target_user_id)

    return False


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
        "If this should be a managed admin account, run `myaccess` first."
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
    manager_user_id, _ = await get_sender_identity(event)
    existing_manager_id = get_manager_id(target_user_id)

    if target_user_id in SUPER_ADMIN_USERS:
        await event.reply(f"❌ User `{target_user_id}` is already a super admin.")
        return

    if existing_manager_id is not None and existing_manager_id != manager_user_id:
        await event.reply(
            f"❌ User `{target_user_id}` already belongs to manager `{existing_manager_id}`."
        )
        return

    ADMIN_USERS.add(target_user_id)
    set_manager_for_user(target_user_id, manager_user_id)
    save_state()
    await event.reply(
        f"✅ Admin access granted to user `{target_user_id}`\n"
        f"👤 Managed by: `{manager_user_id}`\n"
        "They can now manage only their own assigned users."
    )


async def remove_admin_for_user(event, target_user_id: int):
    """Remove a normal admin."""
    if target_user_id in SUPER_ADMIN_USERS:
        await event.reply(
            f"❌ User `{target_user_id}` is a super admin. Use a separate super-admin removal flow for that."
        )
        return

    if not await can_manage_target_user(event, target_user_id):
        await event.reply(f"❌ You cannot remove admin `{target_user_id}` from outside your branch.")
        return

    if target_user_id not in ADMIN_USERS:
        await event.reply(f"❌ User `{target_user_id}` is not a normal admin.")
        return

    actor_user_id, _ = await get_sender_identity(event)
    for child_user_id in list(get_direct_children(target_user_id)):
        set_manager_for_user(child_user_id, actor_user_id)

    ADMIN_USERS.discard(target_user_id)
    set_manager_for_user(target_user_id, None)
    save_state()
    await event.reply(f"✅ Admin access removed for user `{target_user_id}`")


async def start_super_admin_verification(event, target_user_id: int):
    """Start super admin verification flow for a user."""
    actor_user_id, _ = await get_sender_identity(event)
    actor_is_owner = await is_owner(event)
    existing_manager_id = get_manager_id(target_user_id)

    if existing_manager_id is not None and existing_manager_id != actor_user_id and not actor_is_owner:
        await event.reply(
            f"❌ User `{target_user_id}` already belongs to manager `{existing_manager_id}`."
        )
        return

    PENDING_SUPER_ADMINS[target_user_id] = actor_user_id
    set_manager_for_user(target_user_id, actor_user_id)
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
        "You can now use branch admin commands and `setadmin` for your own branch."
    )


async def check_limit(event, like_type: int) -> bool:
    """
    Check if user still has quota this month.
    NOTE: This does NOT increment usage. Increment only on success.
    """
    user_id = event.sender_id
    key = _usage_key(user_id, like_type)

    # For super admins/admins, self-use comes from the same assigned pool
    # that they also distribute to child users.
    if user_id in ADMIN_USERS or user_id in SUPER_ADMIN_USERS:
        limit = get_available_self_usage_limit(user_id, like_type)
    else:
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


async def record_like_activity(event, uid: str, like_type: int, likes_added: int):
    """Store successful like activity for dashboard reporting."""
    actor_id, actor_username = await get_sender_identity(event)
    actor_role = await get_access_role(event)
    actor_name = await get_sender_display_name(event)

    REQUEST_ACTIVITY.append({
        'at': _utc_timestamp_str(),
        'month': _this_month_str(),
        'actor_id': actor_id,
        'actor_username': actor_username,
        'actor_name': actor_name,
        'actor_role': actor_role,
        'manager_id': get_manager_id(actor_id),
        'uid': str(uid),
        'packageType': int(like_type),
        'likesAdded': int(likes_added),
    })
    del REQUEST_ACTIVITY[:-200]
    save_state()


async def reset_monthly_usage_for_user(event, target_user_id: int):
    """Reset this month's usage counter for a specific user for all like types."""
    if not await can_manage_target_user(event, target_user_id, allow_self=True):
        await event.reply("❌ You can only reset usage for your own branch.")
        return

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
    actor_user_id, _ = await get_sender_identity(event)
    actor_is_owner = await is_owner(event)
    actor_is_super_admin = await is_super_admin(event)
    actor_is_admin = await is_admin(event)

    if not actor_is_owner:
        if target_user_id == actor_user_id:
            await event.reply("❌ You cannot set your own limit. Your parent admin must set it.")
            return

        if target_user_id in SUPER_ADMIN_USERS:
            await event.reply("❌ You cannot change another super admin's limit.")
            return

        if actor_is_admin and not actor_is_super_admin and target_user_id in ADMIN_USERS:
            await event.reply("❌ Normal admins can only distribute limit to regular users.")
            return

        if not await can_manage_target_user(event, target_user_id):
            if get_manager_id(target_user_id) is not None:
                await event.reply("❌ You can only set limit for users inside your own branch.")
                return

        used_by_others = get_direct_child_limit_sum(actor_user_id, like_type, exclude_user_id=target_user_id)
        parent_limit = get_user_limit(actor_user_id, like_type)
        parent_used = get_user_used_count(actor_user_id, like_type)
        if used_by_others + parent_used + limit > parent_limit:
            remaining = max(parent_limit - used_by_others - parent_used, 0)
            await event.reply(
                f"❌ Not enough distributable limit.\n"
                f"🎯 Like type: `{like_type}`\n"
                f"📌 Your total limit: `{parent_limit}`\n"
                f"🔄 Remaining distributable: `{remaining}`"
            )
            return

        existing_manager_id = get_manager_id(target_user_id)
        if existing_manager_id is not None and existing_manager_id != actor_user_id:
            await event.reply(
                f"❌ User `{target_user_id}` already belongs to manager `{existing_manager_id}`."
            )
            return

    if target_user_id != actor_user_id and get_manager_id(target_user_id) is None and not actor_is_owner:
        set_manager_for_user(target_user_id, actor_user_id)

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


RESPONSE_FOOTER = "\n━━━━━━━━━━━━━━━━━━━━\n🤖 Powered by Telegon"


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
            await record_like_activity(event, uid, like_type, likes_added)
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
  ➤ নিজের branch-এর নিচে নতুন normal admin বানাবে
  উদাহরণ: `setadmin @testuser`

- `removeadmin @username`
  ➤ normal admin remove করবে
  উদাহরণ: `removeadmin @testuser`

- `setsuperadmin @username`
  ➤ main admin নতুন super admin request শুরু করবে
  উদাহরণ: `setsuperadmin @testuser`

- `superauth <api_id> <api_hash> <session_string>`
  ➤ invited user নিজের credentials submit করে super admin verify করবে

- `setsplimit <n> @username <100|200>`
  ➤ main admin নির্দিষ্ট super admin-এর shared pool limit set করবে
  উদাহরণ: `setsplimit 1000 @testsuper 100`

- `setlimit <n> <100|200>`  
  ➤ main admin নিজের account limit set করবে
  উদাহরণ: `setlimit 1000 100`

- `setlimit <n> @username <100|200>`  
  ➤ নির্দিষ্ট child user/admin-এর জন্য limit set করবে
  উদাহরণ: `setlimit 5 @testuser 200`

- `resetlimit` / `/resetlimit`  
  ➤ নিজের এই মাসের usage reset করবে

- `resetlimit @username`  
  ➤ ঐ user-এর এই মাসের usage reset করবে

- `alllimit` / `/alllimit`  
  ➤ শুধু নিজের branch-এর user data দেখাবে
"""

    # Owner/admin হলে full help, regular user হলে শুধু user commands
    if can_manage:
        help_message = f"""📖 **Help**

{user_cmds}{admin_cmds}

⚙️ **Note:**
- Commands case-insensitive: `like`, `Like`, `LIKE` সব কাজ করবে
- Slash (`/`) সহ বা ছাড়া – দু’ভাবেই command দেওয়া যাবে
- Valid UID numeric হতে হবে
- Main admin super admin-এর limit set করবে
- `setsplimit` দিয়ে দেওয়া super admin pool সে নিজে use করতে পারবে, আবার একই pool থেকে distribute-ও করতে পারবে
- Super admin নিজের পাওয়া limit-এর ভিতরে তার user/admin-দের limit distribute করবে
- এক branch-এর admin অন্য branch-এর data দেখতে পারবে না
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
    if not await can_create_admin(event):
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
        cache_entity_profile(entity)
        save_state()
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
    if not await can_create_admin(event):
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
        cache_entity_profile(entity)
        save_state()
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
    if not await can_create_super_admin(event):
        await event.reply(await build_access_denied_message(event, "Owner", "setsuperadmin"))
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
        cache_entity_profile(entity)
        save_state()
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
      /setlimit 1000 100        -> owner sets own top-level limit
      /setlimit 5 @username 200 -> set 200-like monthly limit for a managed child
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
            cache_entity_profile(entity)
            save_state()
            target_user_id = entity.id
        except Exception as e:
            await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
            return
    else:
        target_user_id, _ = await get_sender_identity(event)

    await set_limit_for_user(event, target_user_id, limit, like_type)


@client.on(events.NewMessage(pattern=r'(?i)^/?setsplimit\s+(\d+)\s+(@?\w+)\s+(100|200)$'))
async def setsplimit_command_handler(event):
    """
    Set a super admin pool limit.
    Usage:
      /setsplimit 1000 @username 100
    """
    await log_access_check(event, "setsplimit")
    if not await is_owner(event):
        await event.reply(await build_access_denied_message(event, "Owner", "setsplimit"))
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?setsplimit\s+(\d+)\s+(@?\w+)\s+(100|200)$', text)
    if not match:
        await event.reply("❌ Invalid format.\nUsage: `/setsplimit 1000 @username 100`")
        return

    limit = int(match.group(1))
    username = match.group(2)
    like_type = int(match.group(3))
    active_client = get_event_client(event)

    try:
        entity = await active_client.get_entity(username)
        cache_entity_profile(entity)
        save_state()
        target_user_id = entity.id
    except Exception as e:
        await event.reply(f"❌ Could not find user `{username}`\nError: `{e}`")
        return

    if target_user_id not in SUPER_ADMIN_USERS:
        await event.reply("❌ This command only works for verified super admins.")
        return

    await set_limit_for_user(event, target_user_id, limit, like_type)
    await event.reply(
        f"ℹ️ Super admin `{target_user_id}` can now use this `{like_type}` pool personally "
        "and also distribute from the same pool to their users."
    )


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
            cache_entity_profile(entity)
            save_state()
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
    role = await get_access_role(event)
    lines = [
        "📊 **Your Limit Status**\n",
        f"👤 User ID: `{user_id}`",
        f"🛡 Role: `{role}`",
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

        if role in {"Super Admin", "Admin"}:
            distributable = get_remaining_distributable_limit(user_id, like_type)
            lines.append(f"📤 Can Distribute: `{distributable}` request(s)\n")

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
        f"🛡 Role: `{role}`\n"
        f"👤 Manager ID: `{get_manager_id(sender_id) or 'N/A'}`"
    )


@client.on(events.NewMessage(pattern=r'(?i)^/?alllimit$'))
async def alllimit_command_handler(event):
    """
    Show this month's usage & limits only for the caller's own branch.
    Usage: alllimit / /alllimit
    """
    # Allow owner and delegated admins
    await log_access_check(event, "alllimit")
    if not await is_admin(event):
        await event.reply(await build_access_denied_message(event, "Admin", "alllimit"))
        return

    this_month = _this_month_str()

    actor_user_id, _ = await get_sender_identity(event)

    if await is_owner(event):
        user_ids = set(USER_LIMITS.keys())
        for (uid, month_str, like_type), _ in USER_USAGE.items():
            if month_str == this_month and like_type in LIKE_TYPES:
                user_ids.add(uid)
    else:
        user_ids = get_descendant_user_ids(actor_user_id)
        user_ids.add(actor_user_id)

    if not user_ids:
        await event.reply("📊 এই মাসে এখনও কেউ কোনো request পাঠায়নি।")
        return

    lines = [f"📊 **Branch Limit Status**\n📅 Month: `{this_month}`\n"]

    # Pre-fetch entities for better names (best-effort)
    name_cache = {}
    active_client = get_event_client(event)
    for uid in user_ids:
        cached_display = get_cached_display_label(uid)
        if cached_display:
            name_cache[uid] = cached_display
            continue

        try:
            entity = await active_client.get_entity(uid)
            cache_entity_profile(entity)
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

    save_state()

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

            if uid in ADMIN_USERS or uid in SUPER_ADMIN_USERS or uid == actor_user_id:
                distributable = get_remaining_distributable_limit(uid, like_type)
                user_block.append(
                    f"📤 `{like_type}` Distributable Remaining: `{distributable}`"
                )

        lines.append("\n".join(user_block) + "\n")

    msg = "\n".join(lines)
    await event.reply(msg)


async def calculator_message_handler(event):
    """Auto-calculate plain arithmetic messages in chats and groups."""
    if not getattr(event, 'raw_text', None):
        return

    expression = event.raw_text.strip()
    if not is_calculator_expression(expression):
        return

    try:
        result = evaluate_calculator_expression(expression)
        await event.reply(f"`= {format_calculator_result(result)}`")
    except CalculatorError:
        return
    except Exception as e:
        print(f"⚠️ Calculator handler error for `{expression}`: {e}")


client.add_event_handler(calculator_message_handler, events.NewMessage)


HANDLER_SPECS = [
    (like_command_handler, r'(?i)^/?like\s+(\d+)\s+(100|200)$'),
    (start_command_handler, r'(?i)^/?start$'),
    (help_command_handler, r'(?i)^/?help$'),
    (setadmin_command_handler, r'(?i)^/?setadmin\s+(@?\w+)$'),
    (removeadmin_command_handler, r'(?i)^/?removeadmin\s+(@?\w+)$'),
    (setsuperadmin_command_handler, r'(?i)^/?setsuperadmin\s+(@?\w+)$'),
    (superauth_command_handler, r'(?i)^/?superauth\s+(\d+)\s+([A-Za-z0-9]+)\s+(.+)$'),
    (setsplimit_command_handler, r'(?i)^/?setsplimit\s+(\d+)\s+(@?\w+)\s+(100|200)$'),
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
    target_client.add_event_handler(calculator_message_handler, events.NewMessage)


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


async def resolve_user_label(user_id: int) -> dict:
    """Resolve a safe dashboard label for a user id."""
    cached_display = get_cached_display_label(user_id)
    cached_profile = USER_PROFILES.get(user_id, {})
    if cached_display:
        return {
            'id': user_id,
            'username': f"@{cached_profile['username']}" if cached_profile.get('username') else '',
            'name': cached_display,
        }

    creds = SUPER_ADMIN_CREDENTIALS.get(user_id, {})
    verified_username = creds.get('verified_account_username')
    if verified_username:
        return {
            'id': user_id,
            'username': f"@{verified_username}",
            'name': f"@{verified_username}",
        }

    try:
        entity = await MAIN_CLIENT.get_entity(user_id)
        username = getattr(entity, 'username', None)
        first = getattr(entity, 'first_name', '') or ''
        last = getattr(entity, 'last_name', '') or ''
        full_name = (first + ' ' + last).strip()
        return {
            'id': user_id,
            'username': f"@{username}" if username else '',
            'name': full_name or (f"@{username}" if username else str(user_id)),
        }
    except Exception:
        return {
            'id': user_id,
            'username': '',
            'name': str(user_id),
        }


def get_role_name_for_user(user_id: int, owner_id: int) -> str:
    """Return dashboard role label for a user id."""
    if user_id == owner_id:
        return "Main Admin"
    if user_id in SUPER_ADMIN_USERS:
        return "Super Admin"
    if user_id in ADMIN_USERS:
        return "Admin"
    return "User"


async def build_dashboard_payload() -> dict:
    """Build a sanitized dashboard payload for the frontend."""
    me = await MAIN_CLIENT.get_me()
    owner_id = me.id
    month = _this_month_str()

    known_user_ids = set(USER_LIMITS.keys())
    known_user_ids.update(USER_MANAGERS.keys())
    known_user_ids.update(USER_MANAGERS.values())
    known_user_ids.update(ADMIN_USERS)
    known_user_ids.update(SUPER_ADMIN_USERS)
    known_user_ids.add(owner_id)
    for item in REQUEST_ACTIVITY:
        actor_id = item.get('actor_id')
        manager_id = item.get('manager_id')
        if actor_id is not None:
            known_user_ids.add(int(actor_id))
        if manager_id is not None:
            known_user_ids.add(int(manager_id))

    labels = {}
    for user_id in known_user_ids:
        labels[user_id] = await resolve_user_label(user_id)

    def build_usage(user_id: int, like_type: int) -> int:
        return USER_USAGE.get((user_id, month, like_type), 0)

    def build_user_summary(user_id: int) -> dict:
        label = labels[user_id]
        return {
            'id': user_id,
            'username': label.get('username', ''),
            'name': label.get('name', str(user_id)),
            'role': get_role_name_for_user(user_id, owner_id),
            'limit100': get_user_limit(user_id, 100),
            'used100': build_usage(user_id, 100),
            'limit200': get_user_limit(user_id, 200),
            'used200': build_usage(user_id, 200),
        }

    super_admins = []
    for user_id in sorted(uid for uid in SUPER_ADMIN_USERS if uid != owner_id):
        direct_children = sorted(get_direct_children(user_id))
        admins = [build_user_summary(child_id) for child_id in direct_children if child_id in ADMIN_USERS and child_id not in SUPER_ADMIN_USERS]
        for admin in admins:
            admin['users'] = [
                build_user_summary(child_id)
                for child_id in sorted(get_direct_children(admin['id']))
                if child_id not in ADMIN_USERS and child_id not in SUPER_ADMIN_USERS
            ]

        direct_users = [
            build_user_summary(child_id)
            for child_id in direct_children
            if child_id not in ADMIN_USERS and child_id not in SUPER_ADMIN_USERS
        ]

        node = build_user_summary(user_id)
        node['distributed100'] = get_direct_child_limit_sum(user_id, 100)
        node['distributed200'] = get_direct_child_limit_sum(user_id, 200)
        node['admins'] = admins
        node['directUsers'] = direct_users
        super_admins.append(node)

    recent_activity = []
    for item in reversed(REQUEST_ACTIVITY[-50:]):
        actor_id = item.get('actor_id')
        manager_id = item.get('manager_id')
        actor_label = labels.get(actor_id, {'name': str(actor_id), 'username': ''})
        manager_label = labels.get(manager_id, {'name': 'Main Admin'}) if manager_id is not None else {'name': 'Main Admin'}
        recent_activity.append({
            'at': item.get('at', ''),
            'actor': item.get('actor_name') or actor_label.get('name', str(actor_id)),
            'actorRole': item.get('actor_role') or get_role_name_for_user(actor_id, owner_id),
            'manager': manager_label.get('name', 'Main Admin'),
            'uid': item.get('uid', ''),
            'packageType': item.get('packageType', 0),
            'likesAdded': item.get('likesAdded', 0),
        })

    total_admins = len([uid for uid in ADMIN_USERS if uid not in SUPER_ADMIN_USERS and uid != owner_id])
    total_users = len([
        uid for uid in known_user_ids
        if uid not in ADMIN_USERS and uid not in SUPER_ADMIN_USERS and uid != owner_id
    ])

    return {
        'generatedAt': _utc_timestamp_str(),
        'month': month,
        'summary': {
            'totalSuperAdmins': len(super_admins),
            'totalAdmins': total_admins,
            'totalUsers': total_users,
            'totalUidRequests': len(recent_activity),
            'totalDistributed100': sum(item['distributed100'] for item in super_admins),
            'totalDistributed200': sum(item['distributed200'] for item in super_admins),
        },
        'superAdmins': super_admins,
        'recentActivity': recent_activity,
    }


async def main():
    """Main function to start the bot and the built-in dashboard web server."""
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
    # HTTP server for dashboard + health endpoint
    # ----------------------
    async def health(request):
        return web.Response(text="OK")

    async def dashboard_index(request):
        index_path = DASHBOARD_DIR / "index.html"
        if not index_path.exists():
            return web.Response(
                text="Dashboard file not found. Expected index.html in project root.",
                status=404,
            )
        return web.FileResponse(index_path)

    async def dashboard_asset(request):
        allowed_files = {"style.css", "app.js"}
        filename = request.match_info["filename"]
        if filename not in allowed_files:
            raise web.HTTPNotFound(text="Asset not found.")

        asset_path = DASHBOARD_DIR / filename
        if not asset_path.exists():
            raise web.HTTPNotFound(text=f"Missing asset: {filename}")

        return web.FileResponse(asset_path)

    async def dashboard_api(request):
        payload = await build_dashboard_payload()
        return web.json_response(payload)

    app = web.Application()
    app.router.add_get("/", dashboard_index)
    app.router.add_get(r"/{filename:style\.css|app\.js}", dashboard_asset)
    app.router.add_get("/api/dashboard", dashboard_api)
    app.router.add_get("/health", health)

    port = int(os.getenv("PORT", 8000))  # Render will set PORT
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"🌐 HTTP server running on port {port}")
    print(f"🖥 Dashboard: http://127.0.0.1:{port}/")
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
