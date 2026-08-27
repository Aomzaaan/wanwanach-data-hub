"""Location Dashboard — พื้นที่รายเดือน."""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from config import DATASETS
from auth import require_login, can_access
from datasets import load_dataset
from usage_log import log_event
from time_utils import th_str
from ui_helpers import COLORS, fmt_num, safe_div, styled_metric


st.set_page_config(page_title="Locations — Wanwanach", page_icon="🗺", layout="wide")
require_login()

# COLORS + fmt_num + styled_metric imported from ui_helpers


st.title("🗺 Location Dashboard")
st.caption(f"อัพเดทล่าสุด: {th_str()}")

if not can_access(DATASETS.get("location_monthly", {})):
    st.warning("ยังไม่มีสิทธิ์เข้าถึง"); st.stop()

try:
    df = load_dataset("location_monthly")
except Exception as e:
    st.error(f"โหลดไม่สำเร็จ: {e}"); st.stop()

log_event("view_dashboard", "location_monthly")

date_col = "year_month"
df[date_col] = df[date_col].astype(str)
all_months = sorted(df[date_col].unique())

# ─── Sidebar ───
with st.sidebar:
    st.markdown("### 🎛 ตัวกรอง")
    if all_months:
        default_start = all_months[max(0, len(all_months) - 12)]
        start_m, end_m = st.select_slider(
            "ช่วงเดือน", options=all_months,
            value=(default_start, all_months[-1]),
        )

        # Region / Area filter
        if "area" in df.columns:
            areas = sorted(df["area"].dropna().astype(str).unique().tolist())
            sel_areas = st.multiselect("Area", areas, default=[])
        else:
            sel_areas = []

        if "province" in df.columns:
            provs = sorted(df["province"].dropna().astype(str).unique().tolist())
            sel_provs = st.multiselect("จังหวัด", provs, default=[])
        else:
            sel_provs = []

# ─── Filter ───
mask = (df[date_col] >= start_m) & (df[date_col] <= end_m)
if sel_areas and "area" in df.columns:
    mask &= df["area"].astype(str).isin(sel_areas)
if sel_provs and "province" in df.columns:
    mask &= df["province"].astype(str).isin(sel_provs)
current = df[mask].copy()

# Previous
n_months = all_months.index(end_m) - all_months.index(start_m) + 1
prev_end_idx = all_months.index(start_m) - 1
prev_start_idx = max(0, prev_end_idx - n_months + 1)
if prev_end_idx >= 0:
    prev_mask = (df[date_col] >= all_months[prev_start_idx]) & (df[date_col] <= all_months[prev_end_idx])
    if sel_areas and "area" in df.columns:
        prev_mask &= df["area"].astype(str).isin(sel_areas)
    if sel_provs and "province" in df.columns:
        prev_mask &= df["province"].astype(str).isin(sel_provs)
    previous = df[prev_mask].copy()
else:
    previous = pd.DataFrame(columns=df.columns)

if len(current) == 0:
    st.warning("ไม่มีข้อมูลในช่วงที่เลือก"); st.stop()

# ═══════════════════════════════════════════════════════════
# 🔥 KPI Row
# ═══════════════════════════════════════════════════════════
cur_rev = current["revenue"].sum()
prev_rev = previous["revenue"].sum() if len(previous) else 0
# ⭐ Only show % if previous window is complete (else misleading)
_full_prev = prev_end_idx >= 0 and (prev_end_idx - prev_start_idx + 1) == n_months
rev_pct = safe_div(cur_rev - prev_rev, prev_rev, 0) * 100 if _full_prev else None

cur_provs = current["province"].nunique() if "province" in current.columns else 0
cur_branches = current["branch_code"].nunique() if "branch_code" in current.columns else 0
cur_routes = current["route"].nunique() if "route" in current.columns else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    styled_metric("💰 Revenue", fmt_num(cur_rev, " ฿"), delta=rev_pct)
with c2:
    styled_metric("🏙 Provinces", f"{cur_provs:,}")
with c3:
    styled_metric("🏪 Branches", f"{cur_branches:,}")
with c4:
    styled_metric("🚚 Routes", f"{cur_routes:,}")

st.divider()

# ═══════════════════════════════════════════════════════════
# 📊 By Province + By Area
# ═══════════════════════════════════════════════════════════
col_l, col_r = st.columns(2)

with col_l:
    st.markdown("### 🏙 Top 20 Provinces")
    if "province" in current.columns:
        by_prov = (current.groupby("province", as_index=False)["revenue"].sum()
                   .nlargest(20, "revenue"))
        if len(by_prov) > 0:
            fig = px.bar(
                by_prov.sort_values("revenue"),
                x="revenue", y="province",
                orientation="h",
                text=by_prov.sort_values("revenue")["revenue"].apply(fmt_num),
                color_discrete_sequence=[COLORS["primary"]],
            )
            fig.update_traces(textposition="outside", textfont_size=10)
            fig.update_layout(
                height=500,
                margin=dict(l=10, r=100, t=20, b=20),
                xaxis_title="Revenue", yaxis_title=None,
                xaxis=dict(tickformat=".2s", ticksuffix="฿", showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
                yaxis=dict(showgrid=False, type="category"),
            )
            st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.markdown("### 🌏 Revenue by Area")
    if "area" in current.columns:
        by_area = current.groupby("area", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        if len(by_area) > 0:
            fig = px.pie(
                by_area, names="area", values="revenue",
                hole=0.55,
            )
            fig.update_traces(textposition="outside", textinfo="label+percent")
            total = by_area["revenue"].sum()
            fig.add_annotation(
                text=f"<b>{fmt_num(total)}</b><br><span style='font-size:12px;color:gray;'>Total ฿</span>",
                showarrow=False, x=0.5, y=0.5, font=dict(size=18),
            )
            fig.update_layout(height=500, margin=dict(l=0, r=0, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# 🚚 Top Routes + Trend
# ═══════════════════════════════════════════════════════════
col_l, col_r = st.columns(2)

with col_l:
    st.markdown("### 🚚 Top 20 Routes")
    if "route" in current.columns:
        by_route = (current[current["route"].notna()]
                    .groupby("route", as_index=False)["revenue"].sum()
                    .nlargest(20, "revenue"))
        if len(by_route) > 0:
            fig = px.bar(
                by_route.sort_values("revenue"),
                x="revenue", y="route",
                orientation="h",
                text=by_route.sort_values("revenue")["revenue"].apply(fmt_num),
                color_discrete_sequence=["#4CAF50"],
            )
            fig.update_traces(textposition="outside", textfont_size=10)
            fig.update_layout(
                height=500,
                margin=dict(l=10, r=100, t=20, b=20),
                xaxis_title="Revenue", yaxis_title=None,
                xaxis=dict(tickformat=".2s", ticksuffix="฿", showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
                yaxis=dict(showgrid=False, type="category"),
            )
            st.plotly_chart(fig, use_container_width=True)

with col_r:
    st.markdown("### 📈 Trend by Area")
    if "area" in current.columns:
        by_month_area = current.groupby([date_col, "area"], as_index=False)["revenue"].sum()
        if len(by_month_area) > 0:
            n_periods = by_month_area[date_col].nunique()
            chart_fn = px.line if n_periods <= 3 else px.area
            fig = chart_fn(
                by_month_area, x=date_col, y="revenue", color="area",
                hover_data={"revenue": ":,.0f"},
                markers=(chart_fn == px.line),
            )
            fig.update_layout(
                height=500,
                margin=dict(l=20, r=20, t=20, b=40),
                hovermode="x unified",
                xaxis_title=None, yaxis_title="Revenue",
                yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.3)", tickformat=".2s", ticksuffix="฿"),
                xaxis=dict(showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
            )
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# 📋 Detail table
# ═══════════════════════════════════════════════════════════
st.markdown("### 📋 Details by Province × Route")
grouped = (current.groupby([c for c in ["province", "district", "route"] if c in current.columns], as_index=False, dropna=False)
           .agg(revenue=("revenue", "sum"), qty=("qty", "sum"))
           .sort_values("revenue", ascending=False)
           .head(500))
st.caption(f"แสดง {len(grouped):,} rows")
st.dataframe(
    grouped.style.format({"revenue": "{:,.0f}", "qty": "{:,.0f}"}),
    use_container_width=True, hide_index=True, height=400,
)

st.caption(f"📅 Period: {start_m} → {end_m}")
