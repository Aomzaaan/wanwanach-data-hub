"""Dataset Browser — Filter + Preview + Download."""
import streamlit as st
import pandas as pd

from config import DATASETS, MAX_PREVIEW_ROWS, MAX_DOWNLOAD_ROWS
from auth import require_login, can_access, current_role
from datasets import load_dataset, apply_filters
from downloads import to_csv_bytes, to_excel_bytes, to_parquet_bytes
from usage_log import log_event


st.set_page_config(page_title="Datasets — Wanwanach", page_icon="📊", layout="wide")
require_login()

st.title("📊 Data Browser")

# ─── Dataset picker ───
accessible = {did: c for did, c in DATASETS.items() if can_access(c)}
if not accessible:
    st.warning("ยังไม่มีสิทธิ์เข้าถึง dataset")
    st.stop()

default_id = st.session_state.get("selected_dataset")
options = list(accessible.keys())
default_idx = options.index(default_id) if default_id in options else 0

dataset_id = st.selectbox(
    "เลือก Dataset:",
    options=options,
    format_func=lambda x: DATASETS[x]["name"],
    index=default_idx,
)
st.session_state["selected_dataset"] = dataset_id
conf = DATASETS[dataset_id]

st.caption(f"📝 {conf['description']}")
st.divider()

# ─── Load data ───
try:
    df = load_dataset(dataset_id)
except Exception as e:
    err_msg = str(e)
    if "NoSuchKey" in err_msg or "404" in err_msg:
        st.error(
            f"⚠️ **ยังไม่มีข้อมูลใน R2 สำหรับ dataset นี้**\n\n"
            f"ต้องรัน `daily_pipeline/push_aggregates_to_r2.ipynb` "
            f"เพื่ออัพโหลดข้อมูลก่อน\n\n"
            f"Key: `{conf['source_key']}`"
        )
    else:
        st.error(f"❌ โหลดข้อมูลไม่สำเร็จ: {e}")
    st.stop()

log_event("view_dataset", dataset_id, {"rows": len(df)})

# ─── Filter Sidebar ───
with st.sidebar:
    st.markdown("### 🎛 ตัวกรอง")
    filters = {}

    # Date range
    date_col = conf.get("date_col")
    if date_col and date_col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[date_col]):
            min_d, max_d = df[date_col].min(), df[date_col].max()
            if pd.notna(min_d) and pd.notna(max_d):
                # Default: last 12 months (or all-time if data < 12 months)
                default_start = max(min_d.date(), (max_d - pd.DateOffset(years=1)).date())
                date_range = st.date_input(
                    f"📅 {date_col}  ({min_d.date()} – {max_d.date()})",
                    value=(default_start, max_d.date()),
                    min_value=min_d.date(),
                    max_value=max_d.date(),
                )
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    filters[date_col] = date_range

    # Categorical filters
    for col in conf.get("filters", []):
        if col not in df.columns:
            continue
        vals = sorted(df[col].dropna().astype(str).unique().tolist())
        if len(vals) < 200:
            selected = st.multiselect(
                f"🔹 {col}",
                options=vals,
                default=[],
                key=f"filter_{col}",
            )
            if selected:
                filters[col] = selected
        else:
            search = st.text_input(f"🔍 {col} (search)", key=f"filter_search_{col}")
            if search:
                filters[col] = [v for v in vals if search.lower() in str(v).lower()]

    if st.button("🔄 ล้างตัวกรอง", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("filter_"):
                del st.session_state[k]
        st.rerun()

# ─── Apply filters ───
filtered = apply_filters(df, filters)

# ─── Summary metrics ───
c1, c2, c3, c4 = st.columns(4)
c1.metric("แถวทั้งหมด", f"{len(df):,}")
c2.metric("หลังกรอง", f"{len(filtered):,}", delta=f"{len(filtered)-len(df):+,}")
c3.metric("คอลัมน์", f"{len(filtered.columns)}")

# Sum if there's a numeric total column
num_cols = filtered.select_dtypes("number").columns.tolist()
if "total_price" in num_cols:
    c4.metric("ยอดรวม", f"{filtered['total_price'].sum():,.0f} ฿")
elif "amount" in num_cols:
    c4.metric("ยอดรวม", f"{filtered['amount'].sum():,.0f} ฿")
elif "total_amount" in num_cols:
    c4.metric("ยอดรวม", f"{filtered['total_amount'].sum():,.0f} ฿")

st.divider()

# ─── Preview ───
st.markdown(f"### 👀 Preview (แสดง {min(MAX_PREVIEW_ROWS, len(filtered))} จาก {len(filtered):,} แถว)")
st.dataframe(filtered.head(MAX_PREVIEW_ROWS), use_container_width=True, hide_index=True)

# ─── Download ───
st.divider()
st.markdown("### ⬇ ดาวน์โหลดข้อมูล")

if len(filtered) > MAX_DOWNLOAD_ROWS:
    st.warning(
        f"⚠️ ผลลัพธ์ {len(filtered):,} แถว เกินขีดจำกัด {MAX_DOWNLOAD_ROWS:,}\n\n"
        f"กรุณาใช้ filter เพื่อลดจำนวนก่อน download"
    )
else:
    d1, d2, d3 = st.columns(3)
    fname = f"{dataset_id}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}"

    with d1:
        st.download_button(
            "📄 CSV",
            data=to_csv_bytes(filtered),
            file_name=f"{fname}.csv",
            mime="text/csv",
            use_container_width=True,
            key="dlbtn_csv",
            on_click=lambda: log_event("download", dataset_id, {"format": "csv", "rows": len(filtered)}),
        )
    with d2:
        st.download_button(
            "📊 Excel",
            data=to_excel_bytes(filtered),
            file_name=f"{fname}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dlbtn_xlsx",
            on_click=lambda: log_event("download", dataset_id, {"format": "xlsx", "rows": len(filtered)}),
        )
    with d3:
        st.download_button(
            "📦 Parquet",
            data=to_parquet_bytes(filtered),
            file_name=f"{fname}.parquet",
            mime="application/octet-stream",
            use_container_width=True,
            key="dlbtn_pq",
            on_click=lambda: log_event("download", dataset_id, {"format": "parquet", "rows": len(filtered)}),
        )

# ─── Column info ───
with st.expander("📖 คำอธิบายคอลัมน์"):
    info_df = pd.DataFrame({
        "column": filtered.columns,
        "dtype": [str(filtered[c].dtype) for c in filtered.columns],
        "non-null": [filtered[c].notna().sum() for c in filtered.columns],
        "sample": [str(filtered[c].dropna().iloc[0])[:50] if filtered[c].notna().any() else "-" for c in filtered.columns],
    })
    st.dataframe(info_df, use_container_width=True, hide_index=True)
