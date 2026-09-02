"""Dataset Browser — Filter (right panel) + Preview + Smart loading."""
import streamlit as st
import pandas as pd

from config import DATASETS, MAX_PREVIEW_ROWS, MAX_DOWNLOAD_ROWS
from auth import require_login, can_access, current_role
from datasets import load_dataset, apply_filters, dataset_metadata
from downloads import to_csv_bytes, to_excel_bytes, to_parquet_bytes
from usage_log import log_event
from time_utils import th_str


st.set_page_config(page_title="Datasets — Wanwanach", page_icon="📊", layout="wide")
require_login()

# ─── Constants ──────────────────────────────────────────
SIZE_WARN_MB = 20          # เตือนถ้าไฟล์ > 20 MB
SIZE_HARD_MB = 100         # บล็อคถ้าไฟล์ > 100 MB (ต้องเลือกโหมด sample)
SAMPLE_ROWS = 100_000      # Sample mode: อ่านแค่ N แถวแรก
RECENT_MONTHS_DEFAULT = 12 # Recent mode: 12 เดือนล่าสุด


st.title("📊 Data Browser")

# ─── Dataset picker ───
accessible = {did: c for did, c in DATASETS.items() if can_access(c)}
if not accessible:
    st.warning("ยังไม่มีสิทธิ์เข้าถึง dataset")
    st.stop()

default_id = st.session_state.get("selected_dataset")
options = list(accessible.keys())
default_idx = options.index(default_id) if default_id in options else 0

top_l, top_r = st.columns([2, 1])
with top_l:
    dataset_id = st.selectbox(
        "เลือก Dataset:",
        options=options,
        format_func=lambda x: DATASETS[x]["name"],
        index=default_idx,
    )
st.session_state["selected_dataset"] = dataset_id
conf = DATASETS[dataset_id]

# ─── Pre-flight: ตรวจขนาดไฟล์ก่อนโหลด ───
meta = dataset_metadata(dataset_id)
size_mb = meta.get("size_mb", 0) if meta.get("available") else 0
last_mod = meta.get("last_modified")

with top_r:
    if meta.get("available"):
        st.metric(
            "📦 ขนาดไฟล์",
            f"{size_mb:,.1f} MB",
            help=f"Last update: {th_str(last_mod) if last_mod else '-'}",
        )
    else:
        st.error("❌ ไม่พบไฟล์")
        st.stop()

st.caption(f"📝 {conf['description']}")

# ─── Load Mode selector (สำคัญ: ใช้ก่อนโหลด) ───
mode_options = ["🌱 Sample (100K แถวแรก)", "📅 Recent (12 เดือนล่าสุด)", "🌍 Full (ทั้งหมด)"]

# Default mode ตามขนาดไฟล์
if size_mb > SIZE_HARD_MB:
    default_mode_idx = 0  # Force Sample
    st.error(
        f"⚠️ ไฟล์นี้ใหญ่มาก **{size_mb:.0f} MB** — โหลดทั้งหมดอาจทำให้ browser ค้าง\n\n"
        f"แนะนำโหมด **Sample** หรือ **Recent** เพื่อประสบการณ์ที่ดี"
    )
elif size_mb > SIZE_WARN_MB:
    default_mode_idx = 1  # Recent
    st.warning(
        f"⚠️ ไฟล์นี้ **{size_mb:.0f} MB** — โหลดทั้งหมดอาจช้า (5-15 วิ)\n\n"
        f"💡 แนะนำโหมด **Recent** เพื่อโหลดเฉพาะช่วงที่คุณอาจต้องดู"
    )
else:
    default_mode_idx = 2  # Full — ไฟล์เล็ก โหลดหมดเลย

load_mode = st.radio(
    "🎯 โหมดการโหลด:",
    options=mode_options,
    index=default_mode_idx,
    horizontal=True,
    help=(
        "**Sample** — อ่านแค่ 100K แถวแรก (เร็วมาก, ใช้ทดลอง filter)\n\n"
        "**Recent** — เฉพาะ 12 เดือนล่าสุด (เหมาะกับ dashboard วิเคราะห์)\n\n"
        "**Full** — ทั้งหมดตั้งแต่ 2022 (ใช้เมื่อต้องการ export หรือดูย้อนหลัง)"
    ),
)

mode_key = "sample" if "Sample" in load_mode else ("recent" if "Recent" in load_mode else "full")

st.divider()

# ─── Load data ───
try:
    if mode_key == "sample":
        df = load_dataset(dataset_id, nrows=SAMPLE_ROWS)
        st.info(f"🌱 Sample mode: โหลด {SAMPLE_ROWS:,} แถวแรก (ไม่ใช่ข้อมูลทั้งหมด)")
    elif mode_key == "recent":
        df_all = load_dataset(dataset_id)
        date_col = conf.get("date_col")
        if date_col and date_col in df_all.columns and pd.api.types.is_datetime64_any_dtype(df_all[date_col]):
            # 12 FULL calendar months (ตรงกับหน้า Dashboard/Products/Locations)
            # ถ้า max = 2026-09-15 → start = 2025-10-01 (ต้นเดือน) → 12 เดือนเต็ม
            max_d = df_all[date_col].max()
            max_month_start = pd.Timestamp(max_d.year, max_d.month, 1)
            cutoff = max_month_start - pd.DateOffset(months=RECENT_MONTHS_DEFAULT - 1)
            df = df_all[df_all[date_col] >= cutoff].copy()
            n_months = (max_d.year - cutoff.year) * 12 + (max_d.month - cutoff.month) + 1
            st.info(f"📅 Recent mode: {n_months} เต็มเดือน ({cutoff.date()} → {df[date_col].max().date()}) — ตรงกับ Dashboard")
        else:
            df = df_all
    else:  # full
        df = load_dataset(dataset_id)
except Exception as e:
    err_type = type(e).__name__
    if "NoSuchKey" in str(e) or "404" in str(e):
        st.error(
            "⚠️ **ยังไม่มีข้อมูลใน R2 สำหรับ dataset นี้**\n\n"
            "กรุณาติดต่อผู้ดูแลระบบเพื่ออัพโหลดข้อมูล"
        )
    else:
        st.error(f"❌ โหลดข้อมูลไม่สำเร็จ ({err_type}) — โปรดลองใหม่ในภายหลัง")
    st.stop()

log_event("view_dataset", dataset_id, {"rows": len(df), "mode": mode_key})


# ═══════════════════════════════════════════════════════════
# Layout: [Main 3fr] | [Filter 1fr]  ← ตัวกรองอยู่ทางขวา
# ═══════════════════════════════════════════════════════════
main_col, filter_col = st.columns([3, 1], gap="large")

# ─── Filter (RIGHT panel) ───
with filter_col:
    st.markdown("### 🎛 ตัวกรอง")
    filters = {}

    # Date range
    date_col = conf.get("date_col")
    if date_col and date_col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[date_col]):
            min_d, max_d = df[date_col].min(), df[date_col].max()
            if pd.notna(min_d) and pd.notna(max_d):
                default_start = max(min_d.date(), (max_d - pd.DateOffset(years=1)).date())
                date_range = st.date_input(
                    f"📅 {date_col}",
                    value=(default_start, max_d.date()),
                    min_value=min_d.date(),
                    max_value=max_d.date(),
                    help=f"ช่วงข้อมูล: {min_d.date()} – {max_d.date()}",
                )
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    filters[date_col] = date_range
                elif isinstance(date_range, tuple) and len(date_range) == 1:
                    st.info("ℹ️ กรุณาเลือกวันสิ้นสุดด้วย")

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

# ─── Main (LEFT panel) ───
with main_col:
    # Apply filters
    filtered = apply_filters(df, filters)

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("แถวทั้งหมด", f"{len(df):,}")
    c2.metric("หลังกรอง", f"{len(filtered):,}", delta=f"{len(filtered)-len(df):+,}")
    c3.metric("คอลัมน์", f"{len(filtered.columns)}")

    num_cols = filtered.select_dtypes("number").columns.tolist()
    if "revenue" in num_cols:
        c4.metric("💰 Revenue", f"{filtered['revenue'].sum():,.0f} ฿")
    elif "total_price" in num_cols:
        c4.metric("💰 ยอดรวม", f"{filtered['total_price'].sum():,.0f} ฿")
    elif "amount" in num_cols:
        c4.metric("💰 ยอดรวม", f"{filtered['amount'].sum():,.0f} ฿")

    st.divider()

    # Preview
    st.markdown(f"### 👀 Preview (แสดง {min(MAX_PREVIEW_ROWS, len(filtered))} จาก {len(filtered):,} แถว)")
    st.dataframe(filtered.head(MAX_PREVIEW_ROWS), use_container_width=True, hide_index=True)

    # Download
    st.divider()
    st.markdown("### ⬇ ดาวน์โหลดข้อมูล")

    if len(filtered) > MAX_DOWNLOAD_ROWS:
        st.warning(
            f"⚠️ ผลลัพธ์ **{len(filtered):,}** แถว เกินขีดจำกัด {MAX_DOWNLOAD_ROWS:,}\n\n"
            f"💡 แนะนำ: **ใช้ filter เพื่อลดจำนวน** หรือ **แบ่งดาวน์โหลดเป็นช่วงเวลา** (เช่นทีละไตรมาส)"
        )
        # Chunked download by date
        if date_col and date_col in filtered.columns and pd.api.types.is_datetime64_any_dtype(filtered[date_col]):
            st.markdown("**📦 แบ่งดาวน์โหลดตามไตรมาส:**")
            filtered["_q"] = filtered[date_col].dt.to_period("Q").astype(str)
            quarters = sorted(filtered["_q"].unique())
            n_cols = min(4, len(quarters))
            for i, q in enumerate(quarters):
                col = st.columns(n_cols)[i % n_cols]
                chunk = filtered[filtered["_q"] == q].drop(columns=["_q"])
                col.download_button(
                    f"📄 {q} ({len(chunk):,})",
                    data=to_csv_bytes(chunk),
                    file_name=f"{dataset_id}_{q}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"dlq_{q}",
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

    # Column info
    with st.expander("📖 คำอธิบายคอลัมน์"):
        info_df = pd.DataFrame({
            "column": filtered.columns,
            "dtype": [str(filtered[c].dtype) for c in filtered.columns],
            "non-null": [filtered[c].notna().sum() for c in filtered.columns],
            "sample": [str(filtered[c].dropna().iloc[0])[:50] if filtered[c].notna().any() else "-" for c in filtered.columns],
        })
        st.dataframe(info_df, use_container_width=True, hide_index=True)
