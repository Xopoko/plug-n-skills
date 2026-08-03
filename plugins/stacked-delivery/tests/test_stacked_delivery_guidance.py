from __future__ import annotations

import importlib.util
import json
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
PREPARED_REFERENCE = (
    ROOT
    / "skills"
    / "stacked-change-delivery"
    / "references"
    / "prepared-mutation-handoff.md"
)
HANDOFF_REFERENCE = (
    ROOT
    / "skills"
    / "stacked-change-delivery"
    / "references"
    / "landing-and-handoff.md"
)
SNAPSHOT_REFERENCE = (
    ROOT
    / "skills"
    / "stacked-change-delivery"
    / "references"
    / "stack-snapshot-contract.md"
)
GUARD_PATH = (
    ROOT
    / "skills"
    / "stacked-change-delivery"
    / "scripts"
    / "stacked_delivery_guard.py"
)
CODEX_MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
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
    value = {
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
    composition_digest = guard.snapshot_composition_digest(value)
    inventory = {
        "audit_id": "metadata-audit-1",
        "audit_digest": "c" * 64,
        "audited_kinds": sorted(guard.METADATA_RECORD_KINDS),
        "complete": True,
        "composition_digest": composition_digest,
        "evidence_id": "metadata-evidence-1",
        "records": [],
    }
    inventory["audit_digest"] = guard.metadata_audit_digest(inventory)
    value["metadata_inventory"] = inventory
    return value


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

    def test_proof_layer_requires_mandatory_gap_to_remain_proofless(self):
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

    def test_pre_write_gates_do_not_conflate_proof_provenance_and_authority(self):
        skill = compact(SKILL)
        restack = compact(REFERENCE)
        prepared = compact(PREPARED_REFERENCE)
        for invariant in (
            "keep composition proof, contribution provenance, and mutation "
            "authority separate",
            "do not establish preserved attribution or permission to replace "
            "published history",
            "treat its authority record as preparation evidence, not "
            "automatically fresh publication permission",
        ):
            self.assertIn(invariant, skill)
        for invariant in (
            "composition equivalence",
            "contribution provenance",
            "mutation authority",
            "local `writer_id` is not that authority",
            "current publication authority",
        ):
            self.assertIn(invariant, restack)
        for invariant in (
            "preparation authority versus publication authority",
            "does not grant publication authority",
            "fresh grant authorizes the exact `history-ref-update`",
            "does not ask the receiver to repeat the earlier rewrite",
            "revocation and veto state",
        ):
            self.assertIn(invariant, prepared)

    def test_post_rewrite_proof_bearing_records_are_rebound(self):
        skill = compact(SKILL)
        restack = compact(REFERENCE)
        handoff = compact(HANDOFF_REFERENCE)
        for invariant in (
            "reconcile every active proof-bearing mutable record",
            "change descriptions, status or check summaries, checkpoints, "
            "and handoff summaries",
            "treat a record bound to an old identity as `metadata-stale`",
            "readiness claim, evidence reply, or handoff",
            "fresh authority for that exact surface and action",
            "refreshed by its authoritative producer",
            "same fail-closed rule as `metadata-unverified`",
            "explicitly historical and excluded from current proof",
            "do not rewrite immutable provenance, lease, or old-to-new mappings",
            "metadata freshness can block an independently applicable action",
            "it never makes that action required",
            "zero eligible existing review discussions",
            "no evidence-reply gate and no substitute top-level note",
            "forge-specific review workflow",
            "metadata inventory to be complete, content-bound, and "
            "`metadata-current`",
            "separate inventory digest",
        ):
            self.assertIn(invariant, skill)
        for invariant in (
            "post-rewrite evidence binding",
            "restack, non-fast-forward rewrite, or retarget",
            "`metadata-current`",
            "counts, labels such as \"latest\", a green badge, or a receipt "
            "that is internally self-consistent do not establish live freshness",
            "classify that record as `metadata-stale`",
            "pending proof may be recorded as pending",
            "`metadata-stale` and `metadata-unverified` block a readiness "
            "claim, evidence reply, or handoff",
            "authority to push, restack, retarget, reply, or edit another "
            "surface does not imply authority",
            "update an agent-maintained record only through its authorized owner",
            "producer-owned check or status through its authoritative producer",
            "without that authority or producer path",
            "old-to-new mappings, append-only discussion history",
            "explicitly labelled historical or superseded",
            "do not parse arbitrary generated prose",
            "classify the record as `metadata-unverified`",
            "do not silently infer missing bindings",
            "does not fetch or authenticate forge descriptions, checkpoints, "
            "statuses, or handoff summaries",
            "internal receipt validation does not prove that a live public "
            "record is current",
            "after another workflow or explicit policy independently establishes",
            "it does not create a reply obligation",
            "an evidence reply is `not-applicable`",
            "do not add it as a delivery gate",
            "do not create a top-level note as a substitute",
            "stack proof, review-thread eligibility, and write authority as "
            "separate decisions",
            "`stacked_delivery.snapshot.v2` `metadata_inventory`",
            "`next-action` blocks an exact legacy v1 snapshot, and enforces "
            "the v2 audit before returning `ready` or `complete`",
            "`validate-handoff` fails an exact v1 receipt",
            "a separate digest of the inventory carried by handoff v2",
        ):
            self.assertIn(invariant, restack)
        for invariant in (
            "exact identity and evidence references for each active "
            "proof-bearing description, status, checkpoint, and handoff summary",
            "`metadata-current`, `metadata-stale`, or `metadata-unverified`",
            "only `metadata-current` supports the handoff",
            "historical or superseded non-proof",
            "complete active metadata inventory",
            "`metadata_inventory_digest`",
            "`validate-handoff` returns `fail`",
        ):
            self.assertIn(invariant, handoff)

    def test_replay_interval_and_shared_artifact_scope_are_exact(self):
        skill = compact(SKILL)
        restack = compact(REFERENCE)
        for invariant in (
            "never from a range against the base branch",
            "re-recorded in that descendant rather than here",
            "already bound as that descendant's expected parent head",
            "never recompute that old endpoint from a merge or fork point",
        ):
            self.assertIn(invariant, skill)
        for invariant in (
            "capture the mutated node's pre-mutation head before its first new "
            "commit",
            "neither endpoint is the grandparent's head or the descendant's own "
            "head",
            "never derive the old endpoint by recomputing a merge point or fork "
            "point in any form",
            "returns the stack's fork from the base branch",
            "ref log of the parent's remote-tracking ref",
            "dropping or skipping the descendant's commit is not a resolution",
            "every rewritten descendant needs that lease publish",
            "publishes as an ordinary fast-forward",
            "verifies every module whose recorded artifacts depend on that "
            "component, not only the edited module",
            "re-recorded inside that descendant",
        ):
            self.assertIn(invariant, restack)

    def test_manifest_names_the_full_audited_surface(self):
        manifest = json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))
        long_description = manifest["interface"]["longDescription"].lower()
        self.assertIn(
            "descriptions, statuses, checkpoints, and handoffs",
            long_description,
        )

    def test_versioned_metadata_gate_is_exact_and_fail_closed(self):
        remote = {
            "proof_id": "remote-proof-1",
            "node_id": "node-1",
            "node_head_sha": "b" * 40,
            "dependency_head_sha": "a" * 40,
            "status": "success",
            "terminal": True,
            "superseded": False,
        }
        current = one_node_snapshot([remote])
        _, ready = guard.next_action_data(current)
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["metadata"]["status"], "metadata-current")

        legacy = dict(current)
        legacy["schema"] = guard.SNAPSHOT_SCHEMA_V1
        del legacy["metadata_inventory"]
        parsed = guard.parse_snapshot(legacy)
        self.assertNotIn("metadata_inventory", parsed)
        _, blocked = guard.next_action_data(legacy)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn(
            "legacy_snapshot_metadata_gate",
            {item["code"] for item in blocked["violations"]},
        )

        snapshot_reference = compact(SNAPSHOT_REFERENCE)
        self.assertIn("`stacked_delivery.snapshot.v2`", snapshot_reference)
        self.assertIn("exact legacy v1 snapshots", snapshot_reference)
        self.assertIn("cannot return `ready` or `complete`", snapshot_reference)

    def test_paths_and_dirty_work_contract_are_portable_and_bounded(self):
        skill = compact(SKILL)
        handoff = compact(HANDOFF_REFERENCE)
        snapshot = compact(SNAPSHOT_REFERENCE)
        self.assertIn("bundled commands use `$plugin_root`", skill)
        self.assertIn(
            "$plugin_root/skills/stacked-change-delivery/scripts/"
            "stacked_delivery_guard.py",
            skill,
        )
        for invariant in (
            "does not define or validate a cross-repository dirty-work receipt",
            "repository-native recovery mechanism",
            "preserve the worktree in place",
            "local digest labeled as unverified by this plugin",
            "bundled guard does not validate that note",
        ):
            self.assertIn(invariant, handoff)
        for invariant in (
            "full lowercase, non-zero 40- or 64-hex object ids",
            "all-zero deletion or unborn sentinel is not an object",
            "`writer_id` coordinates the local editor only",
            "not forge change ownership",
        ):
            self.assertIn(invariant, snapshot)

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
        for path in (
            SKILL,
            REFERENCE,
            PREPARED_REFERENCE,
            HANDOFF_REFERENCE,
            SNAPSHOT_REFERENCE,
        ):
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
