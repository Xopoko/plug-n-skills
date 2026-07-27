from __future__ import annotations

import re
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VISUAL_SKILL = PLUGIN_ROOT / "skills" / "visual-communication" / "SKILL.md"
ROUTER_SKILL = PLUGIN_ROOT / "skills" / "design-intelligence" / "SKILL.md"


def normalized_text(text: str) -> str:
    return " ".join(text.lower().split())


def skill_description(text: str) -> str:
    match = re.search(r'^description:\s*"([^"]+)"$', text, re.MULTILINE)
    if match is None:
        raise AssertionError("quoted skill description is missing")
    return normalized_text(match.group(1))


def markdown_section(text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    if marker not in text:
        raise AssertionError(f"missing section: {heading}")
    return normalized_text(text.split(marker, 1)[1].split("\n## ", 1)[0])


class VisualCommunicationSkillContractTests(unittest.TestCase):
    def test_contract_matching_ignores_markdown_reflow(self) -> None:
        self.assertEqual(
            "compare only equivalent states",
            normalized_text("compare  only\n\tequivalent   states"),
        )

    def test_trigger_metadata_routes_visual_evidence_review(self) -> None:
        description = skill_description(VISUAL_SKILL.read_text(encoding="utf-8"))

        for trigger in ("ui screenshots", "golden images", "visual diffs", "capture state"):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, description)
        self.assertIn("test-harness artifacts", description)
        self.assertIn("do not use for screenshot generation/export", description)

    def test_screenshot_evidence_requires_state_and_causal_boundaries(self) -> None:
        text = VISUAL_SKILL.read_text(encoding="utf-8")
        section = markdown_section(text, "Screenshot Evidence Boundary")

        for requirement in (
            "exact rendered build or artifact",
            "provenance to the source revision",
            "capture harness",
            "scroll position",
            "capture order",
            "precondition, interaction, capture",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, section)
        self.assertIn("compare only equivalent states", section)
        self.assertIn("does not by itself prove a product layout defect", section)
        self.assertIn("keep the cause `unknown` until affirmative evidence establishes it", section)
        self.assertIn("classify `harness` or `product` only when", section)
        self.assertIn("a harness defect can still invalidate a visual acceptance artifact", section)
        self.assertIn("use synthetic or allowlisted data", section)
        self.assertIn("redact secrets", section)
        self.assertIn("keep unavoidable raw evidence private", section)

    def test_router_exposes_the_visual_evidence_boundary(self) -> None:
        router = normalized_text(ROUTER_SKILL.read_text(encoding="utf-8"))

        self.assertIn("screenshot or golden-image evidence boundaries", router)


if __name__ == "__main__":
    unittest.main()
