"""Usage logging — track downloads per user."""
import streamlit as st
from datetime import datetime
import json
import os
import threading

LOG_FILE = ".usage_log.jsonl"

# ⭐ Serialize concurrent writes across user sessions
_LOG_LOCK = threading.Lock()


def log_event(event_type: str, dataset_id: str = "", meta: dict = None):
    """Log a usage event (login, view, download) — thread-safe."""
    user = st.session_state.get("user", {})
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event_type,
        "user": st.session_state.get("username", "anonymous"),
        "role": user.get("role", ""),
        "dataset": dataset_id,
        "meta": meta or {},
    }
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    try:
        with _LOG_LOCK:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception:
        pass  # Don't crash on log failure


def read_logs(limit: int = 500) -> list:
    """Read recent logs (admin only)."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, encoding="utf-8") as f:
        lines = f.readlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries[::-1]  # newest first
