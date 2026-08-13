import ast
import hashlib
import json
import re
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import plugin_catalog  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LOCAL_PLUGINS = [
    "agent-harness",
    "capability-workbench",
    "context-density",
    "git-workflows",
    "engineering-hygiene",
    "scientific-research",
    "technology-intelligence",
    "design-intelligence",
    "architecture-intelligence",
    "spec-driven-development",
    "kotlin-multiplatform",
    "tauri",
    "pixijs",
    "game-design-intelligence",
]
CATALOG = plugin_catalog.validate_catalog(ROOT)
FIRST_PARTY = {item["name"]: item for item in CATALOG["plugins"]}
PLUGINS = [
    "agent-harness",
    "capability-workbench",
    "context-density",
    "git-workflows",
    "engineering-hygiene",
    "scientific-research",
    "technology-intelligence",
    "design-intelligence",
    "architecture-intelligence",
    "spec-driven-development",
    "build-swift-apps",
    "kotlin-multiplatform",
    "tauri",
    "pixijs",
    "game-design-intelligence",
    "career",
]


class RepoStructureTest(unittest.TestCase):
    def test_every_plugin_has_both_manifests(self):
        for name in LOCAL_PLUGINS:
            claude = ROOT / "plugins" / name / ".claude-plugin" / "plugin.json"
            codex = ROOT / "plugins" / name / ".codex-plugin" / "plugin.json"
            self.assertTrue(claude.is_file(), f"missing {claude}")
            self.assertTrue(codex.is_file(), f"missing {codex}")

    def test_manifest_name_parity(self):
        for name in LOCAL_PLUGINS:
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
            if entry["name"] in FIRST_PARTY:
                plugin = FIRST_PARTY[entry["name"]]
                self.assertEqual(
                    {
                        "source": "github",
                        "repo": plugin["source"]["repository"],
                        "sha": plugin["source"]["commit"],
                    },
                    src,
                )
            else:
                path = ROOT / Path(src.lstrip("./")) if isinstance(src, str) else None
                self.assertTrue(path and path.is_dir(), f"bad source for {entry['name']}")

    def test_external_dependency_lock_is_valid_and_currently_empty(self):
        lock_path = ROOT / "external-dependencies.lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(lock.get("schemaVersion"), 1)

        dependencies = lock.get("dependencies")
        self.assertIsInstance(
            dependencies, list, "external dependency lock must contain a list"
        )
        self.assertEqual(dependencies, [])
        self.assertTrue(
            (ROOT / "scripts" / "external-dependencies.py").is_file(),
            "missing external dependency validator",
        )

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

    def test_agent_harness_contract_exists(self):
        plugin = ROOT / "plugins" / "agent-harness"
        router = (plugin / "skills" / "agent-harness" / "SKILL.md").read_text()
        validator = plugin / "scripts" / "harness" / "validate_harness_artifact.py"
        references = (
            "agent-harness-contracts.md",
            "agent-harness-patterns.md",
            "agent-harness-evaluation.md",
            "agent-harness-landscape.md",
        )

        self.assertTrue(validator.is_file(), "missing Agent Harness validator")
        for name in ("agent-harness-engineering", "agent-harness-evaluation"):
            skill = plugin / "skills" / name / "SKILL.md"
            self.assertTrue(skill.is_file(), f"missing Agent Harness skill {name}")
            self.assertIn(name, router)
            self.assertIn(
                "scripts/harness/validate_harness_artifact.py",
                skill.read_text(),
            )
        engineering = (
            plugin / "skills" / "agent-harness-engineering" / "SKILL.md"
        ).read_text()
        evaluation = (
            plugin / "skills" / "agent-harness-evaluation" / "SKILL.md"
        ).read_text()
        self.assertIn("agent_harness.design.v1", engineering)
        self.assertIn("agent_harness.evaluation_plan.v1", evaluation)
        self.assertIn("agent_harness.run_result.v1", evaluation)
        for name in references:
            self.assertTrue(
                (plugin / "references" / name).is_file(),
                f"missing Agent Harness reference {name}",
            )

    def test_harness_surface_is_not_duplicated_in_capability_workbench(self):
        workbench = ROOT / "plugins" / "capability-workbench"
        retired_paths = (
            workbench / "skills" / "agent-harness-engineering",
            workbench / "skills" / "agent-harness-evaluation",
            workbench / "scripts" / "harness",
            workbench / "references" / "agent-harness-contracts.md",
            workbench / "references" / "agent-harness-patterns.md",
            workbench / "references" / "agent-harness-evaluation.md",
            workbench / "references" / "agent-harness-landscape.md",
        )
        for path in retired_paths:
            self.assertFalse(path.exists(), f"duplicated harness surface: {path}")

    def test_capability_workbench_evaluation_surface_exists(self):
        plugin = ROOT / "plugins" / "capability-workbench"
        skill = plugin / "skills" / "capability-evaluation" / "SKILL.md"
        metadata = skill.parent / "agents" / "openai.yaml"
        reference = plugin / "references" / "capability-evaluation.md"
        validator = plugin / "scripts" / "evaluation" / "validate_capability_evaluation.py"
        router = (plugin / "skills" / "capability-workbench" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        plugin_readme = (plugin / "README.md").read_text(encoding="utf-8")

        for path in (skill, metadata, reference, validator):
            self.assertTrue(path.is_file(), f"missing {path.relative_to(ROOT)}")
        skill_text = skill.read_text(encoding="utf-8")
        self.assertIn("name: capability-evaluation", skill_text)
        self.assertIn("baseline", skill_text.lower())
        self.assertIn("Agent Harness", skill_text)
        self.assertIn("capability-evaluation", router)
        self.assertIn("capability-evaluation", plugin_readme)

        codex = json.loads(
            (plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        for field in ("name", "version", "description", "author", "license", "keywords"):
            self.assertEqual(codex[field], claude[field], f"manifest {field} mismatch")
        self.assertEqual(codex["version"], "0.6.1")
        self.assertIn("Artifact-first agent capability engineering", codex["description"])
        self.assertIn("harness-level evaluation", codex["description"])
        self.assertIn("agent-capability-engineering", codex["keywords"])
        self.assertIn("behavioral-evaluation", codex["keywords"])

        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entry = next(
            item
            for item in marketplace["plugins"]
            if item["name"] == "capability-workbench"
        )
        self.assertEqual(entry["source"], "./plugins/capability-workbench")
        self.assertEqual(entry["description"], codex["description"])

    def test_ai_assisted_code_architecture_surface_exists(self):
        plugin = ROOT / "plugins" / "architecture-intelligence"
        skill_name = "architecture-refactoring-strategy"
        skill = plugin / "skills" / skill_name / "SKILL.md"
        reference = plugin / "references" / "ai-assisted-code-architecture.md"
        fixture = plugin / "tests" / "fixtures" / f"{skill_name}-trigger-probes.json"
        router = (plugin / "skills" / "architecture-intelligence" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        for path in (skill, reference, fixture):
            self.assertTrue(path.is_file(), f"missing {path.relative_to(ROOT)}")
        self.assertIn(skill_name, router)
        self.assertIn("AI-assisted code architecture", router)
        self.assertIn("Agent Harness", router)
        self.assertNotIn("agent-assisted-development-architecture", router)

        probes = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(probes["skill"], skill_name)
        self.assertGreaterEqual(len(probes["should_trigger"]), 6)
        self.assertGreaterEqual(len(probes["should_not_trigger"]), 4)

        codex = json.loads(
            (plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(codex["version"], claude["version"])
        self.assertIn("AI-assisted code architecture", codex["description"])
        self.assertIn("ai-assisted-code-architecture", codex["keywords"])

        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entry = next(
            item
            for item in marketplace["plugins"]
            if item["name"] == "architecture-intelligence"
        )
        self.assertIn("AI-assisted code architecture", entry["description"])

    def test_technology_intelligence_capability_interface_surface_exists(self):
        plugin = ROOT / "plugins" / "technology-intelligence"
        capabilities = json.loads(
            (plugin / "data" / "capabilities.v1.json").read_text(encoding="utf-8")
        )
        interfaces = json.loads(
            (plugin / "data" / "interfaces.v1.json").read_text(encoding="utf-8")
        )
        technologies = json.loads(
            (plugin / "data" / "technologies.v1.json").read_text(encoding="utf-8")
        )
        runtime_schema = json.loads(
            (plugin / "data" / "runtime-capability.schema.v1.json").read_text(
                encoding="utf-8"
            )
        )

        capability_ids = {item["id"] for item in capabilities["capabilities"]}
        technology_by_id = {item["id"]: item for item in technologies["technologies"]}
        anydoc_interfaces = [
            item for item in interfaces["interfaces"] if item["technology_id"] == "anydoc"
        ]
        self.assertIn("document-to-markdown", capability_ids)
        self.assertEqual(["document-to-markdown"], technology_by_id["anydoc"]["capability_ids"])
        self.assertEqual({"cli", "sdk", "skill", "wasm"}, {item["surface"] for item in anydoc_interfaces})
        self.assertEqual("interface_id", runtime_schema["interface_join_key"])

        codex = json.loads(
            (plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual("0.3.0", codex["version"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertIn("Capability-first", codex["description"])

    def test_career_is_a_pinned_standalone_first_party_plugin(self):
        self.assertIn("career", FIRST_PARTY)
        plugin = FIRST_PARTY["career"]
        receipt = plugin_catalog.receipt_for(ROOT, plugin)
        expected_skills = {
            "career",
            "career-context",
            "career-direction",
            "career-market-research",
            "opportunity-search",
            "opportunity-analysis",
            "career-materials",
            "application-tailoring",
            "application-assistance",
            "application-campaign",
            "career-inbox",
            "career-networking",
            "recruiter-coordination",
            "interview-preparation",
            "offer-negotiation",
            "career-pipeline",
            "career-operations",
            "career-data-governance",
            "career-development",
            "career-source-adapter",
        }
        actual_skills = {item["name"] for item in receipt["skills"]["items"]}
        self.assertEqual(expected_skills, actual_skills)
        self.assertEqual("Xopoko/career-skills", plugin["source"]["repository"])
        self.assertRegex(plugin["source"]["commit"], r"^[0-9a-f]{40}$")
        self.assertFalse((ROOT / "plugins" / "career").exists())

    def test_retired_plugin_directories_are_absent(self):
        for name in ("codex-cli", "claude-code", "scheduled-automation"):
            self.assertFalse(
                (ROOT / "plugins" / name).exists(),
                f"retired top-level plugin directory still exists: {name}",
            )

    def test_readme_dashboard_header_renderer_exists(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("assets/plugin-dashboard-header.webp", readme)
        self.assertTrue(
            (ROOT / "assets" / "plugin-dashboard-background.png").is_file(),
            "missing generated dashboard background",
        )
        self.assertTrue(
            (ROOT / "assets" / "plugin-dashboard-background-prompt.md").is_file(),
            "missing dashboard background prompt provenance",
        )
        self.assertTrue(
            (ROOT / "assets" / "plugin-dashboard-header.webp").is_file(),
            "missing rendered dashboard header",
        )
        self.assertFalse(
            (ROOT / "assets" / "plugin-dashboard-header.png").exists(),
            "superseded PNG dashboard header should not be retained",
        )
        for font_asset in ("InterVariable.ttf", "LICENSE.txt", "SOURCE.md"):
            self.assertTrue(
                (ROOT / "assets" / "fonts" / "inter" / font_asset).is_file(),
                f"missing dashboard font asset {font_asset}",
            )
        font = ROOT / "assets" / "fonts" / "inter" / "InterVariable.ttf"
        self.assertEqual(
            hashlib.sha256(font.read_bytes()).hexdigest(),
            "4989b125924991b90d05b2d16e0e388c48f7d5bb8b30539bbf9c755278d0ccaf",
        )
        background = ROOT / "assets" / "plugin-dashboard-background.png"
        background_prompt = (
            ROOT / "assets" / "plugin-dashboard-background-prompt.md"
        ).read_text()
        self.assertIn(
            hashlib.sha256(background.read_bytes()).hexdigest(),
            background_prompt,
        )
        self.assertTrue(
            (ROOT / "scripts" / "render_plugin_dashboard_header.py").is_file(),
            "missing dashboard header renderer",
        )

    def test_dashboard_layout_matches_the_canonical_three_row_catalog(self):
        renderer = ROOT / "scripts" / "render_plugin_dashboard_header.py"
        tree = ast.parse(renderer.read_text(encoding="utf-8"))
        assignments = {
            target.id: ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and target.id in {"PLUGIN_LAYOUT_ROWS", "PLUGIN_SUMMARIES"}
        }

        rows = assignments["PLUGIN_LAYOUT_ROWS"]
        summaries = assignments["PLUGIN_SUMMARIES"]
        flattened = [name for row in rows for name in row]
        self.assertEqual([5, 5, 6], [len(row) for row in rows])
        self.assertEqual(PLUGINS, flattened)
        self.assertEqual(set(PLUGINS), set(summaries))

    def test_readme_token_report_generator_exists(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("scripts/token-report.py", readme)
        self.assertTrue(
            (ROOT / "scripts" / "token-report.py").is_file(),
            "missing token report generator",
        )

    def test_pull_request_merge_gate_is_current_head_bound(self):
        guidance = (ROOT / "AGENTS.md").read_text()
        heading = "## Pull Request Merge Gate"
        _, found_heading, remainder = guidance.partition(heading)
        self.assertEqual(found_heading, heading, "missing Pull Request Merge Gate")
        section = remainder.partition("## ")[0]
        normalized = " ".join(re.findall(r"[a-z0-9]+", section.lower()))

        section.encode("ascii")
        for required_contract in (
            r"merge authority.*merge readiness.*separate",
            r"same immutable pull request head h",
            r"required ci for h.*terminal.*successful",
            r"running.*skipped.*cancelled.*failed.*unbound.*do not satisfy",
            r"completed codex review.*covers h",
            r"completed copilot review.*covers h",
            (
                r"after both bot reviews.*complete final reread.*all review "
                r"comments and threads.*for h.*address every actionable finding"
            ),
            (
                r"immediately before merge.*reread.*pull request head.*"
                r"complete comment thread inventory"
            ),
            (
                r"any head change or any new or edited actionable comment "
                r"after the final reread invalidates readiness"
            ),
            (
                r"re run.*affected ci.*bot review gates.*new head.*"
                r"repeat.*final reread"
            ),
            (
                r"if either bot is unavailable or its current head receipt "
                r"cannot be proven hold the pull request do not merge"
            ),
            (
                r"perform the merge only with an expected head compare and swap "
                r"bound to h.*server side condition.*rejects atomically.*current "
                r"pull request head differs from h.*pre merge reread is not enough.*"
                r"never fall back to an unguarded merge primitive"
            ),
        ):
            self.assertRegex(normalized, required_contract)


if __name__ == "__main__":
    unittest.main()
