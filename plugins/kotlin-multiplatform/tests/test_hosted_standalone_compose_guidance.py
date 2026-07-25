from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "kmp-compose-ui" / "SKILL.md"
REFERENCE = (
    ROOT
    / "skills"
    / "kmp-compose-ui"
    / "references"
    / "hosted-standalone-composition.md"
)


class HostedStandaloneComposeGuidanceTest(unittest.TestCase):
    def test_hot_path_routes_to_the_full_contract(self):
        text = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()

        for invariant in (
            "neutral to parent-owned same-axis scrolling and pull-to-refresh",
            "one scroll/pull owner per same-axis or gesture boundary",
            "orthogonal or deliberately coordinated nesting",
            "host own its scroll/pull container",
            "preserve the standalone public facade",
            "published or externally consumed semantics ids",
            "do not widen production visibility or module apis only",
            "references/hosted-standalone-composition.md",
        ):
            self.assertIn(invariant, text)

        self.assertTrue(REFERENCE.is_file())

    def test_reference_preserves_ownership_and_compatibility_nuance(self):
        text = " ".join(REFERENCE.read_text(encoding="utf-8").split()).lower()

        for invariant in (
            "not a blanket ban on nesting",
            "axis, gesture priority, state handoff",
            "do not mount the standalone wrapper",
            "never widen production visibility",
            "not treat every internal test tag",
            "supported meaning, lookup behavior, and expected cardinality",
            "shared supported states, actions, callbacks, and effects",
            "intentional context-specific difference",
            "same public embedding entry point that production uses",
            "a screenshot alone cannot prove gesture ownership",
            "| standalone |",
            "| hosted |",
            "| shared feature behavior |",
            "| external semantics |",
            "| public api and modules |",
            "| coordinated nesting exception |",
            "final source revision",
        ):
            self.assertIn(invariant, text)

    def test_guidance_is_public_safe_ascii(self):
        for path in (SKILL, REFERENCE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            self.assertNotIn("/Users/", text)
            self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
