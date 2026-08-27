"""
Executive Dashboard — BI-style overview with KPIs, trends, and rankings.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from config import DATASETS
from auth import require_login, can_access
from datasets import load_dataset
from usage_log import log_event
from time_utils import th_str
from ui_helpers import COLORS, CHANNEL_COLORS, SOURCE_COLORS, fmt_num, safe_div, styled_metric


st.set_page_config(page_title="Dashboard — Wanwanach", page_icon="📊", layout="wide")
require_login()

# Theme + fmt_num + styled_metric imported from ui_helpers (was duplicated 3x)


st.title("📊 Executive Dashboard")
st.caption(f"อัพเดทล่าสุด: {th_str()}")

# ⭐ Memory-safe: cap max range (Streamlit Free tier = 1 GB RAM)
_MAX_MONTHS = 48  # 4 ปี max

# ─── Load sales_daily ───
if not can_access(DATASETS.get("sales_daily", {})):
    st.warning("ยังไม่มีสิทธิ์เข้าถึง")
    st.stop()

try:
    df = load_dataset("sales_daily")
except Exception as e:
    st.error(f"โหลดข้อมูลไม่สำเร็จ: {e}")
    st.stop()

# ⭐ Memory-friendly: convert string cols to categorical (saves ~70% RAM)
for _c in ["source", "channel", "customer_category", "branch_code"]:
    if _c in df.columns and df[_c].dtype == "object":
        df[_c] = df[_c].astype("category")

log_event("view_dashboard", "sales_daily")

# ─── Sidebar filter ───
with st.sidebar:
    st.markdown("### 🎛 ตัวกรอง")

    if pd.api.types.is_datetime64_any_dtype(df["date"]):
        min_d, max_d = df["date"].min(), df["date"].max()

        preset = st.radio(
            "ช่วงเวลา",
            ["30 วัน", "3 เดือน", "6 เดือน", "12 เดือน", "ปีนี้ (YTD)", "กำหนดเอง"],
            index=3,
            help="ช่วง 'เดือน' = เต็มเดือน ตรงกับหน้า Products / Locations",
        )
        # First day of max_d's month (align to Products/Locations)
        max_month_start = pd.Timestamp(max_d.year, max_d.month, 1)

        if preset == "30 วัน":
            start = max_d - pd.DateOffset(days=30)
            end = max_d
        elif preset == "3 เดือน":
            # Last 3 full months (e.g., if max = 2026-08-31 → Jun 1 → Aug 31)
            start = max_month_start - pd.DateOffset(months=2)
            end = max_d
        elif preset == "6 เดือน":
            start = max_month_start - pd.DateOffset(months=5)
            end = max_d
        elif preset == "12 เดือน":
            start = max_month_start - pd.DateOffset(months=11)
            end = max_d
        elif preset == "ปีนี้ (YTD)":
            start = pd.Timestamp(max_d.year, 1, 1)
            end = max_d
        else:
            date_range = st.date_input(
                "เลือกช่วง",
                value=(max_d.date() - timedelta(days=365), max_d.date()),
                min_value=min_d.date(),
                max_value=max_d.date(),
            )
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
            else:
                start, end = min_d, max_d

        st.caption(f"📅 {start.date()} → {end.date()}")
        if preset in ("3 เดือน", "6 เดือน", "12 เดือน", "ปีนี้ (YTD)"):
            n_m = ((end.year - start.year) * 12 + (end.month - start.month) + 1)
            st.caption(f"= {n_m} เต็มเดือน (ตรงกับ Products/Locations)")

        # Channel filter
        channels = sorted(df["channel"].dropna().astype(str).unique().tolist())
        sel_channels = st.multiselect("ช่องทาง", channels, default=[])

        # Source filter
        sources = sorted(df["source"].dropna().astype(str).unique().tolist())
        sel_sources = st.multiselect("แหล่งข้อมูล", sources, default=[])

        # Customer category filter
        if "customer_category" in df.columns:
            cats = sorted(df["customer_category"].dropna().astype(str).unique().tolist())
            sel_cats = st.multiselect("กลุ่มลูกค้า", cats, default=[])
        else:
            sel_cats = []

    else:
        start, end = df["date"].min(), df["date"].max()
        sel_channels = []
        sel_sources = []
        sel_cats = []

# ⭐ Guard: ตัด range ก่อน filter (ป้องกัน OOM + ให้ previous คำนวณถูกต้อง)
_n_months = ((end.year - start.year) * 12 + (end.month - start.month) + 1)
if _n_months > _MAX_MONTHS:
    st.warning(
        f"⚠️ ช่วงเวลาที่เลือก **{_n_months} เดือน** ยาวเกิน limit ({_MAX_MONTHS} เดือน)\n\n"
        f"อาจทำให้ระบบค้าง — ตัดเป็น {_MAX_MONTHS} เดือนล่าสุดอัตโนมัติ"
    )
    start = end - pd.DateOffset(months=_MAX_MONTHS)

# ─── Apply filters ───
def _build_mask(_start, _end):
    m = (df["date"] >= _start) & (df["date"] <= _end)
    if sel_channels:
        m &= df["channel"].astype(str).isin(sel_channels)
    if sel_sources:
        m &= df["source"].astype(str).isin(sel_sources)
    if sel_cats and "customer_category" in df.columns:
        m &= df["customer_category"].astype(str).isin(sel_cats)
    return m


current = df[_build_mask(start, end)].copy()

# Previous period (same length, before start)
period_days = (end - start).days + 1
prev_start = start - pd.DateOffset(days=period_days)
prev_end = start - pd.DateOffset(days=1)
previous = df[_build_mask(prev_start, prev_end)].copy()

if len(current) == 0:
    st.warning("ไม่มีข้อมูลในช่วงเวลาที่เลือก")
    st.stop()


# ═══════════════════════════════════════════════════════════
# 🔥 KPI Row
# ═══════════════════════════════════════════════════════════
cur_rev  = current["revenue"].sum()
prev_rev = previous["revenue"].sum() if len(previous) else 0
rev_pct  = ((cur_rev - prev_rev) / prev_rev * 100) if prev_rev else 0

cur_qty  = current["qty"].sum()
prev_qty = previous["qty"].sum() if len(previous) else 0
qty_pct  = safe_div(cur_qty - prev_qty, prev_qty, 0) * 100

# ⭐ txn: only compute if column exists (no misleading fallback to row count)
has_txn = "n_transactions" in current.columns
if has_txn:
    cur_txn = current["n_transactions"].sum()
    prev_txn = previous["n_transactions"].sum() if len(previous) else 0
    txn_pct = safe_div(cur_txn - prev_txn, prev_txn, 0) * 100

cur_branches  = current["branch_code"].nunique()
prev_branches = previous["branch_code"].nunique() if len(previous) else 0
br_delta = cur_branches - prev_branches

c1, c2, c3, c4 = st.columns(4)
with c1:
    styled_metric("💰 Revenue", fmt_num(cur_rev, " ฿"), delta=safe_div(cur_rev - prev_rev, prev_rev, 0) * 100)
with c2:
    styled_metric("📦 Quantity", fmt_num(cur_qty), delta=qty_pct)
with c3:
    if has_txn:
        styled_metric("🧾 Transactions", fmt_num(cur_txn), delta=txn_pct)
    else:
        styled_metric("🧾 Transactions", "—")
with c4:
    styled_metric(
        "🏪 Active Branches", f"{cur_branches:,}",
        delta=safe_div(br_delta, prev_branches, 0) * 100,
    )

st.caption(f"เทียบกับช่วงก่อน: {prev_start.date()} → {prev_end.date()}")
st.divider()


# ═══════════════════════════════════════════════════════════
# 📈 Revenue Trend + Channel Mix
# ═══════════════════════════════════════════════════════════
col_l, col_r = st.columns([2, 1])

with col_l:
    st.markdown("### 📈 Revenue Trend")
    # ⭐ Auto-switch granularity based on period length
    if period_days <= 62:                     # ≤ 2 months → daily
        grain, gr_col = "day", current["date"].dt.date.astype(str)
    elif period_days <= 366:                  # ≤ 1 year → monthly
        grain, gr_col = "month", current["date"].dt.to_period("M").astype(str)
    else:                                     # > 1 year → quarterly
        grain, gr_col = "quarter", current["date"].dt.to_period("Q").astype(str)

    trend = (current.assign(period=gr_col)
             .groupby(["period", "channel"], as_index=False)["revenue"].sum())

    if len(trend) > 0:
        # ⭐ Stacked bar ทุกช่วง — ตรงกับ Source Breakdown, เห็น total + channel ชัดเจน
        fig = px.bar(
            trend, x="period", y="revenue", color="channel",
            color_discrete_map=CHANNEL_COLORS,
            barmode="stack",
            hover_data={"revenue": ":,.0f"},
        )
        fig.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=20, b=40),
            hovermode="x unified",
            xaxis_title=None, yaxis_title="Revenue (฿)",
            yaxis=dict(
                showgrid=True, gridcolor="rgba(200,200,200,0.3)",
                tickformat=".2s",  # SI notation: 2.5M, 30M, 1.5B
                ticksuffix="฿",
            ),
            xaxis=dict(showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"granularity: {grain} · {len(trend['period'].unique())} periods")
    else:
        st.info("ไม่มีข้อมูล")

with col_r:
    st.markdown("### 🥧 Channel Mix")
    mix = current.groupby("channel", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
    if len(mix) > 0:
        fig = px.pie(
            mix, names="channel", values="revenue",
            color="channel", color_discrete_map=CHANNEL_COLORS,
            hole=0.55,
        )
        fig.update_traces(
            textposition="outside",
            textinfo="label+percent",
            textfont_size=12,
        )
        total = mix["revenue"].sum()
        fig.add_annotation(
            text=f"<b>{fmt_num(total)}</b><br><span style='font-size:12px;color:gray;'>Total ฿</span>",
            showarrow=False, x=0.5, y=0.5, font=dict(size=18),
        )
        fig.update_layout(
            height=380,
            margin=dict(l=0, r=0, t=20, b=20),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# 🏆 Top Branches + Source Breakdown
# ═══════════════════════════════════════════════════════════
col_l, col_r = st.columns(2)

with col_l:
    st.markdown("### 🏆 Top 15 Branches")
    top_br = (current.groupby("branch_code", as_index=False)["revenue"].sum()
              .nlargest(15, "revenue")).sort_values("revenue")
    if len(top_br) > 0:
        top_br["branch_label"] = top_br["branch_code"].astype(str)
        fig = px.bar(
            top_br,
            x="revenue", y="branch_label",
            orientation="h",
            text=top_br["revenue"].apply(fmt_num),
            color_discrete_sequence=[COLORS["primary"]],
        )
        fig.update_traces(textposition="outside", textfont_size=10)
        fig.update_layout(
            height=450,
            margin=dict(l=10, r=80, t=20, b=20),
            xaxis_title="Revenue (฿)", yaxis_title=None,
            xaxis=dict(
                tickformat=".2s",  # 10M instead of 10,000,000
                ticksuffix="฿",
                showgrid=True, gridcolor="rgba(200,200,200,0.3)",
            ),
            yaxis=dict(showgrid=False, type="category"),  # ⭐ Force categorical
        )
        st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.markdown("### 📊 Source Breakdown")
    src_month = (current.assign(period=gr_col)
                 .groupby(["period", "source"], as_index=False)["revenue"].sum())
    if len(src_month) > 0:
        fig = px.bar(
            src_month, x="period", y="revenue", color="source",
            color_discrete_map=SOURCE_COLORS,
            hover_data={"revenue": ":,.0f"},
        )
        fig.update_layout(
            height=450,
            barmode="stack",
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis_title=None, yaxis_title="Revenue (฿)",
            yaxis=dict(
                showgrid=True, gridcolor="rgba(200,200,200,0.3)",
                tickformat=".2s", ticksuffix="฿",
            ),
            xaxis=dict(showgrid=False),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ไม่มีข้อมูล")


# ═══════════════════════════════════════════════════════════
# 📅 Weekly Pattern (Heatmap) + Growth by Channel
# ═══════════════════════════════════════════════════════════
col_l, col_r = st.columns(2)

with col_l:
    st.markdown("### 🔥 Weekly Pattern (day × month)")
    # ⭐ Safeguard: skip heatmap if too many months (RAM heavy) or too few (meaningless)
    n_months_period = ((end.year - start.year) * 12 + (end.month - start.month) + 1)
    if n_months_period > 36:
        st.info(f"ℹ️ ช่วงที่เลือก {n_months_period} เดือน ใหญ่เกินไปสำหรับ heatmap — เลือกช่วงสั้นลง (≤ 36 เดือน) เพื่อดู pattern รายวัน")
        heatmap = pd.DataFrame()
    else:
        hm_df = current[["date", "revenue"]].copy()
        # Thai day names for readability
        _th_days = {0: "จ.", 1: "อ.", 2: "พ.", 3: "พฤ.", 4: "ศ.", 5: "ส.", 6: "อา."}
        hm_df["day_name"] = hm_df["date"].dt.dayofweek.map(_th_days)
        hm_df["month"] = hm_df["date"].dt.to_period("M").astype(str)
        day_order = ["จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา."]

        heatmap = (hm_df.groupby(["day_name", "month"], as_index=False)["revenue"].sum()
                   .pivot(index="day_name", columns="month", values="revenue")
                   .reindex(day_order))
        heatmap = heatmap.dropna(how="all").dropna(how="all", axis=1)
        del hm_df
    if not heatmap.empty and heatmap.shape[1] >= 1:
        # ⭐ Format text overlay ให้อ่านง่าย (K/M/B)
        text_matrix = [[fmt_num(v) if pd.notna(v) else "" for v in row] for row in heatmap.values]
        fig = px.imshow(
            heatmap.values,
            x=heatmap.columns,
            y=heatmap.index,
            aspect="auto",
            color_continuous_scale="Blues",
            labels=dict(x="Month", y="Day", color="Revenue (฿)"),
        )
        fig.update_traces(
            text=text_matrix, texttemplate="%{text}",
            textfont=dict(size=10),
            hovertemplate="<b>%{y}</b> · %{x}<br>Revenue: %{text}<extra></extra>",
        )
        fig.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=20, b=40),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.markdown("### 📊 Channel Growth vs Previous Period")
    growth_data = []
    for ch in current["channel"].dropna().unique():
        c_rev = current[current["channel"] == ch]["revenue"].sum()
        p_rev = previous[previous["channel"] == ch]["revenue"].sum() if len(previous) else 0
        growth = ((c_rev - p_rev) / p_rev * 100) if p_rev else 0
        growth_data.append({"channel": ch, "current": c_rev, "previous": p_rev, "growth": growth})

    gr = pd.DataFrame(growth_data).sort_values("current", ascending=True)
    if len(gr) > 0:
        gr["color"] = gr["growth"].apply(lambda g: COLORS["success"] if g >= 0 else COLORS["danger"])
        gr["label"] = gr.apply(lambda r: f"{fmt_num(r['current'])} ({'+' if r['growth']>=0 else ''}{r['growth']:.1f}%)", axis=1)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=gr["current"], y=gr["channel"],
            orientation="h",
            marker=dict(color=gr["color"]),
            text=gr["label"],
            textposition="outside",
            name="Current",
        ))
        fig.update_layout(
            height=380,
            margin=dict(l=20, r=100, t=20, b=40),
            xaxis_title="Revenue (฿)",
            yaxis_title=None,
            xaxis=dict(
                tickformat=".2s", ticksuffix="฿",
                showgrid=True, gridcolor="rgba(200,200,200,0.3)",
            ),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# 📋 Summary Table
# ═══════════════════════════════════════════════════════════
st.markdown("### 📋 Summary by Channel")
summary = (current.groupby("channel", as_index=False).agg(
    revenue=("revenue", "sum"),
    qty=("qty", "sum"),
    branches=("branch_code", "nunique"),
    days=("date", lambda x: x.dt.date.nunique()),
).sort_values("revenue", ascending=False))
summary["avg/day"] = (summary["revenue"] / summary["days"]).round(0)
summary["revenue"] = summary["revenue"].apply(lambda v: f"{v:,.0f}")
summary["qty"] = summary["qty"].apply(lambda v: f"{v:,.0f}")
summary["avg/day"] = summary["avg/day"].apply(lambda v: f"{v:,.0f}")
st.dataframe(summary, use_container_width=True, hide_index=True)

st.caption(
    f"📅 Period: {start.date()} → {end.date()}  ({period_days} days)  |  "
    f"Rows: {len(current):,}"
)
