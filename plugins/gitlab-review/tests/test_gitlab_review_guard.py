import ast
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "gitlab-review-response"
    / "scripts"
    / "gitlab_review_guard.py"
)
SPEC = importlib.util.spec_from_file_location("gitlab_review_guard", SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(guard)


HEAD_A = "a" * 40
HEAD_B = "b" * 40
BASE = "c" * 40
START = "d" * 40
TARGET = "e" * 40
ACTOR_ID = "777"
HOST = "gitlab.example.test"
RESPONSE_TEXT = "Addressed in the current review epoch."
RESPONSE_HASH = guard.stable_hash(RESPONSE_TEXT)


def merge_request(head=HEAD_A, **overrides):
    value = {
        "id": 101,
        "iid": 7,
        "project_id": 42,
        "source_project_id": 41,
        "target_project_id": 42,
        "state": "opened",
        "source_branch": "feature/review-fix",
        "target_branch": "main",
        "sha": head,
        "diff_refs": {
            "base_sha": BASE,
            "head_sha": head,
            "start_sha": START,
        },
        "head_pipeline": {
            "id": 701,
            "sha": head,
            "status": "success",
            "source": "merge_request_event",
        },
    }
    value.update(overrides)
    return value


def diff_version(head=HEAD_A, **overrides):
    value = {
        "id": 9,
        "base_commit_sha": BASE,
        "head_commit_sha": head,
        "start_commit_sha": START,
    }
    value.update(overrides)
    return value


def note(
    note_id,
    body="Please handle the edge case.",
    *,
    author_id=501,
    resolved=False,
    updated_at="2026-01-01T10:00:00Z",
    new_line=12,
):
    return {
        "id": note_id,
        "type": "DiffNote",
        "body": body,
        "author": {"id": author_id, "username": "reviewer"},
        "created_at": "2026-01-01T09:00:00Z",
        "updated_at": updated_at,
        "system": False,
        "resolvable": True,
        "resolved": resolved,
        "position": {
            "position_type": "text",
            "base_sha": BASE,
            "head_sha": HEAD_A,
            "new_path": "src/example.py",
            "new_line": new_line,
        },
    }


def discussion(discussion_id="d-1", notes=None, **overrides):
    value = {
        "id": discussion_id,
        "individual_note": False,
        "notes": notes if notes is not None else [note(11)],
    }
    value.update(overrides)
    return value


def collection_from_value(value, *, assume=True):
    return guard.parse_discussions_text(
        json.dumps(value), assume_complete_array=assume
    )


def snapshot_from_value(
    value,
    *,
    assume=True,
    mr=None,
    diff=None,
    source_ref=HEAD_A,
    target_ref=TARGET,
):
    return guard.build_snapshot(
        mr or merge_request(),
        collection_from_value(value, assume=assume),
        host=HOST,
        actor_id=ACTOR_ID,
        source_ref_head=source_ref,
        target_ref_head=target_ref,
        diff_version_value=diff or diff_version(),
    )


def pipeline_collection(values=None, *, assume=True):
    values = values or [
        {"id": 701, "sha": HEAD_A, "status": "success"}
    ]
    return guard.parse_pipelines_text(
        json.dumps(values), assume_complete_array=assume
    )


def exact_head_proof(snapshot, pipelines=None):
    return guard.verify_exact_head(
        snapshot,
        HEAD_A,
        local_head=HEAD_A,
        source_ref_head=HEAD_A,
        pipeline_collection=pipelines or pipeline_collection(),
    )


def expected_contract(snapshot, discussion_id="d-1"):
    mr = snapshot["merge_request"]
    binding = snapshot["binding"]
    selected = next(
        item for item in snapshot["discussions"] if item["id"] == discussion_id
    )
    return {
        "host_hash": binding["host_hash"],
        "actor_id_hash": binding["actor_id_hash"],
        "project_id": mr["project_id"],
        "source_project_id": mr["source_project_id"],
        "target_project_id": mr["target_project_id"],
        "mr_iid": mr["iid"],
        "head_sha": mr["head_sha"],
        "diff_version_id": binding["diff_version"]["id"],
        "review_context_digest": snapshot["review_context_digest"],
        "epoch_digest": snapshot["epoch_digest"],
        "inventory_digest": snapshot["inventory_digest"],
        "discussion_id": discussion_id,
        "discussion_digest": selected["digest"],
    }


def validate_plan(snapshot, plan, proof=None):
    return guard.validate_action_plan(
        snapshot,
        plan,
        exact_head_proof=proof if proof is not None else exact_head_proof(snapshot),
    )


def valid_reply_plan(
    snapshot, *, no_change=False, response_hash=RESPONSE_HASH
):
    expected = expected_contract(snapshot)
    action = {
        "id": "reply-d-1",
        "type": "reply",
        "operation": "post",
        "discussion_id": "d-1",
        "addressed_note_ids": ["11"],
        "fix_commit": "no-change" if no_change else HEAD_A,
        "response_hash": response_hash,
        "dedupe": {
            "status": "clear",
            "matching_note_ids": [],
            "readback_complete": True,
            "readback_epoch_digest": snapshot["epoch_digest"],
        },
        "receipt": {"status": "not_attempted"},
        "delivery_head": HEAD_A,
    }
    if no_change:
        action["no_change_evidence_hash"] = guard.stable_hash(
            "No source edit was required."
        )
    action["dedupe_key"] = guard.make_dedupe_key(action, expected)
    posted_body = (
        RESPONSE_TEXT
        + "\n\n<!-- gitlab-review-response:v2:"
        + action["dedupe_key"]
        + " -->"
    )
    action["posted_body_hash"] = guard.stable_hash(posted_body)
    plan = {
        "schema": guard.PLAN_INPUT_SCHEMA,
        "mode": "reply-only",
        "writer": {"id": ACTOR_ID},
        "expected": expected,
        "actions": [action],
    }
    return plan


def confirmed_reply_fixture(
    *,
    resolvable=True,
    response_hash=RESPONSE_HASH,
    duplicate_reply=False,
    extra_reviewer_note=False,
    include_unaddressed_prewrite_note=False,
    edit_unaddressed_after_reply=False,
    system_reply=False,
):
    original = note(11)
    if not resolvable:
        original["type"] = None
        original["resolvable"] = False
        original.pop("resolved")
        original.pop("position")
    prewrite_notes = [original]
    if include_unaddressed_prewrite_note:
        prewrite_notes.append(
            note(
                12,
                body="A separate request.",
                author_id=502,
                updated_at="2026-01-01T10:01:00Z",
                new_line=13,
            )
        )
    before = snapshot_from_value([discussion(notes=prewrite_notes)])
    reply_plan = valid_reply_plan(before, response_hash=response_hash)
    reply_action = reply_plan["actions"][0]
    posted_body = (
        RESPONSE_TEXT
        + "\n\n<!-- gitlab-review-response:v2:"
        + reply_action["dedupe_key"]
        + " -->"
    )
    reply = note(
        9001,
        body=posted_body,
        author_id=int(ACTOR_ID),
        updated_at="2026-01-01T12:00:00Z",
        new_line=14,
    )
    reply["system"] = system_reply
    if not resolvable:
        reply["type"] = None
        reply["resolvable"] = False
        reply.pop("resolved")
        reply.pop("position")
    reply_notes = list(prewrite_notes) + [reply]
    if edit_unaddressed_after_reply:
        reply_notes[1] = note(
            12,
            body="A separately edited request.",
            author_id=502,
            updated_at="2026-01-01T12:03:00Z",
            new_line=13,
        )
    if duplicate_reply:
        duplicate = note(
            9002,
            body=posted_body,
            author_id=int(ACTOR_ID),
            updated_at="2026-01-01T12:01:00Z",
            new_line=15,
        )
        if not resolvable:
            duplicate["type"] = None
            duplicate["resolvable"] = False
            duplicate.pop("resolved")
            duplicate.pop("position")
        reply_notes.append(duplicate)
    if extra_reviewer_note:
        reply_notes.append(
            note(
                22,
                body="One more request.",
                author_id=501,
                updated_at="2026-01-01T12:02:00Z",
                new_line=16,
            )
        )
    snapshot = snapshot_from_value([discussion(notes=reply_notes)])
    discussion_value = snapshot["discussions"][0]
    reply_snapshot = next(
        item for item in discussion_value["notes"] if item["id"] == "9001"
    )
    receipt = {
        "status": "confirmed",
        "note_id": "9001",
        "response_hash": response_hash,
        "posted_body_hash": reply_action["posted_body_hash"],
        "response_key": reply_action["dedupe_key"],
        "delivery_head": reply_action["delivery_head"],
        "fix_commit": reply_action["fix_commit"],
        "addressed_note_ids": reply_action["addressed_note_ids"],
        "author_id_hash": snapshot["binding"]["actor_id_hash"],
        "note_fingerprint": reply_snapshot["fingerprint"],
        "readback_epoch_digest": snapshot["epoch_digest"],
        "reply_epoch_digest": before["epoch_digest"],
        "reply_review_context_digest": before["review_context_digest"],
        "reply_discussion_digest": before["discussions"][0]["digest"],
        "prewrite_discussion": {
            "id": before["discussions"][0]["id"],
            "resolution_hash": before["discussions"][0][
                "resolution_hash"
            ],
            "state_hash": before["discussions"][0]["state_hash"],
            "notes": [
                {
                    "id": item["id"],
                    "fingerprint": item["fingerprint"],
                }
                for item in before["discussions"][0]["notes"]
            ],
        },
    }
    if "no_change_evidence_hash" in reply_action:
        receipt["no_change_evidence_hash"] = reply_action[
            "no_change_evidence_hash"
        ]
    return snapshot, receipt


def valid_resolve_plan(snapshot, receipt):
    return {
        "schema": guard.PLAN_INPUT_SCHEMA,
        "mode": "resolve-only",
        "writer": {"id": ACTOR_ID},
        "expected": expected_contract(snapshot),
        "actions": [
            {
                "id": "resolve-d-1",
                "type": "resolve",
                "operation": "resolve",
                "discussion_id": "d-1",
                "authorization": {
                    "source": "user",
                    "evidence_id": "note:11",
                    "evidence_hash": guard.stable_hash(
                        "Reviewer asked the author to resolve after verification."
                    ),
                },
                "all_active_requests_addressed": True,
                "reread_discussion_digest": snapshot["discussions"][0]["digest"],
                "reply_receipt": receipt,
            }
        ],
    }


class SafetySurfaceTests(unittest.TestCase):
    def test_guard_imports_and_calls_remain_read_only(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported_roots = set()
        direct_calls = set()
        attribute_calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0] for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    direct_calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    attribute_calls.add(node.func.attr)

        self.assertLessEqual(
            imported_roots,
            {
                "__future__",
                "argparse",
                "hashlib",
                "ipaddress",
                "json",
                "pathlib",
                "re",
                "sys",
                "typing",
                "urllib",
            },
        )
        self.assertTrue(
            {"open", "exec", "eval", "compile"}.isdisjoint(direct_calls)
        )
        self.assertTrue(
            {
                "mkdir",
                "rename",
                "rmdir",
                "unlink",
                "write_bytes",
                "write_text",
            }.isdisjoint(attribute_calls)
        )


class SnapshotTests(unittest.TestCase):
    def test_raw_discussion_array_is_incomplete_without_explicit_declaration(self):
        snapshot = snapshot_from_value([discussion()], assume=False)
        self.assertFalse(snapshot["complete"])
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn(
            "caller_completeness_declaration_missing",
            snapshot["pagination"]["reasons"],
        )

    def test_declared_raw_array_is_body_free_and_mutation_safe(self):
        snapshot = snapshot_from_value([discussion()])
        self.assertTrue(snapshot["complete"])
        self.assertTrue(snapshot["mutation_safe"])
        serialized = json.dumps(snapshot, sort_keys=True)
        self.assertNotIn("Please handle the edge case.", serialized)
        self.assertNotIn('"body":', serialized)
        self.assertIn('"body_hash":', serialized)
        self.assertNotIn(HOST, serialized)
        self.assertNotIn(f'"{ACTOR_ID}"', serialized)

    def test_complete_paginated_chain_requires_order_and_one_terminal(self):
        pages = [
            {
                "page": 1,
                "next_page": 2,
                "items": [discussion("d-1")],
            },
            {
                "page": 2,
                "next_page": "",
                "items": [discussion("d-2", [note(12)])],
            },
        ]
        snapshot = snapshot_from_value(pages, assume=False)
        self.assertTrue(snapshot["complete"])
        self.assertTrue(snapshot["mutation_safe"])

    def test_completion_before_later_data_is_rejected(self):
        pages = [
            {
                "page": 1,
                "next_page": "",
                "items": [discussion("d-1")],
            },
            {
                "page": 2,
                "next_page": "",
                "items": [discussion("d-2", [note(12)])],
            },
        ]
        snapshot = snapshot_from_value(pages, assume=False)
        self.assertFalse(snapshot["complete"])
        self.assertIn("multiple_terminal_pages", snapshot["pagination"]["reasons"])
        self.assertIn("terminal_before_last_page", snapshot["pagination"]["reasons"])

    def test_top_level_complete_cannot_hide_missing_next_page(self):
        value = {
            "complete": True,
            "pages": [
                {
                    "page": 1,
                    "next_page": 2,
                    "items": [discussion()],
                }
            ],
        }
        snapshot = snapshot_from_value(value, assume=False)
        self.assertFalse(snapshot["complete"])
        self.assertIn("missing_next_page", snapshot["pagination"]["reasons"])

    def test_single_complete_envelope_needs_no_implicit_page_number(self):
        value = {
            "complete": True,
            "items": [discussion()],
        }
        snapshot = snapshot_from_value(value, assume=False)
        self.assertTrue(snapshot["complete"])
        self.assertTrue(snapshot["mutation_safe"])

    def test_multiple_implicit_page_terminals_are_incomplete(self):
        value = {
            "complete": True,
            "pages": [
                {"page": 1, "items": [discussion("d-1")]},
                {"page": 2, "items": [discussion("d-2", [note(12)])]},
            ],
        }
        snapshot = snapshot_from_value(value, assume=False)
        self.assertFalse(snapshot["complete"])
        self.assertIn("next_page_missing", snapshot["pagination"]["reasons"])

    def test_fractional_page_number_is_rejected(self):
        value = {
            "pages": [
                {
                    "page": 1.9,
                    "next_page": "",
                    "items": [discussion()],
                }
            ],
        }
        snapshot = snapshot_from_value(value, assume=False)
        self.assertFalse(snapshot["complete"])
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn("invalid_current_page", snapshot["pagination"]["reasons"])

    def test_conflicting_layered_pagination_is_rejected(self):
        value = {
            "page": 1,
            "next_page": "",
            "pagination": {"next_page": 2},
            "items": [discussion()],
        }
        with self.assertRaisesRegex(guard.GuardError, "conflicting"):
            snapshot_from_value(value, assume=False)

    def test_conflicting_layered_complete_flag_is_rejected(self):
        value = {
            "complete": True,
            "pagination": {"complete": False},
            "items": [discussion()],
        }
        with self.assertRaisesRegex(guard.GuardError, "conflicting"):
            snapshot_from_value(value, assume=False)

    def test_ndjson_completion_sentinel_must_be_last(self):
        raw = "\n".join(
            [
                json.dumps({"complete": True}),
                json.dumps(
                    {
                        "page": 1,
                        "next_page": "",
                        "items": [discussion()],
                    }
                ),
            ]
        )
        with self.assertRaisesRegex(guard.GuardError, "sentinel must be last"):
            guard.parse_discussions_text(raw)

    def test_duplicate_note_ids_block_mutation_even_when_identical(self):
        snapshot = snapshot_from_value(
            [
                discussion("d-1", [note(11)]),
                discussion("d-2", [note(11)]),
            ]
        )
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn("duplicate_note_id", snapshot["mutation_blockers"])

    def test_numeric_note_ids_are_canonicalized_before_duplicate_detection(self):
        snapshot = snapshot_from_value(
            [
                discussion("d-1", [note(11)]),
                discussion("d-2", [note("011")]),
            ]
        )
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn("duplicate_note_id", snapshot["mutation_blockers"])

    def test_invalid_dns_labels_are_rejected(self):
        for host in ("gitlab..example.test", "bad-.example"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(guard.GuardError, "DNS label"):
                    guard.build_snapshot(
                        merge_request(),
                        collection_from_value([discussion()]),
                        host=host,
                        actor_id=ACTOR_ID,
                        source_ref_head=HEAD_A,
                        target_ref_head=TARGET,
                        diff_version_value=diff_version(),
                    )

    def test_direct_discussion_cannot_mix_collection_fields(self):
        mixed = discussion()
        mixed["items"] = [discussion("ignored")]
        with self.assertRaisesRegex(guard.GuardError, "must not mix"):
            snapshot_from_value(mixed)

    def test_discussion_pages_cannot_mix_top_level_collection(self):
        mixed = {
            "complete": True,
            "items": [discussion("ignored")],
            "pages": [
                {
                    "page": 1,
                    "next_page": "",
                    "items": [discussion()],
                }
            ],
        }
        with self.assertRaisesRegex(
            guard.GuardError, "top-level collection"
        ):
            snapshot_from_value(mixed, assume=False)

    def test_structurally_incomplete_mr_blocks_mutation(self):
        mr = merge_request()
        del mr["source_project_id"]
        snapshot = snapshot_from_value([discussion()], mr=mr)
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn(
            "source_project_id_missing_or_invalid", snapshot["mutation_blockers"]
        )

    def test_missing_direct_mr_head_cannot_be_relabelled_safe(self):
        mr = merge_request()
        del mr["sha"]
        snapshot = snapshot_from_value([discussion()], mr=mr)
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn(
            "mr_head_missing_or_invalid", snapshot["mutation_blockers"]
        )
        snapshot["mutation_blockers"] = []
        snapshot["mutation_safe"] = True
        with self.assertRaisesRegex(guard.GuardError, "integrity"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_mismatched_head_pipeline_cannot_be_relabelled_safe(self):
        mr = merge_request()
        mr["head_pipeline"]["sha"] = HEAD_B
        snapshot = snapshot_from_value([discussion()], mr=mr)
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn(
            "head_pipeline_sha_mismatch", snapshot["mutation_blockers"]
        )
        snapshot["mutation_blockers"] = []
        snapshot["mutation_safe"] = True
        with self.assertRaisesRegex(guard.GuardError, "integrity"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_malformed_head_pipeline_types_are_rejected(self):
        for malformed in ("oops", [], 123, True):
            with self.subTest(malformed=malformed):
                with self.assertRaisesRegex(
                    guard.GuardError, "head_pipeline must be an object or null"
                ):
                    snapshot_from_value(
                        [discussion()],
                        mr=merge_request(head_pipeline=malformed),
                    )

    def test_malformed_head_pipeline_status_types_are_rejected(self):
        for malformed in (True, [], {}):
            with self.subTest(malformed=malformed):
                mr = merge_request()
                mr["head_pipeline"]["status"] = malformed
                with self.assertRaisesRegex(
                    guard.GuardError, "pipeline status must be a string"
                ):
                    snapshot_from_value([discussion()], mr=mr)

    def test_missing_head_pipeline_status_blocks_mutation(self):
        mr = merge_request()
        mr["head_pipeline"]["status"] = None
        snapshot = snapshot_from_value([discussion()], mr=mr)
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn(
            "head_pipeline_status_missing_or_invalid",
            snapshot["mutation_blockers"],
        )

    def test_conflicting_mr_head_aliases_are_rejected(self):
        with self.assertRaisesRegex(guard.GuardError, "aliases conflict"):
            snapshot_from_value(
                [discussion()],
                mr=merge_request(head_sha=HEAD_B),
            )

    def test_mr_wrapper_cannot_mix_direct_fields(self):
        with self.assertRaisesRegex(guard.GuardError, "must not mix"):
            snapshot_from_value(
                [discussion()],
                mr={
                    "merge_request": merge_request(),
                    "sha": HEAD_B,
                    "state": "closed",
                },
            )

    def test_conflicting_diff_version_aliases_are_rejected(self):
        with self.assertRaisesRegex(guard.GuardError, "aliases conflict"):
            snapshot_from_value(
                [discussion()],
                diff=diff_version(base_sha=HEAD_B),
            )

    def test_diff_version_wrapper_cannot_mix_direct_fields(self):
        with self.assertRaisesRegex(guard.GuardError, "must not mix"):
            snapshot_from_value(
                [discussion()],
                diff={
                    "diff_version": diff_version(),
                    "id": 999,
                    "head_commit_sha": HEAD_B,
                },
            )

    def test_malformed_branch_types_are_rejected(self):
        for field, malformed in (
            ("source_branch", ["feature"]),
            ("target_branch", {"name": "main"}),
            ("state", ["opened"]),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(guard.GuardError, field):
                    snapshot_from_value(
                        [discussion()],
                        mr=merge_request(**{field: malformed}),
                    )

    def test_discussion_id_must_be_a_nonempty_string(self):
        for malformed in (["d-1"], {"id": "d-1"}, 123, True, ""):
            with self.subTest(malformed=malformed):
                with self.assertRaisesRegex(
                    guard.GuardError, "non-empty string id"
                ):
                    snapshot_from_value([discussion(malformed)])

    def test_contradictory_discussion_resolution_state_is_rejected(self):
        resolved_note = note(11, resolved=True)
        with self.assertRaisesRegex(
            guard.GuardError, "resolved state conflicts with notes"
        ):
            snapshot_from_value(
                [discussion(notes=[resolved_note], resolved=False)]
            )

    def test_closed_mr_and_diff_version_mismatch_block_mutation(self):
        snapshot = snapshot_from_value(
            [discussion()],
            mr=merge_request(state="closed"),
            diff=diff_version(head_commit_sha=HEAD_B),
        )
        self.assertFalse(snapshot["mutation_safe"])
        self.assertIn("merge_request_not_opened", snapshot["mutation_blockers"])
        self.assertIn(
            "diff_version_head_sha_mismatch", snapshot["mutation_blockers"]
        )

    def test_target_ref_is_separate_from_merge_base(self):
        snapshot = snapshot_from_value([discussion()])
        self.assertEqual(snapshot["binding"]["target_ref_head"], TARGET)
        self.assertNotEqual(
            snapshot["binding"]["target_ref_head"],
            snapshot["merge_request"]["diff_refs"]["base_sha"],
        )

    def test_sparse_diff_note_is_rejected(self):
        sparse = note(11)
        del sparse["updated_at"]
        with self.assertRaisesRegex(guard.GuardError, "updated_at"):
            snapshot_from_value([discussion(notes=[sparse])])


class CompareTests(unittest.TestCase):
    def test_edited_snapshot_digest_is_rejected_as_malformed(self):
        snapshot = snapshot_from_value([discussion()])
        snapshot["discussions"][0]["notes"][0]["body_hash"] = "f" * 64
        with self.assertRaisesRegex(guard.GuardError, "integrity"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_binding_drift_fails_epoch_compare(self):
        before = snapshot_from_value([discussion()])
        after = snapshot_from_value([discussion()], target_ref=HEAD_B)
        result = guard.compare_snapshots(before, after)
        self.assertFalse(result["ok"])
        self.assertTrue(result["changes"]["binding"]["target_ref_head_changed"])

    def test_head_pipeline_tamper_breaks_snapshot_integrity(self):
        snapshot = snapshot_from_value([discussion()])
        snapshot["merge_request"]["head_pipeline"]["id"] = "702"
        with self.assertRaisesRegex(guard.GuardError, "integrity"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_pagination_evidence_tamper_breaks_snapshot_integrity(self):
        snapshot = snapshot_from_value([discussion()])
        snapshot["pagination"]["completion_basis"] = ["page_complete"]
        with self.assertRaisesRegex(guard.GuardError, "integrity"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_resolution_projection_tamper_breaks_snapshot_integrity(self):
        snapshot, _receipt = confirmed_reply_fixture(resolvable=False)
        snapshot["discussions"][0]["resolved"] = False
        for note_value in snapshot["discussions"][0]["notes"]:
            note_value["resolvable"] = True
            note_value["resolved"] = False
            note_value["type"] = "DiffNote"
        with self.assertRaisesRegex(guard.GuardError, "integrity"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_author_projection_tamper_breaks_snapshot_integrity(self):
        snapshot, _receipt = confirmed_reply_fixture()
        snapshot["discussions"][0]["notes"][-1][
            "author_id_hash"
        ] = guard.stable_hash("888")
        with self.assertRaisesRegex(guard.GuardError, "integrity"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_discussion_note_count_tamper_breaks_snapshot_integrity(self):
        snapshot = snapshot_from_value([discussion()])
        snapshot["discussions"][0]["note_count"] = 2
        with self.assertRaisesRegex(guard.GuardError, "integrity"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_note_edit_resolution_and_position_drift_are_distinct(self):
        before = snapshot_from_value([discussion()])
        changed_note = note(
            11,
            body="Please handle the updated edge case.",
            resolved=True,
            updated_at="2026-01-01T11:00:00Z",
            new_line=18,
        )
        after = snapshot_from_value([discussion(notes=[changed_note])])
        result = guard.compare_snapshots(before, after)
        change = result["changes"]["changed_discussions"][0]
        note_change = change["changed_notes"][0]
        self.assertTrue(change["resolution_changed"])
        self.assertTrue(note_change["body_changed"])
        self.assertTrue(note_change["state_changed"])
        self.assertTrue(note_change["position_changed"])

    def test_compare_reports_pagination_evidence_change(self):
        before = snapshot_from_value([discussion()])
        after = snapshot_from_value(
            {"complete": True, "items": [discussion()]}, assume=False
        )
        result = guard.compare_snapshots(before, after)
        self.assertFalse(result["ok"])
        self.assertIn(
            "pagination_evidence_changed", result["mutation_blockers"]
        )
        self.assertTrue(result["changes"]["pagination"]["changed"])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot_from_value([discussion()])

    def test_raw_pipeline_array_is_incomplete_without_declaration(self):
        collection = pipeline_collection(assume=False)
        result = guard.verify_exact_head(
            self.snapshot,
            HEAD_A,
            local_head=HEAD_A,
            source_ref_head=HEAD_A,
            pipeline_collection=collection,
        )
        self.assertFalse(result["ok"])
        self.assertIn("pipeline_collection_incomplete", result["blockers"])

    def test_partial_green_pipeline_page_cannot_prove_success(self):
        value = {
            "page": 1,
            "next_page": 2,
            "items": [{"id": 701, "sha": HEAD_A, "status": "success"}],
        }
        collection = guard.parse_pipelines_text(json.dumps(value))
        result = guard.verify_exact_head(
            self.snapshot,
            HEAD_A,
            local_head=HEAD_A,
            source_ref_head=HEAD_A,
            pipeline_collection=collection,
        )
        self.assertFalse(result["ok"])
        self.assertIn("pipeline_collection_incomplete", result["blockers"])

    def test_conflicting_layered_pipeline_pagination_is_rejected(self):
        value = {
            "page": 1,
            "next_page": "",
            "pagination": {"next_page": 2},
            "items": [{"id": 701, "sha": HEAD_A, "status": "success"}],
        }
        with self.assertRaisesRegex(guard.GuardError, "conflicting"):
            guard.parse_pipelines_text(json.dumps(value))

    def test_single_complete_pipeline_envelope_proves_collection(self):
        collection = guard.parse_pipelines_text(
            json.dumps(
                {
                    "complete": True,
                    "pipelines": [
                        {"id": 701, "sha": HEAD_A, "status": "success"}
                    ],
                }
            )
        )
        result = guard.verify_exact_head(
            self.snapshot,
            HEAD_A,
            local_head=HEAD_A,
            source_ref_head=HEAD_A,
            pipeline_collection=collection,
        )
        self.assertTrue(result["ok"])

    def test_single_pipeline_wrapper_rejects_conflicting_pagination(self):
        with self.assertRaisesRegex(guard.GuardError, "pagination metadata"):
            guard.parse_pipelines_text(
                json.dumps(
                    {
                        "complete": True,
                        "next_page": 2,
                        "pipeline": {
                            "id": 701,
                            "sha": HEAD_A,
                            "status": "success",
                        },
                    }
                )
            )

    def test_complete_exact_head_pipeline_proves_head(self):
        result = exact_head_proof(self.snapshot)
        self.assertTrue(result["ok"])
        self.assertTrue(result["pipeline_proof"]["collection_complete"])
        self.assertTrue(result["pipeline_proof"]["proven"])

    def test_conflicting_pipeline_aliases_are_rejected(self):
        snapshot = snapshot_from_value([discussion()])
        pipelines = pipeline_collection(
            [
                {
                    "id": 701,
                    "pipeline_id": 702,
                    "sha": HEAD_A,
                    "head_sha": HEAD_B,
                    "status": "success",
                }
            ]
        )
        with self.assertRaisesRegex(guard.GuardError, "aliases conflict"):
            guard.verify_exact_head(
                snapshot,
                HEAD_A,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipelines,
            )

    def test_pipeline_wrapper_cannot_mix_direct_fields(self):
        mixed = {
            "pipeline": {
                "id": 701,
                "sha": HEAD_A,
                "status": "success",
            },
            "id": 702,
            "sha": HEAD_B,
            "status": "success",
        }
        with self.assertRaisesRegex(guard.GuardError, "must not mix"):
            guard.parse_pipelines_text(json.dumps(mixed))

    def test_pipeline_shapes_cannot_mix_collection_fields(self):
        direct = {
            "id": 701,
            "sha": HEAD_A,
            "status": "success",
            "pipelines": [
                {"id": 702, "sha": HEAD_B, "status": "failed"}
            ],
        }
        wrapper = {
            "complete": True,
            "pipeline": {
                "id": 701,
                "sha": HEAD_A,
                "status": "success",
            },
            "pipelines": [
                {"id": 701, "sha": HEAD_A, "status": "failed"}
            ],
        }
        pages = {
            "complete": True,
            "pipelines": [
                {"id": 701, "sha": HEAD_A, "status": "failed"}
            ],
            "pages": [
                {
                    "page": 1,
                    "next_page": "",
                    "pipelines": [
                        {"id": 701, "sha": HEAD_A, "status": "success"}
                    ],
                }
            ],
        }
        for value in (direct, wrapper, pages):
            with self.subTest(keys=sorted(value)):
                with self.assertRaises(guard.GuardError):
                    guard.parse_pipelines_text(
                        json.dumps(value), assume_complete_array=True
                    )

    def test_numeric_pipeline_ids_are_canonicalized_before_duplicates(self):
        result = guard.verify_exact_head(
            self.snapshot,
            HEAD_A,
            local_head=HEAD_A,
            source_ref_head=HEAD_A,
            pipeline_collection=pipeline_collection(
                [
                    {"id": 701, "sha": HEAD_A, "status": "success"},
                    {"id": "0701", "sha": HEAD_A, "status": "success"},
                ]
            ),
        )
        self.assertFalse(result["ok"])
        self.assertIn("duplicate_pipeline_id", result["blockers"])

    def test_missing_local_or_source_head_never_passes(self):
        result = guard.verify_exact_head(
            self.snapshot,
            HEAD_A,
            local_head=None,
            source_ref_head=None,
            pipeline_collection=pipeline_collection(),
        )
        self.assertFalse(result["ok"])
        self.assertIn("local_head_mismatch", result["blockers"])
        self.assertIn("source_ref_head_mismatch", result["blockers"])

    def test_41_character_sha_is_malformed(self):
        with self.assertRaisesRegex(guard.GuardError, "40 or 64"):
            guard.verify_exact_head(
                self.snapshot,
                "a" * 41,
                local_head=HEAD_A,
                source_ref_head=HEAD_A,
                pipeline_collection=pipeline_collection(),
            )

    def test_mr_head_pipeline_id_must_be_present(self):
        result = guard.verify_exact_head(
            self.snapshot,
            HEAD_A,
            local_head=HEAD_A,
            source_ref_head=HEAD_A,
            pipeline_collection=pipeline_collection(
                [{"id": 702, "sha": HEAD_A, "status": "success"}]
            ),
        )
        self.assertFalse(result["ok"])
        self.assertIn("mr_head_pipeline_missing_from_proof", result["blockers"])

    def test_historical_same_head_failure_does_not_override_current_success(self):
        result = guard.verify_exact_head(
            self.snapshot,
            HEAD_A,
            local_head=HEAD_A,
            source_ref_head=HEAD_A,
            pipeline_collection=pipeline_collection(
                [
                    {"id": 701, "sha": HEAD_A, "status": "success"},
                    {"id": 702, "sha": HEAD_A, "status": "failed"},
                ]
            ),
        )
        self.assertTrue(result["ok"])

    def test_current_mr_head_pipeline_must_succeed(self):
        result = guard.verify_exact_head(
            self.snapshot,
            HEAD_A,
            local_head=HEAD_A,
            source_ref_head=HEAD_A,
            pipeline_collection=pipeline_collection(
                [
                    {"id": 701, "sha": HEAD_A, "status": "running"},
                    {"id": 702, "sha": HEAD_A, "status": "success"},
                ]
            ),
        )
        self.assertFalse(result["ok"])
        self.assertIn(
            "exact_head_pipeline_not_success:701:running", result["blockers"]
        )


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot_from_value([discussion()])

    def test_valid_reply_plan_is_mutation_ready(self):
        result = validate_plan(self.snapshot, valid_reply_plan(self.snapshot))
        self.assertTrue(result["ok"])
        self.assertTrue(result["mutation_ready"])

    def test_no_change_reply_requires_and_accepts_evidence_hash(self):
        plan = valid_reply_plan(self.snapshot, no_change=True)
        result = validate_plan(self.snapshot, plan)
        self.assertTrue(result["ok"])
        del plan["actions"][0]["no_change_evidence_hash"]
        plan["actions"][0]["dedupe_key"] = guard.make_dedupe_key(
            plan["actions"][0], plan["expected"]
        )
        blocked = validate_plan(self.snapshot, plan)
        self.assertFalse(blocked["ok"])
        self.assertIn(
            "action_reply-d-1:no_change_evidence_hash_invalid", blocked["errors"]
        )

    def test_reply_write_requires_exact_head_proof(self):
        plan = valid_reply_plan(self.snapshot)
        result = guard.validate_action_plan(self.snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn("exact_head_proof_missing", result["errors"])

    def test_self_asserted_pipeline_proof_without_collection_evidence_fails(self):
        plan = valid_reply_plan(self.snapshot)
        proof = exact_head_proof(self.snapshot)
        proof["pipeline_proof"]["completion_basis"] = []
        proof["pipeline_proof"]["collection_digest"] = "f" * 64
        result = guard.validate_action_plan(
            self.snapshot, plan, exact_head_proof=proof
        )
        self.assertFalse(result["ok"])
        self.assertIn(
            "exact_head_proof_pipeline_completion_basis_invalid",
            result["errors"],
        )
        self.assertIn(
            "exact_head_proof_pipeline_collection_digest_mismatch",
            result["errors"],
        )

    def test_writer_and_expected_identity_are_bound(self):
        plan = valid_reply_plan(self.snapshot)
        plan["writer"]["id"] = "778"
        plan["expected"]["project_id"] = "99"
        result = validate_plan(self.snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn("writer_does_not_match_snapshot_actor", result["errors"])
        self.assertIn("expected_project_id_mismatch", result["errors"])

    def test_missing_schema_and_unknown_fields_are_rejected(self):
        plan = valid_reply_plan(self.snapshot)
        del plan["schema"]
        plan["surprise"] = True
        result = validate_plan(self.snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn("plan_missing_schema", result["errors"])
        self.assertIn("plan_unknown_surprise", result["errors"])
        self.assertIn("unsupported_plan_schema", result["errors"])

    def test_duplicate_addressed_note_ids_cannot_bypass_dedupe(self):
        plan = valid_reply_plan(self.snapshot)
        action = plan["actions"][0]
        action["addressed_note_ids"] = ["11", "11"]
        action["dedupe_key"] = guard.make_dedupe_key(action, plan["expected"])
        result = validate_plan(self.snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_reply-d-1:addressed_note_ids_duplicate", result["errors"]
        )

    def test_fix_commit_must_be_expected_head_or_evidenced_no_change(self):
        plan = valid_reply_plan(self.snapshot)
        action = plan["actions"][0]
        action["fix_commit"] = HEAD_B
        action["dedupe_key"] = guard.make_dedupe_key(action, plan["expected"])
        result = validate_plan(self.snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_reply-d-1:fix_commit_not_expected_head", result["errors"]
        )

    def test_dedupe_key_binds_project_head_and_thread(self):
        plan = valid_reply_plan(self.snapshot)
        original_key = plan["actions"][0]["dedupe_key"]
        changed = dict(plan["expected"])
        changed["project_id"] = "99"
        self.assertNotEqual(
            original_key, guard.make_dedupe_key(plan["actions"][0], changed)
        )

    def test_lost_or_ambiguous_receipt_never_allows_retry(self):
        plan = valid_reply_plan(self.snapshot)
        action = plan["actions"][0]
        action["operation"] = "retry"
        action["receipt"] = {"status": "lost"}
        result = validate_plan(self.snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn("action_reply-d-1:invalid_reply_operation", result["errors"])

    def test_repeat_after_success_finds_stable_existing_response(self):
        snapshot, receipt = confirmed_reply_fixture()
        plan = valid_reply_plan(snapshot)
        self.assertEqual(
            plan["actions"][0]["dedupe_key"], receipt["response_key"]
        )
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_reply-d-1:response_already_exists", result["errors"]
        )
        self.assertIn(
            "action_reply-d-1:dedupe_status_snapshot_mismatch",
            result["errors"],
        )
        self.assertIn(
            "action_reply-d-1:dedupe_matches_snapshot_mismatch",
            result["errors"],
        )

    def test_foreign_writer_marker_blocks_duplicate_post(self):
        before = snapshot_from_value([discussion()])
        reply_plan = valid_reply_plan(before)
        action = reply_plan["actions"][0]
        posted_body = (
            RESPONSE_TEXT
            + "\n\n<!-- gitlab-review-response:v2:"
            + action["dedupe_key"]
            + " -->"
        )
        foreign_reply = note(
            9001,
            body=posted_body,
            author_id=888,
            updated_at="2026-01-01T12:00:00Z",
            new_line=14,
        )
        snapshot = snapshot_from_value(
            [discussion(notes=[note(11), foreign_reply])]
        )
        plan = valid_reply_plan(snapshot)
        self.assertEqual(
            plan["actions"][0]["dedupe_key"], action["dedupe_key"]
        )
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_reply-d-1:response_receipt_ambiguous",
            result["errors"],
        )

    def test_valid_resolve_requires_current_confirmed_reply(self):
        snapshot, receipt = confirmed_reply_fixture()
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertTrue(result["ok"])
        self.assertTrue(result["mutation_ready"])

    def test_resolve_rejects_self_asserted_or_missing_reply_receipt(self):
        snapshot, receipt = confirmed_reply_fixture()
        plan = valid_resolve_plan(snapshot, receipt)
        plan["actions"][0]["reply_receipt"]["note_id"] = "9999"
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_note_not_in_current_discussion",
            result["errors"],
        )

    def test_resolve_requires_authorization_evidence(self):
        snapshot, receipt = confirmed_reply_fixture()
        plan = valid_resolve_plan(snapshot, receipt)
        plan["actions"][0]["authorization"]["evidence_hash"] = ""
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:authorization_evidence_hash_invalid",
            result["errors"],
        )

    def test_resolve_requires_unique_marker_bound_to_reply_context(self):
        snapshot, receipt = confirmed_reply_fixture()
        plan = valid_resolve_plan(snapshot, receipt)
        plan["actions"][0]["reply_receipt"]["response_key"] = "f" * 64
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_response_key_context_mismatch",
            result["errors"],
        )
        self.assertIn(
            "action_resolve-d-1:reply_receipt_response_key_marker_not_unique",
            result["errors"],
        )

    def test_resolve_binds_semantic_hash_to_pre_marker_body(self):
        snapshot, receipt = confirmed_reply_fixture(
            response_hash="f" * 64
        )
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_response_hash_body_mismatch",
            result["errors"],
        )

    def test_resolve_rejects_duplicate_matching_reply_receipts(self):
        snapshot, receipt = confirmed_reply_fixture(duplicate_reply=True)
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_response_key_discussion_not_unique",
            result["errors"],
        )
        self.assertIn(
            "action_resolve-d-1:reply_receipt_response_receipt_note_mismatch",
            result["errors"],
        )

    def test_system_note_cannot_satisfy_reply_receipt(self):
        snapshot, receipt = confirmed_reply_fixture(system_reply=True)
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_note_must_be_non_system",
            result["errors"],
        )
        self.assertIn(
            "action_resolve-d-1:reply_receipt_response_receipt_note_mismatch",
            result["errors"],
        )

    def test_resolve_rejects_reply_note_as_addressed_prewrite_note(self):
        snapshot, receipt = confirmed_reply_fixture()
        receipt["addressed_note_ids"] = [receipt["note_id"]]
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_receipt_note_cannot_be_addressed",
            result["errors"],
        )
        self.assertIn(
            "action_resolve-d-1:reply_receipt_addressed_note_not_prewrite",
            result["errors"],
        )

    def test_resolve_rejects_new_note_after_reply(self):
        snapshot, receipt = confirmed_reply_fixture(
            extra_reviewer_note=True
        )
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_discussion_notes_changed_since_reply",
            result["errors"],
        )

    def test_resolve_rejects_edit_to_any_prewrite_note(self):
        snapshot, receipt = confirmed_reply_fixture(
            include_unaddressed_prewrite_note=True,
            edit_unaddressed_after_reply=True,
        )
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_discussion_notes_changed_since_reply",
            result["errors"],
        )

    def test_resolve_rejects_discussion_state_drift_after_reply(self):
        before = snapshot_from_value([discussion(individual_note=False)])
        reply_plan = valid_reply_plan(before)
        reply_action = reply_plan["actions"][0]
        posted_body = (
            RESPONSE_TEXT
            + "\n\n<!-- gitlab-review-response:v2:"
            + reply_action["dedupe_key"]
            + " -->"
        )
        original = note(11)
        reply = note(
            9001,
            body=posted_body,
            author_id=int(ACTOR_ID),
            updated_at="2026-01-01T12:00:00Z",
            new_line=14,
        )
        snapshot = snapshot_from_value(
            [discussion(notes=[original, reply], individual_note=True)]
        )
        reply_snapshot = next(
            item
            for item in snapshot["discussions"][0]["notes"]
            if item["id"] == "9001"
        )
        receipt = {
            "status": "confirmed",
            "note_id": "9001",
            "response_hash": reply_action["response_hash"],
            "posted_body_hash": reply_action["posted_body_hash"],
            "response_key": reply_action["dedupe_key"],
            "delivery_head": reply_action["delivery_head"],
            "fix_commit": reply_action["fix_commit"],
            "addressed_note_ids": reply_action["addressed_note_ids"],
            "author_id_hash": snapshot["binding"]["actor_id_hash"],
            "note_fingerprint": reply_snapshot["fingerprint"],
            "readback_epoch_digest": snapshot["epoch_digest"],
            "reply_epoch_digest": before["epoch_digest"],
            "reply_review_context_digest": before[
                "review_context_digest"
            ],
            "reply_discussion_digest": before["discussions"][0]["digest"],
            "prewrite_discussion": {
                "id": before["discussions"][0]["id"],
                "resolution_hash": before["discussions"][0][
                    "resolution_hash"
                ],
                "state_hash": before["discussions"][0]["state_hash"],
                "notes": [
                    {
                        "id": item["id"],
                        "fingerprint": item["fingerprint"],
                    }
                    for item in before["discussions"][0]["notes"]
                ],
            },
        }
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_discussion_state_changed_since_reply",
            result["errors"],
        )

    def test_resolve_rejects_review_context_drift_after_reply(self):
        _snapshot, receipt = confirmed_reply_fixture()
        posted_body = (
            RESPONSE_TEXT
            + "\n\n<!-- gitlab-review-response:v2:"
            + receipt["response_key"]
            + " -->"
        )
        drifted = snapshot_from_value(
            [
                discussion(
                    notes=[
                        note(11),
                        note(
                            9001,
                            body=posted_body,
                            author_id=int(ACTOR_ID),
                            updated_at="2026-01-01T12:00:00Z",
                            new_line=14,
                        ),
                    ]
                )
            ],
            target_ref=HEAD_B,
        )
        reply_snapshot = next(
            item
            for item in drifted["discussions"][0]["notes"]
            if item["id"] == "9001"
        )
        receipt["readback_epoch_digest"] = drifted["epoch_digest"]
        receipt["note_fingerprint"] = reply_snapshot["fingerprint"]
        plan = valid_resolve_plan(drifted, receipt)
        result = validate_plan(drifted, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:reply_receipt_review_context_changed_since_reply",
            result["errors"],
        )

    def test_reviewer_evidence_alone_does_not_authorize_resolution(self):
        snapshot, receipt = confirmed_reply_fixture()
        plan = valid_resolve_plan(snapshot, receipt)
        plan["actions"][0]["authorization"]["source"] = "reviewer"
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:authorization_source_invalid",
            result["errors"],
        )

    def test_resolve_rejects_noop_and_malformed_string_ids(self):
        snapshot, receipt = confirmed_reply_fixture()
        plan = valid_resolve_plan(snapshot, receipt)
        action = plan["actions"][0]
        action["operation"] = "noop"
        action["id"] = ""
        action["authorization"]["evidence_id"] = {"bad": "shape"}
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_index-0:invalid_resolve_operation", result["errors"]
        )
        self.assertIn(
            "action_index-0:action_id_missing_or_invalid", result["errors"]
        )
        self.assertIn(
            "action_index-0:authorization_evidence_id_missing",
            result["errors"],
        )

    def test_non_resolvable_discussion_cannot_be_resolved(self):
        snapshot, receipt = confirmed_reply_fixture(resolvable=False)
        plan = valid_resolve_plan(snapshot, receipt)
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn(
            "action_resolve-d-1:discussion_has_no_unresolved_resolvable_note",
            result["errors"],
        )

    def test_multiple_actions_and_reply_resolve_combination_fail_closed(self):
        snapshot, receipt = confirmed_reply_fixture()
        plan = valid_resolve_plan(snapshot, receipt)
        reply_plan = valid_reply_plan(snapshot)
        plan["actions"].append(reply_plan["actions"][0])
        result = validate_plan(snapshot, plan)
        self.assertFalse(result["ok"])
        self.assertIn("exactly_one_action_required", result["errors"])
        self.assertIn("reply_and_resolve_writes_must_be_separate", result["errors"])


class CliTests(unittest.TestCase):
    @staticmethod
    def write_snapshot_inputs(root):
        mr_path = root / "mr.json"
        discussions_path = root / "discussions.json"
        diff_path = root / "diff.json"
        mr_path.write_text(json.dumps(merge_request()), encoding="utf-8")
        discussions_path.write_text(
            json.dumps([discussion()]), encoding="utf-8"
        )
        diff_path.write_text(json.dumps(diff_version()), encoding="utf-8")
        return mr_path, discussions_path, diff_path

    def test_malformed_invocation_returns_json_error_and_exit_one(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = guard.main(["snapshot", "--mr", "only-one-argument.json"])
        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["schema"], guard.ERROR_SCHEMA)
        self.assertFalse(payload["ok"])

    def test_non_object_snapshot_returns_json_error_and_exit_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before_path = root / "before.json"
            after_path = root / "after.json"
            before_path.write_text("[]", encoding="utf-8")
            after_path.write_text("[]", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                stderr
            ):
                code = guard.main(
                    [
                        "compare",
                        "--before",
                        str(before_path),
                        "--after",
                        str(after_path),
                    ]
                )
            self.assertEqual(code, 1)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(stderr.getvalue())
            self.assertEqual(payload["schema"], guard.ERROR_SCHEMA)
            self.assertIn("snapshot JSON must be an object", payload["error"])

    def test_well_formed_gate_failure_returns_exit_two(self):
        before = snapshot_from_value([discussion()])
        after = snapshot_from_value([discussion()], target_ref=HEAD_B)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before_path = root / "before.json"
            after_path = root / "after.json"
            before_path.write_text(json.dumps(before), encoding="utf-8")
            after_path.write_text(json.dumps(after), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                code = guard.main(
                    [
                        "compare",
                        "--before",
                        str(before_path),
                        "--after",
                        str(after_path),
                    ]
                )
        self.assertEqual(code, 2)

    def test_snapshot_cli_requires_explicit_binding_and_completeness(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mr_path, discussions_path, diff_path = self.write_snapshot_inputs(
                root
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = guard.main(
                    [
                        "snapshot",
                        "--mr",
                        str(mr_path),
                        "--discussions",
                        str(discussions_path),
                        "--diff-version",
                        str(diff_path),
                        "--host",
                        HOST,
                        "--actor-id",
                        ACTOR_ID,
                        "--source-ref-head",
                        HEAD_A,
                        "--target-ref-head",
                        TARGET,
                        "--assume-complete-discussion-array",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["mutation_safe"])

    def test_unsafe_snapshot_cli_returns_exit_two(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mr_path, discussions_path, diff_path = self.write_snapshot_inputs(
                root
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = guard.main(
                    [
                        "snapshot",
                        "--mr",
                        str(mr_path),
                        "--discussions",
                        str(discussions_path),
                        "--diff-version",
                        str(diff_path),
                        "--host",
                        HOST,
                        "--actor-id",
                        ACTOR_ID,
                        "--source-ref-head",
                        HEAD_A,
                        "--target-ref-head",
                        TARGET,
                    ]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 2)
            self.assertFalse(payload["mutation_safe"])

    def test_malformed_bracket_host_returns_json_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mr_path, discussions_path, diff_path = self.write_snapshot_inputs(
                root
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                stderr
            ):
                code = guard.main(
                    [
                        "snapshot",
                        "--mr",
                        str(mr_path),
                        "--discussions",
                        str(discussions_path),
                        "--diff-version",
                        str(diff_path),
                        "--host",
                        "http://[malformed",
                        "--actor-id",
                        ACTOR_ID,
                        "--source-ref-head",
                        HEAD_A,
                        "--target-ref-head",
                        TARGET,
                        "--assume-complete-discussion-array",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(stderr.getvalue())
            self.assertEqual(payload["schema"], guard.ERROR_SCHEMA)
            self.assertIn("malformed", payload["error"])

    def test_hash_body_file_normalizes_newlines_without_echoing_body(self):
        with tempfile.TemporaryDirectory() as directory:
            body_path = Path(directory) / "response.txt"
            raw_body = "Sensitive response\r\nsecond line\r"
            body_path.write_text(raw_body, encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = guard.main(
                    ["hash-body", "--body-file", str(body_path)]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(
                payload["body_hash"],
                guard.stable_hash("Sensitive response\nsecond line\n"),
            )
            self.assertNotIn("Sensitive response", stdout.getvalue())

    def test_dedupe_key_cli_matches_reply_plan(self):
        snapshot = snapshot_from_value([discussion()])
        plan = valid_reply_plan(snapshot)
        expected_key = plan["actions"][0].pop("dedupe_key")
        plan["actions"][0].pop("posted_body_hash")
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = guard.main(["dedupe-key", "--plan", str(plan_path)])
            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["response_key"], expected_key)
            self.assertEqual(
                payload["marker"],
                "<!-- gitlab-review-response:v2:" + expected_key + " -->",
            )

    def test_dedupe_key_cli_rejects_malformed_plan_subset(self):
        malformed_plan = {
            "expected": {},
            "actions": [{"type": "reply"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(malformed_plan), encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                stderr
            ):
                code = guard.main(["dedupe-key", "--plan", str(plan_path)])
            self.assertEqual(code, 1)
            self.assertEqual(stdout.getvalue(), "")
            payload = json.loads(stderr.getvalue())
            self.assertEqual(payload["schema"], guard.ERROR_SCHEMA)
            self.assertFalse(payload["ok"])
            self.assertIn("dedupe-key plan invalid", payload["error"])

    def test_validate_plan_cli_derives_proof_from_separate_evidence(self):
        snapshot = snapshot_from_value([discussion()])
        plan = valid_reply_plan(snapshot)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_path = root / "snapshot.json"
            plan_path = root / "plan.json"
            pipeline_path = root / "pipelines.json"
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            pipeline_path.write_text(
                json.dumps(
                    [{"id": 701, "sha": HEAD_A, "status": "success"}]
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = guard.main(
                    [
                        "validate-plan",
                        "--snapshot",
                        str(snapshot_path),
                        "--plan",
                        str(plan_path),
                        "--expected-head",
                        HEAD_A,
                        "--local-head",
                        HEAD_A,
                        "--source-ref-head",
                        HEAD_A,
                        "--pipeline",
                        str(pipeline_path),
                        "--assume-complete-pipelines",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertTrue(payload["mutation_ready"])


if __name__ == "__main__":
    unittest.main()
