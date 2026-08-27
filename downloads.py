"""Download helpers — CSV / Excel / Parquet with formula-injection guard."""
from io import BytesIO

import pandas as pd

# Cells starting with these characters can execute in Excel/Numbers/LibreOffice
_INJECTION_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _sanitize_series(s: pd.Series) -> pd.Series:
    """Prefix leading '=', '+', '-', '@', tab, CR with a single quote to defang."""
    if s.dtype == "object":
        mask = s.astype(str).str.startswith(_INJECTION_CHARS)
        if mask.any():
            s = s.copy()
            s.loc[mask] = "'" + s.loc[mask].astype(str)
    return s


def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return copy of df with all string columns sanitized against formula injection."""
    out = df.copy()
    for c in out.columns:
        out[c] = _sanitize_series(out[c])
    return out


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    df = _sanitize_df(df)
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def to_excel_bytes(df: pd.DataFrame, sheet: str = "Data") -> bytes:
    df = _sanitize_df(df)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name=sheet[:31], index=False)
    return buf.getvalue()


def to_parquet_bytes(df: pd.DataFrame) -> bytes:
    # Parquet is binary — no injection risk, skip sanitize
    buf = BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()
