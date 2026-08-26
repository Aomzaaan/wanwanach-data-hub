"""Thailand timezone helpers (Streamlit Cloud runs UTC by default)."""
from datetime import datetime, timezone, timedelta

TH_TZ = timezone(timedelta(hours=7), name="ICT")  # Indochina Time


def th_now() -> datetime:
    """Current time in Bangkok."""
    return datetime.now(TH_TZ)


def to_th(dt) -> datetime:
    """Convert any datetime (naive assumed UTC, or aware) to Bangkok time."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TH_TZ)


def th_str(dt=None, fmt="%Y-%m-%d %H:%M") -> str:
    """Format datetime as Bangkok time string. If dt is None, use now."""
    if dt is None:
        return th_now().strftime(fmt)
    return to_th(dt).strftime(fmt)
