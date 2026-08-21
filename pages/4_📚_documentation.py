"""Documentation — คู่มือการใช้."""
import streamlit as st
from config import DATASETS
from auth import require_login, can_access


st.set_page_config(page_title="Documentation — Wanwanach", page_icon="📚", layout="wide")
require_login()

st.title("📚 คู่มือการใช้งาน")

tab1, tab2, tab3, tab4 = st.tabs(["🏠 เริ่มต้น", "📊 Datasets", "🔑 API", "❓ FAQ"])

with tab1:
    st.markdown("""
## เริ่มต้นใช้งาน

### 1. เลือกข้อมูลที่ต้องการ
ไปที่หน้า **📊 ข้อมูลทั้งหมด** → เลือก dataset จาก dropdown

### 2. กรองข้อมูล
ใช้ตัวกรองใน sidebar ซ้าย:
- 📅 **วันที่**: เลือกช่วงวันที่ที่ต้องการ
- 🔹 **Category**: เลือก branch, product, source ฯลฯ
- 🔄 คลิก "ล้างตัวกรอง" เพื่อเริ่มใหม่

### 3. ดาวน์โหลด
เลือก format ที่ต้องการ:
- **📄 CSV** — เปิดได้ทุกโปรแกรม
- **📊 Excel** — เปิดใน Excel ทันที
- **📦 Parquet** — สำหรับ Python/BI tools (ขนาดเล็กสุด)

### 4. ดูกราฟ
ไปหน้า **📈 กราฟ** → เลือก dataset → ตั้งค่ากราฟ → view
""")

with tab2:
    st.markdown("## Datasets ที่มี")
    for did, conf in DATASETS.items():
        if not can_access(conf):
            continue
        with st.expander(f"{conf['name']}"):
            st.markdown(f"**คำอธิบาย**: {conf['description']}")
            st.markdown(f"**ความถี่**: {conf['update_freq']}")
            st.markdown(f"**Filters**: {', '.join(conf.get('filters', []))}")
            st.markdown(f"**Roles**: {', '.join(conf['allowed_roles'])}")

with tab3:
    st.markdown("""
## API Reference

### Base URL
```
https://YOUR-APP.streamlit.app/api/v1
```

### Authentication
ใส่ API Key ใน header:
```
X-API-Key: wwn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Endpoints

#### GET `/api/v1/datasets`
List datasets ทั้งหมดที่คุณเข้าถึงได้

#### GET `/api/v1/dataset`
Query dataset

**Query params**:
| Param | Type | Description |
|---|---|---|
| `dataset` | string | dataset id (เช่น `sales_daily`) |
| `format` | string | `csv` / `json` / `parquet` |
| `year` | int | (optional) filter ปี |
| `month` | int | (optional) filter เดือน |
| `limit` | int | (optional) max rows (default 100k) |

**Example**:
```
GET /api/v1/dataset?dataset=sales_daily&year=2025&format=csv
```

⚠️ API endpoint นี้จะพร้อมใน v2 — ตอนนี้ใช้ web portal ก่อน
""")

with tab4:
    st.markdown("""
## FAQ

### ❓ ข้อมูลอัพเดทเมื่อไหร่?
- **sales_daily** — ทุกวัน (ประมาณ 9:00)
- **product_monthly / location_monthly** — ทุกเดือน (วันที่ 1)
- **sales_fact_raw** — ทุกวัน

### ❓ ทำไมยอดในไฟล์ต่างกันแต่ละครั้ง refresh?
Retroactive updates ตามปกติ — dashboard sync กับข้อมูลล่าสุดจาก pipeline

### ❓ ข้อมูลย้อนหลังได้กี่ปี?
2565 (2022) — ปัจจุบัน

### ❓ ต้องการ dataset เพิ่ม?
ติดต่อ Admin: **data@wanwanach.com**

### ❓ Download แล้ว file ใหญ่มาก เปิดใน Excel ไม่ได้?
- **>1M rows** → Excel เปิดไม่ครบ ใช้ Data Model แทน
- **หรือ**: ใช้ Parquet format + Python

### ❓ ลืม password?
ติดต่อ Admin

### ❓ พบ bug?
ส่งรายละเอียด + screenshot ไปที่ data@wanwanach.com
""")
