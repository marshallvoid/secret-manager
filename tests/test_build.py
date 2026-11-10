from __future__ import annotations

import sys
import tarfile
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from scripts.build_support.archive import archive, stage
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

    def test_staging_only_includes_build_output_and_notices(self) -> None:

        with TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            target = current_target(system="Windows", machine="AMD64")
            executable = binary_path(output=output, target=target)
            executable.parent.mkdir(parents=True)
            executable.write_bytes(data=b"synthetic executable")
            (root / "unrelated.txt").write_text(data="Do not package workspace files", encoding="utf-8")
            package = root / target.name
            stage(
                output=output,
                destination=package,
                target=target,
                notices="Synthetic notices",
                version="1.2.3",
            )
            destination = root / "portable.zip"
            archive(source=package, destination=destination, target=target)

            with zipfile.ZipFile(file=destination) as result:
                names = result.namelist()
                self.assertEqual(result.read(name=f"{target.name}/VERSION"), b"1.2.3\n")

            self.assertIn(f"{target.name}/SecretManager/SecretManager.exe", names)
            self.assertIn(f"{target.name}/THIRD_PARTY_NOTICES.txt", names)
            self.assertFalse(any("unrelated" in name for name in names))

    @unittest.skipIf(sys.platform == "win32", "Symlink creation requires extra Windows permissions")
    def test_linux_archive_preserves_executable_permissions_and_symlinks(self) -> None:

        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "portable"
            source.mkdir()
            executable = source / "app"
            executable.write_bytes(data=b"synthetic executable")
            executable.chmod(mode=0o755)
            link = source / "app-link"
            link.symlink_to(target="app")
            destination = root / "portable.tar.gz"
            archive(source=source, destination=destination, target=current_target(system="Linux", machine="x86_64"))

            with tarfile.open(name=destination) as result:
                self.assertEqual(result.getmember(name="portable/app").mode, 0o755)
                self.assertTrue(result.getmember(name="portable/app-link").issym())

    def test_macos_archive_preserves_app_bundle_with_ditto(self) -> None:

        with patch("scripts.build_support.archive.subprocess.run") as run:
            archive(
                source=Path("portable"),
                destination=Path("portable.zip"),
                target=current_target(system="Darwin", machine="arm64"),
            )

        self.assertIn("--keepParent", run.call_args.kwargs["args"])
        self.assertTrue(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
