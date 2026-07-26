from __future__ import annotations

import copy
import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_thread_skill_handoff.py"
REFERENCE = ROOT / "references" / "thread-skill-handoff-contract.md"
SPEC = importlib.util.spec_from_file_location(
    "validate_thread_skill_handoff", SCRIPT
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load thread skill handoff validator")
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


def surface(
    source: dict,
    relation: str,
    *,
    version: str | None = None,
    revision: str | None = None,
    digest: str | None = None,
) -> dict:
    if relation == "absent":
        return {
            "version": "absent",
            "source_repository": "absent",
            "source_revision": "absent",
            "content_digest": "absent",
            "relation_to_source": "absent",
        }
    if relation == "unknown":
        return {
            "version": "unknown",
            "source_repository": "unknown",
            "source_revision": "unknown",
            "content_digest": "unknown",
            "relation_to_source": "unknown",
        }
    return {
        "version": version or source["source_version"],
        "source_repository": source["source_repository"],
        "source_revision": revision or source["source_revision"],
        "content_digest": digest or source["content_digest"],
        "relation_to_source": relation,
    }


def sample_handoff(requested: str = "direct-source-read") -> dict:
    entry_digest = "sha256:" + "1" * 64
    manifest = {
        "schema": "codex.skill_content_manifest.v1",
        "entries": [
            {
                "path": "skills/example/SKILL.md",
                "sha256": entry_digest,
                "size": 123,
            }
        ],
    }
    source = {
        "name": "example-skill",
        "source_repository": "git+https://example.invalid/example/skills",
        "source_version": "1.2.0",
        "source_revision": "a" * 40,
        "source_path": "skills/example/SKILL.md",
        "content_manifest": manifest,
        "content_digest": CONTRACT.content_manifest_digest(manifest),
        "verification_state": "verified",
    }
    older = surface(
        source,
        "older",
        version="1.1.0",
        revision="b" * 40,
        digest="sha256:" + "2" * 64,
    )
    absent = surface(source, "absent")
    basis = {
        "catalog": copy.deepcopy(older),
        "cache": copy.deepcopy(older),
        "runtime": {
            "discovery": "inactive",
            "loaded": copy.deepcopy(absent),
        },
    }
    if requested == "runtime-loaded":
        exact = surface(source, "exact")
        basis = {
            "catalog": copy.deepcopy(exact),
            "cache": copy.deepcopy(exact),
            "runtime": {
                "discovery": "active",
                "loaded": copy.deepcopy(exact),
            },
        }
    handoff = {
        "schema": "codex.thread_skill_handoff.v2",
        "handoff_id": "handoff-001",
        "payload_fingerprint": "sha256:" + "0" * 64,
        "skill": source,
        "why_now": "The next step needs the exact transferred guardrail.",
        "mechanism": "Apply only the version-bound guardrail.",
        "receiver_basis": basis,
        "requested_consumption": requested,
        "activation_authorized": False,
        "scope_effect": "none",
        "authority_effect": "none",
        "ack_required": True,
    }
    handoff["payload_fingerprint"] = CONTRACT.payload_fingerprint(handoff)
    return handoff


def source_observation(source: dict, relation: str = "exact") -> dict:
    return {
        "name": source["name"],
        "source_repository": source["source_repository"],
        "source_version": source["source_version"],
        "source_revision": source["source_revision"],
        "source_path": source["source_path"],
        "content_digest": source["content_digest"],
        "verification_state": "verified",
        "relation_to_source": relation,
    }


def applied_ack(handoff: dict) -> dict:
    requested = handoff["requested_consumption"]
    runtime = requested == "runtime-loaded"
    return {
        "schema": "codex.thread_skill_handoff_ack.v1",
        "handoff_id": handoff["handoff_id"],
        "payload_fingerprint": handoff["payload_fingerprint"],
        "expected_source_content_digest": handoff["skill"]["content_digest"],
        "observed_source": source_observation(handoff["skill"]),
        "receiver_record_fingerprint": handoff["payload_fingerprint"],
        "status": "applied",
        "reason": (
            "exact-runtime-loaded" if runtime else "exact-direct-source-read"
        ),
        "supersession_evidence_ref": None,
        "observed_receiver": copy.deepcopy(handoff["receiver_basis"]),
        "consumption_mode": requested,
        "runtime_used": runtime,
        "install_attempted": False,
        "evidence_refs": ["receiver-local:exact-source-proof"],
    }


class ThreadSkillHandoffValidatorTests(unittest.TestCase):
    def test_documented_sender_and_acknowledgement_examples_validate(self):
        text = REFERENCE.read_text(encoding="utf-8")
        sender_match = re.search(
            r"## Sender Envelope.*?```json\n(.*?)\n```", text, re.DOTALL
        )
        acknowledgement_match = re.search(
            r"## Receiver Acknowledgement.*?```json\n(.*?)\n```",
            text,
            re.DOTALL,
        )
        self.assertIsNotNone(sender_match)
        self.assertIsNotNone(acknowledgement_match)
        handoff = json.loads(sender_match.group(1))
        acknowledgement = json.loads(acknowledgement_match.group(1))
        CONTRACT.validate_handoff(handoff)
        CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_accepts_exact_direct_source_read_without_runtime_claim(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        CONTRACT.validate_handoff(handoff)
        CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_accepts_runtime_loaded_only_with_exact_loaded_identity(self):
        handoff = sample_handoff("runtime-loaded")
        acknowledgement = applied_ack(handoff)
        CONTRACT.validate_handoff(handoff)
        CONTRACT.validate_acknowledgement(handoff, acknowledgement)

        acknowledgement["observed_receiver"]["runtime"]["loaded"] = surface(
            handoff["skill"],
            "older",
            version="1.1.0",
            revision="d" * 40,
            digest="sha256:" + "5" * 64,
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "runtime loaded identity"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_applied_unavailable_or_mode_fallback(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement["consumption_mode"] = "unavailable"
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "requested consumption"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_applied_after_install_attempt(self):
        handoff = sample_handoff("runtime-loaded")
        acknowledgement = applied_ack(handoff)
        acknowledgement["install_attempted"] = True
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "install_attempted"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_observed_digest_mismatch_as_applied(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement["observed_source"]["content_digest"] = (
            "sha256:" + "3" * 64
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "observed source"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_accepts_closed_digest_mismatch_conflict(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "source-mismatch",
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        acknowledgement["observed_source"]["content_digest"] = (
            "sha256:" + "3" * 64
        )
        acknowledgement["observed_source"]["verification_state"] = "unverified"
        acknowledgement["observed_source"]["relation_to_source"] = "mismatch"
        CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_accepts_newer_verified_source_as_stale(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "stale",
                "reason": "newer-source-supersedes",
                "supersession_evidence_ref": (
                    "receiver-local:newer-supersedes-proof"
                ),
                "runtime_used": False,
            }
        )
        acknowledgement["observed_source"].update(
            {
                "source_version": "1.3.0",
                "source_revision": "c" * 40,
                "content_digest": "sha256:" + "4" * 64,
                "relation_to_source": "newer",
            }
        )
        CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_stale_without_newer_verified_source(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "stale",
                "reason": "newer-source-supersedes",
                "supersession_evidence_ref": (
                    "receiver-local:newer-supersedes-proof"
                ),
                "runtime_used": False,
            }
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "newer observed source"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_noncanonical_manifest_or_payload_fingerprint(self):
        handoff = sample_handoff()
        handoff["skill"]["content_manifest"]["entries"].append(
            copy.deepcopy(handoff["skill"]["content_manifest"]["entries"][0])
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "strictly sorted and unique"
        ):
            CONTRACT.validate_handoff(handoff)

        handoff = sample_handoff()
        handoff["payload_fingerprint"] = "sha256:" + "f" * 64
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "payload_fingerprint"
        ):
            CONTRACT.validate_handoff(handoff)

    def test_rejects_activation_authority_inside_handoff(self):
        handoff = sample_handoff()
        handoff["activation_authorized"] = True
        handoff["payload_fingerprint"] = CONTRACT.payload_fingerprint(handoff)
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "must remain false"
        ):
            CONTRACT.validate_handoff(handoff)

    def test_accepts_id_conflict_only_with_different_receiver_record(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "id-conflict",
                "observed_source": None,
                "receiver_record_fingerprint": "sha256:" + "6" * 64,
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        CONTRACT.validate_acknowledgement(handoff, acknowledgement)

        acknowledgement["receiver_record_fingerprint"] = handoff[
            "payload_fingerprint"
        ]
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "different stored fingerprint"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_accepts_reservation_unavailable_without_applying(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "reservation-unavailable",
                "observed_source": None,
                "receiver_record_fingerprint": "none",
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        CONTRACT.validate_acknowledgement(handoff, acknowledgement)

        acknowledgement["observed_source"] = source_observation(
            handoff["skill"]
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError,
            "reservation-unavailable cannot read source",
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_downgrade_labeled_as_newer(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "stale",
                "reason": "newer-source-supersedes",
                "supersession_evidence_ref": (
                    "receiver-local:newer-supersedes-proof"
                ),
                "runtime_used": False,
            }
        )
        acknowledgement["observed_source"].update(
            {
                "source_version": "0.1.0",
                "source_revision": "e" * 40,
                "content_digest": "sha256:" + "7" * 64,
                "relation_to_source": "newer",
            }
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "semantic version"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_source_mismatch_when_identity_is_exact(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "source-mismatch",
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        acknowledgement["observed_source"]["verification_state"] = "unverified"
        acknowledgement["observed_source"]["relation_to_source"] = "mismatch"
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "mismatch label"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_runtime_mismatch_when_loaded_identity_is_exact(self):
        handoff = sample_handoff("runtime-loaded")
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "runtime-mismatch",
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "requires runtime drift"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_runtime_mismatch_requires_concrete_nonexact_runtime_state(self):
        handoff = sample_handoff("runtime-loaded")
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "runtime-mismatch",
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        acknowledgement["observed_receiver"]["runtime"]["loaded"] = surface(
            handoff["skill"],
            "older",
            version="1.1.0",
            revision="f" * 40,
            digest="sha256:" + "8" * 64,
        )
        CONTRACT.validate_acknowledgement(handoff, acknowledgement)

        acknowledgement["observed_receiver"]["runtime"] = {
            "discovery": "unknown",
            "loaded": surface(handoff["skill"], "unknown"),
        }
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError,
            "unknown runtime state",
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_ambiguous_evidence_when_every_identity_is_known(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "ambiguous-evidence",
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError, "requires unknown evidence"
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_rejects_ambiguous_evidence_when_source_is_unavailable(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "ambiguous-evidence",
                "observed_source": None,
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError,
            "must use source-unavailable",
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_id_conflict_cannot_read_source_before_rejecting(self):
        handoff = sample_handoff()
        acknowledgement = applied_ack(handoff)
        acknowledgement.update(
            {
                "status": "conflict",
                "reason": "id-conflict",
                "receiver_record_fingerprint": "sha256:" + "9" * 64,
                "consumption_mode": "unavailable",
                "runtime_used": False,
            }
        )
        with self.assertRaisesRegex(
            CONTRACT.ContractValidationError,
            "id-conflict cannot read source",
        ):
            CONTRACT.validate_acknowledgement(handoff, acknowledgement)

    def test_compares_large_semver_numbers_without_runtime_integer_limits(self):
        huge = ("9" * 5000) + ".0.0"
        self.assertEqual(
            CONTRACT._compare_semver(huge, "1.0.0", "test.version_order"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
