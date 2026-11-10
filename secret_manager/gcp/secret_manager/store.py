from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from google.cloud import secretmanager

from ..credentials import GoogleAccount
from .models import NewSecret, SecretInfo, VersionAction, VersionInfo

ID_RE = re.compile(pattern=r"[A-Za-z0-9_-]{1,255}")


def check_id(secret_id: str) -> str | None:
    if not ID_RE.fullmatch(secret_id):
        return "Use 1 to 255 letters, digits, - and _."

    return None


def _replication(secret: secretmanager.Secret) -> str:
    if "user_managed" in secret.replication:
        locations = [replica.location for replica in secret.replication.user_managed.replicas]

        return "User managed: " + ", ".join(locations)

    return "Automatic"


# The API returns protobuf messages; they become models as they enter the program
class SecretStore:
    def __init__(self, account: GoogleAccount) -> None:
        self.project = account.project
        self.parent = f"projects/{account.project}"
        self.client = secretmanager.SecretManagerServiceClient(credentials=account.credentials)

    def _name(self, secret_id: str) -> str:
        return f"{self.parent}/secrets/{secret_id}"

    def _version_name(self, secret_id: str, version: str) -> str:
        return f"{self._name(secret_id=secret_id)}/versions/{version}"

    def list_secrets(self) -> list[SecretInfo]:
        secrets = [
            SecretInfo.model_validate(
                obj={
                    "id": secret.name.rsplit("/", 1)[-1],
                    "created": secret.create_time,
                    "replication": _replication(secret=secret),
                    "labels": dict(secret.labels),
                }
            )
            for secret in self.client.list_secrets(request={"parent": self.parent})
        ]

        return sorted(secrets, key=lambda secret: secret.id.lower())

    # newest first, like the console
    def list_versions(self, secret_id: str) -> list[VersionInfo]:
        request = {"parent": self._name(secret_id=secret_id)}
        versions = [
            VersionInfo.model_validate(
                obj={
                    "number": version.name.rsplit("/", 1)[-1],
                    "state": secretmanager.SecretVersion.State(version.state).name,
                    "created": version.create_time,
                }
            )
            for version in self.client.list_secret_versions(request=request)
        ]

        return sorted(versions, key=lambda version: int(version.number), reverse=True)

    def access(self, secret_id: str, version: str) -> bytes:
        name = self._version_name(secret_id=secret_id, version=version)

        return self.client.access_secret_version(request={"name": name}).payload.data

    def create_secret(self, secret: NewSecret) -> None:
        body: dict[str, Any] = {
            "replication": {"automatic": {}},
            "labels": secret.labels,
        }
        self.client.create_secret(
            request={
                "parent": self.parent,
                "secret_id": secret.secret_id,
                "secret": body,
            }
        )

        if secret.value:
            self.add_version(secret_id=secret.secret_id, value=secret.value)

    def add_version(self, secret_id: str, value: str) -> None:
        payload = {"data": value.encode("utf-8")}
        self.client.add_secret_version(request={"parent": self._name(secret_id=secret_id), "payload": payload})

    def change_version(self, secret_id: str, version: str, action: VersionAction) -> None:
        request = {"name": self._version_name(secret_id=secret_id, version=version)}
        methods: dict[str, Callable[..., Any]] = {
            "enable": self.client.enable_secret_version,
            "disable": self.client.disable_secret_version,
            "destroy": self.client.destroy_secret_version,
        }
        methods[action](request=request)

    def delete_secret(self, secret_id: str) -> None:
        self.client.delete_secret(request={"name": self._name(secret_id=secret_id)})
