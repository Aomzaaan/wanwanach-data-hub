"""Data loading + caching — connect to Cloudflare R2."""
import streamlit as st
import pandas as pd
import boto3
from io import BytesIO
from config import DATASETS, CACHE_TTL_SECONDS


def _r2_client():
    """Build boto3 client from Streamlit secrets."""
    r2 = st.secrets["r2"]
    return boto3.client(
        "s3",
        endpoint_url=r2["endpoint_url"],
        aws_access_key_id=r2["access_key_id"],
        aws_secret_access_key=r2["secret_access_key"],
        region_name=r2.get("region", "auto"),
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="⏳ กำลังดึงข้อมูล...")
def load_dataset(dataset_id: str) -> pd.DataFrame:
    """Load dataset from R2 (cached)."""
    conf = DATASETS[dataset_id]
    r2 = _r2_client()
    bucket = st.secrets["r2"]["bucket"]
    key = conf["source_key"]

    resp = r2.get_object(Bucket=bucket, Key=key)
    body = resp["Body"].read()

    if conf["source_type"] == "r2_csv":
        df = pd.read_csv(BytesIO(body), encoding="utf-8-sig")
    elif conf["source_type"] == "r2_parquet":
        df = pd.read_parquet(BytesIO(body))
    else:
        raise ValueError(f"Unsupported source_type: {conf['source_type']}")

    # Parse date column if exists
    date_col = conf.get("date_col")
    if date_col and date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

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
        return {"available": False, "error": str(e)}


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Apply user-selected filters to df."""
    for col, val in filters.items():
        if val is None or val == [] or val == "":
            continue
        if col not in df.columns:
            continue
        if isinstance(val, list):
            df = df[df[col].astype(str).isin([str(x) for x in val])]
        elif isinstance(val, tuple) and len(val) == 2:
            # Date range
            start, end = val
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df = df[(df[col] >= pd.Timestamp(start)) & (df[col] <= pd.Timestamp(end))]
        else:
            df = df[df[col].astype(str) == str(val)]
    return df
