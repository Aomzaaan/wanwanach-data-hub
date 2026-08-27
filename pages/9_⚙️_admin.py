"""Admin — user management, usage logs, hash generator."""
import streamlit as st
import pandas as pd

from auth import require_login, current_role, hash_password
from usage_log import read_logs
import users_store


st.set_page_config(page_title="Admin — Wanwanach", page_icon="⚙️", layout="wide")
require_login()

if current_role() != "admin":
    st.error("⛔ Access denied — Admin only")
    st.stop()

st.title("⚙️ Admin Panel")

tab_users, tab_logs, tab_hash = st.tabs(["👥 Users", "📊 Usage Logs", "🔧 Password Hash"])


# ═══════════════════════════════════════════════════════════
# 👥 Users
# ═══════════════════════════════════════════════════════════
with tab_users:
    ROLES = ["admin", "internal", "external"]
    ROLE_DESC = {
        "admin":    "ดูทุก dataset + จัดการระบบ",
        "internal": "ดูทุก dataset (raw + aggregated)",
        "external": "ดูเฉพาะ aggregated (2025+)",
    }

    users = users_store.get_all()
    current_username = st.session_state.get("username", "")

    # ─── Current users table ───
    st.markdown("### 📋 รายชื่อผู้ใช้ทั้งหมด")
    df = pd.DataFrame([
        {
            "username": u,
            "name":  info.get("name", ""),
            "role":  info.get("role", ""),
            "email": info.get("email", ""),
        }
        for u, info in users.items()
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ─── Add new user ───
    st.divider()
    st.markdown("### ➕ เพิ่ม User ใหม่")
    with st.form("add_user", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            new_username = st.text_input("Username (ไม่มีช่องว่าง)", placeholder="e.g. somchai")
            new_name     = st.text_input("ชื่อ-นามสกุล", placeholder="e.g. คุณสมชาย")
            new_email    = st.text_input("Email")
        with c2:
            new_role     = st.selectbox("Role", ROLES, format_func=lambda r: f"{r} — {ROLE_DESC[r]}")
            new_password = st.text_input("Password (ตั้งครั้งแรก)", type="password")
            new_password2 = st.text_input("Password (ยืนยัน)", type="password")
        submitted = st.form_submit_button("➕ เพิ่ม User", type="primary")

    if submitted:
        errors = []
        if not new_username or " " in new_username:
            errors.append("Username ห้ามว่าง/มีช่องว่าง")
        if new_username in users:
            errors.append(f"Username `{new_username}` มีอยู่แล้ว")
        if not new_name:
            errors.append("ชื่อว่าง")
        if not new_password:
            errors.append("Password ว่าง")
        if new_password != new_password2:
            errors.append("Password 2 ครั้งไม่ตรงกัน")
        if len(new_password) < 6:
            errors.append("Password ต้องยาว ≥ 6 ตัว")

        if errors:
            for e in errors:
                st.error(f"❌ {e}")
        else:
            users_store.add_or_update(new_username, {
                "password_hash": hash_password(new_password),
                "name": new_name,
                "role": new_role,
                "email": new_email or "",
            })
            st.success(f"✅ เพิ่ม `{new_username}` สำเร็จ")
            st.rerun()

    # ─── Edit / Delete existing users ───
    st.divider()
    st.markdown("### ✏️ แก้ไข / ลบ User")

    edit_username = st.selectbox(
        "เลือก User ที่จะแก้ไข:",
        options=[""] + [u for u in users.keys() if u != current_username],
        help="ไม่สามารถแก้/ลบ user ของตัวเองที่กำลัง login ได้",
    )

    if edit_username:
        u_info = users[edit_username]
        with st.container(border=True):
            st.markdown(f"#### 👤 `{edit_username}`")

            with st.form(f"edit_{edit_username}"):
                c1, c2 = st.columns(2)
                with c1:
                    e_name  = st.text_input("ชื่อ", value=u_info.get("name", ""))
                    e_email = st.text_input("Email", value=u_info.get("email", ""))
                with c2:
                    e_role = st.selectbox(
                        "Role",
                        ROLES,
                        index=ROLES.index(u_info.get("role", "external")) if u_info.get("role") in ROLES else 2,
                        format_func=lambda r: f"{r} — {ROLE_DESC[r]}",
                    )
                    st.markdown("**Reset Password** (เว้นว่างถ้าไม่เปลี่ยน)")
                    e_new_pw = st.text_input("Password ใหม่", type="password", key=f"pw_{edit_username}")

                b1, b2 = st.columns([1, 1])
                do_save = b1.form_submit_button("💾 บันทึกการแก้ไข", type="primary", use_container_width=True)
                do_delete = b2.form_submit_button("🗑 ลบ User นี้", use_container_width=True)

            if do_save:
                updated = {
                    "password_hash": (
                        hash_password(e_new_pw) if e_new_pw
                        else u_info["password_hash"]
                    ),
                    "name": e_name,
                    "role": e_role,
                    "email": e_email or "",
                }
                users_store.add_or_update(edit_username, updated)
                pw_msg = " + reset password" if e_new_pw else ""
                st.success(f"✅ อัพเดท `{edit_username}` สำเร็จ{pw_msg}")
                st.rerun()

            if do_delete:
                actor = st.session_state.get("username", "")
                if users_store.delete(edit_username, actor=actor):
                    st.success(f"✅ ลบ `{edit_username}` สำเร็จ")
                    st.rerun()
                else:
                    st.error("❌ ไม่สามารถลบตัวเองได้ — ป้องกัน self-lockout")


# ═══════════════════════════════════════════════════════════
# 📊 Usage Logs
# ═══════════════════════════════════════════════════════════
with tab_logs:
    st.markdown("### 📊 Usage Log (500 latest)")
    logs = read_logs(500)
    if not logs:
        st.info("ยังไม่มี log")
    else:
        df = pd.DataFrame(logs)
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)

        st.markdown("#### 📈 สรุป")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total events", len(df))
        c2.metric("Unique users", df["user"].nunique())
        c3.metric("Downloads", (df["event"] == "download").sum())

        st.markdown("#### กิจกรรมแต่ละ user")
        st.dataframe(
            df.groupby(["user", "event"]).size().unstack(fill_value=0),
            use_container_width=True,
        )


# ═══════════════════════════════════════════════════════════
# 🔧 Password Hash
# ═══════════════════════════════════════════════════════════
with tab_hash:
    st.markdown("### 🔐 Generate Password Hash")
    st.caption("สำหรับกรณีต้องแก้ `config.py` ตรงๆ (เช่น seed initial admin)")
    with st.form("hash_form"):
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Generate Hash")
    if submitted and pw:
        h = hash_password(pw)
        st.code(h)
        st.caption("💡 สำหรับ user ใหม่ ใช้ tab 👥 Users จะสะดวกกว่า")
