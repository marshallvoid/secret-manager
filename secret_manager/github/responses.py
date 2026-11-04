from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


# JSON printed by gh, validated where it enters the program
class GhModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class GhRepo(GhModel):
    name: str
    name_with_owner: str = Field(alias="nameWithOwner")


class GhOrg(GhModel):
    login: str


class GhEnvironment(GhModel):
    name: str


class GhEnvironments(GhModel):
    environments: list[GhEnvironment] = Field(default_factory=list)


class GhEntry(GhModel):
    name: str
    updated_at: str | None = Field(default=None, alias="updatedAt")
    value: str | None = None
    visibility: str | None = None
    num_selected_repos: int | None = Field(default=None, alias="numSelectedRepos")


REPOS = TypeAdapter(list[GhRepo])
ORGS = TypeAdapter(list[GhOrg])
ENTRIES = TypeAdapter(list[GhEntry])
