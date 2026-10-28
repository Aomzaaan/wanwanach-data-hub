# -*- coding: utf-8 -*-
"""แผนผลิตรายวัน (CJ + Big C) — PO มาก่อน, forecast เติมช่องว่าง
อ่าน forecast/daily_plan.csv จาก R2 (สร้างโดย po_forecast_plan.py)
Timeline: วางแผน D-3 · ผลิต D-2 · ส่ง D-1 · ถึงลูกค้า D
"""
from io import BytesIO
import pandas as pd
import streamlit as st
import boto3
from auth import require_login
from usage_log import log_event

st.set_page_config(page_title="แผนผลิตรายวัน — Wanwanach", page_icon="🗓️", layout="wide")
require_login()
PREFIX = "forecast/"

@st.cache_resource(show_spinner=False)
def _r2():
    r2 = st.secrets["r2"]
    return boto3.client("s3", endpoint_url=r2["endpoint_url"],
        aws_access_key_id=r2["access_key_id"], aws_secret_access_key=r2["secret_access_key"],
        region_name=r2.get("region", "auto")), r2["bucket"]

@st.cache_data(ttl=900, show_spinner="⏳ โหลดแผนจาก R2...")
def load_csv(name):
    c, b = _r2()
    try:
        return pd.read_csv(BytesIO(c.get_object(Bucket=b, Key=PREFIX+name)["Body"].read()), dtype={"product_code": str})
    except Exception:
        return None

_l, _r = st.columns([5,1])
_l.title("🗓️ แผนผลิตรายวัน — CJ + Big C")
if _r.button("🔄 รีเฟรช", use_container_width=True):
    st.cache_data.clear(); st.rerun()

plan = load_csv("daily_plan.csv")
if plan is None or not len(plan):
    st.warning("ยังไม่พบแผนผลิตบน R2 — รัน run_all_daily.bat (export PO → ทำแผน → push) ก่อน")
    st.stop()
for col in ["plan_date","prod_date","ship_date","delivery_date"]:
    plan[col] = pd.to_datetime(plan[col], errors="coerce")
log_event("view_dashboard", "daily_plan")

_TH=["ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."]
_DOW=["จ.","อ.","พ.","พฤ.","ศ.","ส.","อา."]
def dthai(ts): return f"{_DOW[ts.weekday()]} {ts.day} {_TH[ts.month-1]}" if pd.notna(ts) else "-"

st.caption("PO = ยอดสั่งจริงจาก AIOM (แน่นอน) · FC = forecast เผื่อไว้ (ยังไม่มี PO) · ยึดวันส่งถึงลูกค้าเป็นหลัก")

# ─── ตัวกรองลูกค้า ───
who = st.radio("ลูกค้า", ["ทั้งหมด","CJ (ซีเจ)","Big C"], horizontal=True)
d = plan.copy()
if who.startswith("CJ"): d = d[d["cust"]=="ซีเจ"]
elif who=="Big C": d = d[d["cust"]=="BIG C"]

# ─── KPI ───
T=d["demand"].sum(); po=d[d["source"]=="PO"]["demand"].sum(); fc=d[d["source"]=="FC"]["demand"].sum()
nxt=d["prod_date"].min()
c1,c2,c3,c4=st.columns(4)
c1.metric("วันผลิตถัดไป", dthai(nxt))
c2.metric("ควรผลิตวันถัดไป", f"{d[d['prod_date']==nxt]['recommend'].sum():,.0f}")
c3.metric("PO จริง (ทั้งช่วง)", f"{100*po/T:.0f}%" if T else "-", help="สัดส่วนยอดที่เป็น PO จริงแล้ว ที่เหลือเป็น forecast")
c4.metric("รายการทั้งหมด", f"{len(d):,}")

# ─── ไฮไลต์: วันผลิตถัดไป ───
st.subheader(f"🔥 วันผลิตถัดไป: {dthai(nxt)}  (ส่งถึงลูกค้า {dthai(nxt+pd.Timedelta(days=2))})")
nx=d[d["prod_date"]==nxt].sort_values("recommend",ascending=False)
nx_show=nx[["cust","product_code","name","source","demand","recommend"]].rename(columns={
    "cust":"ลูกค้า","name":"ชื่อสินค้า","source":"แหล่ง","demand":"ยอดคาด","recommend":"ควรผลิต"})
st.dataframe(nx_show, hide_index=True, use_container_width=True, height=360)
st.caption(f"รวมควรผลิตวันนี้ {nx['recommend'].sum():,.0f} ชิ้น · PO {len(nx[nx['source']=='PO'])} / forecast {len(nx[nx['source']=='FC'])} รายการ")

# ─── ตารางเต็ม: ทุกวันผลิตข้างหน้า ───
st.subheader("📋 แผนล่วงหน้าทั้งหมด (ตาม 'วันผลิต')")
full=d.copy()
for col,lab in [("plan_date","วันวางแผน"),("prod_date","วันผลิต"),("ship_date","วันส่ง"),("delivery_date","ถึงลูกค้า")]:
    full[lab]=full[col].map(dthai)
cols=["วันวางแผน","วันผลิต","วันส่ง","ถึงลูกค้า","cust","product_code","name","source","demand","recommend"]
full=full[cols].rename(columns={"cust":"ลูกค้า","name":"ชื่อสินค้า","source":"แหล่ง","demand":"ยอดคาด","recommend":"ควรผลิต"})
st.dataframe(full, hide_index=True, use_container_width=True, height=460)

# ─── สรุปรายวันผลิต ───
st.subheader("📊 ยอดรวมแต่ละวันผลิต")
by=d.groupby([d["prod_date"],"cust"]).agg(ควรผลิต=("recommend","sum"),
    PO=("source",lambda x:(x=="PO").sum()),FC=("source",lambda x:(x=="FC").sum())).reset_index()
by["วันผลิต"]=by["prod_date"].map(dthai)
st.dataframe(by[["วันผลิต","cust","ควรผลิต","PO","FC"]].rename(columns={"cust":"ลูกค้า"}),
    hide_index=True, use_container_width=True)
