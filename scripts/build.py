from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_support.package import package
from scripts.build_support.targets import binary_path, current_target

DIST = ROOT / "dist"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a portable app for the current platform.")
    parser.add_argument("--clean", action="store_true", help="Remove generated portable build output.")
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(path=DIST, ignore_errors=True)

        return

    target = current_target()
    DIST.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix=".build-", dir=DIST) as directory:
        work = Path(directory)
        output = work / "output"
        PyInstaller.__main__.run(
            pyi_args=[
                "--noconfirm",
                "--windowed",
                "--onedir" if target.system == "macos" else "--onefile",
                "--name",
                "SecretManager",
                "--paths",
                str(ROOT),
                "--distpath",
                str(output),
                "--workpath",
                str(work / "pyinstaller"),
                "--specpath",
                str(work),
                "--exclude-module",
                "tkinter",
                "--exclude-module",
                "PyQt5",
                "--exclude-module",
                "PyQt6",
                "--exclude-module",
                "PySide2",
                "--collect-data",
                "certifi",
                "--copy-metadata",
                "google-cloud-firestore",
                "--copy-metadata",
                "google-cloud-secret-manager",
                str(ROOT / "scripts" / "portable_entry.py"),
            ]
        )
        subprocess.run(args=[str(binary_path(output=output, target=target)), "--smoke-test"], check=True)
        destination = DIST / f"{target.name}{target.extension}"
        package(output=output, destination=destination, target=target)

    print(destination)


if __name__ == "__main__":
    main()
