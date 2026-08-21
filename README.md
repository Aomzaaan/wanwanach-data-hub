# 🥐 Wanwanach Data Hub

Free & easy internal data platform สำหรับดึงข้อมูลยอดขาย ผ่าน web browser

## ✨ Features

- 🔐 Multi-user login + role-based access (admin / internal / external)
- 📊 Dataset catalog (4 datasets: daily / product / location / raw)
- 🎛 Filter UI (date range + categorical)
- ⬇ Download CSV / Excel / Parquet
- 📈 Charts (Bar / Line / Pie / Scatter) with Plotly
- 🔑 API Key management (v1 web-only; v2 API endpoint coming)
- 📊 Usage logs (admin)
- 🇹🇭 Thai UI

## 🚀 Deploy — 4 Steps (30 นาที)

### 1️⃣ Push to GitHub

```bash
cd data_portal
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR-USERNAME/wanwanach-data-hub.git
git push -u origin main
```

⚠️ **ตรวจสอบว่า `.streamlit/secrets.toml` ไม่ได้ push** (มี `.gitignore` แล้ว)

### 2️⃣ Deploy on Streamlit Cloud

1. เปิด https://share.streamlit.io
2. Sign in with GitHub
3. คลิก **"New app"**
4. เลือก:
   - Repository: `YOUR-USERNAME/wanwanach-data-hub`
   - Branch: `main`
   - Main file path: `app.py`
5. คลิก **"Deploy"**

### 3️⃣ Add Secrets

หลัง deploy → ที่แอพเปิดขึ้นมา → คลิก ⚙️ → **Settings** → **Secrets** → paste:

```toml
[r2]
access_key_id     = "..."
secret_access_key = "..."
endpoint_url      = "https://xxx.r2.cloudflarestorage.com"
bucket            = "wanwanach-data"
region            = "auto"
```

(copy จาก `daily_pipeline/common.py`)

### 4️⃣ Share URL

ได้ URL แบบ: `https://YOUR-APP-NAME.streamlit.app`

**Default users:**
- `admin` / `REDACTED` — Admin (แก้ password ทันที!)
- `wanwan` / `REDACTED` — พี่วี (แก้ทันที!)

## 🔧 การเพิ่ม User ใหม่

### Step 1: Generate password hash
Login เป็น admin → หน้า **⚙️ Admin** → tab **"Password Hash"** → กรอก password → copy hash

### Step 2: แก้ `config.py`

```python
USERS = {
    "somchai": {
        "password_hash": "$2b$12$....",  # paste hash
        "name": "คุณสมชาย",
        "role": "internal",   # admin / internal / external
        "email": "somchai@wanwanach.com",
    },
    # ...
}
```

### Step 3: Push GitHub → Streamlit Cloud จะ auto-deploy ใหม่

## 🎯 Roles & Permissions

| Role | เห็น aggregated | เห็น raw | Admin panel |
|---|:-:|:-:|:-:|
| `admin` | ✅ | ✅ | ✅ |
| `internal` | ✅ | ✅ | ❌ |
| `external` | ✅ | ❌ | ❌ |

## 🏗 Local Development

```bash
cd data_portal
pip install -r requirements.txt

# Copy secrets template + fill in R2 credentials
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# แก้ค่าใน .streamlit/secrets.toml

streamlit run app.py
```

เปิด http://localhost:8501

## 📁 Structure

```
data_portal/
├── app.py                  # Landing page + navigation
├── config.py               # USERS + DATASETS config
├── auth.py                 # Login / session
├── datasets.py             # R2 data loader
├── downloads.py            # CSV/Excel/Parquet export
├── usage_log.py            # Track events
├── requirements.txt
├── README.md               # This file
├── USER_GUIDE.md           # User manual (แจกให้ user)
├── .gitignore
├── .streamlit/
│   ├── config.toml         # Theme
│   └── secrets.toml.example  # R2 credentials template
└── pages/
    ├── 1_📊_datasets.py    # Browse + filter + download
    ├── 2_📈_charts.py      # Quick charts
    ├── 3_🔑_api_keys.py    # API key management
    ├── 4_📚_documentation.py  # In-app docs
    └── 9_⚙️_admin.py       # Admin panel
```

## 💰 Cost

- Streamlit Community Cloud: **฿0**
- Cloudflare R2 (existing): **฿0**
- Total: **฿0/month**

## 🔒 Security Notes

- Change default passwords ทันทีหลัง deploy
- Rotate R2 credentials ทุก 3-6 เดือน
- `.streamlit/secrets.toml` ห้าม push GitHub
- `.usage_log.jsonl` และ `.api_keys.json` เก็บใน container (จะหายเมื่อ restart) — ถ้าต้อง persist ให้ push ไป R2

## 📞 Support

- Email: data@wanwanach.com
- Docs: หน้า **📚 คู่มือ** ใน app

---

Built with ❤️ using Streamlit + Cloudflare R2
