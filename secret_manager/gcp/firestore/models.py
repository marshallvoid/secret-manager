from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from . import values

NodeKind = Literal["root", "collection", "document"]


# One panel of the browser: the database, a collection or a document
class NodeKey(BaseModel, frozen=True):
    model_config = ConfigDict(frozen=True)

    kind: NodeKind
    path: str


class Query(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: str = ""
    op: str = "=="
    value: Any = None
    order: str = ""
    descending: bool = False

    @property
    def active(self) -> bool:
        return bool(self.field or self.order)

    def describe(self) -> str:
        parts: list[str] = []

        if self.field:
            parts.append(f"{self.field} {self.op} {values.preview(value=self.value, limit=30)}")

        if self.order:
            parts.append(f"order by {self.order} {'desc' if self.descending else 'asc'}")

        return ", ".join(parts)


class Snapshot(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    exists: bool = False
    data: dict[str, Any] = Field(default_factory=dict)
    subcollections: list[str] = Field(default_factory=list)


class FieldResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # None for an array item, which has no name
    name: str | None
    value: Any


class DocumentResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    collection: str
    doc_id: str
    data: dict[str, Any] = Field(default_factory=dict)
