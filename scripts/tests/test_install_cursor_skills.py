import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = ROOT / "scripts" / "install-cursor-skills.py"

spec = importlib.util.spec_from_file_location("install_cursor_skills", INSTALLER_PATH)
install_cursor_skills = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(install_cursor_skills)


class CursorInstallerTest(unittest.TestCase):
    def test_exclude_plugins_removes_default_plugins(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["a", "b", "c"],
            [],
            ["b"],
        )

        self.assertEqual(unknown, [])
        self.assertEqual(selected, ["a", "c"])

    def test_unknown_include_or_exclude_is_reported(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["a", "b"],
            ["a"],
            ["missing"],
        )

        self.assertEqual(selected, [])
        self.assertEqual(unknown, ["missing"])

    def test_plugin_cannot_be_selected_and_excluded(self):
        with self.assertRaises(SystemExit):
            install_cursor_skills.select_plugins(["a"], ["a"], ["a"])


if __name__ == "__main__":
    unittest.main()
