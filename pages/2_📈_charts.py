"""Charts — quick visualization."""
import streamlit as st
import pandas as pd
import plotly.express as px

from config import DATASETS
from auth import require_login, can_access
from datasets import load_dataset, apply_filters, dataset_metadata
from usage_log import log_event


SAMPLE_ROWS = 100_000
SIZE_WARN_MB = 20
SIZE_HARD_MB = 100


st.set_page_config(page_title="Charts — Wanwanach", page_icon="📈", layout="wide")
require_login()

st.title("📈 Charts & Visualization")

accessible = {did: c for did, c in DATASETS.items() if can_access(c)}
if not accessible:
    st.warning("ไม่มี dataset ที่เข้าถึงได้")
    st.stop()

default_id = st.session_state.get("selected_dataset")
options = list(accessible.keys())
default_idx = options.index(default_id) if default_id in options else 0

dataset_id = st.selectbox(
    "Dataset:",
    options=options,
    format_func=lambda x: DATASETS[x]["name"],
    index=default_idx,
)
conf = DATASETS[dataset_id]

# ⭐ Pre-flight size check + mode selector (avoid OOM on big datasets)
meta = dataset_metadata(dataset_id)
size_mb = meta.get("size_mb", 0) if meta.get("available") else 0

if size_mb > SIZE_HARD_MB:
    default_mode = 0  # Sample
elif size_mb > SIZE_WARN_MB:
    default_mode = 0
else:
    default_mode = 1  # Full

load_mode = st.radio(
    "🎯 โหมด: (ไฟล์ {:.0f} MB)".format(size_mb),
    ["🌱 Sample ({:,} แถว)".format(SAMPLE_ROWS), "🌍 Full"],
    index=default_mode,
    horizontal=True,
)
_use_sample = "Sample" in load_mode

try:
    df = load_dataset(dataset_id, nrows=SAMPLE_ROWS if _use_sample else None)
except Exception as e:
    if "NoSuchKey" in str(e) or "404" in str(e):
        st.error(f"⚠️ ยังไม่มีข้อมูลใน R2 — รัน `push_aggregates_to_r2.ipynb` ก่อน")
    else:
        st.error(f"❌ โหลดไม่สำเร็จ — โปรดลองใหม่")
    st.stop()
log_event("view_chart", dataset_id, {"mode": "sample" if _use_sample else "full"})
if _use_sample:
    st.info(f"🌱 Sample mode: แสดงข้อมูล {SAMPLE_ROWS:,} แถวแรก")

# ─── Chart config ───
st.sidebar.markdown("### 🎨 กำหนดกราฟ")
chart_type = st.sidebar.radio(
    "ประเภท:",
    ["Bar", "Line", "Pie", "Scatter"],
)

num_cols = df.select_dtypes("number").columns.tolist()
cat_cols = df.select_dtypes(exclude="number").columns.tolist()

x_col = st.sidebar.selectbox("แกน X:", cat_cols + num_cols)
y_col = st.sidebar.selectbox("แกน Y (ค่า):", num_cols)
color_col = st.sidebar.selectbox("แยกสีตาม:", [None] + cat_cols)
agg = st.sidebar.selectbox("Aggregation:", ["sum", "mean", "count", "max", "min"])

show_labels = st.sidebar.checkbox("แสดงตัวเลขบนกราฟ", value=True)
label_format = st.sidebar.selectbox(
    "รูปแบบตัวเลข:",
    ["auto (K/M/B)", "จำนวนเต็ม", "ทศนิยม 2 ตำแหน่ง"],
    index=0,
)

# ⭐ ช่วยเห็นค่าเล็ก (Booth, Online) ที่โดนกลบด้วยค่าใหญ่
scale_mode = st.sidebar.selectbox(
    "แสดงผลแบบ:",
    ["ปกติ (linear)", "100% Stacked (สัดส่วน)", "Log scale"],
    index=0,
    help="ค่าเล็กๆ (เช่น Booth) จะเห็นชัดขึ้นถ้าใช้ % หรือ Log",
)

# Optional filter
st.sidebar.markdown("### 🎛 กรอง")
date_col = conf.get("date_col")
if date_col and date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]):
    min_d, max_d = df[date_col].min(), df[date_col].max()
    if pd.notna(min_d) and pd.notna(max_d):
        default_start = max(min_d.date(), (max_d - pd.DateOffset(years=1)).date())
        date_range = st.sidebar.date_input(
            f"📅 {date_col}",
            value=(default_start, max_d.date()),
            min_value=min_d.date(),
            max_value=max_d.date(),
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            df = df[(df[date_col] >= pd.Timestamp(date_range[0])) & (df[date_col] <= pd.Timestamp(date_range[1]))]

top_n = st.sidebar.slider(
    "Top N (สำหรับ Bar/Pie):",
    5, 100, 30,
    help="กรอง top N ของแกน X — ถ้ามาก อาจตัด category เล็กๆ ทิ้ง",
)
show_all_x = st.sidebar.checkbox(
    "แสดง X ทั้งหมด (ไม่ใช้ Top N)",
    value=False,
    help="สำคัญเมื่อ X เป็น date หรือ month — แสดงทุกวัน/เดือน",
)


def _format_num(v):
    if pd.isna(v):
        return ""
    if label_format == "จำนวนเต็ม":
        return f"{v:,.0f}"
    if label_format == "ทศนิยม 2 ตำแหน่ง":
        return f"{v:,.2f}"
    # auto K/M/B
    for suffix, div in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(v) >= div:
            return f"{v/div:.1f}{suffix}"
    return f"{v:.0f}"


# ─── Aggregate ───
if x_col and y_col:
    group_cols = [x_col] + ([color_col] if color_col else [])
    grouped = df.groupby(group_cols, as_index=False)[y_col].agg(agg)

    # Top N by y_col (skip if user wants all X, e.g. for time-series with color)
    if chart_type in ("Bar", "Pie") and not show_all_x:
        top_x = grouped.groupby(x_col, as_index=False)[y_col].sum().nlargest(top_n, y_col)[x_col]
        grouped = grouped[grouped[x_col].isin(top_x)]

    # Prepare label text
    text_col = None
    if show_labels:
        grouped = grouped.copy()
        grouped["_label"] = grouped[y_col].apply(_format_num)
        text_col = "_label"

    # ─── Draw ───
    if chart_type == "Bar":
        # 100% Stacked → normalize each x-group to sum to 100%
        if scale_mode == "100% Stacked (สัดส่วน)" and color_col:
            grouped["_total"] = grouped.groupby(x_col)[y_col].transform("sum")
            grouped["_pct"] = grouped[y_col] / grouped["_total"] * 100
            grouped["_label"] = grouped["_pct"].apply(lambda v: f"{v:.1f}%")
            fig = px.bar(
                grouped, x=x_col, y="_pct", color=color_col,
                text="_label" if show_labels else None,
                title=f"{y_col} distribution (% by {x_col})",
                labels={"_pct": "% of total"},
            )
            fig.update_layout(barmode="stack", yaxis_ticksuffix="%", yaxis_range=[0, 100])
            if show_labels:
                fig.update_traces(textposition="inside", textfont_size=10)
        else:
            fig = px.bar(
                grouped, x=x_col, y=y_col, color=color_col,
                text=text_col,
                title=f"{agg}({y_col}) by {x_col}",
                barmode="group",
            )
            if show_labels:
                fig.update_traces(textposition="outside", textfont_size=11)
    elif chart_type == "Line":
        fig = px.line(
            grouped, x=x_col, y=y_col, color=color_col,
            text=text_col,
            title=f"{y_col} over {x_col}",
            markers=True,
        )
        if show_labels:
            fig.update_traces(textposition="top center", textfont_size=10)
    elif chart_type == "Pie":
        pie_df = grouped.groupby(x_col, as_index=False)[y_col].sum()
        fig = px.pie(pie_df, names=x_col, values=y_col, title=f"{y_col} distribution by {x_col}")
        if show_labels:
            fig.update_traces(textposition="inside", textinfo="percent+label+value")
        else:
            fig.update_traces(textinfo="percent+label")
    elif chart_type == "Scatter":
        fig = px.scatter(df, x=x_col, y=y_col, color=color_col, title=f"{y_col} vs {x_col}")

    # Better layout — grid, hover, height
    fig.update_layout(
        height=600,
        hovermode="x unified" if chart_type in ("Line", "Bar") else "closest",
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        margin=dict(l=40, r=140, t=60, b=80),
        yaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
        xaxis=dict(showgrid=False),
    )
    if scale_mode != "100% Stacked (สัดส่วน)":
        fig.update_yaxes(tickformat=",.0f")

    # Log scale
    if scale_mode == "Log scale":
        fig.update_yaxes(type="log")

    st.plotly_chart(fig, use_container_width=True)

    # Show data table
    with st.expander("📋 ข้อมูลที่ใช้วาด"):
        show_df = grouped.drop(columns=["_label"], errors="ignore")
        st.dataframe(show_df, use_container_width=True, hide_index=True)
else:
    st.info("กรุณาเลือกคอลัมน์ X และ Y")
