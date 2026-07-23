import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = [
    "build-swift-apps",
    "pixijs",
    "tauri",
    "scientific-research",
    "context-density",
    "capability-workbench",
    "codex-cli",
    "scheduled-automation",
    "gitlab-review",
    "claude-code",
    "architecture-intelligence",
    "design-intelligence",
    "game-design-intelligence",
    "kotlin-multiplatform",
    "spec-driven-development",
]


class RepoStructureTest(unittest.TestCase):
    def test_every_plugin_has_both_manifests(self):
        for name in PLUGINS:
            claude = ROOT / "plugins" / name / ".claude-plugin" / "plugin.json"
            codex = ROOT / "plugins" / name / ".codex-plugin" / "plugin.json"
            self.assertTrue(claude.is_file(), f"missing {claude}")
            self.assertTrue(codex.is_file(), f"missing {codex}")

    def test_manifest_name_parity(self):
        for name in PLUGINS:
            for marker in (".claude-plugin", ".codex-plugin"):
                data = json.loads(
                    (ROOT / "plugins" / name / marker / "plugin.json").read_text()
                )
                self.assertEqual(data.get("name"), name,
                                 f"{name}/{marker} name mismatch")

    def test_root_marketplace_lists_all_plugins(self):
        mp = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        listed = {p["name"] for p in mp["plugins"]}
        self.assertEqual(listed, set(PLUGINS))
        for entry in mp["plugins"]:
            src = entry["source"]
            path = ROOT / Path(src.lstrip("./")) if isinstance(src, str) else None
            self.assertTrue(path and path.is_dir(), f"bad source for {entry['name']}")

    def test_gitignore_keeps_local_work_products_private(self):
        gitignore = (ROOT / ".gitignore").read_text()
        for pattern in (
            ".agents/",
            "research/",
            "skill-synthesis/",
            "docs/superpowers/",
            "plugins/*/synthesis/",
            "plugins/*/reports/",
            "output/",
            "scratch/",
        ):
            self.assertIn(pattern, gitignore)

    def test_capability_workbench_icon_generation_contract_exists(self):
        plugin = ROOT / "plugins" / "capability-workbench"
        reference = plugin / "references" / "plugin-icon-system.md"
        prompt_helper = plugin / "scripts" / "plugin" / "prepare_plugin_icon_prompt.py"
        wire_helper = plugin / "scripts" / "plugin" / "wire_plugin_icon.py"
        factory = plugin / "skills" / "plugin-factory" / "SKILL.md"

        self.assertTrue(reference.is_file(), "missing Workbench icon system reference")
        self.assertTrue(prompt_helper.is_file(), "missing Workbench icon prompt helper")
        self.assertTrue(wire_helper.is_file(), "missing Workbench icon manifest helper")
        self.assertIn("$imagegen", factory.read_text())

    def test_readme_dashboard_header_renderer_exists(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("assets/plugin-dashboard-header.png", readme)
        self.assertTrue(
            (ROOT / "assets" / "plugin-dashboard-background.png").is_file(),
            "missing generated dashboard background",
        )
        self.assertTrue(
            (ROOT / "assets" / "plugin-dashboard-header.png").is_file(),
            "missing rendered dashboard header",
        )
        self.assertTrue(
            (ROOT / "scripts" / "render_plugin_dashboard_header.py").is_file(),
            "missing dashboard header renderer",
        )

    def test_readme_token_report_generator_exists(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("scripts/token-report.py", readme)
        self.assertTrue(
            (ROOT / "scripts" / "token-report.py").is_file(),
            "missing token report generator",
        )


if __name__ == "__main__":
    unittest.main()
