from __future__ import annotations

import re


# Turns any key into an environment-variable style name, such as "api-key" → "API_KEY"
def env_name(text: str, fallback: str = "SECRET") -> str:
    name = re.sub(pattern=r"[^A-Za-z0-9_]", repl="_", string=text).upper()

    return name.lstrip("0123456789") or fallback
