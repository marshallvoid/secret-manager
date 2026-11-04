from __future__ import annotations

import base64
import datetime
import json
import math
import re
from typing import Any

from google.cloud.firestore import Client, GeoPoint
from google.cloud.firestore_v1.document import DocumentReference

# A field's place in a document: map keys and array indexes, from the top-level field down
KeyPath = list[str | int]

# The types the Firebase console lets you pick, in its order
TYPES: list[str] = [
    "string",
    "number",
    "boolean",
    "map",
    "array",
    "null",
    "timestamp",
    "geopoint",
    "reference",
]
CONTAINERS: tuple[str, ...] = ("map", "array")
INT_RE = re.compile(pattern=r"[+-]?\d+")


# A reference typed by the user, resolved to a DocumentReference just before writing
class RefPath(str):
    pass


def type_of(value: Any) -> str:
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, (int, float)):
        return "number"

    if isinstance(value, str) and not isinstance(value, RefPath):
        return "string"

    if isinstance(value, dict):
        return "map"

    if isinstance(value, list):
        return "array"

    if isinstance(value, datetime.datetime):
        return "timestamp"

    if isinstance(value, GeoPoint):
        return "geopoint"

    if isinstance(value, (DocumentReference, RefPath)):
        return "reference"

    if isinstance(value, bytes):
        return "bytes"

    return type(value).__name__


def default_for(kind: str) -> Any:
    now = datetime.datetime.now(tz=datetime.timezone.utc).replace(microsecond=0)
    defaults: dict[str, Any] = {
        "string": "",
        "number": 0,
        "boolean": True,
        "map": {},
        "array": [],
        "null": None,
        "timestamp": now,
        "geopoint": GeoPoint(latitude=0.0, longitude=0.0),
        "reference": RefPath(""),
    }

    return defaults[kind]


def parse_number(text: str) -> int | float:
    text = text.strip()

    if INT_RE.fullmatch(text):
        return int(text)

    number = float(text)

    if not math.isfinite(number):
        raise ValueError("NaN and Infinity are not supported here")

    return number


def format_number(value: float) -> str:
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e16:
        return str(int(value))

    return repr(value)


# The console's format: "November 3, 2026 at 9:16:00 PM UTC+7"
def format_time(value: datetime.datetime) -> str:
    local = value.astimezone()
    offset = local.utcoffset() or datetime.timedelta()
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, rest = divmod(abs(minutes), 60)
    zone = f"UTC{sign}{hours}" + (f":{rest:02d}" if rest else "")
    hour = local.hour % 12 or 12
    half = "AM" if local.hour < 12 else "PM"
    clock = f"{hour}:{local.minute:02d}:{local.second:02d} {half}"

    return f"{local.strftime('%B')} {local.day}, {local.year} at {clock} {zone}"


def format_geopoint(point: GeoPoint) -> str:
    lat = f"{abs(point.latitude)}° {'N' if point.latitude >= 0 else 'S'}"
    lng = f"{abs(point.longitude)}° {'E' if point.longitude >= 0 else 'W'}"

    return f"[{lat}, {lng}]"


def ref_path(value: DocumentReference | str) -> str:
    path = value.path if isinstance(value, DocumentReference) else str(value).strip("/")

    return "/" + path


def preview(value: Any, limit: int = 80) -> str:
    kind = type_of(value=value)

    if kind == "string":
        text = json.dumps(obj=value, ensure_ascii=False)
    elif kind == "number":
        text = format_number(value=value)
    elif kind == "boolean":
        text = "true" if value else "false"
    elif kind == "null":
        text = "null"
    elif kind == "timestamp":
        text = format_time(value=value)
    elif kind == "geopoint":
        text = format_geopoint(point=value)
    elif kind == "reference":
        text = ref_path(value=value)
    elif kind == "bytes":
        text = base64.b64encode(value).decode("ascii")
    elif kind == "array":
        text = "[" + ", ".join(preview(value=item, limit=limit) for item in value) + "]"
    elif kind == "map":
        pairs = (
            f"{key}: {preview(value=item, limit=limit)}" for key, item in value.items()
        )
        text = "{" + ", ".join(pairs) + "}"
    else:
        text = str(value)

    if len(text) > limit:
        text = text[: limit - 3] + "..."

    return text


# JSON for copying a value; types JSON lacks are written as the console shows them
def to_json(value: Any) -> Any:
    kind = type_of(value=value)

    if kind == "map":
        return {key: to_json(value=item) for key, item in value.items()}

    if kind == "array":
        return [to_json(value=item) for item in value]

    if kind in ("string", "number", "boolean", "null"):
        return value

    if kind == "timestamp":
        return value.isoformat()

    return preview(value=value, limit=10**6)


def plain(value: Any) -> str:
    if isinstance(value, str):
        return value

    return json.dumps(obj=to_json(value=value), ensure_ascii=False, indent=2)


# Copies containers only; leaves such as DocumentReference hold a client and must not be copied
def copy_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: copy_value(value=item) for key, item in value.items()}

    if isinstance(value, list):
        return [copy_value(value=item) for item in value]

    return value


def get_at(data: Any, path: KeyPath) -> Any:
    for key in path:
        data = data[key]

    return data


def with_set(top: Any, path: KeyPath, value: Any) -> Any:
    if not path:
        return value

    top = copy_value(value=top)
    parent = get_at(data=top, path=path[:-1])

    if isinstance(parent, list) and path[-1] == len(parent):
        parent.append(value)
    else:
        parent[path[-1]] = value

    return top


def with_renamed(top: Any, path: KeyPath, new_key: str, value: Any) -> Any:
    top = copy_value(value=top)
    parent = get_at(data=top, path=path[:-1])

    if isinstance(parent, dict):
        # keep the field in the same place
        old_key = path[-1]
        items = [
            (new_key if key == old_key else key, value if key == old_key else item)
            for key, item in parent.items()
        ]
        parent.clear()
        parent.update(items)
    else:
        parent[path[-1]] = value

    return top


def with_deleted(top: Any, path: KeyPath) -> Any:
    top = copy_value(value=top)
    parent = get_at(data=top, path=path[:-1])
    del parent[path[-1]]

    return top


def resolve(value: Any, client: Client) -> Any:
    if isinstance(value, RefPath):
        path = value.strip("/")

        if not path or path.count("/") % 2 == 0:
            raise ValueError(f"'{value}' is not a document path")

        return client.document(path)

    if isinstance(value, dict):
        return {key: resolve(value=item, client=client) for key, item in value.items()}

    if isinstance(value, list):
        return [resolve(value=item, client=client) for item in value]

    return value
