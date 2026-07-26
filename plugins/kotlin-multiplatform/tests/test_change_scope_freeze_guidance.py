from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "kmp-testing-quality" / "SKILL.md"


class ChangeScopeFreezeGuidanceTest(unittest.TestCase):
    def test_pre_freeze_gate_accounts_for_the_complete_diff(self):
        text = (
            " ".join(SKILL.read_text(encoding="utf-8").split())
            .lower()
            .replace("`", "")
        )

        for invariant in (
            "change scope freeze",
            "bind the exact base and candidate",
            "complete changed-path set",
            "from committed, staged, and unstaged changes",
            "inventory every task-scope untracked path without mutating user-owned work",
            "mark each as retained candidate or excluded with a reason",
            "include retained bytes in the candidate manifest with status untracked",
            "create one ledger row per candidate path",
            "production, compatibility, test/fixture/harness, generated/project membership, or temporary",
            "served claim or seam",
            "affected target",
            "unique proof obligation",
            "final disposition",
            "candidate's exact (path, status) set must equal the ledger",
            "if cleanup residue exists and cleanup is authorized, remove or revert temporary proof residue, generator-only configuration, accidental format-only churn, and obsolete or duplicate scaffolding",
            "if residue exists without cleanup authority, report the blocker and stop with scope_unresolved",
            "retain compatibility, platform, and test seams only with a named consumer or claim plus targeted proof",
            "review-capacity signal, not an acceptance criterion",
            "split when reviewers or proofs cannot cover every row",
            "retain necessary cross-boundary seams when they form the smallest coherent implementation",
            "after any cleanup, base change, or input drift, re-derive the ledger and invalidate the affected fingerprint, review, and proof",
            "freeze only the minimized candidate",
            "if any path is unclassified or unjustified, stop with scope_unresolved",
        ):
            self.assertIn(invariant, text)


if __name__ == "__main__":
    unittest.main()
