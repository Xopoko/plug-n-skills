"""Behavior tests for the utilities shared by repository scripts."""

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import lockfile_json  # noqa: E402
import plugin_registry  # noqa: E402


class PluginRegistryTests(unittest.TestCase):
    def test_repo_root_is_the_checkout(self):
        self.assertEqual(plugin_registry.repo_root(), ROOT)

    def test_canonical_names_map_legacy_ids_and_drop_repeats(self):
        self.assertEqual(
            plugin_registry.canonical_names(["codex-cli", "claude-code", "tauri"]),
            ["agent-harness", "tauri"],
        )

    def test_selection_defaults_to_available_names(self):
        selection = plugin_registry.resolve_selection(None, None, available=["a", "b"])
        self.assertEqual(selection.selected, ["a", "b"])

    def test_selection_prefers_explicit_default_names(self):
        selection = plugin_registry.resolve_selection(
            None, None, available=["a", "b"], default_names=["b"]
        )
        self.assertEqual(selection.selected, ["b"])

    def test_selection_applies_exclusions_after_canonicalization(self):
        selection = plugin_registry.resolve_selection(
            ["codex-cli", "tauri"],
            ["gitlab-review"],
            available=["agent-harness", "git-workflows", "tauri"],
        )
        self.assertEqual(selection.selected, ["agent-harness", "tauri"])

    def test_legacy_aliases_of_the_same_plugin_count_as_overlap(self):
        selection = plugin_registry.resolve_selection(
            ["codex-cli"], ["claude-code"], available=["agent-harness"]
        )
        self.assertEqual((selection.selected, selection.overlap), ([], ["agent-harness"]))

    def test_selection_reports_unknown_names(self):
        selection = plugin_registry.resolve_selection(["nope"], [], available=["tauri"])
        self.assertEqual((selection.selected, selection.unknown), ([], ["nope"]))

    def test_selection_reports_include_exclude_overlap(self):
        selection = plugin_registry.resolve_selection(
            ["tauri"], ["tauri"], available=["tauri"]
        )
        self.assertEqual((selection.selected, selection.overlap), ([], ["tauri"]))

    def test_selection_is_empty_when_everything_is_excluded(self):
        selection = plugin_registry.resolve_selection(
            ["tauri"], ["pixijs", "tauri"], available=["tauri", "pixijs"]
        )
        self.assertEqual(selection.selected, [])


class LockfileJsonTests(unittest.TestCase):
    def write(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "payload.json"
        path.write_text(text, encoding="utf-8")
        return path

    def test_loads_json_objects(self):
        path = self.write(json.dumps({"schemaVersion": 1}))
        self.assertEqual(lockfile_json.load_object(path, "lockfile"), {"schemaVersion": 1})

    def test_rejects_duplicate_keys(self):
        path = self.write('{"schemaVersion": 1, "schemaVersion": 2}')
        with self.assertRaisesRegex(lockfile_json.StrictJsonError, "duplicate key"):
            lockfile_json.load_object(path, "lockfile")

    def test_rejects_non_object_payloads(self):
        path = self.write("[]")
        with self.assertRaisesRegex(lockfile_json.StrictJsonError, "must be a JSON object"):
            lockfile_json.load_object(path, "lockfile")

    def test_reports_missing_file_when_required(self):
        path = self.write("{}").with_name("absent.json")
        with self.assertRaisesRegex(lockfile_json.StrictJsonError, "does not exist"):
            lockfile_json.load_object(path, "lockfile", require_file=True)


if __name__ == "__main__":
    unittest.main()
