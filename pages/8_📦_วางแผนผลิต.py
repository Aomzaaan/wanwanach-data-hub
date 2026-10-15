# -*- coding: utf-8 -*-
"""วางแผนผลิต (Production Forecast) — อ่าน forecast จาก R2 (prefix: forecast/)
เห็นได้ทุก role · เป็นหน้าหนึ่งใน Wanwanach Data Hub
ข้อมูลมาจากโปรเจค MD_Forecast_System (push_forecast_to_r2.py) — แยกจาก pipeline ยอดขาย
"""
from io import BytesIO
import pandas as pd
import streamlit as st
import boto3

from auth import require_login
from usage_log import log_event

st.set_page_config(page_title="วางแผนผลิต — Wanwanach", page_icon="📦", layout="wide")
require_login()                      # ทุก role เข้าได้ (แค่ต้อง login)

PREFIX = "forecast/"

@st.cache_resource(show_spinner=False)
def _r2():
    r2 = st.secrets["r2"]
    client = boto3.client("s3",
        endpoint_url=r2["endpoint_url"],
        aws_access_key_id=r2["access_key_id"],
        aws_secret_access_key=r2["secret_access_key"],
        region_name=r2.get("region", "auto"))
    return client, r2["bucket"]

@st.cache_data(ttl=1800, show_spinner="⏳ โหลด forecast จาก R2...")
def load_csv(name):
    c, bucket = _r2()
    try:
        resp = c.get_object(Bucket=bucket, Key=PREFIX + name)
        return pd.read_csv(BytesIO(resp["Body"].read()), dtype={"product_code": str})
    except Exception:
        return None

sp    = load_csv("stock_policy.csv")
cyc   = load_csv("cycle_total.csv")
rev   = load_csv("review_list.csv")
drift = load_csv("drift_alerts.csv")
hist  = load_csv("learning_history.csv")
names = load_csv("product_names.csv")
NAME  = dict(zip(names["product_code"].astype(str), names["product_name"])) if names is not None else {}

def add_name(df):
    if df is None: return df
    d = df.copy()
    if "product_code" in d.columns:
        d.insert(d.columns.get_loc("product_code") + 1, "ชื่อสินค้า",
                 d["product_code"].astype(str).map(lambda c: NAME.get(c, "")))
    return d

st.title("📦 วางแผนผลิต — ModernTrade")
if sp is None:
    st.warning("ยังไม่พบข้อมูล forecast บน R2 — รัน push_forecast_to_r2.py จากเครื่องที่ประมวลผลก่อน")
    st.stop()
st.caption("ข้อมูลจากโมเดลพยากรณ์ (seasonal-naive, group×product) · อ่านจาก R2 prefix forecast/ · แยกจากข้อมูลยอดขาย")
log_event("view_dashboard", "production_forecast")

# ─── KPI ───
tot_rec = sp["recommend_week"].sum(); tot_fc = sp["forecast_week"].sum(); tot_ss = sp["safety_stock"].sum()
wape = hist["WAPE_recent"].iloc[-1] if (hist is not None and len(hist)) else None
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("ควรผลิตรวม / สัปดาห์", f"{tot_rec:,.0f}")
c2.metric("Safety stock รวม", f"{tot_ss:,.0f}", f"+{100*tot_ss/tot_fc:.0f}%")
c3.metric("ความแม่น (WAPE)", f"{wape*100:.1f}%" if wape is not None else "-")
c4.metric("SKU ต้องตรวจ", f"{len(rev) if rev is not None else 0}")
c5.metric("แจ้งเตือน DRIFT", f"{len(drift) if drift is not None else 0}")

if drift is not None and len(drift):
    st.error("⚠️ SKU ที่เปลี่ยนพฤติกรรม — ตรวจก่อนสั่งผลิต")
    cols = [c for c in ["customer_category","product_code","ชื่อสินค้า","drift_ratio","forecast_next"] if c in add_name(drift).columns]
    st.dataframe(add_name(drift)[cols], hide_index=True, use_container_width=True)

st.info("👉 ใช้คอลัมน์ **ควรผลิต/วัน** ไปสั่งผลิต (= forecast + safety stock แล้ว) · เช็ค 'ต้องตรวจ' ก่อนเชื่อตัวเลข")

tab1, tab2, tab3 = st.tabs(["🏭 ควรผลิตเท่าไหร่", "🔎 ต้องตรวจก่อน", "📊 สถานะ & ความแม่น"])

with tab1:
    d = add_name(sp).sort_values("recommend_per_day", ascending=False)
    if cyc is not None and "status" in cyc.columns:
        stt = dict(zip(cyc["customer_category"].astype(str)+"|"+cyc["product_code"].astype(str), cyc["status"]))
        d["สถานะ"] = (d["customer_category"].astype(str)+"|"+d["product_code"].astype(str)).map(stt).fillna("")
    q = st.text_input("🔍 ค้นหา (รหัส / ชื่อสินค้า / เชน)", "")
    if q:
        m = (d["product_code"].astype(str).str.contains(q, case=False, na=False)
             | d["ชื่อสินค้า"].astype(str).str.contains(q, case=False, na=False)
             | d["customer_category"].astype(str).str.contains(q, case=False, na=False))
        d = d[m]
    cols = ["customer_category","product_code","ชื่อสินค้า"] + (["สถานะ"] if "สถานะ" in d.columns else []) \
         + ["forecast_week","safety_stock","recommend_week","recommend_per_day"]
    st.dataframe(d[cols].rename(columns={
        "customer_category":"เชน","forecast_week":"Forecast/สัปดาห์","safety_stock":"เผื่อ",
        "recommend_week":"ควรผลิต/สัปดาห์","recommend_per_day":"ควรผลิต/วัน"}),
        hide_index=True, use_container_width=True, height=560)
    st.caption(f"ทั้งหมด {len(d):,} รายการ")

with tab2:
    if rev is not None and len(rev):
        order = {"NEW":0,"VOLATILE":1,"DISCONTINUED":2}
        rv = add_name(rev).copy(); rv["_o"] = rv["status"].map(order).fillna(9); rv = rv.sort_values("_o")
        f = st.multiselect("กรองสถานะ", ["NEW","VOLATILE","DISCONTINUED"], default=["NEW","VOLATILE"])
        if f: rv = rv[rv["status"].isin(f)]
        cols = [c for c in ["status","customer_category","product_code","ชื่อสินค้า","weeks_since_last","nonzero_ratio","cv"] if c in rv.columns]
        st.dataframe(rv[cols].rename(columns={
            "status":"สถานะ","customer_category":"เชน","weeks_since_last":"ไม่สั่งมา(สัปดาห์)",
            "nonzero_ratio":"ความถี่สั่ง","cv":"ผันผวน(CV)"}),
            hide_index=True, use_container_width=True, height=560)
    else:
        st.success("ไม่มีรายการต้องตรวจ")

with tab3:
    colA, colB = st.columns(2)
    with colA:
        st.subheader("ภาพรวมสถานะสินค้า")
        if cyc is not None and "status" in cyc.columns:
            st.bar_chart(cyc["status"].value_counts())
    with colB:
        st.subheader("แนวโน้มความแม่น (WAPE)")
        if hist is not None and len(hist):
            h = hist.copy(); h["WAPE %"] = h["WAPE_recent"]*100
            st.line_chart(h.set_index("run_date")["WAPE %"])
        else:
            st.caption("ยังไม่มีประวัติ")
