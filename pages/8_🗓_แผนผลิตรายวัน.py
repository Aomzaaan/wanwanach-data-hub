# -*- coding: utf-8 -*-
"""แผนผลิตรายวัน (CJ + Big C) — PO มาก่อน, forecast เติมช่องว่าง
อ่าน forecast/daily_plan.csv จาก R2 (สร้างโดย po_forecast_plan.py)
ปฏิทินจริง: หยุดผลิตวันเสาร์ · ส่งก่อนถึง 1 วัน · พฤ. ผลิตรวมของถึง ส.+อา. · ศ. ผลิตของถึง จ. · อา. ผลิตของถึง อ.
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
for col in ["plan_date","prod_date","ship_date","delivery_date","run_at","po_asof","locked_at"]:
    if col in plan.columns: plan[col] = pd.to_datetime(plan[col], errors="coerce")
log_event("view_dashboard", "daily_plan")

_TH=["ม.ค.","ก.พ.","มี.ค.","เม.ย.","พ.ค.","มิ.ย.","ก.ค.","ส.ค.","ก.ย.","ต.ค.","พ.ย.","ธ.ค."]
_DOW=["จ.","อ.","พ.","พฤ.","ศ.","ส.","อา."]
def dthai(ts): return f"{_DOW[ts.weekday()]} {ts.day} {_TH[ts.month-1]}" if pd.notna(ts) else "-"
def dlist(sr): return " + ".join(dthai(pd.Timestamp(x)) for x in sorted(pd.Series(sr).dropna().unique()))
def cname(k): return "CJ" if k == "ซีเจ" else "Big C"
_LAB = {"PO":"PO ครบ","PO+FC":"PO บางส่วน + เติม forecast","FC":"forecast (ยังไม่มี PO)"}
_REN = {"cust":"ลูกค้า","name":"ชื่อสินค้า","po_qty":"PO มาแล้ว","fc_qty":"forecast","demand":"ใช้วางแผน","recommend":"ควรผลิต"}

_run = plan["run_at"].max() if "run_at" in plan.columns else pd.NaT
_asof = plan["po_asof"].max() if "po_asof" in plan.columns else _run
RUNDAY = _run.normalize() if pd.notna(_run) else plan["plan_date"].min()

st.caption("PO = ยอดสั่งจริงจาก AIOM · forecast = ยอดคาดการณ์เติมส่วนที่ PO ยังไม่มา · ยึดวันส่งถึงลูกค้าเป็นหลัก · หยุดผลิตวันเสาร์")
with st.expander("🗓️ ปฏิทินผลิต & เวลารันที่แนะนำ (จากประวัติเวลาที่ PO เข้า)"):
    st.dataframe(pd.DataFrame([
        ["อา.","จ.","อ.","พ.","หลัง 09:30 น.","Big C เข้าเช้าวันอาทิตย์"],
        ["จ.","อ.","พ.","พฤ.","หลัง 13:30 น.","PO ครบช่วงเที่ยง"],
        ["อ.","พ.","พฤ.","ศ.","หลัง 16:30 น.","CJ/Big C เข้า ~13:30–16:00"],
        ["พ.","พฤ.","ศ. / ส.","ส. + อา.","หลัง 13:30 น. + รันซ้ำ พฤ. หลัง 12:00","PO อา. ของ CJ ยังไม่มา (เข้า พฤ. ~11:30) → ใช้ forecast ก่อน แล้วปรับยอดวันผลิต"],
        ["พฤ.","ศ.","อา.","จ.","หลัง 16:30 น. + รันซ้ำ ศ. หลัง 13:00","Big C เข้า ~16:00 · CJ มาแค่ ~30% ที่เหลือเข้า ศ. ~12:30"],
        ["ศ.","อา.","จ.","อ.","หลัง 16:30 น.","CJ เข้า ~15:30–16:30 · Big C บางส่วนเข้าช้า"],
    ], columns=["วันวางแผน","วันผลิต","วันส่ง","ถึงลูกค้า","รันแนะนำ","หมายเหตุ"]), hide_index=True, use_container_width=True)
    st.caption("ส่วนที่ PO ยังไม่มา ระบบเติมด้วย forecast (+25%) · PO ครบ +5% · รันซ้ำในวันผลิตจะเห็นยอดที่ต้องผลิตเพิ่ม/ลดจากแผนที่วางไว้")

# ─── ตัวกรองลูกค้า ───
who = st.radio("ลูกค้า", ["ทั้งหมด","CJ (ซีเจ)","Big C"], horizontal=True)
d = plan.copy()
if who.startswith("CJ"): d = d[d["cust"]=="ซีเจ"]
elif who=="Big C": d = d[d["cust"]=="BIG C"]
fut = d[d["prod_date"] > RUNDAY]
tday = d[d["prod_date"] == RUNDAY]
if fut.empty:
    st.info("ไม่มีแผนผลิตข้างหน้า"); st.stop()
_pdays = sorted(fut["prod_date"].dropna().unique())
nxt = pd.Timestamp(_pdays[0])
nx = fut[fut["prod_date"]==nxt].sort_values(["delivery_date","recommend"], ascending=[True,False]).copy()

# ─── KPI ───
c1,c2,c3,c4 = st.columns(4)
c1.metric("วันผลิตถัดไป", dthai(nxt))
c2.metric("ควรผลิต", f"{nx['recommend'].sum():,.0f}")
_dm = nx["demand"].sum()
c3.metric("PO มาแล้ว (ของรอบนี้)", f"{100*nx['po_qty'].sum()/_dm:.0f}%" if _dm else "-", help="PO ที่เข้ามาแล้ว เทียบยอดที่ใช้วางแผน ที่เหลือเป็น forecast")
c4.metric("คำนวณเมื่อ", f"{dthai(_run)} {_run:%H:%M}" if pd.notna(_run) else "-",
          help=f"PO ในไฟล์ export ถึงเวลา {_asof:%H:%M} น." if pd.notna(_asof) else None)

# ─── ไฮไลต์: วันผลิตถัดไป ───
st.subheader(f"🔥 ผลิต {dthai(nxt)} → ส่ง {dlist(nx['ship_date'])} → ถึงลูกค้า {dlist(nx['delivery_date'])}")
if nx["delivery_date"].nunique() > 1:
    st.info(f"📌 วันนี้ผลิตรวม {nx['delivery_date'].nunique()} รอบส่ง เพราะหยุดผลิตวันเสาร์ — แยกยอดตามวันถึงลูกค้าด้านล่าง")
summ = nx.groupby(["delivery_date","ship_date","cust"]).agg(po=("po_qty","sum"), dm=("demand","sum"),
        rec=("recommend","sum"), pct=("po_arrived_pct","first")).reset_index()
for _, r in summ.iterrows():
    tag = f"{cname(r['cust'])} ถึง {dthai(r['delivery_date'])}"
    if pd.notna(r["pct"]) and r["pct"] >= 95:
        st.success(f"✅ {tag}: PO ถือว่าครบ (~{r['pct']:.0f}%) — ใช้ยอด PO จริง {r['po']:,.0f}")
    else:
        pct = f"~{r['pct']:.0f}%" if pd.notna(r["pct"]) else "ไม่ทราบ"
        st.warning(f"⏳ {tag}: ตามประวัติ ณ เวลานี้ PO มักมาแล้ว {pct} (มาแล้ว {r['po']:,.0f}) — เติม forecast เป็น {r['dm']:,.0f} · ควรผลิต {r['rec']:,.0f}")
summ_show = summ.assign(**{"ถึงลูกค้า": summ["delivery_date"].map(dthai), "ส่ง": summ["ship_date"].map(dthai),
    "ลูกค้า": summ["cust"].map(cname)})[["ถึงลูกค้า","ส่ง","ลูกค้า","po","dm","rec","pct"]].rename(
    columns={"po":"PO มาแล้ว","dm":"ใช้วางแผน","rec":"ควรผลิต","pct":"PO มาแล้ว ~% (ประวัติ)"})
st.dataframe(summ_show, hide_index=True, use_container_width=True)
nx["สถานะ"] = nx["source"].map(_LAB).fillna(nx["source"]); nx["ถึงลูกค้า"] = nx["delivery_date"].map(dthai)
st.dataframe(nx[["ถึงลูกค้า","cust","product_code","name","สถานะ","po_qty","fc_qty","demand","recommend"]].rename(columns=_REN),
             hide_index=True, use_container_width=True, height=360)
st.caption(f"รวมควรผลิต {nx['recommend'].sum():,.0f} ชิ้น · PO ครบ {(nx['source']=='PO').sum()} / PO บางส่วน {(nx['source']=='PO+FC').sum()} / forecast {(nx['source']=='FC').sum()} รายการ"
           " · ควรผลิต = PO +5% และส่วน forecast +25%")

# ─── วันนี้เป็นวันผลิต: อัปเดตตาม PO ล่าสุด เทียบแผนที่วางไว้ ───
if len(tday):
    st.subheader(f"🛠️ ผลิตวันนี้ {dthai(RUNDAY)} (ถึงลูกค้า {dlist(tday['delivery_date'])}) — อัปเดตตาม PO ล่าสุด")
    t = tday.copy()
    has_lock = "locked_rec" in t.columns and t["locked_rec"].notna().any()
    if has_lock:
        t["locked_rec"] = t["locked_rec"].fillna(0)
        t["ปรับ (+ผลิตเพิ่ม/−ลด)"] = t["recommend"] - t["locked_rec"]
        diff = t["ปรับ (+ผลิตเพิ่ม/−ลด)"].sum()
        k1,k2,k3 = st.columns(3)
        k1.metric("แผนที่วางไว้", f"{t['locked_rec'].sum():,.0f}")
        k2.metric("ควรผลิตตาม PO ล่าสุด", f"{t['recommend'].sum():,.0f}")
        k3.metric("ต่าง", f"{diff:+,.0f}")
        t = t.reindex(t["ปรับ (+ผลิตเพิ่ม/−ลด)"].abs().sort_values(ascending=False).index)
        cols = ["cust","product_code","name","po_qty","locked_rec","recommend","ปรับ (+ผลิตเพิ่ม/−ลด)"]
        st.dataframe(t[cols].rename(columns={**_REN,"locked_rec":"แผนที่วางไว้","recommend":"ควรผลิต (ล่าสุด)"}),
                     hide_index=True, use_container_width=True, height=300)
        st.caption("แผนที่วางไว้ = ยอดจากการรันครั้งล่าสุดในวันวางแผน · ใช้ปรับยอดระหว่างวัน เช่น พฤ. (PO อา. ของ CJ เข้า ~11:30) และ ศ. (PO จ. ของ CJ เข้า ~12:30)")
    else:
        st.caption(f"ควรผลิตตาม PO ล่าสุด {t['recommend'].sum():,.0f} ชิ้น (ยังไม่มีแผนที่ล็อกไว้จากวันวางแผนให้เทียบ — จะเริ่มมีตั้งแต่รอบหน้า)")
        st.dataframe(t[["cust","product_code","name","po_qty","demand","recommend"]].rename(columns=_REN),
                     hide_index=True, use_container_width=True, height=240)

# ─── วันผลิตถัดไปอีก (PO มาแล้วบางส่วน + เติม forecast ส่วนที่ขาด) ───
if len(_pdays) >= 2:
    n2 = pd.Timestamp(_pdays[1])
    x2 = fut[fut["prod_date"]==n2].sort_values(["delivery_date","recommend"], ascending=[True,False]).copy()
    st.subheader(f"📦 วันผลิตถัดไปอีก: ผลิต {dthai(n2)} → ส่ง {dlist(x2['ship_date'])} → ถึงลูกค้า {dlist(x2['delivery_date'])}")
    x2["สถานะ"] = x2["source"].map(_LAB).fillna(x2["source"]); x2["ถึงลูกค้า"] = x2["delivery_date"].map(dthai)
    st.dataframe(x2[["ถึงลูกค้า","cust","product_code","name","สถานะ","po_qty","fc_qty","demand","recommend"]].rename(columns=_REN),
                 hide_index=True, use_container_width=True, height=360)
    _g2 = x2.groupby("cust")["po_arrived_pct"].first().dropna()
    _a2 = (" · ตามประวัติ ณ เวลานี้ PO มักมาแล้ว " + " / ".join(f"{cname(k)} ~{v:.0f}%" for k, v in _g2.items())) if len(_g2) else ""
    st.caption(f"PO มาแล้ว {x2['po_qty'].sum():,.0f} · ใช้วางแผน {x2['demand'].sum():,.0f} · ควรผลิต {x2['recommend'].sum():,.0f} ชิ้น"
               f"{_a2} · ส่วนที่ขาดเติมด้วย forecast · รันครั้งถัดไปจะอัปเดตตาม PO ที่เข้ามาเพิ่ม")

# ─── forecast รอบถัดไป (ยังไม่มี PO — เตรียมล่วงหน้า) ───
_g = fut.groupby("prod_date")[["po_qty","demand"]].sum()
_after = pd.Timestamp(_pdays[1]) if len(_pdays) > 1 else nxt
_fcdays = [x for x in _g.index[_g["po_qty"] < 0.5*_g["demand"]] if x > _after]
if len(_fcdays):
    fnxt = min(_fcdays)
    fx = fut[fut["prod_date"]==fnxt].sort_values(["delivery_date","recommend"], ascending=[True,False]).copy()
    st.subheader(f"🔮 forecast รอบถัดไป: ผลิต {dthai(fnxt)} → ส่ง {dlist(fx['ship_date'])} → ถึงลูกค้า {dlist(fx['delivery_date'])}")
    fx["ถึงลูกค้า"] = fx["delivery_date"].map(dthai)
    st.dataframe(fx[["ถึงลูกค้า","cust","product_code","name","po_qty","demand","recommend"]].rename(columns=_REN),
                 hide_index=True, use_container_width=True, height=320)
    st.caption(f"ยอด forecast รวม {fx['recommend'].sum():,.0f} ชิ้น · ไว้เตรียมวัตถุดิบ/กำลังคนล่วงหน้า · จะเปลี่ยนเป็น PO จริงเมื่อ PO มาถึง")

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
        e2.metric("คลาดรายสินค้า (forecast)", f"{100*ev['fc_err'].abs().sum()/A:.1f}%", help="forecast ที่มีตอนวันวางแผน (3–4 วันก่อนส่ง ตามปฏิทินผลิต) เทียบ PO จริงรายสินค้า (WAPE)")
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
    st.caption("forecast ที่ใช้เทียบ = ตัวที่มีตอนวันวางแผนตามปฏิทินผลิต (ถึง จ./อ./อา. วางแผนล่วงหน้า 4 วัน, วันอื่น 3 วัน) · PO จริง = ยอดสั่งสุดท้ายหลังวันส่งผ่านไป")
    top = ev.groupby(["cust","product_code","name"], dropna=False).agg(fc=("fc","sum"), act=("actual","sum"), err=("fc_err","sum")).reset_index()
    top = top.reindex(top["err"].abs().sort_values(ascending=False).index).head(10)
    top["ต่าง %"] = (100*(top["fc"]/top["act"].replace(0,_nan)-1)).round(0)
    st.markdown("**สินค้าที่ forecast พลาดมากสุด (14 วันส่งล่าสุด)**")
    st.dataframe(top[["cust","product_code","name","fc","act","err","ต่าง %"]].rename(columns={"cust":"ลูกค้า",
        "name":"ชื่อสินค้า","fc":"forecast","act":"PO จริง","err":"ต่าง (ชิ้น)"}).round(0), hide_index=True, use_container_width=True)
