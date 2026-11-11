from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import build


class BuildTests(unittest.TestCase):
    def test_release_asset_names(self) -> None:

        for system, machine, name in [
            ("linux", "x86_64", "SecretManager-linux-x86_64"),
            ("win32", "AMD64", "SecretManager-windows-x86_64.exe"),
            ("darwin", "arm64", "SecretManager-macos-arm64.dmg"),
            ("darwin", "x86_64", "SecretManager-macos-x86_64.dmg"),
        ]:
            with (
                self.subTest(system=system, machine=machine),
                patch("scripts.build.sys.platform", system),
                patch("scripts.build.platform.machine", return_value=machine),
            ):
                self.assertEqual(build.asset_name(), name)

    def test_packages_only_executable_and_keeps_permissions(self) -> None:

        with TemporaryDirectory() as directory:
            root = Path(directory)
            work = root / "work"
            output = work / "output"
            output.mkdir(parents=True)
            executable = output / build.NAME
            executable.write_bytes(data=b"synthetic executable")
            executable.chmod(mode=0o755)
            (output / "README.txt").write_text(data="Do not package", encoding="utf-8")

            with (
                patch.object(build, "DIST", root),
                patch.object(build, "WORK", work),
                patch("scripts.build.sys.platform", "linux"),
            ):
                destination = build.package()

            self.assertEqual(destination.read_bytes(), b"synthetic executable")
            self.assertFalse(executable.exists())
            self.assertEqual(sorted(path.name for path in root.iterdir()), [destination.name, "work"])

            if sys.platform != "win32":
                self.assertEqual(destination.stat().st_mode & 0o777, 0o755)

    def test_macos_packages_app_bundle(self) -> None:

        with patch("scripts.build.sys.platform", "darwin"), patch("scripts.build.subprocess.run") as run:
            destination = build.package()

        args = run.call_args.kwargs["args"]
        self.assertEqual(args[0:2], ["hdiutil", "create"])
        self.assertEqual(args[args.index("-srcfolder") + 1], str(build.WORK / "output" / "SecretManager.app"))
        self.assertEqual(args[-1], str(destination))
        self.assertTrue(run.call_args.kwargs["check"])


if __name__ == "__main__":
    unittest.main()
