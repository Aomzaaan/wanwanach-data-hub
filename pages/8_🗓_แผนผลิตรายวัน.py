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
c1.metric("ผลิตพรุ่งนี้", dthai(nxt))
c2.metric("ควรผลิต (พรุ่งนี้)", f"{d[d['prod_date']==nxt]['recommend'].sum():,.0f}")
c3.metric("PO จริง (ทั้งช่วง)", f"{100*po/T:.0f}%" if T else "-", help="สัดส่วนยอดที่เป็น PO จริงแล้ว ที่เหลือเป็น forecast")
c4.metric("รายการทั้งหมด", f"{len(d):,}")

# ─── ไฮไลต์: วันผลิตถัดไป ───
st.subheader(f"🔥 ผลิต {dthai(nxt)} → ส่ง {dthai(nxt+pd.Timedelta(days=1))} → ถึงลูกค้า {dthai(nxt+pd.Timedelta(days=2))}")
_run = pd.to_datetime(d["run_at"].iloc[0], errors="coerce") if "run_at" in d.columns and len(d) else pd.NaT
_runtxt = f" · คำนวณเมื่อ {dthai(_run)} {_run:%H:%M} น." if pd.notna(_run) else ""
st.caption(f"วางแผนวันที่ {dthai(d['plan_date'].min())}{_runtxt} · ยอดนี้คือของที่ต้องผลิตวันถัดไป")
nx=d[d["prod_date"]==nxt].sort_values("recommend",ascending=False)
_LAB = {"PO":"PO ครบ","PO+FC":"PO บางส่วน + เติม forecast","FC":"forecast (ยังไม่มี PO)"}
if "po_arrived_pct" in nx.columns and len(nx):
    _arr = nx.groupby("cust")["po_arrived_pct"].first()
    _pend = {k: v for k, v in _arr.items() if pd.notna(v) and v < 95}
    _txt = " · ".join(f"{'CJ' if k=='ซีเจ' else 'Big C'} ~{v:.0f}%" for k, v in _arr.items() if pd.notna(v))
    if _pend:
        _tip = ("· แนะนำรัน run_all_daily.bat อีกครั้งหลัง ~15:00 น. เพื่อได้ยอด PO ที่ครบกว่า"
                if pd.notna(_run) and _run.hour < 15 else
                "· ส่วนที่ยังไม่มา ระบบเผื่อด้วย forecast (+25%) ไว้แล้ว — ถ้า PO เข้าเพิ่มก่อนผลิต รันใหม่เพื่ออัปเดต")
        st.warning(f"⏳ PO ของรอบนี้ยังมาไม่ครบ (ประเมินจากประวัติเวลาที่ PO เข้า: {_txt}) — ส่วนที่ขาดเติมด้วย forecast {_tip}")
    elif _txt:
        st.success(f"✅ PO ของรอบนี้ถือว่าครบแล้ว ({_txt}) — ใช้ยอด PO จริงเป็นหลัก")
nx = nx.copy(); nx["สถานะ"] = nx["source"].map(_LAB).fillna(nx["source"])
_c1 = ["cust","product_code","name","สถานะ"] + [c for c in ["po_qty","fc_qty"] if c in nx.columns] + ["demand","recommend"]
nx_show=nx[_c1].rename(columns={"cust":"ลูกค้า","name":"ชื่อสินค้า","po_qty":"PO มาแล้ว",
    "fc_qty":"forecast","demand":"ใช้วางแผน","recommend":"ควรผลิต"})
st.dataframe(nx_show, hide_index=True, use_container_width=True, height=360)
st.caption(f"รวมควรผลิต {nx['recommend'].sum():,.0f} ชิ้น · PO ครบ {(nx['source']=='PO').sum()} / PO บางส่วน {(nx['source']=='PO+FC').sum()} / forecast {(nx['source']=='FC').sum()} รายการ"
           " · ควรผลิต = PO +5% และส่วน forecast +25%")

# ─── วันถัดไปอีก 1 วัน (PO มาแล้วบางส่วน + เติม forecast ส่วนที่ขาด) ───
_pdays = sorted(d["prod_date"].dropna().unique())
if len(_pdays) >= 2:
    n2 = pd.Timestamp(_pdays[1])
    st.subheader(f"📦 วันถัดไป: ผลิต {dthai(n2)} → ส่ง {dthai(n2+pd.Timedelta(days=1))} → ถึงลูกค้า {dthai(n2+pd.Timedelta(days=2))}")
    x2 = d[d["prod_date"]==n2].sort_values("recommend", ascending=False).copy()
    x2["สถานะ"] = x2["source"].map(_LAB).fillna(x2["source"])
    cols2 = ["cust","product_code","name","สถานะ"] + [c for c in ["po_qty","fc_qty"] if c in x2.columns] + ["demand","recommend"]
    st.dataframe(x2[cols2].rename(columns={"cust":"ลูกค้า","name":"ชื่อสินค้า","po_qty":"PO มาแล้ว",
        "fc_qty":"forecast","demand":"ใช้วางแผน","recommend":"ควรผลิต"}), hide_index=True, use_container_width=True, height=360)
    if "po_qty" in x2.columns:
        _a2 = ""
        if "po_arrived_pct" in x2.columns:
            _g2 = x2.groupby("cust")["po_arrived_pct"].first().dropna()
            if len(_g2):
                _a2 = " · ตามประวัติ ณ เวลานี้ PO มักมาแล้ว " + " / ".join(f"{'CJ' if k=='ซีเจ' else 'Big C'} ~{v:.0f}%" for k, v in _g2.items())
        st.caption(f"PO มาแล้ว {x2['po_qty'].sum():,.0f} · ใช้วางแผน {x2['demand'].sum():,.0f} · ควรผลิต {x2['recommend'].sum():,.0f} ชิ้น"
                   f"{_a2} · ส่วนที่ขาดเติมด้วย forecast · รันครั้งถัดไปจะอัปเดตตาม PO ที่เข้ามาเพิ่ม")

# ─── forecast รอบถัดไป (ยังไม่มี PO — เตรียมล่วงหน้า) ───
if "po_qty" in d.columns and len(_pdays):
    _g = d.groupby("prod_date")[["po_qty","demand"]].sum()
    _after = pd.Timestamp(_pdays[1]) if len(_pdays) > 1 else pd.Timestamp(_pdays[0])
    _fcdays = [x for x in _g.index[_g["po_qty"] < 0.5*_g["demand"]] if x > _after]
else:
    _byd = d.pivot_table(index="prod_date", columns="source", values="recommend", aggfunc="sum", fill_value=0)
    _po = _byd["PO"] if "PO" in _byd.columns else 0
    _fc = _byd["FC"] if "FC" in _byd.columns else 0
    _fcdays = list(_byd.index[_fc > _po])
if len(_fcdays):
    fnxt = min(_fcdays)
    st.subheader(f"🔮 forecast รอบถัดไป (ยังไม่มี PO): ผลิต {dthai(fnxt)} → ส่ง {dthai(fnxt+pd.Timedelta(days=1))} → ถึงลูกค้า {dthai(fnxt+pd.Timedelta(days=2))}")
    fx = d[d["prod_date"]==fnxt].sort_values("recommend", ascending=False)
    fx_show = fx[["cust","product_code","name","source","demand","recommend"]].rename(columns={
        "cust":"ลูกค้า","name":"ชื่อสินค้า","source":"แหล่ง","demand":"ยอดคาด","recommend":"ควรผลิต"})
    st.dataframe(fx_show, hide_index=True, use_container_width=True, height=320)
    st.caption(f"ยอด forecast รวม {fx['recommend'].sum():,.0f} ชิ้น · ไว้เตรียมวัตถุดิบ/กำลังคนล่วงหน้า · จะเปลี่ยนเป็น PO จริงเมื่อ PO มาถึง (รันเช้าถัดไป)")

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
    PO=("source",lambda x:(x=="PO").sum()),POFC=("source",lambda x:(x=="PO+FC").sum()),FC=("source",lambda x:(x=="FC").sum())).reset_index()
by["วันผลิต"]=by["prod_date"].map(dthai)
st.dataframe(by[["วันผลิต","cust","ควรผลิต","PO","POFC","FC"]].rename(columns={"cust":"ลูกค้า",
    "PO":"PO ครบ (รายการ)","POFC":"PO บางส่วน (รายการ)","FC":"forecast (รายการ)"}),
    hide_index=True, use_container_width=True)


# ─── forecast เทียบ PO จริง (ข้อมูลไว้ปรับโมเดล) ───
st.subheader("🎯 forecast เทียบ PO จริง (ไว้ปรับโมเดล)")
ev = load_csv("fc_vs_actual.csv")
if ev is None or not len(ev):
    st.info("ยังไม่มีข้อมูล — ระบบบันทึก forecast ทุกครั้งที่รัน run_all_daily.bat แล้วจะเทียบให้เมื่อวันส่งนั้นผ่านไป (PO ครบ)")
else:
    _nan = float("nan")
    ev["delivery_date"] = pd.to_datetime(ev["delivery_date"], errors="coerce")
    if who.startswith("CJ"): ev = ev[ev["cust"]=="ซีเจ"]
    elif who == "Big C": ev = ev[ev["cust"]=="BIG C"]
    ev = ev[ev["delivery_date"] >= ev["delivery_date"].max() - pd.Timedelta(days=13)]
    A = ev["actual"].sum()
    if A > 0:
        e1, e2, e3 = st.columns(3)
        e1.metric("forecast รวม vs PO จริง", f"{100*(ev['fc'].sum()/A-1):+.1f}%", help="บวก = forecast สูงกว่าจริง · ลบ = ต่ำกว่าจริง (รวมทุกสินค้า)")
        e2.metric("คลาดรายสินค้า (forecast)", f"{100*ev['fc_err'].abs().sum()/A:.1f}%", help="forecast ที่ทำไว้ ≥4 วันก่อนส่ง เทียบ PO จริงรายสินค้า (WAPE)")
        e3.metric("คลาดรายสินค้า (แผน PO+forecast)", f"{100*ev['plan_err'].abs().sum()/A:.1f}%", help="ยอดที่ส่วน 'วันถัดไป' ใช้วางแผน ณ ตอนนั้น เทียบ PO จริง")
    g = ev.groupby("delivery_date").agg(fc=("fc","sum"), plan=("plan_qty","sum"), act=("actual","sum"),
            fe=("fc_err", lambda x: x.abs().sum()), pe=("plan_err", lambda x: x.abs().sum())).reset_index()
    g = g.sort_values("delivery_date", ascending=False)
    g["วันส่ง"] = g["delivery_date"].map(dthai)
    g["ต่างรวม %"] = (100*(g["fc"]/g["act"].replace(0,_nan)-1)).round(1)
    g["คลาดรายสินค้า % (forecast)"] = (100*g["fe"]/g["act"].replace(0,_nan)).round(1)
    g["คลาดรายสินค้า % (แผน)"] = (100*g["pe"]/g["act"].replace(0,_nan)).round(1)
    st.dataframe(g[["วันส่ง","fc","plan","act","ต่างรวม %","คลาดรายสินค้า % (forecast)","คลาดรายสินค้า % (แผน)"]]
        .rename(columns={"fc":"forecast","plan":"แผน (PO+FC)","act":"PO จริง"}).round(1), hide_index=True, use_container_width=True)
    st.caption("forecast ที่ใช้เทียบ = ตัวที่ระบบทำไว้อย่างน้อย 4 วันก่อนส่ง (ตรงกับส่วน 📦 วันถัดไป) · PO จริง = ยอดสั่งสุดท้ายหลังวันส่งผ่านไป")
    top = ev.groupby(["cust","product_code","name"], dropna=False).agg(fc=("fc","sum"), act=("actual","sum"), err=("fc_err","sum")).reset_index()
    top = top.reindex(top["err"].abs().sort_values(ascending=False).index).head(10)
    top["ต่าง %"] = (100*(top["fc"]/top["act"].replace(0,_nan)-1)).round(0)
    st.markdown("**สินค้าที่ forecast พลาดมากสุด (14 วันส่งล่าสุด)**")
    st.dataframe(top[["cust","product_code","name","fc","act","err","ต่าง %"]].rename(columns={"cust":"ลูกค้า",
        "name":"ชื่อสินค้า","fc":"forecast","act":"PO จริง","err":"ต่าง (ชิ้น)"}).round(0), hide_index=True, use_container_width=True)
