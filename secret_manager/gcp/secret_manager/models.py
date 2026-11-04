from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VersionAction = Literal["enable", "disable", "destroy"]


class SecretInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    created: datetime.datetime | None = None
    replication: str = "Automatic"
    labels: dict[str, str] = Field(default_factory=dict)


class VersionInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: str
    state: str
    created: datetime.datetime | None = None


class NewSecret(BaseModel):
    secret_id: str
    value: str = ""
    labels: dict[str, str] = Field(default_factory=dict)
