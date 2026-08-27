"""
Wanwanach Data Hub — Main Page
==============================
Streamlit portal สำหรับดึงข้อมูลยอดขาย
"""
import streamlit as st
from datetime import datetime

from config import APP_TITLE, APP_SUBTITLE, DATASETS
from auth import require_login, current_user, current_role, logout, can_access, safe_html
from datasets import dataset_metadata
from usage_log import log_event
from time_utils import th_now, th_str


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        return f"{local[0]}*@{domain}"
    return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"


st.set_page_config(
    page_title="Wanwanach Data Hub",
    page_icon="🥐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Auth gate ───
require_login()

# ─── Sidebar ───
with st.sidebar:
    st.markdown(f"### 👤 {safe_html(current_user().get('name', 'User'))}")
    st.caption(f"Role: `{safe_html(current_role())}`")
    with st.expander("📧 Email"):
        st.caption(_mask_email(current_user().get("email", "")))
    if st.button("🚪 ออกจากระบบ", use_container_width=True):
        log_event("logout")
        logout()
        st.rerun()

    st.divider()
    st.markdown("### 📖 เมนู")
    st.page_link("app.py", label="🏠 หน้าแรก")
    st.page_link("pages/5_📊_dashboard.py", label="📊 Overview")
    st.page_link("pages/6_🥐_products.py", label="🥐 Products")
    st.page_link("pages/7_🗺_locations.py", label="🗺 Locations")
    st.divider()
    st.page_link("pages/1_📊_datasets.py", label="🗂 ข้อมูลทั้งหมด")
    st.page_link("pages/2_📈_charts.py", label="📈 กราฟ (custom)")
    st.page_link("pages/4_📚_documentation.py", label="📚 คู่มือ / Docs")
    if current_role() == "admin":
        st.divider()
        st.markdown("### ⚙️ Admin")
        st.page_link("pages/9_⚙️_admin.py", label="👥 Users & Logs")

# ─── Main Content ───
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

# Welcome banner
st.markdown(
    f"""
    <div style="background:linear-gradient(90deg,#1976D2,#42A5F5); padding:20px; border-radius:10px; color:white;">
        <h3 style="margin:0;">👋 ยินดีต้อนรับ, {safe_html(current_user().get('name', 'User'))}!</h3>
        <p style="margin:10px 0 0 0; opacity:0.9;">
            เลือก dataset จากด้านล่างเพื่อเริ่มดูข้อมูล กรอง และดาวน์โหลด
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("### 📊 Datasets ที่คุณเข้าถึงได้")

# ─── Dataset Cards ───
accessible = [(did, conf) for did, conf in DATASETS.items() if can_access(conf)]

if not accessible:
    st.warning("⚠️ Account ของคุณยังไม่มีสิทธิ์เข้าถึง dataset ใดๆ ติดต่อ Admin")
else:
    cols = st.columns(2)
    for i, (dataset_id, conf) in enumerate(accessible):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"#### {conf['name']}")
                st.caption(conf["description"])

                # Metadata
                meta = dataset_metadata(dataset_id)
                if meta.get("available"):
                    c1, c2 = st.columns(2)
                    c1.metric("ขนาด", f"{meta['size_mb']:.1f} MB")
                    lm = meta["last_modified"]
                    c2.metric("อัพเดทล่าสุด", th_str(lm))
                else:
                    st.warning(f"⚠️ ไม่พร้อมใช้งาน: {meta.get('error', 'unknown')}")

                st.caption(f"🔄 ความถี่: {conf['update_freq']}")

                # Action buttons
                b1, b2 = st.columns(2)
                if b1.button(f"🔍 เปิด", key=f"open_{dataset_id}", use_container_width=True):
                    st.session_state["selected_dataset"] = dataset_id
                    st.switch_page("pages/1_📊_datasets.py")
                if b2.button(f"📈 กราฟ", key=f"chart_{dataset_id}", use_container_width=True):
                    st.session_state["selected_dataset"] = dataset_id
                    st.switch_page("pages/2_📈_charts.py")

# ─── Footer ───
st.divider()
c1, c2, c3 = st.columns(3)
c1.caption(f"🕐 {th_str()}")
c2.caption("🥐 Wanwanach Data Hub v1.0")
c3.caption("📧 data@wanwanach.com")

# Log the visit (throttle 1 per 5 min to avoid spam on rerun)
import time as _time
_now = _time.time()
if _now - st.session_state.get("_last_home_log", 0) > 300:
    log_event("view", "home")
    st.session_state["_last_home_log"] = _now
