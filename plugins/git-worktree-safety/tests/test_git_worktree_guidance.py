from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "git-worktree-recovery" / "SKILL.md"
REFERENCE = (
    ROOT
    / "skills"
    / "git-worktree-recovery"
    / "references"
    / "recovery-contract.md"
)
OPENAI = ROOT / "skills" / "git-worktree-recovery" / "agents" / "openai.yaml"
TRIGGERS = ROOT / "tests" / "fixtures" / "trigger-cases.json"
CODEX_MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
ICON_PROMPT = ROOT / "assets" / "icon-prompt.json"


def compact(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split()).lower()


class GitWorktreeGuidanceTests(unittest.TestCase):
    def test_frontmatter_anchors_trigger_and_negative_boundaries(self):
        text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = " ".join(match.group(1).split()).lower()
        for cue in (
            "expected git worktree path",
            "convenience symlink",
            "missing, stale, or broken",
            "registered replacement",
            "branch-ref",
            "reflog-only",
            "object-only",
            "exact symlink repair",
        ):
            self.assertIn(cue, frontmatter)
        for boundary in (
            "git administrative worktree repair",
            "creation/removal/pruning",
            "ref restoration",
            "checkout/reset",
            "stacked-change restacking",
            "host-specific session orchestration",
            "recovery of unsaved content",
            "arbitrary non-git symlink repair",
        ):
            self.assertIn(boundary, frontmatter)

    def test_trigger_fixture_has_bounded_positive_and_negative_coverage(self):
        payload = json.loads(TRIGGERS.read_text(encoding="utf-8"))
        positives = payload["should_trigger"]
        negatives = payload["should_not_trigger"]
        self.assertGreaterEqual(len(positives), 6)
        self.assertLessEqual(len(positives), 10)
        self.assertGreaterEqual(len(negatives), 4)
        self.assertLessEqual(len(negatives), 8)
        self.assertEqual(
            sum(bool(item.get("buried_need")) for item in positives),
            1,
        )
        self.assertEqual(
            len({item["id"] for item in positives + negatives}),
            len(positives) + len(negatives),
        )
        negative_by_id = {item["id"]: item["prompt"].lower() for item in negatives}
        native_repair = negative_by_id["administrative-worktree-repair"]
        self.assertIn("git worktree repair", native_repair)
        self.assertIn("moved the main or a linked worktree", native_repair)
        self.assertIn("administrative paths", native_repair)
        self.assertIn("uncommitted", negative_by_id["unsaved-content-recovery"])
        self.assertIn("untracked", negative_by_id["unsaved-content-recovery"])
        self.assertIn("no retained commit", negative_by_id["unsaved-content-recovery"])
        self.assertIn("arbitrary broken symlink", negative_by_id["non-git-symlink"])
        self.assertIn("no git repository", negative_by_id["non-git-symlink"])

    def test_skill_and_reference_keep_the_mutation_boundary_explicit(self):
        skill = compact(SKILL)
        reference = compact(REFERENCE)
        for phrase in (
            "one unique registered replacement",
            "head` equal to the live branch ref",
            "clean porcelain-v2 status including untracked files",
            "no locked or prunable annotation",
            "reflog-only or object-only retention is salvage evidence",
            "uncommitted, untracked, or ignored content",
            "repair only a verified broken symlink",
            "never create, add, move, remove, prune, repair, unlock, or delete "
            "worktrees",
            "raw absolute paths",
        ):
            self.assertIn(phrase, skill)
        for phrase in (
            "`branch-reachable`",
            "`reflog-only`",
            "`object-only`",
            "`retention-unknown`",
            "git operation is already in progress",
            "outside every registered worktree",
            "directory-anchored compare-and-swap-style guard",
            "predicate-and-replace",
            "`postcondition-unavailable`",
            "`mutation_performed: true`",
            "missing_target_uncommitted_state_unverifiable",
            "raw absolute paths",
        ):
            self.assertIn(phrase, reference)

    def test_manifests_and_icon_contract_are_aligned(self):
        codex = json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))
        claude = json.loads(CLAUDE_MANIFEST.read_text(encoding="utf-8"))
        for field in ("name", "version", "description", "author", "license", "keywords"):
            self.assertEqual(codex[field], claude[field])
        self.assertEqual(codex["version"], "0.1.0")
        interface = codex["interface"]
        self.assertEqual(interface["brandColor"], "#143C45")
        self.assertEqual(interface["composerIcon"], "./assets/icon.png")
        self.assertEqual(interface["logo"], "./assets/icon.png")
        self.assertTrue((ROOT / "assets" / "icon.png").is_file())

        prompt = json.loads(ICON_PROMPT.read_text(encoding="utf-8"))
        self.assertEqual(prompt["brandColor"], "#143C45")
        self.assertEqual(prompt["recommended_asset_path"], "assets/icon.png")
        self.assertIn("Text (verbatim): none.", prompt["prompt"])

    def test_openai_interface_and_public_source_are_safe(self):
        self.assertIn(
            "$git-worktree-recovery",
            OPENAI.read_text(encoding="utf-8"),
        )
        paths = (
            SKILL,
            REFERENCE,
            OPENAI,
            TRIGGERS,
            CODEX_MANIFEST,
            CLAUDE_MANIFEST,
            ICON_PROMPT,
            ROOT / "README.md",
        )
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            self.assertNotIn("/Users/", text)
            self.assertNotIn("\\Users\\", text)
            self.assertNotIn("BEGIN PRIVATE KEY", text)


if __name__ == "__main__":
    unittest.main()
