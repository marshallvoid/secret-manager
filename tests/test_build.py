from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from scripts.build_support.package import package
from scripts.build_support.targets import binary_path, current_target


class BuildTests(unittest.TestCase):
    def test_supported_platforms_and_architectures(self) -> None:

        for system, machine, name in [
            ("Linux", "x86_64", "SecretManager-linux-x86_64"),
            ("Windows", "AMD64", "SecretManager-windows-x86_64"),
            ("Darwin", "arm64", "SecretManager-macos-arm64"),
            ("Darwin", "x86_64", "SecretManager-macos-x86_64"),
        ]:
            self.assertEqual(current_target(system=system, machine=machine).name, name)

        with self.assertRaises(ValidationError):
            current_target(system="Linux", machine="unsupported")

    def test_executables_are_published_without_sidecar_files(self) -> None:

        for system in ["Linux", "Windows"]:
            with self.subTest(system=system), TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "output"
                output.mkdir()
                target = current_target(system=system, machine="x86_64")
                executable = binary_path(output=output, target=target)
                executable.write_bytes(data=b"synthetic executable")
                executable.chmod(mode=0o755)
                (output / "README.txt").write_text(data="Do not package", encoding="utf-8")
                destination = root / f"{target.name}{target.extension}"
                package(output=output, destination=destination, target=target)
                self.assertEqual(destination.read_bytes(), b"synthetic executable")
                self.assertFalse(executable.exists())
                self.assertEqual(sorted(path.name for path in root.iterdir()), [destination.name, "output"])

                if sys.platform != "win32":
                    self.assertEqual(destination.stat().st_mode & 0o777, 0o755)

    def test_macos_packages_only_app_bundle_as_disk_image(self) -> None:
        target = current_target(system="Darwin", machine="arm64")
        self.assertEqual(target.extension, ".dmg")
        self.assertEqual(
            binary_path(output=Path("output"), target=target),
            Path("output/SecretManager.app/Contents/MacOS/SecretManager"),
        )

        with patch("scripts.build_support.package.subprocess.run") as run:
            package(output=Path("output"), destination=Path("portable.dmg"), target=target)

        run.assert_called_once_with(
            args=[
                "hdiutil",
                "create",
                "-volname",
                "SecretManager",
                "-srcfolder",
                str(Path("output/SecretManager.app")),
                "-format",
                "UDZO",
                "-ov",
                "portable.dmg",
            ],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
