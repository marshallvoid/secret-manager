from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path
from typing import List, Set

from packaging.requirements import Requirement

LICENSE_NAME = re.compile(pattern=r"licen[cs]e|copying|notice", flags=re.IGNORECASE)
ROOT = Path(__file__).resolve().parents[2]


def third_party_notices() -> str:
    pending: List[str] = ["secret-manager", "pyinstaller"]
    visited: Set[str] = set()
    licensed: Set[str] = set()
    sections: List[str] = ["Third-party software notices for this portable build."]
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    prefix = Path(sys.base_prefix)

    for path in [prefix / "lib" / version / "LICENSE.txt", prefix / "LICENSE.txt", prefix / "LICENSE"]:
        if path.is_file():
            sections.append(f"Python\n\n{path.read_text(encoding='utf-8', errors='replace')}")

            break

    for license_file in ["lgpl-3.0.txt", "gpl-3.0.txt"]:
        text = (ROOT / "licenses" / license_file).read_text(encoding="utf-8")
        sections.append(f"Qt / PySide6: {license_file}\n\n{text}")

    while pending:
        requested = Requirement(requirement_string=pending.pop())
        distribution = metadata.distribution(distribution_name=requested.name)
        normalized = distribution.metadata["Name"].lower().replace("_", "-")
        dependency_key = normalized + str(sorted(requested.extras))

        if dependency_key in visited:
            continue

        visited.add(dependency_key)

        for requirement_text in distribution.requires or []:
            requirement = Requirement(requirement_string=requirement_text)

            if requirement.marker is None or any(
                requirement.marker.evaluate(environment={"extra": extra}) for extra in ["", *requested.extras]
            ):
                pending.append(str(requirement))

        if normalized == "secret-manager" or normalized in licensed:
            continue

        licensed.add(normalized)
        texts: List[str] = []

        for file in distribution.files or []:
            if ".dist-info" in str(file) and LICENSE_NAME.search(string=file.name):
                license_path = Path(str(distribution.locate_file(path=file)))
                texts.append(license_path.read_text(encoding="utf-8", errors="replace"))

        license_info = distribution.metadata["License-Expression"] or distribution.metadata["License"] or ""
        sections.append(
            f"{'=' * 72}\n{distribution.metadata['Name']} {distribution.version}\n"
            f"{'=' * 72}\n" + ("\n\n".join(texts) or license_info or "See the upstream package license.")
        )

    return "\n\n".join(sections) + "\n"
