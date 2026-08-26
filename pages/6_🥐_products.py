"""Product Dashboard — สินค้ารายเดือน."""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from config import DATASETS
from auth import require_login, can_access
from datasets import load_dataset
from usage_log import log_event
from time_utils import th_str


st.set_page_config(page_title="Products — Wanwanach", page_icon="🥐", layout="wide")
require_login()

COLORS = {"primary": "#1976D2", "success": "#4CAF50", "danger": "#EF5350", "muted": "#78909C"}


def fmt_num(v, unit=""):
    if pd.isna(v) or v == 0:
        return "0" + unit
    for suffix, div in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(v) >= div:
            return f"{v/div:,.2f}{suffix}{unit}"
    return f"{v:,.0f}{unit}"


def styled_metric(label, value, delta=None):
    delta_html = ""
    if delta is not None:
        color = COLORS["success"] if delta >= 0 else COLORS["danger"]
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = f'<div style="color:{color};font-size:14px;margin-top:4px;">{arrow} {abs(delta):.1f}%</div>'
    html = (
        f'<div style="padding:16px;background:linear-gradient(135deg,#F5F7FA 0%,#E8EAF6 100%);'
        f'border-left:4px solid {COLORS["primary"]};border-radius:8px;height:100%;">'
        f'<div style="color:{COLORS["muted"]};font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>'
        f'<div style="color:{COLORS["primary"]};font-size:24px;font-weight:700;margin-top:4px;">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


st.title("🥐 Product Dashboard")
st.caption(f"อัพเดทล่าสุด: {th_str()}")

if not can_access(DATASETS.get("product_monthly", {})):
    st.warning("ยังไม่มีสิทธิ์เข้าถึง"); st.stop()

try:
    df = load_dataset("product_monthly")
except Exception as e:
    st.error(f"โหลดไม่สำเร็จ: {e}"); st.stop()

log_event("view_dashboard", "product_monthly")

# Detect date column
date_col = "year_month" if "year_month" in df.columns else None
if date_col is None:
    st.error("ไม่พบคอลัมน์ year_month")
    st.stop()

df[date_col] = df[date_col].astype(str)
all_months = sorted(df[date_col].unique())

# ─── Sidebar ───
with st.sidebar:
    st.markdown("### 🎛 ตัวกรอง")
    if all_months:
        default_start = all_months[max(0, len(all_months) - 12)]
        default_end = all_months[-1]
        start_m, end_m = st.select_slider(
            "ช่วงเดือน",
            options=all_months,
            value=(default_start, default_end),
        )

        channels = sorted(df["channel"].dropna().astype(str).unique().tolist()) if "channel" in df.columns else []
        sel_channels = st.multiselect("ช่องทาง", channels, default=[])

        if "customer_category" in df.columns:
            cats = sorted(df["customer_category"].dropna().astype(str).unique().tolist())
            sel_cats = st.multiselect("กลุ่มลูกค้า", cats, default=[])
        else:
            sel_cats = []

        rank_mode = st.radio(
            "🏆 มุมมอง",
            options=["Top (ขายดี)", "Bottom (ขายไม่ดี)", "Both"],
            index=0,
            horizontal=False,
        )
        top_n = st.slider("จำนวน N สินค้า", 5, 50, 20)

# ─── Filter ───
mask = (df[date_col] >= start_m) & (df[date_col] <= end_m)
if sel_channels and "channel" in df.columns:
    mask &= df["channel"].astype(str).isin(sel_channels)
if sel_cats and "customer_category" in df.columns:
    mask &= df["customer_category"].astype(str).isin(sel_cats)
current = df[mask].copy()

# Previous period (same length)
n_months = all_months.index(end_m) - all_months.index(start_m) + 1
prev_end_idx = all_months.index(start_m) - 1
prev_start_idx = max(0, prev_end_idx - n_months + 1)
if prev_end_idx >= 0:
    prev_start = all_months[prev_start_idx]
    prev_end = all_months[prev_end_idx]
    prev_mask = (df[date_col] >= prev_start) & (df[date_col] <= prev_end)
    if sel_channels and "channel" in df.columns:
        prev_mask &= df["channel"].astype(str).isin(sel_channels)
    if sel_cats and "customer_category" in df.columns:
        prev_mask &= df["customer_category"].astype(str).isin(sel_cats)
    previous = df[prev_mask].copy()
else:
    previous = pd.DataFrame(columns=df.columns)

if len(current) == 0:
    st.warning("ไม่มีข้อมูลในช่วงที่เลือก"); st.stop()

# ═══════════════════════════════════════════════════════════
# 🔥 KPI Row
# ═══════════════════════════════════════════════════════════
cur_rev = current["revenue"].sum()
cur_qty = current["qty"].sum()
cur_products = current["product_code"].nunique()
prev_rev = previous["revenue"].sum() if len(previous) else 0

rev_pct = ((cur_rev - prev_rev) / prev_rev * 100) if prev_rev else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    styled_metric("💰 Revenue", fmt_num(cur_rev, " ฿"), delta=rev_pct)
with c2:
    styled_metric("📦 Units Sold", fmt_num(cur_qty))
with c3:
    styled_metric("🥐 Unique SKUs", f"{cur_products:,}")
with c4:
    avg_ppu = (cur_rev / cur_qty) if cur_qty else 0
    styled_metric("💵 Avg Price/Unit", fmt_num(avg_ppu, " ฿"))

st.divider()

# ═══════════════════════════════════════════════════════════
# 📊 Rank Products (Top / Bottom / Both)
# ═══════════════════════════════════════════════════════════
def _rank_chart(ranked_df, title, color):
    """Reusable horizontal bar chart for ranked products."""
    ranked_df = ranked_df.copy()
    ranked_df["label"] = (
        ranked_df["product_name"].astype(str).str[:30] + " (" +
        ranked_df["product_code"].astype(str) + ")"
    )
    ranked_df = ranked_df.sort_values("revenue")
    fig = px.bar(
        ranked_df, x="revenue", y="label",
        orientation="h",
        text=ranked_df["revenue"].apply(fmt_num),
        color_discrete_sequence=[color],
    )
    fig.update_traces(textposition="outside", textfont_size=10)
    fig.update_layout(
        height=max(400, len(ranked_df) * 25),
        margin=dict(l=10, r=100, t=20, b=20),
        xaxis_title="Revenue (฿)", yaxis_title=None,
        xaxis=dict(tickformat=".2s", ticksuffix="฿", showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
        yaxis=dict(showgrid=False, type="category"),
    )
    return fig


# Group once for both Top and Bottom
all_products = (current.groupby(["product_code", "product_name"], as_index=False)
                .agg(revenue=("revenue", "sum"), qty=("qty", "sum")))
# Filter out products with 0 revenue (they're noise for Bottom)
all_products = all_products[all_products["revenue"] > 0]

top_prod    = all_products.nlargest(top_n, "revenue")
bottom_prod = all_products.nsmallest(top_n, "revenue")

show_top    = rank_mode in ("Top (ขายดี)", "Both")
show_bottom = rank_mode in ("Bottom (ขายไม่ดี)", "Both")

if rank_mode == "Both":
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.markdown(f"### 🏆 Top {top_n} — ขายดี")
        if len(top_prod) > 0:
            st.plotly_chart(_rank_chart(top_prod, "Top", COLORS["success"]), use_container_width=True)
    with col_r:
        st.markdown(f"### 📉 Bottom {top_n} — ขายไม่ดี")
        if len(bottom_prod) > 0:
            st.plotly_chart(_rank_chart(bottom_prod, "Bottom", COLORS["danger"]), use_container_width=True)
else:
    col_l, col_r = st.columns([1, 1])
    with col_l:
        if show_top:
            st.markdown(f"### 🏆 Top {top_n} Products by Revenue")
            if len(top_prod) > 0:
                st.plotly_chart(_rank_chart(top_prod, "Top", COLORS["primary"]), use_container_width=True)
        else:
            st.markdown(f"### 📉 Bottom {top_n} Products by Revenue")
            if len(bottom_prod) > 0:
                st.plotly_chart(_rank_chart(bottom_prod, "Bottom", COLORS["danger"]), use_container_width=True)

    with col_r:
        # ⭐ Trend limit — cap at 10 lines (readable)
        trend_n = min(top_n, 10)
        trend_source = top_prod if show_top else bottom_prod
        trend_label = "Top" if show_top else "Bottom"
        st.markdown(f"### 📈 Monthly Trend ({trend_label} {trend_n})")
        top_codes = trend_source.head(trend_n)["product_code"].tolist() if len(trend_source) else []
        if top_codes:
            trend = current[current["product_code"].isin(top_codes)]
            trend_pv = (trend.groupby([date_col, "product_code", "product_name"], as_index=False)["revenue"].sum())
            trend_pv["label"] = trend_pv["product_name"].astype(str).str[:18] + " (" + trend_pv["product_code"].astype(str) + ")"

            fig = px.line(
                trend_pv, x=date_col, y="revenue",
                color="label",
                markers=True,
                hover_data={"revenue": ":,.0f", "product_code": True},
            )
            fig.update_layout(
                height=max(450, top_n * 25),
                margin=dict(l=20, r=20, t=20, b=20),
                hovermode="x unified",
                xaxis_title=None, yaxis_title="Revenue (฿)",
                yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.3)", tickformat=".2s", ticksuffix="฿"),
                xaxis=dict(showgrid=False, tickangle=-30),
                legend=dict(
                    orientation="v",
                    yanchor="top", y=1, xanchor="left", x=1.02,
                    font=dict(size=10),
                    title_text="",
                ),
            )
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# 📊 Category (source) breakdown
# ═══════════════════════════════════════════════════════════
if "channel" in current.columns:
    st.markdown("### 📊 Revenue by Channel (per month)")
    by_ch = current.groupby([date_col, "channel"], as_index=False)["revenue"].sum()
    if len(by_ch) > 0:
        fig = px.bar(
            by_ch, x=date_col, y="revenue", color="channel",
            barmode="stack",
            hover_data={"revenue": ":,.0f"},
        )
        fig.update_layout(
            height=400,
            margin=dict(l=20, r=20, t=20, b=40),
            xaxis_title=None, yaxis_title="Revenue",
            yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.3)", tickformat=".2s", ticksuffix="฿"),
            xaxis=dict(showgrid=False),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# 📋 Product Table (searchable)
# ═══════════════════════════════════════════════════════════
st.markdown("### 📋 All Products (search + sort)")
prod_search = st.text_input("🔍 ค้นหาสินค้า (ชื่อ/รหัส)", "")

all_prod = (current.groupby(["product_code", "product_name"], as_index=False)
            .agg(revenue=("revenue", "sum"), qty=("qty", "sum")))
all_prod["avg_price"] = (all_prod["revenue"] / all_prod["qty"]).round(2)
if prod_search:
    all_prod = all_prod[
        all_prod["product_code"].astype(str).str.contains(prod_search, case=False, na=False) |
        all_prod["product_name"].astype(str).str.contains(prod_search, case=False, na=False)
    ]
all_prod = all_prod.sort_values("revenue", ascending=False)
st.caption(f"แสดง {len(all_prod):,} สินค้า")
st.dataframe(
    all_prod.style.format({"revenue": "{:,.0f}", "qty": "{:,.0f}", "avg_price": "{:,.2f}"}),
    use_container_width=True, hide_index=True, height=400,
)

st.caption(f"📅 Period: {start_m} → {end_m}  ({n_months} months)")
