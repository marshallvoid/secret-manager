from __future__ import annotations

import datetime

UNITS: tuple[tuple[int, str], ...] = (
    (31536000, "year"),
    (2592000, "month"),
    (86400, "day"),
    (3600, "hour"),
    (60, "minute"),
)


# Accepts an ISO 8601 string or a datetime; naive datetimes are taken as UTC
def parse_time(value: str | datetime.datetime | None) -> datetime.datetime | None:
    if value is None or value == "":
        return None

    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)

    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def relative_time(
    value: str | datetime.datetime | None, prefix: str = "Updated"
) -> str:
    when = parse_time(value=value)

    if when is None:
        return ""

    seconds = (datetime.datetime.now(tz=datetime.timezone.utc) - when).total_seconds()

    for size, unit in UNITS:
        if seconds >= size:
            count = int(seconds // size)

            return f"{prefix} {count} {unit}{'s' if count > 1 else ''} ago"

    return f"{prefix} just now"


def exact_time(value: str | datetime.datetime | None) -> str:
    when = parse_time(value=value)

    return when.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z") if when else ""
