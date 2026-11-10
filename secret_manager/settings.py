from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .github.models import EntryKind, Owner, RepositoryFilter


# Only paths, names and choices are stored here, never secret values
class AppSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tab: int = 0
    google_tab: int = 0
    credentials: str = ""
    database: str = ""
    databases: list[str] = Field(default_factory=list)
    firestore_path: str = ""
    github_owner: Owner | None = None
    github_kind: EntryKind = "secret"
    github_scope: str = "actions"
    github_repo_filter: RepositoryFilter = "all"
    github_repo_search: str = ""
    github_collapsed_sections: List[str] = Field(default_factory=list)
    # written by versions before organizations were supported
    repo: str = ""


def settings_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"

    return Path(base) / "secret-manager" / "settings.json"


# A missing or broken file falls back to the defaults
def load() -> AppSettings:
    try:
        text = settings_path().read_text(encoding="utf-8")
    except OSError:
        return AppSettings()

    try:
        return AppSettings.model_validate_json(text)
    except ValidationError:
        return AppSettings()


def save(settings: AppSettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(settings.model_dump_json(indent=2, exclude={"repo"}), encoding="utf-8")
    tmp.replace(path)
