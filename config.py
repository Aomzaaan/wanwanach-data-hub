"""
Wanwanach Data Portal — Configuration
=====================================
แก้ USERS และ DATASETS ตรงนี้เพื่อ customize
"""

# ─── Users ────────────────────────────────────────────────
# ⚠️ SEED users ไม่ hardcode ในโค้ดอีกต่อไป — เก็บใน Streamlit Secrets
# [seed_admin]
# username      = "admin"
# password_hash = "$2b$12$..."     # bcrypt hash (สร้างจาก admin panel)
# name          = "ผู้ดูแลระบบ"
# email         = "data@wanwanach.com"
#
# ถ้า secrets ไม่มี → ระบบสร้าง admin/random_password ครั้งแรก แล้วบังคับเปลี่ยน
#
# Roles:
#   admin    — ดูทุก dataset + จัดการ users + ดู usage log
#   internal — ดูทุก dataset (raw + aggregated)
#   external — ดูเฉพาะ aggregated (2025+)
def _load_seed_users():
    """Load seed users from Streamlit secrets (fallback: empty)."""
    try:
        import streamlit as st
        seed = st.secrets.get("seed_admin", None)
        if seed:
            return {
                seed["username"]: {
                    "password_hash": seed["password_hash"],
                    "name": seed.get("name", "Admin"),
                    "role": "admin",
                    "email": seed.get("email", ""),
                }
            }
    except Exception:
        pass
    return {}


USERS = _load_seed_users()


# ─── Datasets ─────────────────────────────────────────────
# แต่ละ dataset:
#   name        — ชื่อแสดงใน UI
#   description — คำอธิบาย
#   source_type — 'r2_csv' | 'r2_parquet' | 'local_parquet'
#   source_key  — ชื่อไฟล์ใน R2 หรือ local path
#   filters     — list ของ column ที่ให้ filter ได้
#   date_col    — คอลัมน์วันที่ (สำหรับ date range filter)
#   allowed_roles — role ไหนดูได้
#   update_freq — เพื่อ display

DATASETS = {
    "sales_daily": {
        "name": "📊 ยอดขายรายวัน (Daily Sales)",
        "description": "ยอดขายรวมรายวัน × source × branch (2022–ปัจจุบัน)",
        "source_type": "r2_csv",
        "source_key": "aggregated/sales_daily.csv",
        "filters": ["source", "branch_code", "channel", "route"],
        "date_col": "date",
        "allowed_roles": ["admin", "internal", "external"],
        "update_freq": "รายวัน",
    },
    "product_monthly": {
        "name": "🥐 สินค้ารายเดือน (Products)",
        "description": "ยอดขายสินค้ารายเดือน",
        "source_type": "r2_csv",
        "source_key": "aggregated/product_monthly.csv",
        "filters": ["product_code"],
        "date_col": "year_month",
        "allowed_roles": ["admin", "internal", "external"],
        "update_freq": "รายเดือน",
    },
    "location_monthly": {
        "name": "🗺️ พื้นที่รายเดือน (Locations)",
        "description": "ยอดขายรายเดือน × จังหวัด/พื้นที่",
        "source_type": "r2_csv",
        "source_key": "aggregated/location_monthly.csv",
        "filters": ["province", "area", "route"],
        "date_col": "year_month",
        "allowed_roles": ["admin", "internal", "external"],
        "update_freq": "รายเดือน",
    },
    # Raw data — 1.1 GB — เก็บไว้ใน R2 แต่ไม่ให้ portal โหลด (จะช้า/hang)
    # ถ้าต้องการ ให้ใช้ signed URL / API key แทน
    # "sales_fact_raw": {
    #     "name": "📦 ข้อมูลดิบทั้งหมด (Raw)",
    #     "description": "Transaction line-item — 1.1 GB (ห้ามโหลดใน browser)",
    #     "source_type": "r2_csv",
    #     "source_key": "raw/sales_fact.csv",
    #     "filters": ["source", "branch_code", "product_code", "channel"],
    #     "date_col": "date",
    #     "allowed_roles": ["admin"],  # admin only
    #     "update_freq": "รายวัน",
    # },
}


# ─── R2 Configuration ─────────────────────────────────────
# ใน Streamlit Cloud → App Settings → Secrets → paste ค่า
# ค่าจะ inject เป็น st.secrets["r2"]
#
# [r2]
# access_key_id     = "..."
# secret_access_key = "..."
# endpoint_url      = "https://xxx.r2.cloudflarestorage.com"
# bucket            = "wanwanach-data"
# region            = "auto"


# ─── UI Configuration ─────────────────────────────────────
APP_TITLE = "🥐 Wanwanach Data Hub"
APP_SUBTITLE = "ฐานข้อมูลกลาง — ยอดขาย & Analytics"
PRIMARY_COLOR = "#1976D2"
LOGO_URL = None  # ใส่ URL รูป logo ถ้ามี

# ─── Rate limit / safety ──────────────────────────────────
MAX_DOWNLOAD_ROWS = 500_000  # download ครั้งละไม่เกิน N rows
MAX_PREVIEW_ROWS = 100
CACHE_TTL_SECONDS = 3600  # cache data 1 ชั่วโมง
