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
