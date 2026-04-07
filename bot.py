import os
import asyncio
import base64
import hashlib
import hmac
import re
import json
from decimal import Decimal, InvalidOperation, getcontext
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
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
STOCK_TOKEN_SECRET = os.getenv('STOCK_TOKEN_SECRET') or f"{API_HASH}:{API_KEY}"
UCBOT_TOPUP_URL = os.getenv('UCBOT_TOPUP_URL', 'http://api.ucbot.store/topup-sync')
UCBOT_AUTH_TOKEN = os.getenv('UCBOT_AUTH_TOKEN', '')

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

# Per-manager signup prefix: user_id -> single-character prefix
MANAGER_PREFIXES = {}

# Internal payment info: user_id -> {due, balance, due_limit}
USER_FINANCE = {}

# Branch UC stock: owner_user_id -> {category: [signed_token, ...]}
UC_STOCK = {}

# Branch UC rate list: owner_user_id -> {category: price}
UC_RATES = {}

# Extra admins promoted by the owner: user_id set
ADMIN_USERS = set()

# Super admins can create admins inside their own branch
SUPER_ADMIN_USERS = set()

# Pending super admin verification: user_id -> invited_by_user_id
PENDING_SUPER_ADMINS = {}

# Verified super admin credentials kept in memory
SUPER_ADMIN_CREDENTIALS = {}
STATE_LOCK = asyncio.Lock()
TOPUP_ORDER_SEQ = 0

mongo_client = None
mongo_db = None
state_collection = None
DASHBOARD_DIR = Path(__file__).resolve().parent
getcontext().prec = 28

CALCULATOR_ALLOWED_PATTERN = re.compile(r'^[\d\s+\-*/().%]+$')
CALCULATOR_TOKEN_PATTERN = re.compile(r'\d+(?:\.\d+)?|[()+\-*/%]')
UC_CATEGORY_PATTERNS = {
    '20': [r'(BDMB-T-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-Q-S-\d{8})[,\s]+([\d\-]+)'],
    '36': [r'(BDMB-U-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-R-S-\d{8})[,\s]+([\d\-]+)'],
    '80': [r'(BDMB-J-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-G-S-\d{8})[,\s]+([\d\-]+)'],
    '160': [r'(BDMB-I-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-F-S-\d{8})[,\s]+([\d\-]+)'],
    '161': [r'(BDMB-Q-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-N-S-\d{8})[,\s]+([\d\-]+)'],
    '162': [r'(BDMB-R-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-O-S-\d{8})[,\s]+([\d\-]+)'],
    '405': [r'(BDMB-K-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-H-S-\d{8})[,\s]+([\d\-]+)'],
    '800': [r'(BDMB-S-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-P-S-\d{8})[,\s]+([\d\-]+)'],
    '810': [r'(BDMB-L-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-I-S-\d{8})[,\s]+([\d\-]+)'],
    '1625': [r'(BDMB-M-S-\d{8})[,\s]+([\d\-]+)', r'(UPBD-J-S-\d{8})[,\s]+([\d\-]+)'],
    '2000': [r'(UPBD-7-S-\d{8})[,\s]+([\d\-]+)'],
}
UC_STOCK_CATEGORY_ORDER = ['20', '36', '80', '160', '161', '162', '405', '800', '810', '1625', '2000']
UC_STOCK_WORTH_USDT = {
    '20': Decimal('0'),
    '36': Decimal('0'),
    '80': Decimal('0'),
    '160': Decimal('0'),
    '161': Decimal('0'),
    '162': Decimal('0'),
    '405': Decimal('0'),
    '800': Decimal('0'),
    '810': Decimal('0'),
    '1625': Decimal('0'),
    '2000': Decimal('0'),
}
TOPUP_PRODUCT_MAP = {
    '25': {'category': '20', 'label': '25 Diamond', 'fee': Decimal('0.5')},
    '50': {'category': '36', 'label': '50 Diamond', 'fee': Decimal('0.5')},
    '115': {'category': '80', 'label': '115 Diamond', 'fee': Decimal('0.5')},
    '240': {'category': '160', 'label': '240 Diamond', 'fee': Decimal('0.5')},
    'weekly': {'category': '161', 'label': 'Weekly', 'fee': Decimal('0.5')},
    '610': {'category': '405', 'label': '610 Diamond', 'fee': Decimal('0.5')},
    'monthly': {'category': '800', 'label': 'Monthly', 'fee': Decimal('0.5')},
    '1240': {'category': '810', 'label': '1240 Diamond', 'fee': Decimal('0.5')},
    '2530': {'category': '1625', 'label': '2530 Diamond', 'fee': Decimal('0.5')},
}
TOPUP_DIAMOND_ALIASES = {
    '25': '25',
    '50': '50',
    '115': '115',
    '240': '240',
    '161': 'weekly',
    'weekly': 'weekly',
    '610': '610',
    '800': 'monthly',
    'monthly': 'monthly',
    '810': '1240',
    '1240': '1240',
    '1625': '2530',
    '2530': '2530',
}


def _build_fernet(secret: str) -> Fernet:
    """Derive a Fernet key from an application secret."""
    key_material = hashlib.sha256(secret.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


FERNET = _build_fernet(STOCK_TOKEN_SECRET)


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
    global MANAGER_PREFIXES, USER_FINANCE, UC_STOCK, UC_RATES, TOPUP_ORDER_SEQ

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
        MANAGER_PREFIXES = {
            int(user_id): str(prefix)
            for user_id, prefix in data.get('manager_prefixes', {}).items()
            if str(prefix).strip()
        }
        USER_FINANCE = {}
        for user_id, finance_blob in data.get('user_finance', {}).items():
            if isinstance(finance_blob, str):
                finance = decrypt_payload_token(finance_blob, 'user-finance')
                if finance is None:
                    continue
            else:
                finance = finance_blob

            USER_FINANCE[int(user_id)] = {
                'due': str(finance.get('due', '0')),
                'balance': str(finance.get('balance', '0')),
                'due_limit': str(finance.get('due_limit', '0')),
                'purchases': {
                    str(product): int(count)
                    for product, count in finance.get('purchases', {}).items()
                },
            }

        UC_STOCK = {}
        for owner_id, stock_blob in data.get('uc_stock', {}).items():
            if isinstance(stock_blob, str):
                category_map = decrypt_payload_token(stock_blob, 'branch-stock')
                if category_map is None:
                    continue
            else:
                category_map = stock_blob

            UC_STOCK[int(owner_id)] = {
                str(category): list(tokens)
                for category, tokens in category_map.items()
            }

        UC_RATES = {}
        for owner_id, rate_blob in data.get('uc_rates', {}).items():
            if isinstance(rate_blob, str):
                category_map = decrypt_payload_token(rate_blob, 'branch-rates')
                if category_map is None:
                    continue
            else:
                category_map = rate_blob

            UC_RATES[int(owner_id)] = {
                str(category): str(price)
                for category, price in category_map.items()
            }
        TOPUP_ORDER_SEQ = int(data.get('topup_order_seq', 0))
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
            'manager_prefixes': {
                str(user_id): prefix
                for user_id, prefix in MANAGER_PREFIXES.items()
            },
            'user_finance': {
                str(user_id): encrypt_payload_token(finance, 'user-finance')
                for user_id, finance in USER_FINANCE.items()
            },
            'uc_stock': {
                str(owner_id): encrypt_payload_token(category_map, 'branch-stock')
                for owner_id, category_map in UC_STOCK.items()
            },
            'uc_rates': {
                str(owner_id): encrypt_payload_token(category_map, 'branch-rates')
                for owner_id, category_map in UC_RATES.items()
            },
            'topup_order_seq': TOPUP_ORDER_SEQ,
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


async def save_state_locked():
    """Persist state while holding the shared async lock."""
    async with STATE_LOCK:
        save_state()


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


def get_manager_prefix(user_id: int) -> str | None:
    """Return stored signup prefix for an owner/super admin."""
    prefix = MANAGER_PREFIXES.get(user_id)
    if not prefix:
        return None
    return str(prefix)


def set_manager_prefix(user_id: int, prefix: str):
    """Persist a single-character signup prefix for an owner/super admin."""
    MANAGER_PREFIXES[user_id] = prefix


def _sanitize_money_value(value) -> str:
    """Convert numeric-like values to a clean decimal string."""
    try:
        return str(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return '0'


def ensure_user_finance_record(user_id: int):
    """Ensure every known user has a finance record."""
    if user_id not in USER_FINANCE:
        USER_FINANCE[user_id] = {
            'due': '0',
            'balance': '0',
            'due_limit': '0',
            'purchases': {},
        }


def get_user_finance(user_id: int) -> dict:
    """Return normalized finance info for a user."""
    ensure_user_finance_record(user_id)
    finance = USER_FINANCE[user_id]
    return {
        'due': _sanitize_money_value(finance.get('due', '0')),
        'balance': _sanitize_money_value(finance.get('balance', '0')),
        'due_limit': _sanitize_money_value(finance.get('due_limit', '0')),
        'purchases': {
            str(product): int(count)
            for product, count in finance.get('purchases', {}).items()
        },
    }


def set_user_due_limit(user_id: int, amount: Decimal):
    """Set finance due limit for a user."""
    ensure_user_finance_record(user_id)
    USER_FINANCE[user_id]['due_limit'] = str(amount)


def set_user_balance(user_id: int, amount: Decimal):
    """Set finance balance for a user."""
    ensure_user_finance_record(user_id)
    USER_FINANCE[user_id]['balance'] = str(amount)


def format_money_amount(value) -> str:
    """Render internal finance values without noisy trailing zeros."""
    normalized = Decimal(str(value)).normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal('1')))
    return format(normalized, 'f').rstrip('0').rstrip('.')


def increment_user_purchase(user_id: int, product_name: str, quantity: int):
    """Track how many units of a product a user has bought on due."""
    ensure_user_finance_record(user_id)
    purchases = USER_FINANCE[user_id].setdefault('purchases', {})
    purchases[product_name] = int(purchases.get(product_name, 0)) + int(quantity)


def get_prefix_owners_for_user(user_id: int) -> list[int]:
    """Return self + ancestor chain for prefix ownership lookup."""
    owners = []
    current_user_id = user_id
    visited = set()

    while current_user_id is not None and current_user_id not in visited:
        owners.append(current_user_id)
        visited.add(current_user_id)
        current_user_id = get_manager_id(current_user_id)

    return owners


def get_nearest_prefix_owner(user_id: int) -> int | None:
    """Return the closest self/ancestor that explicitly owns a branch prefix."""
    for owner_id in get_prefix_owners_for_user(user_id):
        if get_manager_prefix(owner_id):
            return owner_id
    return None


def resolve_prefix_owner_for_user(user_id: int, prefix_text: str) -> int | None:
    """Resolve only the nearest branch prefix owner for this user."""
    owner_id = get_nearest_prefix_owner(user_id)
    if owner_id is None:
        return None

    owner_prefix = get_manager_prefix(owner_id)
    if owner_prefix and owner_prefix.lower() == prefix_text.lower():
        return owner_id
    return None


def resolve_prefix_owner_for_private_chat(sender_id: int, private_chat_user_id: int, prefix_text: str) -> int | None:
    """Resolve a branch prefix in a private chat.

    In most user chats, ``sender_id`` and ``private_chat_user_id`` are the same.
    Some Telegram event shapes can differ though, so we try both identities to
    avoid silently dropping valid branch commands.
    """
    owner_id = resolve_prefix_owner_for_user(sender_id, prefix_text)
    if owner_id is not None:
        return owner_id
    if private_chat_user_id != sender_id:
        return resolve_prefix_owner_for_user(private_chat_user_id, prefix_text)
    return None


def is_registered_under_branch(prefix_owner_id: int, target_user_id: int) -> bool:
    """Return True when a target belongs to the prefix owner's branch."""
    if target_user_id == prefix_owner_id:
        return True
    return is_managed_by(prefix_owner_id, target_user_id)


def resolve_prefixed_branch_account_user(prefix_owner_id: int, sender_id: int, private_chat_user_id: int) -> int:
    """Resolve which user account a prefixed private-chat command should use.

    In a private chat, the branch owner may send commands while talking directly
    to one of their managed users. In that case the command should affect the
    chat user, not the sender/owner. For regular branch users messaging from
    their own private chat, the sender and chat user are the same person.
    """
    if sender_id == prefix_owner_id and is_registered_under_branch(prefix_owner_id, private_chat_user_id):
        return int(private_chat_user_id)
    return int(sender_id)


def encrypt_payload_token(payload: dict, purpose: str) -> str:
    """Encrypt a JSON payload for database storage."""
    envelope = {
        'v': 1,
        'p': purpose,
        'd': payload,
    }
    return FERNET.encrypt(json.dumps(envelope, separators=(',', ':')).encode('utf-8')).decode('utf-8')


def decrypt_payload_token(token: str, purpose: str) -> dict | None:
    """Decrypt a JSON payload token and verify its purpose."""
    try:
        envelope_raw = FERNET.decrypt(token.encode('utf-8'))
        envelope = json.loads(envelope_raw.decode('utf-8'))
        if not isinstance(envelope, dict):
            return None
        if envelope.get('p') != purpose:
            return None
        payload = envelope.get('d')
        if not isinstance(payload, dict):
            return None
        return payload
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError):
        return None


def _jwt_b64encode(payload_bytes: bytes) -> str:
    """Encode bytes using JWT-style base64url without padding."""
    return base64.urlsafe_b64encode(payload_bytes).rstrip(b'=').decode('ascii')


def _jwt_b64decode(payload_text: str) -> bytes:
    """Decode JWT-style base64url text."""
    padding = '=' * (-len(payload_text) % 4)
    return base64.urlsafe_b64decode(payload_text + padding)


def decode_legacy_stock_token(token: str) -> dict | None:
    """Verify and decode the previous signed stock token format."""
    try:
        header_b64, payload_b64, signature_b64 = token.split('.')
        signing_input = f"{header_b64}.{payload_b64}".encode('ascii')
        expected_signature = hmac.new(STOCK_TOKEN_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
        provided_signature = _jwt_b64decode(signature_b64)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return None
        payload = json.loads(_jwt_b64decode(payload_b64).decode('utf-8'))
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception:
        return None


def make_stock_token(owner_id: int, category: str, code_head: str, code_tail: str) -> str:
    """Create an encrypted token for one stock code."""
    payload = {
        'owner_id': owner_id,
        'category': category,
        'code_head': code_head,
        'code_tail': code_tail,
        'added_at': _utc_timestamp_str(),
    }
    return encrypt_payload_token(payload, 'stock-code')


def decode_stock_token(token: str) -> dict | None:
    """Decrypt a stock token, with legacy fallback for older signed tokens."""
    payload = decrypt_payload_token(token, 'stock-code')
    if payload is not None:
        return payload
    return decode_legacy_stock_token(token)


def ensure_branch_stock(owner_user_id: int):
    """Ensure a branch stock container exists."""
    if owner_user_id not in UC_STOCK:
        UC_STOCK[owner_user_id] = {}


def ensure_branch_rates(owner_user_id: int):
    """Ensure a branch rate container exists."""
    if owner_user_id not in UC_RATES:
        UC_RATES[owner_user_id] = {}


def set_branch_rate(owner_user_id: int, category: str, price: Decimal):
    """Set one UC category rate for a branch."""
    ensure_branch_rates(owner_user_id)
    UC_RATES[owner_user_id][category] = str(price)


def get_branch_rate(owner_user_id: int, category: str) -> Decimal:
    """Get one UC category rate for a branch."""
    ensure_branch_rates(owner_user_id)
    raw_price = UC_RATES[owner_user_id].get(category, '0')
    try:
        return Decimal(str(raw_price))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def extract_uc_stock_entries(raw_text: str) -> tuple[list[dict], int]:
    """Parse incoming stock text line-by-line into categorized UC code entries."""
    entries = []
    ignored_lines = 0

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        matched = False
        for category in UC_STOCK_CATEGORY_ORDER:
            for pattern in UC_CATEGORY_PATTERNS.get(category, []):
                match = re.fullmatch(pattern, line, flags=re.IGNORECASE)
                if not match:
                    continue

                entries.append({
                    'category': category,
                    'code_head': match.group(1).upper().strip(),
                    'code_tail': match.group(2).strip(),
                })
                matched = True
                break
            if matched:
                break

        if not matched:
            ignored_lines += 1

    return entries, ignored_lines


def get_branch_stock_snapshot(owner_user_id: int) -> tuple[dict, set[str]]:
    """Return category counts and fingerprint set for one branch stock."""
    ensure_branch_stock(owner_user_id)
    counts = {category: 0 for category in UC_STOCK_CATEGORY_ORDER}
    fingerprints = set()

    for category, tokens in UC_STOCK.get(owner_user_id, {}).items():
        for token in tokens:
            payload = decode_stock_token(token)
            if not payload:
                continue
            code_head = str(payload.get('code_head', '')).strip().upper()
            code_tail = str(payload.get('code_tail', '')).strip()
            token_category = str(payload.get('category', category))
            fingerprint = f"{code_head}|{code_tail}"
            fingerprints.add(fingerprint)
            if token_category in counts:
                counts[token_category] += 1

    return counts, fingerprints


def add_uc_stock_entries(owner_user_id: int, entries: list[dict]) -> tuple[int, int, list[dict]]:
    """Add new UC entries to branch stock and skip duplicates."""
    ensure_branch_stock(owner_user_id)
    _, existing_fingerprints = get_branch_stock_snapshot(owner_user_id)
    added_count = 0
    skipped_count = 0
    duplicate_entries = []

    for entry in entries:
        category = entry['category']
        code_head = entry['code_head']
        code_tail = entry['code_tail']
        fingerprint = f"{code_head}|{code_tail}"
        if fingerprint in existing_fingerprints:
            skipped_count += 1
            duplicate_entries.append(entry)
            continue

        UC_STOCK[owner_user_id].setdefault(category, []).append(
            make_stock_token(owner_user_id, category, code_head, code_tail)
        )
        existing_fingerprints.add(fingerprint)
        added_count += 1

    return added_count, skipped_count, duplicate_entries


def pop_branch_stock_entries(owner_user_id: int, category: str, quantity: int) -> list[dict]:
    """Atomically reserve verified stock entries from a branch category."""
    decoded_entries, _ = reserve_branch_stock_entries(owner_user_id, category, quantity)
    return decoded_entries


def reserve_branch_stock_entries(owner_user_id: int, category: str, quantity: int) -> tuple[list[dict], list[str]]:
    """Reserve verified stock entries from a branch category and return entries plus removed tokens."""
    ensure_branch_stock(owner_user_id)
    tokens = list(UC_STOCK.get(owner_user_id, {}).get(category, []))
    if quantity <= 0:
        return [], []

    decoded_entries = []
    selected_tokens = []
    remaining_tokens = []

    for token in tokens:
        payload = decode_stock_token(token)
        if not payload:
            continue

        if len(decoded_entries) < quantity:
            decoded_entries.append({
                'category': str(payload.get('category', category)),
                'code_head': str(payload.get('code_head', '')).strip().upper(),
                'code_tail': str(payload.get('code_tail', '')).strip(),
            })
            selected_tokens.append(token)
            continue

        remaining_tokens.append(token)

    if len(decoded_entries) < quantity:
        UC_STOCK[owner_user_id][category] = selected_tokens + remaining_tokens
        return [], []

    UC_STOCK[owner_user_id][category] = remaining_tokens
    return decoded_entries, selected_tokens


def restore_branch_stock_tokens(owner_user_id: int, category: str, tokens: list[str]):
    """Put reserved stock tokens back into the front of the branch category list."""
    if not tokens:
        return
    ensure_branch_stock(owner_user_id)
    existing = list(UC_STOCK.get(owner_user_id, {}).get(category, []))
    UC_STOCK[owner_user_id][category] = list(tokens) + existing


def build_stock_summary_message(owner_user_id: int) -> str:
    """Render branch stock summary in the requested format."""
    counts, _ = get_branch_stock_snapshot(owner_user_id)
    total_worth = Decimal('0')
    lines = ["▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔"]

    for category in UC_STOCK_CATEGORY_ORDER:
        count = counts.get(category, 0)
        total_worth += get_branch_rate(owner_user_id, category) * Decimal(count)
        lines.append(f"☞︎︎︎ {category:<4} 🆄︎🅲︎  ➪  {count} ᴘᴄs")
        lines.append("")

    lines.append("▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔")
    lines.append(f"Wᴏʀᴛʜ Oғ : {format_money_amount(total_worth)} ᴜsᴅᴛ")
    return "\n".join(lines)


def build_rate_list_message(owner_user_id: int) -> str:
    """Render branch rate list in the requested format."""
    lines = ["▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔"]

    for category in UC_STOCK_CATEGORY_ORDER:
        price = format_money_amount(get_branch_rate(owner_user_id, category))
        lines.append(f"☞︎︎︎ {category:<4} 🆄︎🅲︎  ➪  {price} Bᴀɴᴋ")
        lines.append("")

    lines.append("▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔")
    return "\n".join(lines)


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


def resolve_branch_actor_user_id(sender_id: int | None, sender_username: str | None) -> int | None:
    """Map a verified super-admin identity back to its stored branch owner id."""
    if sender_id is not None and sender_id in SUPER_ADMIN_CREDENTIALS:
        return int(sender_id)

    for stored_user_id, creds in SUPER_ADMIN_CREDENTIALS.items():
        verified_account_id = creds.get('verified_account_id')
        verified_username = creds.get('verified_account_username')

        if sender_id is not None and verified_account_id == sender_id:
            return int(stored_user_id)

        if sender_username and verified_username and verified_username.lower() == sender_username:
            return int(stored_user_id)

    return sender_id


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


async def can_use_signup_prefix(event) -> bool:
    """Only owner and super admins can register users with a prefix command."""
    return await is_super_admin(event)


async def can_set_prefix(event) -> bool:
    """Any admin-level account can save a branch prefix."""
    return await is_admin(event)


async def can_manage_due_limit(event) -> bool:
    """Owner, super admins, and admins can manage due limits in their branch."""
    return await is_admin(event)


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


async def remove_super_admin_for_user(event, target_user_id: int):
    """Remove a verified or pending super admin."""
    owner = await MAIN_CLIENT.get_me()
    owner_user_id = owner.id

    if target_user_id == owner_user_id:
        await event.reply("❌ You cannot remove the main owner from super admin access.")
        return

    if (
        target_user_id not in SUPER_ADMIN_USERS
        and target_user_id not in SUPER_ADMIN_CREDENTIALS
        and target_user_id not in PENDING_SUPER_ADMINS
    ):
        await event.reply(f"❌ User `{target_user_id}` is not a super admin.")
        return

    creds = SUPER_ADMIN_CREDENTIALS.pop(target_user_id, None)
    PENDING_SUPER_ADMINS.pop(target_user_id, None)

    verified_account_id = None
    if creds:
        raw_verified_account_id = creds.get('verified_account_id')
        if raw_verified_account_id is not None:
            verified_account_id = int(raw_verified_account_id)

    super_client = SUPER_ADMIN_CLIENTS.pop(target_user_id, None)
    if super_client is not None:
        try:
            await super_client.disconnect()
        except Exception:
            pass

    SUPER_ADMIN_USERS.discard(target_user_id)
    ADMIN_USERS.discard(target_user_id)

    if verified_account_id is not None:
        SUPER_ADMIN_USERS.discard(verified_account_id)
        ADMIN_USERS.discard(verified_account_id)

    for child_user_id in list(get_direct_children(target_user_id)):
        set_manager_for_user(child_user_id, owner_user_id)

    set_manager_for_user(target_user_id, owner_user_id)
    MANAGER_PREFIXES.pop(target_user_id, None)
    UC_STOCK.pop(target_user_id, None)
    UC_RATES.pop(target_user_id, None)

    save_state()
    await event.reply(
        f"✅ Super admin access removed for user `{target_user_id}`\n"
        f"👤 Reassigned to owner: `{owner_user_id}`"
    )


async def register_user_under_manager(event, target_user_id: int):
    """Attach a regular user to the sender's branch."""
    actor_user_id, _ = await get_sender_identity(event)

    if target_user_id == actor_user_id:
        await event.reply("❌ You cannot register yourself with signup.")
        return

    existing_manager_id = get_manager_id(target_user_id)
    if existing_manager_id == actor_user_id:
        username_text = "N/A"
        profile = USER_PROFILES.get(target_user_id, {})
        if profile.get('username'):
            username_text = f"@{profile['username']}"

        await event.reply(
            "ℹ️ 𝗨𝘀𝗲𝗿 𝗔𝗹𝗿𝗲𝗮𝗱𝘆 𝗥𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱\n\n"
            f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗: `{target_user_id}`\n"
            f"👤 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: `{username_text}`\n"
            "⚠️ 𝗔𝗹𝗿𝗲𝗮𝗱𝘆 𝗿𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱 𝘂𝗻𝗱𝗲𝗿 𝘆𝗼𝘂𝗿 𝗯𝗿𝗮𝗻𝗰𝗵."
        )
        return

    role_text = "User"
    if target_user_id in SUPER_ADMIN_USERS:
        role_text = "Super Admin"
    elif target_user_id in ADMIN_USERS:
        role_text = "Admin"

    async with STATE_LOCK:
        set_manager_for_user(target_user_id, actor_user_id)
        ensure_user_finance_record(target_user_id)
        save_state()
    await event.reply(
        "✅ 𝗦𝗶𝗴𝗻𝘂𝗽 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹\n\n"
        f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗: `{target_user_id}`\n"
        f"🛡 𝗥𝗼𝗹𝗲: `{role_text}`\n"
        f"👤 𝗠𝗮𝗻𝗮𝗴𝗲𝗿 𝗜𝗗: `{actor_user_id}`"
    )


async def signout_user_from_manager(event, target_user_id: int):
    """Remove any managed account from the sender's branch."""
    actor_user_id, _ = await get_sender_identity(event)

    if target_user_id == actor_user_id:
        await event.reply("❌ You cannot sign out yourself.")
        return

    existing_manager_id = get_manager_id(target_user_id)
    if existing_manager_id is None:
        await event.reply(
            "ℹ️ 𝗨𝘀𝗲𝗿 𝗡𝗼𝘁 𝗥𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱\n\n"
            f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗: `{target_user_id}`\n"
            "⚠️ 𝗧𝗵𝗶𝘀 𝘂𝘀𝗲𝗿 𝗶𝘀 𝗻𝗼𝘁 𝗿𝗲𝗴𝗶𝘀𝘁𝗲𝗿𝗲𝗱 𝘂𝗻𝗱𝗲𝗿 𝗮𝗻𝘆 𝗯𝗿𝗮𝗻𝗰𝗵."
        )
        return

    if existing_manager_id != actor_user_id:
        await event.reply(
            f"❌ User `{target_user_id}` belongs to another manager `{existing_manager_id}`."
        )
        return

    role_text = "User"
    if target_user_id in SUPER_ADMIN_USERS:
        role_text = "Super Admin"
    elif target_user_id in ADMIN_USERS:
        role_text = "Admin"

    async with STATE_LOCK:
        set_manager_for_user(target_user_id, None)
        save_state()
    await event.reply(
        "✅ 𝗨𝘀𝗲𝗿 𝗦𝗶𝗴𝗻𝗲𝗱 𝗢𝘂𝘁\n\n"
        f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗: `{target_user_id}`\n"
        f"🛡 𝗥𝗼𝗹𝗲: `{role_text}`\n"
        "⚠️ 𝗥𝗲𝗺𝗼𝘃𝗲𝗱 𝗳𝗿𝗼𝗺 𝘆𝗼𝘂𝗿 𝗯𝗿𝗮𝗻𝗰𝗵."
    )


async def set_due_limit_for_managed_user(event, target_user_id: int, amount: Decimal):
    """Set a due-limit amount for a managed target."""
    actor_user_id, _ = await get_sender_identity(event)
    if target_user_id == actor_user_id:
        await event.reply("❌ You cannot set your own due limit with this command.")
        return

    can_manage = False
    if await is_owner(event):
        can_manage = True
    elif is_managed_by(actor_user_id, target_user_id):
        can_manage = True

    if not can_manage:
        await event.reply("❌ You can only set due limit for users inside your own branch.")
        return

    async with STATE_LOCK:
        set_user_due_limit(target_user_id, amount)
        save_state()
    await event.reply(
        "✅ 𝗗𝘂𝗲 𝗟𝗶𝗺𝗶𝘁 𝗨𝗽𝗱𝗮𝘁𝗲𝗱\n\n"
        f"🆔 𝗨𝘀𝗲𝗿 𝗜𝗗: `{target_user_id}`\n"
        f"💳 𝗗𝘂𝗲 𝗟𝗶𝗺𝗶𝘁: `{format_money_amount(amount)}` 𝗧𝗸"
    )


async def send_balance_card(event, target_user_id: int):
    """Show the internal payment snapshot for a branch member."""
    async with STATE_LOCK:
        finance = get_user_finance(target_user_id)
        profile = USER_PROFILES.get(target_user_id, {}).copy()
    name_text = profile.get('name') or (f"@{profile['username']}" if profile.get('username') else str(target_user_id))

    lines = [
        "───────〔 USER INFO 〕───────",
        f"Name      : {name_text}",
        "",
        f"Due       : {format_money_amount(finance['due'])} Tk",
        f"Balance   : {format_money_amount(finance['balance'])} Tk",
        f"Due Limit : {format_money_amount(finance['due_limit'])} Tk",
        "───────────────────────────",
    ]
    await event.reply("\n".join(lines))


async def send_stock_card(event, owner_user_id: int):
    """Show branch UC stock summary."""
    async with STATE_LOCK:
        message = build_stock_summary_message(owner_user_id)
    await event.reply(message)


async def add_branch_stock_from_text(event, owner_user_id: int, raw_stock_text: str):
    """Parse and store UC stock codes for one branch owner."""
    entries, ignored_lines = extract_uc_stock_entries(raw_stock_text)
    if not entries:
        await event.reply(
            "❌ No valid UC stock codes found in your message.\n"
            f"➪ Ignored : {ignored_lines} ʟɪɴᴇs"
        )
        return

    async with STATE_LOCK:
        added_count, skipped_count, duplicate_entries = add_uc_stock_entries(owner_user_id, entries)
        save_state()
        stock_message = build_stock_summary_message(owner_user_id)

    duplicate_preview = ""
    if duplicate_entries:
        preview_lines = []
        for entry in duplicate_entries[:5]:
            preview_lines.append(f"{entry['code_head']} {entry['code_tail']} [{entry['category']} UC]")
        duplicate_preview = "\n➪ Already :\n" + "\n".join(preview_lines)

    await event.reply(
        f"✅ 𝗦𝘁𝗼𝗰𝗸 𝗨𝗽𝗱𝗮𝘁𝗲𝗱\n\n"
        f"➪ Found   : {len(entries)} ᴄᴏᴅᴇs\n"
        f"➪ Added   : {added_count} ᴄᴏᴅᴇs\n"
        f"➪ Skipped : {skipped_count} ᴅᴜᴘʟɪᴄᴀᴛᴇs\n\n"
        f"➪ Ignored : {ignored_lines} ʟɪɴᴇs"
        f"{duplicate_preview}\n\n"
        f"{stock_message}"
    )


async def send_rate_card(event, owner_user_id: int):
    """Show branch UC rates."""
    async with STATE_LOCK:
        message = build_rate_list_message(owner_user_id)
    await event.reply(message)


async def send_prefix_help_card(event, prefix: str, prefix_owner_id: int, sender_id: int):
    """Show branch-prefixed help for users and managers."""
    user_lines = [
        "📘 Pʀᴇғɪx Hᴇʟᴘ",
        "",
        f"🔑 Pʀᴇғɪx : {prefix}",
        "",
        "👤 Usᴇʀ Cᴏᴍᴍᴀɴᴅs",
        f"- `{prefix}help`",
        f"- `{prefix}balance`",
        f"- `{prefix}due`",
        f"- `{prefix}rate`",
        f"- `{prefix}stock`",
        f"- `{prefix}tp <uid> <diamond> [qty]`",
    ]

    is_prefix_owner = prefix_owner_id == sender_id
    if is_prefix_owner:
        user_lines.extend([
            "",
            "🛠 Mᴀɴᴀɢᴇʀ Cᴏᴍᴍᴀɴᴅs",
            f"- `{prefix}signup`",
            f"- `{prefix}signout`",
            f"- `{prefix}duelimit <amount>`",
            f"- `{prefix}balance <amount>`",
            f"- `{prefix}clear`",
            f"- `{prefix}stockadd <codes>`",
            f"- `{prefix}20 <price>`",
            f"- `{prefix}36 <price>`",
            f"- `{prefix}80 <price>`",
            f"- `{prefix}160 <price>`",
            f"- `{prefix}161 <price>`",
            f"- `{prefix}162 <price>`",
            f"- `{prefix}405 <price>`",
            f"- `{prefix}800 <price>`",
            f"- `{prefix}810 <price>`",
            f"- `{prefix}1625 <price>`",
            f"- `{prefix}2000 <price>`",
        ])

    await event.reply("\n".join(user_lines))


async def set_branch_rate_command(event, owner_user_id: int, category: str, price: Decimal):
    """Persist one branch UC rate."""
    async with STATE_LOCK:
        set_branch_rate(owner_user_id, category, price)
        save_state()

    await event.reply(f"✅ 𝗥𝗮𝘁𝗲 `{category} UC` 𝘀𝗲𝘁 𝘁𝗼 `{format_money_amount(price)}` 𝗕ᴀɴᴋ")


async def send_due_summary_card(event, target_user_id: int):
    """Show the user's purchased products and total due."""
    async with STATE_LOCK:
        finance = get_user_finance(target_user_id)
        purchases = dict(finance.get('purchases', {}))
        migrated = False

        for diamond_key, product in TOPUP_PRODUCT_MAP.items():
            product_label = product['label']
            category = product['category']
            legacy_count = int(purchases.get(product_label, 0))
            if legacy_count > 0:
                purchases[category] = int(purchases.get(category, 0)) + legacy_count
                purchases.pop(product_label, None)
                USER_FINANCE[target_user_id]['purchases'] = purchases
                migrated = True

        if migrated:
            save_state()
            finance = get_user_finance(target_user_id)

    purchases = finance.get('purchases', {})
    lines = []
    for product_name, count in purchases.items():
        if count <= 0:
            continue

        if product_name in UC_STOCK_CATEGORY_ORDER:
            lines.append(f"☞︎︎︎ {product_name} 🆄︎🅲︎ ➪ {count} ᴘᴄs")
        else:
            lines.append(f"☞︎︎︎ {product_name} ➪ {count} ᴘᴄs")
        lines.append("")

    if not lines:
        lines.append("☞︎︎︎ Nᴏ Pᴜʀᴄʜᴀsᴇ Hɪsᴛᴏʀʏ ➪ 0 ᴘᴄs")
        lines.append("")

    lines.append("▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔")
    lines.append(f"☞︎︎︎ Tᴏᴛᴀʟ Dᴜᴇ ➪ {format_money_amount(finance['due'])} Tᴋ")
    await event.reply("\n".join(lines))


async def clear_user_due_command(event, target_user_id: int):
    """Clear a user's due amount and purchase summary."""
    async with STATE_LOCK:
        ensure_user_finance_record(target_user_id)
        finance = USER_FINANCE[target_user_id]
        cleared_due = Decimal(finance.get('due', '0'))
        finance['due'] = '0'
        finance['purchases'] = {}
        save_state()

        profile = USER_PROFILES.get(target_user_id, {}).copy()

    customer_name = profile.get('name') or (f"@{profile['username']}" if profile.get('username') else str(target_user_id))
    await event.reply(
        f"- Dᴜᴇ Cʟᴇᴀʀ Oғ {customer_name} !\n\n"
        f"- Dᴜᴇ Aᴍᴍᴏᴜɴᴛ : {format_money_amount(cleared_due)} Tᴋ \n\n"
        "Tʜᴀɴᴋs Fᴏʀ Yᴏᴜʀ Sᴜᴘᴘᴏʀᴛ ❤️❤️"
    )


async def set_user_balance_command(event, target_user_id: int, amount: Decimal):
    """Set a user's balance amount."""
    async with STATE_LOCK:
        set_user_balance(target_user_id, amount)
        save_state()
        profile = USER_PROFILES.get(target_user_id, {}).copy()

    customer_name = profile.get('name') or (f"@{profile['username']}" if profile.get('username') else str(target_user_id))
    await event.reply(
        f"✅ Bᴀʟᴀɴᴄᴇ Uᴘᴅᴀᴛᴇᴅ Oғ {customer_name} !\n\n"
        f"💳 Bᴀʟᴀɴᴄᴇ Aᴍᴏᴜɴᴛ : {format_money_amount(amount)} Tᴋ"
    )


async def purchase_uc_with_due(event, owner_user_id: int, target_user_id: int, category: str, quantity: int):
    """Sell UC stock to a branch user using their due limit."""
    if quantity <= 0:
        await event.reply("❌ Quantity must be at least 1.")
        return

    async with STATE_LOCK:
        ensure_user_finance_record(target_user_id)
        counts, _ = get_branch_stock_snapshot(owner_user_id)
        available_stock = counts.get(category, 0)
        if available_stock < quantity:
            await event.reply(
                f"❌ Not enough stock.\n"
                f"➪ Category : {category} UC\n"
                f"➪ Need     : {quantity}\n"
                f"➪ Stock    : {available_stock}"
            )
            return

        unit_price = get_branch_rate(owner_user_id, category)
        if unit_price <= 0:
            await event.reply(f"❌ Rate for `{category} UC` is not set.")
            return

        finance = USER_FINANCE[target_user_id]
        current_due = Decimal(finance.get('due', '0'))
        due_limit = Decimal(finance.get('due_limit', '0'))
        total_price = unit_price * Decimal(quantity)
        if current_due + total_price > due_limit:
            await event.reply(
                "❌ Due limit exceeded.\n"
                f"➪ Current Due : {format_money_amount(current_due)} Tk\n"
                f"➪ Due Limit   : {format_money_amount(due_limit)} Tk\n"
                f"➪ Need More   : {format_money_amount((current_due + total_price) - due_limit)} Tk"
            )
            return

        codes = pop_branch_stock_entries(owner_user_id, category, quantity)
        if len(codes) != quantity:
            await event.reply("❌ Could not reserve the requested stock. Please try again.")
            return

        finance['due'] = str(current_due + total_price)
        increment_user_purchase(target_user_id, category, quantity)
        save_state()

    profile = USER_PROFILES.get(target_user_id, {})
    buyer_name = profile.get('name') or (f"@{profile['username']}" if profile.get('username') else str(target_user_id))
    code_lines = []
    for index, item in enumerate(codes, start=1):
        number_emoji = f"{index}️⃣" if index <= 9 else f"{index}."
        code_lines.append(
            f"{number_emoji} {item['code_head']}\n"
            f"    {item['code_tail']}"
        )
    await event.reply(
        "✅ 𝗗𝘂𝗲 𝗢𝗿𝗱𝗲𝗿 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹\n\n"
        f"👤 Buyer    : {buyer_name}\n"
        f"📦 Product  : {category} UC\n"
        f"🔢 Quantity : {quantity}\n"
        f"💸 Price    : {format_money_amount(total_price)} Tk\n"
        f"🧾 total Due  : {format_money_amount(Decimal(finance['due']))} Tk\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔑 Codes:\n\n"
        + "\n\n".join(code_lines)
        + "\n━━━━━━━━━━━━━━━━━━━"
    )


async def call_ucbot_topup_api(order_id: str, player_id: str, codes: list[str]) -> tuple[dict | None, str | None, float]:
    """Call the external UcBot topup API."""
    started = asyncio.get_running_loop().time()
    if not UCBOT_AUTH_TOKEN:
        return None, "Missing `UCBOT_AUTH_TOKEN` in environment.", 0.0

    headers = {
        'Authorization': UCBOT_AUTH_TOKEN,
        'Content-Type': 'application/json',
    }
    payload = {
        'orderid': order_id,
        'playerid': player_id,
        'code': ",".join(codes),
    }

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(UCBOT_TOPUP_URL, headers=headers, json=payload) as response:
                duration = asyncio.get_running_loop().time() - started
                if response.status != 200:
                    response_text = await response.text()
                    return None, f"HTTP {response.status}: {response_text[:300]}", duration
                return await response.json(), None, duration
    except Exception as e:
        duration = asyncio.get_running_loop().time() - started
        return None, str(e), duration


def next_topup_order_id() -> str:
    """Allocate the next sequential topup order id."""
    global TOPUP_ORDER_SEQ
    TOPUP_ORDER_SEQ += 1
    return str(TOPUP_ORDER_SEQ)


async def topup_with_uc_codes(event, owner_user_id: int, target_user_id: int, uid: str, diamond_key: str, quantity: int):
    """Use reserved UC stock to top up a player through the external API."""
    product = TOPUP_PRODUCT_MAP[diamond_key]
    category = product['category']
    product_label = product['label']
    fee_per_unit = product['fee']
    processing_msg = await event.reply(
        f"⏳ Processing {product_label} topup...\n"
        f"UID: `{uid}`\n"
        f"Quantity: `{quantity}`"
    )

    if quantity <= 0 or quantity > 5:
        await processing_msg.edit("❌ Quantity must be between 1 and 5.")
        return

    async with STATE_LOCK:
        ensure_user_finance_record(target_user_id)
        counts, _ = get_branch_stock_snapshot(owner_user_id)
        available_stock = counts.get(category, 0)
        if available_stock < quantity:
            await processing_msg.edit(
                f"❌ Not enough stock.\n"
                f"➪ Category : {category} UC\n"
                f"➪ Need     : {quantity}\n"
                f"➪ Stock    : {available_stock}"
            )
            return

        unit_price = get_branch_rate(owner_user_id, category)
        if unit_price <= 0:
            await processing_msg.edit(f"❌ Rate for `{category} UC` is not set.")
            return

        finance = USER_FINANCE[target_user_id]
        current_due = Decimal(finance.get('due', '0'))
        due_limit = Decimal(finance.get('due_limit', '0'))
        total_price = (unit_price + fee_per_unit) * Decimal(quantity)
        if current_due + total_price > due_limit:
            await processing_msg.edit(
                "❌ Due limit exceeded.\n"
                f"➪ Current Due : {format_money_amount(current_due)} Tk\n"
                f"➪ Due Limit   : {format_money_amount(due_limit)} Tk\n"
                f"➪ Need More   : {format_money_amount((current_due + total_price) - due_limit)} Tk"
            )
            return

        reserved_entries, reserved_tokens = reserve_branch_stock_entries(owner_user_id, category, quantity)
        if len(reserved_entries) != quantity:
            await processing_msg.edit("❌ Could not reserve the requested stock. Please try again.")
            return

        order_id = next_topup_order_id()
        save_state()

    codes = [f"{item['code_head']} {item['code_tail']}" for item in reserved_entries]
    response_json, error_message, duration = await call_ucbot_topup_api(order_id, uid, codes)

    if error_message or not response_json:
        async with STATE_LOCK:
            restore_branch_stock_tokens(owner_user_id, category, reserved_tokens)
            save_state()
        await processing_msg.edit(f"❌ Topup API failed.\nError: `{error_message or 'Unknown error'}`")
        return

    batch = response_json.get('batch') or []
    success_entries = []
    failed_entries = []

    for index, entry in enumerate(batch):
        code_text = str(entry.get('uc', '')).strip()
        detail = str(entry.get('detail', '')).strip() or "Unknown"
        ok = bool(entry.get('ok'))
        if ok:
            success_entries.append({'code': code_text, 'detail': detail})
        else:
            failed_entries.append({'code': code_text, 'detail': detail})

    async with STATE_LOCK:
        finance = USER_FINANCE[target_user_id]
        old_due = Decimal(finance.get('due', '0'))
        successful_units = len(success_entries)
        charged_units = quantity
        charged_total = (unit_price + fee_per_unit) * Decimal(charged_units)
        finance['due'] = str(old_due + charged_total)
        increment_user_purchase(target_user_id, category, charged_units)
        save_state()
        total_due = Decimal(finance['due'])
        profile = USER_PROFILES.get(target_user_id, {}).copy()

    username = response_json.get('username') or profile.get('name') or (f"@{profile['username']}" if profile.get('username') else str(target_user_id))
    batch_lines = []
    for item in success_entries + failed_entries:
        batch_lines.append(f"{item['code']}  {item['detail']}")

    if successful_units == quantity and quantity > 0:
        status_header = f"✅ {product_label} 💎 TOPUP DONE"
        status_footer = "✅ আপনার Top-Up সম্পন্ন হয়েছে 🎉"
    elif successful_units > 0:
        status_header = f"⚠️ {product_label} 💎 TOPUP PARTIAL"
        status_footer = "⚠️ আপনার Top-Up আংশিক সম্পন্ন হয়েছে"
    else:
        status_header = f"❌ {product_label} 💎 TOPUP FAILED"
        status_footer = "❌ আপনার Top-Up সম্পন্ন হয়নি"

    final_message = (
        f"{status_header}\n"
        "┌──────────────────────────┐\n"
        f"│ Order ID : #{order_id}\n"
        f"│ User     : {username}\n"
        f"│ UID      : {uid}\n"
        "└──────────────────────────┘\n"
        + ("\n".join(batch_lines) if batch_lines else "No batch details returned.")
        + "\n┌──────────────────────────┐\n"
        f"│ Charge : {format_money_amount(charged_total)} ৳ ({format_money_amount(fee_per_unit)}৳ Fee/Unit)\n"
        "│\n"
        f"│ {product_label}  : {successful_units}x\n"
        f"│ Failed : {len(failed_entries)}x\n"
        f"│ due Charge : {format_money_amount(charged_total)}৳ \n"
        f"│ Total Due  : {format_money_amount(old_due)} + {format_money_amount(charged_total)} = {format_money_amount(total_due)}৳ \n"
        "│ \n"
        f"│ Duration : {duration:.2f}s\n"
        "└── 🤖 Powered by TelegonBot ───┘\n\n"
        f"{status_footer}"
    )
    try:
        await processing_msg.edit(final_message)
    except Exception:
        await event.reply(final_message)


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
    user_id, _ = await get_sender_identity(event)
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


LIKE_PATTERN = r'(?i)^/?like\s+(\d+)\s+(100|200)$'


@client.on(events.NewMessage(outgoing=True, pattern=LIKE_PATTERN))
async def like_command_handler(event):
    """Handle like <uid> <100|200> command."""
    match = re.match(LIKE_PATTERN, event.raw_text.strip())
    if not match:
        await event.reply("❌ Invalid format. Use: `/like <uid> 100` or `/like <uid> 200`")
        return

    uid = match.group(1)
    like_type = int(match.group(2))
    actor_user_id, _ = await get_sender_identity(event)

    if get_user_limit(actor_user_id, like_type) <= 0:
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
            increment_usage_for_user(actor_user_id, like_type)
            await record_like_activity(event, uid, like_type, likes_added)
        else:
            # Not enough likes added -> don't count towards limit, just a short note
            formatted_message += "\n\n✅ **Limit refunded**"

        formatted_message += RESPONSE_FOOTER

        try:
            await processing_msg.edit(formatted_message)
        except:
            await event.reply(formatted_message)


START_PATTERN = r'(?i)^/?start$'


@client.on(events.NewMessage(outgoing=True, pattern=START_PATTERN))
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


HELP_PATTERN = r'(?i)^/?help$'


@client.on(events.NewMessage(outgoing=True, pattern=HELP_PATTERN))
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

- `setPrefix R`
  ➤ admin / super admin / owner নিজের branch prefix set করবে
  উদাহরণ: `setPrefix R`

- `Rsignup`
  ➤ private chat-এ এই command send করলে ওই user আপনার branch-এর নিচে register হবে
  নোট: এটা শুধু owner / super admin use করতে পারবে
  উদাহরণ: private chat-এ `Rsignup`

- `Rsignout`
  ➤ private chat-এ এই command send করলে ওই user আপনার branch থেকে remove হবে

- `Rduelimit 200`
  ➤ private chat-এ target user-এর due limit set করবে

- `Rbalance`
  ➤ নিজের due, balance, due limit card দেখাবে
  ➤ owner / super admin `Rbalance 200` দিয়ে target user-এর balance set করতে পারবে

- `Rstock`
  ➤ নিজের branch-এর UC stock summary দেখাবে

- `Rstockadd`
  ➤ command-এর পরে UC code paste করলে auto category-wise stock add হবে

- `Rrate`
  ➤ নিজের branch-এর সব UC rate list দেখাবে

- `R20 19`
  ➤ owner / super admin নিজের branch-এর 20 UC rate set করবে

- `Rdue 20` / `Rdue 20 2`
  ➤ due limit ব্যবহার করে stock থেকে UC code কিনবে

- `Rclear`
  ➤ admin / super admin registered user-এর due clear করবে

- `Rtp <uid> <diamond> [qty]`
  ➤ UC code দিয়ে direct topup করবে, max quantity `5`

- `setadmin @username`
  ➤ নিজের branch-এর নিচে নতুন normal admin বানাবে
  উদাহরণ: `setadmin @testuser`

- `removeadmin @username`
  ➤ normal admin remove করবে
  উদাহরণ: `removeadmin @testuser`

- `setsuperadmin @username`
  ➤ main admin নতুন super admin request শুরু করবে
  উদাহরণ: `setsuperadmin @testuser`

- `removesuperadmin @username`
  ➤ main admin verified/pending super admin remove করবে
  উদাহরণ: `removesuperadmin @testuser`

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


@client.on(events.NewMessage(outgoing=True, pattern=r'(?i)^/?setadmin\s+(@?\w+)$'))
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


@client.on(events.NewMessage(outgoing=True, pattern=r'(?i)^/?removeadmin\s+(@?\w+)$'))
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


@client.on(events.NewMessage(outgoing=True, pattern=r'(?i)^/?removesuperadmin\s+(@?\w+)$'))
async def removesuperadmin_command_handler(event):
    """
    Remove a super admin.
    Usage:
      /removesuperadmin @username
    """
    await log_access_check(event, "removesuperadmin")
    if not await is_owner(event):
        await event.reply(await build_access_denied_message(event, "Owner", "removesuperadmin"))
        return

    text = event.raw_text.strip()
    match = re.match(r'(?i)^/?removesuperadmin\s+(@?\w+)$', text)
    if not match:
        await event.reply("❌ Invalid format.\nUsage: `/removesuperadmin @username`")
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

    await remove_super_admin_for_user(event, target_user_id)


@client.on(events.NewMessage(outgoing=True, pattern=r'(?i)^/?setsuperadmin\s+(@?\w+)$'))
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


SUPERAUTH_PATTERN = r'(?i)^/?superauth\s+(\d+)\s+([A-Za-z0-9]+)\s+(.+)$'


@client.on(events.NewMessage(outgoing=True, pattern=SUPERAUTH_PATTERN))
async def superauth_command_handler(event):
    """
    Submit credentials for pending super admin verification.
    Usage:
      /superauth <api_id> <api_hash> <session_string>
    """
    text = event.raw_text.strip()
    match = re.match(SUPERAUTH_PATTERN, text)
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


@client.on(events.NewMessage(outgoing=True, pattern=r'(?i)^/?setlimit\s+(\d+)(?:\s+(@?\w+))?\s+(100|200)$'))
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


@client.on(events.NewMessage(outgoing=True, pattern=r'(?i)^/?setsplimit\s+(\d+)\s+(@?\w+)\s+(100|200)$'))
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


@client.on(events.NewMessage(outgoing=True, pattern=r'(?i)^/?resetlimit(?:\s+(@?\w+))?$'))
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


MYLIMIT_PATTERN = r'(?i)^/?mylimit$'


@client.on(events.NewMessage(outgoing=True, pattern=MYLIMIT_PATTERN))
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


MYACCESS_PATTERN = r'(?i)^/?myaccess$'


@client.on(events.NewMessage(outgoing=True, pattern=MYACCESS_PATTERN))
async def myaccess_command_handler(event):
    """Show the sender's current access level."""
    await log_access_check(event, "myaccess")
    sender_id, sender_username = await get_sender_identity(event)
    branch_actor_user_id = resolve_branch_actor_user_id(sender_id, sender_username)
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
        f"👤 Branch ID: `{branch_actor_user_id or 'N/A'}`\n"
        f"👤 Manager ID: `{get_manager_id(branch_actor_user_id) or 'N/A'}`\n"
        f"🔑 Prefix: `{get_manager_prefix(branch_actor_user_id) or 'Not set'}`"
    )


@client.on(events.NewMessage(outgoing=True, pattern=r'(?i)^/?alllimit$'))
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


async def prefix_command_handler(event):
    """Handle dynamic setPrefix and branch-aware prefixed commands."""
    if not getattr(event, 'raw_text', None):
        return

    text = event.raw_text.strip()
    if not text:
        return

    sender_id, sender_username = await get_sender_identity(event)
    branch_actor_user_id = resolve_branch_actor_user_id(sender_id, sender_username)

    setprefix_match = re.match(r'(?i)^/?setprefix\s+(\S)$', text)
    if setprefix_match:
        await log_access_check(event, "setprefix")
        if not await can_set_prefix(event):
            await event.reply(await build_access_denied_message(event, "Admin", "setprefix"))
            return

        prefix = setprefix_match.group(1)
        async with STATE_LOCK:
            set_manager_prefix(branch_actor_user_id, prefix)
            save_state()
        await event.reply(
            f"✅ 𝗣𝗿𝗲𝗳𝗶𝘅 `{prefix}` 𝗮𝗹𝗶𝘃𝗲\n"
            f"👤 Branch ID: `{branch_actor_user_id}`"
        )
        return

    if not event.is_private:
        return

    command_match = re.match(r'(?is)^([A-Za-z])(\w+)(?:\s+([\s\S]+))?$', text)
    if not command_match:
        return

    prefix = command_match.group(1)
    action = command_match.group(2).lower()
    argument_text = (command_match.group(3) or '').strip()
    supported_prefixed_actions = {
        "signup",
        "signout",
        "duelimit",
        "balance",
        "stock",
        "stockadd",
        "help",
        "rate",
        "due",
        "clear",
        "tp",
    }
    supported_prefixed_actions.update(UC_STOCK_CATEGORY_ORDER)
    if action not in supported_prefixed_actions:
        return

    try:
        private_chat = await event.get_chat()
    except Exception as e:
        await event.reply(f"❌ Could not resolve private chat user.\nError: `{e}`")
        return

    target_user_id = getattr(private_chat, 'id', None)
    if target_user_id is None:
        await event.reply("❌ Could not detect the target user in this private chat.")
        return

    prefix_owner_id = resolve_prefix_owner_for_private_chat(int(branch_actor_user_id), int(target_user_id), prefix)
    if prefix_owner_id is None:
        return

    async with STATE_LOCK:
        cache_entity_profile(private_chat)
        save_state()

    if action == "signup":
        if prefix_owner_id != branch_actor_user_id:
            return

        await log_access_check(event, "prefixsignup")
        if not await can_use_signup_prefix(event):
            await event.reply(await build_access_denied_message(event, "Admin", "prefixsignup"))
            return
        await register_user_under_manager(event, int(target_user_id))
        return

    if action == "signout":
        if prefix_owner_id != branch_actor_user_id:
            return

        await log_access_check(event, "prefixsignout")
        if not await can_use_signup_prefix(event):
            await event.reply(await build_access_denied_message(event, "Admin", "prefixsignout"))
            return
        if not is_registered_under_branch(prefix_owner_id, int(target_user_id)):
            await event.reply("❌ This user is not registered under your branch.")
            return
        await signout_user_from_manager(event, int(target_user_id))
        return

    if action == "duelimit":
        if prefix_owner_id != branch_actor_user_id:
            return

        await log_access_check(event, "prefixduelimit")
        if not await can_manage_due_limit(event):
            await event.reply(await build_access_denied_message(event, "Admin", "prefixduelimit"))
            return

        if not argument_text:
            await event.reply("❌ Invalid format.\nUsage: `prefixduelimit 200`")
            return

        try:
            amount = Decimal(argument_text)
        except InvalidOperation:
            await event.reply("❌ Invalid amount. Example: `Aduelimit 200`")
            return

        if amount < 0:
            await event.reply("❌ Due limit cannot be negative.")
            return
        if not is_registered_under_branch(prefix_owner_id, int(target_user_id)):
            await event.reply("❌ This user is not registered under your branch.")
            return

        await set_due_limit_for_managed_user(event, int(target_user_id), amount)
        return

    if action == "balance":
        branch_user_id = resolve_prefixed_branch_account_user(
            prefix_owner_id,
            int(branch_actor_user_id),
            int(target_user_id),
        )
        if not is_registered_under_branch(prefix_owner_id, branch_user_id):
            await event.reply("❌ This user is not registered under your branch.")
            return
        if argument_text:
            if prefix_owner_id != branch_actor_user_id:
                return

            await log_access_check(event, "prefixsetbalance")
            if not await can_use_signup_prefix(event):
                await event.reply(await build_access_denied_message(event, "Super Admin", "prefixsetbalance"))
                return

            try:
                amount = Decimal(argument_text)
            except InvalidOperation:
                await event.reply(f"❌ Invalid amount. Example: `{prefix}balance 200`")
                return

            if amount < 0:
                await event.reply("❌ Balance cannot be negative.")
                return

            await set_user_balance_command(event, int(target_user_id), amount)
            return
        await send_balance_card(event, branch_user_id)
        return

    if action == "stock":
        if not is_registered_under_branch(prefix_owner_id, int(branch_actor_user_id)):
            await event.reply("❌ You are not registered under this branch.")
            return
        await send_stock_card(event, prefix_owner_id)
        return

    if action == "stockadd":
        if prefix_owner_id != branch_actor_user_id:
            return

        await log_access_check(event, "prefixstockadd")
        if not await can_use_signup_prefix(event):
            await event.reply(await build_access_denied_message(event, "Super Admin", "prefixstockadd"))
            return

        if not argument_text:
            await event.reply("❌ Invalid format.\nUsage: `Astockadd <paste uc codes>`")
            return

        await add_branch_stock_from_text(event, prefix_owner_id, argument_text)
        return

    if action == "help":
        if not is_registered_under_branch(prefix_owner_id, int(branch_actor_user_id)):
            await event.reply("❌ You are not registered under this branch.")
            return
        await send_prefix_help_card(event, prefix, prefix_owner_id, int(branch_actor_user_id))
        return

    if action == "rate":
        if not is_registered_under_branch(prefix_owner_id, int(branch_actor_user_id)):
            await event.reply("❌ You are not registered under this branch.")
            return
        await send_rate_card(event, prefix_owner_id)
        return

    if action == "due":
        branch_user_id = resolve_prefixed_branch_account_user(
            prefix_owner_id,
            int(branch_actor_user_id),
            int(target_user_id),
        )
        if not is_registered_under_branch(prefix_owner_id, branch_user_id):
            await event.reply("❌ This user is not registered under your branch.")
            return

        parts = argument_text.split() if argument_text else []
        if not parts:
            await send_due_summary_card(event, branch_user_id)
            return

        category = parts[0]
        if category not in UC_STOCK_CATEGORY_ORDER:
            await event.reply("❌ Invalid UC category.")
            return

        quantity = 1
        if len(parts) >= 2:
            if not parts[1].isdigit():
                await event.reply("❌ Quantity must be a whole number.")
                return
            quantity = int(parts[1])

        await purchase_uc_with_due(event, prefix_owner_id, branch_user_id, category, quantity)
        return

    if action == "clear":
        if prefix_owner_id != branch_actor_user_id:
            return

        await log_access_check(event, "prefixclear")
        if not await can_manage_due_limit(event):
            await event.reply(await build_access_denied_message(event, "Admin", "prefixclear"))
            return

        if not is_registered_under_branch(prefix_owner_id, int(target_user_id)):
            await event.reply("❌ This user is not registered under your branch.")
            return

        await clear_user_due_command(event, int(target_user_id))
        return

    if action == "tp":
        branch_user_id = resolve_prefixed_branch_account_user(
            prefix_owner_id,
            int(branch_actor_user_id),
            int(target_user_id),
        )
        if not is_registered_under_branch(prefix_owner_id, branch_user_id):
            await event.reply("❌ This user is not registered under your branch.")
            return

        parts = argument_text.split() if argument_text else []
        if len(parts) < 2:
            await event.reply(f"❌ Invalid format.\nUsage: `{prefix}tp <uid> <diamond> [qty]`")
            return

        uid = parts[0].strip()
        if not uid.isdigit():
            await event.reply("❌ UID must be numeric.")
            return

        diamond_input = parts[1].strip().lower()
        diamond_key = TOPUP_DIAMOND_ALIASES.get(diamond_input)
        if diamond_key is None:
            await event.reply("❌ Invalid topup amount. Supported: 25, 50, 115, 240, 161/weekly, 610, 800/monthly, 1240, 2530.")
            return

        quantity = 1
        if len(parts) >= 3:
            if not parts[2].isdigit():
                await event.reply("❌ Quantity must be a whole number.")
                return
            quantity = int(parts[2])

        await topup_with_uc_codes(event, prefix_owner_id, branch_user_id, uid, diamond_key, quantity)
        return

    if action in set(UC_STOCK_CATEGORY_ORDER):
        if prefix_owner_id != branch_actor_user_id:
            return

        await log_access_check(event, "prefixsetrate")
        if not await can_use_signup_prefix(event):
            await event.reply(await build_access_denied_message(event, "Super Admin", "prefixsetrate"))
            return

        if not argument_text:
            await event.reply(f"❌ Invalid format.\nUsage: `{prefix}{action} 19`")
            return

        try:
            price = Decimal(argument_text)
        except InvalidOperation:
            await event.reply(f"❌ Invalid price. Example: `{prefix}{action} 19`")
            return

        if price < 0:
            await event.reply("❌ Rate cannot be negative.")
            return

        await set_branch_rate_command(event, prefix_owner_id, action, price)


client.add_event_handler(calculator_message_handler, events.NewMessage(outgoing=True))
client.add_event_handler(prefix_command_handler, events.NewMessage())
client.add_event_handler(start_command_handler, events.NewMessage(pattern=START_PATTERN, incoming=True))
client.add_event_handler(help_command_handler, events.NewMessage(pattern=HELP_PATTERN, incoming=True))
client.add_event_handler(like_command_handler, events.NewMessage(pattern=LIKE_PATTERN, incoming=True))
client.add_event_handler(mylimit_command_handler, events.NewMessage(pattern=MYLIMIT_PATTERN, incoming=True))
client.add_event_handler(myaccess_command_handler, events.NewMessage(pattern=MYACCESS_PATTERN, incoming=True))
# Pending super admins send `superauth` to the main account as an incoming DM.
client.add_event_handler(superauth_command_handler, events.NewMessage(pattern=SUPERAUTH_PATTERN, incoming=True))


HANDLER_SPECS = [
    (like_command_handler, r'(?i)^/?like\s+(\d+)\s+(100|200)$'),
    (start_command_handler, r'(?i)^/?start$'),
    (help_command_handler, r'(?i)^/?help$'),
    (setadmin_command_handler, r'(?i)^/?setadmin\s+(@?\w+)$'),
    (removeadmin_command_handler, r'(?i)^/?removeadmin\s+(@?\w+)$'),
    (setsuperadmin_command_handler, r'(?i)^/?setsuperadmin\s+(@?\w+)$'),
    (removesuperadmin_command_handler, r'(?i)^/?removesuperadmin\s+(@?\w+)$'),
    (superauth_command_handler, SUPERAUTH_PATTERN),
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
        target_client.add_event_handler(handler, events.NewMessage(pattern=pattern, outgoing=True))
    target_client.add_event_handler(calculator_message_handler, events.NewMessage(outgoing=True))
    target_client.add_event_handler(prefix_command_handler, events.NewMessage())
    target_client.add_event_handler(start_command_handler, events.NewMessage(pattern=START_PATTERN, incoming=True))
    target_client.add_event_handler(help_command_handler, events.NewMessage(pattern=HELP_PATTERN, incoming=True))
    target_client.add_event_handler(like_command_handler, events.NewMessage(pattern=LIKE_PATTERN, incoming=True))
    target_client.add_event_handler(mylimit_command_handler, events.NewMessage(pattern=MYLIMIT_PATTERN, incoming=True))
    target_client.add_event_handler(myaccess_command_handler, events.NewMessage(pattern=MYACCESS_PATTERN, incoming=True))


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
