from __future__ import annotations

import platform
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel


class BuildTarget(BaseModel):
    system: Literal["linux", "windows", "macos"]
    arch: Literal["x86_64", "arm64"]

    @property
    def name(self) -> str:
        return f"SecretManager-{self.system}-{self.arch}"

    @property
    def extension(self) -> str:
        return {"linux": "", "windows": ".exe", "macos": ".dmg"}[self.system]


def current_target(system: Optional[str] = None, machine: Optional[str] = None) -> BuildTarget:
    detected_system = (system or platform.system()).lower()
    detected_machine = (machine or platform.machine()).lower()
    systems = {"linux": "linux", "windows": "windows", "darwin": "macos"}
    architectures = {"amd64": "x86_64", "x86_64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}

    return BuildTarget.model_validate(
        obj={
            "system": systems.get(detected_system, detected_system),
            "arch": architectures.get(detected_machine, detected_machine),
        }
    )


def binary_path(output: Path, target: BuildTarget) -> Path:

    if target.system == "macos":
        return output / "SecretManager.app" / "Contents" / "MacOS" / "SecretManager"

    return output / ("SecretManager.exe" if target.system == "windows" else "SecretManager")
