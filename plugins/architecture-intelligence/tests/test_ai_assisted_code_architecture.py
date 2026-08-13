from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
SKILL = ROOT / "skills" / "architecture-refactoring-strategy" / "SKILL.md"
REFERENCE = ROOT / "references" / "ai-assisted-code-architecture.md"
CONTRACTS = ROOT / "references" / "contracts.md"
FIXTURE = ROOT / "tests" / "fixtures" / "architecture-refactoring-strategy-trigger-probes.json"


def frontmatter_value(text: str, key: str) -> str:
    lines = text.splitlines()
    prefix = f"{key}:"
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        value = line.split(":", 1)[1].strip()
        if value in {">", ">-", "|", "|-"}:
            parts = []
            for continuation in lines[index + 1 :]:
                if not continuation.startswith("  "):
                    break
                parts.append(continuation.strip())
            return " ".join(parts)
        return value.strip("\"'")
    raise AssertionError(f"missing frontmatter key: {key}")


class AiAssistedCodeArchitectureTest(unittest.TestCase):
    def test_existing_skill_trigger_is_code_architecture_first(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertEqual(frontmatter_value(text, "name"), "architecture-refactoring-strategy")
        description = frontmatter_value(text, "description")
        self.assertLessEqual(len(description), 240)
        lowered = description.lower()
        for signal in (
            "incremental code-boundary changes",
            "characterization tests",
            "per-slice proof",
            "fitness functions",
            "rollback",
            "before/after evidence",
        ):
            self.assertIn(signal, lowered)
        for boundary in ("routine cleanup", "agent-runtime design"):
            self.assertIn(boundary, lowered)

    def test_trigger_probes_cover_code_architecture_and_near_misses(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "architecture_intelligence.trigger_probes.v1")
        self.assertEqual(payload["skill"], "architecture-refactoring-strategy")
        self.assertEqual(len(payload["should_trigger"]), 8)
        self.assertEqual(len(payload["should_not_trigger"]), 7)
        positive_ids = {item["id"] for item in payload["should_trigger"]}
        negative_ids = {item["id"] for item in payload["should_not_trigger"]}
        self.assertEqual(len(positive_ids), 8)
        self.assertEqual(len(negative_ids), 7)
        self.assertTrue(positive_ids.isdisjoint(negative_ids))
        routes = {item["route"] for item in payload["should_not_trigger"]}
        for route in (
            "codebase-architecture-audit",
            "architecture-decisions",
            "architecture-fitness-functions",
            "async-state-consistency",
            "agent-harness",
            "context-density",
        ):
            self.assertIn(route, routes)

    def test_hot_path_executes_one_code_architecture_slice_at_a_time(self):
        compact = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "architecture of the application or library code",
            "ai-assisted code architecture",
            "coding agents are tools",
            "one smallest behavior-preserving architecture slice",
            "separate requested behavior from incidental refactoring",
            "review findings before mutation",
            "functional proof and architecture proof",
            "same architecture method",
        ):
            self.assertIn(invariant, compact)

    def test_reference_has_direct_evidence_rubric_workflow_and_limits(self):
        text = REFERENCE.read_text(encoding="utf-8")
        compact = " ".join(text.split()).lower()
        scenario_ids = {
            line.split("|")[1].strip()
            for line in text.splitlines()
            if line.startswith("| AICA-")
        }
        self.assertEqual(scenario_ids, {f"AICA-{index:02d}" for index in range(1, 11)})
        for signal in (
            "the architecture of application and library code",
            "source shape is evidence, not design authority",
            "plausible-but-wrong implementation path",
            "callers and callees",
            "boundary_edges_before",
            "architecture_fitness_proof",
            "review before fixing",
        ):
            self.assertIn(signal, compact)
        for source in (
            "https://arxiv.org/abs/2606.14948",
            "https://doi.org/10.1109/MS.2026.3663353",
            "https://arxiv.org/abs/2605.22526",
            "https://arxiv.org/abs/2608.09802",
            "https://arxiv.org/abs/2608.09290",
        ):
            self.assertIn(source, text)
        for limitation in (
            "without reported agreement with independent human architects",
            "no longitudinal controlled study",
            "agent runtime behavior, not code architecture",
            "no independent human replication",
        ):
            self.assertIn(limitation, compact)

    def test_contract_and_architecture_skills_link_the_evidence_path(self):
        contracts = CONTRACTS.read_text(encoding="utf-8")
        self.assertIn("Optional `architecture_assessment` appendix", contracts)
        for relative in (
            "skills/codebase-architecture-audit/SKILL.md",
            "skills/architecture-conformance/SKILL.md",
            "skills/architecture-refactoring-strategy/SKILL.md",
            "skills/architecture-fitness-functions/SKILL.md",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("ai-assisted-code-architecture.md", text)

    def test_publication_surfaces_position_ai_as_code_architecture_assistance(self):
        router = (ROOT / "skills" / "architecture-intelligence" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("AI-assisted code architecture", router)
        self.assertNotIn("agent-assisted-development-architecture", router)

        codex_manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude_manifest = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(codex_manifest["version"], "0.1.13")
        self.assertEqual(codex_manifest["version"], claude_manifest["version"])
        for manifest in (codex_manifest, claude_manifest):
            self.assertIn("AI-assisted code architecture", manifest["description"])
            self.assertIn("ai-assisted-code-architecture", manifest["keywords"])

        marketplace = json.loads(
            (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entry = next(
            item for item in marketplace["plugins"] if item["name"] == "architecture-intelligence"
        )
        self.assertIn("AI-assisted code architecture", entry["description"])
        root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("AI-assisted code architecture", root_readme)

    def test_new_capability_files_are_public_safe_ascii(self):
        for path in (SKILL, REFERENCE, FIXTURE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            self.assertNotRegex(text, re.compile(r"(?:/|\\)Users(?:/|\\)"))


if __name__ == "__main__":
    unittest.main()
