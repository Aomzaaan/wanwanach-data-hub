"""
เครม Amazon — Claim Rate Monitor
เช็คว่าแต่ละร้านในแต่ละวันเครม มียอดเครมเกิน X% ของยอดขายไหม (default 10%)
"""
import streamlit as st
import pandas as pd

from config import DATASETS
from auth import require_login, can_access
from datasets import load_dataset
from time_utils import th_str

st.set_page_config(page_title="เครม Amazon — Wanwanach", page_icon="♻️", layout="wide")
require_login()

st.title("♻️ เครม Amazon — Claim Rate Monitor")
st.caption(f"อัพเดทล่าสุด: {th_str()}")

DS = DATASETS.get("amazon_claim_summary", {})
if not can_access(DS):
    st.warning("ยังไม่มีสิทธิ์เข้าถึงข้อมูลนี้")
    st.stop()

try:
    df = load_dataset("amazon_claim_summary")
except Exception as e:
    st.error(f"โหลดข้อมูลไม่สำเร็จ: {e}")
    st.stop()

if df is None or df.empty:
    st.info("ยังไม่มีข้อมูลเครม (รัน amazon_claims_reconcile แล้ว push R2 ก่อน)")
    st.stop()

# ─── clean types ───
for dc in ["claim_date", "delivery_date"]:
    if dc in df.columns:
        df[dc] = pd.to_datetime(df[dc], errors="coerce")
for c in ["sale_amount", "claim_amount", "claim_pct", "days_after"]:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
df = df.dropna(subset=["claim_date"])

# ─── filters ───
c1, c2, c3 = st.columns(3)
with c1:
    dmin, dmax = df["claim_date"].min().date(), df["claim_date"].max().date()
    dr = st.date_input("ช่วงวันเครม", (dmin, dmax))
with c2:
    branches = ["(ทุกสาขา)"] + sorted(df["branch_code"].dropna().astype(str).unique().tolist())
    br = st.selectbox("รหัสสาขา", branches)
with c3:
    thr = st.number_input("เตือนเมื่อ claim % เกิน", min_value=0.0, value=10.0, step=1.0)

f = df.copy()
if isinstance(dr, tuple) and len(dr) == 2:
    f = f[(f["claim_date"] >= pd.Timestamp(dr[0])) & (f["claim_date"] <= pd.Timestamp(dr[1]))]
if br != "(ทุกสาขา)":
    f = f[f["branch_code"].astype(str) == br]

f["เกินเกณฑ์"] = f["claim_pct"] > thr

# ─── KPI ───
k1, k2, k3, k4 = st.columns(4)
k1.metric("ร้าน × วัน (ทั้งหมด)", f"{len(f):,}")
k2.metric(f"⚠️ เกิน {thr:.0f}%", f"{int(f['เกินเกณฑ์'].sum()):,}")
k3.metric("ยอดขายรวม", f"{f['sale_amount'].sum():,.0f}")
k4.metric("ยอดเครมรวม", f"{f['claim_amount'].sum():,.0f}")

st.divider()

cols = [c for c in ["claim_date", "branch_code", "billing_no", "ref",
                     "sale_amount", "claim_amount", "claim_pct"] if c in df.columns]
RENAME = {
    "claim_date": "วันที่เครม", "branch_code": "รหัสสาขา", "billing_no": "Billing No",
    "ref": "เลขใบเคลม", "sale_amount": "ยอดขาย", "claim_amount": "ยอดเครม", "claim_pct": "claim %",
}
fmt = {"ยอดขาย": "{:,.0f}", "ยอดเครม": "{:,.0f}", "claim %": "{:.2f}%"}


def _prep(d):
    d = d[cols].copy()
    if "claim_date" in d.columns:
        d["claim_date"] = pd.to_datetime(d["claim_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return d.rename(columns=RENAME)

# ─── ร้านที่เครมเกิน X% (มากกว่า ไม่รวม = X%) ───
st.subheader(f"⚠️ ร้านที่เครม **เกิน** {thr:.0f}% ของยอดขาย (10% พอดีไม่นับ)")
over = f[f["เกินเกณฑ์"]].sort_values("claim_pct", ascending=False)
if over.empty:
    st.success(f"ไม่มีร้านที่เครมเกิน {thr:.0f}% ในช่วงที่เลือก ✅")
else:
    show = _prep(over)
    st.dataframe(
        show.style.format(fmt).apply(
            lambda r: ["background-color:#ffd6d6; color:#b00020"] * len(r), axis=1
        ),
        use_container_width=True, hide_index=True,
    )
    st.download_button(
        f"⬇ ดาวน์โหลดร้านที่เกิน {thr:.0f}% (CSV)",
        show.to_csv(index=False).encode("utf-8-sig"),
        "amazon_claim_over.csv", "text/csv",
    )

# ─── รายการทั้งหมด (ซ่อนใน expander — เผื่ออยากดูภาพรวม) ───
with st.expander("ดูรายการทั้งหมด (รวมร้านที่ไม่เกินเกณฑ์)"):
    allshow = f.sort_values("claim_pct", ascending=False)
    disp = _prep(allshow)
    over_by_idx = allshow["เกินเกณฑ์"]   # aligned by index with disp

    def _hl(row):
        style = "background-color:#ffecec" if bool(over_by_idx.loc[row.name]) else ""
        return [style] * len(row)

    st.dataframe(
        disp.style.format(fmt).apply(_hl, axis=1),
        use_container_width=True, hide_index=True,
    )
    st.download_button(
        "⬇ ดาวน์โหลดทั้งหมด (CSV)",
        disp.to_csv(index=False).encode("utf-8-sig"),
        "amazon_claim_summary.csv", "text/csv",
    )
