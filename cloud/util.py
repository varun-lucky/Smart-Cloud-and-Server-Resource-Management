from datetime import datetime, timezone


def now() -> str:
    """Return UTC timestamp in a MySQL-friendly, timezone-naive format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
