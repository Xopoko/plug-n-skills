from __future__ import annotations

import ast
import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "stacked-change-delivery"
    / "scripts"
    / "stacked_delivery_guard.py"
)
SKILL = SCRIPT.parents[1] / "SKILL.md"
REFERENCE = SCRIPT.parents[1] / "references" / "prepared-mutation-handoff.md"
SPEC = importlib.util.spec_from_file_location("prepared_mutation_guard", SCRIPT)
assert SPEC is not None
guard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(guard)


BASE = "a" * 40
OLD_1 = "b" * 40
OLD_2 = "c" * 40
NEW_PARENT = "d" * 40
NEW_1 = "e" * 40
NEW_2 = "f" * 40
OTHER = "1" * 40
LANDING = "0" * 40
DIGEST_A = "2" * 64
DIGEST_B = "3" * 64
DIGEST_C = "4" * 64
DIGEST_D = "5" * 64
AUTHOR = "6" * 64
COMMITTER = "7" * 64
AUTHORIZED_COMMITTER = "8" * 64
EVIDENCE_HASH = "9" * 64


def snapshot() -> dict:
    return {
        "schema": guard.SNAPSHOT_SCHEMA,
        "repository_id": "repository-1",
        "forge_adapter": "generic-v1",
        "stack_id": "stack-1",
        "forge_mode": "sequential",
        "base": {"branch": "main", "head_sha": BASE},
        "nodes": [
            {
                "node_id": "node-1",
                "change_id": "change-1",
                "source_branch": "stack/change-1",
                "target_branch": "main",
                "head_sha": OLD_1,
                "landing_head_sha": None,
                "parent_node_id": None,
                "expected_parent_head_sha": BASE,
                "worktree_id": "worktree-1",
                "writer_id": "writer-1",
                "state": "unlanded",
                "proofs": [],
            },
            {
                "node_id": "node-2",
                "change_id": "change-2",
                "source_branch": "stack/change-2",
                "target_branch": "stack/change-1",
                "head_sha": OLD_2,
                "landing_head_sha": None,
                "parent_node_id": "node-1",
                "expected_parent_head_sha": OLD_1,
                "worktree_id": "worktree-2",
                "writer_id": "writer-2",
                "state": "unlanded",
                "proofs": [],
            },
        ],
    }


def equivalence(index: int, kind: str) -> dict:
    digest = {
        (1, "patch"): DIGEST_A,
        (1, "tree"): DIGEST_B,
        (2, "patch"): DIGEST_C,
        (2, "tree"): DIGEST_D,
    }[(index, kind)]
    if kind == "patch":
        method = "stable-patch-id"
        scope = "node-delta"
    else:
        method = "canonical-tree-delta"
        scope = "node-delta"
    return {
        "method": method,
        "scope": scope,
        "old_digest": digest,
        "new_digest": digest,
        "evidence_id": f"{kind}-equivalence-{index}",
        "equivalent": True,
    }


def attribution() -> dict:
    return {
        "relation": "preserve-author-and-committer",
        "old_author_fingerprint": AUTHOR,
        "new_author_fingerprint": AUTHOR,
        "old_committer_fingerprint": COMMITTER,
        "new_committer_fingerprint": COMMITTER,
        "authorized_committer_fingerprint": None,
    }


def prepared_proof(index: int, surface: str, head: str, parent: str) -> dict:
    return {
        "proof_id": f"proof-{index}-{surface}",
        "surface_id": surface,
        "node_head_sha": head,
        "dependency_head_sha": parent,
        "status": "success",
        "terminal": True,
        "superseded": False,
        "execution_nonempty": True,
    }


def proof_gap(index: int, surface: str, head: str, parent: str) -> dict:
    return {
        "surface_id": surface,
        "node_head_sha": head,
        "dependency_head_sha": parent,
        "blocks_action": "metadata-update",
        "evidence_id": f"proof-gap-{index}-{surface}",
    }


def prepared_node(
    index: int,
    old_head: str,
    new_head: str,
    old_parent: str,
    new_parent: str,
) -> dict:
    required = ["local-test", "remote-ci"]
    return {
        "node_id": f"node-{index}",
        "change_id": f"change-{index}",
        "source_branch": f"stack/change-{index}",
        "old_head_sha": old_head,
        "new_head_sha": new_head,
        "old_parent_head_sha": old_parent,
        "new_parent_head_sha": new_parent,
        "patch_equivalence": equivalence(index, "patch"),
        "tree_equivalence": equivalence(index, "tree"),
        "attribution": attribution(),
        "backup": {
            "ref": f"refs/stacked-delivery/backups/change-{index}",
            "expected_head_sha": old_head,
            "readback_head_sha": old_head,
            "confirmed": True,
        },
        "lease": {
            "remote_ref": f"stack/change-{index}",
            "expected_remote_head_sha": old_head,
            "mode": "exact-remote-head",
        },
        "required_proof_surfaces": required,
        "proofs": [
            prepared_proof(index, "local-test", new_head, new_parent)
        ],
        "open_proof_gaps": [
            proof_gap(index, "remote-ci", new_head, new_parent)
        ],
    }


def prepared_mutation() -> dict:
    old_snapshot = snapshot()
    nodes = [
        prepared_node(1, OLD_1, NEW_1, BASE, NEW_PARENT),
        prepared_node(2, OLD_2, NEW_2, OLD_1, NEW_1),
    ]
    authority_id = "authority-1"
    return {
        "schema": guard.PREPARED_MUTATION_SCHEMA,
        "receiver_id": "receiver-1",
        "snapshot_digest": guard.stable_digest(old_snapshot),
        "snapshot": old_snapshot,
        "new_predecessor": {
            "kind": "retarget",
            "node_id": None,
            "source_ref": "refs/heads/integration/main",
            "head_sha": NEW_PARENT,
            "evidence_id": "new-predecessor-1",
        },
        "proof_wait_owner_ref": "external-proof-owner-1",
        "authority": {
            "authority_id": authority_id,
            "source": "user",
            "evidence_id": "authority-evidence-1",
            "evidence_hash": EVIDENCE_HASH,
            "allowed_actions": [
                "history-ref-update",
                "metadata-update",
            ],
        },
        "proof_policy": {
            "policy_id": "proof-policy-1",
            "policy_hash": DIGEST_A,
        },
        "attribution_policy": {
            "policy_id": "attribution-policy-1",
            "policy_hash": DIGEST_B,
        },
        "excluded_actions": sorted(guard.REQUIRED_EXCLUDED_ACTIONS),
        "nodes": nodes,
        "actions": [
            {
                "action_id": "history-1",
                "kind": "history-ref-update",
                "node_id": "node-1",
                "authority_id": authority_id,
                "remote_ref": "stack/change-1",
                "expected_remote_head_sha": OLD_1,
                "new_head_sha": NEW_1,
                "backup_ref": "refs/stacked-delivery/backups/change-1",
            },
            {
                "action_id": "history-2",
                "kind": "history-ref-update",
                "node_id": "node-2",
                "authority_id": authority_id,
                "remote_ref": "stack/change-2",
                "expected_remote_head_sha": OLD_2,
                "new_head_sha": NEW_2,
                "backup_ref": "refs/stacked-delivery/backups/change-2",
            },
            {
                "action_id": "metadata-1",
                "kind": "metadata-update",
                "node_id": "node-1",
                "authority_id": authority_id,
                "old_target_branch": "main",
                "new_target_branch": "integration/main",
                "expected_new_target_head_sha": NEW_PARENT,
                "expected_node_head_sha": NEW_1,
            },
        ],
        "history_receipts": [],
        "metadata_receipt": None,
    }


def fully_proven_mutation() -> dict:
    value = prepared_mutation()
    for index, node in enumerate(value["nodes"], start=1):
        gap = node["open_proof_gaps"].pop()
        node["proofs"].append(
            prepared_proof(
                index,
                gap["surface_id"],
                gap["node_head_sha"],
                gap["dependency_head_sha"],
            )
        )
    value["proof_wait_owner_ref"] = None
    return value


def history_only_mutation() -> dict:
    value = fully_proven_mutation()
    value["new_predecessor"] = {
        "kind": "base",
        "node_id": None,
        "source_ref": "refs/heads/main",
        "head_sha": BASE,
        "evidence_id": "new-predecessor-base",
    }
    value["nodes"][0]["new_parent_head_sha"] = BASE
    for proof in value["nodes"][0]["proofs"]:
        proof["dependency_head_sha"] = BASE
    value["actions"].pop()
    value["authority"]["allowed_actions"] = ["history-ref-update"]
    return value


def add_history_receipts(value: dict, count: int) -> dict:
    history_actions = [
        action
        for action in value["actions"]
        if action["kind"] == "history-ref-update"
    ]
    transaction_digest = guard.prepared_transaction_digest(value)
    receipts = []
    for index, action in enumerate(history_actions[:count]):
        receipt = {
            "receipt_id": f"history-receipt-{index + 1}",
            "transaction_digest": transaction_digest,
            "action_id": action["action_id"],
            "node_id": action["node_id"],
            "remote_ref": action["remote_ref"],
            "expected_old_head_sha": action["expected_remote_head_sha"],
            "written_head_sha": action["new_head_sha"],
            "readback_head_sha": action["new_head_sha"],
            "backup_ref": action["backup_ref"],
            "backup_readback_head_sha": action["expected_remote_head_sha"],
        }
        receipt["receipt_hash"] = guard.stable_digest(receipt)
        receipts.append(receipt)
    value["history_receipts"] = receipts
    return value


def add_metadata_receipt(value: dict) -> dict:
    action = next(
        action
        for action in value["actions"]
        if action["kind"] == "metadata-update"
    )
    receipt = {
        "receipt_id": "metadata-receipt-1",
        "transaction_digest": guard.prepared_transaction_digest(value),
        "action_id": action["action_id"],
        "node_id": action["node_id"],
        "old_target_ref": guard._full_head_ref(action["old_target_branch"]),
        "new_target_ref": guard._full_head_ref(action["new_target_branch"]),
        "readback_target_ref": guard._full_head_ref(
            action["new_target_branch"]
        ),
        "expected_new_target_head_sha": action[
            "expected_new_target_head_sha"
        ],
        "readback_new_target_head_sha": action[
            "expected_new_target_head_sha"
        ],
        "expected_node_head_sha": action["expected_node_head_sha"],
        "readback_node_head_sha": action["expected_node_head_sha"],
    }
    receipt["receipt_hash"] = guard.stable_digest(receipt)
    value["metadata_receipt"] = receipt
    return value


def result_for(value: dict) -> dict:
    return guard.validate_prepared_mutation_data(value)[1]


def codes(value: dict) -> set[str]:
    return {item["code"] for item in result_for(value)["violations"]}


class PreparedMutationShapeTests(unittest.TestCase):
    def test_valid_prepared_mutation_is_history_ready(self):
        value = prepared_mutation()
        parsed, result = guard.validate_prepared_mutation_data(value)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["readiness"], "history-ready")
        self.assertEqual(result["next_action_id"], "history-1")
        self.assertEqual(result["prepared_mutation_digest"], guard.stable_digest(parsed))
        self.assertEqual(result["node_count"], 2)
        self.assertEqual(result["action_count"], 3)
        self.assertEqual(result["proof_surface_count"], 4)
        self.assertEqual(result["proof_count"], 2)
        self.assertEqual(result["open_proof_gap_count"], 2)
        self.assertEqual(result["proof_policy_id"], "proof-policy-1")
        self.assertEqual(
            result["attribution_policy_id"],
            "attribution-policy-1",
        )

    def test_schema_is_additive_and_old_handoff_parser_is_unchanged(self):
        self.assertNotEqual(guard.PREPARED_MUTATION_SCHEMA, guard.HANDOFF_SCHEMA)
        with self.assertRaises(guard.InputError):
            guard.parse_handoff(prepared_mutation())

    def test_unknown_field_is_rejected(self):
        value = prepared_mutation()
        value["heartbeat"] = {"id": "not-portable"}
        with self.assertRaises(guard.InputError):
            guard.parse_prepared_mutation(value)

    def test_proof_wait_owner_is_nullable_but_never_a_collection(self):
        value = prepared_mutation()
        value["proof_wait_owner_ref"] = ["owner-1", "owner-2"]
        with self.assertRaises(guard.InputError):
            guard.parse_prepared_mutation(value)

    def test_repository_policies_are_opaque_and_hash_bound(self):
        for field in ("proof_policy", "attribution_policy"):
            with self.subTest(field=field, invalid="id"):
                value = prepared_mutation()
                value[field]["policy_id"] = "https://private.invalid/policy"
                with self.assertRaises(guard.InputError):
                    guard.parse_prepared_mutation(value)

            with self.subTest(field=field, invalid="hash"):
                value = prepared_mutation()
                value[field]["policy_hash"] = "short"
                with self.assertRaises(guard.InputError):
                    guard.parse_prepared_mutation(value)

    def test_rewrite_mapping_binds_old_and_new_heads_and_parents(self):
        cases = (
            ("old_head_sha", OTHER, "prepared_old_head_mismatch"),
            ("old_parent_head_sha", OTHER, "prepared_old_parent_mismatch"),
            ("new_head_sha", OLD_1, "prepared_head_not_rewritten"),
        )
        for field, replacement, expected_code in cases:
            with self.subTest(field=field):
                value = prepared_mutation()
                value["nodes"][0][field] = replacement
                if field == "new_head_sha":
                    value["nodes"][0]["proofs"][0]["node_head_sha"] = replacement
                    value["nodes"][0]["open_proof_gaps"][0][
                        "node_head_sha"
                    ] = replacement
                self.assertIn(expected_code, codes(value))

    def test_rewrite_nodes_must_be_one_contiguous_suffix(self):
        value = prepared_mutation()
        value["nodes"].pop(0)
        value["actions"].pop(0)
        value["actions"][-1]["node_id"] = "node-2"
        value["actions"][-1]["old_target_branch"] = "stack/change-1"
        value["actions"][-1]["expected_new_target_head_sha"] = NEW_1
        value["actions"][-1]["expected_node_head_sha"] = NEW_2
        value["new_predecessor"]["head_sha"] = NEW_1
        self.assertEqual(result_for(value)["status"], "ready")

        value = prepared_mutation()
        value["nodes"].reverse()
        self.assertIn("rewrite_nodes_not_contiguous_suffix", codes(value))

    def test_new_parent_chain_must_follow_prepared_heads(self):
        value = prepared_mutation()
        value["nodes"][1]["new_parent_head_sha"] = OTHER
        for proof in value["nodes"][1]["proofs"]:
            proof["dependency_head_sha"] = OTHER
        for gap in value["nodes"][1]["open_proof_gaps"]:
            gap["dependency_head_sha"] = OTHER
        self.assertIn("prepared_new_parent_chain_mismatch", codes(value))

        value = prepared_mutation()
        value["nodes"][0]["new_parent_head_sha"] = NEW_1
        for proof in value["nodes"][0]["proofs"]:
            proof["dependency_head_sha"] = NEW_1
        for gap in value["nodes"][0]["open_proof_gaps"]:
            gap["dependency_head_sha"] = NEW_1
        value["new_predecessor"]["head_sha"] = NEW_1
        value["actions"][-1]["expected_new_target_head_sha"] = NEW_1
        self.assertIn("prepared_new_head_equals_parent", codes(value))

    def test_first_new_parent_is_bound_to_an_explicit_predecessor(self):
        value = prepared_mutation()
        value["new_predecessor"]["head_sha"] = OTHER
        self.assertIn(
            "first_new_parent_predecessor_head_mismatch",
            codes(value),
        )

        value = history_only_mutation()
        value["new_predecessor"]["source_ref"] = "refs/heads/other"
        self.assertIn("new_predecessor_ref_mismatch", codes(value))

    def test_landed_prefix_retarget_uses_current_base_as_predecessor(self):
        value = history_only_mutation()
        old_snapshot = value["snapshot"]
        old_snapshot["base"]["head_sha"] = LANDING
        first = old_snapshot["nodes"][0]
        first["landing_head_sha"] = LANDING
        first["worktree_id"] = None
        first["writer_id"] = None
        first["state"] = "landed"
        second = old_snapshot["nodes"][1]
        second["target_branch"] = "main"
        second["expected_parent_head_sha"] = LANDING
        second["state"] = "retargeted"
        value["snapshot_digest"] = guard.stable_digest(old_snapshot)

        value["nodes"].pop(0)
        node = value["nodes"][0]
        node["old_parent_head_sha"] = LANDING
        node["new_parent_head_sha"] = LANDING
        for proof in node["proofs"]:
            proof["dependency_head_sha"] = LANDING
        value["actions"].pop(0)
        value["new_predecessor"] = {
            "kind": "base",
            "node_id": None,
            "source_ref": "refs/heads/main",
            "head_sha": LANDING,
            "evidence_id": "landed-prefix-base",
        }

        result = result_for(value)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["next_action_id"], "history-2")


class EquivalenceAndAttributionTests(unittest.TestCase):
    def test_patch_and_tree_equivalence_are_both_required(self):
        for field in ("patch_equivalence", "tree_equivalence"):
            with self.subTest(field=field):
                value = prepared_mutation()
                value["nodes"][0][field]["new_digest"] = EVIDENCE_HASH
                self.assertIn(f"{field}_digest_mismatch", codes(value))

                value = prepared_mutation()
                value["nodes"][0][field]["equivalent"] = False
                self.assertIn(f"{field}_not_equivalent", codes(value))

    def test_tree_equivalence_method_scope_pairs_are_exact(self):
        for method, scope in (
            ("tree-object", "node-delta"),
            ("canonical-tree-delta", "result-tree"),
        ):
            with self.subTest(method=method, scope=scope):
                value = prepared_mutation()
                evidence = value["nodes"][0]["tree_equivalence"]
                evidence["method"] = method
                evidence["scope"] = scope
                with self.assertRaises(guard.InputError):
                    guard.parse_prepared_mutation(value)

    def test_green_proofs_do_not_override_author_attribution_drift(self):
        value = fully_proven_mutation()
        value["nodes"][0]["attribution"]["new_author_fingerprint"] = DIGEST_A
        result = result_for(value)
        self.assertEqual(result["proof_count"], 4)
        self.assertEqual(result["status"], "fail")
        self.assertIn("author_attribution_drift", codes(value))

    def test_preserve_policy_rejects_committer_drift(self):
        value = fully_proven_mutation()
        value["nodes"][0]["attribution"][
            "new_committer_fingerprint"
        ] = AUTHORIZED_COMMITTER
        self.assertIn("committer_attribution_drift", codes(value))

    def test_intentional_authorized_committer_change_passes(self):
        value = fully_proven_mutation()
        attribution_value = value["nodes"][0]["attribution"]
        attribution_value[
            "relation"
        ] = "preserve-author-allow-authorized-committer"
        attribution_value["new_committer_fingerprint"] = AUTHORIZED_COMMITTER
        attribution_value[
            "authorized_committer_fingerprint"
        ] = AUTHORIZED_COMMITTER
        result = result_for(value)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["readiness"], "mutation-ready")

    def test_authorized_committer_policy_rejects_another_identity(self):
        value = prepared_mutation()
        attribution_value = value["nodes"][0]["attribution"]
        attribution_value[
            "relation"
        ] = "preserve-author-allow-authorized-committer"
        attribution_value["new_committer_fingerprint"] = DIGEST_A
        attribution_value[
            "authorized_committer_fingerprint"
        ] = AUTHORIZED_COMMITTER
        self.assertIn("unauthorized_committer_identity", codes(value))


class BackupLeaseActionAndProofTests(unittest.TestCase):
    def test_backups_are_unique_confirmed_and_read_back_at_old_head(self):
        value = prepared_mutation()
        value["nodes"][0]["backup"]["confirmed"] = False
        self.assertIn("backup_not_confirmed", codes(value))

        value = prepared_mutation()
        value["nodes"][0]["backup"]["readback_head_sha"] = OTHER
        self.assertIn("backup_readback_head_mismatch", codes(value))

        value = prepared_mutation()
        duplicate_ref = "refs/stacked-delivery/backups/change-1"
        value["nodes"][1]["backup"]["ref"] = duplicate_ref
        value["actions"][1]["backup_ref"] = duplicate_ref
        self.assertIn("duplicate_backup_ref", codes(value))

        value = prepared_mutation()
        value["nodes"][0]["backup"]["ref"] = "refs/heads/stack/change-2"
        value["actions"][0]["backup_ref"] = "refs/heads/stack/change-2"
        self.assertIn("backup_ref_conflicts_live_ref", codes(value))

        for live_ref in ("refs/heads/main", "refs/heads/integration/main"):
            with self.subTest(live_ref=live_ref):
                value = prepared_mutation()
                value["nodes"][0]["backup"]["ref"] = live_ref
                value["actions"][0]["backup_ref"] = live_ref
                self.assertIn("backup_ref_conflicts_live_ref", codes(value))

    def test_backup_ref_must_use_the_dedicated_recovery_namespace(self):
        for ref in (
            "refs/heads/unrelated-live-branch",
            "refs/tags/release",
            "refs/remotes/origin/main",
            "refs/stacked-delivery/backups",
            "refs/stacked-delivery/backups-other/change-1",
        ):
            with self.subTest(ref=ref):
                value = prepared_mutation()
                value["nodes"][0]["backup"]["ref"] = ref
                value["actions"][0]["backup_ref"] = ref
                self.assertIn(
                    "backup_ref_outside_recovery_namespace",
                    codes(value),
                )

    def test_remote_lease_must_equal_snapshot_old_head(self):
        value = prepared_mutation()
        value["nodes"][0]["lease"]["expected_remote_head_sha"] = OTHER
        value["actions"][0]["expected_remote_head_sha"] = OTHER
        self.assertIn("lease_expected_head_mismatch", codes(value))

    def test_history_and_metadata_actions_are_distinct_and_ordered(self):
        value = prepared_mutation()
        value["actions"] = [
            value["actions"][2],
            value["actions"][0],
            value["actions"][1],
        ]
        self.assertIn("history_action_after_metadata", codes(value))

        value = prepared_mutation()
        value["actions"][0]["new_target_branch"] = "integration/main"
        with self.assertRaises(guard.InputError):
            guard.parse_prepared_mutation(value)

    def test_every_action_binds_the_explicit_authority(self):
        value = prepared_mutation()
        value["actions"][0]["authority_id"] = "other-authority"
        self.assertIn("action_authority_mismatch", codes(value))

    def test_required_exclusions_fail_closed(self):
        value = prepared_mutation()
        value["excluded_actions"].remove("delete-backup")
        self.assertIn("required_exclusions_missing", codes(value))

    def test_metadata_action_is_optional_and_head_bound(self):
        result = result_for(history_only_mutation())
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["readiness"], "mutation-ready")

        value = prepared_mutation()
        value["actions"][-1]["expected_node_head_sha"] = OTHER
        self.assertIn("metadata_expected_head_mismatch", codes(value))

        value = prepared_mutation()
        value["actions"][-1]["expected_new_target_head_sha"] = OTHER
        self.assertIn("metadata_new_target_head_mismatch", codes(value))

    def test_metadata_is_first_node_only_and_topology_safe(self):
        value = prepared_mutation()
        value["actions"][-1]["node_id"] = "node-2"
        value["actions"][-1]["old_target_branch"] = "stack/change-1"
        value["actions"][-1]["expected_node_head_sha"] = NEW_2
        self.assertIn("metadata_action_not_first_rewritten_node", codes(value))

        for target in ("stack/change-1", "stack/change-2"):
            with self.subTest(target=target):
                value = prepared_mutation()
                value["actions"][-1]["new_target_branch"] = target
                value["new_predecessor"]["source_ref"] = (
                    f"refs/heads/{target}"
                )
                self.assertIn("metadata_target_topology_conflict", codes(value))

        value = prepared_mutation()
        value["actions"][-1]["new_target_branch"] = "refs/heads/main"
        value["new_predecessor"]["source_ref"] = "refs/heads/main"
        self.assertIn("metadata_target_not_changed", codes(value))

        for ref in (
            "refs/tags/release",
            "refs/remotes/origin/main",
            "refs/notes/build",
        ):
            with self.subTest(non_branch_ref=ref):
                value = prepared_mutation()
                value["actions"][-1]["new_target_branch"] = ref
                value["new_predecessor"]["source_ref"] = ref
                with self.assertRaises(guard.InputError):
                    guard.parse_prepared_mutation(value)

    def test_every_required_new_composition_surface_is_proof_or_gap(self):
        value = prepared_mutation()
        value["nodes"][0]["open_proof_gaps"].pop()
        self.assertIn("required_proof_surface_missing", codes(value))

        value = prepared_mutation()
        value["nodes"][0]["proofs"][0]["node_head_sha"] = OLD_1
        self.assertIn("prepared_proof_node_head_stale", codes(value))

        value = prepared_mutation()
        value["nodes"][0]["proofs"][0]["execution_nonempty"] = False
        self.assertIn("prepared_proof_execution_empty", codes(value))

        value = prepared_mutation()
        gap = copy.deepcopy(value["nodes"][0]["open_proof_gaps"][0])
        gap["surface_id"] = "local-test"
        value["nodes"][0]["open_proof_gaps"].append(gap)
        self.assertIn("duplicate_proof_surface", codes(value))

    def test_proof_wait_owner_exists_iff_open_gaps_exist(self):
        value = prepared_mutation()
        value["proof_wait_owner_ref"] = None
        self.assertIn("proof_wait_owner_missing", codes(value))

        value = fully_proven_mutation()
        value["proof_wait_owner_ref"] = "unneeded-owner"
        self.assertIn("unexpected_proof_wait_owner", codes(value))

    def test_history_blocking_gap_blocks_all_mutation(self):
        value = prepared_mutation()
        value["nodes"][0]["open_proof_gaps"][0][
            "blocks_action"
        ] = "history-ref-update"
        result = result_for(value)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["readiness"], "blocked")
        self.assertIsNone(result["next_action_id"])

    def test_higher_node_history_gap_does_not_block_first_action(self):
        value = prepared_mutation()
        value["nodes"][1]["open_proof_gaps"][0][
            "blocks_action"
        ] = "history-ref-update"
        result = result_for(value)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["next_action_id"], "history-1")

        add_history_receipts(value, 1)
        result = result_for(value)
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["next_action_id"])

    def test_metadata_gap_requires_a_metadata_action(self):
        value = history_only_mutation()
        node = value["nodes"][0]
        remote_proof = node["proofs"].pop()
        node["open_proof_gaps"] = [
            proof_gap(
                1,
                remote_proof["surface_id"],
                remote_proof["node_head_sha"],
                remote_proof["dependency_head_sha"],
            )
        ]
        value["proof_wait_owner_ref"] = "external-proof-owner-1"
        self.assertIn("proof_gap_blocks_absent_action", codes(value))

    def test_prepared_receipts_cannot_reuse_old_snapshot_proof_ids(self):
        value = prepared_mutation()
        value["snapshot"]["nodes"][0]["proofs"] = [
            {
                "proof_id": "proof-1-local-test",
                "node_id": "node-1",
                "node_head_sha": OLD_1,
                "dependency_head_sha": BASE,
                "status": "success",
                "terminal": True,
                "superseded": False,
            }
        ]
        value["snapshot_digest"] = guard.stable_digest(value["snapshot"])
        self.assertIn(
            "prepared_proof_id_reuses_snapshot_receipt",
            codes(value),
        )

    def test_one_git_object_id_width_is_required(self):
        value = prepared_mutation()
        replacement = "e" * 64
        value["nodes"][0]["new_head_sha"] = replacement
        value["nodes"][0]["proofs"][0]["node_head_sha"] = replacement
        value["nodes"][0]["open_proof_gaps"][0]["node_head_sha"] = replacement
        value["nodes"][1]["new_parent_head_sha"] = replacement
        value["nodes"][1]["proofs"][0][
            "dependency_head_sha"
        ] = replacement
        value["nodes"][1]["open_proof_gaps"][0][
            "dependency_head_sha"
        ] = replacement
        value["actions"][0]["new_head_sha"] = replacement
        self.assertIn("mixed_git_object_id_width", codes(value))


class PreparedMutationProgressReceiptTests(unittest.TestCase):
    def test_receipt_prefix_advances_exactly_one_history_action(self):
        value = add_history_receipts(prepared_mutation(), 1)
        result = result_for(value)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["readiness"], "history-ready")
        self.assertEqual(result["next_action_id"], "history-2")
        self.assertEqual(result["completed_history_count"], 1)

    def test_all_history_then_remote_proof_reaches_metadata_ready(self):
        value = add_history_receipts(prepared_mutation(), 2)
        result = result_for(value)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["readiness"], "proof-wait")
        self.assertIsNone(result["next_action_id"])

        value = add_history_receipts(fully_proven_mutation(), 2)
        result = result_for(value)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["readiness"], "metadata-ready")
        self.assertEqual(result["next_action_id"], "metadata-1")

        add_metadata_receipt(value)
        result = result_for(value)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["readiness"], "complete")
        self.assertTrue(result["metadata_completed"])
        self.assertIsNone(result["next_action_id"])

    def test_pure_history_remote_gap_can_finish_without_metadata(self):
        value = history_only_mutation()
        node = value["nodes"][0]
        remote_proof = node["proofs"].pop()
        gap = proof_gap(
            1,
            remote_proof["surface_id"],
            remote_proof["node_head_sha"],
            remote_proof["dependency_head_sha"],
        )
        gap["blocks_action"] = "finalize"
        node["open_proof_gaps"] = [gap]
        value["proof_wait_owner_ref"] = "external-proof-owner-1"

        self.assertEqual(result_for(value)["next_action_id"], "history-1")
        add_history_receipts(value, 2)
        result = result_for(value)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["readiness"], "proof-wait")

        node["open_proof_gaps"] = []
        node["proofs"].append(remote_proof)
        value["proof_wait_owner_ref"] = None
        result = result_for(value)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["readiness"], "complete")
        self.assertIsNone(result["next_action_id"])

    def test_history_receipts_are_an_exact_contiguous_prefix(self):
        value = add_history_receipts(prepared_mutation(), 2)
        value["history_receipts"].reverse()
        self.assertIn("history_receipt_action_order_mismatch", codes(value))

        value = add_history_receipts(prepared_mutation(), 1)
        value["history_receipts"][0]["readback_head_sha"] = OTHER
        self.assertIn("history_receipt_readback_mismatch", codes(value))
        self.assertIn("history_receipt_digest_mismatch", codes(value))

        value = add_history_receipts(prepared_mutation(), 1)
        value["history_receipts"][0]["receipt_hash"] = EVIDENCE_HASH
        self.assertIn("history_receipt_digest_mismatch", codes(value))

        value = add_history_receipts(prepared_mutation(), 1)
        value["history_receipts"][0]["backup_readback_head_sha"] = OTHER
        self.assertIn(
            "history_receipt_backup_readback_mismatch",
            codes(value),
        )

    def test_receipt_cannot_bypass_a_history_blocking_gap(self):
        value = prepared_mutation()
        value["nodes"][0]["open_proof_gaps"][0][
            "blocks_action"
        ] = "history-ref-update"
        add_history_receipts(value, 1)
        self.assertIn("history_receipt_bypasses_open_gate", codes(value))

    def test_transaction_digest_is_stable_across_proofs_but_binds_scope(self):
        initial = prepared_mutation()
        proven = fully_proven_mutation()
        self.assertEqual(
            guard.prepared_transaction_digest(initial),
            guard.prepared_transaction_digest(proven),
        )

        cases = ("repository", "stack", "authority", "backup")
        for case in cases:
            with self.subTest(case=case):
                value = add_history_receipts(prepared_mutation(), 1)
                if case == "repository":
                    value["snapshot"]["repository_id"] = "repository-2"
                    value["snapshot_digest"] = guard.stable_digest(
                        value["snapshot"]
                    )
                elif case == "stack":
                    value["snapshot"]["stack_id"] = "stack-2"
                    value["snapshot_digest"] = guard.stable_digest(
                        value["snapshot"]
                    )
                elif case == "authority":
                    value["authority"]["authority_id"] = "authority-2"
                    for action in value["actions"]:
                        action["authority_id"] = "authority-2"
                else:
                    replacement = (
                        "refs/stacked-delivery/backups/replacement-1"
                    )
                    value["nodes"][0]["backup"]["ref"] = replacement
                    value["actions"][0]["backup_ref"] = replacement
                self.assertIn(
                    "history_receipt_transaction_mismatch",
                    codes(value),
                )

    def test_finalize_gap_waits_after_metadata_not_before_it(self):
        value = fully_proven_mutation()
        node = value["nodes"][0]
        remote_proof = node["proofs"].pop()
        gap = proof_gap(
            1,
            remote_proof["surface_id"],
            remote_proof["node_head_sha"],
            remote_proof["dependency_head_sha"],
        )
        gap["blocks_action"] = "finalize"
        node["open_proof_gaps"] = [gap]
        value["proof_wait_owner_ref"] = "external-proof-owner-1"
        add_history_receipts(value, 2)

        result = result_for(value)
        self.assertEqual(result["readiness"], "metadata-ready")
        self.assertEqual(result["next_action_id"], "metadata-1")

        add_metadata_receipt(value)
        result = result_for(value)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["readiness"], "proof-wait")

        node["open_proof_gaps"] = []
        node["proofs"].append(remote_proof)
        value["proof_wait_owner_ref"] = None
        result = result_for(value)
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["metadata_completed"])

    def test_metadata_receipt_is_exact_content_bound_and_gate_aware(self):
        value = add_history_receipts(fully_proven_mutation(), 2)
        add_metadata_receipt(value)
        value["metadata_receipt"]["readback_target_ref"] = "refs/heads/other"
        receipt_codes = codes(value)
        self.assertIn("metadata_receipt_digest_mismatch", receipt_codes)
        self.assertIn("metadata_receipt_target_readback_mismatch", receipt_codes)

        value = add_history_receipts(fully_proven_mutation(), 2)
        add_metadata_receipt(value)
        value["metadata_receipt"]["readback_new_target_head_sha"] = OTHER
        self.assertIn(
            "metadata_receipt_target_head_readback_mismatch",
            codes(value),
        )

        value = add_history_receipts(prepared_mutation(), 2)
        add_metadata_receipt(value)
        self.assertIn("metadata_receipt_bypasses_open_gate", codes(value))


class PreparedMutationCliAndSafetyTests(unittest.TestCase):
    def run_main(self, value: dict) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prepared.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                status = guard.main(
                    ["validate-prepared-mutation", "--input", str(path)]
                )
        return status, json.loads(output.getvalue())

    def test_cli_returns_zero_for_valid_package(self):
        status, output = self.run_main(prepared_mutation())
        self.assertEqual(status, 0)
        self.assertEqual(output["status"], "ready")
        self.assertEqual(output["readiness"], "history-ready")
        self.assertEqual(output["next_action_id"], "history-1")
        self.assertEqual(
            output["schema"],
            guard.PREPARED_MUTATION_VALIDATION_SCHEMA,
        )

    def test_cli_returns_two_when_a_safety_gate_fails(self):
        value = prepared_mutation()
        value["nodes"][0]["attribution"]["new_author_fingerprint"] = DIGEST_A
        status, output = self.run_main(value)
        self.assertEqual(status, 2)
        self.assertEqual(output["status"], "fail")

    def test_guard_remains_read_only_and_has_no_supervisor_runtime_fields(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        forbidden_imports = {
            "subprocess",
            "socket",
            "urllib",
            "http",
            "ftplib",
            "requests",
            "git",
        }
        imports: set[str] = set()
        writes: list[str] = []
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in item.names)
            elif isinstance(item, ast.ImportFrom) and item.module:
                imports.add(item.module.split(".")[0])
            elif isinstance(item, ast.Call):
                function = item.func
                if isinstance(function, ast.Attribute) and function.attr in {
                    "write_text",
                    "write_bytes",
                    "touch",
                    "mkdir",
                    "unlink",
                    "rename",
                    "replace",
                }:
                    writes.append(function.attr)
        self.assertFalse(imports & forbidden_imports)
        self.assertEqual(writes, [])
        self.assertNotIn("heartbeat", guard.PREPARED_MUTATION_KEYS)
        self.assertNotIn("cursor", guard.PREPARED_MUTATION_KEYS)


class PreparedMutationGuidanceTests(unittest.TestCase):
    def test_skill_routes_future_rewrite_handoffs_to_the_contract(self):
        compact = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "future history rewrite prepared for another task",
            "references/prepared-mutation-handoff.md",
            "validate the additive prepared mutation handoff",
            "does not expand the receiver's authority",
        ):
            self.assertIn(invariant, compact)

    def test_reference_preserves_safety_and_ownership_boundaries(self):
        compact = " ".join(REFERENCE.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "stacked_delivery.prepared_mutation_handoff.v1",
            "successful proof or green remote pipeline cannot override attribution drift",
            "preserve-author-allow-authorized-committer",
            "opaque proof-policy id and fingerprint",
            "opaque attribution-policy id and fingerprint",
            "explicit new predecessor",
            "one unique full `refs/` backup",
            "`refs/stacked-delivery/backups/`",
            "exact-remote-head",
            "`history_receipts` is an ordered, contiguous prefix",
            "one immutable transaction digest",
            "not a watcher cursor",
            "all history actions appear first",
            "metadata actions are optional",
            "metadata update is not composition proof",
            "tags, notes, and remote-tracking refs are rejected",
            "`metadata-ready`",
            "`metadata_receipt` must bind the immutable transaction digest",
            "a `finalize` gap does not block metadata",
            "a higher node's gap does not block the lower next action",
            "`proof_wait_owner_ref` is null when no gap is open",
            "does not embed scheduler, heartbeat, cursor, host, or polling state",
            "one git object-id width",
            "retarget predecessor ref must equal its bound head",
            "preserve backups and the last confirmed old/new mapping",
        ):
            self.assertIn(invariant, compact)

    def test_guidance_is_ascii_and_public_safe(self):
        for path in (SKILL, REFERENCE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            for forbidden in (
                "/Users/",
                "\\Users\\",
                "BEGIN PRIVATE KEY",
                "b2broker",
                "b2core",
            ):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
