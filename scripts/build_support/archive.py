from __future__ import annotations

import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

from .targets import BuildTarget


def stage(output: Path, destination: Path, target: BuildTarget, notices: str, version: str = "development") -> None:
    destination.mkdir(parents=True)
    source = output / ("SecretManager.app" if target.system == "macos" else "SecretManager")

    if target.system == "macos":
        subprocess.run(args=["ditto", str(source), str(destination / source.name)], check=True)
    else:
        shutil.copytree(src=source, dst=destination / source.name, symlinks=True)

    (destination / "THIRD_PARTY_NOTICES.txt").write_text(data=notices, encoding="utf-8")
    (destination / "VERSION").write_bytes(data=f"{version}\n".encode())
    (destination / "README.txt").write_text(
        data=(
            "Secret Manager portable\n\n"
            "- Extract the entire archive before opening the app.\n"
            "- Windows/Linux: open SecretManager/SecretManager (.exe on Windows).\n"
            "- macOS: open SecretManager.app.\n"
            "- GitHub features require GitHub CLI (gh) installed on PATH and signed in.\n"
            "- Google Cloud features require your own service account file.\n"
            "- Credentials and user configuration are not bundled.\n"
            "- Settings use the same user configuration location as the source app.\n"
        ),
        encoding="utf-8",
    )


def archive(source: Path, destination: Path, target: BuildTarget) -> None:

    if target.system == "macos":
        subprocess.run(
            args=["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(source), str(destination)],
            check=True,
        )

        return

    if target.system == "linux":
        with tarfile.open(name=destination, mode="w:gz", dereference=False, compresslevel=6) as output:
            output.add(name=source, arcname=source.name)

        return

    with zipfile.ZipFile(file=destination, mode="w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(source.rglob(pattern="*")):
            output.write(filename=path, arcname=str(path.relative_to(source.parent)))
