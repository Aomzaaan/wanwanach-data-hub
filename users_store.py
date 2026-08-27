"""
User store — durable via R2 (not local FS which is ephemeral on Streamlit Cloud).

Users are stored in R2 key: control/users.json
On first run, seeded from USERS in config.py (loaded from Streamlit secrets).

Format:
{
    "admin": {"password_hash": "$2b$...", "name": "...", "role": "admin", "email": "..."},
    ...
}

Thread-safe read-modify-write via threading.Lock.
"""
import threading
import copy

import r2_store
from config import USERS as SEED_USERS

USERS_KEY = "control/users.json"
_LOCK = threading.Lock()


def _load_raw() -> dict:
    """Load users from R2. Never returns None."""
    data = r2_store.get_json(USERS_KEY, default={})
    return data if isinstance(data, dict) else {}


def _save_raw(data: dict):
    r2_store.put_json(USERS_KEY, data)


def get_all() -> dict:
    """Get all users. Seeds from SEED_USERS on first run only."""
    users = _load_raw()
    if not users and SEED_USERS:
        # Only seed if R2 store is EMPTY — never overwrite existing data
        users = copy.deepcopy(SEED_USERS)
        try:
            _save_raw(users)
        except Exception:
            pass
    return users


def get_user(username: str) -> dict | None:
    return get_all().get(username)


def _validate(user_data: dict) -> bool:
    """Basic schema check — prevent broken writes."""
    if not isinstance(user_data, dict):
        return False
    required = {"password_hash", "name", "role", "email"}
    return required.issubset(user_data.keys())


def add_or_update(username: str, user_data: dict) -> bool:
    """Add or update user. Returns True if added, False if updated.
    Raises ValueError on bad data.
    """
    if not _validate(user_data):
        raise ValueError("user_data missing required fields")
    with _LOCK:
        users = _load_raw()
        # ⚠️ If R2 returned empty, seed FIRST — don't overwrite with just the new user
        if not users:
            users = copy.deepcopy(SEED_USERS)
        is_new = username not in users
        users[username] = user_data
        _save_raw(users)
        return is_new


def delete(username: str, actor: str = "") -> bool:
    """Delete user. Blocks self-delete. Returns True if deleted."""
    if actor and username == actor:
        return False  # server-side protection against self-lockout
    with _LOCK:
        users = _load_raw()
        if not users:
            return False
        if username in users:
            del users[username]
            _save_raw(users)
            return True
        return False


def reset_password(username: str, new_hash: str) -> bool:
    """Update just the password hash."""
    with _LOCK:
        users = _load_raw()
        if not users or username not in users:
            return False
        users[username]["password_hash"] = new_hash
        _save_raw(users)
        return True
