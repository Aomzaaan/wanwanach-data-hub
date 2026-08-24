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


st.set_page_config(page_title="Dashboard — Wanwanach", page_icon="📊", layout="wide")
require_login()

# ─── Theme constants ───
COLORS = {
    "primary":   "#1976D2",
    "accent":    "#42A5F5",
    "success":   "#4CAF50",
    "warning":   "#FFA726",
    "danger":    "#EF5350",
    "muted":     "#78909C",
}
CHANNEL_COLORS = {
    "Telesale":    "#1976D2",
    "ModernTrade": "#EF5350",
    "Booth":       "#4CAF50",
    "Online":      "#FFA726",
}
SOURCE_COLORS = {
    "amazon":         "#EF5350",
    "credit":         "#1976D2",
    "credit_note":    "#78909C",
    "cash":           "#4CAF50",
    "booth":          "#FFA726",
    "online_product": "#AB47BC",
}


def fmt_num(v, unit=""):
    """Format 1_234_567 → 1.2M"""
    if pd.isna(v) or v == 0:
        return "0" + unit
    for suffix, div in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(v) >= div:
            return f"{v/div:,.2f}{suffix}{unit}"
    return f"{v:,.0f}{unit}"


def styled_metric(label, value, delta=None, delta_prefix="", help=None):
    """Render a colored metric card."""
    delta_html = ""
    if delta is not None:
        color = COLORS["success"] if delta >= 0 else COLORS["danger"]
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = f'<div style="color:{color};font-size:14px;margin-top:4px;">{arrow} {delta_prefix}{abs(delta):.1f}%</div>'
    html = (
        f'<div style="padding:16px;background:linear-gradient(135deg,#F5F7FA 0%,#E8EAF6 100%);'
        f'border-left:4px solid {COLORS["primary"]};border-radius:8px;height:100%;">'
        f'<div style="color:{COLORS["muted"]};font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>'
        f'<div style="color:{COLORS["primary"]};font-size:28px;font-weight:700;margin-top:4px;">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


st.title("📊 Executive Dashboard")
st.caption(f"อัพเดทล่าสุด: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# ─── Load sales_daily ───
if not can_access(DATASETS.get("sales_daily", {})):
    st.warning("ยังไม่มีสิทธิ์เข้าถึง")
    st.stop()

try:
    df = load_dataset("sales_daily")
except Exception as e:
    st.error(f"โหลดข้อมูลไม่สำเร็จ: {e}")
    st.stop()

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

    else:
        start, end = df["date"].min(), df["date"].max()
        sel_channels = []
        sel_sources = []

# ─── Apply filters ───
mask = (df["date"] >= start) & (df["date"] <= end)
if sel_channels:
    mask &= df["channel"].astype(str).isin(sel_channels)
if sel_sources:
    mask &= df["source"].astype(str).isin(sel_sources)
current = df[mask].copy()

# Previous period (same length, before start)
period_days = (end - start).days + 1
prev_start = start - pd.DateOffset(days=period_days)
prev_end = start - pd.DateOffset(days=1)
prev_mask = (df["date"] >= prev_start) & (df["date"] <= prev_end)
if sel_channels:
    prev_mask &= df["channel"].astype(str).isin(sel_channels)
if sel_sources:
    prev_mask &= df["source"].astype(str).isin(sel_sources)
previous = df[prev_mask].copy()

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
qty_pct  = ((cur_qty - prev_qty) / prev_qty * 100) if prev_qty else 0

cur_txn  = current["n_transactions"].sum() if "n_transactions" in current.columns else len(current)
prev_txn = previous["n_transactions"].sum() if "n_transactions" in previous.columns and len(previous) else 0
txn_pct  = ((cur_txn - prev_txn) / prev_txn * 100) if prev_txn else 0

cur_branches  = current["branch_code"].nunique()
prev_branches = previous["branch_code"].nunique() if len(previous) else 0
br_delta = cur_branches - prev_branches

c1, c2, c3, c4 = st.columns(4)
with c1:
    styled_metric("💰 Revenue", fmt_num(cur_rev, " ฿"), delta=rev_pct)
with c2:
    styled_metric("📦 Quantity", fmt_num(cur_qty), delta=qty_pct)
with c3:
    styled_metric("🧾 Transactions", fmt_num(cur_txn), delta=txn_pct)
with c4:
    styled_metric("🏪 Active Branches", f"{cur_branches:,}",
                  delta=(br_delta / prev_branches * 100) if prev_branches else 0)

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
        # Line chart safer than area for short periods (won't look empty)
        chart_fn = px.line if len(trend["period"].unique()) <= 3 else px.area
        fig = chart_fn(
            trend, x="period", y="revenue", color="channel",
            color_discrete_map=CHANNEL_COLORS,
            hover_data={"revenue": ":,.0f"},
            markers=True if chart_fn == px.line else False,
        )
        fig.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=20, b=40),
            hovermode="x unified",
            xaxis_title=None, yaxis_title=None,
            yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.3)", tickformat=",.0f"),
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
              .nlargest(15, "revenue"))
    if len(top_br) > 0:
        fig = px.bar(
            top_br.sort_values("revenue"),
            x="revenue", y="branch_code",
            orientation="h",
            text=top_br.sort_values("revenue")["revenue"].apply(fmt_num),
            color_discrete_sequence=[COLORS["primary"]],
        )
        fig.update_traces(textposition="outside", textfont_size=10)
        fig.update_layout(
            height=450,
            margin=dict(l=10, r=80, t=20, b=20),
            xaxis_title=None, yaxis_title=None,
            xaxis=dict(tickformat=",.0f", showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
            yaxis=dict(showgrid=False),
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
            xaxis_title=None, yaxis_title=None,
            yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.3)", tickformat=",.0f"),
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
    hm_df = current.copy()
    hm_df["day_name"] = hm_df["date"].dt.day_name()
    hm_df["month"] = hm_df["date"].dt.to_period("M").astype(str)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    heatmap = (hm_df.groupby(["day_name", "month"], as_index=False)["revenue"].sum()
               .pivot(index="day_name", columns="month", values="revenue")
               .reindex(day_order))
    # Drop rows/cols that are all NaN (day_names not in filtered data)
    heatmap = heatmap.dropna(how="all").dropna(how="all", axis=1)
    if not heatmap.empty and heatmap.shape[1] >= 1:
        fig = px.imshow(
            heatmap.values,
            x=heatmap.columns,
            y=heatmap.index,
            aspect="auto",
            color_continuous_scale="Blues",
            labels=dict(x="Month", y="Day", color="Revenue"),
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
            xaxis_title="Revenue",
            yaxis_title=None,
            xaxis=dict(tickformat=",.0f", showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
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
