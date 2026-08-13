from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "git-commit-signing-recovery" / "SKILL.md"
REFERENCE = (
    ROOT
    / "skills"
    / "git-commit-signing-recovery"
    / "references"
    / "recovery-contract.md"
)
OPENAI = (
    ROOT
    / "skills"
    / "git-commit-signing-recovery"
    / "agents"
    / "openai.yaml"
)
TRIGGERS = ROOT / "tests" / "fixtures" / "signing-trigger-cases.json"
CODEX_MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
PLUGIN_README = ROOT / "README.md"


def compact(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split()).lower()


class GitCommitSigningGuidanceTests(unittest.TestCase):
    def test_frontmatter_anchors_trigger_and_negative_boundaries(self):
        text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = " ".join(match.group(1).split()).lower()
        for cue in (
            "git commit",
            "before ref advancement",
            "ssh signer",
            "agent, socket, or helper",
            "staged state",
            "one verified retry",
        ):
            self.assertIn(cue, frontmatter)
        for boundary in (
            "hooks",
            "conflicts",
            "remote auth",
            "non-ssh signing",
            "amend/merge/rebase",
        ):
            self.assertIn(boundary, frontmatter)

    def test_trigger_fixture_has_bounded_positive_and_negative_coverage(self):
        payload = json.loads(TRIGGERS.read_text(encoding="utf-8"))
        positives = payload["should_trigger"]
        negatives = payload["should_not_trigger"]
        self.assertGreaterEqual(len(positives), 6)
        self.assertLessEqual(len(positives), 9)
        self.assertGreaterEqual(len(negatives), 6)
        self.assertLessEqual(len(negatives), 9)
        self.assertEqual(
            sum(bool(item.get("buried_need")) for item in positives),
            1,
        )
        self.assertEqual(
            len({item["id"] for item in positives + negatives}),
            len(positives) + len(negatives),
        )
        negative_cues = {
            "hook-failure": "pre-commit hook",
            "invocation-override": "core.hookspath=/alternate commit -a",
            "index-corruption": "corrupt index",
            "remote-authentication": "push cannot authenticate",
            "artifact-signing": "release artifact",
            "key-rotation": "rotate trust policy",
            "sequencer-operation": "rebase or cherry-pick",
            "unsupported-commit-mode": "amend, merge, empty, editor, template",
            "unsupported-openpgp": "openpgp or x.509",
        }
        self.assertEqual(
            {item["id"] for item in negatives},
            set(negative_cues),
        )
        for item in negatives:
            self.assertIn(
                negative_cues[item["id"]],
                item["prompt"].lower(),
            )
        for item in positives:
            self.assertIn("ssh", item["prompt"].lower())
        hooks_passed = next(
            item
            for item in positives
            if item["id"] == "hooks-passed-before-signer-failure"
        )
        self.assertIn("hooks completed successfully", hooks_passed["prompt"])

    def test_skill_and_reference_keep_fail_closed_recovery_explicit(self):
        skill = compact(SKILL)
        reference = compact(REFERENCE)
        for phrase in (
            "required and unknown policy fail closed",
            "one-command signer-program override",
            "same trusted key identity",
            "another linked worktree or ref at the same commit is not equivalent",
            "retry the exact signed commit at most once",
            "unsigned_fallback_allowed",
            "namespaced baseline and consumed-token records",
            "post-commit receipt verified",
        ):
            self.assertIn(phrase, skill)
        for phrase in (
            "`signer-failure`",
            "`sequencer-operation`",
            "`remote-auth-failure`",
            "receipt proves only consistency with the state observed",
            "`--signer-probe verified`",
            "`--commit-shape verified-plain-index`",
            "caller-supplied evidence",
            "sole retry exception",
            "one-retry rule",
            "hostile process running as the same local principal",
            "observed signer identity matches",
            "`git verify-commit`",
            "replacement refs",
            "legacy grafts",
            "repository-configured clean, smudge, and process filters are not executed",
            "raw tracked-worktree content",
            "`skip-worktree` and `assume-unchanged` flags",
            "symbolic branch or detached-head identity",
            "remote publication",
        ):
            self.assertIn(phrase, reference)

    def test_interfaces_and_manifests_are_aligned(self):
        codex = json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))
        claude = json.loads(CLAUDE_MANIFEST.read_text(encoding="utf-8"))
        for field in ("name", "version", "description", "author", "license", "keywords"):
            self.assertEqual(codex[field], claude[field])
        self.assertEqual(codex["name"], "git-workflows")
        self.assertEqual(codex["version"], "0.1.1")
        self.assertEqual(codex["interface"]["displayName"], "Git Workflows")
        self.assertIn(
            "SSH-signed-commit",
            " ".join(codex["interface"]["capabilities"]),
        )

        openai = OPENAI.read_text(encoding="utf-8")
        self.assertIn('display_name: "Git Commit Signing Recovery"', openai)
        self.assertIn("$git-commit-signing-recovery", openai)
        self.assertIn("git-commit-signing-recovery", PLUGIN_README.read_text())

    def test_public_source_contains_no_private_or_host_specific_details(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SKILL, REFERENCE, OPENAI, TRIGGERS)
        )
        for forbidden in (
            "/private/home/",
            "private-organization",
            "private-project",
            "private-thread-id",
            "private-key-fingerprint",
        ):
            self.assertNotIn(forbidden, combined)
        combined.encode("ascii")


if __name__ == "__main__":
    unittest.main()
