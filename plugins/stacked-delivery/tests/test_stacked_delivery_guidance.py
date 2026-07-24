from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "stacked-change-delivery" / "SKILL.md"
REFERENCE = (
    ROOT
    / "skills"
    / "stacked-change-delivery"
    / "references"
    / "proof-drift-and-restack.md"
)
GUARD_PATH = (
    ROOT
    / "skills"
    / "stacked-change-delivery"
    / "scripts"
    / "stacked_delivery_guard.py"
)
SPEC = importlib.util.spec_from_file_location(
    "stacked_delivery_guidance_guard", GUARD_PATH
)
assert SPEC is not None
guard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(guard)


def compact(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split()).lower()


def one_node_snapshot(proofs: list[dict]) -> dict:
    base = "a" * 40
    head = "b" * 40
    return {
        "schema": guard.SNAPSHOT_SCHEMA,
        "repository_id": "repository-1",
        "forge_adapter": "generic-v1",
        "stack_id": "stack-1",
        "forge_mode": "sequential",
        "base": {"branch": "main", "head_sha": base},
        "nodes": [
            {
                "node_id": "node-1",
                "change_id": "change-1",
                "source_branch": "stack/change-1",
                "target_branch": "main",
                "head_sha": head,
                "landing_head_sha": None,
                "parent_node_id": None,
                "expected_parent_head_sha": base,
                "worktree_id": "worktree-1",
                "writer_id": "writer-1",
                "state": "unlanded",
                "proofs": proofs,
            }
        ],
    }


class StackedDeliveryGuidanceTests(unittest.TestCase):
    def test_unchanged_proof_gate_is_not_retried_or_accepted(self):
        skill = compact(SKILL)
        reference = compact(REFERENCE)
        for invariant in (
            "unchanged external gate persists",
            "redacted task-local proof-gap record",
            "keep it out of accepted proofs",
            "do not retry until relevant code, fixture, configuration, "
            "environment, or external state changes",
            "snapshot `proofs` empty while any policy-required surface remains open",
            "partial evidence stays task-local",
        ):
            self.assertIn(invariant, skill)
        for invariant in (
            "keep this record out of the snapshot's accepted `proofs`",
            "unavailability is neither a failed proof result nor a successful proof",
            "do not rerun the same proof while its gate fingerprint is unchanged",
            "retry only after a relevant input or external state changes",
            "opaque proof-surface id, command identity, and exact node and dependency heads",
            "use `proofs: []` while any policy-required proof surface remains open",
            "partial or non-equivalent results stay in task-local evidence",
        ):
            self.assertIn(invariant, reference)

    def test_v1_guard_requires_mandatory_gap_to_remain_proofless(self):
        _, blocked = guard.next_action_data(one_node_snapshot([]))
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(
            blocked["reasons"], ["lowest_unlanded_node_has_no_current_proof"]
        )

        remote = {
            "proof_id": "remote-proof-1",
            "node_id": "node-1",
            "node_head_sha": "b" * 40,
            "dependency_head_sha": "a" * 40,
            "status": "success",
            "terminal": True,
            "superseded": False,
        }
        _, ready = guard.next_action_data(one_node_snapshot([remote]))
        self.assertEqual(ready["status"], "ready")
        self.assertIn(
            "use `proofs: []` while any policy-required proof surface remains open",
            compact(REFERENCE),
        )

    def test_remote_proof_preserves_authority_and_exact_head_binding(self):
        reference = compact(REFERENCE)
        for invariant in (
            "does not authorize the publish",
            "existing mutation and lease gates still apply",
            "read back the remote head before accepting a later result",
            "repository policy permits that proof authority",
            "terminal success binds the exact node and dependency heads",
            "any required execution is non-empty",
            "does not satisfy a mandatory local surface unless policy explicitly "
            "declares the two surfaces equivalent",
            "non-equivalent remote result remains task-local evidence",
            "must not enter landing-eligible snapshot proofs",
            "`next-action` remains blocked until every policy-required proof surface "
            "is satisfied or explicitly equivalent",
            "open proof gap separately from a later accepted remote proof",
        ):
            self.assertIn(invariant, reference)

    def test_guidance_is_public_safe(self):
        reference = compact(REFERENCE)
        for invariant in (
            "public-safe task-local proof-gap sidecar",
            "without copying their raw values",
            "generic bounded failure class and opaque evidence reference",
            "recovery role, not a personal identity",
            "sidecar and handoff must not contain local paths, private urls, "
            "dependency coordinates, credentials, raw log fragments, personal "
            "identities, or private project names",
        ):
            self.assertIn(invariant, reference)
        for path in (SKILL, REFERENCE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            for forbidden in (
                "/Users/",
                "\\Users\\",
                "BEGIN PRIVATE KEY",
            ):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
