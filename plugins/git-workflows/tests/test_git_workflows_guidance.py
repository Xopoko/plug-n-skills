from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "forge-code-review" / "SKILL.md"
OPENAI = ROOT / "skills" / "forge-code-review" / "agents" / "openai.yaml"
README = ROOT / "README.md"
CONTRACT = ROOT / "references" / "forge-adapter-contract.md"
SELECTOR = ROOT / "scripts" / "forge_adapter_selector.py"
CODEX = ROOT / ".codex-plugin" / "plugin.json"
CLAUDE = ROOT / ".claude-plugin" / "plugin.json"


class GitWorkflowsGuidanceTests(unittest.TestCase):
    def test_consolidated_skill_inventory_is_complete(self):
        expected = {
            "forge-code-review",
            "gitlab-review-response",
            "stacked-change-delivery",
            "git-worktree-recovery",
            "git-commit-signing-recovery",
        }
        actual = {
            path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")
        }
        self.assertEqual(actual, expected)

    def test_forge_code_review_trigger_is_read_only_and_link_scoped(self):
        text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        self.assertIsNotNone(match)
        frontmatter = " ".join(match.group(1).split()).lower()
        for phrase in (
            "read-only review",
            "github pr",
            "gitlab mr",
            "mcp, connector, cli, or rest",
            "never posts, approves, resolves, merges, pushes, edits",
        ):
            self.assertIn(phrase, frontmatter)
        for boundary in (
            "broad repository audits",
        ):
            self.assertIn(boundary, frontmatter)

    def test_read_only_skill_forbids_every_remote_write_class(self):
        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for phrase in (
            "never edit files",
            "post a note or review",
            "submit an approval",
            "resolve a thread",
            "retarget, merge",
            "trigger/cancel/retry ci",
            "report, do not post",
        ):
            self.assertIn(phrase, skill)

    def test_complete_review_requires_file_pagination_and_visible_truncation(self):
        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        contract = CONTRACT.read_text(encoding="utf-8")
        for phrase in (
            "terminal page-chain receipt for both changed files and discussions",
            "explicit non-truncated patch/content verdict",
            "truncated patch",
            "forbids a complete review claim",
        ):
            self.assertIn(phrase, skill)
        self.assertIn("forge.change.files.list-complete.v1", contract)
        self.assertIn("change_diff_truncation=explicit", contract)

    def test_platform_semantics_are_not_flattened(self):
        skill = SKILL.read_text(encoding="utf-8").lower()
        contract = CONTRACT.read_text(encoding="utf-8").lower()
        self.assertIn("preserve platform semantics", skill)
        self.assertIn("not interchangeable", contract)
        self.assertIn(
            "without flattening platform-specific semantics",
            README.read_text(encoding="utf-8").lower(),
        )

    def test_gitlab_and_stacked_skills_route_live_reads_through_shared_contract(self):
        gitlab = (
            ROOT / "skills" / "gitlab-review-response" / "SKILL.md"
        ).read_text(encoding="utf-8")
        stacked = (
            ROOT / "skills" / "stacked-change-delivery" / "SKILL.md"
        ).read_text(encoding="utf-8")
        for text in (gitlab, stacked):
            self.assertIn("forge-adapter-contract.md", text)
        self.assertIn("forge_adapter_selector.py", gitlab)

    def test_manifests_and_migration_notes_are_aligned(self):
        codex = json.loads(CODEX.read_text(encoding="utf-8"))
        claude = json.loads(CLAUDE.read_text(encoding="utf-8"))
        for field in ("name", "version", "description", "author", "license", "keywords"):
            self.assertEqual(codex[field], claude[field])
        self.assertEqual(codex["name"], "git-workflows")
        self.assertEqual(codex["version"], "0.1.2")
        self.assertIsInstance(codex["interface"]["defaultPrompt"], list)
        self.assertTrue(codex["interface"]["defaultPrompt"])
        self.assertEqual(codex["interface"]["composerIcon"], "./assets/icon.png")
        self.assertEqual(codex["interface"]["logo"], "./assets/icon.png")
        self.assertTrue((ROOT / "assets" / "icon.png").is_file())
        readme = README.read_text(encoding="utf-8")
        for legacy in ("gitlab-review", "git-worktree-safety", "stacked-delivery"):
            self.assertIn(legacy, readme)
        for skill in (
            "gitlab-review-response",
            "git-worktree-recovery",
            "git-commit-signing-recovery",
            "stacked-change-delivery",
        ):
            self.assertIn(skill, readme)

    def test_public_contract_surface_is_ascii_and_present(self):
        for path in (SKILL, OPENAI, README, CONTRACT, SELECTOR, CODEX, CLAUDE):
            self.assertTrue(path.is_file(), str(path))
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            self.assertNotIn("C:\\Users\\", text)
            self.assertNotIn("/Users/", text)


if __name__ == "__main__":
    unittest.main()
