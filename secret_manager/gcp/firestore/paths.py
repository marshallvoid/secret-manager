from __future__ import annotations

from .values import KeyPath


def join(*parts: str) -> str:
    return "/".join(part for part in parts if part)


def parse_path(text: str) -> list[str]:
    return [part for part in text.strip().split("/") if part]


def parent_path(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def last_segment(path: str) -> str:
    return path.rsplit("/", 1)[-1]


# A field's path as the console writes it, such as settings.colors[2]
def field_path(path: KeyPath) -> str:
    out = ""

    for part in path:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else part

    return out
