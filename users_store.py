"""
User store — dynamic user management.

Users are stored in `.users.json` (runtime, editable via UI).
On first run, seeded from USERS in config.py.

Format:
{
    "admin":  {"password_hash": "$2b$...", "name": "...", "role": "admin", "email": "..."},
    "wanwan": {...},
}

Thread-safe read-modify-write via threading.Lock + atomic file rename.
"""
import json
import os
import tempfile
import threading

from config import USERS as SEED_USERS

USERS_FILE = ".users.json"
_LOCK = threading.Lock()


def _load_raw() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_raw(data: dict):
    """Atomic write: temp file + rename (POSIX)."""
    dir_ = os.path.dirname(os.path.abspath(USERS_FILE)) or "."
    tmp_fd, tmp_path = tempfile.mkstemp(prefix=".users_", suffix=".tmp", dir=dir_)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, USERS_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def get_all() -> dict:
    """Get all users. Seeds from config.py if empty."""
    users = _load_raw()
    if not users:
        # Seed from config.py on first run
        users = dict(SEED_USERS)
        try:
            _save_raw(users)
        except Exception:
            pass  # Fall back to in-memory
    return users


def get_user(username: str) -> dict | None:
    return get_all().get(username)


def add_or_update(username: str, user_data: dict) -> bool:
    """Add or update user. Returns True if added, False if updated."""
    with _LOCK:
        users = _load_raw() or dict(SEED_USERS)
        is_new = username not in users
        users[username] = user_data
        _save_raw(users)
        return is_new


def delete(username: str) -> bool:
    """Delete user. Returns True if deleted."""
    with _LOCK:
        users = _load_raw() or dict(SEED_USERS)
        if username in users:
            del users[username]
            _save_raw(users)
            return True
        return False


def reset_password(username: str, new_hash: str) -> bool:
    """Update just the password hash."""
    with _LOCK:
        users = _load_raw() or dict(SEED_USERS)
        if username not in users:
            return False
        users[username]["password_hash"] = new_hash
        _save_raw(users)
        return True
