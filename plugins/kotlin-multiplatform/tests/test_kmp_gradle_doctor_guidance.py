from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRADLE_DOCTOR = ROOT / "skills" / "kmp-gradle-doctor" / "SKILL.md"


class KmpGradleDoctorGuidanceTest(unittest.TestCase):
    def test_static_analysis_tool_crash_is_fail_closed(self):
        text = " ".join(GRADLE_DOCTOR.read_text(encoding="utf-8").split()).lower()

        for classification_input in (
            "reported finding",
            "task/configuration failure",
            "environment/dependency failure",
            "tool crash",
            "exact task or entrypoint",
            "tool/plugin version",
            "jdk and kotlin versions",
            "config and baseline inputs",
            "project-pinned task",
            "standalone binary",
            "exact binary and config",
            "disposable directory",
            "same failure fingerprint",
            "last known-good input",
            "parser avoidance",
            "suppressing a rule",
            "excluding a source",
            "disabling the analyzer",
            "unproven syntax-only edit",
            "diagnostic experiment, not acceptance proof",
        ):
            self.assertIn(classification_input, text)

        for required_directive in (
            "before publishing another code head, require positive local evidence "
            "that the pinned analyzer executes and accepts the candidate",
            "the candidate remains unproven until remote ci reports terminal "
            "success with non-empty execution of the same analyzer and config on "
            "the immutable exact published head",
            "if that published head retains the same tool-crash fingerprint after "
            "a local pass, the local reproducer is non-equivalent",
            "stop further code publication until evidence identifies a relevant "
            "difference",
            "another source edit alone is not new evidence",
        ):
            self.assertIn(required_directive, text)

        for contradictory_directive in (
            "do not require positive local evidence",
            "need not require positive local evidence",
            "do not stop further code publication",
            "remote ci success is optional",
            "empty execution is proof",
        ):
            self.assertNotIn(contradictory_directive, text)

    def test_guidance_is_public_safe_ascii(self):
        text = GRADLE_DOCTOR.read_text(encoding="utf-8")
        self.assertTrue(text.isascii())
        self.assertNotIn("/Users/", text)
        self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
