from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "kmp-testing-quality" / "SKILL.md"


class DiFixtureDiagnosticsGuidanceTest(unittest.TestCase):
    def test_generic_di_failure_requires_observed_missing_edge(self):
        text = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()

        for invariant in (
            "generic dependency-injection exception as a symptom",
            "not as proof of which binding is missing",
            "do not add a guessed fallback",
            "project-pinned task",
            "exact test filter",
            "full exception chain or stack trace",
            "exact requested type, qualifier, scope, parameter path",
            "active module set",
            "production graph from test-only modules",
            "test-only binding only when the observed missing edge belongs to the harness",
            "never add an unrelated production fallback",
            "remove every disproven diagnostic binding",
            "a new exception is a new failure",
            "publication is explicitly authorized",
            "diagnostic-only immutable revision",
            "without that authority",
            "do not commit, push, or trigger ci",
            "terminal failure identifies evidence; it is not a source fix",
            "remove the diagnostic configuration before final acceptance",
        ):
            self.assertIn(invariant, text)

    def test_guidance_is_public_safe_ascii(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertTrue(text.isascii())
        self.assertNotIn("/Users/", text)
        self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
