from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VISUAL_EXPLANATION = PLUGIN_ROOT / "skills" / "visual-explanation" / "SKILL.md"
ROUTER_SKILL = PLUGIN_ROOT / "skills" / "design-intelligence" / "SKILL.md"
TRIGGER_CASES = Path(__file__).parent / "fixtures" / "visual-explanation-trigger-cases.json"


def normalized_text(text: str) -> str:
    return " ".join(text.lower().split())


def skill_description(text: str) -> str:
    match = re.search(r'^description:\s*"([^"]+)"$', text, re.MULTILINE)
    if match is None:
        raise AssertionError("quoted skill description is missing")
    return normalized_text(match.group(1))


class VisualExplanationSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill_text = VISUAL_EXPLANATION.read_text(encoding="utf-8")
        cls.normalized_skill = normalized_text(cls.skill_text)
        cls.description = skill_description(cls.skill_text)
        cls.fixture = json.loads(TRIGGER_CASES.read_text(encoding="utf-8"))

    def test_trigger_metadata_is_specific_and_bounded(self) -> None:
        for trigger in (
            "visual explanations",
            "coding and technical work",
            "table",
            "tree",
            "call flow",
            "structural diff",
            "wireframe",
        ):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, self.description)
        for boundary in (
            "not for ui screenshot audits",
            "data charts",
            "image assets",
            "architecture recovery",
        ):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary, self.description)

    def test_trigger_probes_define_bounded_positive_and_near_miss_routes(self) -> None:
        self.assertEqual(
            self.fixture["schema"], "visual-explanation.trigger-probes.v1"
        )
        self.assertEqual(self.fixture["skill"], "visual-explanation")
        positives = self.fixture["should_trigger"]
        negatives = self.fixture["should_not_trigger"]
        self.assertEqual(
            {case["id"] for case in positives},
            {
                "branching-logic",
                "explicit-current-topic",
                "field-comparison",
                "layout-wireframe",
                "module-ownership",
                "runtime-sequence",
                "state-transition",
            },
        )
        self.assertEqual(
            {case["id"] for case in negatives},
            {
                "architecture-recovery",
                "focus-mode",
                "image-asset",
                "quantitative-chart",
                "simple-fact",
                "ui-screenshot-audit",
            },
        )
        for case in positives:
            with self.subTest(case=case["id"]):
                self.assertEqual(
                    set(case), {"id", "prompt", "representation", "evidenceLabels"}
                )
                self.assertTrue(case["prompt"].strip())
                self.assertIn(case["representation"], self.normalized_skill)
                self.assertTrue(case["evidenceLabels"])
                self.assertTrue(
                    set(case["evidenceLabels"]) <= {"observed", "given", "proposed"}
                )
        for case in negatives:
            with self.subTest(case=case["id"]):
                self.assertEqual(set(case), {"id", "prompt", "route"})
                self.assertTrue(case["prompt"].strip())
                self.assertIn(case["route"], self.normalized_skill)

    def test_selector_preserves_the_smallest_clear_form(self) -> None:
        for requirement in (
            "if concise prose is equally clear, stop and use concise prose",
            "choose one smallest useful form",
            "table",
            "tree",
            "pseudocode",
            "caller/callee structure without chronology",
            "call tree",
            "short call flow",
            "sequence diagram",
            "state diagram",
            "structural diff",
            "types or signatures",
            "wireframe",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, self.normalized_skill)

    def test_truth_renderer_and_accessibility_boundaries_are_explicit(self) -> None:
        for requirement in (
            "label a view `observed`",
            "label unverified user-supplied material `given` or `reported`",
            "label a view `proposed`",
            "label an inference without adequate verification `assumed`",
            "`given (proposed design)`",
            "file paths, symbols, trace events, or evidence references",
            "mermaid support is unknown or absent",
            "readable text fallback",
            "`acctitle` and `accdescr`",
            "never make color the only carrier of meaning",
            "escape untrusted labels",
            "do not create standalone html, viewers, servers, hooks, or feedback runtimes",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, self.normalized_skill)

    def test_router_exposes_visual_explanation_without_absorbing_neighbors(self) -> None:
        router = normalized_text(ROUTER_SKILL.read_text(encoding="utf-8"))
        self.assertIn("`visual-explanation`", router)
        self.assertIn("technical or coding explanation", router)
        self.assertIn("`visual-communication`", router)
        self.assertIn("screenshot or golden-image evidence boundaries", router)


if __name__ == "__main__":
    unittest.main()
