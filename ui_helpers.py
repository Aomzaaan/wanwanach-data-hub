"""Shared UI helpers used across dashboard pages."""
import html as _html

import pandas as pd
import streamlit as st


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


def fmt_num(v, unit: str = "") -> str:
    """Format 1_234_567 → 1.23M. Safe on NaN/None/0."""
    if pd.isna(v) or v == 0:
        return "0" + unit
    for suffix, div in [("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(v) >= div:
            return f"{v/div:,.2f}{suffix}{unit}"
    return f"{v:,.0f}{unit}"


def safe_div(numerator, denominator, default=0):
    """Divide safely — avoids inf/NaN when denom is 0."""
    try:
        d = float(denominator or 0)
        if d == 0:
            return default
        return float(numerator) / d
    except Exception:
        return default


def styled_metric(label: str, value, delta=None, delta_prefix: str = ""):
    """Colored metric card — escapes label/value to prevent XSS."""
    label = _html.escape(str(label))
    value = _html.escape(str(value))
    delta_html = ""
    if delta is not None:
        color = COLORS["success"] if delta >= 0 else COLORS["danger"]
        arrow = "▲" if delta >= 0 else "▼"
        delta_html = (
            f'<div style="color:{color};font-size:14px;margin-top:4px;">'
            f'{arrow} {delta_prefix}{abs(delta):.1f}%</div>'
        )
    html = (
        f'<div style="padding:16px;background:linear-gradient(135deg,#F5F7FA 0%,#E8EAF6 100%);'
        f'border-left:4px solid {COLORS["primary"]};border-radius:8px;height:100%;">'
        f'<div style="color:{COLORS["muted"]};font-size:13px;text-transform:uppercase;letter-spacing:0.5px;">{label}</div>'
        f'<div style="color:{COLORS["primary"]};font-size:28px;font-weight:700;margin-top:4px;">{value}</div>'
        f'{delta_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
