# 📖 คู่มือผู้ใช้ — Wanwanach Data Hub

## 🚀 เริ่มต้นใน 3 ขั้นตอน

### 1. เข้าเว็บ
เปิด browser (Chrome / Edge / Firefox) ไปที่:  
🔗 **https://YOUR-APP.streamlit.app**

### 2. Login
- ใส่ **Username** และ **Password** ที่ Admin ให้
- คลิก **"เข้าสู่ระบบ"**

### 3. เลือก Dataset
- ในหน้าแรก → จะเห็น dataset ที่คุณเข้าถึงได้
- คลิก **"🔍 เปิด"** ที่ dataset ที่ต้องการ

## 📊 การใช้งานหน้า Datasets

### กรองข้อมูล (Sidebar ซ้าย)

**📅 กรองตามวันที่**
```
1. คลิกช่อง Date
2. เลือกวันเริ่ม → วันสิ้นสุด
3. ข้อมูลจะกรองอัตโนมัติ
```

**🔹 กรองตาม Category**
```
คลิก dropdown → เลือกที่ต้องการ (เลือกได้หลายรายการ)
```

**🔄 ล้างตัวกรอง**
คลิกปุ่ม "🔄 ล้างตัวกรอง" เพื่อเริ่มใหม่

### ดู Preview
- Preview แสดงข้อมูล 100 แถวแรก
- ดูจำนวนแถวทั้งหมด/หลังกรอง/ยอดรวมที่ Metrics ด้านบน

### ดาวน์โหลด
เลือก format:

| Format | ควรใช้เมื่อ |
|---|---|
| 📄 **CSV** | เปิดใน Excel, Google Sheets, Notepad |
| 📊 **Excel** | ต้องการเปิดใน Excel ทันที (มี formatting) |
| 📦 **Parquet** | ขนาดเล็ก (10-20% ของ CSV), ใช้ใน Python/Power BI |

**⚠️ ถ้าข้อมูลเกิน 500,000 แถว** — กรุณากรองให้เล็กลงก่อน

## 📈 การใช้งานหน้า Charts

### สร้างกราฟง่ายๆ

1. เลือก **Dataset**
2. เลือก **ประเภทกราฟ**: Bar / Line / Pie / Scatter
3. ตั้งค่า:
   - **แกน X**: เช่น `year_month`, `branch_name`
   - **แกน Y**: ตัวเลข เช่น `total_price`, `qty`
   - **แยกสีตาม** (optional): แยกกลุ่ม
   - **Aggregation**: `sum` (ผลรวม), `mean` (เฉลี่ย), `count` (นับ)
4. **Top N**: จำนวนอันดับที่แสดง

### ตัวอย่าง

**ยอดขายรายเดือน**
```
Dataset: sales_daily
Chart: Line
X: year_month
Y: total_price
Aggregation: sum
```

**Top 15 สาขา**
```
Dataset: sales_daily
Chart: Bar
X: branch_name
Y: total_price
Top N: 15
```

**สัดส่วน channel**
```
Dataset: sales_daily
Chart: Pie
X: channel
Y: total_price
```

## 🔑 API Keys (ผู้ใช้ Advanced)

**ใช้เมื่อ**: ต้องการดึงข้อมูลผ่าน Python, Excel Power Query, curl

### สร้าง Key
1. หน้า **🔑 API Keys** → กรอก label เช่น "Excel-office"
2. คลิก **Generate Key**
3. Copy key ที่ได้เก็บไว้ (จะเห็นครั้งเดียวเท่านั้น!)

### วิธีใช้
ดูตัวอย่างในหน้า API Keys → tab **🐍 Python** / **📊 Excel** / **💻 curl**

## ⚠️ ข้อควรระวัง

- 🔒 **ห้ามแชร์ Username/Password** ให้คนอื่น
- 🔑 **ห้ามแชร์ API Key** เก็บเป็นความลับ
- 📥 **Download แล้วห้ามส่งต่อภายนอก** โดยไม่ได้รับอนุญาต
- 🕐 ข้อมูล **cache 1 ชั่วโมง** — ถ้าไม่เห็น update ล่าสุด รอ 1 ชม.

## ❓ ปัญหาที่พบบ่อย

### เปิด CSV ใน Excel แล้ว **ตัวหนังสือไทยเพี้ยน**
- Excel ต้อง **Import** ผ่าน `Data → From Text/CSV` เลือก encoding **UTF-8**
- หรือใช้ Format **Excel (.xlsx)** แทน

### Download นาน / ช้า
- ผู้ใช้เยอะพร้อมกัน → คนละครั้ง
- กรองข้อมูลให้เล็กลงก่อน

### Login ไม่ได้
- ตรวจ Caps Lock
- ติดต่อ Admin ให้ reset password

### ไม่เห็น dataset ที่ต้องการ
- คุณอาจไม่มี permission → ติดต่อ Admin

## 📞 ติดต่อ

- 📧 **Admin**: data@wanwanach.com
- 🆘 **แจ้งปัญหา**: ส่ง screenshot + คำอธิบายไปที่ email

## 💡 Tips

1. **Bookmark URL** — ไม่ต้องพิมพ์ทุกครั้ง
2. **ใช้ Chrome/Edge** — ทำงานได้ดีที่สุด
3. **Filter ก่อน download** — เร็วกว่าและไฟล์เล็กกว่า
4. **Parquet + Python** — ประหยัด quota มากที่สุด
5. **API Key** — ถ้าต้อง download ประจำ ทำให้ automate ได้

---

Happy analyzing! 🥐📊
