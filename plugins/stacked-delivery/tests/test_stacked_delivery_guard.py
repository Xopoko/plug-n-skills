import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
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
SPEC = importlib.util.spec_from_file_location("stacked_delivery_guard", SCRIPT)
assert SPEC is not None
guard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(guard)


BASE = "a" * 40
HEAD_1 = "b" * 40
HEAD_2 = "c" * 40
HEAD_3 = "d" * 40
OTHER = "e" * 40
LAND_1 = "1" * 40
LAND_2 = "2" * 40
LAND_3 = "3" * 40


def proof(index, node_head, dependency_head, **overrides):
    value = {
        "proof_id": f"proof-{index}",
        "node_id": f"node-{index}",
        "node_head_sha": node_head,
        "dependency_head_sha": dependency_head,
        "status": "success",
        "terminal": True,
        "superseded": False,
    }
    value.update(overrides)
    return value


def node(index, head, parent, target, dependency, **overrides):
    value = {
        "node_id": f"node-{index}",
        "change_id": f"change-{index}",
        "source_branch": f"stack/change-{index}",
        "target_branch": target,
        "head_sha": head,
        "landing_head_sha": None,
        "parent_node_id": parent,
        "expected_parent_head_sha": dependency,
        "worktree_id": f"worktree-{index}",
        "writer_id": f"writer-{index}",
        "state": "unlanded",
        "proofs": [proof(index, head, dependency)],
    }
    value.update(overrides)
    return value


def snapshot(mode="sequential"):
    return {
        "schema": guard.SNAPSHOT_SCHEMA,
        "repository_id": "repository-1",
        "forge_adapter": "generic-v1",
        "stack_id": "stack-1",
        "forge_mode": mode,
        "base": {"branch": "main", "head_sha": BASE},
        "nodes": [
            node(1, HEAD_1, None, "main", BASE),
            node(2, HEAD_2, "node-1", "stack/change-1", HEAD_1),
            node(3, HEAD_3, "node-2", "stack/change-2", HEAD_2),
        ],
    }


def landed_snapshot():
    value = snapshot()
    value["base"]["head_sha"] = LAND_1
    value["nodes"][0]["state"] = "landed"
    value["nodes"][0]["landing_head_sha"] = LAND_1
    value["nodes"][0]["worktree_id"] = None
    value["nodes"][0]["writer_id"] = None
    value["nodes"][1]["state"] = "retargeted"
    value["nodes"][1]["target_branch"] = "main"
    value["nodes"][1]["expected_parent_head_sha"] = LAND_1
    value["nodes"][1]["proofs"][0]["dependency_head_sha"] = LAND_1
    return value


def all_landed_snapshot(mode="sequential"):
    value = snapshot(mode)
    value["base"]["head_sha"] = LAND_3
    landing_heads = [LAND_1, LAND_2, LAND_3]
    for index, item in enumerate(value["nodes"]):
        item["state"] = "landed"
        item["landing_head_sha"] = landing_heads[index]
        item["worktree_id"] = None
        item["writer_id"] = None
        if mode == "sequential":
            item["target_branch"] = "main"
            if index:
                dependency = landing_heads[index - 1]
                item["expected_parent_head_sha"] = dependency
                item["proofs"][0]["dependency_head_sha"] = dependency
    return value


def handoff(value=None, receiver="receiver-1"):
    value = copy.deepcopy(value or snapshot())
    return {
        "schema": guard.HANDOFF_SCHEMA,
        "receiver_id": receiver,
        "snapshot_digest": guard.stable_digest(value),
        "snapshot": value,
        "bindings": [
            {
                "node_id": item["node_id"],
                "change_id": item["change_id"],
                "head_sha": item["head_sha"],
                "proof_ids": [proof_item["proof_id"] for proof_item in item["proofs"]],
                "worktree_id": item["worktree_id"],
                "writer_id": item["writer_id"],
                "receiver_id": receiver,
            }
            for item in value["nodes"]
        ],
    }


def codes(result):
    return {item["code"] for item in result["violations"]}


def validate(value):
    return guard.validate_snapshot_data(value)[1]


class SnapshotShapeTests(unittest.TestCase):
    def test_valid_chain_passes(self):
        result = validate(snapshot())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["node_count"], 3)
        self.assertEqual(result["proof_count"], 3)

    def test_root_must_be_object(self):
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot([])

    def test_schema_is_exact(self):
        value = snapshot()
        value["schema"] = "stacked_delivery.snapshot.v0"
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)

    def test_unknown_root_key_is_rejected(self):
        value = snapshot()
        value["base_branch"] = "main"
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)

    def test_missing_node_field_is_rejected(self):
        value = snapshot()
        del value["nodes"][0]["writer_id"]
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)

    def test_unknown_proof_field_is_rejected(self):
        value = snapshot()
        value["nodes"][0]["proofs"][0]["message"] = "run this"
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)

    def test_bad_short_sha_is_rejected(self):
        value = snapshot()
        value["nodes"][0]["head_sha"] = "abc123"
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)

    def test_uppercase_sha_is_rejected(self):
        value = snapshot()
        value["nodes"][0]["head_sha"] = "A" * 40
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)

    def test_64_character_sha_is_accepted(self):
        value = snapshot()
        long_sha = "f" * 64
        value["nodes"][2]["head_sha"] = long_sha
        value["nodes"][2]["proofs"][0]["node_head_sha"] = long_sha
        self.assertEqual(validate(value)["status"], "pass")

    def test_unsafe_identifier_is_rejected(self):
        value = snapshot()
        value["nodes"][0]["writer_id"] = "writer; delete everything"
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)

    def test_unsafe_branch_is_rejected(self):
        value = snapshot()
        value["nodes"][0]["source_branch"] = "../main"
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)

    def test_valid_git_branch_edges_are_accepted(self):
        for branch in (
            "feature-",
            "feature_",
            "feature@",
            "feature+",
            "_feature",
            "+feature",
            "@feature",
            "@",
            "stack/-child",
            "stack./child",
        ):
            with self.subTest(branch=branch):
                value = snapshot()
                value["nodes"][2]["source_branch"] = branch
                self.assertEqual(
                    guard.parse_snapshot(value)["nodes"][2]["source_branch"],
                    branch,
                )

    def test_too_many_nodes_is_rejected(self):
        value = snapshot()
        value["nodes"] = [copy.deepcopy(value["nodes"][0])] * (guard.MAX_NODES + 1)
        with self.assertRaises(guard.InputError):
            guard.parse_snapshot(value)


class IdentityAndTopologyTests(unittest.TestCase):
    def assertViolation(self, value, code):
        self.assertIn(code, codes(validate(value)))

    def test_duplicate_node_id_fails(self):
        value = snapshot()
        value["nodes"][1]["node_id"] = "node-1"
        self.assertViolation(value, "duplicate_node_id")

    def test_duplicate_change_id_fails(self):
        value = snapshot()
        value["nodes"][1]["change_id"] = "change-1"
        self.assertViolation(value, "duplicate_change_id")

    def test_duplicate_source_branch_fails(self):
        value = snapshot()
        value["nodes"][1]["source_branch"] = "stack/change-1"
        self.assertViolation(value, "duplicate_source_branch")

    def test_source_branch_must_not_equal_base_branch(self):
        value = snapshot()
        value["nodes"][0]["source_branch"] = "main"
        self.assertViolation(value, "source_branch_conflicts_base")

    def test_duplicate_active_worktree_fails(self):
        value = snapshot()
        value["nodes"][1]["worktree_id"] = "worktree-1"
        self.assertViolation(value, "duplicate_active_worktree")

    def test_one_writer_may_own_multiple_worktrees(self):
        value = snapshot()
        value["nodes"][1]["writer_id"] = "writer-1"
        self.assertEqual(validate(value)["status"], "pass")

    def test_unassigned_node_has_explicit_null_pair(self):
        value = snapshot()
        value["nodes"][2]["worktree_id"] = None
        value["nodes"][2]["writer_id"] = None
        self.assertEqual(validate(value)["status"], "pass")

    def test_partial_ownership_binding_fails(self):
        value = snapshot()
        value["nodes"][2]["writer_id"] = None
        self.assertViolation(value, "incomplete_ownership_binding")

    def test_bottom_parent_must_be_null(self):
        value = snapshot()
        value["nodes"][0]["parent_node_id"] = "node-3"
        self.assertViolation(value, "bottom_parent_not_null")

    def test_cycle_fails(self):
        value = snapshot()
        value["nodes"][0]["parent_node_id"] = "node-3"
        self.assertViolation(value, "parent_cycle")

    def test_non_linear_parent_fails(self):
        value = snapshot()
        value["nodes"][2]["parent_node_id"] = "node-1"
        self.assertViolation(value, "nonlinear_parent")

    def test_fork_fails(self):
        value = snapshot()
        value["nodes"][2]["parent_node_id"] = "node-1"
        self.assertViolation(value, "parent_fork")

    def test_unknown_parent_fails(self):
        value = snapshot()
        value["nodes"][1]["parent_node_id"] = "node-9"
        self.assertViolation(value, "unknown_parent")

    def test_bottom_target_must_be_base(self):
        value = snapshot()
        value["nodes"][0]["target_branch"] = "develop"
        self.assertViolation(value, "bottom_target_mismatch")

    def test_higher_target_must_be_parent_source(self):
        value = snapshot()
        value["nodes"][2]["target_branch"] = "main"
        self.assertViolation(value, "target_branch_mismatch")

    def test_expected_parent_head_must_match(self):
        value = snapshot()
        value["nodes"][2]["expected_parent_head_sha"] = OTHER
        self.assertViolation(value, "expected_parent_head_mismatch")

    def test_bottom_expected_head_must_match_base(self):
        value = snapshot()
        value["nodes"][0]["expected_parent_head_sha"] = OTHER
        self.assertViolation(value, "bottom_expected_head_mismatch")


class ProofTests(unittest.TestCase):
    def assertViolation(self, mutate, code):
        value = snapshot()
        mutate(value["nodes"][1]["proofs"][0], value)
        self.assertIn(code, codes(validate(value)))

    def test_stale_node_head_fails(self):
        self.assertViolation(
            lambda item, _: item.update(node_head_sha=OTHER),
            "proof_node_head_stale",
        )

    def test_stale_dependency_head_fails(self):
        self.assertViolation(
            lambda item, _: item.update(dependency_head_sha=OTHER),
            "proof_dependency_head_stale",
        )

    def test_inherited_parent_proof_fails(self):
        self.assertViolation(
            lambda item, _: item.update(node_id="node-1"),
            "proof_node_mismatch",
        )

    def test_nonterminal_proof_fails(self):
        self.assertViolation(
            lambda item, _: item.update(terminal=False),
            "proof_not_terminal",
        )

    def test_unsuccessful_proof_fails(self):
        self.assertViolation(
            lambda item, _: item.update(status="failure"),
            "proof_not_successful",
        )

    def test_superseded_proof_fails(self):
        self.assertViolation(
            lambda item, _: item.update(superseded=True),
            "proof_superseded",
        )

    def test_duplicate_proof_id_across_nodes_fails(self):
        value = snapshot()
        value["nodes"][1]["proofs"][0]["proof_id"] = "proof-1"
        self.assertIn("duplicate_proof_id", codes(validate(value)))

    def test_empty_proof_collection_is_valid_snapshot(self):
        value = snapshot()
        value["nodes"][0]["proofs"] = []
        self.assertEqual(validate(value)["status"], "pass")


class StateAndActionTests(unittest.TestCase):
    def test_out_of_order_landing_fails(self):
        value = snapshot()
        value["nodes"][1]["state"] = "landed"
        self.assertIn("out_of_order_landed", codes(validate(value)))

    def test_retarget_without_landing_fails(self):
        value = snapshot()
        value["nodes"][0]["state"] = "retargeted"
        self.assertIn("retarget_without_landed_prefix", codes(validate(value)))

    def test_landed_prefix_requires_current_base_head(self):
        value = landed_snapshot()
        value["base"]["head_sha"] = OTHER
        self.assertIn("landed_base_head_mismatch", codes(validate(value)))

    def test_landed_node_requires_resulting_integration_head(self):
        value = landed_snapshot()
        value["nodes"][0]["landing_head_sha"] = None
        self.assertIn("landed_head_missing", codes(validate(value)))

    def test_unlanded_node_rejects_landing_head(self):
        value = snapshot()
        value["nodes"][0]["landing_head_sha"] = LAND_1
        self.assertIn("unexpected_landing_head", codes(validate(value)))

    def test_landed_node_releases_ownership(self):
        value = landed_snapshot()
        value["nodes"][0]["worktree_id"] = "worktree-1"
        value["nodes"][0]["writer_id"] = "writer-1"
        self.assertIn("landed_ownership_not_released", codes(validate(value)))

    def test_lower_landing_requires_retargeted_next_node(self):
        value = landed_snapshot()
        value["nodes"][1]["state"] = "unlanded"
        self.assertIn("missing_retarget_after_landing", codes(validate(value)))

    def test_coherent_retarget_state_passes(self):
        self.assertEqual(validate(landed_snapshot())["status"], "pass")

    def test_sequential_returns_only_lowest_unlanded_node(self):
        _, result = guard.next_action_data(snapshot())
        self.assertEqual(result["status"], "ready")
        self.assertEqual([item["node_id"] for item in result["nodes"]], ["node-1"])
        self.assertEqual(result["nodes"][0]["expected_parent_head_sha"], BASE)

    def test_atomic_prefix_returns_contiguous_proven_prefix(self):
        _, result = guard.next_action_data(snapshot("atomic-prefix"))
        self.assertEqual(
            [item["node_id"] for item in result["nodes"]],
            ["node-1", "node-2", "node-3"],
        )

    def test_atomic_prefix_stops_at_first_missing_proof(self):
        value = snapshot("atomic-prefix")
        value["nodes"][1]["proofs"] = []
        _, result = guard.next_action_data(value)
        self.assertEqual([item["node_id"] for item in result["nodes"]], ["node-1"])

    def test_atomic_prefix_never_skips_unproven_bottom(self):
        value = snapshot("atomic-prefix")
        value["nodes"][0]["proofs"] = []
        _, result = guard.next_action_data(value)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["nodes"], [])

    def test_next_action_after_landing_is_retargeted_node(self):
        _, result = guard.next_action_data(landed_snapshot())
        self.assertEqual(result["nodes"][0]["node_id"], "node-2")

    def test_all_landed_is_complete(self):
        value = all_landed_snapshot()
        _, result = guard.next_action_data(value)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["nodes"], [])

    def test_two_sequential_non_fast_forward_landings_pass(self):
        value = all_landed_snapshot()
        self.assertEqual(validate(value)["status"], "pass")
        self.assertNotEqual(
            value["nodes"][0]["landing_head_sha"],
            value["nodes"][0]["head_sha"],
        )
        self.assertEqual(value["nodes"][1]["expected_parent_head_sha"], LAND_1)

    def test_atomic_prefix_preserves_parent_source_topology(self):
        value = all_landed_snapshot("atomic-prefix")
        self.assertEqual(validate(value)["status"], "pass")
        self.assertEqual(value["nodes"][1]["target_branch"], "stack/change-1")


class CompareTests(unittest.TestCase):
    def test_identical_snapshots_pass(self):
        _, _, result = guard.compare_snapshot_data(snapshot(), snapshot())
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["invalidated_descendants"], [])

    def test_ancestor_head_drift_invalidates_every_descendant(self):
        before = snapshot()
        after = snapshot()
        after["nodes"][0]["head_sha"] = OTHER
        after["nodes"][0]["proofs"][0]["node_head_sha"] = OTHER
        after["nodes"][1]["expected_parent_head_sha"] = OTHER
        after["nodes"][1]["proofs"][0]["dependency_head_sha"] = OTHER
        _, _, result = guard.compare_snapshot_data(before, after)
        self.assertEqual(result["status"], "fail")
        invalidated_ids = {
            item["node_id"] for item in result["invalidated_descendants"]
        }
        self.assertIn("node-1", invalidated_ids)
        self.assertIn("node-2", invalidated_ids)
        self.assertIn("node-3", invalidated_ids)

    def test_proofless_head_drift_invalidates_self_and_descendants(self):
        before = snapshot()
        after = snapshot()
        before["nodes"][0]["proofs"] = []
        after["nodes"][0]["proofs"] = []
        after["nodes"][0]["head_sha"] = OTHER
        after["nodes"][1]["expected_parent_head_sha"] = OTHER
        after["nodes"][1]["proofs"][0]["dependency_head_sha"] = OTHER
        _, _, result = guard.compare_snapshot_data(before, after)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(
            {item["node_id"] for item in result["invalidated_descendants"]},
            {"node-1", "node-2", "node-3"},
        )

    def test_base_head_drift_invalidates_all_nodes(self):
        before = snapshot()
        after = snapshot()
        after["base"]["head_sha"] = OTHER
        after["nodes"][0]["expected_parent_head_sha"] = OTHER
        after["nodes"][0]["proofs"][0]["dependency_head_sha"] = OTHER
        _, _, result = guard.compare_snapshot_data(before, after)
        self.assertEqual(
            {item["node_id"] for item in result["invalidated_descendants"]},
            {"node-1", "node-2", "node-3"},
        )

    def test_topology_order_change_fails_closed(self):
        after = snapshot()
        after["nodes"][1], after["nodes"][2] = (
            after["nodes"][2],
            after["nodes"][1],
        )
        _, _, result = guard.compare_snapshot_data(snapshot(), after)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["topology_changes"])

    def test_identity_change_fails_closed(self):
        after = snapshot()
        after["nodes"][1]["change_id"] = "change-new"
        _, _, result = guard.compare_snapshot_data(snapshot(), after)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["topology_changes"])

    def test_repository_or_forge_scope_change_invalidates_all(self):
        for field, replacement in (
            ("repository_id", "repository-2"),
            ("forge_adapter", "generic-v2"),
        ):
            with self.subTest(field=field):
                after = snapshot()
                after[field] = replacement
                _, _, result = guard.compare_snapshot_data(snapshot(), after)
                self.assertEqual(result["status"], "fail")
                self.assertEqual(
                    {item["node_id"] for item in result["invalidated_descendants"]},
                    {"node-1", "node-2", "node-3"},
                )

    def test_branch_drift_is_detected(self):
        after = snapshot()
        after["nodes"][1]["source_branch"] = "stack/rebased-2"
        after["nodes"][2]["target_branch"] = "stack/rebased-2"
        _, _, result = guard.compare_snapshot_data(snapshot(), after)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(result["branch_drift"])
        self.assertEqual(
            {item["node_id"] for item in result["invalidated_descendants"]},
            {"node-2", "node-3"},
        )

    def test_state_change_fails_comparison(self):
        after = snapshot()
        after["nodes"][0]["state"] = "landed"
        _, _, result = guard.compare_snapshot_data(snapshot(), after)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["state_changes"][0]["node_id"], "node-1")

    def test_dependency_drift_invalidates_self_and_descendants(self):
        after = snapshot()
        after["nodes"][1]["expected_parent_head_sha"] = OTHER
        after["nodes"][1]["proofs"][0]["dependency_head_sha"] = OTHER
        _, _, result = guard.compare_snapshot_data(snapshot(), after)
        self.assertEqual(
            {item["node_id"] for item in result["invalidated_descendants"]},
            {"node-2", "node-3"},
        )

    def test_proof_refresh_invalidates_node_and_descendants(self):
        after = snapshot()
        after["nodes"][0]["proofs"][0]["proof_id"] = "proof-new"
        _, _, result = guard.compare_snapshot_data(snapshot(), after)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["proof_changes"], [{"node_id": "node-1"}])
        self.assertEqual(
            {item["node_id"] for item in result["invalidated_descendants"]},
            {"node-1", "node-2", "node-3"},
        )


class HandoffTests(unittest.TestCase):
    def test_valid_handoff_passes(self):
        value = handoff()
        _, result = guard.validate_handoff_data(value)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["handoff_digest"], guard.stable_digest(value))

    def test_receiver_change_creates_a_new_handoff_digest(self):
        first = handoff(receiver="receiver-1")
        second = handoff(receiver="receiver-2")
        _, first_result = guard.validate_handoff_data(first)
        _, second_result = guard.validate_handoff_data(second)
        self.assertEqual(
            first_result["snapshot_digest"],
            second_result["snapshot_digest"],
        )
        self.assertNotEqual(
            first_result["handoff_digest"],
            second_result["handoff_digest"],
        )

    def test_scope_changes_snapshot_and_handoff_digests(self):
        for field, replacement in (
            ("repository_id", "repository-2"),
            ("forge_adapter", "generic-v2"),
        ):
            with self.subTest(field=field):
                first_snapshot = snapshot()
                second_snapshot = snapshot()
                second_snapshot[field] = replacement
                first = handoff(first_snapshot)
                second = handoff(second_snapshot)
                _, first_result = guard.validate_handoff_data(first)
                _, second_result = guard.validate_handoff_data(second)
                self.assertNotEqual(
                    first_result["snapshot_digest"],
                    second_result["snapshot_digest"],
                )
                self.assertNotEqual(
                    first_result["handoff_digest"],
                    second_result["handoff_digest"],
                )

    def test_stale_snapshot_digest_fails(self):
        value = handoff()
        value["snapshot_digest"] = "f" * 64
        _, result = guard.validate_handoff_data(value)
        self.assertIn("stale_snapshot_digest", codes(result))

    def test_head_binding_mismatch_fails(self):
        value = handoff()
        value["bindings"][1]["head_sha"] = OTHER
        _, result = guard.validate_handoff_data(value)
        self.assertIn("binding_head_mismatch", codes(result))

    def test_proof_binding_mismatch_fails(self):
        value = handoff()
        value["bindings"][1]["proof_ids"] = []
        _, result = guard.validate_handoff_data(value)
        self.assertIn("binding_proof_mismatch", codes(result))

    def test_worktree_binding_mismatch_fails(self):
        value = handoff()
        value["bindings"][1]["worktree_id"] = "worktree-new"
        _, result = guard.validate_handoff_data(value)
        self.assertIn("binding_worktree_mismatch", codes(result))

    def test_writer_binding_mismatch_fails(self):
        value = handoff()
        value["bindings"][1]["writer_id"] = "writer-new"
        _, result = guard.validate_handoff_data(value)
        self.assertIn("binding_writer_mismatch", codes(result))

    def test_receiver_binding_mismatch_fails(self):
        value = handoff()
        value["bindings"][1]["receiver_id"] = "receiver-2"
        _, result = guard.validate_handoff_data(value)
        self.assertIn("binding_receiver_mismatch", codes(result))

    def test_one_writer_may_own_multiple_handoff_worktrees(self):
        value = snapshot()
        value["nodes"][1]["writer_id"] = "writer-1"
        receipt = handoff(value)
        _, result = guard.validate_handoff_data(receipt)
        self.assertEqual(result["status"], "pass")

    def test_duplicate_active_binding_worktree_fails(self):
        value = handoff()
        value["bindings"][1]["worktree_id"] = "worktree-1"
        _, result = guard.validate_handoff_data(value)
        self.assertIn("duplicate_binding_active_worktree", codes(result))

    def test_partial_binding_ownership_fails(self):
        value = handoff()
        value["bindings"][1]["writer_id"] = None
        _, result = guard.validate_handoff_data(value)
        self.assertIn("incomplete_binding_ownership", codes(result))

    def test_duplicate_binding_node_fails(self):
        value = handoff()
        value["bindings"][1]["node_id"] = "node-1"
        _, result = guard.validate_handoff_data(value)
        self.assertIn("duplicate_binding_node_id", codes(result))

    def test_binding_count_mismatch_fails(self):
        value = handoff()
        value["bindings"].pop()
        _, result = guard.validate_handoff_data(value)
        self.assertIn("binding_count_mismatch", codes(result))


class CliAndSafetyTests(unittest.TestCase):
    def run_main(self, argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = guard.main(argv)
        return status, json.loads(output.getvalue())

    def test_malformed_json_exits_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{", encoding="utf-8")
            status, output = self.run_main(["validate-snapshot", "--input", str(path)])
        self.assertEqual(status, 1)
        self.assertEqual(output["schema"], guard.ERROR_SCHEMA)

    def test_duplicate_json_key_exits_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema":"x","schema":"y"}', encoding="utf-8")
            status, _ = self.run_main(["validate-snapshot", "--input", str(path)])
        self.assertEqual(status, 1)

    def test_json_integer_exits_one_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "number.json"
            path.write_text("9" * 5000, encoding="utf-8")
            status, output = self.run_main(["validate-snapshot", "--input", str(path)])
        self.assertEqual(status, 1)
        self.assertEqual(output["schema"], guard.ERROR_SCHEMA)

    def test_unreadable_input_exits_one(self):
        status, _ = self.run_main(
            ["validate-snapshot", "--input", "missing-input.json"]
        )
        self.assertEqual(status, 1)

    def test_oversized_input_exits_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "huge.json"
            path.write_bytes(b" " * (guard.MAX_INPUT_BYTES + 1))
            status, _ = self.run_main(["validate-snapshot", "--input", str(path)])
        self.assertEqual(status, 1)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO is unavailable")
    def test_nonregular_input_exits_one(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.fifo"
            os.mkfifo(path)
            status, output = self.run_main(["validate-snapshot", "--input", str(path)])
        self.assertEqual(status, 1)
        self.assertEqual(output["schema"], guard.ERROR_SCHEMA)

    def test_hidden_ref_component_exits_one(self):
        value = snapshot()
        value["nodes"][0]["source_branch"] = "stack/.hidden"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            status, output = self.run_main(["validate-snapshot", "--input", str(path)])
        self.assertEqual(status, 1)
        self.assertEqual(output["schema"], guard.ERROR_SCHEMA)

    def test_gate_failure_exits_two(self):
        value = snapshot()
        value["nodes"][0]["proofs"][0]["terminal"] = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            status, output = self.run_main(["validate-snapshot", "--input", str(path)])
        self.assertEqual(status, 2)
        self.assertEqual(output["status"], "fail")

    def test_pass_exits_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(snapshot()), encoding="utf-8")
            status, output = self.run_main(["validate-snapshot", "--input", str(path)])
        self.assertEqual(status, 0)
        self.assertEqual(output["status"], "pass")

    def test_script_has_no_network_git_subprocess_or_file_writes(self):
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
        imports = set()
        forbidden_calls = []
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
                    forbidden_calls.append(function.attr)
        self.assertFalse(imports & forbidden_imports)
        self.assertEqual(forbidden_calls, [])


if __name__ == "__main__":
    unittest.main()
