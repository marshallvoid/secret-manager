from __future__ import annotations

import json

import requests
from google.auth.transport.requests import AuthorizedSession
from pydantic import ValidationError

from ..credentials import GoogleAccount
from .models import (
    ApiTemplate,
    ErrorBody,
    Template,
    TemplateVersion,
    VersionList,
    parse_template,
)

BASE_URL = (
    "https://firebaseremoteconfig.googleapis.com/v1/projects/{project}/remoteConfig"
)
TIMEOUT = 30


class RemoteConfigError(Exception):
    pass


def _check(response: requests.Response) -> None:
    if response.ok:
        return

    if response.status_code in (409, 412):
        raise RemoteConfigError(
            "The template was changed elsewhere since it was loaded. "
            "Refresh, then make your changes again."
        )

    try:
        message = ErrorBody.model_validate_json(response.content).error.message
    except ValidationError:
        message = ""

    raise RemoteConfigError(
        f"HTTP {response.status_code}: {message or response.text[:500]}"
    )


class RemoteConfigClient:
    def __init__(self, account: GoogleAccount) -> None:
        self.project = account.project
        self.url = BASE_URL.format(project=account.project)
        self.session = AuthorizedSession(account.credentials)

    def _template(self, response: requests.Response) -> Template:
        _check(response=response)
        api = ApiTemplate.model_validate_json(response.content)

        return parse_template(api=api, etag=response.headers.get("ETag", "*"))

    def get(self) -> Template:
        return self._template(response=self.session.get(self.url, timeout=TIMEOUT))

    # The ETag makes the write fail if someone published in between
    def publish(self, template: Template) -> Template:
        headers = {"If-Match": template.etag, "Content-Type": "application/json; UTF-8"}
        response = self.session.put(
            self.url,
            data=json.dumps(obj=template.body()),
            headers=headers,
            timeout=TIMEOUT,
        )

        return self._template(response=response)

    def versions(self, limit: int = 50) -> list[TemplateVersion]:
        response = self.session.get(
            f"{self.url}:listVersions",
            params={"pageSize": limit},
            timeout=TIMEOUT,
        )
        _check(response=response)

        return VersionList.model_validate_json(response.content).versions

    def rollback(self, number: str) -> Template:
        response = self.session.post(
            f"{self.url}:rollback",
            json={"versionNumber": number},
            timeout=TIMEOUT,
        )

        return self._template(response=response)
