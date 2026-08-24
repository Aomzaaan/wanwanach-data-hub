"""Authentication + session management."""
import streamlit as st
import bcrypt
import secrets
from datetime import datetime
import users_store


def hash_password(plain: str) -> str:
    """Generate bcrypt hash — ใช้ตอน setup user ใหม่."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def login(username: str, password: str) -> bool:
    """Try login. Return True if success."""
    user = users_store.get_user(username)
    if not user:
        return False
    if not verify_password(password, user["password_hash"]):
        return False
    # Store in session
    st.session_state["logged_in"] = True
    st.session_state["username"] = username
    st.session_state["user"] = user
    st.session_state["login_time"] = datetime.now().isoformat()
    return True


def logout():
    for k in ["logged_in", "username", "user", "login_time"]:
        st.session_state.pop(k, None)


def is_logged_in() -> bool:
    return st.session_state.get("logged_in", False)


def current_user() -> dict:
    return st.session_state.get("user", {})


def current_role() -> str:
    return current_user().get("role", "guest")


def can_access(dataset_conf: dict) -> bool:
    return current_role() in dataset_conf.get("allowed_roles", [])


def require_login():
    """Call at top of every page. Redirect to login if not logged in."""
    if not is_logged_in():
        show_login_page()
        st.stop()


def show_login_page():
    """Render login form."""
    st.title("🔐 เข้าสู่ระบบ / Sign in")
    st.caption("Wanwanach Data Hub — ฐานข้อมูลกลางยอดขาย")

    with st.form("login_form"):
        col1, col2 = st.columns([2, 1])
        with col1:
            username = st.text_input("👤 Username", placeholder="username")
            password = st.text_input("🔑 Password", type="password")
        submitted = st.form_submit_button("เข้าสู่ระบบ", type="primary", use_container_width=True)

    if submitted:
        if login(username, password):
            st.success(f"✅ ยินดีต้อนรับ {current_user().get('name', username)}")
            st.rerun()
        else:
            st.error("❌ Username หรือ Password ไม่ถูกต้อง")

    with st.expander("ℹ️ ต้องการ Account?"):
        st.info(
            "ติดต่อผู้ดูแลระบบ (Admin) เพื่อขอสิทธิ์เข้าถึงข้อมูล\n\n"
            "📧 data@wanwanach.com"
        )


def generate_api_key() -> str:
    """Generate a new API key (32-char hex)."""
    return "wwn_" + secrets.token_hex(16)
