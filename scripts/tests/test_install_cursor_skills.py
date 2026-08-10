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

    def test_legacy_git_plugin_names_route_to_one_consolidated_plugin(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["git-workflows", "technology-intelligence"],
            ["gitlab-review", "stacked-delivery", "git-worktree-safety"],
            [],
        )

        self.assertEqual(unknown, [])
        self.assertEqual(selected, ["git-workflows"])

    def test_legacy_git_alias_conflicts_with_canonical_exclusion(self):
        with self.assertRaises(SystemExit):
            install_cursor_skills.select_plugins(
                ["git-workflows"],
                ["gitlab-review"],
                ["git-workflows"],
            )

    def test_legacy_harness_plugin_names_route_to_one_consolidated_plugin(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["agent-harness", "capability-workbench"],
            ["codex-cli", "claude-code", "scheduled-automation"],
            [],
        )

        self.assertEqual(unknown, [])
        self.assertEqual(selected, ["agent-harness"])

    def test_legacy_harness_alias_conflicts_with_canonical_exclusion(self):
        with self.assertRaises(SystemExit):
            install_cursor_skills.select_plugins(
                ["agent-harness"],
                ["claude-code"],
                ["agent-harness"],
            )

    def test_legacy_harness_alias_excludes_canonical_default(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["agent-harness", "capability-workbench"],
            [],
            ["scheduled-automation"],
        )

        self.assertEqual(unknown, [])
        self.assertEqual(selected, ["capability-workbench"])


if __name__ == "__main__":
    unittest.main()
