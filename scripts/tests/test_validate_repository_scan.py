import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "validate-repository.py"
SPEC = importlib.util.spec_from_file_location("validate_repository", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATE_REPOSITORY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATE_REPOSITORY)


class ScanFilesTests(unittest.TestCase):
    def test_non_utf8_text_source_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_bytes(b"latin-1 text: \xe9\n")
            errors = VALIDATE_REPOSITORY.scan_files(root)
            expected = "notes.md: text source must be valid UTF-8"
            self.assertTrue(any(expected in error for error in errors), errors)

    def test_valid_utf8_text_source_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text("plain ascii notes\n", encoding="utf-8")
            self.assertEqual(VALIDATE_REPOSITORY.scan_files(root), [])


if __name__ == "__main__":
    unittest.main()
