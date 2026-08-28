"""
Authentication — Option B: Auto-login via Streamlit's Google identity.

User flow:
  1. Streamlit Cloud "Only specific people can view" gates Google login
  2. Once passed, st.experimental_user.email is populated
  3. This module maps email → role via EMAIL_ROLE_MAPPING in config.py
  4. No password / no user CRUD needed

Fallback: local dev (no Google auth) → shows a manual email input for testing.
"""
import html as _html
import secrets

import streamlit as st

from config import EMAIL_ROLE_MAPPING, USERS as SEED_USERS
from time_utils import th_now
from usage_log import log_event


# ─── Helpers ────────────────────────────────────────────


def safe_html(s: str) -> str:
    """Escape user-controlled strings before injecting into HTML markdown."""
    return _html.escape(str(s or ""))


def _google_email() -> str | None:
    """Read Google-authenticated email from Streamlit.
    Returns None if not available (e.g., local dev, public app)."""
    try:
        email = st.experimental_user.email  # newer Streamlit
    except Exception:
        try:
            email = st.user.email  # very new API
        except Exception:
            email = None
    if not email:
        return None
    return str(email).strip().lower()


def determine_role(email: str | None) -> str | None:
    """Map email → role from EMAIL_ROLE_MAPPING. Returns None if disallowed."""
    if not email:
        return None
    email = email.strip().lower()

    # 1. Exact match (highest priority)
    if email in EMAIL_ROLE_MAPPING:
        return EMAIL_ROLE_MAPPING[email]

    # 2. Domain match (@wanwanach.com etc.)
    for pattern, role in EMAIL_ROLE_MAPPING.items():
        if pattern.startswith("@") and email.endswith(pattern):
            return role

    # 3. Fallback (usually None = deny)
    return EMAIL_ROLE_MAPPING.get("*")


def _display_name(email: str) -> str:
    """Best-effort name from email — 'data@wanwanach.com' → 'Data'."""
    local = email.split("@", 1)[0]
    return local.replace(".", " ").replace("_", " ").title()


def _autologin(email: str, role: str):
    """Set session for authenticated user."""
    st.session_state["logged_in"] = True
    st.session_state["username"] = email
    st.session_state["user"] = {
        "email": email,
        "name": _display_name(email),
        "role": role,
    }
    st.session_state["login_time"] = th_now().isoformat()


# ─── Public API ─────────────────────────────────────────


def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)


def current_user() -> dict:
    return st.session_state.get("user", {})


def current_role() -> str:
    return current_user().get("role", "guest")


def can_access(dataset_conf: dict) -> bool:
    return current_role() in dataset_conf.get("allowed_roles", [])


def logout():
    """Clear all session state.
    Note: won't log user out of Google — that must be done via Google Account UI."""
    st.session_state.clear()


def require_login():
    """Gate every page. Auto-login via Google email, or show local-dev override."""
    if is_logged_in():
        return

    email = _google_email()

    if email:
        # ⭐ Production path — Streamlit Cloud with Google whitelist
        role = determine_role(email)
        if role is None:
            _show_denied(email)
            st.stop()
        _autologin(email, role)
        log_event("login", meta={"method": "google", "email": email})
        st.rerun()
    else:
        # ⚠️ Fallback path — local dev / public app (no Google session)
        _show_local_dev_login()
        st.stop()


def _show_denied(email: str):
    st.title("🚫 Access Denied")
    st.error(
        f"บัญชี **{safe_html(email)}** ยังไม่มีสิทธิ์เข้าใช้ Portal นี้\n\n"
        f"กรุณาติดต่อผู้ดูแลระบบเพื่อเปิดสิทธิ์"
    )
    st.caption("📧 data@wanwanach.com")


def _show_local_dev_login():
    """Manual email input — only for local dev where st.experimental_user is empty."""
    st.title("🔐 เข้าสู่ระบบ / Sign in")
    st.caption("Wanwanach Data Hub")
    st.warning(
        "⚠️ ตรวจไม่พบ Google session — โหมด local dev\n\n"
        "หน้านี้ควรจะไม่เห็นบน production (Streamlit Cloud)"
    )

    with st.form("dev_login"):
        email = st.text_input("📧 Email", placeholder="data@wanwanach.com")
        submit = st.form_submit_button("Login")

    if submit and email:
        role = determine_role(email)
        if role is None:
            st.error(f"❌ Email `{email}` ไม่มีสิทธิ์เข้าใช้")
        else:
            _autologin(email.lower(), role)
            log_event("login", meta={"method": "local_dev", "email": email})
            st.rerun()


# ─── Legacy helpers (kept for admin panel compat) ───────


def hash_password(plain: str) -> str:
    """Kept for admin panel Generate Hash tool — not used for login."""
    import bcrypt
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def generate_api_key() -> str:
    return "wwn_" + secrets.token_hex(16)
