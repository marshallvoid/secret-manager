#!/usr/bin/env python3
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parents[1]
NAME = "SecretManager"
DIST = ROOT / "dist"
WORK = DIST / "work"


def asset_name() -> str:
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    machine = platform.machine().lower()
    extension = {"linux": "", "win32": ".exe", "darwin": ".dmg"}[sys.platform]

    return f"{NAME}-{system}-{'x86_64' if machine == 'amd64' else machine}{extension}"


def compile_app() -> None:
    args = [
        "--noconfirm",
        "--log-level",
        "WARN",
        "--windowed",
        "--name",
        NAME,
        "--paths",
        str(ROOT),
        "--exclude-module",
        "tkinter",
        "--collect-data",
        "certifi",
        "--copy-metadata",
        "google-cloud-firestore",
        "--copy-metadata",
        "google-cloud-secret-manager",
        "--distpath",
        str(WORK / "output"),
        "--workpath",
        str(WORK / "pyinstaller"),
        "--specpath",
        str(WORK),
    ]

    if sys.platform != "darwin":
        args.append("--onefile")

    PyInstaller.__main__.run(pyi_args=[*args, str(ROOT / "secret_manager" / "__main__.py")])


def package() -> Path:
    target = DIST / asset_name()
    output = WORK / "output"

    if sys.platform == "darwin":
        subprocess.run(
            args=[
                "hdiutil",
                "create",
                "-volname",
                NAME,
                "-srcfolder",
                str(output / f"{NAME}.app"),
                "-format",
                "UDZO",
                "-ov",
                str(target),
            ],
            check=True,
        )
    else:
        binary = f"{NAME}.exe" if sys.platform == "win32" else NAME
        shutil.move(src=str(output / binary), dst=str(target))

    return target


def main() -> None:
    shutil.rmtree(path=DIST, ignore_errors=True)
    compile_app()
    target = package()
    shutil.rmtree(path=WORK)
    print(target)


if __name__ == "__main__":
    main()
