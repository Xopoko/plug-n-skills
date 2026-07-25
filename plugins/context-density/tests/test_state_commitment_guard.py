import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "context-density"
SCRIPT = SKILL_DIR / "scripts" / "state_commitment_guard.py"
sys.path.insert(0, str(SCRIPT.parent))

import state_commitment_guard as guard  # noqa: E402


def source(ref_id, kind, observed="2026-07-24T10:00:00Z", *, origin_id=None):
    return {
        "id": ref_id,
        "origin_id": origin_id or f"origin.{ref_id}",
        "kind": kind,
        "location": f"evidence/{ref_id}.json",
        "observed_at_utc": observed,
    }


def identity(identity_id, kind, value, ref_id, *, status="current", superseded_by=None):
    return {
        "id": identity_id,
        "kind": kind,
        "value": value,
        "status": status,
        "source_ref_ids": [ref_id],
        "superseded_by": superseded_by,
    }


def valid_bundle():
    refs = [
        source("ref.identity.old", "identity"),
        source("ref.identity.task", "identity"),
        source("ref.identity.revision", "identity"),
        source("ref.review.one", "review"),
        source("ref.proof.one", "executable_proof"),
        source("ref.authority.one", "authority"),
        source("ref.confidence.one", "confidence"),
        source("ref.stop.one", "stop"),
        source("ref.identity.two", "identity"),
        source("ref.review.two", "review"),
        source("ref.authority.two", "authority"),
        source("ref.confidence.two", "confidence"),
        source("ref.conflict.two", "conflict"),
    ]
    entities = [
        {
            "id": "entity.one",
            "identities": [
                identity(
                    "identity.task.old",
                    "task",
                    "archived-passed-stop",
                    "ref.identity.old",
                    status="superseded",
                    superseded_by="identity.task.current",
                ),
                identity(
                    "identity.task.current",
                    "task",
                    "work-item-7",
                    "ref.identity.task",
                ),
                identity(
                    "identity.revision.current",
                    "revision",
                    "abc123",
                    "ref.identity.revision",
                ),
            ],
            "current_identity_ids": [
                "identity.task.current",
                "identity.revision.current",
            ],
            "source_review": {
                "status": "accepted",
                "identity_ids": [
                    "identity.task.current",
                    "identity.revision.current",
                ],
                "source_ref_ids": ["ref.review.one"],
            },
            "executable_proof": {
                "status": "passed",
                "identity_ids": ["identity.revision.current"],
                "source_ref_ids": ["ref.proof.one"],
                "execution_count": 2,
            },
            "authority": {
                "mode": "scoped_write",
                "actions": ["deploy", "publish"],
                "source_ref_ids": ["ref.authority.one"],
            },
            "confidence": {
                "level": "high",
                "source_ref_ids": ["ref.confidence.one"],
            },
            "conflict": {
                "status": "none",
                "fallback": "none",
                "source_ref_ids": [],
            },
        },
        {
            "id": "entity.two",
            "identities": [
                identity(
                    "identity.service.current",
                    "service",
                    "accepted passed deploy stop",
                    "ref.identity.two",
                ),
            ],
            "current_identity_ids": ["identity.service.current"],
            "source_review": {
                "status": "accepted",
                "identity_ids": ["identity.service.current"],
                "source_ref_ids": ["ref.review.two"],
            },
            "executable_proof": {
                "status": "not_run",
                "identity_ids": [],
                "source_ref_ids": [],
                "execution_count": 0,
            },
            "authority": {
                "mode": "read_only",
                "actions": [],
                "source_ref_ids": ["ref.authority.two"],
            },
            "confidence": {
                "level": "medium",
                "source_ref_ids": ["ref.confidence.two"],
            },
            "conflict": {
                "status": "none",
                "fallback": "none",
                "source_ref_ids": [],
            },
        },
    ]
    return {
        "schema": guard.STATE_SCHEMA,
        "state_version": 3,
        "cutoff_utc": "2026-07-24T10:30:00Z",
        "entities": entities,
        "stop_scopes": [
            {
                "id": "stop.active.one",
                "status": "active",
                "entity_ids": ["entity.one"],
                "actions": ["deploy"],
                "source_ref_ids": ["ref.stop.one"],
            },
            {
                "id": "stop.inactive.two",
                "status": "inactive",
                "entity_ids": [],
                "actions": [],
                "source_ref_ids": [],
            },
        ],
        "source_refs": refs,
        "commitment_digest": "0" * 64,
        "companions": [],
    }


class BundleCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve(strict=True)
        self.input = self.root / "state.json"

    def tearDown(self):
        self.tmp.cleanup()

    def materialize(self, bundle=None, *, names=None):
        bundle = copy.deepcopy(bundle or valid_bundle())
        names = names or ["summary.md", "handoff.md", "recovery.md"]
        bundle["commitment_digest"] = guard.compute_digest(bundle)
        bundle["companions"] = []
        for index, name in enumerate(names):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            content = (
                f"# Companion {index}\n\n"
                f"<!-- cda:state-commitment "
                f"sha256:{bundle['commitment_digest']} -->\n"
            ).encode()
            target.write_bytes(content)
            bundle["companions"].append(
                {
                    "path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
        self.write_bundle(bundle)
        return bundle

    def write_bundle(self, bundle):
        self.input.write_text(
            json.dumps(bundle, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def run_cli(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "validate", "--input", str(self.input)],
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode, completed.stdout, json.loads(completed.stdout)

    def assert_error_code(self, bundle, code, expected_exit=2):
        self.materialize(bundle)
        exit_code, _, payload = self.run_cli()
        self.assertEqual(exit_code, expected_exit, payload)
        if expected_exit == 1:
            self.assertEqual(payload["schema"], guard.ERROR_SCHEMA)
            self.assertEqual(payload["error"]["code"], code)
        else:
            self.assertEqual(payload["schema"], guard.VALIDATION_SCHEMA)
            self.assertIn(code, {item["code"] for item in payload["errors"]})
        return payload

    def assert_error_code_from_disk(self, code, expected_exit=2):
        exit_code, _, payload = self.run_cli()
        self.assertEqual(exit_code, expected_exit, payload)
        if expected_exit == 1:
            self.assertEqual(payload["error"]["code"], code)
        else:
            self.assertIn(code, {item["code"] for item in payload["errors"]})


class ValidBundleTests(BundleCase):
    def test_valid_three_companion_multi_entity_bundle(self):
        bundle = self.materialize()
        exit_code, stdout, payload = self.run_cli()
        self.assertEqual(exit_code, 0, payload)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["commitment_digest"], bundle["commitment_digest"])
        self.assertEqual(len(bundle["companions"]), 3)
        one, two = payload["entities"]
        self.assertEqual(one["effective_actions"], ["publish"])
        self.assertTrue(one["has_effective_authority"])
        self.assertIn("ref.stop.one", one["evidence_ref_ids"])
        self.assertEqual(two["effective_actions"], [])
        self.assertFalse(two["has_effective_authority"])
        self.assertIn("authority:read_only", two["blockers"])
        self.assertNotIn("executable_proof:not_run", two["blockers"])
        self.assertEqual(stdout, stdout.strip() + "\n")

    def test_output_is_byte_deterministic_without_generated_timestamp(self):
        self.materialize()
        first = self.run_cli()
        second = self.run_cli()
        self.assertEqual(first, second)
        self.assertNotIn("generated_at", first[1])

    def test_digest_contract_is_exact_and_unicode_safe(self):
        bundle = valid_bundle()
        bundle["entities"][0]["identities"][1]["value"] = "revision-\u2603"
        expected = hashlib.sha256(
            json.dumps(
                {
                    key: value
                    for key, value in bundle.items()
                    if key not in {"commitment_digest", "companions"}
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(guard.compute_digest(bundle), expected)
        materialized = self.materialize(bundle)
        self.assertEqual(materialized["commitment_digest"], expected)
        self.assertEqual(self.run_cli()[0], 0)

    def test_prose_words_do_not_change_typed_decisions(self):
        bundle = valid_bundle()
        bundle["entities"][0]["identities"][1]["value"] = (
            "rejected failed stop read_only passed accepted"
        )
        self.materialize(bundle)
        payload = self.run_cli()[2]
        self.assertTrue(payload["valid"])
        self.assertTrue(payload["entities"][0]["has_effective_authority"])

    def test_unresolved_conflict_is_valid_but_fail_closed(self):
        bundle = valid_bundle()
        conflict = bundle["entities"][0]["conflict"]
        conflict.update(
            {
                "status": "unresolved",
                "fallback": "ask_user",
                "source_ref_ids": ["ref.conflict.two"],
            }
        )
        self.materialize(bundle)
        exit_code, _, payload = self.run_cli()
        self.assertEqual(exit_code, 0, payload)
        entity = payload["entities"][0]
        self.assertFalse(entity["has_effective_authority"])
        self.assertEqual(entity["effective_actions"], [])
        self.assertIn("conflict:unresolved", entity["blockers"])

    def test_unknown_authority_is_valid_but_fail_closed(self):
        bundle = valid_bundle()
        bundle["entities"][0]["authority"].update(
            {
                "mode": "unknown",
                "actions": [],
            }
        )
        self.materialize(bundle)
        exit_code, _, payload = self.run_cli()
        self.assertEqual(exit_code, 0, payload)
        self.assertEqual(payload["entities"][0]["effective_actions"], [])
        self.assertIn("authority:unknown", payload["entities"][0]["blockers"])

    def test_full_review_and_proof_lifecycle_enums_are_accepted(self):
        for review_status in [
            "in_progress",
            "changes_requested",
            "rejected",
            "unavailable",
        ]:
            bundle = valid_bundle()
            bundle["entities"][0]["source_review"]["status"] = review_status
            self.materialize(bundle)
            self.assertEqual(self.run_cli()[0], 0, review_status)
        for proof_status, count in [("running", 0), ("unavailable", 0)]:
            bundle = valid_bundle()
            proof = bundle["entities"][0]["executable_proof"]
            proof["status"] = proof_status
            proof["execution_count"] = count
            self.materialize(bundle)
            self.assertEqual(self.run_cli()[0], 0, proof_status)

    def test_review_and_proof_observations_do_not_authorize_actions(self):
        bundle = valid_bundle()
        bundle["entities"][0]["source_review"]["status"] = "changes_requested"
        proof = bundle["entities"][0]["executable_proof"]
        proof.update(
            {
                "status": "not_run",
                "identity_ids": [],
                "source_ref_ids": [],
                "execution_count": 0,
            }
        )
        self.materialize(bundle)
        exit_code, _, payload = self.run_cli()
        self.assertEqual(exit_code, 0, payload)
        entity = payload["entities"][0]
        self.assertEqual(entity["effective_actions"], ["publish"])
        self.assertTrue(entity["has_effective_authority"])
        self.assertNotIn("source_review:changes_requested", entity["blockers"])
        self.assertNotIn("executable_proof:not_run", entity["blockers"])


class IdentityAndEvidenceTests(BundleCase):
    def test_multiple_current_identities_of_one_kind_rejected(self):
        bundle = valid_bundle()
        bundle["entities"][0]["identities"].append(
            identity("identity.task.also", "task", "work-item-8", "ref.identity.task")
        )
        bundle["entities"][0]["current_identity_ids"].append("identity.task.also")
        self.assert_error_code(bundle, "multiple_current_identities_per_kind")

    def test_current_identity_list_must_match_statuses(self):
        bundle = valid_bundle()
        bundle["entities"][0]["current_identity_ids"].remove(
            "identity.revision.current"
        )
        self.assert_error_code(bundle, "current_identity_mismatch")

    def test_superseded_identity_must_target_current_same_kind(self):
        bundle = valid_bundle()
        bundle["entities"][0]["identities"][0]["superseded_by"] = (
            "identity.revision.current"
        )
        self.assert_error_code(bundle, "superseded_target_wrong_kind")

    def test_review_and_proof_bind_only_current_identities(self):
        bundle = valid_bundle()
        bundle["entities"][0]["source_review"]["identity_ids"] = ["identity.task.old"]
        self.assert_error_code(bundle, "non_current_identity_ref")

    def test_global_ids_are_unique(self):
        bundle = valid_bundle()
        bundle["source_refs"][0]["id"] = "entity.one"
        self.assert_error_code(bundle, "duplicate_id", expected_exit=1)

    def test_dangling_and_wrong_kind_refs_rejected(self):
        bundle = valid_bundle()
        bundle["entities"][0]["source_review"]["source_ref_ids"] = ["missing"]
        self.assert_error_code(bundle, "dangling_source_ref")
        bundle = valid_bundle()
        bundle["entities"][0]["source_review"]["source_ref_ids"] = ["ref.proof.one"]
        self.assert_error_code(bundle, "wrong_source_ref_kind")

    def test_identity_and_authority_require_kind_correct_evidence(self):
        bundle = valid_bundle()
        bundle["entities"][0]["authority"]["source_ref_ids"] = ["ref.confidence.one"]
        self.assert_error_code(bundle, "wrong_source_ref_kind")
        bundle = valid_bundle()
        bundle["entities"][0]["identities"][1]["source_ref_ids"] = []
        self.assert_error_code(bundle, "empty_array", expected_exit=1)

    def test_dangling_authority_ref_fails_all_derived_decisions_closed(self):
        bundle = valid_bundle()
        bundle["entities"][0]["authority"]["source_ref_ids"] = ["ref.authority.missing"]
        self.materialize(bundle)
        exit_code, _, payload = self.run_cli()
        self.assertEqual(exit_code, 2, payload)
        self.assertIn(
            "dangling_source_ref",
            {item["code"] for item in payload["errors"]},
        )
        for entity in payload["entities"]:
            self.assertFalse(entity["has_effective_authority"])
            self.assertEqual(entity["effective_actions"], [])

    def test_review_and_proof_evidence_are_independent(self):
        bundle = valid_bundle()
        review_ref = next(
            ref for ref in bundle["source_refs"] if ref["id"] == "ref.review.one"
        )
        proof_ref = next(
            ref for ref in bundle["source_refs"] if ref["id"] == "ref.proof.one"
        )
        proof_ref["origin_id"] = "origin.ref.review.one"
        proof_ref["location"] = review_ref["location"]
        self.assert_error_code(bundle, "review_proof_not_independent")

    def test_review_and_proof_independence_is_not_location_based(self):
        bundle = valid_bundle()
        proof_ref = next(
            ref for ref in bundle["source_refs"] if ref["id"] == "ref.proof.one"
        )
        proof_ref["origin_id"] = "origin.ref.review.one"
        proof_ref["location"] = "evidence/derived-proof.json"
        self.assert_error_code(bundle, "review_proof_not_independent")

    def test_one_source_location_cannot_declare_multiple_origins(self):
        bundle = valid_bundle()
        review_ref = next(
            ref for ref in bundle["source_refs"] if ref["id"] == "ref.review.one"
        )
        proof_ref = next(
            ref for ref in bundle["source_refs"] if ref["id"] == "ref.proof.one"
        )
        proof_ref["location"] = review_ref["location"]
        self.assert_error_code(bundle, "source_location_origin_conflict")

    def test_source_origin_id_is_required_and_portable(self):
        for value, code in [
            (None, "invalid_type"),
            ("", "empty_string"),
            ("contains spaces", "invalid_id"),
        ]:
            bundle = valid_bundle()
            if value is None:
                del bundle["source_refs"][0]["origin_id"]
            else:
                bundle["source_refs"][0]["origin_id"] = value
            self.assert_error_code(bundle, code, expected_exit=1)

    def test_source_observation_cannot_exceed_cutoff(self):
        bundle = valid_bundle()
        bundle["source_refs"][0]["observed_at_utc"] = "2026-07-24T10:30:01Z"
        self.assert_error_code(bundle, "source_after_cutoff")

    def test_blank_authority_source_location_cannot_promote_authority(self):
        bundle = valid_bundle()
        authority_ref = next(
            ref for ref in bundle["source_refs"] if ref["id"] == "ref.authority.one"
        )
        authority_ref["location"] = "   "
        payload = self.assert_error_code(
            bundle,
            "blank_source_location",
            expected_exit=1,
        )
        self.assertNotIn("entities", payload)

    def test_cutoff_is_strict_utc(self):
        bundle = valid_bundle()
        bundle["cutoff_utc"] = "2026-07-24T12:30:00+02:00"
        self.assert_error_code(bundle, "invalid_utc_timestamp", expected_exit=1)


class ReviewProofAuthorityStopTests(BundleCase):
    def test_passed_and_failed_proof_require_positive_count(self):
        for status in ["passed", "failed"]:
            bundle = valid_bundle()
            proof = bundle["entities"][0]["executable_proof"]
            proof["status"] = status
            proof["execution_count"] = 0
            self.assert_error_code(bundle, "executed_proof_zero_count")

    def test_passed_proof_requires_evidence_ref(self):
        bundle = valid_bundle()
        bundle["entities"][0]["executable_proof"]["source_ref_ids"] = []
        self.assert_error_code(bundle, "proof_missing_evidence")

    def test_accepted_review_with_not_run_proof_is_valid(self):
        self.materialize()
        exit_code, _, payload = self.run_cli()
        self.assertEqual(exit_code, 0, payload)
        self.assertEqual(
            payload["entities"][1]["blockers"],
            ["authority:read_only"],
        )

    def test_resolved_conflict_requires_no_fallback(self):
        bundle = valid_bundle()
        bundle["entities"][0]["conflict"].update(
            {
                "status": "resolved",
                "fallback": "revalidate",
                "source_ref_ids": ["ref.conflict.two"],
            }
        )
        self.assert_error_code(bundle, "resolved_conflict_has_fallback")

    def test_read_only_cannot_authorize_actions(self):
        bundle = valid_bundle()
        bundle["entities"][1]["authority"]["actions"] = ["publish"]
        self.assert_error_code(bundle, "non_write_authority_has_actions")

    def test_scoped_write_requires_nonempty_actions(self):
        bundle = valid_bundle()
        bundle["entities"][0]["authority"]["actions"] = []
        self.assert_error_code(bundle, "scoped_write_missing_actions")

    def test_active_stop_requires_actions_and_evidence(self):
        bundle = valid_bundle()
        bundle["stop_scopes"][0]["entity_ids"] = []
        self.assert_error_code(bundle, "active_stop_missing_entities")
        bundle = valid_bundle()
        bundle["stop_scopes"][0]["actions"] = []
        self.assert_error_code(bundle, "active_stop_missing_actions")
        bundle = valid_bundle()
        bundle["stop_scopes"][0]["source_ref_ids"] = []
        self.assert_error_code(bundle, "active_stop_missing_evidence")

    def test_inactive_stop_cannot_have_effect(self):
        bundle = valid_bundle()
        bundle["stop_scopes"][1]["actions"] = ["publish"]
        self.assert_error_code(bundle, "inactive_stop_has_effect")


class CompanionTests(BundleCase):
    def test_digest_drift_is_exit_two(self):
        bundle = self.materialize()
        bundle["state_version"] += 1
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("commitment_digest_mismatch")

    def test_companion_hash_drift(self):
        self.materialize()
        (self.root / "summary.md").write_text("changed", encoding="utf-8")
        self.assert_error_code_from_disk("companion_hash_mismatch")

    def test_marker_digest_and_count_drift(self):
        bundle = self.materialize()
        target = self.root / "summary.md"
        wrong = ("<!-- cda:state-commitment sha256:" + "f" * 64 + " -->\n").encode()
        target.write_bytes(wrong)
        bundle["companions"][0]["sha256"] = hashlib.sha256(wrong).hexdigest()
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("companion_marker_mismatch")

        bundle = self.materialize()
        target = self.root / "summary.md"
        doubled = target.read_bytes() + target.read_bytes()
        target.write_bytes(doubled)
        bundle["companions"][0]["sha256"] = hashlib.sha256(doubled).hexdigest()
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("companion_marker_count")

    def test_valid_and_malformed_marker_prefixes_count_as_duplicates(self):
        bundle = self.materialize()
        target = self.root / "summary.md"
        content = target.read_bytes() + b"<!-- cda:state-commitment malformed -->\n"
        target.write_bytes(content)
        bundle["companions"][0]["sha256"] = hashlib.sha256(content).hexdigest()
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("companion_marker_count")

    def test_companion_set_changes_snapshot_digest(self):
        self.materialize()
        first = self.run_cli()[2]["snapshot_digest"]
        self.materialize(names=["summary.md", "handoff.md", "recovery.md", "extra.md"])
        second = self.run_cli()[2]["snapshot_digest"]
        self.assertNotEqual(first, second)

    def test_absolute_parent_and_non_markdown_paths_are_unsafe(self):
        for unsafe in [
            str(self.root / "summary.md"),
            "../summary.md",
            "./summary.md",
            "nested//summary.md",
            "summary.txt",
        ]:
            bundle = self.materialize()
            bundle["companions"][0]["path"] = unsafe
            self.write_bundle(bundle)
            self.assert_error_code_from_disk("unsafe_companion_path", expected_exit=1)

    @unittest.skipIf(os.name == "nt", "hard-link semantics differ on Windows")
    def test_duplicate_inode_targets_are_rejected(self):
        bundle = self.materialize()
        summary = self.root / "summary.md"
        handoff = self.root / "handoff.md"
        handoff.unlink()
        os.link(summary, handoff)
        bundle["companions"][1]["sha256"] = bundle["companions"][0]["sha256"]
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("duplicate_companion_target", expected_exit=1)

    @unittest.skipIf(os.name == "nt", "symlink semantics differ on Windows")
    def test_companion_symlink_is_unsafe(self):
        bundle = self.materialize()
        target = self.root / "summary.md"
        outside = self.root / "outside.md"
        outside.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(outside)
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("unsafe_companion_symlink", expected_exit=1)

    @unittest.skipIf(os.name == "nt", "symlink semantics differ on Windows")
    def test_intermediate_companion_symlink_is_unsafe(self):
        bundle = self.materialize(names=["nested/summary.md"])
        nested = self.root / "nested"
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "summary.md").write_bytes((nested / "summary.md").read_bytes())
        for child in nested.iterdir():
            child.unlink()
        nested.rmdir()
        nested.symlink_to(outside, target_is_directory=True)
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("unsafe_companion_symlink", expected_exit=1)

    @unittest.skipIf(os.name == "nt", "dir_fd traversal is unavailable on Windows")
    def test_intermediate_swap_before_open_is_rejected(self):
        self.materialize(names=["nested/summary.md"])
        nested = self.root / "nested"
        original = self.root / "nested-original"
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "summary.md").write_bytes((nested / "summary.md").read_bytes())
        real_open = os.open
        swapped = False

        def racing_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "nested" and dir_fd is not None and not swapped:
                nested.rename(original)
                nested.symlink_to(outside, target_is_directory=True)
                swapped = True
            if dir_fd is None:
                return real_open(path, flags, mode)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        stdout = io.StringIO()
        with (
            patch.object(guard.os, "open", side_effect=racing_open),
            patch.object(guard, "_safe_relative_io_supported", return_value=True),
            redirect_stdout(stdout),
        ):
            exit_code = guard.main(["validate", "--input", str(self.input)])
        payload = json.loads(stdout.getvalue())
        self.assertTrue(swapped)
        self.assertEqual(exit_code, 1, payload)
        self.assertEqual(payload["error"]["code"], "unsafe_companion_symlink")

    @unittest.skipIf(os.name == "nt", "dir_fd traversal is unavailable on Windows")
    def test_intermediate_swap_after_open_stays_on_pinned_directory(self):
        self.materialize(names=["nested/summary.md"])
        nested = self.root / "nested"
        original = self.root / "nested-original"
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "summary.md").write_text("outside", encoding="utf-8")
        real_open = os.open
        swapped = False

        def racing_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if dir_fd is None:
                return real_open(path, flags, mode)
            descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
            if path == "nested" and not swapped:
                nested.rename(original)
                nested.symlink_to(outside, target_is_directory=True)
                swapped = True
            return descriptor

        stdout = io.StringIO()
        with (
            patch.object(guard.os, "open", side_effect=racing_open),
            patch.object(guard, "_safe_relative_io_supported", return_value=True),
            redirect_stdout(stdout),
        ):
            exit_code = guard.main(["validate", "--input", str(self.input)])
        payload = json.loads(stdout.getvalue())
        self.assertTrue(swapped)
        self.assertEqual(exit_code, 0, payload)
        self.assertTrue(payload["valid"])

    def test_missing_safe_relative_io_primitives_fail_closed(self):
        self.materialize()
        stdout = io.StringIO()
        with (
            patch.object(guard, "_safe_relative_io_supported", return_value=False),
            redirect_stdout(stdout),
        ):
            exit_code = guard.main(["validate", "--input", str(self.input)])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1, payload)
        self.assertEqual(payload["error"]["code"], "safe_traversal_unavailable")


class MalformedInputTests(BundleCase):
    @unittest.skipIf(os.name == "nt", "symlink semantics differ on Windows")
    def test_input_parent_symlink_is_unsafe(self):
        self.materialize(names=["summary.md"])
        actual = self.root / "actual"
        actual.mkdir()
        self.input.rename(actual / "state.json")
        (self.root / "summary.md").rename(actual / "summary.md")
        alias = self.root / "alias"
        alias.symlink_to(actual, target_is_directory=True)
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "validate",
                "--input",
                str(alias / "state.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(completed.returncode, 1, payload)
        self.assertEqual(payload["error"]["code"], "input_unsafe_path")

    @unittest.skipIf(os.name == "nt", "dir_fd traversal is unavailable on Windows")
    def test_input_parent_swap_before_open_is_rejected(self):
        self.materialize(names=["summary.md"])
        parent = self.root / "input-parent"
        parent.mkdir()
        self.input.rename(parent / "state.json")
        (self.root / "summary.md").rename(parent / "summary.md")
        original = self.root / "input-parent-original"
        outside = self.root / "outside-input"
        outside.mkdir()
        (outside / "state.json").write_bytes((parent / "state.json").read_bytes())
        (outside / "summary.md").write_bytes((parent / "summary.md").read_bytes())
        real_open = os.open
        swapped = False

        def racing_open(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal swapped
            if path == "input-parent" and dir_fd is not None and not swapped:
                parent.rename(original)
                parent.symlink_to(outside, target_is_directory=True)
                swapped = True
            if dir_fd is None:
                return real_open(path, flags, mode)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        stdout = io.StringIO()
        with (
            patch.object(guard.os, "open", side_effect=racing_open),
            patch.object(guard, "_safe_relative_io_supported", return_value=True),
            redirect_stdout(stdout),
        ):
            exit_code = guard.main(["validate", "--input", str(parent / "state.json")])
        payload = json.loads(stdout.getvalue())
        self.assertTrue(swapped)
        self.assertEqual(exit_code, 1, payload)
        self.assertEqual(payload["error"]["code"], "input_unsafe_path")

    def test_duplicate_keys_are_exit_one_json_error(self):
        self.input.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
        exit_code, _, payload = self.run_cli()
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["schema"], guard.ERROR_SCHEMA)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error"]["code"], "duplicate_key")

    def test_unknown_fields_are_exit_one(self):
        bundle = valid_bundle()
        bundle["entities"][0]["narrative_status"] = "accepted"
        self.assert_error_code(bundle, "unknown_field", expected_exit=1)

    def test_malformed_json_and_invalid_utf8_are_exit_one(self):
        self.input.write_text("{", encoding="utf-8")
        self.assert_error_code_from_disk("malformed_json", expected_exit=1)
        self.input.write_bytes(b'{"schema":"\xff"}')
        self.assert_error_code_from_disk("invalid_utf8", expected_exit=1)

    def test_lone_surrogate_strings_and_keys_are_exit_one(self):
        self.materialize()
        raw = self.input.read_text(encoding="utf-8")
        self.input.write_text(
            raw.replace("work-item-7", r"\ud800"),
            encoding="utf-8",
        )
        self.assert_error_code_from_disk("invalid_unicode", expected_exit=1)

        self.input.write_text('{"\\ud800":1}', encoding="utf-8")
        self.assert_error_code_from_disk("invalid_unicode", expected_exit=1)

    def test_oversize_input_is_rejected_before_decode(self):
        self.input.write_bytes(b" " * (guard.MAX_INPUT_BYTES + 1))
        self.assert_error_code_from_disk("input_too_large", expected_exit=1)

    def test_oversize_array_and_string_are_rejected(self):
        bundle = valid_bundle()
        bundle["entities"] = [None] * (guard.MAX_ARRAY_ITEMS + 1)
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("array_too_large", expected_exit=1)
        bundle = valid_bundle()
        bundle["entities"][0]["identities"][0]["value"] = "x" * (
            guard.MAX_STRING_CHARS + 1
        )
        self.write_bundle(bundle)
        self.assert_error_code_from_disk("string_too_long", expected_exit=1)

    def test_cli_argument_errors_are_json(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = guard.main(["validate"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(payload["schema"], guard.ERROR_SCHEMA)
        self.assertEqual(payload["error"]["code"], "invalid_arguments")


if __name__ == "__main__":
    unittest.main()
