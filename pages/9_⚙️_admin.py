"""Admin — usage logs + email/role reference.

Note (Option B — Google auto-login):
  User management is now handled at Streamlit Cloud Settings → Sharing.
  Role mapping is defined in config.py → EMAIL_ROLE_MAPPING.
  This page is read-only for admin insights (logs + current mapping).
"""
import pandas as pd
import streamlit as st

from auth import require_login, current_role
from config import EMAIL_ROLE_MAPPING
from usage_log import read_logs
from time_utils import th_str


st.set_page_config(page_title="Admin — Wanwanach", page_icon="⚙️", layout="wide")
require_login()

if current_role() != "admin":
    st.error("⛔ Access denied — Admin only")
    st.stop()

st.title("⚙️ Admin Panel")

tab_users, tab_logs = st.tabs(["👥 Access Control", "📊 Usage Logs"])


# ═══════════════════════════════════════════════════════════
# 👥 Access Control (read-only reference)
# ═══════════════════════════════════════════════════════════
with tab_users:
    st.markdown("### 🔐 Access Control")
    st.info(
        "**Option B — Google-based auto-login**\n\n"
        "การเพิ่ม/ลบ users ทำที่ 2 จุด:\n\n"
        "1. **Streamlit Cloud Settings → Sharing** — invite email → ให้ user login Google ได้\n"
        "2. **config.py → EMAIL_ROLE_MAPPING** — กำหนด role (admin/internal/external)"
    )

    st.markdown("#### 📋 Email → Role mapping (จาก config.py)")
    df = pd.DataFrame([
        {"pattern": pat, "role": role or "❌ deny"}
        for pat, role in EMAIL_ROLE_MAPPING.items()
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### ➕ เพิ่ม user ใหม่")
    st.markdown(
        "1. **Streamlit Cloud** → Settings → Sharing → เพิ่ม email\n"
        "2. ถ้าอยาก role พิเศษ (นอกจาก `@wanwanach.com` = internal):\n"
        "   - แก้ `config.py` → `EMAIL_ROLE_MAPPING` → เพิ่ม `\"user@wanwanach.com\": \"admin\"`\n"
        "   - `git push` → รอ Streamlit redeploy"
    )


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
        # Convert ISO ts → BKK display
        if "ts" in df.columns:
            df["ts_bkk"] = pd.to_datetime(df["ts"], errors="coerce")
            df = df[["ts_bkk", "event", "user", "role", "dataset", "meta"]]

        c1, c2, c3 = st.columns(3)
        c1.metric("รวม events", f"{len(df):,}")
        c2.metric("Unique users", f"{df['user'].nunique():,}")
        if "event" in df.columns:
            c3.metric("Login events", f"{(df['event'] == 'login').sum():,}")

        # Filters
        with st.expander("🎛 กรอง"):
            events = sorted(df["event"].dropna().unique().tolist())
            sel_events = st.multiselect("Event type", events, default=[])
            users = sorted(df["user"].dropna().unique().tolist())
            sel_users = st.multiselect("User", users, default=[])

            if sel_events:
                df = df[df["event"].isin(sel_events)]
            if sel_users:
                df = df[df["user"].isin(sel_users)]

        st.dataframe(df, use_container_width=True, hide_index=True, height=500)

        # ⭐ Timeline chart
        if "ts_bkk" in df.columns and len(df) > 0:
            import plotly.express as px
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
