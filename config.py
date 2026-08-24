"""
Wanwanach Data Portal — Configuration
=====================================
แก้ USERS และ DATASETS ตรงนี้เพื่อ customize
"""

# ─── Users ────────────────────────────────────────────────
# password_hash สร้างจาก: bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
# หรือใช้ /pages/9_admin.py → Generate Hash
#
# Roles:
#   admin    — ดูทุก dataset + จัดการ users + ดู usage log
#   internal — ดูทุก dataset (raw + aggregated)
#   external — ดูเฉพาะ aggregated (2025+)
USERS = {
    "admin": {
        "password_hash": "$2b$12$FbLOtZ79wBZ0qPr2DAOwnuVgocX2XliYIohPA2K3KSik8e.bxPLgm",  # "REDACTED"
        "name": "ผู้ดูแลระบบ",
        "role": "admin",
        "email": "data@wanwanach.com",
    },
    "wanwan": {
        "password_hash": "$2b$12$z10b15DO6nNZ6k2CkS/o4e9uWN0WtraHXEFpnE9Ty/9rMUNJ0l4Wm",  # "REDACTED"
        "name": "พี่วี",
        "role": "internal",
        "email": "wanwan@wanwanach.com",
    },
    # เพิ่ม user ที่นี่
}


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
