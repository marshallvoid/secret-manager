from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from subprocess import TimeoutExpired
from typing import List, Optional

from pydantic import BaseModel

from . import cli
from .models import Target


class RepoSecretStatus(BaseModel):
    name: str
    count: Optional[int] = None
    error: str = ""


def inspect_repository(name: str) -> RepoSecretStatus:
    """Read repository Actions secret metadata, never secret values."""
    try:
        entries = cli.list_entries(target=Target(owner="repo", name=name, kind="secret"))

        return RepoSecretStatus(name=name, count=len(entries))
    except (cli.GhError, TimeoutExpired, OSError) as exc:
        return RepoSecretStatus(name=name, error=str(exc))


def inspect_repositories(names: List[str]) -> List[RepoSecretStatus]:
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(inspect_repository, names)

        return list(results)
