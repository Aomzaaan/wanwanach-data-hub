"""API Keys — สำหรับดึงข้อมูลผ่าน Python/Excel/curl."""
import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

from auth import require_login, current_user, generate_api_key
from usage_log import log_event


st.set_page_config(page_title="API Keys — Wanwanach", page_icon="🔑", layout="wide")
require_login()

st.title("🔑 API Keys")
st.caption("สร้าง key สำหรับดึงข้อมูลจาก Python / Excel / curl แบบ automate")

KEY_FILE = ".api_keys.json"


def _load_keys() -> dict:
    if not os.path.exists(KEY_FILE):
        return {}
    with open(KEY_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_keys(keys: dict):
    with open(KEY_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, ensure_ascii=False, indent=2)


all_keys = _load_keys()
username = st.session_state["username"]
my_keys = all_keys.get(username, [])

# ─── Create new key ───
st.markdown("### ➕ สร้าง API Key ใหม่")
with st.form("new_key"):
    label = st.text_input("ชื่ออ้างอิง (เช่น 'Excel-office', 'Python-notebook')", "")
    submitted = st.form_submit_button("🔐 Generate Key", type="primary")

if submitted and label:
    new_key = generate_api_key()
    my_keys.append({
        "key": new_key,
        "label": label,
        "created": datetime.now().isoformat(timespec="seconds"),
        "last_used": None,
    })
    all_keys[username] = my_keys
    _save_keys(all_keys)
    log_event("create_api_key", meta={"label": label})
    st.success(f"✅ สร้างสำเร็จ! copy key นี้เก็บไว้ ปิดหน้าไปจะไม่เห็นอีก")
    st.code(new_key)
    st.warning("⚠️ เก็บ key เป็นความลับ ห้ามแชร์")

# ─── Existing keys ───
st.divider()
st.markdown("### 🗂 Keys ของคุณ")

if not my_keys:
    st.info("ยังไม่มี key — สร้างใหม่ด้านบน")
else:
    for i, k in enumerate(my_keys):
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(f"**{k['label']}**")
            c1.caption(f"`{k['key'][:12]}...{k['key'][-4:]}`  (ซ่อนไว้)")
            c2.caption(f"สร้าง: {k['created']}")
            c2.caption(f"ใช้ล่าสุด: {k.get('last_used') or '-'}")
            if c3.button("🗑 ลบ", key=f"del_{i}"):
                my_keys.pop(i)
                all_keys[username] = my_keys
                _save_keys(all_keys)
                log_event("delete_api_key", meta={"label": k["label"]})
                st.rerun()

# ─── Usage examples ───
st.divider()
st.markdown("### 📖 วิธีใช้ API Key")

tab1, tab2, tab3 = st.tabs(["🐍 Python", "📊 Excel Power Query", "💻 curl"])

with tab1:
    st.code("""
import requests
import pandas as pd
from io import StringIO

API_KEY = "wwn_..."  # paste key
URL = "https://YOUR-APP.streamlit.app/api/v1/dataset"

resp = requests.get(
    URL,
    headers={"X-API-Key": API_KEY},
    params={"dataset": "sales_daily", "year": 2025, "format": "csv"},
)
df = pd.read_csv(StringIO(resp.text))
print(df.head())
""", language="python")

with tab2:
    st.code("""
let
    URL     = "https://YOUR-APP.streamlit.app/api/v1/dataset?dataset=sales_daily&format=csv",
    API_KEY = "wwn_...",
    Source  = Csv.Document(
        Web.Contents(
            URL,
            [Headers = [#"X-API-Key" = API_KEY]]
        ),
        [Delimiter=",", Encoding=65001]
    ),
    Table = Table.PromoteHeaders(Source)
in
    Table
""", language="text")

with tab3:
    st.code("""
curl -H "X-API-Key: wwn_..." \\
     "https://YOUR-APP.streamlit.app/api/v1/dataset?dataset=sales_daily&format=csv" \\
     -o sales_daily.csv
""", language="bash")

st.info(
    "⚠️ **หมายเหตุ**: API endpoint จะพร้อมใช้ใน v2 — "
    "ตอนนี้ใช้ web portal (หน้า Datasets) ในการ download ก่อน"
)
