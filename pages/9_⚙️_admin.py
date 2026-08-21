"""Admin — user management, usage logs, hash generator."""
import streamlit as st
import pandas as pd

from auth import require_login, current_role, hash_password
from usage_log import read_logs
from config import USERS


st.set_page_config(page_title="Admin — Wanwanach", page_icon="⚙️", layout="wide")
require_login()

if current_role() != "admin":
    st.error("⛔ Access denied — Admin only")
    st.stop()

st.title("⚙️ Admin Panel")

tab1, tab2, tab3 = st.tabs(["📊 Usage Logs", "👥 Users", "🔧 Password Hash"])

with tab1:
    st.markdown("### 📊 Usage Log (500 latest)")
    logs = read_logs(500)
    if not logs:
        st.info("ยังไม่มี log")
    else:
        df = pd.DataFrame(logs)
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)

        st.markdown("#### 📈 สรุป")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total events", len(df))
        c2.metric("Unique users", df["user"].nunique())
        c3.metric("Downloads", (df["event"] == "download").sum())

        # Events by user
        st.markdown("#### กิจกรรมแต่ละ user")
        st.dataframe(
            df.groupby(["user", "event"]).size().unstack(fill_value=0),
            use_container_width=True,
        )

with tab2:
    st.markdown("### 👥 Users")
    st.info("แก้ user ที่ไฟล์ `config.py` → USERS dict")

    users_df = pd.DataFrame([
        {"username": u, "name": info["name"], "role": info["role"], "email": info["email"]}
        for u, info in USERS.items()
    ])
    st.dataframe(users_df, use_container_width=True, hide_index=True)

with tab3:
    st.markdown("### 🔐 Generate Password Hash")
    st.caption("สำหรับสร้าง user ใหม่ในไฟล์ `config.py`")
    with st.form("hash_form"):
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Generate Hash")
    if submitted and pw:
        h = hash_password(pw)
        st.code(h)
        st.caption("Copy hash นี้ไปใส่ใน USERS ใน config.py")
