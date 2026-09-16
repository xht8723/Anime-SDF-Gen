"""Import safety and reproducible archive output."""

from contextlib import ExitStack
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import package

ROOT = Path(__file__).resolve().parents[1]


class ReleaseToolTests(unittest.TestCase):
    def test_importing_helpers_and_tools_does_not_write_files(self):
        for relative in (
            "tests/support.py",
            "tests/samples.py",
            "tools/package.py",
            "tools/validate.py",
            "tools/verify_release.py",
            "tools/check_i18n.py",
        ):
            spec = importlib.util.spec_from_file_location("_import_probe", ROOT / relative)
            module = importlib.util.module_from_spec(spec)
            with ExitStack() as stack:
                for name in ("mkdir", "write_text", "write_bytes"):
                    stack.enter_context(
                        patch.object(Path, name, side_effect=AssertionError("Import wrote files"))
                    )
                spec.loader.exec_module(module)

    def test_archive_bytes_ignore_input_order_and_source_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root / "a.py", root / "b.py"
            a.write_text("a = 1\n")
            b.write_text("b = 2\n")
            first, second = root / "one.zip", root / "two.zip"
            package.write_archive(first, [("b.py", b), ("a.py", a)])
            os.utime(a, (1_000_000_000, 1_000_000_000))
            os.utime(b, (1_700_000_000, 1_700_000_000))
            package.write_archive(second, [("a.py", a), ("b.py", b)])
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertTrue(first.with_name("one.zip.sha256").is_file())
