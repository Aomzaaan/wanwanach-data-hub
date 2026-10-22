# -*- coding: utf-8 -*-
"""วางแผนผลิต (Production Forecast) — อ่าน forecast จาก R2 (prefix: forecast/)
เห็นได้ทุก role · เป็นหน้าหนึ่งใน Wanwanach Data Hub
ข้อมูลมาจากโปรเจค MD_Forecast_System (push_forecast_to_r2.py) — แยกจาก pipeline ยอดขาย
รองรับหลายช่องทาง: forecast/<channel>/... (ModernTrade, Telesale) + ไฟล์ใช้ร่วม product_names / learning_history
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
CHANNELS = {"ModernTrade": "ModernTrade (MD)", "Telesale": "Telesale"}

@st.cache_resource(show_spinner=False)
def _r2():
    r2 = st.secrets["r2"]
    client = boto3.client("s3",
        endpoint_url=r2["endpoint_url"],
        aws_access_key_id=r2["access_key_id"],
        aws_secret_access_key=r2["secret_access_key"],
        region_name=r2.get("region", "auto"))
    return client, r2["bucket"]

@st.cache_data(ttl=900, show_spinner="⏳ โหลด forecast จาก R2...")
def load_csv(key):
    c, bucket = _r2()
    try:
        resp = c.get_object(Bucket=bucket, Key=PREFIX + key)
        return pd.read_csv(BytesIO(resp["Body"].read()), dtype={"product_code": str})
    except Exception:
        return None

# ─── เลือกช่องทาง + รีเฟรช ───
_top_l, _top_r = st.columns([5, 1])
CH = _top_l.radio("ช่องทาง", list(CHANNELS.keys()),
                  format_func=lambda k: CHANNELS[k], horizontal=True)
if _top_r.button("🔄 รีเฟรช", use_container_width=True):
    st.cache_data.clear(); st.rerun()
st.title(f"📦 วางแผนผลิต — {CHANNELS[CH]}")

CUST = "เชน" if CH == "ModernTrade" else "ลูกค้า"   # ป้ายคอลัมน์ customer_category

# per-channel
sp    = load_csv(f"{CH}/stock_policy.csv")
cyc   = load_csv(f"{CH}/cycle_total.csv")
rev   = load_csv(f"{CH}/review_list.csv")
drift = load_csv(f"{CH}/drift_alerts.csv")
fweek = load_csv(f"{CH}/forecast_weekly.csv")
# shared
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

if sp is None:
    st.warning(f"ยังไม่พบข้อมูล forecast ของช่องทาง {CHANNELS[CH]} บน R2 — รัน push_forecast_to_r2.py จากเครื่องที่ประมวลผลก่อน")
    st.stop()
st.caption("ข้อมูลจากโมเดลพยากรณ์ (group×product) · อ่านจาก R2 prefix forecast/<ช่องทาง>/ · แยกจากข้อมูลยอดขาย")
log_event("view_dashboard", f"production_{CH}")

# ─── แถบช่วงวันที่ (คำนวณจากคอลัมน์ week ของช่องทางที่เลือก) ───
_THMON = ["ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."]
def _d(ts):  return f"{ts.day} {_THMON[ts.month-1]}"
def _dy(ts): return f"{ts.day} {_THMON[ts.month-1]} {ts.year}"
def _date_window(fw):
    try:
        wks = sorted(pd.to_datetime(fw["week"]).dt.normalize().unique())
        if not wks: return None
        ps = pd.Timestamp(wks[0]); pe = pd.Timestamp(wks[-1]) + pd.Timedelta(days=6)
        bs = ps - pd.Timedelta(days=7); be = ps - pd.Timedelta(days=1)
        return bs, be, ps, pe, len(wks)
    except Exception:
        return None
_win = _date_window(fweek) if fweek is not None else None
if _win:
    _bs,_be,_ps,_pe,_nwk = _win
    _w1e = _ps + pd.Timedelta(days=6)
    st.success(
        f"📅 **ใช้ยอดจริงล่าสุด**: สัปดาห์ {_d(_bs)}–{_dy(_be)} (ข้อมูลครบถึง {_dy(_be)})  →  "
        f"**วางแผนผลิต {_nwk} สัปดาห์**: {_d(_ps)} – {_dy(_pe)}")
    st.caption(f"👉 ตัวเลข KPI และตารางด้านล่าง = แผนของ **สัปดาห์ถัดไป ({_d(_ps)}–{_dy(_w1e)})** · อีก {_nwk-1} สัปดาห์เป็นแนวโน้มล่วงหน้าไว้เตรียมวัตถุดิบ/กำลังคน")

# ─── KPI ───
tot_rec = sp["recommend_week"].sum(); tot_fc = sp["forecast_week"].sum(); tot_ss = sp["safety_stock"].sum()
def _last(col):
    if hist is None or not len(hist) or col not in hist.columns: return None
    h = hist
    if "channel" in hist.columns:
        hh = hist[hist["channel"] == f"{CH}_group_product"]
        if len(hh): h = hh
    v = h[col].iloc[-1]
    return None if pd.isna(v) else float(v)
wape_sku   = _last("WAPE_recent")        # รายสินค้า×ลูกค้า/สัปดาห์ (โหดสุด รวม timing noise)
wape_total = _last("WAPE_total_weekly")  # ยอดรวมทั้งช่องทาง/สัปดาห์ (error หักล้างกัน)
_pct = lambda v: f"{v*100:.1f}%" if v is not None else "-"
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("ควรผลิตรวม / สัปดาห์", f"{tot_rec:,.0f}")
c2.metric("Safety stock รวม", f"{tot_ss:,.0f}", f"+{100*tot_ss/tot_fc:.0f}%")
c3.metric("แม่นยอดรวม / สัปดาห์", _pct(wape_total),
          help="ความคลาดของยอดผลิตรวมทั้งหมดต่อสัปดาห์ (WAPE · ยิ่งต่ำยิ่งดี) — ใช้วางแผนวัตถุดิบ/กำลังการผลิตรวม")
c4.metric("แม่นรายสินค้า / สัปดาห์", _pct(wape_sku),
          help="ความคลาดเฉลี่ยรายสินค้า×ลูกค้าต่อสัปดาห์ (WAPE) สูงกว่าเพราะรวม timing noise ว่าสลับสั่งตัวไหนสัปดาห์ไหน — เราเผื่อไว้ใน safety stock แล้ว")
c5.metric("SKU ต้องตรวจ", f"{len(rev) if rev is not None else 0}")
c6.metric("แจ้งเตือน DRIFT", f"{len(drift) if drift is not None else 0}")
_acc = f"~{100-wape_total*100:.0f}%" if wape_total is not None else "—"
st.caption(f"ℹ️ WAPE = ความคลาด (ยิ่งต่ำยิ่งดี) · **ยอดรวมแม่นกว่ารายสินค้า** เพราะ error ตัวเกิน/ตัวขาดหักล้างกัน — ภาพรวมช่องทางนี้แม่นระดับ {_acc}")
if wape_sku is not None and wape_sku > 0.18:
    st.warning("⚠️ ช่องทางนี้รายสินค้าผันผวนสูง (สั่งเป็นล็อต/ไม่สม่ำเสมอ) — ยึด **ยอดรวม** เป็นหลักในการวางกำลังผลิต และเช็ก 'ต้องตรวจก่อน' ก่อนสั่งรายตัว")

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
    q = st.text_input(f"🔍 ค้นหา (รหัส / ชื่อสินค้า / {CUST})", "")
    if q:
        m = (d["product_code"].astype(str).str.contains(q, case=False, na=False)
             | d["ชื่อสินค้า"].astype(str).str.contains(q, case=False, na=False)
             | d["customer_category"].astype(str).str.contains(q, case=False, na=False))
        d = d[m]
    cols = ["customer_category","product_code","ชื่อสินค้า"] + (["สถานะ"] if "สถานะ" in d.columns else []) \
         + ["forecast_week","safety_stock","recommend_week","recommend_per_day"]
    st.dataframe(d[cols].rename(columns={
        "customer_category":CUST,"forecast_week":"Forecast/สัปดาห์","safety_stock":"เผื่อ",
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
            "status":"สถานะ","customer_category":CUST,"weeks_since_last":"ไม่สั่งมา(สัปดาห์)",
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
        st.subheader("แนวโน้มความแม่น (WAPE รายสินค้า)")
        if hist is not None and len(hist):
            h = hist.copy()
            if "channel" in h.columns: h = h[h["channel"] == f"{CH}_group_product"]
            if len(h):
                h["WAPE %"] = h["WAPE_recent"]*100
                st.line_chart(h.set_index("run_date")["WAPE %"])
            else:
                st.caption("ยังไม่มีประวัติของช่องทางนี้")
        else:
            st.caption("ยังไม่มีประวัติ")
