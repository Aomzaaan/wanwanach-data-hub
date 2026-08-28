"""Admin — user CRUD + usage logs + password hash generator."""
import pandas as pd
import plotly.express as px
import streamlit as st

from auth import require_login, current_role, hash_password, safe_html
from time_utils import th_str
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
    st.caption(
        "⚠️ **สำคัญ**: email ต้องตรงกับที่ invite ที่ Streamlit Cloud Settings → Sharing "
        "ไม่งั้น user เข้าจากภายนอกไม่ได้"
    )

    with st.form("add_user"):
        c1, c2, c3 = st.columns(3)
        new_username = c1.text_input("Username", placeholder="เช่น logistic", max_chars=32)
        new_name = c2.text_input("Display Name", placeholder="ทีม Logistics")
        new_email = c3.text_input("Email", placeholder="logistic@wanwanach.com")

        c4, c5 = st.columns([2, 1])
        new_password = c4.text_input("Password", type="password", max_chars=128)
        new_role = c5.selectbox("Role", ROLES, index=1)
        st.caption(f"**{new_role}** — {ROLE_DESC[new_role]}")

        submitted = st.form_submit_button("➕ Add User", type="primary")

    if submitted:
        if not (new_username and new_password and new_name and new_email):
            st.error("❌ กรอกให้ครบทุกช่อง")
        elif new_username in users:
            st.error(f"❌ Username `{new_username}` มีอยู่แล้ว")
        else:
            try:
                users_store.add_or_update(new_username, {
                    "password_hash": hash_password(new_password),
                    "name": new_name,
                    "role": new_role,
                    "email": new_email,
                })
                st.success(f"✅ เพิ่ม `{new_username}` (role: {new_role}) สำเร็จ")
                st.rerun()
            except Exception as e:
                st.error(f"❌ {type(e).__name__}: {e}")

    # ─── Edit / Delete existing user ───
    st.divider()
    st.markdown("### ✏️ แก้ไข / ลบ User")

    editable_usernames = [u for u in users.keys() if u != current_username]
    if not editable_usernames:
        st.info("ยังไม่มี user อื่นให้แก้ไข (ไม่แสดง user ปัจจุบัน)")
    else:
        edit_username = st.selectbox("เลือก user", editable_usernames)
        info = users[edit_username]

        with st.form("edit_user"):
            c1, c2, c3 = st.columns(3)
            e_name = c1.text_input("Display Name", value=info.get("name", ""))
            e_email = c2.text_input("Email", value=info.get("email", ""))
            e_role = c3.selectbox("Role", ROLES, index=ROLES.index(info.get("role", "internal")))

            e_new_pw = st.text_input(
                "🔑 Password ใหม่ (ปล่อยว่าง = ไม่เปลี่ยน)",
                type="password", max_chars=128,
            )

            c1, c2 = st.columns(2)
            do_update = c1.form_submit_button("💾 บันทึกการแก้ไข", type="primary")
            do_delete = c2.form_submit_button("🗑 ลบ User", type="secondary")

            if do_update:
                updated = {
                    "password_hash": (
                        hash_password(e_new_pw) if e_new_pw else info["password_hash"]
                    ),
                    "name": e_name or "",
                    "role": e_role,
                    "email": e_email or "",
                }
                try:
                    users_store.add_or_update(edit_username, updated)
                    pw_msg = " + reset password" if e_new_pw else ""
                    st.success(f"✅ อัพเดท `{edit_username}` สำเร็จ{pw_msg}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {type(e).__name__}: {e}")

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
    st.markdown("### 📊 Recent Activity")

    max_rows = st.slider("จำนวน log ล่าสุด", 50, 1000, 200, step=50)
    logs = read_logs(limit=max_rows)

    if not logs:
        st.info("ยังไม่มี log")
    else:
        df = pd.DataFrame(logs)
        if "ts" in df.columns:
            df["ts_bkk"] = pd.to_datetime(df["ts"], errors="coerce")
            df = df[["ts_bkk", "event", "user", "role", "dataset", "meta"]]

        c1, c2, c3 = st.columns(3)
        c1.metric("รวม events", f"{len(df):,}")
        c2.metric("Unique users", f"{df['user'].nunique():,}")
        if "event" in df.columns:
            c3.metric("Login events", f"{(df['event'] == 'login').sum():,}")

        with st.expander("🎛 กรอง"):
            events = sorted(df["event"].dropna().unique().tolist())
            sel_events = st.multiselect("Event type", events, default=[])
            users_l = sorted(df["user"].dropna().unique().tolist())
            sel_users = st.multiselect("User", users_l, default=[])

            if sel_events:
                df = df[df["event"].isin(sel_events)]
            if sel_users:
                df = df[df["user"].isin(sel_users)]

        st.dataframe(df, use_container_width=True, hide_index=True, height=500)

        # Timeline chart
        if "ts_bkk" in df.columns and len(df) > 0:
            df["date"] = df["ts_bkk"].dt.date
            daily = df.groupby(["date", "event"], as_index=False).size()
            fig = px.bar(
                daily, x="date", y="size", color="event",
                title="กิจกรรมรายวัน",
                labels={"size": "จำนวน events"},
            )
            fig.update_layout(height=300, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

    st.caption(f"อัพเดทล่าสุด: {th_str()}")


# ═══════════════════════════════════════════════════════════
# 🔧 Password Hash Generator
# ═══════════════════════════════════════════════════════════
with tab_hash:
    st.markdown("### 🔧 Generate Password Hash")
    st.caption("ใช้สร้าง bcrypt hash — เอาไปใส่ใน Streamlit Secrets `[seed_admin]`")

    pw = st.text_input("Password", type="password", max_chars=128, key="hash_pw")
    if st.button("Generate Hash"):
        if not pw:
            st.error("กรุณากรอก password")
        else:
            h = hash_password(pw)
            st.success("✅ Bcrypt hash (copy ไปใช้)")
            st.code(h, language=None)
