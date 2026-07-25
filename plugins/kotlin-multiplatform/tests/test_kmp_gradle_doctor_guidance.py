from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRADLE_DOCTOR = ROOT / "skills" / "kmp-gradle-doctor" / "SKILL.md"
ROUTER = ROOT / "skills" / "kotlin-multiplatform" / "SKILL.md"
ENVIRONMENT_READINESS = ROOT / "references" / "environment-readiness.md"


class KmpGradleDoctorGuidanceTest(unittest.TestCase):
    def test_private_dependency_access_is_bounded_and_evidence_based(self):
        skill = " ".join(GRADLE_DOCTOR.read_text(encoding="utf-8").split()).lower()
        router = " ".join(ROUTER.read_text(encoding="utf-8").split()).lower()
        reference = " ".join(
            ENVIRONMENT_READINESS.read_text(encoding="utf-8").split()
        ).lower()

        self.assertIn("../../references/environment-readiness.md", skill)
        for trigger in (
            "private dependency resolution or consumption failures",
            "private gradle/maven dependency resolution or consumption failures",
            "artifact-consuming wrapper task",
        ):
            self.assertIn(trigger, skill)
        for near_miss in (
            "publishing-repository configuration",
            "creating or rotating credentials",
            "broad repository administration",
        ):
            self.assertIn(near_miss, skill)

        for state in (
            "`ready`",
            "`auth-blocked`",
            "`network/repository-blocked`",
            "`artifact-or-coordinate-unknown`",
            "`integrity-blocked`",
            "`variant-incompatible`",
            "`unproven`",
        ):
            self.assertIn(state, reference)

        for boundary in (
            "does not prove that the current principal can read the artifact",
            "an offline success proves only",
            "an offline miss proves only cache absence",
            "a warm online success can still be cache-backed",
            "cache-only or warm-cache evidence is `unproven`, never `ready`",
            "a `404` alone is ambiguous",
            "local process and ci as separate execution surfaces",
            "never read, print, echo, serialize, or compare the credential value",
            "without streaming raw output into an agent",
            "do not use `tee`, `cat`, or a model-visible tool",
            "trusted project-owned sanitizer",
            "do not add `--debug`, a public build scan, `clean`, cache deletion",
            "retry only after a relevant change",
            "graph or metadata resolution does not prove artifact materialization",
            "never claim repository-wide or durable access from one artifact receipt",
        ):
            self.assertIn(boundary, reference)

        self.assertIn(
            "do not open `gradle.properties` or run the generic inspection flow first",
            skill,
        )
        for safe_field in (
            "`gradle_properties_present`",
            "`gradle_property_keys`",
            "from schema-v2 inspector output",
        ):
            self.assertIn(safe_field, skill)
        self.assertNotIn(
            "- `gradle.properties`",
            GRADLE_DOCTOR.read_text(encoding="utf-8"),
        )
        for router_boundary in (
            "private dependency resolution or consumption failure",
            "skip this generic first move",
            "do not open `gradle.properties` or run the inspector first",
        ):
            self.assertIn(router_boundary, router)
        self.assertNotIn(
            "`gradle.properties`,",
            ROUTER.read_text(encoding="utf-8"),
        )

        for capture_boundary in (
            "freshly created mode-`0700` directory",
            "exclusive, no-follow mode-`0600` file",
            "mktemp -d",
            'test -n "$kmp_access_dir" || exit 1',
            'chmod 700 "$kmp_access_dir" || exit 1',
            "set -o noclobber",
            "never use a wildcard or shared-path cleanup",
            "artifact materialization and remote access remain unproven",
        ):
            self.assertIn(capture_boundary, reference)

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
        for path in (GRADLE_DOCTOR, ROUTER, ENVIRONMENT_READINESS):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii())
            self.assertNotIn("/Users/", text)
            self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
