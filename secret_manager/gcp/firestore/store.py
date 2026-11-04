from __future__ import annotations

import secrets
import string
from typing import Any

from google.api_core import exceptions as google_errors
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.field_path import FieldPath
from pydantic import BaseModel, ConfigDict

from ..credentials import GoogleAccount
from . import values
from .models import Query, Snapshot

AUTO_ID_CHARS = string.ascii_letters + string.digits
# marks a field to delete in update_fields
DELETE = object()

# Console labels → client operators
OPERATORS: dict[str, str] = {
    "==": "==",
    "!=": "!=",
    "<": "<",
    "<=": "<=",
    ">": ">",
    ">=": ">=",
    "array-contains": "array_contains",
    "array-contains-any": "array_contains_any",
    "in": "in",
    "not-in": "not-in",
}
LIST_OPERATORS: tuple[str, ...] = ("array-contains-any", "in", "not-in")


class StoreError(Exception):
    pass


def auto_id() -> str:
    return "".join(secrets.choice(seq=AUTO_ID_CHARS) for _ in range(20))


def check_id(name: str) -> str | None:
    if not name:
        return "An ID is required."

    if "/" in name or name in (".", ".."):
        return "IDs must not contain / or be . or .."

    if name.startswith("__") and name.endswith("__"):
        return "IDs of the form __id__ are reserved by Firestore."

    if len(name.encode("utf-8")) > 1500:
        return "IDs must be at most 1500 bytes."

    return None


def check_field_name(name: str | None) -> str | None:
    if not name:
        return "A field name is required."

    if name.startswith("__") and name.endswith("__"):
        return "Field names of the form __name__ are reserved by Firestore."

    if len(name.encode("utf-8")) > 1500:
        return "Field names must be at most 1500 bytes."

    return None


def _field(name: str) -> str:
    return FieldPath(name).to_api_repr()


class Store:
    def __init__(self, account: GoogleAccount, database: str = "") -> None:
        self.project = account.project
        self.database = database or "(default)"
        self.client = firestore.Client(
            project=self.project,
            credentials=account.credentials,
            database=self.database,
        )

    def root_collections(self) -> list[str]:
        return sorted(ref.id for ref in self.client.collections())

    def subcollections(self, doc_path: str) -> list[str]:
        return sorted(ref.id for ref in self.client.document(doc_path).collections())

    # Without a query this also lists documents that only hold subcollections, like the console
    def document_ids(self, coll_path: str, query: Query | None = None) -> list[str]:
        collection = self.client.collection(coll_path)

        if query is None or not query.active:
            return [ref.id for ref in collection.list_documents()]

        ordered: Any = collection

        if query.field:
            value = values.resolve(value=query.value, client=self.client)
            condition = FieldFilter(
                field_path=query.field, op_string=OPERATORS[query.op], value=value
            )
            ordered = ordered.where(filter=condition)

        if query.order:
            direction = (
                firestore.Query.DESCENDING
                if query.descending
                else firestore.Query.ASCENDING
            )
            ordered = ordered.order_by(query.order, direction=direction)

        ids_only = ordered.select([FieldPath.document_id()])

        return [snap.id for snap in ids_only.stream()]

    def document(self, doc_path: str) -> Snapshot:
        ref = self.client.document(doc_path)
        snap = ref.get()
        subcollections = sorted(child.id for child in ref.collections())

        return Snapshot(
            exists=snap.exists, data=snap.to_dict() or {}, subcollections=subcollections
        )

    def create_document(self, coll_path: str, doc_id: str, data: dict[str, Any]) -> str:
        ref = self.client.collection(coll_path).document(doc_id)

        try:
            ref.create(values.resolve(value=data, client=self.client))
        except google_errors.AlreadyExists as exc:
            raise StoreError(f"Document {doc_id} already exists.") from exc

        return ref.path

    # changes: top-level field name → new value, or DELETE
    def update_fields(self, doc_path: str, changes: dict[str, Any]) -> None:
        ref = self.client.document(doc_path)
        payload = {
            _field(name=name): (
                firestore.DELETE_FIELD
                if value is DELETE
                else values.resolve(value=value, client=self.client)
            )
            for name, value in changes.items()
        }

        try:
            ref.update(payload)
        except google_errors.NotFound:
            # a document that only holds subcollections: create it with the new fields
            ref.set(
                {
                    name: values.resolve(value=value, client=self.client)
                    for name, value in changes.items()
                    if value is not DELETE
                }
            )

    def clear_document(self, doc_path: str) -> None:
        self.client.document(doc_path).set({})

    def delete_document(self, doc_path: str) -> None:
        self.client.recursive_delete(self.client.document(doc_path))

    def delete_collection(self, coll_path: str) -> None:
        self.client.recursive_delete(self.client.collection(coll_path))


class OpenedStore(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    store: Store
    root_ids: list[str]


def open_store(account: GoogleAccount, database: str) -> OpenedStore:
    store = Store(account=account, database=database)

    return OpenedStore(store=store, root_ids=store.root_collections())
