"""Usage logging — durable via R2 (survives Streamlit Cloud redeploys)."""
import streamlit as st

import r2_store
from time_utils import th_now

LOG_KEY = "control/usage_log.jsonl"
MAX_LOG_LINES = 10000  # rotate to keep blob under ~2 MB


def log_event(event_type: str, dataset_id: str = "", meta: dict = None):
    """Log a usage event (login, view, download) — thread-safe, never crashes."""
    user = st.session_state.get("user", {})
    entry = {
        "ts": th_now().isoformat(timespec="seconds"),  # BKK time
        "event": event_type,
        "user": st.session_state.get("username", "anonymous"),
        "role": user.get("role", ""),
        "dataset": dataset_id,
        "meta": meta or {},
    }
    r2_store.append_jsonl(LOG_KEY, entry, max_lines=MAX_LOG_LINES)


def read_logs(limit: int = 500) -> list:
    """Read recent logs (admin only)."""
    return r2_store.read_jsonl_tail(LOG_KEY, limit=limit)
