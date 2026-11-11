# Secret Manager

A PySide6 desktop app for secrets and config:

- **Google Cloud** tab, one service account file for all of:
  - **Firestore**: a data browser laid out like the Firebase console.
  - **Secret Manager**: secrets and their versions.
  - **Remote Config**: parameters and conditions, published as one template.
- **GitHub** tab: secrets and variables through `gh`.

## Run

```bash
gh auth login        # once, for the GitHub tab
uv sync
uv run secret-manager
```

- Needs Python 3.10 or newer.
- The window opens maximized.

## Development commands

| Command | Action |
|---|---|
| `make install` | Create .venv with uv and install the git hook |
| `make run` | Open the app |
| `make test` | Run tests using synthetic data |
| `make lint` | Run Ruff checks, format validation, strict mypy and Pyright |
| `make check` | Run lint and tests |
| `make format` | Apply Ruff fixes and formatting |
| `make build` | Build a portable executable or macOS disk image |
| `make clean` | Remove generated files in `dist/` |

## Code checks

- Run `make format` before `make check`.
- Ruff targets Python 3.10, matching the app's minimum Python version.
- The formatter manages trailing commas; the conflicting `COM812` rule is not enabled.
- Collection annotations stay in `typing`, following the project's Python rules.
- Pyright uses the same configuration in the terminal and Pylance; deprecated typing aliases are allowed.
- Firestore's heterogeneous SDK-native values allow explicit `Any` annotations in the value adapters.
- The optional pre-commit hooks check staged Python files without rewriting them.
- CI runs lint and tests before creating a release or building portable artifacts.

## Portable builds

- Build with `make build`, or `.venv/bin/python -B scripts/build.py`.
- Each platform builds on its own OS; cross-compilation is not supported.
- The **Build** workflow builds all four targets for a release or a manual run.
- Windows/Linux: run the downloaded executable; on Linux, run `chmod +x` on it first.
- macOS: open the disk image and copy `SecretManager.app` to Applications.
- Python is bundled on every platform.
- GitHub features still require `gh` installed on `PATH` and signed in.
- Google Cloud features use a service account file selected by the user.
- Release assets contain the application without extra README, LICENSE or VERSION files.
- Builds are unsigned; macOS builds are not notarized.
- Linux builds require compatible system libraries; the workflow uses Ubuntu 22.04.

| Platform | Release asset |
|---|---|
| Linux x86_64 | `dist/SecretManager-linux-x86_64` |
| Windows x86_64 | `dist/SecretManager-windows-x86_64.exe` |
| macOS Apple Silicon | `dist/SecretManager-macos-arm64.dmg` |
| macOS Intel | `dist/SecretManager-macos-x86_64.dmg` |

## Releases

- Pull requests and pushes to `main` run lint and tests.
- After checks pass on `main`, semantic-release reads Conventional Commits and creates a version tag and draft release.
- All four portable builds attach their assets to that draft.
- The release becomes public and latest only after every build succeeds and all four assets are attached.
- A failed build leaves the release as a draft.
- Manual workflow runs build artifacts without creating a release.
- The pipeline uses the built-in GitHub Actions token; no custom credential file is required.
- The release tag identifies the version; Python package metadata keeps the source version.

| Commit | Version change |
|---|---|
| `fix: ...` | Patch |
| `feat: ...` | Minor |
| `BREAKING CHANGE: ...` in the commit body/footer | Major |
| `docs: ...`, `chore: ...`, `test: ...` | No release by default |

## Firestore

- Breadcrumb path on top: click a segment to go back, or the pencil to type a path.
- Three panels below (database → collection → document), shifting as you go deeper.
  - Drag the borders to resize; the first two fit their content, the field panel takes the rest.
- Leave **Database** empty for `(default)`.
- Collections:
  - Start one, at the root or under a document.
  - Filter and sort its documents.
  - Copy its path, or delete it with everything inside (type its ID to confirm).
- Documents:
  - Add one (an empty ID gives an auto-ID), or add a similar one.
  - Delete it with its subcollections, or delete only its fields.
  - Documents that only hold subcollections are listed too, as in the console.
- Fields:
  - All console types: string, number, boolean, map, array, null, timestamp, geopoint, reference.
  - Maps and arrays nest at any depth.
  - Hover a field for its type and the add, edit and delete buttons; double-click to edit.
  - Right-click to copy a value or a field path, or to send a string to GitHub as a secret.
- Limits:
  - An edit inside a map or array rewrites the whole top-level field.
  - Opening a collection reads every document ID in it.

## Secret Manager

- Create a secret, with an optional first value and labels.
- Add versions; the newest is marked latest.
- View a version's value, copy it, or send it to GitHub as a secret.
- Disable, enable or destroy a version.
- Delete a secret (type its name to confirm).

## Remote Config

- Parameters, grouped like the console, each with:
  - a data type, a description and a group;
  - a default value, or the in-app default;
  - a value per condition.
- Conditions: name, color and expression; renaming one updates the parameters that use it.
- Changes stay local until **Publish changes**.
  - Publishing fails safely if someone else published in between.
- **Versions** lists past templates and rolls back to one.

## GitHub

- The sidebar lists, from the widest scope to the narrowest, by name only:
  - your account's Codespaces secrets;
  - each organization: its own secrets and variables, then its repositories;
  - your repositories.
- For the chosen item, pick **Secrets** or **Variables**, then a scope.
- Organization and Codespaces entries choose which repositories can read them.
- Variables show their value; secrets can only be replaced, since GitHub never returns them.
- `.env` import shows the names before it sets anything.

| Owner | Secret scopes | Variable scopes |
|---|---|---|
| Repository | Repository (Actions), each environment, Dependabot, Codespaces | Repository, each environment |
| Organization | Actions, Dependabot, Codespaces | Actions |
| Account | Codespaces | none |

| Shortcut | Action |
|---|---|
| Ctrl+N | New secret or variable |
| F5 | Refresh |
| Del | Delete the selected entries |
| Ctrl+F | Search |

## Permissions

| Feature | Needs |
|---|---|
| Firestore | `Cloud Datastore User` role |
| Secret Manager | `Secret Manager Admin`, or `Secret Manager Secret Accessor` to only read values |
| Remote Config | `Firebase Remote Config Admin` role |
| GitHub organization entries | Org admin rights and the `admin:org` scope |
| GitHub Codespaces secrets | The `codespace` scope |

- Add the GitHub scopes with `gh auth refresh -s admin:org,codespace`.

## Settings

- Stored in `~/.config/secret-manager/settings.json`, validated when read.
- A missing or broken file falls back to the defaults.
- Never holds secret values or credential contents.

| Key | Holds |
|---|---|
| `credentials` | Path to the service account file |
| `database`, `databases` | The Firestore database, and recent ones |
| `firestore_path` | The last place opened in Firestore |
| `tab`, `google_tab` | The open tabs |
| `github_owner`, `github_kind`, `github_scope` | The GitHub item, Secrets or Variables, and scope |
| `github_repo_filter`, `github_repo_search` | The repository secrets filter and search text |
| `github_collapsed_sections` | Collapsed GitHub sidebar groups |

## Layout

| Path | Holds |
|---|---|
| `app.py` | Main window and the background job runner |
| `settings.py` | The settings model, load and save |
| `theme.py` | Colors, style sheet and icons |
| `widgets.py`, `dialogs.py` | Shared Qt widgets and the dialog base |
| `utils/` | Standard-library helpers (dates, names) |
| `gcp/tab.py`, `gcp/credentials.py` | The Google Cloud tab and the shared service account |
| `gcp/firestore/` | Firestore: store, values, models, panels, browser, dialogs |
| `gcp/secret_manager/` | Secret Manager: store, models, rows, dialogs, tab |
| `gcp/remote_config/` | Remote Config: REST client, models, dialogs, tab |
| `github/` | `gh` wrapper, models of its JSON, sidebar, rows, dialogs, tab |
