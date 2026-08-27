"""Authentication + session management — hardened."""
import html as _html
import secrets
import time

import bcrypt
import streamlit as st

import users_store
from time_utils import th_now
from usage_log import log_event


# ─── Rate-limit config ──────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 60 * 15  # 15 minutes


def hash_password(plain: str) -> str:
    """Generate bcrypt hash — ใช้ตอน setup user ใหม่."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def _get_rl_state() -> dict:
    """Rate-limit state kept in session_state."""
    if "_rl" not in st.session_state:
        st.session_state["_rl"] = {"fails": 0, "lock_until": 0.0}
    return st.session_state["_rl"]


def _is_locked() -> tuple[bool, int]:
    """Return (is_locked, seconds_remaining)."""
    rl = _get_rl_state()
    remaining = int(rl["lock_until"] - time.time())
    return remaining > 0, max(0, remaining)


def login(username: str, password: str) -> bool:
    """Try login. Returns True if success. Rate-limits after N fails."""
    rl = _get_rl_state()
    locked, _ = _is_locked()
    if locked:
        return False

    user = users_store.get_user(username)
    ok = bool(user) and verify_password(password, user["password_hash"])

    if not ok:
        rl["fails"] += 1
        if rl["fails"] >= MAX_FAILED_ATTEMPTS:
            rl["lock_until"] = time.time() + LOCKOUT_SECONDS
            log_event("login_locked", meta={"username": username[:32]})
        else:
            log_event("login_failed", meta={"username": username[:32]})
        return False

    # Success — reset RL, set session
    rl["fails"] = 0
    rl["lock_until"] = 0.0
    st.session_state["logged_in"] = True
    st.session_state["username"] = username
    st.session_state["user"] = user
    st.session_state["login_time"] = th_now().isoformat()
    log_event("login", meta={"username": username})
    return True


def logout():
    """Clear all session state — including filters + caches."""
    st.session_state.clear()


def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)


def current_user() -> dict:
    return st.session_state.get("user", {})


def current_role() -> str:
    return current_user().get("role", "guest")


def can_access(dataset_conf: dict) -> bool:
    return current_role() in dataset_conf.get("allowed_roles", [])


def safe_html(s: str) -> str:
    """Escape user-controlled strings before injecting into HTML markdown."""
    return _html.escape(str(s or ""))


def require_login():
    """Call at top of every page. Redirect to login if not logged in."""
    if not is_logged_in():
        show_login_page()
        st.stop()


def show_login_page():
    """Render login form with rate-limit indicator."""
    st.title("🔐 เข้าสู่ระบบ / Sign in")
    st.caption("Wanwanach Data Hub — ฐานข้อมูลกลางยอดขาย")

    locked, remaining = _is_locked()
    if locked:
        m, s = divmod(remaining, 60)
        st.error(f"🚫 ล็อคชั่วคราวจากการ login ผิดหลายครั้ง — รอ {m}:{s:02d} นาที")
        return

    with st.form("login_form"):
        col1, col2 = st.columns([2, 1])
        with col1:
            username = st.text_input("👤 Username", placeholder="username", max_chars=64)
            password = st.text_input("🔑 Password", type="password", max_chars=128)
        submitted = st.form_submit_button("เข้าสู่ระบบ", type="primary", use_container_width=True)

    if submitted:
        if login(username, password):
            st.success(f"✅ ยินดีต้อนรับ {safe_html(current_user().get('name', username))}")
            st.rerun()
        else:
            rl = _get_rl_state()
            attempts_left = max(0, MAX_FAILED_ATTEMPTS - rl["fails"])
            if attempts_left > 0:
                st.error(f"❌ Username หรือ Password ไม่ถูกต้อง — เหลืออีก {attempts_left} ครั้ง")
            else:
                st.error("🚫 ล็อคชั่วคราว 15 นาที")

    with st.expander("ℹ️ ต้องการ Account?"):
        st.info(
            "ติดต่อผู้ดูแลระบบ (Admin) เพื่อขอสิทธิ์เข้าถึงข้อมูล\n\n"
            "📧 data@wanwanach.com"
        )


def generate_api_key() -> str:
    """Generate a new API key (32-char hex)."""
    return "wwn_" + secrets.token_hex(16)
