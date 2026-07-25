from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "kmp-testing-quality" / "SKILL.md"
REFERENCE = ROOT / "references" / "compose-focus-testing.md"


class ComposeFocusTestingGuidanceTest(unittest.TestCase):
    def test_hot_path_routes_to_real_focus_traversal_contract(self):
        text = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()

        for invariant in (
            "real interactive controls",
            "synthetic focus targets",
            "blank focusable sentinels",
            "request and verify keyboard input mode",
            "rejected mode request is not proof",
            "assert each actual destination",
            "focusproperties",
            "screenshot cannot prove keyboard traversal",
            "clean-at-sha",
            "affected-file manifest/content hash",
            "relevant untracked bytes",
            "references/compose-focus-testing.md",
        ):
            self.assertIn(invariant, text)

        self.assertTrue(REFERENCE.is_file())

    def test_reference_preserves_focus_graph_and_evidence_boundaries(self):
        text = " ".join(REFERENCE.read_text(encoding="utf-8").split()).lower()

        for invariant in (
            "test the production focus graph, not a graph invented by the fixture",
            "blank `focusable()` sentinel",
            "existing interactive control",
            "do not widen production visibility or module apis only for the test",
            "request keyboard input mode",
            "verify that the request succeeded",
            "mode as unestablished",
            "`requestfocus()`",
            "`performkeyinput`",
            "`presskey(key.tab)`",
            "`assertisfocused()`",
            "not a universal ordering law",
            "`focusgroup()`",
            "effective focus graph",
            "parent focus properties can override descendant properties",
            "forward traversal",
            "reverse traversal",
            "disabled/hidden skips",
            "complete key press",
            "a tab or arrow-key receipt does not prove rotary or analog-controller input",
            "`performrotaryscrollinput`",
            "screenshot is green but focus test fails",
            "execute the owning target",
            "clean-at-sha revision",
            "manifest/content hash",
            "staged, unstaged, and relevant untracked bytes",
            "explicitly marked uncommitted",
            "do not clean, commit, stash, overwrite",
            "non-empty executed test count",
            "synthetic node",
            "testing compose multiplatform ui",
            "pinned real-control focus test example",
        ):
            self.assertIn(invariant, text)

    def test_guidance_is_public_safe_ascii(self):
        for path in (SKILL, REFERENCE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            lowered = text.lower()
            for private_marker in (
                "/users/",
                "\\users\\",
            ):
                self.assertNotIn(private_marker, lowered, str(path))


if __name__ == "__main__":
    unittest.main()
