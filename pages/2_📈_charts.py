"""Charts — quick visualization."""
import streamlit as st
import pandas as pd
import plotly.express as px

from config import DATASETS
from auth import require_login, can_access
from datasets import load_dataset, apply_filters
from usage_log import log_event


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
df = load_dataset(dataset_id)
log_event("view_chart", dataset_id)

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

# Optional filter
st.sidebar.markdown("### 🎛 กรอง")
date_col = conf.get("date_col")
if date_col and date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]):
    min_d, max_d = df[date_col].min(), df[date_col].max()
    date_range = st.sidebar.date_input(
        f"📅 {date_col}",
        value=(max_d.date().replace(day=1), max_d.date()) if pd.notna(max_d) else None,
        min_value=min_d.date() if pd.notna(min_d) else None,
        max_value=max_d.date() if pd.notna(max_d) else None,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        df = df[(df[date_col] >= pd.Timestamp(date_range[0])) & (df[date_col] <= pd.Timestamp(date_range[1]))]

top_n = st.sidebar.slider("Top N (สำหรับ Bar/Pie):", 5, 50, 15)

# ─── Aggregate ───
if x_col and y_col:
    group_cols = [x_col] + ([color_col] if color_col else [])
    grouped = df.groupby(group_cols, as_index=False)[y_col].agg(agg)

    # Top N by y_col
    if chart_type in ("Bar", "Pie"):
        top_x = grouped.groupby(x_col, as_index=False)[y_col].sum().nlargest(top_n, y_col)[x_col]
        grouped = grouped[grouped[x_col].isin(top_x)]

    # ─── Draw ───
    if chart_type == "Bar":
        fig = px.bar(grouped, x=x_col, y=y_col, color=color_col, title=f"{agg}({y_col}) by {x_col}")
    elif chart_type == "Line":
        fig = px.line(grouped, x=x_col, y=y_col, color=color_col, title=f"{y_col} over {x_col}", markers=True)
    elif chart_type == "Pie":
        pie_df = grouped.groupby(x_col, as_index=False)[y_col].sum()
        fig = px.pie(pie_df, names=x_col, values=y_col, title=f"{y_col} distribution by {x_col}")
    elif chart_type == "Scatter":
        fig = px.scatter(df, x=x_col, y=y_col, color=color_col, title=f"{y_col} vs {x_col}")

    fig.update_layout(height=550)
    st.plotly_chart(fig, use_container_width=True)

    # Show data table
    with st.expander("📋 ข้อมูลที่ใช้วาด"):
        st.dataframe(grouped, use_container_width=True, hide_index=True)
else:
    st.info("กรุณาเลือกคอลัมน์ X และ Y")
