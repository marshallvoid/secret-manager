from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OwnerKind = Literal["repo", "org", "user"]
EntryKind = Literal["secret", "variable"]
RepositoryFilter = Literal["all", "with", "without", "unknown"]
AppName = Literal["actions", "dependabot", "codespaces"]
Visibility = Literal["all", "private", "selected"]

APP_LABELS: dict[str, str] = {
    "actions": "Actions",
    "dependabot": "Dependabot",
    "codespaces": "Codespaces",
}
VISIBILITY_LABELS: dict[str, str] = {
    "all": "All repositories",
    "private": "Private and internal repositories",
    "selected": "Selected repositories",
}


class Frozen(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True)


class Repo(Frozen, frozen=True):
    name: str
    full_name: str


class Owner(Frozen, frozen=True):
    kind: OwnerKind
    # owner/repo for a repository, the login for an organization, "" for the user
    name: str
    label: str


class Scope(Frozen, frozen=True):
    key: str
    label: str


class Target(Frozen, frozen=True):
    owner: OwnerKind
    name: str
    kind: EntryKind = "secret"
    app: AppName = "actions"
    environment: str = ""

    # Org and user entries choose which repositories can read them
    @property
    def shared(self) -> bool:
        return self.owner in ("org", "user")

    def args(self) -> list[str]:
        if self.owner == "repo":
            args = ["--repo", self.name]
        elif self.owner == "org":
            args = ["--org", self.name]
        else:
            args = ["--user"]

        if self.environment:
            args += ["--env", self.environment]
        elif self.kind == "secret" and self.owner != "user" and self.app != "actions":
            args += ["--app", self.app]

        return args

    def label(self) -> str:
        kind = "secrets" if self.kind == "secret" else "variables"

        if self.owner == "user":
            return f"Codespaces {kind}"

        where = self.name.split("/")[-1]

        if self.environment:
            return f"{where} · environment {self.environment} {kind}"

        return f"{where} · {APP_LABELS[self.app]} {kind}"


class Entry(Frozen, frozen=True):
    name: str
    updated: str = ""
    # only variables have a readable value
    value: str | None = None
    visibility: str = ""
    selected_count: int = 0

    def access_text(self) -> str:
        selected = self.visibility == "selected" or (not self.visibility and self.selected_count)

        if selected:
            count = self.selected_count

            return f"{count} repositor{'y' if count == 1 else 'ies'}"

        return VISIBILITY_LABELS.get(self.visibility, "")


class Access(BaseModel):
    visibility: Visibility = "private"
    repos: list[str] = Field(default_factory=list)

    def args(self, owner: OwnerKind) -> list[str]:
        if owner == "user":
            return ["--repos", ",".join(self.repos)] if self.repos else []

        if self.visibility != "selected":
            return ["--visibility", self.visibility]

        return ["--visibility", "selected", "--repos", ",".join(self.repos)]


class EntryResult(BaseModel):
    name: str
    value: str
    access: Access | None = None
