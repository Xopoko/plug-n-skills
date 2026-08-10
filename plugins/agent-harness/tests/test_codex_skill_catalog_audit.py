import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "codex_skill_catalog_audit.py"
PINNED_CODEX_SNAPSHOT = "95c7265e849e6e360a7fa53ffeac70b25d6051a3"


class CodexSkillCatalogAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.plugin = Path(self.tmp.name) / "fixture-pack"
        manifest = self.plugin / ".codex-plugin"
        manifest.mkdir(parents=True)
        (manifest / "plugin.json").write_text(
            json.dumps({"name": "fixture-pack"}), encoding="utf-8"
        )
        self.skills = self.plugin / "skills"
        self.write_skill("alpha-skill", "Trigger-first metadata " + ("x" * 1_100))
        self.write_skill("unicode-skill", "é" * 300)
        manual = self.write_skill("manual-skill", "Explicit-only fixture.")
        agents = manual / "agents"
        agents.mkdir()
        (agents / "openai.yaml").write_text(
            "policy:\n  allow_implicit_invocation: false\n", encoding="utf-8"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def write_skill(self, folder: str, description: str) -> Path:
        skill = self.skills / folder
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {folder}\ndescription: {description}\n---\n\n# Fixture\n",
            encoding="utf-8",
        )
        return skill

    def run_audit(self, *args: str) -> dict:
        return self.run_audit_for_paths([self.plugin], *args)

    def run_audit_for_paths(self, paths: list[Path], *args: str) -> dict:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                *(str(path) for path in paths),
                *args,
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_source_model_is_current_and_explicit_only_is_excluded(self):
        payload = self.run_audit("--context-window", "1000000")
        summary = payload["summary"]
        rows = {row["name"]: row for row in payload["skills"]}

        self.assertEqual(
            payload["source_model"]["codex_source_snapshot"],
            PINNED_CODEX_SNAPSHOT,
        )
        self.assertEqual(
            payload["source_model"]["budget_configuration"],
            "compile_time_constant_without_supported_runtime_override",
        )
        self.assertEqual(
            payload["fidelity"],
            {
                "exact": False,
                "surface": "isolated_host_core_compatible_absolute",
                "direction": "unknown",
                "unknowns": [
                    "scope_and_source_kind",
                    "display_paths_and_roots",
                    "root_alias_selection",
                    "other_catalogs_and_shared_budget",
                ],
            },
        )
        self.assertEqual(summary["discovered_skills"], 3)
        self.assertEqual(summary["implicit_catalog_skills"], 2)
        self.assertTrue(rows["fixture-pack:manual-skill"]["explicit_only"])
        self.assertEqual(
            rows["fixture-pack:alpha-skill"]["catalog_description_chars"], 1024
        )

    def test_exact_full_cost_is_not_shortened(self):
        baseline = self.run_audit("--context-window", "1000000")
        full_cost = baseline["summary"]["full_metadata_cost"]
        payload = self.run_audit("--context-window", str(full_cost * 50))

        self.assertEqual(payload["input"]["budget_limit"], full_cost)
        self.assertEqual(payload["summary"]["state"], "full_metadata_visible")
        self.assertEqual(payload["summary"]["budget_truncated_description_count"], 0)

    def test_soft_pressure_shortens_descriptions_without_omission(self):
        baseline = self.run_audit("--context-window", "1000000")
        summary = baseline["summary"]
        soft_budget = summary["minimum_name_path_cost"] + max(
            (summary["full_metadata_cost"] - summary["minimum_name_path_cost"]) // 2,
            1,
        )
        payload = self.run_audit("--context-window", str(soft_budget * 50))

        self.assertEqual(payload["summary"]["state"], "descriptions_shortened")
        self.assertEqual(payload["summary"]["omitted_skills"], 0)
        self.assertLessEqual(payload["summary"]["visible_metadata_cost"], soft_budget)

    def test_hard_pressure_omits_whole_entries(self):
        baseline = self.run_audit("--context-window", "1000000")
        hard_budget = baseline["summary"]["minimum_name_path_cost"] - 1
        payload = self.run_audit("--context-window", str(hard_budget * 50))

        self.assertEqual(payload["summary"]["state"], "skills_omitted")
        self.assertGreater(payload["summary"]["omitted_skills"], 0)
        self.assertLessEqual(payload["summary"]["visible_metadata_cost"], hard_budget)

    def test_unknown_window_uses_character_fallback_and_marks_approximation(self):
        payload = self.run_audit()

        self.assertEqual(payload["input"]["budget_mode"], "characters")
        self.assertEqual(payload["input"]["budget_limit"], 8000)
        self.assertIn("without_alias_selection", payload["source_model"]["path_model"])
        self.assertIn("modeled_warning_condition", payload["summary"])
        self.assertNotIn("codex_thread_warning_expected", payload["summary"])
        self.assertTrue(
            any("analysis-only scenario input" in row for row in payload["caveats"])
        )

    def test_missing_name_and_malformed_optional_metadata_fail_open(self):
        fallback = self.write_skill("fallback-name", "Fallback fixture.")
        skill_file = fallback / "SKILL.md"
        skill_file.write_text(
            "---\ndescription: Fallback fixture.\n---\n\n# Fixture\n",
            encoding="utf-8",
        )
        agents = fallback / "agents"
        agents.mkdir()
        (agents / "openai.yaml").write_text("policy: [invalid\n", encoding="utf-8")

        payload = self.run_audit("--context-window", "1000000")
        rows = {row["name"]: row for row in payload["skills"]}

        row = rows["fixture-pack:fallback-name"]
        self.assertFalse(row["explicit_only"])
        self.assertTrue(row["unique_plain_name_in_supplied_inventory"])

    def test_plain_name_uniqueness_crosses_plugin_namespaces(self):
        second_plugin = Path(self.tmp.name) / "second-pack"
        manifest = second_plugin / ".codex-plugin"
        manifest.mkdir(parents=True)
        (manifest / "plugin.json").write_text(
            json.dumps({"name": "second-pack"}), encoding="utf-8"
        )
        second_skill = second_plugin / "skills" / "alpha-skill"
        second_skill.mkdir(parents=True)
        (second_skill / "SKILL.md").write_text(
            "---\nname: alpha-skill\ndescription: Second fixture.\n---\n",
            encoding="utf-8",
        )

        payload = self.run_audit_for_paths(
            [self.plugin, second_plugin], "--context-window", "1000000"
        )
        rows = {row["name"]: row for row in payload["skills"]}

        self.assertFalse(
            rows["fixture-pack:alpha-skill"][
                "unique_plain_name_in_supplied_inventory"
            ]
        )
        self.assertFalse(
            rows["second-pack:alpha-skill"][
                "unique_plain_name_in_supplied_inventory"
            ]
        )
        self.assertEqual(
            payload["summary"]["ambiguous_base_skill_names"], ["alpha-skill"]
        )
        self.assertEqual(payload["summary"]["ambiguous_qualified_skill_names"], [])


if __name__ == "__main__":
    unittest.main()
