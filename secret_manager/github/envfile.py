from __future__ import annotations


# Only the names, for the confirmation; gh reads the values from the file itself
def env_names(path: str) -> list[str]:
    names: list[str] = []

    try:
        with open(file=path, encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()

                if line.startswith("export "):
                    line = line[7:].lstrip()

                if line and not line.startswith("#") and "=" in line:
                    names.append(line.split("=", 1)[0].strip().upper())
    except (OSError, UnicodeDecodeError):
        return []

    return names
