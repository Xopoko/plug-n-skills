from __future__ import annotations

import copy
import hashlib
import hmac
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "codex-thread-supervisor" / "SKILL.md"
REFERENCE = ROOT / "references" / "thread-supervision-contract.md"
HANDOFF_REFERENCE = ROOT / "references" / "thread-skill-handoff-contract.md"
MAX_POLICY_SCALAR_BYTES = 1024


def checkpoint_example(text: str) -> dict:
    match = re.search(r"## Checkpoint.*?```json\n(.*?)\n```", text, re.DOTALL)
    if match is None:
        raise AssertionError("checkpoint JSON example not found")
    return json.loads(match.group(1))


def adoption_verdict_example(text: str) -> dict:
    match = re.search(
        r"Keep pair, lineage, protection, commit, readback, and adoption.*?"
        r"```json\n(.*?)\n```",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("adoption verdict JSON example not found")
    return json.loads(match.group(1))


def protected_policy_application_example(text: str) -> dict:
    match = re.search(
        r"## Protected Policy Application.*?```json\n(.*?)\n```",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("protected policy application JSON example not found")
    return json.loads(match.group(1))


def protected_policy_failure_schedule(text: str) -> dict[str, str]:
    match = re.search(
        r"Evaluate this precedence atomically:\n\n"
        r"\| Condition \| Required result \|\n"
        r"\| --- \| --- \|\n"
        r"(.*?)\n\nThis receipt",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("protected policy failure schedule not found")

    rows = {}
    for line in match.group(1).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            raise AssertionError(f"malformed policy schedule row: {line}")
        condition, result = cells
        rows[condition.lower()] = result.lower()
    return rows


def bounded_policy_scalar(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        return len(value.encode("utf-8")) <= MAX_POLICY_SCALAR_BYTES
    except UnicodeEncodeError:
        return False


def valid_keyed_fingerprint(value: object) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"scheme", "key_ref_fingerprint", "digest"}
        and value["scheme"] == "hmac-sha256"
        and isinstance(value["key_ref_fingerprint"], str)
        and re.fullmatch(
            r"sha256:[0-9a-f]{64}", value["key_ref_fingerprint"]
        )
        is not None
        and isinstance(value["digest"], str)
        and re.fullmatch(r"[0-9a-f]{64}", value["digest"]) is not None
    )


def valid_sha256_fingerprint(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None
    )


def operation_policy_fingerprint(policy: dict) -> str:
    payload = json.dumps(
        policy,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def trusted_keyed_fingerprint() -> dict[str, str]:
    key_ref = hashlib.sha256(b"test-only-authorized-key-ref-v1").hexdigest()
    message = (
        b"codex.protected-policy-field.v1\x00"
        b"opaque-domain-field-ref\x00"
        b"synthetic-normalized-field-value"
    )
    digest = hmac.new(
        b"test-only-authorized-hmac-key-material-v1",
        message,
        hashlib.sha256,
    ).hexdigest()
    return {
        "scheme": "hmac-sha256",
        "key_ref_fingerprint": f"sha256:{key_ref}",
        "digest": digest,
    }


def trusted_policy_evidence() -> dict[str, dict]:
    value_fingerprint = trusted_keyed_fingerprint()
    policy = {
        "destination_ref": "opaque-external-system-ref",
        "subject_ref": "opaque-action-intent-or-object-ref",
        "operation": "create",
        "eligibility_cutoff": "opaque-revision-or-timestamp",
        "mandatory_fields": [
            {
                "field_ref": "opaque-domain-field-ref",
                "expected_value_fingerprint": value_fingerprint,
                "expectation_evidence_ref": (
                    "opaque-keyed-expectation-proof-ref"
                ),
            }
        ],
    }
    policy_fingerprint = operation_policy_fingerprint(policy)
    return {
        "opaque-protected-policy-application-recovery-ref": {
            "schema": "codex.protected_policy_application_recovery.v1",
            "policy_revision_id": "opaque-user-authorized-revision",
            "receiver_thread_id": "opaque-receiver-thread-id",
            "operation_policy_fingerprint": policy_fingerprint,
            "store_schema": "codex.authorized_immutable_intent_store.v1",
            "store_ref": "opaque-authorized-intent-store-ref",
            "store_authorization_ref": (
                "opaque-intent-store-authorization-ref"
            ),
            "intent_ref": "opaque-immutable-prewrite-intent-ref",
            "destination_ref": "opaque-external-system-ref",
            "subject_ref": "opaque-action-intent-or-object-ref",
            "intent_operation_id": (
                "opaque-preallocated-intent-operation-id"
            ),
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
        },
        "opaque-receiver-owned-ack-ref": {
            "schema": "codex.receiver_policy_adoption.v1",
            "receiver_thread_id": "opaque-receiver-thread-id",
            "policy_revision_id": "opaque-user-authorized-revision",
            "from_protected_contract_fingerprint": (
                "prior-protected-fingerprint"
            ),
            "to_protected_contract_fingerprint": (
                "current-protected-fingerprint"
            ),
            "operation_policy_fingerprint": policy_fingerprint,
            "cutoff": "opaque-receiver-adoption-cutoff",
        },
        "opaque-intent-store-authorization-ref": {
            "schema": "codex.intent_store_authorization.v1",
            "store_schema": "codex.authorized_immutable_intent_store.v1",
            "store_ref": "opaque-authorized-intent-store-ref",
            "status": "authorized",
        },
        "opaque-adoption-before-intent-proof-ref": {
            "schema": "codex.ordering_evidence.v1",
            "relation": "after-adoption",
            "before_ref": "opaque-receiver-owned-ack-ref",
            "after_operation_id": "opaque-preallocated-intent-operation-id",
        },
        "opaque-intent-immutability-proof-ref": {
            "schema": "codex.intent_immutability_evidence.v1",
            "store_ref": "opaque-authorized-intent-store-ref",
            "operation_id": "opaque-preallocated-intent-operation-id",
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "intent_ref": "opaque-immutable-prewrite-intent-ref",
            "receiver_thread_id": "opaque-receiver-thread-id",
            "receiver_acknowledgement_ref": (
                "opaque-receiver-owned-ack-ref"
            ),
            "operation_policy_fingerprint": policy_fingerprint,
        },
        "opaque-immutable-prewrite-intent-ref": {
            "schema": "codex.authorized_immutable_intent_store.v1",
            "store_ref": "opaque-authorized-intent-store-ref",
            "store_authorization_ref": (
                "opaque-intent-store-authorization-ref"
            ),
            "operation_id": "opaque-preallocated-intent-operation-id",
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "receiver_thread_id": "opaque-receiver-thread-id",
            "receiver_acknowledgement_ref": (
                "opaque-receiver-owned-ack-ref"
            ),
            "operation_policy_fingerprint": policy_fingerprint,
            "immutability_evidence_ref": (
                "opaque-intent-immutability-proof-ref"
            ),
            "cutoff": "opaque-prewrite-intent-cutoff",
        },
        "opaque-owning-system-write-receipt": {
            "schema": "codex.external_mutation_receipt.v1",
            "operation_id": "opaque-preallocated-mutation-operation-id",
            "destination_ref": "opaque-external-system-ref",
            "subject_ref": "opaque-action-intent-or-object-ref",
            "prewrite_intent_operation_id": (
                "opaque-preallocated-intent-operation-id"
            ),
            "prewrite_intent_ref": "opaque-immutable-prewrite-intent-ref",
            "cutoff": "opaque-mutation-cutoff",
        },
        "opaque-mutation-before-readback-proof-ref": {
            "schema": "codex.ordering_evidence.v1",
            "relation": "after-mutation",
            "before_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "before_receipt_ref": "opaque-owning-system-write-receipt",
            "after_object_ref": "opaque-object-id",
            "cutoff": "opaque-post-mutation-cutoff",
        },
        "opaque-keyed-expectation-proof-ref": {
            "schema": "codex.field_expectation_evidence.v1",
            "operation_policy_fingerprint": policy_fingerprint,
            "field_ref": "opaque-domain-field-ref",
            "value_fingerprint": value_fingerprint,
        },
        "opaque-owning-system-readback-ref": {
            "schema": "codex.field_observation_evidence.v1",
            "object_ref": "opaque-object-id",
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "readback_cutoff": "opaque-post-mutation-cutoff",
            "field_ref": "opaque-domain-field-ref",
            "value_fingerprint": value_fingerprint,
            "status": "matched",
        },
    }


def evaluate_protected_policy_application(receipt: dict) -> str:
    evidence = trusted_policy_evidence()
    try:
        if set(receipt) != {
            "schema",
            "policy_revision_id",
            "authorizer",
            "from_protected_contract_fingerprint",
            "to_protected_contract_fingerprint",
            "receiver_thread_id",
            "operation_policy_fingerprint",
            "recovery_ref",
            "receiver_adoption",
            "operation_policy",
            "prewrite_intent",
            "mutation",
            "readback",
            "application",
        }:
            return "invalid"
        if receipt["schema"] != "codex.protected_policy_application.v1":
            return "invalid"
        if receipt["authorizer"] != "user":
            return "invalid"
        if receipt["application"] not in {
            "invalid",
            "blocked",
            "applied",
            "policy-drift",
            "reconciliation-required",
        }:
            return "invalid"
        for field in (
            "policy_revision_id",
            "from_protected_contract_fingerprint",
            "to_protected_contract_fingerprint",
            "receiver_thread_id",
            "operation_policy_fingerprint",
            "recovery_ref",
        ):
            if not bounded_policy_scalar(receipt[field]):
                return "invalid"
        if not valid_sha256_fingerprint(
            receipt["operation_policy_fingerprint"]
        ):
            return "invalid"

        policy = receipt["operation_policy"]
        if set(policy) != {
            "destination_ref",
            "subject_ref",
            "operation",
            "eligibility_cutoff",
            "mandatory_fields",
        }:
            return "invalid"
        if policy["operation"] not in {
            "create",
            "update",
            "transition",
            "other-authorized",
        }:
            return "invalid"
        for field in ("destination_ref", "subject_ref", "eligibility_cutoff"):
            if not bounded_policy_scalar(policy[field]):
                return "invalid"
        mandatory = policy["mandatory_fields"]
        if not isinstance(mandatory, list) or not mandatory:
            return "invalid"
        expected_by_field = {}
        for item in mandatory:
            if set(item) != {
                "field_ref",
                "expected_value_fingerprint",
                "expectation_evidence_ref",
            }:
                return "invalid"
            field_ref = item["field_ref"]
            expected = item["expected_value_fingerprint"]
            if (
                not bounded_policy_scalar(field_ref)
                or not valid_keyed_fingerprint(expected)
                or not bounded_policy_scalar(item["expectation_evidence_ref"])
                or field_ref in expected_by_field
            ):
                return "invalid"
            expected_by_field[field_ref] = expected
        computed_operation_policy_fingerprint = operation_policy_fingerprint(
            policy
        )
        recovery = evidence.get(receipt["recovery_ref"])
        if (
            not isinstance(recovery, dict)
            or set(recovery)
            != {
                "schema",
                "policy_revision_id",
                "receiver_thread_id",
                "operation_policy_fingerprint",
                "store_schema",
                "store_ref",
                "store_authorization_ref",
                "intent_ref",
                "destination_ref",
                "subject_ref",
                "intent_operation_id",
                "mutation_operation_id",
            }
            or recovery["schema"]
            != "codex.protected_policy_application_recovery.v1"
        ):
            return "invalid"
        for field in (
            "policy_revision_id",
            "receiver_thread_id",
            "operation_policy_fingerprint",
            "store_schema",
            "store_ref",
            "store_authorization_ref",
            "intent_ref",
            "destination_ref",
            "subject_ref",
            "intent_operation_id",
            "mutation_operation_id",
        ):
            if not bounded_policy_scalar(recovery[field]):
                return "invalid"
        if not valid_sha256_fingerprint(
            recovery["operation_policy_fingerprint"]
        ):
            return "invalid"
        if (
            recovery["store_schema"]
            != "codex.authorized_immutable_intent_store.v1"
        ):
            return "invalid"
        expected_recovery_store_authorization = {
            "schema": "codex.intent_store_authorization.v1",
            "store_schema": recovery["store_schema"],
            "store_ref": recovery["store_ref"],
            "status": "authorized",
        }
        if (
            evidence.get(recovery["store_authorization_ref"])
            != expected_recovery_store_authorization
        ):
            return "invalid"

        adoption = receipt["receiver_adoption"]
        if set(adoption) != {
            "status",
            "receiver_thread_id",
            "acknowledgement_ref",
            "policy_revision_id",
            "from_protected_contract_fingerprint",
            "to_protected_contract_fingerprint",
            "operation_policy_fingerprint",
            "cutoff",
        }:
            return "invalid"
        adoption_status = adoption["status"]
        if adoption_status not in {
            "not-proven",
            "adopted",
            "conflict",
            "capability-unavailable",
        }:
            return "invalid"
        for field in (
            "receiver_thread_id",
            "acknowledgement_ref",
            "policy_revision_id",
            "from_protected_contract_fingerprint",
            "to_protected_contract_fingerprint",
            "operation_policy_fingerprint",
            "cutoff",
        ):
            if adoption[field] is not None and not bounded_policy_scalar(
                adoption[field]
            ):
                return "invalid"
        if (
            adoption["operation_policy_fingerprint"] is not None
            and not valid_sha256_fingerprint(
                adoption["operation_policy_fingerprint"]
            )
        ):
            return "invalid"

        mutation = receipt["mutation"]
        if set(mutation) != {
            "state",
            "operation_id",
            "destination_ref",
            "subject_ref",
            "receipt_ref",
            "prewrite_intent_operation_id",
            "prewrite_intent_ref",
            "cutoff",
        }:
            return "invalid"
        mutation_state = mutation["state"]
        if mutation_state not in {
            "not-attempted",
            "committed",
            "outcome-unknown",
        }:
            return "invalid"
        for field in (
            "operation_id",
            "destination_ref",
            "subject_ref",
            "receipt_ref",
            "prewrite_intent_operation_id",
            "prewrite_intent_ref",
            "cutoff",
        ):
            if mutation[field] is not None and not bounded_policy_scalar(
                mutation[field]
            ):
                return "invalid"

        intent = receipt["prewrite_intent"]
        if set(intent) != {
            "status",
            "store_schema",
            "store_ref",
            "store_authorization_ref",
            "operation_id",
            "mutation_operation_id",
            "intent_ref",
            "receiver_thread_id",
            "receiver_acknowledgement_ref",
            "operation_policy_fingerprint",
            "relation",
            "ordering_evidence_ref",
            "immutability_evidence_ref",
            "cutoff",
        }:
            return "invalid"
        intent_status = intent["status"]
        if intent_status not in {
            "not-created",
            "created",
            "capability-unavailable",
            "outcome-unknown",
        }:
            return "invalid"
        for field in (
            "store_schema",
            "store_ref",
            "store_authorization_ref",
            "operation_id",
            "mutation_operation_id",
            "intent_ref",
            "receiver_thread_id",
            "receiver_acknowledgement_ref",
            "operation_policy_fingerprint",
            "relation",
            "ordering_evidence_ref",
            "immutability_evidence_ref",
            "cutoff",
        ):
            if intent[field] is not None and not bounded_policy_scalar(intent[field]):
                return "invalid"
        if (
            intent["operation_policy_fingerprint"] is not None
            and not valid_sha256_fingerprint(
                intent["operation_policy_fingerprint"]
            )
        ):
            return "invalid"

        readback = receipt["readback"]
        if set(readback) != {
            "state",
            "object_ref",
            "cutoff",
            "mutation_operation_id",
            "mutation_receipt_ref",
            "relation",
            "ordering_evidence_ref",
            "field_results",
        }:
            return "invalid"
        if readback["state"] not in {"not-run", "complete", "unavailable"}:
            return "invalid"
        for field in (
            "object_ref",
            "cutoff",
            "mutation_operation_id",
            "mutation_receipt_ref",
            "relation",
            "ordering_evidence_ref",
        ):
            if readback[field] is not None and not bounded_policy_scalar(
                readback[field]
            ):
                return "invalid"
        results = readback["field_results"]
        if not isinstance(results, list):
            return "invalid"
        observed_by_field = {}
        for result in results:
            if set(result) != {
                "field_ref",
                "observed_value_fingerprint",
                "evidence_ref",
                "status",
            }:
                return "invalid"
            field_ref = result["field_ref"]
            if not bounded_policy_scalar(field_ref):
                return "invalid"
            if field_ref in observed_by_field:
                return "invalid"
            if result["status"] not in {
                "matched",
                "mismatched",
                "missing",
                "unavailable",
            }:
                return "invalid"
            for field in ("observed_value_fingerprint", "evidence_ref"):
                if field == "observed_value_fingerprint":
                    if result[field] is not None and not valid_keyed_fingerprint(
                        result[field]
                    ):
                        return "invalid"
                elif result[field] is not None and not bounded_policy_scalar(
                    result[field]
                ):
                    return "invalid"
            observed_by_field[field_ref] = result

        mutation_identity_is_trusted = (
            bounded_policy_scalar(mutation["operation_id"])
            and bounded_policy_scalar(mutation["destination_ref"])
            and bounded_policy_scalar(mutation["subject_ref"])
            and bounded_policy_scalar(
                mutation["prewrite_intent_operation_id"]
            )
            and bounded_policy_scalar(mutation["prewrite_intent_ref"])
            and bounded_policy_scalar(mutation["cutoff"])
            and bounded_policy_scalar(intent["operation_id"])
            and bounded_policy_scalar(intent["mutation_operation_id"])
            and bounded_policy_scalar(intent["intent_ref"])
            and mutation["operation_id"] == intent["mutation_operation_id"]
            and mutation["prewrite_intent_operation_id"]
            == intent["operation_id"]
            and mutation["prewrite_intent_ref"] == intent["intent_ref"]
            and intent["operation_id"] == recovery["intent_operation_id"]
            and intent["mutation_operation_id"]
            == recovery["mutation_operation_id"]
            and intent["intent_ref"] == recovery["intent_ref"]
        )
        expected_mutation_receipt = {
            "schema": "codex.external_mutation_receipt.v1",
            "operation_id": recovery["mutation_operation_id"],
            "destination_ref": recovery["destination_ref"],
            "subject_ref": recovery["subject_ref"],
            "prewrite_intent_operation_id": recovery[
                "intent_operation_id"
            ],
            "prewrite_intent_ref": recovery["intent_ref"],
            "cutoff": mutation["cutoff"],
        }
        mutation_receipt_is_trusted = (
            bounded_policy_scalar(mutation["receipt_ref"])
            and evidence.get(mutation["receipt_ref"])
            == expected_mutation_receipt
            and mutation["operation_id"]
            == expected_mutation_receipt["operation_id"]
            and mutation["destination_ref"]
            == expected_mutation_receipt["destination_ref"]
            and mutation["subject_ref"]
            == expected_mutation_receipt["subject_ref"]
            and mutation["prewrite_intent_operation_id"]
            == expected_mutation_receipt[
                "prewrite_intent_operation_id"
            ]
            and mutation["prewrite_intent_ref"]
            == expected_mutation_receipt["prewrite_intent_ref"]
        )
        mutation_is_cleanly_not_attempted = (
            mutation_state == "not-attempted"
            and all(
                mutation[field] is None
                for field in (
                    "operation_id",
                    "destination_ref",
                    "subject_ref",
                    "receipt_ref",
                    "prewrite_intent_operation_id",
                    "prewrite_intent_ref",
                    "cutoff",
                )
            )
        )
        readback_is_cleanly_not_run = (
            readback["state"] == "not-run"
            and all(
                readback[field] is None
                for field in (
                    "object_ref",
                    "cutoff",
                    "mutation_operation_id",
                    "mutation_receipt_ref",
                    "relation",
                    "ordering_evidence_ref",
                )
            )
            and readback["field_results"] == []
        )
        if intent_status == "outcome-unknown" and not (
            bounded_policy_scalar(intent["store_ref"])
            and bounded_policy_scalar(intent["operation_id"])
            and bounded_policy_scalar(intent["mutation_operation_id"])
            and bounded_policy_scalar(intent["cutoff"])
            and intent["operation_id"] == recovery["intent_operation_id"]
            and intent["mutation_operation_id"]
            == recovery["mutation_operation_id"]
            and intent["store_schema"] == recovery["store_schema"]
            and intent["store_ref"] == recovery["store_ref"]
            and intent["store_authorization_ref"]
            == recovery["store_authorization_ref"]
            and mutation_is_cleanly_not_attempted
            and readback_is_cleanly_not_run
        ):
            return "invalid"
        if intent_status == "outcome-unknown":
            return "reconciliation-required"
        if (
            mutation_state == "outcome-unknown"
            and not mutation_identity_is_trusted
        ):
            return "invalid"
        if mutation_state == "outcome-unknown":
            return "reconciliation-required"
        readback_is_incomplete_or_unavailable = (
            readback["state"] != "complete"
            or any(
                item["status"] == "unavailable"
                for item in observed_by_field.values()
            )
        )
        if (
            mutation_state == "committed"
            and readback_is_incomplete_or_unavailable
        ):
            readback_identity_conflicts = (
                readback["mutation_operation_id"] is not None
                and readback["mutation_operation_id"]
                != mutation["operation_id"]
            ) or (
                readback["mutation_receipt_ref"] is not None
                and readback["mutation_receipt_ref"]
                != mutation["receipt_ref"]
            )
            if (
                not mutation_identity_is_trusted
                or not mutation_receipt_is_trusted
                or not bounded_policy_scalar(mutation["cutoff"])
                or readback_identity_conflicts
            ):
                return "invalid"
            return "reconciliation-required"
        if (
            recovery["policy_revision_id"] != receipt["policy_revision_id"]
            or recovery["receiver_thread_id"]
            != receipt["receiver_thread_id"]
            or recovery["operation_policy_fingerprint"]
            != receipt["operation_policy_fingerprint"]
            or recovery["destination_ref"] != policy["destination_ref"]
            or recovery["subject_ref"] != policy["subject_ref"]
        ):
            return "invalid"
        if (
            receipt["operation_policy_fingerprint"]
            != computed_operation_policy_fingerprint
        ):
            return "invalid"
        if intent_status == "created" and not (
            intent["store_schema"]
            == "codex.authorized_immutable_intent_store.v1"
            and bounded_policy_scalar(intent["store_ref"])
            and bounded_policy_scalar(intent["store_authorization_ref"])
            and bounded_policy_scalar(intent["operation_id"])
            and bounded_policy_scalar(intent["mutation_operation_id"])
            and bounded_policy_scalar(intent["intent_ref"])
            and bounded_policy_scalar(intent["immutability_evidence_ref"])
            and intent["operation_policy_fingerprint"]
            == receipt["operation_policy_fingerprint"]
            and intent["operation_id"] == recovery["intent_operation_id"]
            and intent["mutation_operation_id"]
            == recovery["mutation_operation_id"]
            and intent["store_schema"] == recovery["store_schema"]
            and intent["store_ref"] == recovery["store_ref"]
            and intent["store_authorization_ref"]
            == recovery["store_authorization_ref"]
            and intent["intent_ref"] == recovery["intent_ref"]
        ):
            return "invalid"
        if adoption_status != "adopted":
            return "blocked" if mutation_state == "not-attempted" else "policy-drift"
        if (
            adoption["receiver_thread_id"] != receipt["receiver_thread_id"]
            or adoption["policy_revision_id"] != receipt["policy_revision_id"]
            or adoption["from_protected_contract_fingerprint"]
            != receipt["from_protected_contract_fingerprint"]
            or adoption["to_protected_contract_fingerprint"]
            != receipt["to_protected_contract_fingerprint"]
            or adoption["operation_policy_fingerprint"]
            != receipt["operation_policy_fingerprint"]
            or not bounded_policy_scalar(adoption["acknowledgement_ref"])
            or not bounded_policy_scalar(adoption["cutoff"])
        ):
            return "invalid"
        expected_adoption_evidence = {
            "schema": "codex.receiver_policy_adoption.v1",
            "receiver_thread_id": receipt["receiver_thread_id"],
            "policy_revision_id": receipt["policy_revision_id"],
            "from_protected_contract_fingerprint": receipt[
                "from_protected_contract_fingerprint"
            ],
            "to_protected_contract_fingerprint": receipt[
                "to_protected_contract_fingerprint"
            ],
            "operation_policy_fingerprint": receipt[
                "operation_policy_fingerprint"
            ],
            "cutoff": adoption["cutoff"],
        }
        if (
            evidence.get(adoption["acknowledgement_ref"])
            != expected_adoption_evidence
        ):
            return "invalid"

        if intent_status in {"not-created", "capability-unavailable"}:
            return "blocked" if mutation_state == "not-attempted" else "policy-drift"

        intent_matches = (
            intent["receiver_thread_id"] == receipt["receiver_thread_id"]
            and intent["receiver_acknowledgement_ref"]
            == adoption["acknowledgement_ref"]
            and intent["relation"] == "after-adoption"
            and bounded_policy_scalar(intent["ordering_evidence_ref"])
            and bounded_policy_scalar(intent["cutoff"])
        )
        if not intent_matches:
            return "policy-drift" if mutation_state == "not-attempted" else "invalid"
        expected_store_authorization = {
            "schema": "codex.intent_store_authorization.v1",
            "store_schema": intent["store_schema"],
            "store_ref": intent["store_ref"],
            "status": "authorized",
        }
        expected_intent_ordering = {
            "schema": "codex.ordering_evidence.v1",
            "relation": "after-adoption",
            "before_ref": adoption["acknowledgement_ref"],
            "after_operation_id": intent["operation_id"],
        }
        expected_immutability = {
            "schema": "codex.intent_immutability_evidence.v1",
            "store_ref": intent["store_ref"],
            "operation_id": intent["operation_id"],
            "mutation_operation_id": intent["mutation_operation_id"],
            "intent_ref": intent["intent_ref"],
            "receiver_thread_id": intent["receiver_thread_id"],
            "receiver_acknowledgement_ref": intent[
                "receiver_acknowledgement_ref"
            ],
            "operation_policy_fingerprint": intent[
                "operation_policy_fingerprint"
            ],
        }
        expected_intent_record = {
            "schema": intent["store_schema"],
            "store_ref": intent["store_ref"],
            "store_authorization_ref": intent["store_authorization_ref"],
            "operation_id": intent["operation_id"],
            "mutation_operation_id": intent["mutation_operation_id"],
            "receiver_thread_id": intent["receiver_thread_id"],
            "receiver_acknowledgement_ref": intent[
                "receiver_acknowledgement_ref"
            ],
            "operation_policy_fingerprint": intent[
                "operation_policy_fingerprint"
            ],
            "immutability_evidence_ref": intent[
                "immutability_evidence_ref"
            ],
            "cutoff": intent["cutoff"],
        }
        if (
            evidence.get(intent["store_authorization_ref"])
            != expected_store_authorization
            or evidence.get(intent["ordering_evidence_ref"])
            != expected_intent_ordering
            or evidence.get(intent["immutability_evidence_ref"])
            != expected_immutability
            or evidence.get(intent["intent_ref"]) != expected_intent_record
        ):
            return "invalid"

        if mutation_state == "not-attempted":
            return "blocked"
        if (
            mutation["operation_id"] != intent["mutation_operation_id"]
            or mutation["destination_ref"] != policy["destination_ref"]
            or mutation["subject_ref"] != policy["subject_ref"]
            or mutation["prewrite_intent_operation_id"] != intent["operation_id"]
            or mutation["prewrite_intent_ref"] != intent["intent_ref"]
            or not bounded_policy_scalar(mutation["operation_id"])
        ):
            return "invalid"
        if not mutation["receipt_ref"] or not mutation["cutoff"]:
            return "reconciliation-required"
        if not mutation_receipt_is_trusted:
            return "invalid"

        if not readback["object_ref"] or not readback["cutoff"]:
            return "reconciliation-required"
        if (
            readback["mutation_operation_id"] != mutation["operation_id"]
            or readback["mutation_receipt_ref"] != mutation["receipt_ref"]
        ):
            return "policy-drift"
        if readback["relation"] != "after-mutation":
            return "policy-drift"
        if not readback["ordering_evidence_ref"]:
            return "reconciliation-required"
        expected_readback_ordering = {
            "schema": "codex.ordering_evidence.v1",
            "relation": "after-mutation",
            "before_operation_id": mutation["operation_id"],
            "before_receipt_ref": mutation["receipt_ref"],
            "after_object_ref": readback["object_ref"],
            "cutoff": readback["cutoff"],
        }
        if (
            evidence.get(readback["ordering_evidence_ref"])
            != expected_readback_ordering
        ):
            return "policy-drift"

        if set(observed_by_field) != set(expected_by_field):
            return "policy-drift"
        for field_ref, result in observed_by_field.items():
            policy_item = next(
                item
                for item in mandatory
                if item["field_ref"] == field_ref
            )
            expected_expectation_evidence = {
                "schema": "codex.field_expectation_evidence.v1",
                "operation_policy_fingerprint": receipt[
                    "operation_policy_fingerprint"
                ],
                "field_ref": field_ref,
                "value_fingerprint": expected_by_field[field_ref],
            }
            if (
                evidence.get(policy_item["expectation_evidence_ref"])
                != expected_expectation_evidence
            ):
                return "invalid"
            if result["status"] != "matched":
                return "policy-drift"
            if not bounded_policy_scalar(result["evidence_ref"]):
                return "invalid"
            observed = result["observed_value_fingerprint"]
            if not valid_keyed_fingerprint(observed):
                return "invalid"
            if observed != expected_by_field[field_ref]:
                return "policy-drift"
            expected_observation_evidence = {
                "schema": "codex.field_observation_evidence.v1",
                "object_ref": readback["object_ref"],
                "mutation_operation_id": mutation["operation_id"],
                "readback_cutoff": readback["cutoff"],
                "field_ref": field_ref,
                "value_fingerprint": observed,
                "status": result["status"],
            }
            if (
                evidence.get(result["evidence_ref"])
                != expected_observation_evidence
            ):
                return "invalid"
        return "applied" if receipt["application"] == "applied" else "invalid"
    except (AttributeError, KeyError, TypeError):
        return "invalid"


def adoption_failure_schedule(text: str) -> dict[str, str]:
    match = re.search(
        r"Use this deterministic failure schedule:\n\n"
        r"\| Condition \| Required verdict \|\n"
        r"\| --- \| --- \|\n"
        r"(.*?)\n\nThe pre-CAS intent",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("adoption failure schedule not found")

    rows = {}
    for line in match.group(1).splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            raise AssertionError(f"malformed adoption schedule row: {line}")
        condition, verdict = cells
        rows[condition.lower()] = verdict.lower()
    return rows


def skill_handoff_example(text: str) -> dict:
    match = re.search(
        r"## Sender Envelope.*?```json\n(.*?)\n```",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("skill handoff JSON example not found")
    return json.loads(match.group(1))


def skill_handoff_ack_example(text: str) -> dict:
    match = re.search(
        r"## Receiver Acknowledgement.*?```json\n(.*?)\n```",
        text,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("skill handoff acknowledgement JSON example not found")
    return json.loads(match.group(1))


class ThreadSupervisionContractTests(unittest.TestCase):
    def test_checkpoint_binds_one_supervisor_owned_continuation(self):
        contract = checkpoint_example(REFERENCE.read_text(encoding="utf-8"))
        continuation = contract["continuation_owner"]
        heartbeat = contract["heartbeat"]
        self.assertTrue(contract["supervisor_host_id"])
        self.assertEqual(continuation["kind"], "goal-runtime|heartbeat")
        self.assertEqual(continuation["id"], heartbeat["id"])
        self.assertEqual(continuation["owner_task_id"], contract["supervisor_task_id"])
        self.assertEqual(continuation["owner_host_id"], contract["supervisor_host_id"])
        self.assertEqual(heartbeat["owner_task_id"], contract["supervisor_task_id"])
        self.assertEqual(heartbeat["owner_host_id"], contract["supervisor_host_id"])
        self.assertTrue(heartbeat["logical_key"])
        self.assertNotEqual(
            heartbeat["logical_key"], heartbeat["definition_fingerprint"]
        )
        self.assertIn("create-pending", heartbeat["state"].split("|"))
        self.assertIn("update-pending", heartbeat["state"].split("|"))
        self.assertIn("result-unknown", heartbeat["state"].split("|"))
        self.assertIn("idle", contract["targets"][0]["state"].split("|"))
        self.assertIn("terminal", contract["targets"][0]["state"].split("|"))
        policy_application = contract["targets"][0][
            "protected_policy_application"
        ]
        self.assertEqual(
            set(policy_application),
            {
                "schema",
                "state",
                "policy_revision_id",
                "operation_policy_fingerprint",
                "recovery_ref",
                "intent_operation_id",
                "mutation_operation_id",
            },
        )
        self.assertEqual(
            policy_application["schema"],
            "codex.protected_policy_application_checkpoint.v1",
        )
        self.assertIn(
            "mutation-outcome-unknown",
            policy_application["state"].split("|"),
        )
        self.assertIn(
            "intent-outcome-unknown",
            policy_application["state"].split("|"),
        )
        self.assertTrue(policy_application["recovery_ref"])
        self.assertTrue(policy_application["intent_operation_id"])
        self.assertTrue(policy_application["mutation_operation_id"])

    def test_skill_keeps_one_continuation_owner_and_never_blocks_on_no_change(self):
        compact = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "exactly one native continuation owner",
            "prefer an already active native goal continuation",
            "do not add a heartbeat while it remains active",
            "verified handoff that retires or defers the prior continuation",
            "exact supervisor task id and host id",
            "inspect existing native wakeups",
            "stored heartbeat id first",
            "supervisor task and host plus stable logical key",
            "persist `create-pending`",
            "persist `result-unknown`",
            "never blind retry",
            "persist `update-pending`",
            "not a replacement create or blind update retry",
            "multiple or ambiguous matches, create nothing",
            "never a target task or an os scheduler",
            "owner task and host",
            "performs one bounded wait",
            "persists every returned cursor",
            "reporting remains transition-only",
            "must not mark the supervision goal blocked",
            "completed latest turn is `idle`, not `terminal`",
            "never use goal `blocked` as a pause",
        ):
            self.assertIn(invariant, compact)

    def test_reference_distinguishes_idle_terminal_and_unchanged(self):
        compact = " ".join(REFERENCE.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "| `idle` |",
            "| `terminal` |",
            "completed latest turn alone is `idle`, not `terminal`",
            "unchanged timeout is not a transition and preserves the prior state",
            "ongoing watch has exactly one continuation owner",
            "`continuation_owner.kind` is `goal-runtime` and `heartbeat` is `null`",
            "active goal continuation takes precedence",
            "create no heartbeat unless a verified handoff",
            "resolve the stored heartbeat id first",
            "exact `supervisor_host_id`, `supervisor_task_id`, and `logical_key`",
            "definition fingerprint records mutable desired configuration",
            "with zero matches, persist `create-pending`",
            "persist `result-unknown`",
            "never blind-retry create",
            "with one match, reuse that exact id",
            "persist `update-pending` before an update",
            "never a blind update retry or create",
            "with multiple or ambiguous matches, create nothing",
            "perform exactly one bounded wait",
            "persist every returned cursor",
            "not by themselves goal blockers",
            "goal `blocked` is a status report, not a pause",
            "missing the supervisor task or host",
            "heartbeat logical key",
            "heartbeat lifecycle state",
            "do not create, update, or retire a wakeup",
            "confirm its owner task and host",
        ):
            self.assertIn(invariant, compact)

    def test_attention_and_failure_take_precedence_over_idle(self):
        compact = " ".join(REFERENCE.read_text(encoding="utf-8").split()).lower()
        self.assertIn("classify `attention` and `failed` before `idle`", compact)
        self.assertIn(
            "only when no approval, input, explicit attention, system error, "
            "or terminal failure signal exists",
            compact,
        )

    def test_aggregate_claims_fail_closed_without_exact_coverage(self):
        compact = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "separate universe breadth from per-item evidence depth",
            "bind the item set and cutoff",
            "exact item-by-dimension coverage",
            "`capability-workbench:capability-auditor`",
            "do not install or activate another plugin",
            "report the claim as bounded or partial",
            "independent enumeration evidence",
        ):
            self.assertIn(invariant, compact)

    def test_open_gates_require_current_eligible_targets(self):
        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "current live subject or explicit policy requirement",
            "a possible action or available authority is not a gate",
            "zero eligible targets",
            "`not-applicable` outside `open_gates`",
            "never create a discussion, note, approval, or other external write",
        ):
            self.assertIn(invariant, skill)

        contract = " ".join(
            REFERENCE.read_text(encoding="utf-8").split()
        ).lower()
        for invariant in (
            "`open_gates` contains only currently applicable blockers",
            "eligibility evidence, and an owner",
            "capability availability, mutation authority, or a possible workflow",
            "complete inventory contains zero eligible targets",
            "never create an external object or write merely to make a checkpoint",
            '"gate_id": "stable-public-safe-gate-id"',
            '"eligibility_state": "eligible"',
            '"eligibility_evidence_ref": "opaque-current-evidence-ref"',
            '"eligibility_owner": "owning-workflow-or-policy"',
            '"required_transition": "bounded evidence-backed terminal condition"',
            "the supervisor may normalize the receipt into the checkpoint",
            "it must not synthesize eligibility",
            "subject, cutoff, eligibility, or owner drift",
            "a previously evidenced applicable gate",
            "a present empty `open_gates` list is valid",
            "must not be repopulated from prose",
        ):
            self.assertIn(invariant, contract)

    def test_canonical_adoption_contract_fails_closed(self):
        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "validating a supplied `previous -> current` pair is not canonical adoption",
            "explicit mutation authority",
            "existing store interface",
            "never emulate cas",
            "guardrails, not a canonical store or adopter",
            "full retained head token",
            "basis head-token fingerprint",
            "pair-only receipt",
            "generation and creating-intent fingerprint",
            "prevents fork and aba adoption",
            "`reconciliation-required`, not `not-adopted`",
            "independent closed verdicts",
        ):
            self.assertIn(invariant, skill)

        reference = REFERENCE.read_text(encoding="utf-8")
        contract = " ".join(reference.split()).lower()
        for invariant in (
            "## canonical checkpoint adoption",
            "producer-owned transition receipt",
            "separate consumer-owned commit",
            "candidate-supplied predecessor metadata is not authority",
            "existing canonical store interface",
            "never emulate this with a read followed by an ordinary write",
            "full head token",
            "unique monotonic generation",
            "a-to-b-to-a",
            "versioned canonical serialization and digest algorithm",
            "basis head-token fingerprint",
            "pair-only receipt without that binding",
            "reject a store or chain mismatch",
            "cannot repair a namespace mismatch",
            "protected-contract fingerprint",
            "immutable pre-cas adoption intent",
            "this order is non-circular",
            "terminal adoption receipt",
            "never an input to the candidate token",
            "exact replay of the same operation id and intent is idempotent",
            "same id with a different intent",
            "separately authorized baseline receipt",
            "read back the full token and native operation result",
            "`reconciliation-required`",
        ):
            self.assertIn(invariant, contract)

        verdict = adoption_verdict_example(reference)
        self.assertEqual(verdict["schema"], "codex.checkpoint_adoption.v1")
        expected_fields = {
            "pair": {"valid", "invalid", "unknown"},
            "lineage": {
                "valid",
                "baseline-valid",
                "unbound",
                "mismatch",
                "namespace-mismatch",
                "unknown",
            },
            "protection": {"valid", "mismatch", "authorized-new-chain", "unknown"},
            "commit": {
                "not-attempted",
                "committed",
                "conflict",
                "id-conflict",
                "outcome-unknown",
            },
            "readback": {"not-run", "matched", "different", "unavailable"},
            "adoption": {
                "not-eligible",
                "capability-unavailable",
                "adopted",
                "already-adopted",
                "head-conflict",
                "protected-mismatch",
                "namespace-mismatch",
                "id-conflict",
                "reconciliation-required",
            },
        }
        self.assertEqual(set(verdict) - {"schema"}, set(expected_fields))
        for field, states in expected_fields.items():
            self.assertEqual(set(verdict[field].split("|")), states)

        self.assertEqual(
            adoption_failure_schedule(reference),
            {
                "valid pair, but no authorized atomic store": (
                    "`pair=valid`, `commit=not-attempted`, "
                    "`adoption=capability-unavailable`"
                ),
                "missing basis head-token binding": (
                    "`lineage=unbound`, `commit=not-attempted`, "
                    "`adoption=not-eligible`"
                ),
                "wrong retained predecessor, generation, or aba token": (
                    "`lineage=mismatch`, `commit=not-attempted`, "
                    "`adoption=not-eligible`"
                ),
                "store or chain differs": (
                    "`lineage=namespace-mismatch`, `commit=not-attempted`, "
                    "`adoption=namespace-mismatch`"
                ),
                "protected goal or authority differs": (
                    "`protection=mismatch`, `commit=not-attempted`, "
                    "`adoption=protected-mismatch`"
                ),
                "compare-and-swap observes another full head token": (
                    "`commit=conflict`, `adoption=head-conflict`"
                ),
                "store confirms commit but readback is unavailable": (
                    "`commit=committed`, "
                    "`readback=unavailable`, `adoption=reconciliation-required`"
                ),
                "native commit outcome and readback are unavailable": (
                    "`commit=outcome-unknown`, `readback=unavailable`, "
                    "`adoption=reconciliation-required`"
                ),
                "store confirms commit but readback names a different token": (
                    "`commit=committed`, `readback=different`, "
                    "`adoption=reconciliation-required`"
                ),
                "exact operation replay and matching readback": (
                    "`commit=committed`, `readback=matched`, "
                    "`adoption=already-adopted`"
                ),
                "same operation id with different intent": (
                    "`commit=id-conflict`, `adoption=id-conflict`"
                ),
                "atomic commit and exact readback both succeed": (
                    "`commit=committed`, `readback=matched`, `adoption=adopted`"
                ),
            },
        )

    def test_protected_policy_application_blocks_stale_mutations(self):
        reference = REFERENCE.read_text(encoding="utf-8")
        receipt = protected_policy_application_example(reference)
        self.assertEqual(
            receipt["schema"], "codex.protected_policy_application.v1"
        )
        self.assertEqual(
            set(receipt),
            {
                "schema",
                "policy_revision_id",
                "authorizer",
                "from_protected_contract_fingerprint",
                "to_protected_contract_fingerprint",
                "receiver_thread_id",
                "operation_policy_fingerprint",
                "recovery_ref",
                "receiver_adoption",
                "operation_policy",
                "prewrite_intent",
                "mutation",
                "readback",
                "application",
            },
        )
        self.assertEqual(receipt["authorizer"], "user")
        recovery = trusted_policy_evidence()[receipt["recovery_ref"]]
        self.assertEqual(
            recovery["schema"],
            "codex.protected_policy_application_recovery.v1",
        )
        self.assertEqual(
            recovery["intent_operation_id"],
            receipt["prewrite_intent"]["operation_id"],
        )
        self.assertEqual(
            recovery["mutation_operation_id"],
            receipt["mutation"]["operation_id"],
        )
        self.assertEqual(
            set(receipt["receiver_adoption"]),
            {
                "status",
                "receiver_thread_id",
                "acknowledgement_ref",
                "policy_revision_id",
                "from_protected_contract_fingerprint",
                "to_protected_contract_fingerprint",
                "operation_policy_fingerprint",
                "cutoff",
            },
        )
        self.assertEqual(receipt["receiver_adoption"]["status"], "adopted")
        self.assertEqual(
            set(receipt["operation_policy"]),
            {
                "destination_ref",
                "subject_ref",
                "operation",
                "eligibility_cutoff",
                "mandatory_fields",
            },
        )
        self.assertTrue(receipt["operation_policy"]["mandatory_fields"])
        self.assertEqual(
            receipt["operation_policy_fingerprint"],
            operation_policy_fingerprint(receipt["operation_policy"]),
        )
        self.assertEqual(
            set(receipt["operation_policy"]["mandatory_fields"][0]),
            {
                "field_ref",
                "expected_value_fingerprint",
                "expectation_evidence_ref",
            },
        )
        self.assertTrue(
            valid_keyed_fingerprint(
                receipt["operation_policy"]["mandatory_fields"][0][
                    "expected_value_fingerprint"
                ]
            )
        )
        self.assertEqual(
            set(receipt["prewrite_intent"]),
            {
                "status",
                "store_schema",
                "store_ref",
                "store_authorization_ref",
                "operation_id",
                "mutation_operation_id",
                "intent_ref",
                "receiver_thread_id",
                "receiver_acknowledgement_ref",
                "operation_policy_fingerprint",
                "relation",
                "ordering_evidence_ref",
                "immutability_evidence_ref",
                "cutoff",
            },
        )
        self.assertEqual(
            set(receipt["mutation"]),
            {
                "state",
                "operation_id",
                "destination_ref",
                "subject_ref",
                "receipt_ref",
                "prewrite_intent_operation_id",
                "prewrite_intent_ref",
                "cutoff",
            },
        )
        self.assertEqual(
            set(receipt["readback"]),
            {
                "state",
                "object_ref",
                "cutoff",
                "mutation_operation_id",
                "mutation_receipt_ref",
                "relation",
                "ordering_evidence_ref",
                "field_results",
            },
        )
        self.assertEqual(receipt["readback"]["state"], "complete")
        self.assertEqual(
            set(receipt["readback"]["field_results"][0]),
            {
                "field_ref",
                "observed_value_fingerprint",
                "evidence_ref",
                "status",
            },
        )
        self.assertEqual(
            evaluate_protected_policy_application(receipt), "applied"
        )
        self.assertEqual(
            receipt["operation_policy"]["mandatory_fields"][0][
                "expected_value_fingerprint"
            ],
            trusted_keyed_fingerprint(),
        )
        self.assertEqual(
            receipt["operation_policy_fingerprint"],
            trusted_policy_evidence()["opaque-receiver-owned-ack-ref"][
                "operation_policy_fingerprint"
            ],
        )

        def scalar_leaves(value, path=()):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield from scalar_leaves(child, path + (key,))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    yield from scalar_leaves(child, path + (index,))
            else:
                yield path, value

        for path, value in scalar_leaves(receipt):
            substituted = copy.deepcopy(receipt)
            target = substituted
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = f"{value}-substituted"
            with self.subTest(single_leaf_substitution=".".join(map(str, path))):
                self.assertNotEqual(
                    evaluate_protected_policy_application(substituted),
                    "applied",
                )

        cross_receiver_replay = copy.deepcopy(receipt)
        cross_receiver_replay["receiver_thread_id"] = "different-receiver"
        self.assertEqual(
            evaluate_protected_policy_application(cross_receiver_replay),
            "invalid",
        )

        missing_adoption_evidence = copy.deepcopy(receipt)
        missing_adoption_evidence["receiver_adoption"]["acknowledgement_ref"] = ""
        self.assertEqual(
            evaluate_protected_policy_application(missing_adoption_evidence),
            "invalid",
        )

        wrong_adopted_fingerprint = copy.deepcopy(receipt)
        wrong_adopted_fingerprint["receiver_adoption"][
            "to_protected_contract_fingerprint"
        ] = "different-protected-fingerprint"
        self.assertEqual(
            evaluate_protected_policy_application(wrong_adopted_fingerprint),
            "invalid",
        )

        wrong_predecessor_fingerprint = copy.deepcopy(receipt)
        wrong_predecessor_fingerprint["receiver_adoption"][
            "from_protected_contract_fingerprint"
        ] = "different-prior-protected-fingerprint"
        self.assertEqual(
            evaluate_protected_policy_application(wrong_predecessor_fingerprint),
            "invalid",
        )

        understated_application = copy.deepcopy(receipt)
        understated_application["application"] = "blocked"
        self.assertEqual(
            evaluate_protected_policy_application(understated_application),
            "invalid",
        )

        wrong_policy_fingerprint = copy.deepcopy(receipt)
        wrong_policy_fingerprint["operation_policy_fingerprint"] = (
            "sha256:" + "0" * 64
        )
        self.assertEqual(
            evaluate_protected_policy_application(wrong_policy_fingerprint),
            "invalid",
        )

        late_adoption_intent = copy.deepcopy(receipt)
        late_adoption_intent["prewrite_intent"][
            "receiver_acknowledgement_ref"
        ] = "different-receiver-ack"
        self.assertEqual(
            evaluate_protected_policy_application(late_adoption_intent),
            "invalid",
        )

        wrong_mutation_intent = copy.deepcopy(receipt)
        wrong_mutation_intent["mutation"][
            "prewrite_intent_ref"
        ] = "different-prewrite-intent"
        self.assertEqual(
            evaluate_protected_policy_application(wrong_mutation_intent),
            "invalid",
        )

        wrong_mutation_operation = copy.deepcopy(receipt)
        wrong_mutation_operation["readback"][
            "mutation_operation_id"
        ] = "different-mutation-operation"
        self.assertEqual(
            evaluate_protected_policy_application(wrong_mutation_operation),
            "policy-drift",
        )

        wrong_mutation_destination = copy.deepcopy(receipt)
        wrong_mutation_destination["mutation"][
            "destination_ref"
        ] = "different-destination"
        self.assertEqual(
            evaluate_protected_policy_application(wrong_mutation_destination),
            "invalid",
        )

        unauthorized_store = copy.deepcopy(receipt)
        unauthorized_store["prewrite_intent"][
            "store_schema"
        ] = "filesystem.local-write.v1"
        self.assertEqual(
            evaluate_protected_policy_application(unauthorized_store),
            "invalid",
        )

        missing_store_authorization = copy.deepcopy(receipt)
        missing_store_authorization["prewrite_intent"][
            "store_authorization_ref"
        ] = ""
        self.assertEqual(
            evaluate_protected_policy_application(missing_store_authorization),
            "invalid",
        )

        missing_immutability = copy.deepcopy(receipt)
        missing_immutability["prewrite_intent"][
            "immutability_evidence_ref"
        ] = ""
        self.assertEqual(
            evaluate_protected_policy_application(missing_immutability),
            "invalid",
        )

        stale_readback = copy.deepcopy(receipt)
        stale_readback["readback"][
            "mutation_receipt_ref"
        ] = "different-mutation-receipt"
        self.assertEqual(
            evaluate_protected_policy_application(stale_readback),
            "policy-drift",
        )

        unordered_readback = copy.deepcopy(receipt)
        unordered_readback["readback"]["relation"] = "before-mutation"
        self.assertEqual(
            evaluate_protected_policy_application(unordered_readback),
            "policy-drift",
        )

        for label, path, value in (
            (
                "adoption acknowledgement",
                ("receiver_adoption", "acknowledgement_ref"),
                {"raw": "payload"},
            ),
            (
                "adoption cutoff",
                ("receiver_adoption", "cutoff"),
                ["raw", "payload"],
            ),
            (
                "mutation receipt",
                ("mutation", "receipt_ref"),
                {"raw": "payload"},
            ),
            (
                "prewrite intent",
                ("prewrite_intent", "intent_ref"),
                {"raw": "payload"},
            ),
            (
                "intent store authorization",
                ("prewrite_intent", "store_authorization_ref"),
                {"raw": "payload"},
            ),
            (
                "expectation evidence",
                (
                    "operation_policy",
                    "mandatory_fields",
                    0,
                    "expectation_evidence_ref",
                ),
                {"raw": "payload"},
            ),
            (
                "readback object",
                ("readback", "object_ref"),
                ["raw", "payload"],
            ),
            (
                "field evidence",
                ("readback", "field_results", 0, "evidence_ref"),
                {"raw": "payload"},
            ),
            (
                "oversized field evidence",
                ("readback", "field_results", 0, "evidence_ref"),
                "x" * (MAX_POLICY_SCALAR_BYTES + 1),
            ),
        ):
            malformed = copy.deepcopy(receipt)
            target = malformed
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = value
            with self.subTest(malformed_nested_field=label):
                self.assertEqual(
                    evaluate_protected_policy_application(malformed), "invalid"
                )

        missing = copy.deepcopy(receipt)
        missing["readback"]["field_results"] = []
        self.assertEqual(
            evaluate_protected_policy_application(missing), "policy-drift"
        )

        duplicate = copy.deepcopy(receipt)
        duplicate["readback"]["field_results"].append(
            copy.deepcopy(duplicate["readback"]["field_results"][0])
        )
        self.assertEqual(
            evaluate_protected_policy_application(duplicate), "invalid"
        )

        mismatched = copy.deepcopy(receipt)
        mismatched["readback"]["field_results"][0][
            "observed_value_fingerprint"
        ]["digest"] = "3" * 64
        self.assertEqual(
            evaluate_protected_policy_application(mismatched), "policy-drift"
        )

        for label, fingerprint in (
            ("raw private value", "person@example.invalid"),
            ("bare digest", "4" * 64),
            (
                "unsupported envelope",
                {
                    "scheme": "sha256",
                    "key_ref_fingerprint": "sha256:" + "1" * 64,
                    "digest": "2" * 64,
                },
            ),
        ):
            malformed_fingerprint = copy.deepcopy(receipt)
            malformed_fingerprint["operation_policy"]["mandatory_fields"][0][
                "expected_value_fingerprint"
            ] = fingerprint
            malformed_fingerprint["readback"]["field_results"][0][
                "observed_value_fingerprint"
            ] = copy.deepcopy(fingerprint)
            malformed_fingerprint["operation_policy_fingerprint"] = (
                operation_policy_fingerprint(
                    malformed_fingerprint["operation_policy"]
                )
            )
            malformed_fingerprint["receiver_adoption"][
                "operation_policy_fingerprint"
            ] = malformed_fingerprint["operation_policy_fingerprint"]
            malformed_fingerprint["prewrite_intent"][
                "operation_policy_fingerprint"
            ] = malformed_fingerprint["operation_policy_fingerprint"]
            with self.subTest(malformed_keyed_fingerprint=label):
                self.assertEqual(
                    evaluate_protected_policy_application(malformed_fingerprint),
                    "invalid",
                )

        forged_keyed_receipt = copy.deepcopy(receipt)
        forged_keyed_receipt["operation_policy"]["mandatory_fields"][0][
            "expected_value_fingerprint"
        ] = {
            "scheme": "hmac-sha256",
            "key_ref_fingerprint": "sha256:" + "4" * 64,
            "digest": "5" * 64,
        }
        forged_keyed_receipt["readback"]["field_results"][0][
            "observed_value_fingerprint"
        ] = copy.deepcopy(
            forged_keyed_receipt["operation_policy"]["mandatory_fields"][0][
                "expected_value_fingerprint"
            ]
        )
        forged_policy_fingerprint = operation_policy_fingerprint(
            forged_keyed_receipt["operation_policy"]
        )
        forged_keyed_receipt[
            "operation_policy_fingerprint"
        ] = forged_policy_fingerprint
        forged_keyed_receipt["receiver_adoption"][
            "operation_policy_fingerprint"
        ] = forged_policy_fingerprint
        forged_keyed_receipt["prewrite_intent"][
            "operation_policy_fingerprint"
        ] = forged_policy_fingerprint
        forged_evidence = copy.deepcopy(trusted_policy_evidence())
        forged_evidence["opaque-receiver-owned-ack-ref"][
            "operation_policy_fingerprint"
        ] = forged_policy_fingerprint
        forged_evidence["opaque-keyed-expectation-proof-ref"][
            "operation_policy_fingerprint"
        ] = forged_policy_fingerprint
        forged_evidence["opaque-keyed-expectation-proof-ref"][
            "value_fingerprint"
        ] = copy.deepcopy(
            forged_keyed_receipt["operation_policy"]["mandatory_fields"][0][
                "expected_value_fingerprint"
            ]
        )
        # Receipt-supplied or caller-forged records cannot replace the fixed
        # receiver/store/provider resolver used by the acceptance oracle.
        self.assertNotEqual(forged_evidence, trusted_policy_evidence())
        self.assertEqual(
            evaluate_protected_policy_application(forged_keyed_receipt),
            "invalid",
        )

        def mark_not_attempted(candidate):
            candidate["mutation"].update(
                {
                    "state": "not-attempted",
                    "operation_id": None,
                    "destination_ref": None,
                    "subject_ref": None,
                    "receipt_ref": None,
                    "prewrite_intent_operation_id": None,
                    "prewrite_intent_ref": None,
                    "cutoff": None,
                }
            )
            candidate["readback"].update(
                {
                    "state": "not-run",
                    "object_ref": None,
                    "cutoff": None,
                    "mutation_operation_id": None,
                    "mutation_receipt_ref": None,
                    "relation": None,
                    "ordering_evidence_ref": None,
                    "field_results": [],
                }
            )

        stale_receiver = copy.deepcopy(receipt)
        stale_receiver["receiver_adoption"]["status"] = "not-proven"
        mark_not_attempted(stale_receiver)
        self.assertEqual(
            evaluate_protected_policy_application(stale_receiver), "blocked"
        )

        malformed_stale_receiver = copy.deepcopy(stale_receiver)
        malformed_result = copy.deepcopy(receipt["readback"]["field_results"][0])
        malformed_stale_receiver["readback"]["field_results"] = [
            malformed_result,
            copy.deepcopy(malformed_result),
        ]
        self.assertEqual(
            evaluate_protected_policy_application(malformed_stale_receiver),
            "invalid",
        )

        unauthorized_mutation = copy.deepcopy(receipt)
        unauthorized_mutation["receiver_adoption"]["status"] = "not-proven"
        self.assertEqual(
            evaluate_protected_policy_application(unauthorized_mutation),
            "policy-drift",
        )

        nonadopted_unknown = copy.deepcopy(receipt)
        nonadopted_unknown["receiver_adoption"]["status"] = "not-proven"
        nonadopted_unknown["mutation"]["state"] = "outcome-unknown"
        nonadopted_unknown["mutation"]["receipt_ref"] = None
        nonadopted_unknown["readback"].update(
            {
                "state": "not-run",
                "object_ref": None,
                "cutoff": None,
                "mutation_operation_id": None,
                "mutation_receipt_ref": None,
                "relation": None,
                "ordering_evidence_ref": None,
                "field_results": [],
            }
        )
        self.assertEqual(
            evaluate_protected_policy_application(nonadopted_unknown),
            "reconciliation-required",
        )

        unknown_with_policy_mismatch = copy.deepcopy(nonadopted_unknown)
        unknown_with_policy_mismatch["operation_policy_fingerprint"] = (
            "sha256:" + "0" * 64
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                unknown_with_policy_mismatch
            ),
            "reconciliation-required",
        )

        unknown_with_binding_mismatch = copy.deepcopy(nonadopted_unknown)
        unknown_with_binding_mismatch["mutation"][
            "destination_ref"
        ] = "different-destination"
        unknown_with_binding_mismatch["prewrite_intent"][
            "store_schema"
        ] = "different-store-schema"
        self.assertEqual(
            evaluate_protected_policy_application(
                unknown_with_binding_mismatch
            ),
            "reconciliation-required",
        )

        unknown_with_malformed_fingerprint = copy.deepcopy(nonadopted_unknown)
        unknown_with_malformed_fingerprint[
            "operation_policy_fingerprint"
        ] = "not-a-fingerprint"
        self.assertEqual(
            evaluate_protected_policy_application(
                unknown_with_malformed_fingerprint
            ),
            "invalid",
        )

        missing_mutation_operation = copy.deepcopy(nonadopted_unknown)
        missing_mutation_operation["mutation"]["operation_id"] = None
        self.assertEqual(
            evaluate_protected_policy_application(missing_mutation_operation),
            "invalid",
        )

        for section, field in (
            ("mutation", "operation_id"),
            ("mutation", "prewrite_intent_operation_id"),
            ("mutation", "prewrite_intent_ref"),
            ("prewrite_intent", "operation_id"),
            ("prewrite_intent", "mutation_operation_id"),
            ("prewrite_intent", "intent_ref"),
        ):
            conflicting_unknown_identity = copy.deepcopy(nonadopted_unknown)
            conflicting_unknown_identity[section][field] = (
                f"different-{field.replace('_', '-')}"
            )
            self.assertEqual(
                evaluate_protected_policy_application(
                    conflicting_unknown_identity
                ),
                "invalid",
                f"{section}.{field}",
            )

        coordinated_unknown_identity = copy.deepcopy(nonadopted_unknown)
        coordinated_unknown_identity["prewrite_intent"].update(
            {
                "operation_id": "different-intent-operation-id",
                "mutation_operation_id": "different-mutation-operation-id",
                "intent_ref": "different-intent-ref",
            }
        )
        coordinated_unknown_identity["mutation"].update(
            {
                "operation_id": "different-mutation-operation-id",
                "prewrite_intent_operation_id": (
                    "different-intent-operation-id"
                ),
                "prewrite_intent_ref": "different-intent-ref",
            }
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                coordinated_unknown_identity
            ),
            "invalid",
        )

        coordinated_unknown_intent_ref = copy.deepcopy(nonadopted_unknown)
        coordinated_unknown_intent_ref["prewrite_intent"][
            "intent_ref"
        ] = "different-intent-ref"
        coordinated_unknown_intent_ref["mutation"][
            "prewrite_intent_ref"
        ] = "different-intent-ref"
        self.assertEqual(
            evaluate_protected_policy_application(
                coordinated_unknown_intent_ref
            ),
            "invalid",
        )

        no_intent_store = copy.deepcopy(receipt)
        no_intent_store["prewrite_intent"].update(
            {
                "status": "capability-unavailable",
                "store_schema": None,
                "store_ref": None,
                "store_authorization_ref": None,
                "operation_id": None,
                "mutation_operation_id": None,
                "intent_ref": None,
                "receiver_thread_id": None,
                "receiver_acknowledgement_ref": None,
                "operation_policy_fingerprint": None,
                "relation": None,
                "ordering_evidence_ref": None,
                "immutability_evidence_ref": None,
                "cutoff": None,
            }
        )
        mark_not_attempted(no_intent_store)
        self.assertEqual(
            evaluate_protected_policy_application(no_intent_store), "blocked"
        )

        intent_outcome_unknown = copy.deepcopy(receipt)
        intent_outcome_unknown["prewrite_intent"].update(
            {
                "status": "outcome-unknown",
                "intent_ref": None,
                "immutability_evidence_ref": None,
            }
        )
        mark_not_attempted(intent_outcome_unknown)
        self.assertEqual(
            evaluate_protected_policy_application(intent_outcome_unknown),
            "reconciliation-required",
        )

        intent_unknown_with_policy_mismatch = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_policy_mismatch[
            "operation_policy_fingerprint"
        ] = "sha256:" + "0" * 64
        self.assertEqual(
            evaluate_protected_policy_application(
                intent_unknown_with_policy_mismatch
            ),
            "reconciliation-required",
        )

        missing_intent_operation = copy.deepcopy(intent_outcome_unknown)
        missing_intent_operation["prewrite_intent"]["operation_id"] = None
        self.assertEqual(
            evaluate_protected_policy_application(missing_intent_operation),
            "invalid",
        )

        missing_retained_mutation_operation = copy.deepcopy(
            intent_outcome_unknown
        )
        missing_retained_mutation_operation["prewrite_intent"][
            "mutation_operation_id"
        ] = None
        self.assertEqual(
            evaluate_protected_policy_application(
                missing_retained_mutation_operation
            ),
            "invalid",
        )

        coordinated_unknown_intent = copy.deepcopy(intent_outcome_unknown)
        coordinated_unknown_intent["prewrite_intent"].update(
            {
                "operation_id": "different-intent-operation-id",
                "mutation_operation_id": "different-mutation-operation-id",
            }
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                coordinated_unknown_intent
            ),
            "invalid",
        )

        intent_unknown_with_committed_mutation = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_committed_mutation["mutation"] = copy.deepcopy(
            receipt["mutation"]
        )
        intent_unknown_with_committed_mutation["mutation"].update(
            {
                "operation_id": "different-mutation-operation-id",
                "prewrite_intent_operation_id": (
                    "different-intent-operation-id"
                ),
                "prewrite_intent_ref": "different-intent-ref",
                "receipt_ref": "different-mutation-receipt-ref",
            }
        )
        intent_unknown_with_committed_mutation["readback"] = copy.deepcopy(
            receipt["readback"]
        )
        intent_unknown_with_committed_mutation["readback"].update(
            {
                "mutation_operation_id": "different-mutation-operation-id",
                "mutation_receipt_ref": "different-mutation-receipt-ref",
            }
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                intent_unknown_with_committed_mutation
            ),
            "invalid",
        )

        intent_and_mutation_both_unknown = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_and_mutation_both_unknown["prewrite_intent"][
            "intent_ref"
        ] = "opaque-immutable-prewrite-intent-ref"
        intent_and_mutation_both_unknown["mutation"].update(
            {
                "state": "outcome-unknown",
                "operation_id": (
                    "opaque-preallocated-mutation-operation-id"
                ),
                "destination_ref": "opaque-external-system-ref",
                "subject_ref": "opaque-action-intent-or-object-ref",
                "receipt_ref": None,
                "prewrite_intent_operation_id": (
                    "opaque-preallocated-intent-operation-id"
                ),
                "prewrite_intent_ref": (
                    "opaque-immutable-prewrite-intent-ref"
                ),
                "cutoff": "opaque-mutation-attempt-cutoff",
            }
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                intent_and_mutation_both_unknown
            ),
            "invalid",
        )

        intent_unknown_with_stale_mutation_observation = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_stale_mutation_observation["mutation"][
            "operation_id"
        ] = "stale-mutation-operation-id"
        self.assertEqual(
            evaluate_protected_policy_application(
                intent_unknown_with_stale_mutation_observation
            ),
            "invalid",
        )

        for field in (
            "store_schema",
            "store_ref",
            "store_authorization_ref",
        ):
            unknown_intent_with_other_store = copy.deepcopy(
                intent_outcome_unknown
            )
            unknown_intent_with_other_store["prewrite_intent"][field] = (
                f"different-{field.replace('_', '-')}"
            )
            self.assertEqual(
                evaluate_protected_policy_application(
                    unknown_intent_with_other_store
                ),
                "invalid",
                field,
            )

        unavailable = copy.deepcopy(receipt)
        unavailable["readback"]["field_results"][0]["status"] = "unavailable"
        self.assertEqual(
            evaluate_protected_policy_application(unavailable),
            "reconciliation-required",
        )

        unavailable_with_extra = copy.deepcopy(unavailable)
        extra_result = copy.deepcopy(
            unavailable_with_extra["readback"]["field_results"][0]
        )
        extra_result["field_ref"] = "different-field"
        extra_result["status"] = "matched"
        unavailable_with_extra["readback"]["field_results"].append(extra_result)
        self.assertEqual(
            evaluate_protected_policy_application(unavailable_with_extra),
            "reconciliation-required",
        )

        unavailable_with_policy_mismatch = copy.deepcopy(unavailable)
        unavailable_with_policy_mismatch["operation_policy_fingerprint"] = (
            "sha256:" + "0" * 64
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                unavailable_with_policy_mismatch
            ),
            "reconciliation-required",
        )

        incomplete_with_policy_mismatch = copy.deepcopy(receipt)
        incomplete_with_policy_mismatch["readback"].update(
            {
                "state": "not-run",
                "object_ref": None,
                "cutoff": None,
                "mutation_operation_id": None,
                "mutation_receipt_ref": None,
                "relation": None,
                "ordering_evidence_ref": None,
                "field_results": [],
            }
        )
        incomplete_with_policy_mismatch["operation_policy_fingerprint"] = (
            "sha256:" + "0" * 64
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                incomplete_with_policy_mismatch
            ),
            "reconciliation-required",
        )

        unavailable_with_conflicting_operation = copy.deepcopy(unavailable)
        unavailable_with_conflicting_operation["readback"][
            "mutation_operation_id"
        ] = "different-operation-id"
        self.assertEqual(
            evaluate_protected_policy_application(
                unavailable_with_conflicting_operation
            ),
            "invalid",
        )

        unavailable_with_coordinated_intent_ref = copy.deepcopy(unavailable)
        unavailable_with_coordinated_intent_ref["prewrite_intent"][
            "intent_ref"
        ] = "different-intent-ref"
        unavailable_with_coordinated_intent_ref["mutation"][
            "prewrite_intent_ref"
        ] = "different-intent-ref"
        self.assertEqual(
            evaluate_protected_policy_application(
                unavailable_with_coordinated_intent_ref
            ),
            "invalid",
        )

        unavailable_with_coordinated_receipt_ref = copy.deepcopy(unavailable)
        unavailable_with_coordinated_receipt_ref["mutation"][
            "receipt_ref"
        ] = "different-mutation-receipt-ref"
        unavailable_with_coordinated_receipt_ref["readback"][
            "mutation_receipt_ref"
        ] = "different-mutation-receipt-ref"
        self.assertEqual(
            evaluate_protected_policy_application(
                unavailable_with_coordinated_receipt_ref
            ),
            "invalid",
        )

        schedule = protected_policy_failure_schedule(reference)
        self.assertEqual(len(schedule), 21)
        for condition in (
            "direct user revision while unrelated evidence or skill intervention is pending",
            "malformed receipt, empty mandatory set, or duplicate mandatory or result field refs",
            "no authorized typed receiver rebind",
            "receiver reports a revision or protected-fingerprint conflict",
            "mutation outcome is unknown, regardless of another policy defect",
            "intent creation outcome is unknown, regardless of another policy defect",
            "unknown mutation carries a different operation id, intent operation id, or intent ref",
            "mutation is attempted or committed without exact receiver adoption",
            "receiver acknowledgement names a different receiver, revision, or fingerprint",
            "operation-policy fingerprint or keyed fingerprint envelope is malformed or differs at adoption, intent, or readback",
            "no existing authorized immutable intent store",
            "created intent lacks exact store schema, store identity, authorization, either operation id, or immutability evidence",
            "pre-write intent does not bind the exact receiver acknowledgement or prove `after-adoption`",
            "mutation receipt does not bind the exact destination, subject, operation id, or pre-write intent",
            "committed mutation lacks exact object identity, post-mutation cutoff, or complete readback",
            "readback does not bind the exact mutation operation id and receipt or prove `after-mutation`",
            "any mandatory field is missing, extra, mismatched, or has a different observed fingerprint",
            "any field result is unavailable, even with another field mismatch or extra result",
            "exact receiver adoption, committed mutation, object identity, cutoff, and every keyed field result match",
        ):
            self.assertIn(condition, schedule)

        skill = " ".join(SKILL.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "## rebind protected policy before external mutations",
            "capture a new protected policy revision",
            "do not encode that control-plane change as an evidence delta",
            "receiver-owned adoption of the exact policy revision",
            "acknowledgement ref and receiver cutoff",
            "if no authorized typed rebind exists",
            "keep the mutation blocked as `capability-unavailable`",
            "bind the authorized operation, destination, subject, cutoff",
            "every mandatory field",
            "receiver-bound immutable pre-write intent",
            "only through an existing authorized intent store",
            "fixed store schema, exact store",
            "existing authorization, preallocated intent-store and owning-system mutation operation ids",
            "retain both ids in the immutable intent",
            "immutability evidence",
            "if that store is unavailable",
            "never emulate it with an ordinary local write",
            "bind the mutation receipt to it",
            "read back the exact external object and one keyed, evidence-bound result",
            "closed hmac fingerprint envelope",
            "raw values and bare digests are malformed",
            "preallocate the owning-system operation id",
            "bind the readback to both that operation id and the exact mutation receipt",
            "owning-system ordering evidence",
            "missing, extra, or duplicate field results fail closed",
            "object existence",
            "is not policy adoption",
            "`policy-drift`",
            "`reconciliation-required`",
            "any unknown mutation or intent outcome",
            "reconcile by the preallocated operation id",
            "both retained intent identities to exactly match the immutable recovery record",
            "unknown intent write to match its recovered authorized store namespace",
            "mutation remains exactly `not-attempted` with no mutation or readback observations",
            "simultaneous unknown mutation is invalid",
            "independently resolve the canonical owning-system mutation receipt",
            "presence alone is insufficient",
            "regardless of another semantic policy defect",
            "unrelated pending evidence or skill intervention neither blocks",
            "nor proves receiver adoption",
        ):
            self.assertIn(invariant, skill)

        compact = " ".join(reference.split()).lower()
        for invariant in (
            "direct user revision to the protected contract is control-plane state",
            "capture it even when the target already has an unrelated pending intervention",
            "neither serializes protected-policy capture nor proves",
            "require a receiver-owned rebind",
            "rebind is not a new intervention action",
            "do not send an unlisted target message",
            "smuggle policy through `send-evidence-delta`",
            "must enumerate every mandatory external-object field before the write",
            "read back the exact object identity and every mandatory field",
            "keyed, non-reversible expected-value fingerprint envelopes",
            "only supported envelope is `hmac-sha256`",
            "a raw value or bare digest is malformed",
            "domain-separated message that binds the schema and field ref",
            "never use an unsalted digest for a low-entropy field",
            "opaque owning-system evidence ref",
            "persist an immutable pre-write intent after receiver adoption and before the mutation",
            "only through an existing authorized intent store",
            "never create or emulate that store with an ordinary write",
            "if it is unavailable, keep the affected external mutation blocked",
            "if intent creation has an unknown outcome, reconcile it before any external mutation",
            "fixed store schema, exact store, existing authorization",
            "preallocated intent-store operation id",
            "preallocated owning-system mutation operation id",
            "immutability evidence",
            "external mutation uses that retained mutation operation id",
            "terminal readback binds both the exact mutation operation id and mutation receipt",
            "independently resolve them",
            "non-empty string of at most 1024 utf-8 bytes",
            "reject oversized strings, objects, arrays, numbers, and booleans",
            "object existence",
            "is not proof of policy application",
            "`mandatory_fields` is non-empty",
            "unique by `field_ref`",
            "receiver-owned acknowledgement ref and cutoff",
            "echoes the top-level receiver identity, policy revision, and both protected fingerprints",
            "authorization, immutability, and `after-adoption`",
            "a complete readback proves `after-mutation`",
            "binds that exact mutation operation id and receipt",
            "contains exactly one result for every mandatory field and no others",
            "resolve evidence through the owning receiver, intent store, or external system",
            "normalized resolved records must exactly echo their subject bindings",
            "an unresolved, substituted, or differently bound ref cannot support `application=applied`",
            "independently load `recovery_ref` from the private immutable recovery store",
            "exact authorized intent-store schema/ref/authorization",
            "canonical intent ref",
            "the receipt cannot replace that record or supply an alternate resolver",
            "claimed later mutation or readback makes the receipt invalid",
            "simultaneous `mutation.state=outcome-unknown`",
            "after receipt shape, closed states, bounded scalar formats, and durable operation ids are valid",
            "unknown intent or mutation outcome takes precedence over every semantic policy or evidence mismatch",
            "whose unknown state or operation identity cannot be trusted remains `invalid`",
            "`protected_policy_application` is `null` when no affected policy application is active",
            "never overload `current_contract_revision` or `pending_intervention`",
            "persist its immutable content-addressed private `recovery_ref` before each adoption, intent, mutation, or readback attempt",
            "unknown outcome permits reconciliation only, never a new write",
            "keep the affected mutation blocked until receiver adoption",
            "`application=policy-drift`",
            "`application=reconciliation-required`",
            "not mutation authority, intent-store authority, or a canonical store implementation",
        ):
            self.assertIn(invariant, compact)

    def test_skill_handoff_binds_source_receiver_and_consumption_state(self):
        reference = HANDOFF_REFERENCE.read_text(encoding="utf-8")
        handoff = skill_handoff_example(reference)
        self.assertEqual(handoff["schema"], "codex.thread_skill_handoff.v2")
        self.assertEqual(
            set(handoff),
            {
                "schema",
                "handoff_id",
                "payload_fingerprint",
                "skill",
                "why_now",
                "mechanism",
                "receiver_basis",
                "requested_consumption",
                "activation_authorized",
                "scope_effect",
                "authority_effect",
                "ack_required",
            },
        )
        self.assertEqual(
            set(handoff["skill"]),
            {
                "name",
                "source_version",
                "source_repository",
                "source_revision",
                "source_path",
                "content_manifest",
                "content_digest",
                "verification_state",
            },
        )
        self.assertEqual(
            set(handoff["receiver_basis"]),
            {"catalog", "cache", "runtime"},
        )
        for surface in ("catalog", "cache"):
            self.assertEqual(
                set(handoff["receiver_basis"][surface]),
                {
                    "version",
                    "source_repository",
                    "source_revision",
                    "content_digest",
                    "relation_to_source",
                },
            )
            self.assertIn(
                handoff["receiver_basis"][surface]["relation_to_source"],
                {"exact", "older", "newer", "absent", "unknown"},
            )
        self.assertEqual(
            set(handoff["receiver_basis"]["runtime"]),
            {"discovery", "loaded"},
        )
        self.assertEqual(handoff["requested_consumption"], "direct-source-read")
        self.assertFalse(handoff["activation_authorized"])
        self.assertEqual(handoff["scope_effect"], "none")
        self.assertEqual(handoff["authority_effect"], "none")
        self.assertTrue(handoff["ack_required"])

        acknowledgement = skill_handoff_ack_example(reference)
        self.assertEqual(
            acknowledgement["schema"], "codex.thread_skill_handoff_ack.v1"
        )
        self.assertEqual(
            set(acknowledgement),
            {
                "schema",
                "handoff_id",
                "payload_fingerprint",
                "expected_source_content_digest",
                "observed_source",
                "receiver_record_fingerprint",
                "status",
                "reason",
                "supersession_evidence_ref",
                "observed_receiver",
                "consumption_mode",
                "runtime_used",
                "install_attempted",
                "evidence_refs",
            },
        )
        self.assertEqual(acknowledgement["status"], "applied")
        self.assertEqual(
            acknowledgement["reason"], "exact-direct-source-read"
        )
        self.assertEqual(
            acknowledgement["consumption_mode"], "direct-source-read"
        )
        self.assertFalse(acknowledgement["runtime_used"])
        self.assertFalse(acknowledgement["install_attempted"])
        self.assertEqual(
            set(acknowledgement["observed_receiver"]),
            {"catalog", "cache", "runtime"},
        )

        compact_reference = " ".join(reference.split()).lower()
        for invariant in (
            "new handoffs must use v2",
            "v1 cannot prove exact source identity, receiver version, "
            "consumption mode, or runtime activation",
            "runtime.discovery=active` is not proof of the loaded bytes",
            "`activation_authorized` is a constant false safety marker",
            "atomically reserve `(handoff_id, payload_fingerprint)`",
            "same id and fingerprint returns the stored terminal acknowledgement",
            "same id with a different fingerprint returns "
            "`conflict/id-conflict`",
            "persist the terminal acknowledgement atomically with the reservation",
            "expected digest always echoes the handoff",
            "`observed_source` independently records what the receiver verified",
            "content-addressed private payload ref",
            "deterministic validator",
        ):
            self.assertIn(invariant, compact_reference)

        compact_skill = " ".join(
            SKILL.read_text(encoding="utf-8").split()
        ).lower()
        for invariant in (
            "versioned handoff payload and acknowledgement",
            "immutable source, canonical content, and receiver "
            "catalog/cache/loaded-runtime identity",
            "`runtime-loaded` from `direct-source-read`",
            "without proving installed or runtime-active capability",
            "never install or refresh",
            "thread-skill-handoff-contract.md",
        ):
            self.assertIn(invariant, compact_skill)

        compact_supervision = " ".join(
            REFERENCE.read_text(encoding="utf-8").split()
        ).lower()
        for invariant in (
            "immutable content-addressed payload recovery ref",
            "expected source digest and requested consumption mode",
            "load and validate the immutable payload before accepting an "
            "acknowledgement",
            "never infer it from activity or reconstruct it from prose",
        ):
            self.assertIn(invariant, compact_supervision)

    def test_supervision_docs_are_public_safe_and_use_no_raw_directives(self):
        for path in (SKILL, REFERENCE, HANDOFF_REFERENCE):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            for forbidden in (
                "/Users/",
                "\\Users\\",
                "::automation",
                "RRULE:",
                "BEGIN:VEVENT",
            ):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
