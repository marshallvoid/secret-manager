from __future__ import annotations

import subprocess
from pathlib import Path

from .targets import BuildTarget, binary_path


def package(output: Path, destination: Path, target: BuildTarget) -> None:

    if target.system == "macos":
        subprocess.run(
            args=[
                "hdiutil",
                "create",
                "-volname",
                "SecretManager",
                "-srcfolder",
                str(output / "SecretManager.app"),
                "-format",
                "UDZO",
                "-ov",
                str(destination),
            ],
            check=True,
        )

        return

    binary_path(output=output, target=target).replace(target=destination)
