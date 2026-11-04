from __future__ import annotations

from google.oauth2 import service_account
from pydantic import BaseModel, ConfigDict

SCOPES: list[str] = ["https://www.googleapis.com/auth/cloud-platform"]


class CredentialsError(Exception):
    pass


class GoogleAccount(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    path: str
    project: str
    email: str
    credentials: service_account.Credentials | None


def load_account(path: str) -> GoogleAccount:
    try:
        credentials = service_account.Credentials.from_service_account_file(
            path, scopes=SCOPES
        )
    except (OSError, ValueError, KeyError) as exc:
        raise CredentialsError(
            f"Cannot read service account credentials: {exc}"
        ) from exc

    if not credentials.project_id:
        raise CredentialsError("The credentials file has no project_id.")

    return GoogleAccount(
        path=path,
        project=credentials.project_id,
        email=credentials.service_account_email,
        credentials=credentials,
    )
