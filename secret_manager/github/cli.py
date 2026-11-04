from __future__ import annotations

import re
import shutil
import subprocess

from .models import Access, Entry, Repo, Target
from .responses import ENTRIES, ORGS, REPOS, GhEnvironments

REPO_RE = re.compile(pattern=r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
NAME_RE = re.compile(pattern=r"[A-Za-z_][A-Za-z0-9_]*")
SCOPE_HINT = (
    "\n\nOrganization secrets and variables need org admin rights and the admin:org "
    "scope; Codespaces secrets need the codespace scope. Add the scopes with: "
    "gh auth refresh -s admin:org,codespace"
)


class GhError(Exception):
    pass


def _run(args: list[str], stdin: str | None = None) -> str:
    if shutil.which(cmd="gh") is None:
        raise GhError("gh is not installed or not on PATH")

    proc = subprocess.run(
        args=["gh", *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip()
        message = message or f"gh exited with code {proc.returncode}"

        if "scope" in message.lower() or "HTTP 403" in message:
            message += SCOPE_HINT

        raise GhError(message)

    return proc.stdout


def check_name(name: str) -> str | None:
    if not NAME_RE.fullmatch(name):
        return "Use only letters, digits and _, and do not start with a digit."

    if name.upper().startswith("GITHUB_"):
        return "Names must not start with GITHUB_."

    return None


def list_orgs() -> list[str]:
    orgs = ORGS.validate_json(_run(args=["api", "user/orgs", "--paginate"]))

    return sorted(org.login for org in orgs)


# Without an owner, gh lists the signed-in user's own repositories
def list_repos(owner: str = "") -> list[Repo]:
    args = ["repo", "list", "--limit", "1000", "--json", "name,nameWithOwner"]

    if owner:
        args.insert(2, owner)

    repos = [
        Repo(name=item.name, full_name=item.name_with_owner)
        for item in REPOS.validate_json(_run(args=args))
    ]

    return sorted(repos, key=lambda repo: repo.name.lower())


def list_environments(repo: str) -> list[str]:
    try:
        out = _run(args=["api", f"repos/{repo}/environments"])
    except GhError:
        return []

    environments = GhEnvironments.model_validate_json(out).environments

    return sorted(env.name for env in environments)


def list_entries(target: Target) -> list[Entry]:
    fields = "name,updatedAt"

    if target.kind == "variable":
        fields += ",value"

    if target.shared:
        fields += ",visibility,numSelectedRepos"

    out = _run(args=[target.kind, "list", *target.args(), "--json", fields])
    entries = [
        Entry(
            name=item.name,
            updated=item.updated_at or "",
            value=item.value,
            visibility=item.visibility or "",
            selected_count=item.num_selected_repos or 0,
        )
        for item in ENTRIES.validate_json(out)
    ]

    return sorted(entries, key=lambda entry: entry.name)


# The value goes through stdin so it never shows up in the process list
def set_entry(
    target: Target, name: str, value: str, access: Access | None = None
) -> None:
    args = [target.kind, "set", name, *target.args()]

    if access is not None:
        args += access.args(owner=target.owner)

    _run(args=args, stdin=value)


def set_from_env_file(target: Target, path: str) -> None:
    _run(args=[target.kind, "set", "--env-file", path, *target.args()])


def delete_entry(target: Target, name: str) -> None:
    _run(args=[target.kind, "delete", name, *target.args()])


# Repositories that can read an org or user entry whose visibility is "selected"
def selected_repos(target: Target, name: str) -> list[str]:
    plural = "secrets" if target.kind == "secret" else "variables"

    if target.owner == "user":
        path = f"user/codespaces/secrets/{name}/repositories"
    else:
        path = f"orgs/{target.name}/{target.app}/{plural}/{name}/repositories"

    out = _run(args=["api", path, "--paginate", "--jq", ".repositories[].full_name"])

    return sorted(line for line in out.splitlines() if line)
