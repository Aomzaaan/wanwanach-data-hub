"""Data loading + caching — connect to Cloudflare R2."""
from io import BytesIO

import boto3
import pandas as pd
import streamlit as st

from config import DATASETS, CACHE_TTL_SECONDS


# Columns that should stay as string (prevent 10408 → int 10408 shown as 10.4k)
_FORCE_STR_COLS = {
    "branch_code", "product_code", "year_month", "customer_category",
    "channel", "source", "route", "province", "district", "area",
}


@st.cache_resource(show_spinner=False)
def _r2_client():
    """Build boto3 client from Streamlit secrets (cached — 1 client per app)."""
    r2 = st.secrets["r2"]
    return boto3.client(
        "s3",
        endpoint_url=r2["endpoint_url"],
        aws_access_key_id=r2["access_key_id"],
        aws_secret_access_key=r2["secret_access_key"],
        region_name=r2.get("region", "auto"),
    )


def _cast_str_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in _FORCE_STR_COLS:
        if c in df.columns:
            df[c] = df[c].astype(str)
    return df


def _to_categorical(df: pd.DataFrame) -> pd.DataFrame:
    """Convert repeated string columns to categorical — saves ~70% RAM."""
    for c in ["source", "channel", "customer_category", "branch_code", "route", "area", "province"]:
        if c in df.columns and df[c].dtype == "object":
            df[c] = df[c].astype("category")
    return df


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="⏳ กำลังดึงข้อมูล...", max_entries=3)
def load_dataset(dataset_id: str, nrows: int | None = None) -> pd.DataFrame:
    """Load dataset from R2 (cached).

    Args:
        dataset_id: dataset key
        nrows: ถ้าระบุ = อ่านแค่ N แถวแรก (Sample mode) — เร็ว + ประหยัด RAM
    """
    conf = DATASETS[dataset_id]
    r2 = _r2_client()
    bucket = st.secrets["r2"]["bucket"]
    key = conf["source_key"]

    resp = r2.get_object(Bucket=bucket, Key=key)
    force_str_dtype = {c: str for c in _FORCE_STR_COLS}

    if conf["source_type"] == "r2_csv":
        # ⭐ Stream directly from R2 (don't read full into RAM first)
        df = pd.read_csv(
            resp["Body"], encoding="utf-8-sig", dtype=force_str_dtype, nrows=nrows,
        )
    elif conf["source_type"] == "r2_parquet":
        body = resp["Body"].read()
        df = pd.read_parquet(BytesIO(body))
        if nrows:
            df = df.head(nrows)
        df = _cast_str_cols(df)
    else:
        raise ValueError(f"Unsupported source_type: {conf['source_type']}")

    # Parse date column if exists — handle mixed formats
    date_col = conf.get("date_col")
    if date_col and date_col in df.columns:
        try:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce", format="mixed")
        except (ValueError, TypeError):
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    # ⭐ Convert to categorical BEFORE caching → saves ~70% RAM in cache
    df = _to_categorical(df)
    return df


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def dataset_metadata(dataset_id: str) -> dict:
    """Get metadata (size, last update, row count) — light call."""
    conf = DATASETS[dataset_id]
    r2 = _r2_client()
    bucket = st.secrets["r2"]["bucket"]
    key = conf["source_key"]
    try:
        head = r2.head_object(Bucket=bucket, Key=key)
        return {
            "size_mb": head["ContentLength"] / (1024 * 1024),
            "last_modified": head["LastModified"],
            "available": True,
        }
    except Exception as e:
        return {"available": False, "error": type(e).__name__}  # don't leak stack


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply user-selected filters to df. Returns filtered COPY (never mutates input)."""
    result = df
    for col, val in filters.items():
        if val is None or val == [] or val == "":
            continue
        if col not in result.columns:
            continue
        if isinstance(val, list):
            result = result[result[col].astype(str).isin([str(x) for x in val])]
        elif isinstance(val, tuple) and len(val) == 2:
            start, end = val
            if pd.api.types.is_datetime64_any_dtype(result[col]):
                result = result[(result[col] >= pd.Timestamp(start)) & (result[col] <= pd.Timestamp(end))]
        else:
            result = result[result[col].astype(str) == str(val)]
    return result.copy() if result is df else result
