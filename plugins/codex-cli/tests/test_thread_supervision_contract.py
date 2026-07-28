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


def strict_json_loads(text: str) -> object:
    def reject_duplicate_names(pairs: list[tuple[str, object]]) -> dict:
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON object name: {key}")
            value[key] = item
        return value

    def reject_non_json_constant(value: str) -> object:
        raise ValueError(f"non-JSON constant: {value}")

    return json.loads(
        text,
        object_pairs_hook=reject_duplicate_names,
        parse_constant=reject_non_json_constant,
    )


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
    return strict_json_loads(match.group(1))


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


POLICY_APPLICATION_STATES = {
    "revision-captured",
    "adoption-pending",
    "intent-pending",
    "intent-outcome-unknown",
    "mutation-pending",
    "mutation-outcome-unknown",
    "readback-pending",
    "terminal",
}
POLICY_APPLICATION_TRANSITIONS = {
    "revision-captured": {"revision-captured", "adoption-pending", "terminal"},
    "adoption-pending": {"adoption-pending", "intent-pending", "terminal"},
    "intent-pending": {
        "intent-pending",
        "intent-outcome-unknown",
        "mutation-pending",
        "terminal",
    },
    "intent-outcome-unknown": {
        "intent-outcome-unknown",
        "mutation-pending",
        "terminal",
    },
    "mutation-pending": {
        "mutation-pending",
        "mutation-outcome-unknown",
        "readback-pending",
        "terminal",
    },
    "mutation-outcome-unknown": {
        "mutation-outcome-unknown",
        "readback-pending",
        "terminal",
    },
    "readback-pending": {"readback-pending", "terminal"},
    "terminal": {"terminal"},
}
UNKNOWN_POLICY_APPLICATION_STATES = {
    "intent-outcome-unknown",
    "mutation-outcome-unknown",
}
POLICY_RECOVERY_FIELDS = {
    "schema",
    "application_id",
    "policy_revision_id",
    "checkpoint_state",
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
    "operation_namespace_ref",
    "migration_ref",
    "migration_source_checkpoint_ref",
    "migration_checkpoint_fingerprint",
    "migration_target_thread_id",
    "migration_target_host_id",
    "predecessor_ref",
    "reconciliation_receipt_ref",
}
POLICY_RECOVERY_IMMUTABLE_FIELDS = (
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
    "migration_ref",
    "migration_source_checkpoint_ref",
    "migration_checkpoint_fingerprint",
    "migration_target_thread_id",
    "migration_target_host_id",
)


def bounded_policy_enum(value: object, allowed: set[str]) -> bool:
    return bounded_policy_scalar(value) and value in allowed


def exact_policy_count(value: object) -> bool:
    return type(value) is int and value >= 0


def valid_policy_application_entry(item: object) -> bool:
    if not isinstance(item, dict) or set(item) != {
        "schema",
        "application_id",
        "state",
        "policy_revision_id",
        "operation_policy_fingerprint",
        "recovery_ref",
        "intent_operation_id",
        "mutation_operation_id",
    }:
        return False
    if item["schema"] != "codex.protected_policy_application_checkpoint.v2":
        return False
    if not bounded_policy_enum(item["state"], POLICY_APPLICATION_STATES):
        return False
    for field in (
        "application_id",
        "policy_revision_id",
        "recovery_ref",
    ):
        if not bounded_policy_scalar(item[field]):
            return False
    if not bounded_policy_scalar(item["operation_policy_fingerprint"]):
        return False
    for field in (
        "intent_operation_id",
        "mutation_operation_id",
    ):
        if item[field] is not None and not bounded_policy_scalar(item[field]):
            return False
    if item["state"] in {
        "intent-pending",
        "intent-outcome-unknown",
        "mutation-pending",
        "mutation-outcome-unknown",
        "readback-pending",
    } and (
        not bounded_policy_scalar(item["intent_operation_id"])
        or not bounded_policy_scalar(item["mutation_operation_id"])
    ):
        return False
    return True


def valid_policy_application_collection(value: object) -> bool:
    if not isinstance(value, list):
        return False
    application_ids = set()
    revision_ids = set()
    recovery_refs = set()
    for item in value:
        if not valid_policy_application_entry(item):
            return False
        if (
            item["application_id"] in application_ids
            or item["policy_revision_id"] in revision_ids
            or item["recovery_ref"] in recovery_refs
        ):
            return False
        application_ids.add(item["application_id"])
        revision_ids.add(item["policy_revision_id"])
        recovery_refs.add(item["recovery_ref"])
    return True


def policy_application_identity(item: dict) -> tuple[str, str]:
    return (
        item["application_id"],
        item["policy_revision_id"],
    )


def valid_policy_recovery_record(
    recovery: object,
    application_id: str,
    policy_revision_id: str,
) -> bool:
    if (
        not isinstance(recovery, dict)
        or set(recovery) != POLICY_RECOVERY_FIELDS
        or recovery.get("schema")
        != "codex.protected_policy_application_recovery.v2"
        or recovery.get("application_id") != application_id
        or recovery.get("policy_revision_id") != policy_revision_id
        or not bounded_policy_enum(
            recovery.get("checkpoint_state"), POLICY_APPLICATION_STATES
        )
        or not bounded_policy_scalar(recovery.get("operation_namespace_ref"))
    ):
        return False
    for field in (
        "receiver_thread_id",
        "store_ref",
        "store_authorization_ref",
        "intent_ref",
        "destination_ref",
        "subject_ref",
    ):
        if not bounded_policy_scalar(recovery.get(field)):
            return False
    for field in (
        "intent_operation_id",
        "mutation_operation_id",
        "migration_ref",
        "migration_source_checkpoint_ref",
        "migration_checkpoint_fingerprint",
        "migration_target_thread_id",
        "migration_target_host_id",
        "predecessor_ref",
        "reconciliation_receipt_ref",
    ):
        if recovery.get(field) is not None and not bounded_policy_scalar(
            recovery.get(field)
        ):
            return False
    migration_values = (
        recovery.get("migration_ref"),
        recovery.get("migration_source_checkpoint_ref"),
        recovery.get("migration_checkpoint_fingerprint"),
        recovery.get("migration_target_thread_id"),
        recovery.get("migration_target_host_id"),
    )
    if not (
        all(value is None for value in migration_values)
        or (
            all(bounded_policy_scalar(value) for value in migration_values)
            and valid_sha256_fingerprint(
                recovery.get("migration_ref")
            )
            and valid_sha256_fingerprint(
                recovery.get("migration_checkpoint_fingerprint")
            )
        )
    ):
        return False
    if not bounded_policy_scalar(
        recovery.get("operation_policy_fingerprint")
    ):
        return False
    if recovery.get(
        "store_schema"
    ) != "codex.authorized_immutable_intent_store.v1":
        return False
    return True


def policy_recovery_head(
    item: dict, evidence: dict[str, dict]
) -> dict | None:
    recovery = evidence.get(item["recovery_ref"])
    if (
        not valid_policy_recovery_record(
            recovery,
            item["application_id"],
            item["policy_revision_id"],
        )
        or recovery.get("operation_policy_fingerprint")
        != item.get("operation_policy_fingerprint")
        or recovery.get("checkpoint_state") != item.get("state")
        or recovery.get("intent_operation_id")
        != item.get("intent_operation_id")
        or recovery.get("mutation_operation_id")
        != item.get("mutation_operation_id")
    ):
        return None
    return recovery


def valid_migrated_policy_recovery_root(
    item: dict,
    root_ref: str,
    recovery: dict,
    evidence: dict[str, dict],
) -> bool:
    migration_ref = recovery.get("migration_ref")
    if not valid_sha256_fingerprint(migration_ref):
        return False
    migration = evidence.get(migration_ref)
    if (
        not isinstance(migration, dict)
        or checkpoint_fingerprint(migration) != migration_ref
    ):
        return False
    if set(migration) != {
        "schema",
        "source_checkpoint_schema",
        "checkpoint_fingerprint",
        "source_checkpoint_ref",
        "target_thread_id",
        "target_host_id",
        "legacy_recovery_ref",
        "migrated_recovery_ref",
        "operation_namespace_ref",
        "application_id",
        "policy_revision_id",
        "intent_operation_id",
        "mutation_operation_id",
    }:
        return False
    if (
        migration["schema"]
        != "codex.protected_policy_application_migration.v1"
        or migration["source_checkpoint_schema"]
        != "codex.thread_supervision.v1"
        or migration["migrated_recovery_ref"] != root_ref
        or not valid_sha256_fingerprint(
            migration["checkpoint_fingerprint"]
        )
        or any(
            not bounded_policy_scalar(migration[field])
            for field in (
                "target_thread_id",
                "target_host_id",
                "source_checkpoint_ref",
                "legacy_recovery_ref",
                "migrated_recovery_ref",
                "operation_namespace_ref",
                "application_id",
                "policy_revision_id",
            )
        )
        or any(
            migration[field] is not None
            and not bounded_policy_scalar(migration[field])
            for field in (
                "intent_operation_id",
                "mutation_operation_id",
            )
        )
        or migration["application_id"] != recovery["application_id"]
        or migration["policy_revision_id"]
        != recovery["policy_revision_id"]
        or migration["intent_operation_id"]
        != recovery["intent_operation_id"]
        or migration["mutation_operation_id"]
        != recovery["mutation_operation_id"]
        or migration["operation_namespace_ref"]
        != recovery["operation_namespace_ref"]
        or migration["checkpoint_fingerprint"]
        != recovery["migration_checkpoint_fingerprint"]
        or migration["source_checkpoint_ref"]
        != recovery["migration_source_checkpoint_ref"]
        or migration["target_thread_id"]
        != recovery["migration_target_thread_id"]
        or migration["target_host_id"]
        != recovery["migration_target_host_id"]
    ):
        return False
    legacy = evidence.get(migration["legacy_recovery_ref"])
    if not isinstance(legacy, dict) or set(legacy) != {
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
    }:
        return False
    source_checkpoint = evidence.get(migration["source_checkpoint_ref"])
    source_targets = (
        [
            target
            for target in source_checkpoint.get("targets", [])
            if isinstance(target, dict)
            and target.get("thread_id") == migration["target_thread_id"]
            and target.get("host_id") == migration["target_host_id"]
        ]
        if isinstance(source_checkpoint, dict)
        else []
    )
    expected_legacy_application = {
        "schema": "codex.protected_policy_application_checkpoint.v1",
        "state": recovery["checkpoint_state"],
        "policy_revision_id": migration["policy_revision_id"],
        "operation_policy_fingerprint": legacy[
            "operation_policy_fingerprint"
        ],
        "recovery_ref": migration["legacy_recovery_ref"],
        "intent_operation_id": migration["intent_operation_id"],
        "mutation_operation_id": migration["mutation_operation_id"],
    }
    if (
        len(source_targets) != 1
        or source_checkpoint.get("schema")
        != "codex.thread_supervision.v1"
        or checkpoint_fingerprint(source_checkpoint)
        != migration["checkpoint_fingerprint"]
        or source_targets[0].get("protected_policy_application")
        != expected_legacy_application
        or "protected_policy_application_state" in source_targets[0]
    ):
        return False
    expected_recovery = {
        **legacy,
        "schema": "codex.protected_policy_application_recovery.v2",
        "application_id": migration["application_id"],
        "checkpoint_state": recovery["checkpoint_state"],
        "operation_namespace_ref": migration[
            "operation_namespace_ref"
        ],
        "migration_ref": migration_ref,
        "migration_source_checkpoint_ref": migration[
            "source_checkpoint_ref"
        ],
        "migration_checkpoint_fingerprint": migration[
            "checkpoint_fingerprint"
        ],
        "migration_target_thread_id": migration["target_thread_id"],
        "migration_target_host_id": migration["target_host_id"],
        "predecessor_ref": None,
        "reconciliation_receipt_ref": None,
    }
    return (
        legacy["schema"]
        == "codex.protected_policy_application_recovery.v1"
        and legacy["policy_revision_id"] == recovery["policy_revision_id"]
        and legacy["operation_policy_fingerprint"]
        == recovery["operation_policy_fingerprint"]
        and legacy["intent_operation_id"]
        == recovery["intent_operation_id"]
        and legacy["mutation_operation_id"]
        == recovery["mutation_operation_id"]
        and recovery == expected_recovery
    )


def resolve_policy_recovery_chain(
    item: dict, evidence: dict[str, dict]
) -> list[tuple[str, dict]] | None:
    head = policy_recovery_head(item, evidence)
    if head is None:
        return None
    reverse_chain = []
    seen = set()
    ref = item["recovery_ref"]
    while bounded_policy_scalar(ref) and ref not in seen:
        seen.add(ref)
        recovery = evidence.get(ref)
        if not valid_policy_recovery_record(
            recovery,
            item["application_id"],
            item["policy_revision_id"],
        ):
            return None
        reverse_chain.append((ref, recovery))
        predecessor_ref = recovery.get("predecessor_ref")
        if predecessor_ref is None:
            break
        ref = predecessor_ref
    else:
        return None

    chain = list(reversed(reverse_chain))
    if chain[0][1].get("reconciliation_receipt_ref") is not None:
        return None
    root_ref, root = chain[0]
    native_root = (
        root.get("checkpoint_state") == "revision-captured"
        and all(
            root.get(field) is None
            for field in (
                "migration_ref",
                "migration_source_checkpoint_ref",
                "migration_checkpoint_fingerprint",
                "migration_target_thread_id",
                "migration_target_host_id",
            )
        )
    )
    if not native_root and not valid_migrated_policy_recovery_root(
        item,
        root_ref,
        root,
        evidence,
    ):
        return None
    prior_ref, prior = chain[0]
    for successor_ref, successor in chain[1:]:
        if successor.get("predecessor_ref") != prior_ref:
            return None
        if (
            successor.get("operation_namespace_ref")
            != prior.get("operation_namespace_ref")
        ):
            return None
        for field in POLICY_RECOVERY_IMMUTABLE_FIELDS:
            prior_value = prior.get(field)
            successor_value = successor.get(field)
            if (
                field.startswith("migration_")
                and successor_value != prior_value
            ) or (
                not field.startswith("migration_")
                and prior_value is not None
                and successor_value != prior_value
            ):
                return None
        prior_state = prior.get("checkpoint_state")
        successor_state = successor.get("checkpoint_state")
        if not bounded_policy_enum(
            prior_state, POLICY_APPLICATION_STATES
        ) or not bounded_policy_enum(
            successor_state, POLICY_APPLICATION_TRANSITIONS[prior_state]
        ):
            return None
        reconciliation_ref = successor.get("reconciliation_receipt_ref")
        reconciliation_required = (
            prior_state in UNKNOWN_POLICY_APPLICATION_STATES
            and successor_state != prior_state
        )
        if (reconciliation_ref is not None) != reconciliation_required:
            return None
        if reconciliation_required:
            reconciliation = evidence.get(reconciliation_ref)
            if (
                not isinstance(reconciliation, dict)
                or set(reconciliation)
                != {
                    "schema",
                    "authority",
                    "application_id",
                    "policy_revision_id",
                    "from_state",
                    "to_state",
                    "from_recovery_ref",
                    "to_recovery_ref",
                    "intent_operation_id",
                    "mutation_operation_id",
                }
                or reconciliation["schema"]
                != "codex.protected_policy_application_reconciliation.v1"
                or reconciliation["authority"] != "owning-system"
                or reconciliation["application_id"] != item["application_id"]
                or reconciliation["policy_revision_id"]
                != item["policy_revision_id"]
                or reconciliation["from_state"] != prior_state
                or reconciliation["to_state"] != successor_state
                or reconciliation["from_recovery_ref"] != prior_ref
                or reconciliation["to_recovery_ref"] != successor_ref
                or reconciliation["intent_operation_id"]
                != successor.get("intent_operation_id")
                or reconciliation["mutation_operation_id"]
                != successor.get("mutation_operation_id")
            ):
                return None
        prior_ref, prior = successor_ref, successor
    return chain if chain[-1][1] == head else None


def policy_recovery_chain_reaches(
    before_item: dict,
    after_item: dict,
    evidence: dict[str, dict],
) -> bool:
    if policy_application_identity(before_item) != policy_application_identity(
        after_item
    ):
        return False
    before_chain = resolve_policy_recovery_chain(before_item, evidence)
    after_chain = resolve_policy_recovery_chain(after_item, evidence)
    if before_chain is None or after_chain is None:
        return False
    before_refs = [ref for ref, _ in before_chain]
    after_refs = [ref for ref, _ in after_chain]
    return after_refs[: len(before_refs)] == before_refs


def policy_recovery_appends_exact_successor(
    before_item: dict,
    after_item: dict,
    evidence: dict[str, dict],
) -> bool:
    if policy_application_identity(before_item) != policy_application_identity(
        after_item
    ):
        return False
    before_chain = resolve_policy_recovery_chain(before_item, evidence)
    after_chain = resolve_policy_recovery_chain(after_item, evidence)
    if before_chain is None or after_chain is None:
        return False
    before_refs = [ref for ref, _ in before_chain]
    after_refs = [ref for ref, _ in after_chain]
    return (
        len(after_refs) == len(before_refs) + 1
        and after_refs[:-1] == before_refs
        and after_chain[-1][1].get("predecessor_ref")
        == before_item["recovery_ref"]
    )


def resolve_retired_policy_applications(
    ref: object, evidence: dict[str, dict]
) -> list[dict] | None:
    if ref is None:
        return []
    records = []
    seen_refs = set()
    while ref is not None:
        if not bounded_policy_scalar(ref) or ref in seen_refs:
            return None
        seen_refs.add(ref)
        record = evidence.get(ref)
        if not isinstance(record, dict) or set(record) != {
            "schema",
            "predecessor_ref",
            "tombstones",
        }:
            return None
        if record["schema"] != (
            "codex.protected_policy_application_retired_index.v1"
        ):
            return None
        tombstones = record["tombstones"]
        if (
            not isinstance(tombstones, list)
            or not tombstones
            or len(tombstones) > 8
        ):
            return None
        for tombstone in tombstones:
            if not isinstance(tombstone, dict) or set(tombstone) != {
                "schema",
                "application_id",
                "policy_revision_id",
                "recovery_ref",
                "terminal_receipt_ref",
            }:
                return None
            if tombstone["schema"] != (
                "codex.protected_policy_application_terminal.v1"
            ):
                return None
            if not all(
                bounded_policy_scalar(tombstone[field])
                for field in (
                    "application_id",
                    "policy_revision_id",
                    "recovery_ref",
                    "terminal_receipt_ref",
                )
            ):
                return None
            terminal = evidence.get(tombstone["terminal_receipt_ref"])
            if not isinstance(terminal, dict) or set(terminal) != {
                "schema",
                "producer",
                "producer_authority_ref",
                "application_id",
                "policy_revision_id",
                "recovery_ref",
                "application_receipt_ref",
                "reconciliation_receipt_ref",
                "terminal_application",
            }:
                return None
            if terminal["schema"] != (
                "codex.protected_policy_application_terminal_receipt.v1"
            ):
                return None
            if not bounded_policy_enum(
                terminal["terminal_application"],
                {"invalid", "blocked", "applied", "policy-drift"},
            ):
                return None
            if (
                terminal["producer"] != "codex-thread-supervisor"
                or not bounded_policy_scalar(
                    terminal["producer_authority_ref"]
                )
                or not bounded_policy_scalar(
                    terminal["application_receipt_ref"]
                )
                or (
                    terminal["reconciliation_receipt_ref"] is not None
                    and not bounded_policy_scalar(
                        terminal["reconciliation_receipt_ref"]
                    )
                )
            ):
                return None
            if any(
                terminal[field] != tombstone[field]
                for field in (
                    "application_id",
                    "policy_revision_id",
                    "recovery_ref",
                )
            ):
                return None
            authority = evidence.get(terminal["producer_authority_ref"])
            if authority != {
                "schema": (
                    "codex.protected_policy_application_terminal_authority.v1"
                ),
                "producer": terminal["producer"],
                "terminal_receipt_ref": tombstone["terminal_receipt_ref"],
                "application_receipt_ref": terminal[
                    "application_receipt_ref"
                ],
            }:
                return None
            application_receipt = evidence.get(
                terminal["application_receipt_ref"]
            )
            if (
                not isinstance(application_receipt, dict)
                or application_receipt.get("application_id")
                != tombstone["application_id"]
                or application_receipt.get("policy_revision_id")
                != tombstone["policy_revision_id"]
                or application_receipt.get("recovery_ref")
                != tombstone["recovery_ref"]
                or evaluate_protected_policy_application(
                    application_receipt,
                    evidence,
                    current_recovery_ref=tombstone["recovery_ref"],
                )
                != terminal["terminal_application"]
            ):
                return None
            terminal_item = terminal_recovery_item(tombstone, evidence)
            terminal_recovery = (
                policy_recovery_head(terminal_item, evidence)
                if terminal_item is not None
                else None
            )
            if (
                terminal_recovery is None
                or terminal["reconciliation_receipt_ref"]
                != terminal_recovery.get("reconciliation_receipt_ref")
            ):
                return None
            if (
                terminal["reconciliation_receipt_ref"] is not None
                and not valid_terminal_reconciliation_receipt(
                    tombstone, evidence
                )
            ):
                return None
        records.append(tombstones)
        predecessor = record["predecessor_ref"]
        if predecessor is not None and not bounded_policy_scalar(predecessor):
            return None
        ref = predecessor
    return [
        tombstone
        for record_tombstones in reversed(records)
        for tombstone in record_tombstones
    ]


def retired_policy_chain_reaches(
    newest_ref: object,
    predecessor_ref: object,
    evidence: dict[str, dict],
) -> bool:
    if newest_ref == predecessor_ref:
        return True
    seen_refs = set()
    ref = newest_ref
    while ref is not None:
        if not bounded_policy_scalar(ref) or ref in seen_refs:
            return False
        seen_refs.add(ref)
        record = evidence.get(ref)
        if not isinstance(record, dict):
            return False
        ref = record.get("predecessor_ref")
        if ref == predecessor_ref:
            return True
    return False


def resolve_active_policy_applications(
    state: object, evidence: dict[str, dict]
) -> list[dict] | None:
    if not isinstance(state, dict) or set(state) != {
        "schema",
        "active_count",
        "active_inline",
        "active_index_ref",
        "retired_index_ref",
    }:
        return None
    if state["schema"] != "codex.protected_policy_application_state.v1":
        return None
    count = state["active_count"]
    if not exact_policy_count(count):
        return None
    if count <= 8:
        if state["active_index_ref"] is not None:
            return None
        active = state["active_inline"]
        if not isinstance(active, list) or len(active) != count:
            return None
    else:
        if state["active_inline"] != [] or not bounded_policy_scalar(
            state["active_index_ref"]
        ):
            return None
        index = evidence.get(state["active_index_ref"])
        if not isinstance(index, dict) or set(index) != {
            "schema",
            "active_count",
            "applications",
        }:
            return None
        if (
            index["schema"]
            != "codex.protected_policy_application_active_index.v1"
            or not exact_policy_count(index["active_count"])
            or index["active_count"] != count
        ):
            return None
        active = index["applications"]
        if not isinstance(active, list) or len(active) != count:
            return None
    return active if valid_policy_application_collection(active) else None


def valid_policy_application_state(
    state: object, evidence: dict[str, dict]
) -> bool:
    active = resolve_active_policy_applications(state, evidence)
    if active is None or not isinstance(state, dict):
        return False
    retired = resolve_retired_policy_applications(
        state["retired_index_ref"], evidence
    )
    if retired is None:
        return False
    if any(
        resolve_policy_recovery_chain(item, evidence) is None
        for item in active
    ):
        return False
    recoveries = [policy_recovery_head(item, evidence) for item in active]
    for item in retired:
        recovery = evidence.get(item["recovery_ref"])
        if (
            not valid_policy_recovery_record(
                recovery,
                item["application_id"],
                item["policy_revision_id"],
            )
        ):
            return False
        retired_item = {
            "schema": "codex.protected_policy_application_checkpoint.v2",
            "application_id": item["application_id"],
            "state": "terminal",
            "policy_revision_id": item["policy_revision_id"],
            "operation_policy_fingerprint": recovery.get(
                "operation_policy_fingerprint"
            ),
            "recovery_ref": item["recovery_ref"],
            "intent_operation_id": recovery.get("intent_operation_id"),
            "mutation_operation_id": recovery.get("mutation_operation_id"),
        }
        if (
            not valid_policy_application_entry(retired_item)
            or resolve_policy_recovery_chain(retired_item, evidence) is None
        ):
            return False
        recoveries.append(recovery)
    active_ids = [policy_application_identity(item) for item in active]
    retired_ids = [
        (item["application_id"], item["policy_revision_id"])
        for item in retired
    ]
    all_ids = active_ids + retired_ids
    recovery_refs = [item["recovery_ref"] for item in active + retired]
    if not (
        len({item[0] for item in all_ids}) == len(all_ids)
        and len({item[1] for item in all_ids}) == len(all_ids)
        and len(set(recovery_refs)) == len(recovery_refs)
    ):
        return False
    operation_keys = []
    for recovery in recoveries:
        namespace = recovery["operation_namespace_ref"]
        for field in ("intent_operation_id", "mutation_operation_id"):
            operation_id = recovery.get(field)
            if operation_id is not None:
                if not bounded_policy_scalar(operation_id):
                    return False
                operation_keys.append((namespace, operation_id))
    return len(set(operation_keys)) == len(operation_keys)


def valid_policy_reconciliation_transition(
    before_item: dict,
    after_item: dict,
    evidence: dict[str, dict],
) -> bool:
    after_recovery = policy_recovery_head(after_item, evidence)
    if after_recovery is None:
        return False
    reconciliation_ref = after_recovery.get("reconciliation_receipt_ref")
    reconciliation = evidence.get(reconciliation_ref)
    return reconciliation == {
        "schema": "codex.protected_policy_application_reconciliation.v1",
        "authority": "owning-system",
        "application_id": before_item["application_id"],
        "policy_revision_id": before_item["policy_revision_id"],
        "from_state": before_item["state"],
        "to_state": after_item["state"],
        "from_recovery_ref": before_item["recovery_ref"],
        "to_recovery_ref": after_item["recovery_ref"],
        "intent_operation_id": after_item["intent_operation_id"],
        "mutation_operation_id": after_item["mutation_operation_id"],
    }


def valid_terminal_reconciliation(
    before_item: dict,
    tombstone: dict,
    evidence: dict[str, dict],
) -> bool:
    terminal = evidence.get(tombstone["terminal_receipt_ref"])
    if not isinstance(terminal, dict):
        return False
    reconciliation_ref = terminal.get("reconciliation_receipt_ref")
    if not bounded_policy_scalar(reconciliation_ref):
        return False
    reconciliation = evidence.get(reconciliation_ref)
    recovery = evidence.get(tombstone["recovery_ref"])
    if not isinstance(recovery, dict):
        return False
    return (
        terminal.get("reconciliation_receipt_ref")
        == recovery.get("reconciliation_receipt_ref")
        and reconciliation
        == {
            "schema": (
                "codex.protected_policy_application_reconciliation.v1"
            ),
            "authority": "owning-system",
            "application_id": before_item["application_id"],
            "policy_revision_id": before_item["policy_revision_id"],
            "from_state": before_item["state"],
            "to_state": "terminal",
            "from_recovery_ref": before_item["recovery_ref"],
            "to_recovery_ref": tombstone["recovery_ref"],
            "intent_operation_id": recovery.get("intent_operation_id"),
            "mutation_operation_id": recovery.get("mutation_operation_id"),
        }
        and valid_terminal_reconciliation_receipt(tombstone, evidence)
    )


def terminal_recovery_item(
    tombstone: dict, evidence: dict[str, dict]
) -> dict | None:
    recovery = evidence.get(tombstone["recovery_ref"])
    if not isinstance(recovery, dict):
        return None
    item = {
        "schema": "codex.protected_policy_application_checkpoint.v2",
        "application_id": tombstone["application_id"],
        "state": "terminal",
        "policy_revision_id": tombstone["policy_revision_id"],
        "operation_policy_fingerprint": recovery.get(
            "operation_policy_fingerprint"
        ),
        "recovery_ref": tombstone["recovery_ref"],
        "intent_operation_id": recovery.get("intent_operation_id"),
        "mutation_operation_id": recovery.get("mutation_operation_id"),
    }
    return item if valid_policy_application_entry(item) else None


def valid_terminal_reconciliation_receipt(
    tombstone: dict, evidence: dict[str, dict]
) -> bool:
    terminal = evidence.get(tombstone["terminal_receipt_ref"])
    if not isinstance(terminal, dict):
        return False
    reconciliation_ref = terminal.get("reconciliation_receipt_ref")
    if not bounded_policy_scalar(reconciliation_ref):
        return False
    reconciliation = evidence.get(reconciliation_ref)
    if not isinstance(reconciliation, dict) or set(reconciliation) != {
        "schema",
        "authority",
        "application_id",
        "policy_revision_id",
        "from_state",
        "to_state",
        "from_recovery_ref",
        "to_recovery_ref",
        "intent_operation_id",
        "mutation_operation_id",
    }:
        return False
    if (
        reconciliation["schema"]
        != "codex.protected_policy_application_reconciliation.v1"
        or reconciliation["authority"] != "owning-system"
        or not all(
            bounded_policy_scalar(reconciliation[field])
            for field in (
                "application_id",
                "policy_revision_id",
                "from_state",
                "to_state",
                "from_recovery_ref",
                "to_recovery_ref",
                "intent_operation_id",
                "mutation_operation_id",
            )
        )
        or reconciliation["application_id"] != tombstone["application_id"]
        or reconciliation["policy_revision_id"]
        != tombstone["policy_revision_id"]
        or not bounded_policy_enum(
            reconciliation["from_state"],
            UNKNOWN_POLICY_APPLICATION_STATES,
        )
        or reconciliation["to_state"] != "terminal"
        or reconciliation["to_recovery_ref"] != tombstone["recovery_ref"]
    ):
        return False
    from_recovery = evidence.get(reconciliation["from_recovery_ref"])
    before_item = {
        "schema": "codex.protected_policy_application_checkpoint.v2",
        "application_id": tombstone["application_id"],
        "state": reconciliation["from_state"],
        "policy_revision_id": tombstone["policy_revision_id"],
        "operation_policy_fingerprint": (
            from_recovery.get("operation_policy_fingerprint")
            if isinstance(from_recovery, dict)
            else None
        ),
        "recovery_ref": reconciliation["from_recovery_ref"],
        "intent_operation_id": (
            from_recovery.get("intent_operation_id")
            if isinstance(from_recovery, dict)
            else None
        ),
        "mutation_operation_id": (
            from_recovery.get("mutation_operation_id")
            if isinstance(from_recovery, dict)
            else None
        ),
    }
    after_item = terminal_recovery_item(tombstone, evidence)
    after_recovery = (
        policy_recovery_head(after_item, evidence)
        if after_item is not None
        else None
    )
    return (
        valid_policy_application_entry(before_item)
        and after_item is not None
        and after_recovery is not None
        and terminal.get("reconciliation_receipt_ref")
        == after_recovery.get("reconciliation_receipt_ref")
        and reconciliation["intent_operation_id"]
        == after_item["intent_operation_id"]
        and reconciliation["mutation_operation_id"]
        == after_item["mutation_operation_id"]
        and policy_recovery_appends_exact_successor(
            before_item, after_item, evidence
        )
    )


def valid_policy_application_transition(
    before: object, after: object, evidence: dict[str, dict]
) -> bool:
    if not valid_policy_application_state(
        before, evidence
    ) or not valid_policy_application_state(after, evidence):
        return False
    before_active = resolve_active_policy_applications(before, evidence)
    after_active = resolve_active_policy_applications(after, evidence)
    before_retired = resolve_retired_policy_applications(
        before["retired_index_ref"], evidence
    )
    after_retired = resolve_retired_policy_applications(
        after["retired_index_ref"], evidence
    )
    if any(
        value is None
        for value in (
            before_active,
            after_active,
            before_retired,
            after_retired,
        )
    ):
        return False
    if not retired_policy_chain_reaches(
        after["retired_index_ref"],
        before["retired_index_ref"],
        evidence,
    ):
        return False
    before_active_ids = [
        policy_application_identity(item) for item in before_active
    ]
    after_active_ids = [
        policy_application_identity(item) for item in after_active
    ]
    before_retired_records = [
        (
            item["application_id"],
            item["policy_revision_id"],
            item["recovery_ref"],
            item["terminal_receipt_ref"],
        )
        for item in before_retired
    ]
    after_retired_records = [
        (
            item["application_id"],
            item["policy_revision_id"],
            item["recovery_ref"],
            item["terminal_receipt_ref"],
        )
        for item in after_retired
    ]
    if (
        after_retired_records[: len(before_retired_records)]
        != before_retired_records
    ):
        return False
    before_retired_ids = {
        (item["application_id"], item["policy_revision_id"])
        for item in before_retired
    }
    after_retired_set = {
        (item["application_id"], item["policy_revision_id"])
        for item in after_retired
    }
    before_active_set = set(before_active_ids)
    new_tombstone_ids = {
        (item["application_id"], item["policy_revision_id"])
        for item in after_retired[len(before_retired) :]
    }
    if not new_tombstone_ids.issubset(before_active_set):
        return False
    before_by_id = {
        policy_application_identity(item): item for item in before_active
    }
    for tombstone in after_retired[len(before_retired) :]:
        identity = (
            tombstone["application_id"],
            tombstone["policy_revision_id"],
        )
        before_item = before_by_id[identity]
        terminal_item = terminal_recovery_item(tombstone, evidence)
        if terminal_item is None or not policy_recovery_chain_reaches(
            before_item, terminal_item, evidence
        ):
            return False
        if (
            before_item["state"] != terminal_item["state"]
            and not policy_recovery_appends_exact_successor(
                before_item, terminal_item, evidence
            )
        ):
            return False
        if (
            before_item["state"] in UNKNOWN_POLICY_APPLICATION_STATES
            and not valid_terminal_reconciliation(
                before_item, tombstone, evidence
            )
        ):
            return False
    survivors = [
        identity
        for identity in before_active_ids
        if identity not in after_retired_set
    ]
    if after_active_ids[: len(survivors)] != survivors:
        return False
    if any(
        identity not in set(after_active_ids) | after_retired_set
        for identity in before_active_ids
    ):
        return False
    if any(identity in after_active_ids for identity in before_retired_ids):
        return False
    if not all(
        identity not in set(before_active_ids) | set(before_retired_ids)
        for identity in after_active_ids[len(survivors) :]
    ):
        return False
    after_by_id = {
        policy_application_identity(item): item for item in after_active
    }
    for identity in after_active_ids[len(survivors) :]:
        item = after_by_id[identity]
        recovery = policy_recovery_head(item, evidence)
        if (
            item["state"] != "revision-captured"
            or recovery is None
            or any(
            recovery.get(field) is not None
            for field in ("predecessor_ref", "reconciliation_receipt_ref")
            )
        ):
            return False
    for identity in survivors:
        before_item = before_by_id[identity]
        after_item = after_by_id[identity]
        if not bounded_policy_enum(
            after_item["state"],
            POLICY_APPLICATION_TRANSITIONS[before_item["state"]],
        ):
            return False
        if not policy_recovery_chain_reaches(
            before_item, after_item, evidence
        ):
            return False
        before_chain = resolve_policy_recovery_chain(before_item, evidence)
        after_chain = resolve_policy_recovery_chain(after_item, evidence)
        if before_chain is None or after_chain is None:
            return False
        appended_recoveries = after_chain[len(before_chain) :]
        state_changed = after_item["state"] != before_item["state"]
        if state_changed and len(appended_recoveries) != 1:
            return False
        required_reconciliation = (
            before_item["state"] in UNKNOWN_POLICY_APPLICATION_STATES
            and state_changed
        )
        if (
            required_reconciliation
            and not valid_policy_reconciliation_transition(
                before_item, after_item, evidence
            )
        ):
            return False
    return True


def empty_policy_application_state() -> dict:
    return {
        "schema": "codex.protected_policy_application_state.v1",
        "active_count": 0,
        "active_inline": [],
        "active_index_ref": None,
        "retired_index_ref": None,
    }


def checkpoint_recovery_projection(
    item: dict,
    *,
    inherited_recovery: dict | None = None,
    predecessor_ref: str | None = None,
    reconciliation_receipt_ref: str | None = None,
    operation_namespace_ref: str | None = None,
) -> dict:
    inherited = inherited_recovery or {}
    return {
        "schema": "codex.protected_policy_application_recovery.v2",
        "application_id": item["application_id"],
        "policy_revision_id": item["policy_revision_id"],
        "checkpoint_state": item["state"],
        "receiver_thread_id": inherited.get(
            "receiver_thread_id",
            f"synthetic-receiver-{item['application_id']}",
        ),
        "operation_policy_fingerprint": item[
            "operation_policy_fingerprint"
        ],
        "store_schema": inherited.get(
            "store_schema",
            "codex.authorized_immutable_intent_store.v1",
        ),
        "store_ref": inherited.get(
            "store_ref", f"synthetic-store-{item['application_id']}"
        ),
        "store_authorization_ref": inherited.get(
            "store_authorization_ref",
            f"synthetic-store-authorization-{item['application_id']}",
        ),
        "intent_ref": inherited.get(
            "intent_ref", f"synthetic-intent-{item['application_id']}"
        ),
        "destination_ref": inherited.get(
            "destination_ref",
            f"synthetic-destination-{item['application_id']}",
        ),
        "subject_ref": inherited.get(
            "subject_ref", f"synthetic-subject-{item['application_id']}"
        ),
        "intent_operation_id": item["intent_operation_id"],
        "mutation_operation_id": item["mutation_operation_id"],
        "operation_namespace_ref": (
            operation_namespace_ref
            or inherited.get("operation_namespace_ref")
            or "synthetic-operation-namespace"
        ),
        "migration_ref": inherited.get("migration_ref"),
        "migration_source_checkpoint_ref": inherited.get(
            "migration_source_checkpoint_ref"
        ),
        "migration_checkpoint_fingerprint": inherited.get(
            "migration_checkpoint_fingerprint"
        ),
        "migration_target_thread_id": inherited.get(
            "migration_target_thread_id"
        ),
        "migration_target_host_id": inherited.get(
            "migration_target_host_id"
        ),
        "predecessor_ref": predecessor_ref,
        "reconciliation_receipt_ref": reconciliation_receipt_ref,
    }


def checkpoint_fingerprint(checkpoint: dict) -> str | None:
    try:
        payload = json.dumps(
            checkpoint,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError):
        return None
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def migrate_v1_policy_application_state(
    checkpoint: dict,
    evidence: dict[str, dict],
    *,
    target_thread_id: str,
    target_host_id: str,
    migration_ref: str | None = None,
    pre_feature_proof_ref: str | None = None,
) -> dict | None:
    if (
        not isinstance(checkpoint, dict)
        or not isinstance(evidence, dict)
        or not bounded_policy_scalar(target_thread_id)
        or not bounded_policy_scalar(target_host_id)
        or (
            migration_ref is not None
            and not valid_sha256_fingerprint(migration_ref)
        )
        or (
            pre_feature_proof_ref is not None
            and not bounded_policy_scalar(pre_feature_proof_ref)
        )
        or checkpoint.get("schema") != "codex.thread_supervision.v1"
        or not isinstance(checkpoint.get("targets"), list)
    ):
        return None
    targets = [
        item
        for item in checkpoint["targets"]
        if isinstance(item, dict)
        and item.get("thread_id") == target_thread_id
        and item.get("host_id") == target_host_id
    ]
    if len(targets) != 1:
        return None
    target = targets[0]
    if "protected_policy_application_state" in target:
        return None
    fingerprint = checkpoint_fingerprint(checkpoint)
    if fingerprint is None:
        return None
    if "protected_policy_application" not in target:
        if not bounded_policy_scalar(pre_feature_proof_ref):
            return None
        proof = evidence.get(pre_feature_proof_ref)
        if not isinstance(proof, dict):
            return None
        source_ref = proof.get("source_contract_revision_ref")
        inventory_ref = proof.get("evidence_inventory_ref")
        if not bounded_policy_scalar(
            source_ref
        ) or not bounded_policy_scalar(inventory_ref):
            return None
        source = evidence.get(source_ref)
        inventory = evidence.get(inventory_ref)
        if (
            not exact_policy_count(
                proof.get("protected_policy_application_evidence_count")
            )
            or proof.get("protected_policy_application_evidence_count") != 0
            or proof
            != {
                "schema": "codex.thread_supervision_pre_feature_proof.v1",
                "checkpoint_fingerprint": fingerprint,
                "target_thread_id": target_thread_id,
                "target_host_id": target_host_id,
                "source_contract_revision_ref": source_ref,
                "evidence_inventory_ref": inventory_ref,
                "protected_policy_application_evidence_count": 0,
            }
        ):
            return None
        if source != {
            "schema": "codex.thread_supervision_source_contract.v1",
            "checkpoint_fingerprint": fingerprint,
            "contract_revision": "known-pre-feature-v1",
            "protected_policy_feature": "absent",
        }:
            return None
        if not isinstance(inventory, dict):
            return None
        if inventory != {
            "schema": "codex.thread_supervision_evidence_inventory.v1",
            "checkpoint_fingerprint": fingerprint,
            "target_thread_id": target_thread_id,
            "target_host_id": target_host_id,
            "cutoff": inventory.get("cutoff"),
            "application_recovery_refs": [],
        } or not bounded_policy_scalar(inventory.get("cutoff")):
            return None
        return empty_policy_application_state()
    legacy = target["protected_policy_application"]
    if legacy is None:
        return empty_policy_application_state()
    if not valid_sha256_fingerprint(migration_ref):
        return None
    if not isinstance(legacy, dict) or set(legacy) != {
        "schema",
        "state",
        "policy_revision_id",
        "operation_policy_fingerprint",
        "recovery_ref",
        "intent_operation_id",
        "mutation_operation_id",
    }:
        return None
    if (
        legacy["schema"] != "codex.protected_policy_application_checkpoint.v1"
        or not bounded_policy_enum(
            legacy["state"], POLICY_APPLICATION_STATES
        )
    ):
        return None
    for field in (
        "policy_revision_id",
        "recovery_ref",
    ):
        if not bounded_policy_scalar(legacy[field]):
            return None
    for field in (
        "operation_policy_fingerprint",
        "intent_operation_id",
        "mutation_operation_id",
    ):
        if legacy[field] is not None and not bounded_policy_scalar(
            legacy[field]
        ):
            return None
    legacy_recovery = evidence.get(legacy["recovery_ref"])
    if (
        not isinstance(legacy_recovery, dict)
        or set(legacy_recovery)
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
        or legacy_recovery["schema"]
        != "codex.protected_policy_application_recovery.v1"
        or any(
            legacy_recovery[field] != legacy[field]
            for field in (
                "policy_revision_id",
                "operation_policy_fingerprint",
                "intent_operation_id",
                "mutation_operation_id",
            )
        )
    ):
        return None
    migration = evidence.get(migration_ref)
    if not isinstance(migration, dict) or set(migration) != {
        "schema",
        "source_checkpoint_schema",
        "checkpoint_fingerprint",
        "source_checkpoint_ref",
        "target_thread_id",
        "target_host_id",
        "legacy_recovery_ref",
        "migrated_recovery_ref",
        "operation_namespace_ref",
        "application_id",
        "policy_revision_id",
        "intent_operation_id",
        "mutation_operation_id",
    }:
        return None
    if not all(
        bounded_policy_scalar(migration[field])
        for field in (
            "checkpoint_fingerprint",
            "source_checkpoint_ref",
            "target_thread_id",
            "target_host_id",
            "legacy_recovery_ref",
            "migrated_recovery_ref",
            "operation_namespace_ref",
            "application_id",
            "policy_revision_id",
        )
    ) or any(
        migration[field] is not None
        and not bounded_policy_scalar(migration[field])
        for field in ("intent_operation_id", "mutation_operation_id")
    ):
        return None
    expected = {
        "schema": "codex.protected_policy_application_migration.v1",
        "source_checkpoint_schema": "codex.thread_supervision.v1",
        "checkpoint_fingerprint": fingerprint,
        "source_checkpoint_ref": migration["source_checkpoint_ref"],
        "target_thread_id": target_thread_id,
        "target_host_id": target_host_id,
        "legacy_recovery_ref": legacy["recovery_ref"],
        "migrated_recovery_ref": migration["migrated_recovery_ref"],
        "operation_namespace_ref": migration["operation_namespace_ref"],
        "application_id": migration["application_id"],
        "policy_revision_id": legacy["policy_revision_id"],
        "intent_operation_id": legacy["intent_operation_id"],
        "mutation_operation_id": legacy["mutation_operation_id"],
    }
    if (
        migration != expected
        or checkpoint_fingerprint(migration) != migration_ref
        or evidence.get(migration["source_checkpoint_ref"]) != checkpoint
    ):
        return None
    migrated_recovery = evidence.get(migration["migrated_recovery_ref"])
    expected_migrated_recovery = {
        **legacy_recovery,
        "schema": "codex.protected_policy_application_recovery.v2",
        "application_id": migration["application_id"],
        "checkpoint_state": legacy["state"],
        "operation_namespace_ref": migration["operation_namespace_ref"],
        "migration_ref": migration_ref,
        "migration_source_checkpoint_ref": migration[
            "source_checkpoint_ref"
        ],
        "migration_checkpoint_fingerprint": migration[
            "checkpoint_fingerprint"
        ],
        "migration_target_thread_id": migration["target_thread_id"],
        "migration_target_host_id": migration["target_host_id"],
        "predecessor_ref": None,
        "reconciliation_receipt_ref": None,
    }
    if migrated_recovery != expected_migrated_recovery:
        return None
    entry = {
        "schema": "codex.protected_policy_application_checkpoint.v2",
        "application_id": migration["application_id"],
        "state": legacy["state"],
        "policy_revision_id": legacy["policy_revision_id"],
        "operation_policy_fingerprint": legacy[
            "operation_policy_fingerprint"
        ],
        "recovery_ref": migration["migrated_recovery_ref"],
        "intent_operation_id": legacy["intent_operation_id"],
        "mutation_operation_id": legacy["mutation_operation_id"],
    }
    state = empty_policy_application_state()
    state.update({"active_count": 1, "active_inline": [entry]})
    return state if valid_policy_application_state(state, evidence) else None


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


def valid_fingerprint_field_ref(value: object) -> bool:
    return bounded_policy_scalar(value) and "\x00" not in value


def canonical_operation_policy_json(policy: dict) -> bytes:
    if (
        not isinstance(policy, dict)
        or set(policy)
        != {
            "destination_ref",
            "subject_ref",
            "operation",
            "eligibility_cutoff",
            "mandatory_fields",
        }
        or policy["operation"]
        not in {"create", "update", "transition", "other-authorized"}
        or any(
            not bounded_policy_scalar(policy[field])
            for field in (
                "destination_ref",
                "subject_ref",
                "eligibility_cutoff",
            )
        )
        or not isinstance(policy["mandatory_fields"], list)
        or not policy["mandatory_fields"]
    ):
        raise ValueError("operation policy is not schema-valid")
    seen_fields = set()
    for item in policy["mandatory_fields"]:
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "field_ref",
                "expected_value_fingerprint",
                "expectation_evidence_ref",
            }
            or not valid_fingerprint_field_ref(item["field_ref"])
            or item["field_ref"] in seen_fields
            or not valid_keyed_fingerprint(
                item["expected_value_fingerprint"]
            )
            or not bounded_policy_scalar(
                item["expectation_evidence_ref"]
            )
        ):
            raise ValueError("operation policy is not schema-valid")
        seen_fields.add(item["field_ref"])
    return json.dumps(
        policy,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def operation_policy_fingerprint(policy: dict) -> str:
    payload = canonical_operation_policy_json(policy)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


TRUSTED_HMAC_DOMAIN = b"codex.protected-policy-field.v1"
TRUSTED_HMAC_KEY_REF = b"test-only-authorized-key-ref-v1"
TRUSTED_HMAC_KEY_MATERIAL = b"test-only-authorized-hmac-key-material-v1"
TRUSTED_POLICY_SUBJECT_REF = "opaque-action-intent-or-object-ref"
TRUSTED_POLICY_FIELD_REF = "opaque-domain-field-ref"
TRUSTED_POLICY_NORMALIZED_VALUE = b"synthetic-normalized-field-value"


def keyed_fingerprint_message(
    field_ref: str,
    normalized_value: bytes,
) -> bytes:
    if not valid_fingerprint_field_ref(field_ref):
        raise ValueError("fingerprint field ref is not canonical")
    return (
        TRUSTED_HMAC_DOMAIN
        + b"\x00"
        + field_ref.encode("utf-8")
        + b"\x00"
        + normalized_value
    )


def keyed_fingerprint_for(
    *,
    field_ref: str,
    normalized_value: bytes,
    key_ref: bytes = TRUSTED_HMAC_KEY_REF,
    key_material: bytes = TRUSTED_HMAC_KEY_MATERIAL,
) -> dict[str, str]:
    digest = hmac.new(
        key_material,
        keyed_fingerprint_message(field_ref, normalized_value),
        hashlib.sha256,
    ).hexdigest()
    return {
        "scheme": "hmac-sha256",
        "key_ref_fingerprint": (
            "sha256:" + hashlib.sha256(key_ref).hexdigest()
        ),
        "digest": digest,
    }


def trusted_keyed_fingerprint() -> dict[str, str]:
    return keyed_fingerprint_for(
        field_ref=TRUSTED_POLICY_FIELD_REF,
        normalized_value=TRUSTED_POLICY_NORMALIZED_VALUE,
    )


def trusted_fingerprint_provenance(
    *,
    purpose: str,
    evidence_ref: str,
    subject_ref: str,
    field_ref: str,
    fingerprint: object,
    object_ref: str | None = None,
    mutation_operation_id: str | None = None,
    readback_cutoff: str | None = None,
    status: str | None = None,
) -> bool:
    if not valid_fingerprint_field_ref(field_ref):
        return False
    if status is None:
        status = "expected" if purpose == "expectation" else "matched"
    trusted_sources = {
        "opaque-keyed-expectation-proof-ref": {
            "purpose": "expectation",
            "status": "expected",
            "subject_ref": TRUSTED_POLICY_SUBJECT_REF,
            "field_ref": TRUSTED_POLICY_FIELD_REF,
            "object_ref": None,
            "mutation_operation_id": None,
            "readback_cutoff": None,
            "normalized_value": TRUSTED_POLICY_NORMALIZED_VALUE,
        },
        "opaque-owning-system-readback-ref": {
            "purpose": "observation",
            "status": "matched",
            "subject_ref": TRUSTED_POLICY_SUBJECT_REF,
            "field_ref": TRUSTED_POLICY_FIELD_REF,
            "object_ref": "opaque-object-id",
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "readback_cutoff": "opaque-post-mutation-cutoff",
            "normalized_value": TRUSTED_POLICY_NORMALIZED_VALUE,
        },
        "opaque-owning-system-different-readback-ref": {
            "purpose": "observation",
            "status": "mismatched",
            "subject_ref": TRUSTED_POLICY_SUBJECT_REF,
            "field_ref": TRUSTED_POLICY_FIELD_REF,
            "object_ref": "opaque-object-id",
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "readback_cutoff": "opaque-post-mutation-cutoff",
            "normalized_value": b"different-synthetic-normalized-field-value",
        },
        "opaque-owning-system-missing-readback-ref": {
            "purpose": "observation",
            "status": "missing",
            "subject_ref": TRUSTED_POLICY_SUBJECT_REF,
            "field_ref": TRUSTED_POLICY_FIELD_REF,
            "object_ref": "opaque-object-id",
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "readback_cutoff": "opaque-post-mutation-cutoff",
            "normalized_value": None,
        },
        "opaque-owning-system-unavailable-readback-ref": {
            "purpose": "observation",
            "status": "unavailable",
            "subject_ref": TRUSTED_POLICY_SUBJECT_REF,
            "field_ref": TRUSTED_POLICY_FIELD_REF,
            "object_ref": "opaque-object-id",
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "readback_cutoff": "opaque-post-mutation-cutoff",
            "normalized_value": None,
        },
    }
    source = trusted_sources.get(evidence_ref)
    if not isinstance(source, dict):
        return False
    normalized_value = source.get("normalized_value")
    if normalized_value is not None and not isinstance(
        normalized_value, bytes
    ):
        return False
    source_context = {
        key: value
        for key, value in source.items()
        if key != "normalized_value"
    }
    if source_context != {
        "purpose": purpose,
        "status": status,
        "subject_ref": subject_ref,
        "field_ref": field_ref,
        "object_ref": object_ref,
        "mutation_operation_id": mutation_operation_id,
        "readback_cutoff": readback_cutoff,
    }:
        return False
    if normalized_value is None:
        return fingerprint is None
    if not valid_keyed_fingerprint(fingerprint):
        return False
    expected = keyed_fingerprint_for(
        field_ref=field_ref,
        normalized_value=normalized_value,
    )
    return hmac.compare_digest(
        fingerprint["key_ref_fingerprint"],
        expected["key_ref_fingerprint"],
    ) and hmac.compare_digest(fingerprint["digest"], expected["digest"])


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
    revision_recovery_ref = (
        "opaque-protected-policy-application-revision-recovery-ref"
    )
    adoption_recovery_ref = (
        "opaque-protected-policy-application-adoption-recovery-ref"
    )
    intent_pending_recovery_ref = (
        "opaque-protected-policy-application-intent-pending-recovery-ref"
    )
    intent_unknown_recovery_ref = (
        "opaque-protected-policy-application-intent-unknown-recovery-ref"
    )
    mutation_pending_recovery_ref = (
        "opaque-protected-policy-application-mutation-pending-recovery-ref"
    )
    readback_pending_recovery_ref = (
        "opaque-protected-policy-application-readback-pending-recovery-ref"
    )
    root_recovery_ref = "opaque-protected-policy-application-recovery-ref"
    terminal_recovery_ref = (
        "opaque-protected-policy-application-terminal-recovery-ref"
    )
    terminal_reconciliation_ref = (
        "opaque-protected-policy-application-terminal-reconciliation-ref"
    )
    revision_recovery = {
        "schema": "codex.protected_policy_application_recovery.v2",
        "application_id": "stable-opaque-application-id",
        "policy_revision_id": "opaque-user-authorized-revision",
        "checkpoint_state": "revision-captured",
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
        "intent_operation_id": "opaque-preallocated-intent-operation-id",
        "mutation_operation_id": (
            "opaque-preallocated-mutation-operation-id"
        ),
        "operation_namespace_ref": (
            "opaque-owning-system-operation-namespace"
        ),
        "migration_ref": None,
        "migration_source_checkpoint_ref": None,
        "migration_checkpoint_fingerprint": None,
        "migration_target_thread_id": None,
        "migration_target_host_id": None,
        "predecessor_ref": None,
        "reconciliation_receipt_ref": None,
    }
    adoption_recovery = {
        **revision_recovery,
        "checkpoint_state": "adoption-pending",
        "predecessor_ref": revision_recovery_ref,
    }
    intent_pending_recovery = {
        **adoption_recovery,
        "checkpoint_state": "intent-pending",
        "predecessor_ref": adoption_recovery_ref,
    }
    intent_unknown_recovery = {
        **intent_pending_recovery,
        "checkpoint_state": "intent-outcome-unknown",
        "predecessor_ref": intent_pending_recovery_ref,
    }
    mutation_pending_recovery = {
        **intent_pending_recovery,
        "checkpoint_state": "mutation-pending",
        "predecessor_ref": intent_pending_recovery_ref,
    }
    mutation_unknown_recovery = {
        **mutation_pending_recovery,
        "checkpoint_state": "mutation-outcome-unknown",
        "predecessor_ref": mutation_pending_recovery_ref,
    }
    readback_pending_recovery = {
        **mutation_pending_recovery,
        "checkpoint_state": "readback-pending",
        "predecessor_ref": mutation_pending_recovery_ref,
    }
    return {
        revision_recovery_ref: revision_recovery,
        adoption_recovery_ref: adoption_recovery,
        intent_pending_recovery_ref: intent_pending_recovery,
        intent_unknown_recovery_ref: intent_unknown_recovery,
        mutation_pending_recovery_ref: mutation_pending_recovery,
        readback_pending_recovery_ref: readback_pending_recovery,
        root_recovery_ref: mutation_unknown_recovery,
        terminal_recovery_ref: {
            **mutation_unknown_recovery,
            "checkpoint_state": "terminal",
            "predecessor_ref": root_recovery_ref,
            "reconciliation_receipt_ref": terminal_reconciliation_ref,
        },
        terminal_reconciliation_ref: {
            "schema": (
                "codex.protected_policy_application_reconciliation.v1"
            ),
            "authority": "owning-system",
            "application_id": "stable-opaque-application-id",
            "policy_revision_id": "opaque-user-authorized-revision",
            "from_state": "mutation-outcome-unknown",
            "to_state": "terminal",
            "from_recovery_ref": root_recovery_ref,
            "to_recovery_ref": terminal_recovery_ref,
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
            "result_object_ref": "opaque-object-id",
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
        "opaque-owning-system-unavailable-readback-ref": {
            "schema": "codex.field_observation_evidence.v1",
            "object_ref": "opaque-object-id",
            "mutation_operation_id": (
                "opaque-preallocated-mutation-operation-id"
            ),
            "readback_cutoff": "opaque-post-mutation-cutoff",
            "field_ref": "opaque-domain-field-ref",
            "value_fingerprint": None,
            "status": "unavailable",
        },
    }


def trusted_policy_recovery_store() -> dict[str, dict]:
    evidence = trusted_policy_evidence()
    return {
        recovery_ref: copy.deepcopy(evidence[recovery_ref])
        for recovery_ref in (
            "opaque-protected-policy-application-revision-recovery-ref",
            "opaque-protected-policy-application-adoption-recovery-ref",
            "opaque-protected-policy-application-intent-pending-recovery-ref",
            "opaque-protected-policy-application-intent-unknown-recovery-ref",
            "opaque-protected-policy-application-mutation-pending-recovery-ref",
            (
                "opaque-protected-policy-application-"
                "readback-pending-recovery-ref"
            ),
            "opaque-protected-policy-application-recovery-ref",
            "opaque-protected-policy-application-terminal-recovery-ref",
            (
                "opaque-protected-policy-application-"
                "terminal-reconciliation-ref"
            ),
        )
    }


def _compute_protected_policy_application(
    receipt: dict,
    evidence: dict[str, dict] | None = None,
    *,
    current_recovery_ref: object = None,
) -> str:
    evidence = trusted_policy_evidence() if evidence is None else evidence
    try:
        if set(receipt) != {
            "schema",
            "application_id",
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
        if receipt["schema"] != "codex.protected_policy_application.v2":
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
            "application_id",
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
        if (
            not bounded_policy_scalar(current_recovery_ref)
            or receipt["recovery_ref"] != current_recovery_ref
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
                not valid_fingerprint_field_ref(field_ref)
                or not valid_keyed_fingerprint(expected)
                or not bounded_policy_scalar(item["expectation_evidence_ref"])
                or field_ref in expected_by_field
            ):
                return "invalid"
            expected_by_field[field_ref] = expected
        computed_operation_policy_fingerprint = operation_policy_fingerprint(
            policy
        )
        recovery_store = trusted_policy_recovery_store()
        recovery = recovery_store.get(receipt["recovery_ref"])
        if (
            not isinstance(recovery, dict)
            or set(recovery) != POLICY_RECOVERY_FIELDS
            or recovery["schema"]
            != "codex.protected_policy_application_recovery.v2"
            or not valid_policy_recovery_record(
                recovery,
                receipt["application_id"],
                receipt["policy_revision_id"],
            )
        ):
            return "invalid"
        for field in (
            "application_id",
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
            "operation_namespace_ref",
        ):
            if not bounded_policy_scalar(recovery[field]):
                return "invalid"
        for field in ("predecessor_ref", "reconciliation_receipt_ref"):
            if recovery[field] is not None and not bounded_policy_scalar(
                recovery[field]
            ):
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
        if (
            recovery["application_id"] != receipt["application_id"]
            or recovery["policy_revision_id"] != receipt["policy_revision_id"]
            or recovery["receiver_thread_id"]
            != receipt["receiver_thread_id"]
            or recovery["operation_policy_fingerprint"]
            != receipt["operation_policy_fingerprint"]
            or receipt["operation_policy_fingerprint"]
            != computed_operation_policy_fingerprint
            or recovery["destination_ref"] != policy["destination_ref"]
            or recovery["subject_ref"] != policy["subject_ref"]
        ):
            return "invalid"
        recovery_item = {
            "schema": "codex.protected_policy_application_checkpoint.v2",
            "application_id": receipt["application_id"],
            "state": recovery["checkpoint_state"],
            "policy_revision_id": receipt["policy_revision_id"],
            "operation_policy_fingerprint": receipt[
                "operation_policy_fingerprint"
            ],
            "recovery_ref": receipt["recovery_ref"],
            "intent_operation_id": recovery["intent_operation_id"],
            "mutation_operation_id": recovery["mutation_operation_id"],
        }
        if (
            not valid_policy_application_entry(recovery_item)
            or resolve_policy_recovery_chain(
                recovery_item, recovery_store
            )
            is None
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
            "result_object_ref",
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
            "result_object_ref",
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
            if not valid_fingerprint_field_ref(field_ref):
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

        readback_is_incomplete_or_unavailable = (
            readback["state"] != "complete"
            or any(
                item["status"] == "unavailable"
                for item in observed_by_field.values()
            )
        )
        expected_recovery_state = (
            "intent-outcome-unknown"
            if intent_status == "outcome-unknown"
            else (
                "mutation-outcome-unknown"
                if mutation_state == "outcome-unknown"
                else (
                    "readback-pending"
                    if mutation_state == "committed"
                    and readback_is_incomplete_or_unavailable
                    else "terminal"
                )
            )
        )
        if recovery["checkpoint_state"] != expected_recovery_state:
            return "invalid"

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
            and mutation["destination_ref"] == recovery["destination_ref"]
            and mutation["subject_ref"] == recovery["subject_ref"]
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
            "result_object_ref": mutation["result_object_ref"],
            "prewrite_intent_operation_id": recovery[
                "intent_operation_id"
            ],
            "prewrite_intent_ref": recovery["intent_ref"],
            "cutoff": mutation["cutoff"],
        }
        mutation_receipt_is_trusted = (
            bounded_policy_scalar(mutation["receipt_ref"])
            and bounded_policy_scalar(mutation["result_object_ref"])
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
                    "result_object_ref",
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
        readback_is_canonically_unavailable = (
            readback["state"] == "unavailable"
            and readback["mutation_operation_id"] == mutation["operation_id"]
            and readback["mutation_receipt_ref"] == mutation["receipt_ref"]
            and all(
                readback[field] is None
                for field in (
                    "object_ref",
                    "cutoff",
                    "relation",
                    "ordering_evidence_ref",
                )
            )
            and readback["field_results"] == []
        )
        if (
            readback["state"] == "not-run"
            and not readback_is_cleanly_not_run
        ) or (
            readback["state"] == "unavailable"
            and not readback_is_canonically_unavailable
        ):
            return "invalid"
        intent_is_cleanly_unwritten = (
            intent_status in {"not-created", "capability-unavailable"}
            and all(
                intent[field] is None
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
                )
            )
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
        if mutation_state == "not-attempted" and not (
            mutation_is_cleanly_not_attempted
            and readback_is_cleanly_not_run
        ):
            return "invalid"
        if adoption_status != "adopted":
            if intent_status == "created":
                return "policy-drift"
            if (
                intent_is_cleanly_unwritten
                and mutation_is_cleanly_not_attempted
                and readback_is_cleanly_not_run
            ):
                return "blocked"
            return "invalid" if mutation_state == "not-attempted" else "policy-drift"
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
            if (
                intent_is_cleanly_unwritten
                and mutation_is_cleanly_not_attempted
                and readback_is_cleanly_not_run
            ):
                return "blocked"
            return "invalid" if mutation_state == "not-attempted" else "policy-drift"

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

        if (
            mutation_state == "committed"
            and readback["state"] != "complete"
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

        if mutation_state == "not-attempted":
            return (
                "blocked"
                if mutation_is_cleanly_not_attempted
                and readback_is_cleanly_not_run
                else "invalid"
            )
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
            return "invalid"
        if not mutation_receipt_is_trusted:
            return "invalid"

        if not all(
            bounded_policy_scalar(readback[field])
            for field in (
                "object_ref",
                "cutoff",
                "mutation_operation_id",
                "mutation_receipt_ref",
                "relation",
                "ordering_evidence_ref",
            )
        ):
            return "policy-drift"
        if readback["object_ref"] != mutation["result_object_ref"]:
            return "policy-drift"
        if (
            readback["mutation_operation_id"] != mutation["operation_id"]
            or readback["mutation_receipt_ref"] != mutation["receipt_ref"]
        ):
            return "policy-drift"
        if readback["relation"] != "after-mutation":
            return "policy-drift"
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
        readback_has_unavailable_field = False
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
                or not trusted_fingerprint_provenance(
                    purpose="expectation",
                    evidence_ref=policy_item["expectation_evidence_ref"],
                    subject_ref=policy["subject_ref"],
                    field_ref=field_ref,
                    fingerprint=expected_by_field[field_ref],
                )
            ):
                return "invalid"
            if not bounded_policy_scalar(result["evidence_ref"]):
                return "invalid"
            observed = result["observed_value_fingerprint"]
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
                or not trusted_fingerprint_provenance(
                    purpose="observation",
                    evidence_ref=result["evidence_ref"],
                    subject_ref=policy["subject_ref"],
                    field_ref=field_ref,
                    fingerprint=observed,
                    object_ref=readback["object_ref"],
                    mutation_operation_id=mutation["operation_id"],
                    readback_cutoff=readback["cutoff"],
                    status=result["status"],
                )
            ):
                return "invalid"
            if result["status"] == "unavailable":
                readback_has_unavailable_field = True
                continue
            if result["status"] != "matched":
                return "policy-drift"
            if observed != expected_by_field[field_ref]:
                return "policy-drift"
        if readback_has_unavailable_field:
            return "reconciliation-required"
        return "applied"
    except (AttributeError, KeyError, TypeError, ValueError):
        return "invalid"


def evaluate_protected_policy_application(
    receipt: dict,
    evidence: dict[str, dict] | None = None,
    *,
    current_recovery_ref: object = None,
) -> str:
    computed = _compute_protected_policy_application(
        receipt,
        evidence,
        current_recovery_ref=current_recovery_ref,
    )
    if computed == "invalid":
        return "invalid"
    try:
        return (
            computed
            if receipt["application"] == computed
            else "invalid"
        )
    except (KeyError, TypeError):
        return "invalid"


def evaluate_fixture_at_current_head(
    receipt: dict,
    evidence: dict[str, dict] | None = None,
) -> str:
    # Test convenience only: these fixtures model a checkpoint whose
    # independently resolved current head is the receipt's bound ref.
    current_recovery_ref = (
        receipt.get("recovery_ref")
        if isinstance(receipt, dict)
        else None
    )
    return evaluate_protected_policy_application(
        receipt,
        evidence,
        current_recovery_ref=current_recovery_ref,
    )


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
        self.assertEqual(contract["schema"], "codex.thread_supervision.v2")
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
        policy_state = contract["targets"][0][
            "protected_policy_application_state"
        ]
        policy_applications = resolve_active_policy_applications(
            policy_state, {}
        )
        self.assertIsNotNone(policy_applications)
        self.assertEqual(len(policy_applications), 1)
        policy_application = policy_applications[0]
        recovery_evidence = trusted_policy_recovery_store()
        self.assertTrue(
            valid_policy_application_state(policy_state, recovery_evidence)
        )
        for malformed_state in ([], {}):
            malformed_checkpoint = copy.deepcopy(policy_state)
            malformed_checkpoint["active_inline"][0]["state"] = (
                malformed_state
            )
            malformed_recovery = copy.deepcopy(recovery_evidence)
            malformed_recovery[policy_application["recovery_ref"]][
                "checkpoint_state"
            ] = malformed_state
            with self.subTest(malformed_state=type(malformed_state).__name__):
                self.assertFalse(
                    valid_policy_application_state(
                        malformed_checkpoint, recovery_evidence
                    )
                )
                self.assertFalse(
                    valid_policy_application_state(
                        policy_state, malformed_recovery
                    )
                )
        partial_recovery_evidence = copy.deepcopy(recovery_evidence)
        del partial_recovery_evidence[policy_application["recovery_ref"]][
            "receiver_thread_id"
        ]
        self.assertFalse(
            valid_policy_application_state(
                policy_state, partial_recovery_evidence
            )
        )
        for required_recovery_field in (
            "receiver_thread_id",
            "store_schema",
            "store_ref",
            "store_authorization_ref",
            "intent_ref",
            "destination_ref",
            "subject_ref",
            "operation_namespace_ref",
        ):
            null_binding_evidence = copy.deepcopy(recovery_evidence)
            null_binding_evidence[policy_application["recovery_ref"]][
                required_recovery_field
            ] = None
            with self.subTest(
                required_recovery_field=required_recovery_field
            ):
                self.assertFalse(
                    valid_policy_application_state(
                        policy_state, null_binding_evidence
                    )
                )
        grafted_migration_provenance = copy.deepcopy(recovery_evidence)
        grafted_migration_provenance[
            policy_application["recovery_ref"]
        ].update(
            {
                "migration_ref": "sha256:" + "0" * 64,
                "migration_source_checkpoint_ref": (
                    "grafted-source-checkpoint-ref"
                ),
                "migration_checkpoint_fingerprint": (
                    "sha256:" + "1" * 64
                ),
                "migration_target_thread_id": "grafted-target-thread",
                "migration_target_host_id": "grafted-target-host",
            }
        )
        self.assertFalse(
            valid_policy_application_state(
                policy_state, grafted_migration_provenance
            )
        )
        self.assertEqual(
            set(policy_application),
            {
                "schema",
                "application_id",
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
            "codex.protected_policy_application_checkpoint.v2",
        )
        self.assertEqual(
            policy_application["state"], "mutation-outcome-unknown"
        )
        self.assertTrue(policy_application["recovery_ref"])
        self.assertTrue(policy_application["intent_operation_id"])
        self.assertTrue(policy_application["mutation_operation_id"])
        later_application = copy.deepcopy(policy_application)
        later_application.update(
            {
                "application_id": "later-application-id",
                "state": "revision-captured",
                "policy_revision_id": "later-policy-revision",
                "recovery_ref": "later-private-recovery-ref",
                "intent_operation_id": None,
                "mutation_operation_id": None,
            }
        )
        before = copy.deepcopy(policy_state)
        in_flight = [copy.deepcopy(policy_application), later_application]
        operation_namespace = recovery_evidence[
            policy_application["recovery_ref"]
        ]["operation_namespace_ref"]
        for lifecycle_state in POLICY_APPLICATION_STATES:
            fresh_root = {
                "schema": (
                    "codex.protected_policy_application_checkpoint.v2"
                ),
                "application_id": f"fresh-root-{lifecycle_state}",
                "state": lifecycle_state,
                "policy_revision_id": f"fresh-revision-{lifecycle_state}",
                "operation_policy_fingerprint": (
                    f"fresh-policy-fingerprint-{lifecycle_state}"
                ),
                "recovery_ref": f"fresh-recovery-{lifecycle_state}",
                "intent_operation_id": f"fresh-intent-{lifecycle_state}",
                "mutation_operation_id": (
                    f"fresh-mutation-{lifecycle_state}"
                ),
            }
            fresh_evidence = {
                fresh_root["recovery_ref"]: (
                    checkpoint_recovery_projection(fresh_root)
                )
            }
            fresh_state = empty_policy_application_state()
            fresh_state.update(
                {"active_count": 1, "active_inline": [fresh_root]}
            )
            expected = lifecycle_state == "revision-captured"
            with self.subTest(fresh_root_state=lifecycle_state):
                self.assertEqual(
                    valid_policy_application_state(
                        fresh_state, fresh_evidence
                    ),
                    expected,
                )
                self.assertEqual(
                    valid_policy_application_transition(
                        empty_policy_application_state(),
                        fresh_state,
                        fresh_evidence,
                    ),
                    expected,
                )
        recovery_evidence[later_application["recovery_ref"]] = (
            checkpoint_recovery_projection(
                later_application,
                operation_namespace_ref=operation_namespace,
            )
        )
        after = copy.deepcopy(policy_state)
        after.update({"active_count": 2, "active_inline": in_flight})
        self.assertTrue(
            valid_policy_application_state(after, recovery_evidence)
        )
        self.assertTrue(
            valid_policy_application_transition(
                before, after, recovery_evidence
            )
        )
        grafted_after = copy.deepcopy(after)
        grafted_b = grafted_after["active_inline"][1]
        grafted_b["recovery_ref"] = "grafted-new-application-recovery"
        grafted_evidence = {
            **recovery_evidence,
            grafted_b["recovery_ref"]: checkpoint_recovery_projection(
                grafted_b,
                predecessor_ref=policy_application["recovery_ref"],
                operation_namespace_ref=operation_namespace,
            ),
        }
        self.assertFalse(
            valid_policy_application_state(grafted_after, grafted_evidence)
        )
        self.assertFalse(
            valid_policy_application_transition(
                before, grafted_after, grafted_evidence
            )
        )
        self.assertEqual(
            resolve_active_policy_applications(after, {})[0]["state"],
            "mutation-outcome-unknown",
        )
        reset_unknown = copy.deepcopy(after)
        reset_unknown["active_inline"][0]["state"] = "revision-captured"
        self.assertFalse(
            valid_policy_application_transition(
                after, reset_unknown, recovery_evidence
            )
        )
        unknown_without_ids = copy.deepcopy(after)
        unknown_without_ids["active_inline"][0].update(
            {"intent_operation_id": None, "mutation_operation_id": None}
        )
        self.assertFalse(
            valid_policy_application_state(
                unknown_without_ids, recovery_evidence
            )
        )
        for lifecycle_state in POLICY_APPLICATION_STATES:
            null_fingerprint_state = copy.deepcopy(policy_state)
            null_fingerprint_item = null_fingerprint_state[
                "active_inline"
            ][0]
            null_fingerprint_item.update(
                {
                    "state": lifecycle_state,
                    "operation_policy_fingerprint": None,
                }
            )
            null_fingerprint_evidence = copy.deepcopy(recovery_evidence)
            null_fingerprint_recovery = null_fingerprint_evidence[
                policy_application["recovery_ref"]
            ]
            null_fingerprint_recovery.update(
                {
                    "checkpoint_state": lifecycle_state,
                    "operation_policy_fingerprint": None,
                }
            )
            with self.subTest(lifecycle_state=lifecycle_state):
                self.assertFalse(
                    valid_policy_application_state(
                        null_fingerprint_state,
                        null_fingerprint_evidence,
                    )
                )
        reconciled_a = copy.deepcopy(policy_application)
        reconciled_a.update(
            {
                "state": "readback-pending",
                "recovery_ref": "reconciled-a-recovery-ref",
            }
        )
        reconciliation_ref = "reconciled-a-receipt"
        reconciliation_evidence = {
            **recovery_evidence,
            reconciled_a["recovery_ref"]: checkpoint_recovery_projection(
                reconciled_a,
                inherited_recovery=recovery_evidence[
                    policy_application["recovery_ref"]
                ],
                predecessor_ref=policy_application["recovery_ref"],
                reconciliation_receipt_ref=reconciliation_ref,
                operation_namespace_ref=operation_namespace,
            ),
            reconciliation_ref: {
                "schema": (
                    "codex.protected_policy_application_reconciliation.v1"
                ),
                "authority": "owning-system",
                "application_id": policy_application["application_id"],
                "policy_revision_id": policy_application[
                    "policy_revision_id"
                ],
                "from_state": "mutation-outcome-unknown",
                "to_state": "readback-pending",
                "from_recovery_ref": policy_application["recovery_ref"],
                "to_recovery_ref": reconciled_a["recovery_ref"],
                "intent_operation_id": reconciled_a[
                    "intent_operation_id"
                ],
                "mutation_operation_id": reconciled_a[
                    "mutation_operation_id"
                ],
            },
        }
        reconciled_state = copy.deepcopy(after)
        reconciled_state["active_inline"][0] = reconciled_a
        self.assertTrue(
            valid_policy_application_transition(
                after, reconciled_state, reconciliation_evidence
            )
        )
        completed_after_reconciliation = copy.deepcopy(reconciled_state)
        completed_item = completed_after_reconciliation[
            "active_inline"
        ][0]
        completed_item.update(
            {
                "state": "terminal",
                "recovery_ref": "post-reconciliation-terminal-recovery",
            }
        )
        completed_evidence = {
            **reconciliation_evidence,
            completed_item["recovery_ref"]: checkpoint_recovery_projection(
                completed_item,
                inherited_recovery=reconciliation_evidence[
                    reconciled_a["recovery_ref"]
                ],
                predecessor_ref=reconciled_a["recovery_ref"],
                operation_namespace_ref=operation_namespace,
            ),
        }
        self.assertTrue(
            valid_policy_application_state(
                completed_after_reconciliation, completed_evidence
            )
        )
        self.assertTrue(
            valid_policy_application_transition(
                reconciled_state,
                completed_after_reconciliation,
                completed_evidence,
            )
        )
        missing_reconciliation = copy.deepcopy(reconciliation_evidence)
        del missing_reconciliation[reconciliation_ref]
        self.assertFalse(
            valid_policy_application_transition(
                after, reconciled_state, missing_reconciliation
            )
        )
        spurious_reconciliation_state = copy.deepcopy(after)
        spurious_item = spurious_reconciliation_state["active_inline"][0]
        spurious_item["recovery_ref"] = (
            "spurious-reconciliation-recovery"
        )
        spurious_ref = "spurious-reconciliation-receipt"
        spurious_evidence = {
            **recovery_evidence,
            spurious_item["recovery_ref"]: checkpoint_recovery_projection(
                spurious_item,
                inherited_recovery=recovery_evidence[
                    policy_application["recovery_ref"]
                ],
                predecessor_ref=policy_application["recovery_ref"],
                reconciliation_receipt_ref=spurious_ref,
                operation_namespace_ref=operation_namespace,
            ),
            spurious_ref: {
                "schema": (
                    "codex.protected_policy_application_reconciliation.v1"
                ),
                "authority": "owning-system",
                "application_id": policy_application["application_id"],
                "policy_revision_id": policy_application[
                    "policy_revision_id"
                ],
                "from_state": "mutation-outcome-unknown",
                "to_state": "readback-pending",
                "from_recovery_ref": policy_application["recovery_ref"],
                "to_recovery_ref": spurious_item["recovery_ref"],
                "intent_operation_id": spurious_item[
                    "intent_operation_id"
                ],
                "mutation_operation_id": spurious_item[
                    "mutation_operation_id"
                ],
            },
        }
        self.assertFalse(
            valid_policy_application_state(
                spurious_reconciliation_state, spurious_evidence
            )
        )
        self.assertFalse(
            valid_policy_application_transition(
                after,
                spurious_reconciliation_state,
                spurious_evidence,
            )
        )
        hidden_before = copy.deepcopy(policy_state)
        hidden_after = copy.deepcopy(hidden_before)
        hidden_after_item = hidden_after["active_inline"][0]
        hidden_after_item.update(
            {
                "state": "readback-pending",
                "recovery_ref": "hidden-reconciliation-head",
            }
        )
        hidden_intermediate_ref = "hidden-reconciliation-intermediate"
        hidden_receipt_ref = "hidden-reconciliation-receipt"
        hidden_intermediate_item = copy.deepcopy(hidden_after_item)
        hidden_intermediate_item["recovery_ref"] = hidden_intermediate_ref
        hidden_evidence = {
            **recovery_evidence,
            hidden_intermediate_ref: checkpoint_recovery_projection(
                hidden_intermediate_item,
                inherited_recovery=recovery_evidence[
                    policy_application["recovery_ref"]
                ],
                predecessor_ref=policy_application["recovery_ref"],
                reconciliation_receipt_ref=hidden_receipt_ref,
                operation_namespace_ref=operation_namespace,
            ),
            hidden_after_item["recovery_ref"]: (
                checkpoint_recovery_projection(
                    hidden_after_item,
                    inherited_recovery=recovery_evidence[
                        policy_application["recovery_ref"]
                    ],
                    predecessor_ref=hidden_intermediate_ref,
                    operation_namespace_ref=operation_namespace,
                )
            ),
            hidden_receipt_ref: {
                "schema": (
                    "codex.protected_policy_application_reconciliation.v1"
                ),
                "authority": "owning-system",
                "application_id": policy_application["application_id"],
                "policy_revision_id": policy_application[
                    "policy_revision_id"
                ],
                "from_state": "mutation-outcome-unknown",
                "to_state": "readback-pending",
                "from_recovery_ref": policy_application["recovery_ref"],
                "to_recovery_ref": hidden_intermediate_ref,
                "intent_operation_id": policy_application[
                    "intent_operation_id"
                ],
                "mutation_operation_id": policy_application[
                    "mutation_operation_id"
                ],
            },
        }
        self.assertTrue(
            valid_policy_application_state(hidden_before, hidden_evidence)
        )
        self.assertTrue(
            valid_policy_application_state(hidden_after, hidden_evidence)
        )
        self.assertFalse(
            valid_policy_application_transition(
                hidden_before, hidden_after, hidden_evidence
            )
        )
        hidden_state_mismatch = copy.deepcopy(hidden_after)
        hidden_state_mismatch["active_inline"][0][
            "state"
        ] = "revision-captured"
        self.assertFalse(
            valid_policy_application_state(
                hidden_state_mismatch, hidden_evidence
            )
        )
        for field, replacement in (
            ("operation_policy_fingerprint", "rotated-policy-fingerprint"),
            ("intent_operation_id", "rotated-intent-operation-id"),
            ("mutation_operation_id", "rotated-mutation-operation-id"),
            ("operation_namespace_ref", "rotated-operation-namespace"),
        ):
            rotated_state = copy.deepcopy(after)
            rotated_item = rotated_state["active_inline"][0]
            rotated_item["recovery_ref"] = f"rotated-{field}-recovery"
            if field != "operation_namespace_ref":
                rotated_item[field] = replacement
            rotated_evidence = {
                **recovery_evidence,
                rotated_item["recovery_ref"]: (
                    checkpoint_recovery_projection(
                        rotated_item,
                        inherited_recovery=recovery_evidence[
                            policy_application["recovery_ref"]
                        ],
                        predecessor_ref=policy_application["recovery_ref"],
                        operation_namespace_ref=(
                            replacement
                            if field == "operation_namespace_ref"
                            else operation_namespace
                        ),
                    )
                ),
            }
            self.assertFalse(
                valid_policy_application_state(
                    rotated_state, rotated_evidence
                )
            )
            self.assertFalse(
                valid_policy_application_transition(
                    after, rotated_state, rotated_evidence
                )
            )

        reused_operations = copy.deepcopy(after)
        reused_b = reused_operations["active_inline"][1]
        reused_b.update(
            {
                "recovery_ref": "later-reused-operation-recovery",
                "intent_operation_id": policy_application[
                    "intent_operation_id"
                ],
                "mutation_operation_id": policy_application[
                    "mutation_operation_id"
                ],
            }
        )
        reused_operation_evidence = {
            **recovery_evidence,
            reused_b["recovery_ref"]: checkpoint_recovery_projection(
                reused_b,
                operation_namespace_ref=operation_namespace,
            ),
        }
        self.assertFalse(
            valid_policy_application_state(
                reused_operations, reused_operation_evidence
            )
        )

        evolved_b = copy.deepcopy(later_application)
        evolved_b.update(
            {
                "state": "adoption-pending",
                "recovery_ref": "later-private-recovery-ref-v2",
                "intent_operation_id": "later-intent-operation-id",
                "mutation_operation_id": "later-mutation-operation-id",
            }
        )
        evolved_after = copy.deepcopy(after)
        evolved_after["active_inline"][1] = evolved_b
        evolved_evidence = {
            **recovery_evidence,
            evolved_b["recovery_ref"]: checkpoint_recovery_projection(
                evolved_b,
                inherited_recovery=recovery_evidence[
                    later_application["recovery_ref"]
                ],
                predecessor_ref=later_application["recovery_ref"],
                operation_namespace_ref=operation_namespace,
            ),
        }
        self.assertTrue(
            valid_policy_application_transition(
                after, evolved_after, evolved_evidence
            )
        )
        self.assertEqual(
            {item["application_id"] for item in in_flight},
            {"stable-opaque-application-id", "later-application-id"},
        )
        self.assertEqual(
            {item["recovery_ref"] for item in in_flight},
            {
                "opaque-protected-policy-application-recovery-ref",
                "later-private-recovery-ref",
            },
        )
        duplicate_application = copy.deepcopy(later_application)
        duplicate_application["application_id"] = policy_application[
            "application_id"
        ]
        duplicate_application["policy_revision_id"] = "third-policy-revision"
        duplicate_application["recovery_ref"] = "third-private-recovery-ref"
        self.assertFalse(
            valid_policy_application_collection(
                [policy_application, duplicate_application]
            )
        )
        duplicate_revision = copy.deepcopy(later_application)
        duplicate_revision["application_id"] = "third-application-id"
        duplicate_revision["recovery_ref"] = "third-private-recovery-ref"
        duplicate_revision["policy_revision_id"] = policy_application[
            "policy_revision_id"
        ]
        self.assertFalse(
            valid_policy_application_collection(
                [policy_application, duplicate_revision]
            )
        )
        duplicate_recovery = copy.deepcopy(later_application)
        duplicate_recovery["application_id"] = "third-application-id"
        duplicate_recovery["policy_revision_id"] = "third-policy-revision"
        duplicate_recovery["recovery_ref"] = policy_application["recovery_ref"]
        self.assertFalse(
            valid_policy_application_collection(
                [policy_application, duplicate_recovery]
            )
        )

        replaced_unknown = copy.deepcopy(after)
        replaced_unknown.update(
            {"active_count": 1, "active_inline": [later_application]}
        )
        self.assertFalse(
            valid_policy_application_transition(
                before, replaced_unknown, recovery_evidence
            )
        )

        terminal_application_receipt = protected_policy_application_example(
            REFERENCE.read_text(encoding="utf-8")
        )
        terminal_recovery_ref = terminal_application_receipt["recovery_ref"]
        terminal_reconciliation_ref = (
            trusted_policy_evidence()[terminal_recovery_ref][
                "reconciliation_receipt_ref"
            ]
        )
        terminal_evidence = {
            **trusted_policy_evidence(),
            **recovery_evidence,
            "terminal-application-receipt-a": terminal_application_receipt,
            "terminal-authority-a": {
                "schema": (
                    "codex.protected_policy_application_terminal_authority.v1"
                ),
                "producer": "codex-thread-supervisor",
                "terminal_receipt_ref": "terminal-receipt-a",
                "application_receipt_ref": "terminal-application-receipt-a",
            },
            "terminal-receipt-a": {
                "schema": (
                    "codex.protected_policy_application_terminal_receipt.v1"
                ),
                "producer": "codex-thread-supervisor",
                "producer_authority_ref": "terminal-authority-a",
                "application_id": policy_application["application_id"],
                "policy_revision_id": policy_application[
                    "policy_revision_id"
                ],
                "recovery_ref": terminal_recovery_ref,
                "application_receipt_ref": "terminal-application-receipt-a",
                "reconciliation_receipt_ref": terminal_reconciliation_ref,
                "terminal_application": "applied",
            },
            "retired-index-a": {
                "schema": (
                    "codex.protected_policy_application_retired_index.v1"
                ),
                "predecessor_ref": None,
                "tombstones": [
                    {
                        "schema": (
                            "codex.protected_policy_application_terminal.v1"
                        ),
                        "application_id": policy_application[
                            "application_id"
                        ],
                        "policy_revision_id": policy_application[
                            "policy_revision_id"
                        ],
                        "recovery_ref": terminal_recovery_ref,
                        "terminal_receipt_ref": "terminal-receipt-a",
                    }
                ],
            },
        }
        terminal_after = copy.deepcopy(after)
        terminal_after.update(
            {
                "active_count": 1,
                "active_inline": [later_application],
                "retired_index_ref": "retired-index-a",
            }
        )
        self.assertTrue(
            valid_policy_application_transition(
                after, terminal_after, terminal_evidence
            )
        )
        nonterminal_terminal_outcome = copy.deepcopy(terminal_evidence)
        nonterminal_terminal_outcome["terminal-receipt-a"][
            "terminal_application"
        ] = "reconciliation-required"
        self.assertFalse(
            valid_policy_application_state(
                terminal_after, nonterminal_terminal_outcome
            )
        )
        for malformed_enum in ([], {}):
            malformed_terminal_outcome = copy.deepcopy(terminal_evidence)
            malformed_terminal_outcome["terminal-receipt-a"][
                "terminal_application"
            ] = malformed_enum
            malformed_reconciliation_state = copy.deepcopy(terminal_evidence)
            malformed_reconciliation_state[terminal_reconciliation_ref][
                "from_state"
            ] = malformed_enum
            with self.subTest(
                malformed_terminal_enum=type(malformed_enum).__name__
            ):
                self.assertFalse(
                    valid_policy_application_state(
                        terminal_after, malformed_terminal_outcome
                    )
                )
                self.assertFalse(
                    valid_policy_application_state(
                        terminal_after, malformed_reconciliation_state
                    )
                )
        malformed_reconciliation_ref = copy.deepcopy(terminal_evidence)
        malformed_reconciliation_ref[terminal_reconciliation_ref][
            "from_recovery_ref"
        ] = []
        malformed_terminal_reconciliation_ref = copy.deepcopy(
            terminal_evidence
        )
        malformed_terminal_reconciliation_ref["terminal-receipt-a"][
            "reconciliation_receipt_ref"
        ] = []
        self.assertFalse(
            valid_policy_application_state(
                terminal_after, malformed_reconciliation_ref
            )
        )
        self.assertFalse(
            valid_policy_application_state(
                terminal_after, malformed_terminal_reconciliation_ref
            )
        )

        substituted_terminal_envelope = copy.deepcopy(terminal_evidence)
        substituted_terminal_reconciliation_ref = (
            "substituted-terminal-envelope-reconciliation"
        )
        substituted_terminal_envelope[
            substituted_terminal_reconciliation_ref
        ] = copy.deepcopy(
            substituted_terminal_envelope[terminal_reconciliation_ref]
        )
        substituted_terminal_envelope["terminal-receipt-a"][
            "reconciliation_receipt_ref"
        ] = substituted_terminal_reconciliation_ref
        self.assertFalse(
            valid_policy_application_state(
                terminal_after, substituted_terminal_envelope
            )
        )
        self.assertFalse(
            valid_policy_application_transition(
                after, terminal_after, substituted_terminal_envelope
            )
        )
        missing_terminal_envelope = copy.deepcopy(terminal_evidence)
        missing_terminal_envelope["terminal-receipt-a"][
            "reconciliation_receipt_ref"
        ] = None
        self.assertFalse(
            valid_policy_application_state(
                terminal_after, missing_terminal_envelope
            )
        )
        self.assertFalse(
            valid_policy_application_transition(
                terminal_after,
                terminal_after,
                missing_terminal_envelope,
            )
        )

        hidden_terminal_edge_evidence = copy.deepcopy(terminal_evidence)
        hidden_terminal_edge_ref = "hidden-terminal-edge-recovery"
        hidden_terminal_edge_head = hidden_terminal_edge_evidence[
            terminal_recovery_ref
        ]
        hidden_terminal_edge_evidence[hidden_terminal_edge_ref] = {
            **hidden_terminal_edge_head,
            "predecessor_ref": policy_application["recovery_ref"],
            "reconciliation_receipt_ref": terminal_reconciliation_ref,
        }
        hidden_terminal_edge_head.update(
            {
                "predecessor_ref": hidden_terminal_edge_ref,
                "reconciliation_receipt_ref": None,
            }
        )
        hidden_terminal_edge_evidence[terminal_reconciliation_ref][
            "to_recovery_ref"
        ] = hidden_terminal_edge_ref
        envelope_reconciliation_ref = (
            "hidden-terminal-envelope-reconciliation"
        )
        hidden_terminal_edge_evidence[envelope_reconciliation_ref] = {
            "schema": (
                "codex.protected_policy_application_reconciliation.v1"
            ),
            "authority": "owning-system",
            "application_id": policy_application["application_id"],
            "policy_revision_id": policy_application["policy_revision_id"],
            "from_state": "mutation-outcome-unknown",
            "to_state": "terminal",
            "from_recovery_ref": policy_application["recovery_ref"],
            "to_recovery_ref": terminal_recovery_ref,
            "intent_operation_id": policy_application["intent_operation_id"],
            "mutation_operation_id": policy_application[
                "mutation_operation_id"
            ],
        }
        hidden_terminal_edge_evidence["terminal-receipt-a"][
            "reconciliation_receipt_ref"
        ] = envelope_reconciliation_ref
        self.assertFalse(
            valid_policy_application_state(
                terminal_after, hidden_terminal_edge_evidence
            )
        )
        self.assertFalse(
            valid_policy_application_transition(
                after, terminal_after, hidden_terminal_edge_evidence
            )
        )

        hidden_readback_terminal_evidence = {
            **copy.deepcopy(terminal_evidence),
            **copy.deepcopy(reconciliation_evidence),
        }
        hidden_readback_terminal_ref = "hidden-readback-terminal-recovery"
        hidden_readback_head = hidden_readback_terminal_evidence[
            terminal_recovery_ref
        ]
        hidden_readback_terminal_evidence[hidden_readback_terminal_ref] = {
            **hidden_readback_head,
            "predecessor_ref": reconciled_a["recovery_ref"],
            "reconciliation_receipt_ref": None,
        }
        hidden_readback_head.update(
            {
                "predecessor_ref": hidden_readback_terminal_ref,
                "reconciliation_receipt_ref": None,
            }
        )
        hidden_readback_terminal_evidence["terminal-receipt-a"][
            "reconciliation_receipt_ref"
        ] = None
        self.assertTrue(
            valid_policy_application_state(
                terminal_after, hidden_readback_terminal_evidence
            )
        )
        self.assertFalse(
            valid_policy_application_transition(
                reconciled_state,
                terminal_after,
                hidden_readback_terminal_evidence,
            )
        )
        hidden_terminal_evidence = copy.deepcopy(terminal_evidence)
        hidden_terminal_intermediate_ref = (
            "hidden-terminal-reconciliation-recovery"
        )
        hidden_terminal_recovery = hidden_terminal_evidence[
            terminal_recovery_ref
        ]
        hidden_terminal_evidence[
            hidden_terminal_intermediate_ref
        ] = {
            **hidden_terminal_recovery,
            "predecessor_ref": policy_application["recovery_ref"],
        }
        hidden_terminal_recovery.update(
            {
                "predecessor_ref": hidden_terminal_intermediate_ref,
                "reconciliation_receipt_ref": None,
            }
        )
        hidden_terminal_evidence[terminal_reconciliation_ref][
            "to_recovery_ref"
        ] = hidden_terminal_intermediate_ref
        self.assertFalse(
            valid_policy_application_state(
                terminal_after, hidden_terminal_evidence
            )
        )
        self.assertFalse(
            valid_policy_application_transition(
                after, terminal_after, hidden_terminal_evidence
            )
        )
        self.assertFalse(
            valid_policy_application_transition(after, terminal_after, {})
        )
        missing_terminal_application = copy.deepcopy(terminal_evidence)
        del missing_terminal_application["terminal-application-receipt-a"]
        self.assertFalse(
            valid_policy_application_transition(
                after, terminal_after, missing_terminal_application
            )
        )
        partial_terminal_recovery = copy.deepcopy(terminal_evidence)
        del partial_terminal_recovery[terminal_recovery_ref][
            "receiver_thread_id"
        ]
        self.assertFalse(
            valid_policy_application_transition(
                after, terminal_after, partial_terminal_recovery
            )
        )
        reused_retired = copy.deepcopy(terminal_after)
        reused_retired.update(
            {
                "active_count": 2,
                "active_inline": [later_application, policy_application],
            }
        )
        self.assertFalse(
            valid_policy_application_state(reused_retired, terminal_evidence)
        )
        forked_evidence = {
            "forked-retired-index": {"predecessor_ref": None}
        }
        self.assertFalse(
            retired_policy_chain_reaches(
                "forked-retired-index",
                "retired-index-a",
                forked_evidence,
            )
        )

        overflow = []
        for index in range(9):
            entry = copy.deepcopy(later_application)
            entry.update(
                {
                    "application_id": f"overflow-application-{index}",
                    "policy_revision_id": f"overflow-revision-{index}",
                    "recovery_ref": f"overflow-recovery-{index}",
                }
            )
            overflow.append(entry)
        overflow_evidence = {
            "active-index-nine": {
                "schema": (
                    "codex.protected_policy_application_active_index.v1"
                ),
                "active_count": 9,
                "applications": overflow,
            }
        }
        overflow_evidence.update(
            {
                entry["recovery_ref"]: checkpoint_recovery_projection(entry)
                for entry in overflow
            }
        )
        overflow_state = {
            "schema": "codex.protected_policy_application_state.v1",
            "active_count": 9,
            "active_inline": [],
            "active_index_ref": "active-index-nine",
            "retired_index_ref": None,
        }
        self.assertTrue(
            valid_policy_application_state(overflow_state, overflow_evidence)
        )
        indexed_noninitial_root = copy.deepcopy(overflow_evidence)
        indexed_noninitial_root["active-index-nine"]["applications"][0][
            "state"
        ] = "adoption-pending"
        indexed_noninitial_root["overflow-recovery-0"][
            "checkpoint_state"
        ] = "adoption-pending"
        self.assertFalse(
            valid_policy_application_state(
                overflow_state, indexed_noninitial_root
            )
        )
        for malformed_count in (True, 9.0):
            malformed_count_state = copy.deepcopy(overflow_state)
            malformed_count_state["active_count"] = malformed_count
            with self.subTest(malformed_active_count=malformed_count):
                self.assertFalse(
                    valid_policy_application_state(
                        malformed_count_state, overflow_evidence
                    )
                )
        malformed_index_count = copy.deepcopy(overflow_evidence)
        malformed_index_count["active-index-nine"]["active_count"] = 9.0
        self.assertFalse(
            valid_policy_application_state(
                overflow_state, malformed_index_count
            )
        )
        invalid_inline_overflow = copy.deepcopy(overflow_state)
        invalid_inline_overflow.update(
            {"active_inline": overflow, "active_index_ref": None}
        )
        self.assertFalse(
            valid_policy_application_state(
                invalid_inline_overflow, overflow_evidence
            )
        )

    def test_v1_policy_application_migration_is_explicit_and_fail_closed(self):
        target_thread_id = "legacy-thread-id"
        target_host_id = "legacy-host-id"
        legacy_application = {
            "schema": "codex.protected_policy_application_checkpoint.v1",
            "state": "mutation-outcome-unknown",
            "policy_revision_id": "legacy-revision",
            "operation_policy_fingerprint": "legacy-policy-fingerprint",
            "recovery_ref": "legacy-recovery-ref",
            "intent_operation_id": "legacy-intent-operation",
            "mutation_operation_id": "legacy-mutation-operation",
        }
        legacy = {
            "schema": "codex.thread_supervision.v1",
            "targets": [
                {
                    "thread_id": target_thread_id,
                    "host_id": target_host_id,
                    "protected_policy_application": legacy_application,
                }
            ],
        }
        legacy_fingerprint = checkpoint_fingerprint(legacy)
        source_checkpoint_ref = "legacy-source-checkpoint-ref"
        migrated_recovery_ref = "migrated-recovery-ref"
        legacy_recovery = {
            "schema": "codex.protected_policy_application_recovery.v1",
            "policy_revision_id": "legacy-revision",
            "receiver_thread_id": "legacy-receiver-thread",
            "operation_policy_fingerprint": "legacy-policy-fingerprint",
            "store_schema": "codex.authorized_immutable_intent_store.v1",
            "store_ref": "legacy-store-ref",
            "store_authorization_ref": "legacy-store-authorization-ref",
            "intent_ref": "legacy-intent-ref",
            "destination_ref": "legacy-destination-ref",
            "subject_ref": "legacy-subject-ref",
            "intent_operation_id": "legacy-intent-operation",
            "mutation_operation_id": "legacy-mutation-operation",
        }
        migration_record = {
            "schema": (
                "codex.protected_policy_application_migration.v1"
            ),
            "source_checkpoint_schema": "codex.thread_supervision.v1",
            "checkpoint_fingerprint": legacy_fingerprint,
            "source_checkpoint_ref": source_checkpoint_ref,
            "target_thread_id": target_thread_id,
            "target_host_id": target_host_id,
            "legacy_recovery_ref": "legacy-recovery-ref",
            "migrated_recovery_ref": migrated_recovery_ref,
            "operation_namespace_ref": "legacy-operation-namespace",
            "application_id": "migrated-application-id",
            "policy_revision_id": "legacy-revision",
            "intent_operation_id": "legacy-intent-operation",
            "mutation_operation_id": "legacy-mutation-operation",
        }
        migration_ref = checkpoint_fingerprint(migration_record)
        evidence = {
            source_checkpoint_ref: legacy,
            "legacy-recovery-ref": legacy_recovery,
            migration_ref: migration_record,
            migrated_recovery_ref: {
                **legacy_recovery,
                "schema": "codex.protected_policy_application_recovery.v2",
                "application_id": "migrated-application-id",
                "checkpoint_state": "mutation-outcome-unknown",
                "operation_namespace_ref": "legacy-operation-namespace",
                "migration_ref": migration_ref,
                "migration_source_checkpoint_ref": (
                    source_checkpoint_ref
                ),
                "migration_checkpoint_fingerprint": legacy_fingerprint,
                "migration_target_thread_id": target_thread_id,
                "migration_target_host_id": target_host_id,
                "predecessor_ref": None,
                "reconciliation_receipt_ref": None,
            },
        }
        migrated = migrate_v1_policy_application_state(
            legacy,
            evidence,
            target_thread_id=target_thread_id,
            target_host_id=target_host_id,
            migration_ref=migration_ref,
        )
        self.assertIsNotNone(migrated)
        active = resolve_active_policy_applications(migrated, evidence)
        self.assertEqual(active[0]["state"], "mutation-outcome-unknown")
        self.assertEqual(
            active[0]["recovery_ref"], migrated_recovery_ref
        )
        self.assertTrue(
            valid_policy_application_state(migrated, evidence)
        )
        missing_migration_attestation = copy.deepcopy(evidence)
        del missing_migration_attestation[migration_ref]
        self.assertFalse(
            valid_policy_application_state(
                migrated, missing_migration_attestation
            )
        )
        misbound_migration_attestation = copy.deepcopy(evidence)
        misbound_migration_attestation[migration_ref][
            "application_id"
        ] = "different-migrated-application"
        self.assertFalse(
            valid_policy_application_state(
                migrated, misbound_migration_attestation
            )
        )
        for coherently_rebound_field, coherently_rebound_value in (
            ("schema", "attacker.untyped_migration.v1"),
            ("migrated_recovery_ref", "different-migrated-recovery-ref"),
        ):
            coherently_rebound_record = copy.deepcopy(migration_record)
            coherently_rebound_record[
                coherently_rebound_field
            ] = coherently_rebound_value
            coherently_rebound_ref = checkpoint_fingerprint(
                coherently_rebound_record
            )
            coherently_rebound_evidence = copy.deepcopy(evidence)
            coherently_rebound_evidence[
                coherently_rebound_ref
            ] = coherently_rebound_record
            coherently_rebound_evidence[migrated_recovery_ref][
                "migration_ref"
            ] = coherently_rebound_ref
            with self.subTest(
                coherently_rebound_migration_field=coherently_rebound_field
            ):
                self.assertFalse(
                    valid_policy_application_state(
                        migrated, coherently_rebound_evidence
                    )
                )
        self.assertFalse(
            valid_policy_application_transition(
                empty_policy_application_state(),
                migrated,
                evidence,
            )
        )
        migrated_item = active[0]
        reconciled_item = copy.deepcopy(migrated_item)
        reconciled_item.update(
            {
                "state": "readback-pending",
                "recovery_ref": "migrated-readback-recovery-ref",
            }
        )
        reconciliation_ref = "migrated-readback-reconciliation-ref"
        advanced_evidence = {
            **evidence,
            reconciled_item["recovery_ref"]: (
                checkpoint_recovery_projection(
                    reconciled_item,
                    inherited_recovery=evidence[migrated_recovery_ref],
                    predecessor_ref=migrated_recovery_ref,
                    reconciliation_receipt_ref=reconciliation_ref,
                    operation_namespace_ref=(
                        "legacy-operation-namespace"
                    ),
                )
            ),
            reconciliation_ref: {
                "schema": (
                    "codex.protected_policy_application_reconciliation.v1"
                ),
                "authority": "owning-system",
                "application_id": migrated_item["application_id"],
                "policy_revision_id": migrated_item[
                    "policy_revision_id"
                ],
                "from_state": "mutation-outcome-unknown",
                "to_state": "readback-pending",
                "from_recovery_ref": migrated_recovery_ref,
                "to_recovery_ref": reconciled_item["recovery_ref"],
                "intent_operation_id": migrated_item[
                    "intent_operation_id"
                ],
                "mutation_operation_id": migrated_item[
                    "mutation_operation_id"
                ],
            },
        }
        reconciled_migrated = empty_policy_application_state()
        reconciled_migrated.update(
            {
                "active_count": 1,
                "active_inline": [reconciled_item],
            }
        )
        self.assertTrue(
            valid_policy_application_state(
                reconciled_migrated, advanced_evidence
            )
        )
        self.assertTrue(
            valid_policy_application_transition(
                migrated,
                reconciled_migrated,
                advanced_evidence,
            )
        )
        captured_source_ref = "captured-source-checkpoint-ref"
        captured_legacy_ref = "captured-legacy-recovery-ref"
        captured_root_ref = "captured-migrated-recovery-ref"
        captured_legacy = copy.deepcopy(legacy)
        captured_legacy_application = captured_legacy["targets"][0][
            "protected_policy_application"
        ]
        captured_legacy_application.update(
            {
                "state": "revision-captured",
                "recovery_ref": captured_legacy_ref,
                "intent_operation_id": None,
                "mutation_operation_id": None,
            }
        )
        captured_fingerprint = checkpoint_fingerprint(captured_legacy)
        captured_legacy_recovery = copy.deepcopy(legacy_recovery)
        captured_legacy_recovery.update(
            {
                "intent_operation_id": None,
                "mutation_operation_id": None,
            }
        )
        captured_migration = copy.deepcopy(migration_record)
        captured_migration.update(
            {
                "checkpoint_fingerprint": captured_fingerprint,
                "source_checkpoint_ref": captured_source_ref,
                "legacy_recovery_ref": captured_legacy_ref,
                "migrated_recovery_ref": captured_root_ref,
                "application_id": "captured-migrated-application-id",
                "intent_operation_id": None,
                "mutation_operation_id": None,
            }
        )
        captured_migration_ref = checkpoint_fingerprint(captured_migration)
        captured_evidence = {
            captured_source_ref: captured_legacy,
            captured_legacy_ref: captured_legacy_recovery,
            captured_migration_ref: captured_migration,
            captured_root_ref: {
                **captured_legacy_recovery,
                "schema": "codex.protected_policy_application_recovery.v2",
                "application_id": "captured-migrated-application-id",
                "checkpoint_state": "revision-captured",
                "operation_namespace_ref": "legacy-operation-namespace",
                "migration_ref": captured_migration_ref,
                "migration_source_checkpoint_ref": captured_source_ref,
                "migration_checkpoint_fingerprint": captured_fingerprint,
                "migration_target_thread_id": target_thread_id,
                "migration_target_host_id": target_host_id,
                "predecessor_ref": None,
                "reconciliation_receipt_ref": None,
            },
        }
        captured_state = migrate_v1_policy_application_state(
            captured_legacy,
            captured_evidence,
            target_thread_id=target_thread_id,
            target_host_id=target_host_id,
            migration_ref=captured_migration_ref,
        )
        self.assertIsNotNone(captured_state)
        captured_item = resolve_active_policy_applications(
            captured_state, captured_evidence
        )[0]
        adoption_item = copy.deepcopy(captured_item)
        adoption_item.update(
            {
                "state": "adoption-pending",
                "recovery_ref": "captured-adoption-recovery-ref",
            }
        )
        adoption_evidence = {
            **captured_evidence,
            adoption_item["recovery_ref"]: checkpoint_recovery_projection(
                adoption_item,
                inherited_recovery=captured_evidence[captured_root_ref],
                predecessor_ref=captured_root_ref,
            ),
        }
        adoption_state = empty_policy_application_state()
        adoption_state.update(
            {"active_count": 1, "active_inline": [adoption_item]}
        )
        self.assertTrue(
            valid_policy_application_state(adoption_state, adoption_evidence)
        )
        self.assertTrue(
            valid_policy_application_transition(
                captured_state, adoption_state, adoption_evidence
            )
        )
        intent_item = copy.deepcopy(adoption_item)
        intent_item.update(
            {
                "state": "intent-pending",
                "recovery_ref": "captured-intent-recovery-ref",
                "intent_operation_id": "captured-intent-operation-id",
                "mutation_operation_id": "captured-mutation-operation-id",
            }
        )
        intent_evidence = {
            **adoption_evidence,
            intent_item["recovery_ref"]: checkpoint_recovery_projection(
                intent_item,
                inherited_recovery=adoption_evidence[
                    adoption_item["recovery_ref"]
                ],
                predecessor_ref=adoption_item["recovery_ref"],
            ),
        }
        intent_state = empty_policy_application_state()
        intent_state.update(
            {"active_count": 1, "active_inline": [intent_item]}
        )
        self.assertTrue(
            valid_policy_application_state(intent_state, intent_evidence)
        )
        self.assertTrue(
            valid_policy_application_transition(
                adoption_state, intent_state, intent_evidence
            )
        )
        for rebound_field, rebound_value in (
            ("target_thread_id", "different-target-thread"),
            ("target_host_id", "different-target-host"),
            ("checkpoint_fingerprint", "sha256:" + "0" * 64),
        ):
            rebound_evidence = copy.deepcopy(evidence)
            rebound_evidence[migration_ref][
                rebound_field
            ] = rebound_value
            with self.subTest(rebound_migration_field=rebound_field):
                self.assertFalse(
                    valid_policy_application_state(
                        migrated, rebound_evidence
                    )
                )
        unrelated_migration = copy.deepcopy(evidence[migration_ref])
        unrelated_migration.update(
            {
                "migrated_recovery_ref": (
                    "unrelated-migrated-recovery-ref"
                ),
                "application_id": "unrelated-application-id",
                "target_thread_id": "unrelated-thread-id",
                "target_host_id": "unrelated-host-id",
            }
        )
        evidence_with_unrelated_migration = {
            **evidence,
            "unrelated-migration-ref": unrelated_migration,
        }
        self.assertTrue(
            valid_policy_application_state(
                migrated, evidence_with_unrelated_migration
            )
        )
        for malformed_state in ([], {}):
            malformed_legacy_state = copy.deepcopy(legacy)
            malformed_legacy_state["targets"][0][
                "protected_policy_application"
            ]["state"] = malformed_state
            with self.subTest(
                malformed_legacy_state=type(malformed_state).__name__
            ):
                self.assertIsNone(
                    migrate_v1_policy_application_state(
                        malformed_legacy_state,
                        evidence,
                        target_thread_id=target_thread_id,
                        target_host_id=target_host_id,
                        migration_ref=migration_ref,
                    )
                )
        self.assertIsNone(
            migrate_v1_policy_application_state(
                legacy,
                evidence,
                target_thread_id="",
                target_host_id=target_host_id,
                migration_ref=migration_ref,
            )
        )
        self.assertIsNone(
            migrate_v1_policy_application_state(
                legacy,
                evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
            )
        )
        none_key_migration_evidence = copy.deepcopy(evidence)
        none_key_migration_evidence[None] = (
            none_key_migration_evidence.pop(migration_ref)
        )
        self.assertIsNone(
            migrate_v1_policy_application_state(
                legacy,
                none_key_migration_evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
            )
        )
        for malformed_migration_field in (
            "checkpoint_fingerprint",
            "source_checkpoint_ref",
            "target_thread_id",
            "target_host_id",
            "legacy_recovery_ref",
            "migrated_recovery_ref",
            "operation_namespace_ref",
            "application_id",
            "policy_revision_id",
            "intent_operation_id",
            "mutation_operation_id",
        ):
            malformed_migration_evidence = copy.deepcopy(evidence)
            malformed_migration_evidence[migration_ref][
                malformed_migration_field
            ] = []
            with self.subTest(
                malformed_migration_field=malformed_migration_field
            ):
                self.assertIsNone(
                    migrate_v1_policy_application_state(
                        legacy,
                        malformed_migration_evidence,
                        target_thread_id=target_thread_id,
                        target_host_id=target_host_id,
                        migration_ref=migration_ref,
                    )
                )
        missing_legacy_recovery = copy.deepcopy(evidence)
        del missing_legacy_recovery["legacy-recovery-ref"]
        self.assertIsNone(
            migrate_v1_policy_application_state(
                legacy,
                missing_legacy_recovery,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                migration_ref=migration_ref,
            )
        )
        missing_source_checkpoint = copy.deepcopy(evidence)
        del missing_source_checkpoint[source_checkpoint_ref]
        self.assertIsNone(
            migrate_v1_policy_application_state(
                legacy,
                missing_source_checkpoint,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                migration_ref=migration_ref,
            )
        )
        null_legacy_binding = copy.deepcopy(evidence)
        null_legacy_binding["legacy-recovery-ref"][
            "receiver_thread_id"
        ] = None
        null_legacy_binding[migrated_recovery_ref][
            "receiver_thread_id"
        ] = None
        self.assertIsNone(
            migrate_v1_policy_application_state(
                legacy,
                null_legacy_binding,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                migration_ref=migration_ref,
            )
        )
        null_fingerprint_legacy = copy.deepcopy(legacy)
        null_fingerprint_legacy["targets"][0][
            "protected_policy_application"
        ]["operation_policy_fingerprint"] = None
        null_fingerprint_migration_evidence = copy.deepcopy(evidence)
        null_fingerprint_migration_evidence["legacy-recovery-ref"][
            "operation_policy_fingerprint"
        ] = None
        null_fingerprint_migration_evidence[migrated_recovery_ref][
            "operation_policy_fingerprint"
        ] = None
        null_fingerprint_migration_evidence[migration_ref][
            "checkpoint_fingerprint"
        ] = checkpoint_fingerprint(null_fingerprint_legacy)
        self.assertIsNone(
            migrate_v1_policy_application_state(
                null_fingerprint_legacy,
                null_fingerprint_migration_evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                migration_ref=migration_ref,
            )
        )
        both_shapes = copy.deepcopy(legacy)
        both_shapes["targets"][0][
            "protected_policy_application_state"
        ] = empty_policy_application_state()
        self.assertIsNone(
            migrate_v1_policy_application_state(
                both_shapes,
                evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                migration_ref=migration_ref,
            )
        )
        explicit_empty = {
            "schema": "codex.thread_supervision.v1",
            "targets": [
                {
                    "thread_id": target_thread_id,
                    "host_id": target_host_id,
                    "protected_policy_application": None,
                }
            ],
        }
        self.assertEqual(
            migrate_v1_policy_application_state(
                explicit_empty,
                {},
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
            ),
            empty_policy_application_state(),
        )
        missing_field = {
            "schema": "codex.thread_supervision.v1",
            "targets": [
                {
                    "thread_id": target_thread_id,
                    "host_id": target_host_id,
                }
            ],
        }
        self.assertIsNone(
            migrate_v1_policy_application_state(
                missing_field,
                {},
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
            )
        )
        pre_feature_proof_ref = "pre-feature-proof"
        source_revision_ref = "pre-feature-source-revision"
        inventory_ref = "pre-feature-inventory"
        missing_fingerprint = checkpoint_fingerprint(missing_field)
        pre_feature_evidence = {
            pre_feature_proof_ref: {
                "schema": (
                    "codex.thread_supervision_pre_feature_proof.v1"
                ),
                "checkpoint_fingerprint": missing_fingerprint,
                "target_thread_id": target_thread_id,
                "target_host_id": target_host_id,
                "source_contract_revision_ref": source_revision_ref,
                "evidence_inventory_ref": inventory_ref,
                "protected_policy_application_evidence_count": 0,
            },
            source_revision_ref: {
                "schema": "codex.thread_supervision_source_contract.v1",
                "checkpoint_fingerprint": missing_fingerprint,
                "contract_revision": "known-pre-feature-v1",
                "protected_policy_feature": "absent",
            },
            inventory_ref: {
                "schema": "codex.thread_supervision_evidence_inventory.v1",
                "checkpoint_fingerprint": missing_fingerprint,
                "target_thread_id": target_thread_id,
                "target_host_id": target_host_id,
                "cutoff": "legacy-inventory-cutoff",
                "application_recovery_refs": [],
            },
        }
        none_key_proof_evidence = copy.deepcopy(pre_feature_evidence)
        none_key_proof_evidence[None] = none_key_proof_evidence.pop(
            pre_feature_proof_ref
        )
        self.assertIsNone(
            migrate_v1_policy_application_state(
                missing_field,
                none_key_proof_evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
            )
        )
        self.assertEqual(
            migrate_v1_policy_application_state(
                missing_field,
                pre_feature_evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                pre_feature_proof_ref=pre_feature_proof_ref,
            ),
            empty_policy_application_state(),
        )
        for malformed_count in (False, 0.0):
            malformed_count_evidence = copy.deepcopy(pre_feature_evidence)
            malformed_count_evidence[pre_feature_proof_ref][
                "protected_policy_application_evidence_count"
            ] = malformed_count
            with self.subTest(malformed_evidence_count=malformed_count):
                self.assertIsNone(
                    migrate_v1_policy_application_state(
                        missing_field,
                        malformed_count_evidence,
                        target_thread_id=target_thread_id,
                        target_host_id=target_host_id,
                        pre_feature_proof_ref=pre_feature_proof_ref,
                    )
                )
        unrelated_checkpoint = copy.deepcopy(missing_field)
        unrelated_checkpoint["goal"] = "different-checkpoint-content"
        self.assertIsNone(
            migrate_v1_policy_application_state(
                unrelated_checkpoint,
                pre_feature_evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                pre_feature_proof_ref=pre_feature_proof_ref,
            )
        )
        non_json_checkpoint = copy.deepcopy(missing_field)
        non_json_checkpoint["goal"] = float("nan")
        self.assertIsNone(
            migrate_v1_policy_application_state(
                non_json_checkpoint,
                pre_feature_evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                pre_feature_proof_ref=pre_feature_proof_ref,
            )
        )
        self.assertIsNone(
            migrate_v1_policy_application_state(
                legacy,
                pre_feature_evidence,
                target_thread_id=target_thread_id,
                target_host_id=target_host_id,
                pre_feature_proof_ref=pre_feature_proof_ref,
            )
        )

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
        duplicate_name_example = re.search(
            r"## Protected Policy Application.*?```json\n(.*?)\n```",
            reference,
            re.DOTALL,
        )
        self.assertIsNotNone(duplicate_name_example)
        duplicate_name_json = duplicate_name_example.group(1).replace(
            '"destination_ref": '
            '"opaque-external-system-ref",',
            '"destination_ref": '
            '"opaque-external-system-ref",\n'
            '    "destination_ref": '
            '"different-opaque-external-system-ref",',
            1,
        )
        self.assertNotEqual(
            duplicate_name_json,
            duplicate_name_example.group(1),
        )
        with self.assertRaises(ValueError):
            strict_json_loads(duplicate_name_json)
        unicode_policy = {
            "subject_ref": "\u00e9",
            "mandatory_fields": [
                {
                    "expectation_evidence_ref": "proof\u96ea",
                    "expected_value_fingerprint": {
                        "scheme": "hmac-sha256",
                        "key_ref_fingerprint": (
                            "sha256:"
                            "1807dbf17817a8d83d0b098f063b16bd"
                            "2d904809e8cf0731ffa3ff2c68aa30dd"
                        ),
                        "digest": (
                            "8fab1805ae51245c10795c447a58e0196"
                            "bc67352e4e2e8ba663979929778238c"
                        ),
                    },
                    "field_ref": "field\U0001f600",
                }
            ],
            "eligibility_cutoff": "e\u0301",
            "operation": "create",
            "destination_ref": (
                "d\u0000\u0001\b\t\n\f\r\"/\\caf\u00e9\u96ea"
                "\U0001f600\u2028\u2029"
            ),
        }
        expected_canonical_hex = (
            "7b2264657374696e6174696f6e5f726566223a22645c75303030305c7530303031"
            "5c625c745c6e5c665c725c222f5c5c636166c3a9e99baaf09f9880e280a8e280"
            "a9222c22656c69676962696c6974795f6375746f6666223a2265cc81222c226d61"
            "6e6461746f72795f6669656c6473223a5b7b226578706563746174696f6e5f6576"
            "6964656e63655f726566223a2270726f6f66e99baa222c2265787065637465645f"
            "76616c75655f66696e6765727072696e74223a7b22646967657374223a22386661"
            "623138303561653531323435633130373935633434376135386530313936626336"
            "37333532653465326538626136363339373939323937373832333863222c226b65"
            "795f7265665f66696e6765727072696e74223a227368613235363a313830376462"
            "663137383137613864383364306230393866303633623136626432643930343830"
            "39653863663037333166666133666632633638616133306464222c22736368656d"
            "65223a22686d61632d736861323536227d2c226669656c645f726566223a226669"
            "656c64f09f9880227d5d2c226f7065726174696f6e223a22637265617465222c22"
            "7375626a6563745f726566223a22c3a9227d"
        )
        canonical_unicode = canonical_operation_policy_json(unicode_policy)
        self.assertEqual(
            canonical_unicode,
            bytes.fromhex(expected_canonical_hex),
        )
        self.assertEqual(
            operation_policy_fingerprint(unicode_policy),
            "sha256:"
            "736ab4a8bd83267f275978d713efe95c7"
            "1c9f42398dc02e9e16cfc50c8fee2e1",
        )
        escaped_input_policy = copy.deepcopy(unicode_policy)
        escaped_input_policy["subject_ref"] = json.loads('"\\u00e9"')
        escaped_input_policy["mandatory_fields"][0]["field_ref"] = (
            json.loads('"field\\ud83d\\ude00"')
        )
        self.assertEqual(
            canonical_operation_policy_json(escaped_input_policy),
            canonical_unicode,
        )
        nfc_policy = copy.deepcopy(receipt["operation_policy"])
        nfd_policy = copy.deepcopy(receipt["operation_policy"])
        nfc_policy["subject_ref"] = "\u00e9"
        nfd_policy["subject_ref"] = "e\u0301"
        self.assertNotEqual(
            operation_policy_fingerprint(nfc_policy),
            operation_policy_fingerprint(nfd_policy),
        )
        for forbidden_scalar in (None, True, 1, 1.0):
            forbidden_policy = copy.deepcopy(receipt["operation_policy"])
            forbidden_policy["eligibility_cutoff"] = forbidden_scalar
            with self.subTest(
                forbidden_canonical_scalar=repr(forbidden_scalar)
            ):
                with self.assertRaises(ValueError):
                    canonical_operation_policy_json(forbidden_policy)
        surrogate_policy = copy.deepcopy(receipt["operation_policy"])
        surrogate_policy["subject_ref"] = "\ud800"
        with self.assertRaises(ValueError):
            canonical_operation_policy_json(surrogate_policy)
        for non_json_number in (
            float("nan"),
            float("inf"),
            float("-inf"),
        ):
            noncanonical_policy = copy.deepcopy(
                receipt["operation_policy"]
            )
            noncanonical_policy["eligibility_cutoff"] = non_json_number
            with self.assertRaises(ValueError):
                operation_policy_fingerprint(noncanonical_policy)
            noncanonical_receipt = copy.deepcopy(receipt)
            noncanonical_receipt["operation_policy"][
                "eligibility_cutoff"
            ] = non_json_number
            self.assertEqual(
                evaluate_fixture_at_current_head(
                    noncanonical_receipt
                ),
                "invalid",
            )
        self.assertEqual(
            receipt["schema"], "codex.protected_policy_application.v2"
        )
        self.assertEqual(
            set(receipt),
            {
                "schema",
                "application_id",
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
            "codex.protected_policy_application_recovery.v2",
        )
        self.assertEqual(
            recovery["application_id"], receipt["application_id"]
        )
        wrong_application_id = copy.deepcopy(receipt)
        wrong_application_id["application_id"] = "different-application-id"
        self.assertEqual(
            evaluate_fixture_at_current_head(wrong_application_id),
            "invalid",
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
                "result_object_ref",
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
            receipt["mutation"]["result_object_ref"],
            receipt["readback"]["object_ref"],
        )
        self.assertEqual(
            trusted_policy_evidence()[receipt["mutation"]["receipt_ref"]][
                "result_object_ref"
            ],
            receipt["readback"]["object_ref"],
        )
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
            evaluate_fixture_at_current_head(receipt), "applied"
        )
        for missing_committed_field in ("receipt_ref", "cutoff"):
            committed_without_proof = copy.deepcopy(receipt)
            committed_without_proof["mutation"][
                missing_committed_field
            ] = None
            with self.subTest(
                committed_mutation_missing=missing_committed_field
            ):
                self.assertEqual(
                    evaluate_fixture_at_current_head(
                        committed_without_proof
                    ),
                    "invalid",
                )
        self.assertEqual(
            receipt["operation_policy"]["mandatory_fields"][0][
                "expected_value_fingerprint"
            ],
            trusted_keyed_fingerprint(),
        )
        self.assertTrue(
            trusted_fingerprint_provenance(
                purpose="expectation",
                evidence_ref="opaque-keyed-expectation-proof-ref",
                subject_ref=receipt["operation_policy"]["subject_ref"],
                field_ref=TRUSTED_POLICY_FIELD_REF,
                fingerprint=trusted_keyed_fingerprint(),
            )
        )
        self.assertTrue(
            trusted_fingerprint_provenance(
                purpose="observation",
                evidence_ref="opaque-owning-system-readback-ref",
                subject_ref=receipt["operation_policy"]["subject_ref"],
                field_ref=TRUSTED_POLICY_FIELD_REF,
                fingerprint=trusted_keyed_fingerprint(),
                object_ref=receipt["readback"]["object_ref"],
                mutation_operation_id=receipt["mutation"]["operation_id"],
                readback_cutoff=receipt["readback"]["cutoff"],
            )
        )
        for label, overrides in (
            ("different purpose", {"purpose": "observation"}),
            ("different subject", {"subject_ref": "different-subject"}),
            ("different field", {"field_ref": "different-field"}),
            ("different evidence", {"evidence_ref": "different-evidence"}),
        ):
            verifier_arguments = {
                "purpose": "expectation",
                "evidence_ref": "opaque-keyed-expectation-proof-ref",
                "subject_ref": receipt["operation_policy"]["subject_ref"],
                "field_ref": TRUSTED_POLICY_FIELD_REF,
                "fingerprint": trusted_keyed_fingerprint(),
            }
            verifier_arguments.update(overrides)
            with self.subTest(fingerprint_provenance=label):
                self.assertFalse(
                    trusted_fingerprint_provenance(**verifier_arguments)
                )
        for label, field, value in (
            (
                "different key",
                "key_ref_fingerprint",
                "sha256:" + "4" * 64,
            ),
            ("different digest", "digest", "5" * 64),
        ):
            forged_fingerprint = trusted_keyed_fingerprint()
            forged_fingerprint[field] = value
            with self.subTest(fingerprint_provenance=label):
                self.assertFalse(
                    trusted_fingerprint_provenance(
                        purpose="expectation",
                        evidence_ref="opaque-keyed-expectation-proof-ref",
                        subject_ref=receipt["operation_policy"]["subject_ref"],
                        field_ref=TRUSTED_POLICY_FIELD_REF,
                        fingerprint=forged_fingerprint,
                    )
                )
        wrong_domain_fingerprint = trusted_keyed_fingerprint()
        wrong_domain_fingerprint["digest"] = hmac.new(
            TRUSTED_HMAC_KEY_MATERIAL,
            (
                b"different.protected-policy-field.v1\x00"
                + TRUSTED_POLICY_FIELD_REF.encode("utf-8")
                + b"\x00"
                + TRUSTED_POLICY_NORMALIZED_VALUE
            ),
            hashlib.sha256,
        ).hexdigest()
        wrong_field_fingerprint = keyed_fingerprint_for(
            field_ref="different-field",
            normalized_value=TRUSTED_POLICY_NORMALIZED_VALUE,
        )
        for label, fingerprint in (
            ("different domain", wrong_domain_fingerprint),
            ("different field derivation", wrong_field_fingerprint),
        ):
            with self.subTest(fingerprint_provenance=label):
                self.assertFalse(
                    trusted_fingerprint_provenance(
                        purpose="expectation",
                        evidence_ref="opaque-keyed-expectation-proof-ref",
                        subject_ref=receipt["operation_policy"]["subject_ref"],
                        field_ref=TRUSTED_POLICY_FIELD_REF,
                        fingerprint=fingerprint,
                    )
                )
        ambiguous_field_ref = "field-a\x00value-part"
        canonical_message = keyed_fingerprint_message(
            "field-a",
            b"value-part\x00tail",
        )
        ambiguous_unchecked_message = (
            TRUSTED_HMAC_DOMAIN
            + b"\x00"
            + ambiguous_field_ref.encode("utf-8")
            + b"\x00tail"
        )
        self.assertEqual(canonical_message, ambiguous_unchecked_message)
        self.assertFalse(valid_fingerprint_field_ref(ambiguous_field_ref))
        with self.assertRaises(ValueError):
            keyed_fingerprint_message(ambiguous_field_ref, b"tail")
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
                    evaluate_fixture_at_current_head(substituted),
                    "applied",
                )

        cross_receiver_replay = copy.deepcopy(receipt)
        cross_receiver_replay["receiver_thread_id"] = "different-receiver"
        self.assertEqual(
            evaluate_fixture_at_current_head(cross_receiver_replay),
            "invalid",
        )

        missing_adoption_evidence = copy.deepcopy(receipt)
        missing_adoption_evidence["receiver_adoption"]["acknowledgement_ref"] = ""
        self.assertEqual(
            evaluate_fixture_at_current_head(missing_adoption_evidence),
            "invalid",
        )

        wrong_adopted_fingerprint = copy.deepcopy(receipt)
        wrong_adopted_fingerprint["receiver_adoption"][
            "to_protected_contract_fingerprint"
        ] = "different-protected-fingerprint"
        self.assertEqual(
            evaluate_fixture_at_current_head(wrong_adopted_fingerprint),
            "invalid",
        )

        wrong_predecessor_fingerprint = copy.deepcopy(receipt)
        wrong_predecessor_fingerprint["receiver_adoption"][
            "from_protected_contract_fingerprint"
        ] = "different-prior-protected-fingerprint"
        self.assertEqual(
            evaluate_fixture_at_current_head(wrong_predecessor_fingerprint),
            "invalid",
        )

        understated_application = copy.deepcopy(receipt)
        understated_application["application"] = "blocked"
        self.assertEqual(
            evaluate_fixture_at_current_head(understated_application),
            "invalid",
        )

        wrong_policy_fingerprint = copy.deepcopy(receipt)
        wrong_policy_fingerprint["operation_policy_fingerprint"] = (
            "sha256:" + "0" * 64
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(wrong_policy_fingerprint),
            "invalid",
        )

        late_adoption_intent = copy.deepcopy(receipt)
        late_adoption_intent["prewrite_intent"][
            "receiver_acknowledgement_ref"
        ] = "different-receiver-ack"
        self.assertEqual(
            evaluate_fixture_at_current_head(late_adoption_intent),
            "invalid",
        )

        wrong_mutation_intent = copy.deepcopy(receipt)
        wrong_mutation_intent["mutation"][
            "prewrite_intent_ref"
        ] = "different-prewrite-intent"
        self.assertEqual(
            evaluate_fixture_at_current_head(wrong_mutation_intent),
            "invalid",
        )

        wrong_mutation_operation = copy.deepcopy(receipt)
        wrong_mutation_operation["readback"][
            "mutation_operation_id"
        ] = "different-mutation-operation"
        wrong_mutation_operation["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(wrong_mutation_operation),
            "policy-drift",
        )

        wrong_mutation_destination = copy.deepcopy(receipt)
        wrong_mutation_destination["mutation"][
            "destination_ref"
        ] = "different-destination"
        self.assertEqual(
            evaluate_fixture_at_current_head(wrong_mutation_destination),
            "invalid",
        )

        wrong_mutation_result_object = copy.deepcopy(receipt)
        wrong_mutation_result_object["mutation"][
            "result_object_ref"
        ] = "different-object"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                wrong_mutation_result_object
            ),
            "invalid",
        )

        wrong_readback_object = copy.deepcopy(receipt)
        wrong_readback_object["readback"]["object_ref"] = "different-object"
        wrong_readback_object["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(wrong_readback_object),
            "policy-drift",
        )

        unauthorized_store = copy.deepcopy(receipt)
        unauthorized_store["prewrite_intent"][
            "store_schema"
        ] = "filesystem.local-write.v1"
        self.assertEqual(
            evaluate_fixture_at_current_head(unauthorized_store),
            "invalid",
        )

        missing_store_authorization = copy.deepcopy(receipt)
        missing_store_authorization["prewrite_intent"][
            "store_authorization_ref"
        ] = ""
        self.assertEqual(
            evaluate_fixture_at_current_head(missing_store_authorization),
            "invalid",
        )

        missing_immutability = copy.deepcopy(receipt)
        missing_immutability["prewrite_intent"][
            "immutability_evidence_ref"
        ] = ""
        self.assertEqual(
            evaluate_fixture_at_current_head(missing_immutability),
            "invalid",
        )

        stale_readback = copy.deepcopy(receipt)
        stale_readback["readback"][
            "mutation_receipt_ref"
        ] = "different-mutation-receipt"
        stale_readback["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(stale_readback),
            "policy-drift",
        )

        unordered_readback = copy.deepcopy(receipt)
        unordered_readback["readback"]["relation"] = "before-mutation"
        unordered_readback["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(unordered_readback),
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
                    evaluate_fixture_at_current_head(malformed), "invalid"
                )

        missing = copy.deepcopy(receipt)
        missing["readback"]["field_results"] = []
        missing["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(missing), "policy-drift"
        )

        duplicate = copy.deepcopy(receipt)
        duplicate["readback"]["field_results"].append(
            copy.deepcopy(duplicate["readback"]["field_results"][0])
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(duplicate), "invalid"
        )

        mismatched = copy.deepcopy(receipt)
        mismatched["readback"]["field_results"][0][
            "observed_value_fingerprint"
        ]["digest"] = "3" * 64
        self.assertEqual(
            evaluate_fixture_at_current_head(mismatched), "invalid"
        )

        nul_field_ref = copy.deepcopy(receipt)
        nul_field_ref["operation_policy"]["mandatory_fields"][0][
            "field_ref"
        ] = "opaque-domain\x00field-ref"
        nul_field_ref["readback"]["field_results"][0][
            "field_ref"
        ] = "opaque-domain\x00field-ref"
        self.assertEqual(
            evaluate_fixture_at_current_head(nul_field_ref), "invalid"
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
                "sha256:"
                + hashlib.sha256(
                    json.dumps(
                        malformed_fingerprint["operation_policy"],
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest()
            )
            malformed_fingerprint["receiver_adoption"][
                "operation_policy_fingerprint"
            ] = malformed_fingerprint["operation_policy_fingerprint"]
            malformed_fingerprint["prewrite_intent"][
                "operation_policy_fingerprint"
            ] = malformed_fingerprint["operation_policy_fingerprint"]
            with self.subTest(malformed_keyed_fingerprint=label):
                self.assertEqual(
                    evaluate_fixture_at_current_head(malformed_fingerprint),
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
        for recovery_ref in (
            "opaque-protected-policy-application-recovery-ref",
            "opaque-protected-policy-application-terminal-recovery-ref",
        ):
            forged_evidence[recovery_ref][
                "operation_policy_fingerprint"
            ] = forged_policy_fingerprint
        forged_evidence["opaque-intent-immutability-proof-ref"][
            "operation_policy_fingerprint"
        ] = forged_policy_fingerprint
        forged_evidence["opaque-immutable-prewrite-intent-ref"][
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
        forged_evidence["opaque-owning-system-readback-ref"][
            "value_fingerprint"
        ] = copy.deepcopy(
            forged_keyed_receipt["readback"]["field_results"][0][
                "observed_value_fingerprint"
            ]
        )
        # Matching receipt and evidence echoes cannot replace the independent
        # verifier's authorized key, source binding, and HMAC recomputation.
        self.assertEqual(
            evaluate_fixture_at_current_head(
                forged_keyed_receipt,
                forged_evidence,
            ),
            "invalid",
        )

        coordinated_policy_body = copy.deepcopy(receipt)
        coordinated_policy_body["operation_policy"]["operation"] = "update"
        coordinated_policy_fingerprint = operation_policy_fingerprint(
            coordinated_policy_body["operation_policy"]
        )
        coordinated_policy_body[
            "operation_policy_fingerprint"
        ] = coordinated_policy_fingerprint
        coordinated_policy_body["receiver_adoption"][
            "operation_policy_fingerprint"
        ] = coordinated_policy_fingerprint
        coordinated_policy_body["prewrite_intent"][
            "operation_policy_fingerprint"
        ] = coordinated_policy_fingerprint
        coordinated_policy_evidence = copy.deepcopy(
            trusted_policy_evidence()
        )
        for evidence_ref in (
            "opaque-receiver-owned-ack-ref",
            "opaque-intent-immutability-proof-ref",
            "opaque-immutable-prewrite-intent-ref",
            "opaque-keyed-expectation-proof-ref",
            "opaque-protected-policy-application-recovery-ref",
            "opaque-protected-policy-application-terminal-recovery-ref",
        ):
            coordinated_policy_evidence[evidence_ref][
                "operation_policy_fingerprint"
            ] = coordinated_policy_fingerprint
        # The generic evidence map cannot replace the independently loaded
        # private immutable recovery record, even when every echo agrees.
        self.assertEqual(
            evaluate_fixture_at_current_head(
                coordinated_policy_body,
                coordinated_policy_evidence,
            ),
            "invalid",
        )

        different_observation_fingerprint = keyed_fingerprint_for(
            field_ref=TRUSTED_POLICY_FIELD_REF,
            normalized_value=(
                b"different-synthetic-normalized-field-value"
            ),
        )
        verified_field_drift = copy.deepcopy(receipt)
        verified_field_drift["readback"]["field_results"][0].update(
            {
                "observed_value_fingerprint": (
                    different_observation_fingerprint
                ),
                "evidence_ref": (
                    "opaque-owning-system-different-readback-ref"
                ),
                "status": "mismatched",
            }
        )
        verified_field_drift_evidence = copy.deepcopy(
            trusted_policy_evidence()
        )
        verified_field_drift_evidence[
            "opaque-owning-system-different-readback-ref"
        ] = {
            "schema": "codex.field_observation_evidence.v1",
            "object_ref": receipt["readback"]["object_ref"],
            "mutation_operation_id": receipt["mutation"]["operation_id"],
            "readback_cutoff": receipt["readback"]["cutoff"],
            "field_ref": TRUSTED_POLICY_FIELD_REF,
            "value_fingerprint": different_observation_fingerprint,
            "status": "mismatched",
        }
        verified_field_drift["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                verified_field_drift,
                verified_field_drift_evidence,
            ),
            "policy-drift",
        )

        verified_missing_field = copy.deepcopy(receipt)
        verified_missing_field["readback"]["field_results"][0].update(
            {
                "observed_value_fingerprint": None,
                "evidence_ref": "opaque-owning-system-missing-readback-ref",
                "status": "missing",
            }
        )
        verified_missing_evidence = copy.deepcopy(trusted_policy_evidence())
        verified_missing_evidence[
            "opaque-owning-system-missing-readback-ref"
        ] = {
            "schema": "codex.field_observation_evidence.v1",
            "object_ref": receipt["readback"]["object_ref"],
            "mutation_operation_id": receipt["mutation"]["operation_id"],
            "readback_cutoff": receipt["readback"]["cutoff"],
            "field_ref": TRUSTED_POLICY_FIELD_REF,
            "value_fingerprint": None,
            "status": "missing",
        }
        verified_missing_field["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                verified_missing_field,
                verified_missing_evidence,
            ),
            "policy-drift",
        )

        unverified_observation_echo = copy.deepcopy(verified_field_drift)
        unverified_observation_echo["readback"]["field_results"][0].update(
            {
                "observed_value_fingerprint": trusted_keyed_fingerprint(),
                "status": "matched",
            }
        )
        unverified_observation_evidence = copy.deepcopy(
            verified_field_drift_evidence
        )
        unverified_observation_evidence[
            "opaque-owning-system-different-readback-ref"
        ].update(
            {
                "value_fingerprint": trusted_keyed_fingerprint(),
                "status": "matched",
            }
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unverified_observation_echo,
                unverified_observation_evidence,
            ),
            "invalid",
        )

        def mark_readback_not_run(candidate):
            if candidate["mutation"]["state"] == "committed":
                candidate["recovery_ref"] = (
                    "opaque-protected-policy-application-"
                    "readback-pending-recovery-ref"
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

        def mark_not_attempted(candidate):
            candidate["mutation"].update(
                {
                    "state": "not-attempted",
                    "operation_id": None,
                    "destination_ref": None,
                    "subject_ref": None,
                    "result_object_ref": None,
                    "receipt_ref": None,
                    "prewrite_intent_operation_id": None,
                    "prewrite_intent_ref": None,
                    "cutoff": None,
                }
            )
            mark_readback_not_run(candidate)

        def mark_intent_unwritten(candidate, status="not-created"):
            candidate["prewrite_intent"].update(
                {
                    "status": status,
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

        adopted_intent_without_mutation = copy.deepcopy(receipt)
        mark_not_attempted(adopted_intent_without_mutation)
        adopted_intent_without_mutation["application"] = "blocked"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                adopted_intent_without_mutation
            ),
            "blocked",
        )

        intent_before_adoption = copy.deepcopy(receipt)
        intent_before_adoption["receiver_adoption"]["status"] = "not-proven"
        mark_not_attempted(intent_before_adoption)
        intent_before_adoption["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(intent_before_adoption),
            "policy-drift",
        )

        incomplete_before_adoption = copy.deepcopy(receipt)
        incomplete_before_adoption["receiver_adoption"]["status"] = (
            "not-proven"
        )
        mark_readback_not_run(incomplete_before_adoption)
        incomplete_before_adoption["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                incomplete_before_adoption
            ),
            "policy-drift",
        )

        incomplete_with_adoption_mismatch = copy.deepcopy(receipt)
        incomplete_with_adoption_mismatch["receiver_adoption"][
            "policy_revision_id"
        ] = "different-policy-revision"
        mark_readback_not_run(incomplete_with_adoption_mismatch)
        self.assertEqual(
            evaluate_fixture_at_current_head(
                incomplete_with_adoption_mismatch
            ),
            "invalid",
        )

        incomplete_with_intent_ordering_drift = copy.deepcopy(receipt)
        incomplete_with_intent_ordering_drift["prewrite_intent"][
            "relation"
        ] = "before-adoption"
        mark_readback_not_run(incomplete_with_intent_ordering_drift)
        self.assertEqual(
            evaluate_fixture_at_current_head(
                incomplete_with_intent_ordering_drift
            ),
            "invalid",
        )

        for evidence_gate, evidence_ref in (
            (
                "receiver adoption",
                receipt["receiver_adoption"]["acknowledgement_ref"],
            ),
            (
                "intent store authorization",
                receipt["prewrite_intent"]["store_authorization_ref"],
            ),
            (
                "intent ordering",
                receipt["prewrite_intent"]["ordering_evidence_ref"],
            ),
            (
                "intent immutability",
                receipt["prewrite_intent"]["immutability_evidence_ref"],
            ),
            (
                "intent record",
                receipt["prewrite_intent"]["intent_ref"],
            ),
        ):
            for evidence_state in ("missing", "forged"):
                incomplete_with_untrusted_gate = copy.deepcopy(receipt)
                mark_readback_not_run(incomplete_with_untrusted_gate)
                untrusted_evidence = trusted_policy_evidence()
                if evidence_state == "missing":
                    untrusted_evidence.pop(evidence_ref)
                else:
                    untrusted_evidence[evidence_ref] = {
                        "schema": "forged-evidence"
                    }
                with self.subTest(
                    incomplete_evidence_gate=evidence_gate,
                    evidence_state=evidence_state,
                ):
                    self.assertEqual(
                        evaluate_fixture_at_current_head(
                            incomplete_with_untrusted_gate,
                            untrusted_evidence,
                        ),
                        "invalid",
                    )

        stale_receiver = copy.deepcopy(intent_before_adoption)
        mark_intent_unwritten(stale_receiver)
        stale_receiver["application"] = "blocked"
        self.assertEqual(
            evaluate_fixture_at_current_head(stale_receiver), "blocked"
        )

        not_attempted_with_mutation_observation = copy.deepcopy(receipt)
        mark_not_attempted(not_attempted_with_mutation_observation)
        not_attempted_with_mutation_observation["mutation"][
            "operation_id"
        ] = receipt["mutation"]["operation_id"]
        self.assertEqual(
            evaluate_fixture_at_current_head(
                not_attempted_with_mutation_observation
            ),
            "invalid",
        )

        not_attempted_with_readback_observation = copy.deepcopy(receipt)
        mark_not_attempted(not_attempted_with_readback_observation)
        not_attempted_with_readback_observation["readback"][
            "object_ref"
        ] = receipt["readback"]["object_ref"]
        self.assertEqual(
            evaluate_fixture_at_current_head(
                not_attempted_with_readback_observation
            ),
            "invalid",
        )

        malformed_stale_receiver = copy.deepcopy(stale_receiver)
        malformed_result = copy.deepcopy(receipt["readback"]["field_results"][0])
        malformed_stale_receiver["readback"]["field_results"] = [
            malformed_result,
            copy.deepcopy(malformed_result),
        ]
        self.assertEqual(
            evaluate_fixture_at_current_head(malformed_stale_receiver),
            "invalid",
        )

        unauthorized_mutation = copy.deepcopy(receipt)
        unauthorized_mutation["receiver_adoption"]["status"] = "not-proven"
        unauthorized_mutation["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(unauthorized_mutation),
            "policy-drift",
        )

        nonadopted_unknown = copy.deepcopy(receipt)
        nonadopted_unknown["receiver_adoption"]["status"] = "not-proven"
        nonadopted_unknown["mutation"]["state"] = "outcome-unknown"
        nonadopted_unknown["mutation"]["receipt_ref"] = None
        nonadopted_unknown["recovery_ref"] = (
            "opaque-protected-policy-application-recovery-ref"
        )
        nonadopted_unknown["application"] = "reconciliation-required"
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
            evaluate_fixture_at_current_head(nonadopted_unknown),
            "reconciliation-required",
        )
        mutation_unknown_with_terminal_head = copy.deepcopy(
            nonadopted_unknown
        )
        mutation_unknown_with_terminal_head["recovery_ref"] = (
            "opaque-protected-policy-application-terminal-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                mutation_unknown_with_terminal_head
            ),
            "invalid",
        )
        mutation_unknown_with_intent_head = copy.deepcopy(
            nonadopted_unknown
        )
        mutation_unknown_with_intent_head["recovery_ref"] = (
            "opaque-protected-policy-application-"
            "intent-unknown-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                mutation_unknown_with_intent_head
            ),
            "invalid",
        )
        mutation_unknown_with_readback_head = copy.deepcopy(
            nonadopted_unknown
        )
        mutation_unknown_with_readback_head["recovery_ref"] = (
            "opaque-protected-policy-application-"
            "readback-pending-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                mutation_unknown_with_readback_head
            ),
            "invalid",
        )
        substituted_recovery_ref = "generic-substituted-recovery-ref"
        mutation_unknown_with_substituted_head = copy.deepcopy(
            nonadopted_unknown
        )
        mutation_unknown_with_substituted_head[
            "recovery_ref"
        ] = substituted_recovery_ref
        generic_recovery_evidence = trusted_policy_evidence()
        generic_recovery_evidence[substituted_recovery_ref] = (
            copy.deepcopy(
                trusted_policy_recovery_store()[
                    "opaque-protected-policy-application-recovery-ref"
                ]
            )
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                mutation_unknown_with_substituted_head,
                generic_recovery_evidence,
            ),
            "invalid",
        )
        unknown_with_wrong_application = copy.deepcopy(nonadopted_unknown)
        unknown_with_wrong_application["application_id"] = (
            "different-application-id"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unknown_with_wrong_application
            ),
            "invalid",
        )
        unknown_with_stale_policy_body = copy.deepcopy(nonadopted_unknown)
        unknown_with_stale_policy_body["operation_policy"][
            "operation"
        ] = "update"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unknown_with_stale_policy_body
            ),
            "invalid",
        )

        unknown_with_policy_mismatch = copy.deepcopy(nonadopted_unknown)
        unknown_with_policy_mismatch["operation_policy_fingerprint"] = (
            "sha256:" + "0" * 64
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unknown_with_policy_mismatch
            ),
            "invalid",
        )

        unknown_with_later_semantic_mismatch = copy.deepcopy(
            nonadopted_unknown
        )
        unknown_with_later_semantic_mismatch["prewrite_intent"][
            "store_schema"
        ] = "different-store-schema"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unknown_with_later_semantic_mismatch
            ),
            "reconciliation-required",
        )
        for field in ("destination_ref", "subject_ref"):
            unknown_with_wrong_mutation_binding = copy.deepcopy(
                nonadopted_unknown
            )
            unknown_with_wrong_mutation_binding["mutation"][field] = (
                f"different-{field.replace('_ref', '')}"
            )
            with self.subTest(unknown_mutation_binding=field):
                self.assertEqual(
                    evaluate_fixture_at_current_head(
                        unknown_with_wrong_mutation_binding
                    ),
                    "invalid",
                )
        unknown_with_binding_and_later_semantic_mismatch = copy.deepcopy(
            nonadopted_unknown
        )
        unknown_with_binding_and_later_semantic_mismatch["mutation"][
            "destination_ref"
        ] = "different-destination"
        unknown_with_binding_and_later_semantic_mismatch[
            "prewrite_intent"
        ]["store_schema"] = "different-store-schema"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unknown_with_binding_and_later_semantic_mismatch
            ),
            "invalid",
        )

        unknown_with_malformed_fingerprint = copy.deepcopy(nonadopted_unknown)
        unknown_with_malformed_fingerprint[
            "operation_policy_fingerprint"
        ] = "not-a-fingerprint"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unknown_with_malformed_fingerprint
            ),
            "invalid",
        )

        missing_mutation_operation = copy.deepcopy(nonadopted_unknown)
        missing_mutation_operation["mutation"]["operation_id"] = None
        self.assertEqual(
            evaluate_fixture_at_current_head(missing_mutation_operation),
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
                evaluate_fixture_at_current_head(
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
            evaluate_fixture_at_current_head(
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
            evaluate_fixture_at_current_head(
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
        no_intent_store["application"] = "blocked"
        self.assertEqual(
            evaluate_fixture_at_current_head(no_intent_store), "blocked"
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
        intent_outcome_unknown["recovery_ref"] = (
            "opaque-protected-policy-application-"
            "intent-unknown-recovery-ref"
        )
        intent_outcome_unknown["application"] = (
            "reconciliation-required"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(intent_outcome_unknown),
            "reconciliation-required",
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                intent_outcome_unknown
            ),
            "invalid",
        )
        stale_intent_head_ref = intent_outcome_unknown["recovery_ref"]
        current_intent_head_ref = (
            "opaque-current-intent-unknown-recovery-ref"
        )
        current_intent_head = copy.deepcopy(
            trusted_policy_recovery_store()[stale_intent_head_ref]
        )
        current_intent_head.update(
            {
                "predecessor_ref": stale_intent_head_ref,
                "reconciliation_receipt_ref": None,
            }
        )
        current_intent_item = {
            "schema": "codex.protected_policy_application_checkpoint.v2",
            "application_id": intent_outcome_unknown["application_id"],
            "state": "intent-outcome-unknown",
            "policy_revision_id": intent_outcome_unknown[
                "policy_revision_id"
            ],
            "operation_policy_fingerprint": intent_outcome_unknown[
                "operation_policy_fingerprint"
            ],
            "recovery_ref": current_intent_head_ref,
            "intent_operation_id": current_intent_head[
                "intent_operation_id"
            ],
            "mutation_operation_id": current_intent_head[
                "mutation_operation_id"
            ],
        }
        current_intent_state = empty_policy_application_state()
        current_intent_state.update(
            {
                "active_count": 1,
                "active_inline": [current_intent_item],
            }
        )
        current_intent_evidence = trusted_policy_recovery_store()
        current_intent_evidence[
            current_intent_head_ref
        ] = current_intent_head
        self.assertTrue(
            valid_policy_application_state(
                current_intent_state, current_intent_evidence
            )
        )
        self.assertEqual(
            evaluate_protected_policy_application(
                intent_outcome_unknown,
                current_recovery_ref=current_intent_head_ref,
            ),
            "invalid",
        )
        intent_unknown_with_terminal_head = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_terminal_head["recovery_ref"] = (
            "opaque-protected-policy-application-terminal-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                intent_unknown_with_terminal_head
            ),
            "invalid",
        )
        intent_unknown_with_mutation_head = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_mutation_head["recovery_ref"] = (
            "opaque-protected-policy-application-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                intent_unknown_with_mutation_head
            ),
            "invalid",
        )
        intent_unknown_with_readback_head = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_readback_head["recovery_ref"] = (
            "opaque-protected-policy-application-"
            "readback-pending-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                intent_unknown_with_readback_head
            ),
            "invalid",
        )
        declared_results = {
            "invalid",
            "blocked",
            "applied",
            "policy-drift",
            "reconciliation-required",
        }
        for canonical, computed in (
            (adopted_intent_without_mutation, "blocked"),
            (intent_before_adoption, "policy-drift"),
            (receipt, "applied"),
            (intent_outcome_unknown, "reconciliation-required"),
        ):
            for declared in declared_results:
                candidate = copy.deepcopy(canonical)
                candidate["application"] = declared
                with self.subTest(
                    computed_application=computed,
                    declared_application=declared,
                ):
                    self.assertEqual(
                        evaluate_fixture_at_current_head(candidate),
                        computed if declared == computed else "invalid",
                    )
        intent_unknown_with_wrong_application = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_wrong_application["application_id"] = (
            "different-application-id"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                intent_unknown_with_wrong_application
            ),
            "invalid",
        )
        intent_unknown_with_stale_policy_body = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_stale_policy_body["operation_policy"][
            "eligibility_cutoff"
        ] = "different-eligibility-cutoff"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                intent_unknown_with_stale_policy_body
            ),
            "invalid",
        )

        intent_unknown_with_policy_mismatch = copy.deepcopy(
            intent_outcome_unknown
        )
        intent_unknown_with_policy_mismatch[
            "operation_policy_fingerprint"
        ] = "sha256:" + "0" * 64
        self.assertEqual(
            evaluate_fixture_at_current_head(
                intent_unknown_with_policy_mismatch
            ),
            "invalid",
        )

        missing_intent_operation = copy.deepcopy(intent_outcome_unknown)
        missing_intent_operation["prewrite_intent"]["operation_id"] = None
        self.assertEqual(
            evaluate_fixture_at_current_head(missing_intent_operation),
            "invalid",
        )

        missing_retained_mutation_operation = copy.deepcopy(
            intent_outcome_unknown
        )
        missing_retained_mutation_operation["prewrite_intent"][
            "mutation_operation_id"
        ] = None
        self.assertEqual(
            evaluate_fixture_at_current_head(
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
            evaluate_fixture_at_current_head(
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
            evaluate_fixture_at_current_head(
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
            evaluate_fixture_at_current_head(
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
            evaluate_fixture_at_current_head(
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
                evaluate_fixture_at_current_head(
                    unknown_intent_with_other_store
                ),
                "invalid",
                field,
            )

        unavailable = copy.deepcopy(receipt)
        unavailable["readback"]["field_results"][0].update(
            {
                "observed_value_fingerprint": None,
                "evidence_ref": (
                    "opaque-owning-system-unavailable-readback-ref"
                ),
                "status": "unavailable",
            }
        )
        unavailable["recovery_ref"] = (
            "opaque-protected-policy-application-"
            "readback-pending-recovery-ref"
        )
        unavailable["application"] = "reconciliation-required"
        self.assertEqual(
            evaluate_fixture_at_current_head(unavailable),
            "reconciliation-required",
        )
        unavailable_with_terminal_head = copy.deepcopy(unavailable)
        unavailable_with_terminal_head["recovery_ref"] = (
            "opaque-protected-policy-application-terminal-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unavailable_with_terminal_head
            ),
            "invalid",
        )
        complete_with_pending_head = copy.deepcopy(receipt)
        complete_with_pending_head["recovery_ref"] = (
            "opaque-protected-policy-application-"
            "readback-pending-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(complete_with_pending_head),
            "invalid",
        )
        unavailable_without_complete_binding = copy.deepcopy(unavailable)
        unavailable_without_complete_binding["readback"].update(
            {
                "object_ref": None,
                "cutoff": None,
                "mutation_operation_id": None,
                "mutation_receipt_ref": None,
                "relation": None,
                "ordering_evidence_ref": None,
            }
        )
        unavailable_without_complete_binding["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unavailable_without_complete_binding
            ),
            "policy-drift",
        )
        for field, value in (
            ("object_ref", "different-object-ref"),
            ("cutoff", "different-readback-cutoff"),
            ("mutation_operation_id", "different-operation-id"),
            ("mutation_receipt_ref", "different-receipt-ref"),
            ("relation", "different-relation"),
            ("ordering_evidence_ref", "different-ordering-ref"),
        ):
            unavailable_with_wrong_binding = copy.deepcopy(unavailable)
            unavailable_with_wrong_binding["readback"][field] = value
            unavailable_with_wrong_binding["application"] = "policy-drift"
            with self.subTest(
                unavailable_complete_readback_binding=field
            ):
                self.assertEqual(
                    evaluate_fixture_at_current_head(
                        unavailable_with_wrong_binding
                    ),
                    "policy-drift",
                )
        unavailable_with_untrusted_evidence = copy.deepcopy(unavailable)
        unavailable_with_untrusted_evidence["readback"]["field_results"][0][
            "evidence_ref"
        ] = "untrusted-unavailability-evidence-ref"
        unavailable_with_untrusted_evidence["application"] = "invalid"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unavailable_with_untrusted_evidence
            ),
            "invalid",
        )
        for contradictory_state in ("not-run", "unavailable"):
            contradictory_readback = copy.deepcopy(receipt)
            contradictory_readback["recovery_ref"] = (
                "opaque-protected-policy-application-"
                "readback-pending-recovery-ref"
            )
            contradictory_readback["readback"][
                "state"
            ] = contradictory_state
            with self.subTest(
                contradictory_readback_state=contradictory_state
            ):
                self.assertEqual(
                    evaluate_fixture_at_current_head(
                        contradictory_readback
                    ),
                    "invalid",
                )
        canonical_not_run = copy.deepcopy(receipt)
        canonical_not_run["recovery_ref"] = (
            "opaque-protected-policy-application-"
            "readback-pending-recovery-ref"
        )
        canonical_not_run["readback"].update(
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
        canonical_not_run["application"] = "reconciliation-required"
        self.assertEqual(
            evaluate_fixture_at_current_head(canonical_not_run),
            "reconciliation-required",
        )
        not_run_with_terminal_head = copy.deepcopy(canonical_not_run)
        not_run_with_terminal_head["recovery_ref"] = (
            "opaque-protected-policy-application-terminal-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(not_run_with_terminal_head),
            "invalid",
        )
        canonical_unavailable = copy.deepcopy(receipt)
        canonical_unavailable["recovery_ref"] = (
            "opaque-protected-policy-application-"
            "readback-pending-recovery-ref"
        )
        canonical_unavailable["readback"].update(
            {
                "state": "unavailable",
                "object_ref": None,
                "cutoff": None,
                "mutation_operation_id": canonical_unavailable["mutation"][
                    "operation_id"
                ],
                "mutation_receipt_ref": canonical_unavailable["mutation"][
                    "receipt_ref"
                ],
                "relation": None,
                "ordering_evidence_ref": None,
                "field_results": [],
            }
        )
        canonical_unavailable["application"] = "reconciliation-required"
        self.assertEqual(
            evaluate_fixture_at_current_head(canonical_unavailable),
            "reconciliation-required",
        )
        canonical_unavailable_with_terminal_head = copy.deepcopy(
            canonical_unavailable
        )
        canonical_unavailable_with_terminal_head["recovery_ref"] = (
            "opaque-protected-policy-application-terminal-recovery-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                canonical_unavailable_with_terminal_head
            ),
            "invalid",
        )
        unavailable_with_stale_policy_body = copy.deepcopy(unavailable)
        unavailable_with_stale_policy_body["operation_policy"][
            "mandatory_fields"
        ][0]["expectation_evidence_ref"] = (
            "different-expectation-evidence-ref"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unavailable_with_stale_policy_body
            ),
            "invalid",
        )
        for label, path, value in (
            (
                "application",
                ("application_id",),
                "different-application-id",
            ),
            (
                "revision",
                ("policy_revision_id",),
                "different-policy-revision",
            ),
            (
                "receiver",
                ("receiver_thread_id",),
                "different-receiver",
            ),
            (
                "policy fingerprint",
                ("operation_policy_fingerprint",),
                "sha256:" + "0" * 64,
            ),
            (
                "destination",
                ("operation_policy", "destination_ref"),
                "different-destination",
            ),
            (
                "subject",
                ("operation_policy", "subject_ref"),
                "different-subject",
            ),
        ):
            untrusted_reconciliation_target = copy.deepcopy(unavailable)
            target = untrusted_reconciliation_target
            for component in path[:-1]:
                target = target[component]
            target[path[-1]] = value
            with self.subTest(recovery_identity=label):
                self.assertEqual(
                    evaluate_fixture_at_current_head(
                        untrusted_reconciliation_target
                    ),
                    "invalid",
                )

        unavailable_with_extra = copy.deepcopy(unavailable)
        extra_result = copy.deepcopy(
            unavailable_with_extra["readback"]["field_results"][0]
        )
        extra_result["field_ref"] = "different-field"
        extra_result["status"] = "matched"
        unavailable_with_extra["readback"]["field_results"].append(extra_result)
        unavailable_with_extra["application"] = "policy-drift"
        self.assertEqual(
            evaluate_fixture_at_current_head(unavailable_with_extra),
            "policy-drift",
        )

        unavailable_with_policy_mismatch = copy.deepcopy(unavailable)
        unavailable_with_policy_mismatch["operation_policy_fingerprint"] = (
            "sha256:" + "0" * 64
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unavailable_with_policy_mismatch
            ),
            "invalid",
        )

        incomplete_with_policy_mismatch = copy.deepcopy(receipt)
        mark_readback_not_run(incomplete_with_policy_mismatch)
        incomplete_with_policy_mismatch["operation_policy_fingerprint"] = (
            "sha256:" + "0" * 64
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                incomplete_with_policy_mismatch
            ),
            "invalid",
        )
        incomplete_with_wrong_application = copy.deepcopy(
            incomplete_with_policy_mismatch
        )
        incomplete_with_wrong_application[
            "operation_policy_fingerprint"
        ] = receipt["operation_policy_fingerprint"]
        incomplete_with_wrong_application["application_id"] = (
            "different-application-id"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                incomplete_with_wrong_application
            ),
            "invalid",
        )
        incomplete_with_stale_policy_body = copy.deepcopy(receipt)
        mark_readback_not_run(incomplete_with_stale_policy_body)
        incomplete_with_stale_policy_body["operation_policy"][
            "operation"
        ] = "transition"
        self.assertEqual(
            evaluate_fixture_at_current_head(
                incomplete_with_stale_policy_body
            ),
            "invalid",
        )

        unavailable_with_conflicting_operation = copy.deepcopy(unavailable)
        unavailable_with_conflicting_operation["readback"][
            "mutation_operation_id"
        ] = "different-operation-id"
        unavailable_with_conflicting_operation["application"] = (
            "policy-drift"
        )
        self.assertEqual(
            evaluate_fixture_at_current_head(
                unavailable_with_conflicting_operation
            ),
            "policy-drift",
        )

        unavailable_with_coordinated_intent_ref = copy.deepcopy(unavailable)
        unavailable_with_coordinated_intent_ref["prewrite_intent"][
            "intent_ref"
        ] = "different-intent-ref"
        unavailable_with_coordinated_intent_ref["mutation"][
            "prewrite_intent_ref"
        ] = "different-intent-ref"
        self.assertEqual(
            evaluate_fixture_at_current_head(
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
            evaluate_fixture_at_current_head(
                unavailable_with_coordinated_receipt_ref
            ),
            "invalid",
        )

        schedule = protected_policy_failure_schedule(reference)
        self.assertEqual(len(schedule), 27)
        for condition in (
            "direct user revision while unrelated evidence or skill intervention is pending",
            "malformed receipt, empty mandatory set, or duplicate mandatory or result field refs",
            "declared application differs from the independently computed closed result",
            "no authorized typed receiver rebind with no intent, mutation, or readback observation",
            "receiver has not proven the exact revision and fingerprint, and intent, mutation, and readback remain unwritten",
            "receiver reports a revision or protected-fingerprint conflict while intent, mutation, and readback remain unwritten",
            "intent is created before exact receiver adoption",
            "a not-attempted mutation carries any mutation or readback observation",
            "mutation outcome is unknown after exact recovery and mutation identity validation, regardless of a later semantic or evidence defect",
            "intent creation outcome is unknown, regardless of another policy defect",
            "recovery application, revision, receiver, operation-policy, destination, or subject binding differs, or the claimed policy fingerprint does not equal canonical policy recomputation",
            "unknown mutation carries a different destination, subject, operation id, intent operation id, or intent ref",
            "mutation is attempted or committed without exact receiver adoption",
            "receiver acknowledgement names a different receiver, revision, or fingerprint",
            "operation-policy fingerprint or keyed fingerprint envelope is malformed or differs at adoption, intent, or readback",
            "matching fingerprint envelopes or evidence echoes lack independent authorized-verifier recomputation",
            "no existing authorized immutable intent store",
            "created intent lacks exact store schema, store identity, authorization, either operation id, or immutability evidence",
            "pre-write intent does not bind the exact receiver acknowledgement or prove `after-adoption`",
            "committed mutation lacks its exact receipt or cutoff, or the mutation receipt does not bind the exact destination, subject, operation id, pre-write intent, or result object",
            "committed mutation has canonical clean `not-run` or mutation-bound `unavailable` readback, or a causally bound complete readback has independently proven unavailable fields",
            "a non-complete readback carries object, cutoff, ordering, or field-result observations",
            "readback object differs from the recovered mutation result object, does not bind the exact operation id and receipt, or does not prove `after-mutation`",
            "any mandatory field is missing, extra, mismatched, or has a different observed fingerprint",
            "an independently proven field result is unavailable after exact causal binding and exact result-set validation",
            "exact receiver adoption, committed mutation, object identity, cutoff, and every keyed field result match",
        ):
            self.assertIn(condition, schedule)
        self.assertNotIn(
            "mutation outcome is unknown, regardless of another policy defect",
            schedule,
        )
        self.assertEqual(
            schedule[
                "committed mutation has canonical clean `not-run` or "
                "mutation-bound `unavailable` readback, or a causally "
                "bound complete readback has independently proven "
                "unavailable fields"
            ],
            "`checkpoint_state=readback-pending`, "
            "`application=reconciliation-required`",
        )
        self.assertIn(
            "an unavailable field reaches reconciliation only after the "
            "exact object, mutation operation and receipt, "
            "`after-mutation` ordering evidence, exact mandatory-field "
            "set, and owning-system unavailability evidence are "
            "independently valid",
            " ".join(reference.split()).lower(),
        )

        skill_text = SKILL.read_text(encoding="utf-8")
        skill = " ".join(skill_text.split()).lower()
        rebind_section_match = re.search(
            r"## Rebind Protected Policy Before External Mutations\n"
            r"(.*?)(?=\n## |\Z)",
            skill_text,
            re.DOTALL,
        )
        self.assertIsNotNone(rebind_section_match)
        rebind_section = rebind_section_match.group(1)
        rebind_compact = " ".join(rebind_section.split()).lower()
        self.assertLess(
            rebind_compact.index("when direct user input"),
            rebind_compact.index("before accepting"),
        )
        self.assertEqual(
            re.findall(r"(?m)^([0-9]+)\. ", rebind_section),
            ["1", "2", "3", "4"],
        )
        ordered_gate_anchors = (
            "1. require receiver-owned adoption",
            "2. bind the authorized operation",
            "3. bind the owning-system receipt",
            "4. before any `reconciliation-required` result",
        )
        gate_positions = [
            rebind_compact.index(anchor) for anchor in ordered_gate_anchors
        ]
        self.assertEqual(gate_positions, sorted(gate_positions))
        self.assertIn(
            "incomplete, unavailable, or ambiguous readback is "
            "`reconciliation-required` subject to gate 4, never success",
            rebind_compact,
        )
        for invariant in (
            "## rebind protected policy before external mutations",
            "capture a new protected policy revision",
            "do not encode that control-plane change as an evidence delta",
            "receiver-owned adoption of exact revision",
            "use `capability-unavailable` only when intent, mutation, and "
            "readback are all canonically clean",
            "any observed later state follows the fail-closed contract",
            "bind the authorized operation, destination, subject, cutoff",
            "every mandatory field",
            "immutable pre-write intent in the existing authorized intent store",
            "preallocate and retain both intent-store and owning-system operation ids",
            "never emulate an unavailable store",
            "owning-system receipt and exact object readback",
            "trust root outside receipt/evidence echoes",
            "`policy-drift`",
            "`reconciliation-required`",
            "exact private recovery identity and retained operation ids independently of the generic evidence map",
            "unknown outcomes remain sticky",
            "stable application id, immutable recovery ref, and both operation ids",
            "`checkpoint` and `protected policy application` sections",
            "never duplicate or relax those schema rules here",
            "unrelated pending evidence or skill handoff neither blocks",
            "nor proves receiver adoption",
        ):
            self.assertIn(invariant, skill)
        self.assertLess(len(skill_text.encode("utf-8")), 18000)
        for reference_only_detail in (
            "on the ninth, replace the inline cache",
            "codex.protected_policy_application_reconciliation.v1",
            "typed evidence count must be the exact json integer zero",
        ):
            self.assertNotIn(reference_only_detail, skill)

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
            "`codex.protected-policy-operation-json.v1`",
            "the encoding and is not part of `c`",
            "fixed ascii names",
            "never escape solidus",
            "without normalization and reject unpaired surrogates",
            "canonicalize parsed values: literal non-ascii and equivalent "
            "valid `\\uxxxx` or surrogate-pair input escapes produce the same `c`",
            "reject null, booleans, and all numbers",
            "opaque owning-system evidence ref",
            "envelope equality and receipt- or evidence-supplied provenance are never verification",
            "configured verifier whose trust root is selected outside the receipt and its evidence map",
            "independently obtains the normalized expectation or owning-system observation",
            "compares both the key-reference fingerprint and digest in constant time",
            "`field_ref` must not contain u+0000",
            "reject it before derivation",
            "normalized values remain arbitrary bytes",
            "caller-coordinated expectation, observation, and evidence map with matching envelopes is still invalid",
            "verified `missing` result",
            "observed fingerprint remains null",
            "absence never fabricates an hmac",
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
            "complete readback binds both the exact mutation operation id and mutation receipt",
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
            "`readback.object_ref` exactly equal to the recovered mutation result object",
            "reading another object with matching fields is not causal evidence",
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
            "must bind the active `readback-pending` recovery head",
            "reserve `terminal` for a closed result",
            "after receipt shape, closed states, bounded scalar formats, exact recovery-to-receipt application",
            "recomputed operation-policy, destination, and subject bindings",
            "unknown intent or mutation outcome takes precedence over every later semantic policy or evidence mismatch",
            "whose unknown state, recovery identity, or operation identity cannot be trusted remains `invalid`",
            "`protected_policy_application_state.active_count=0`",
            "inline entries or resolved active index form one append-only",
            "no duplicate application, revision, or recovery identity",
            "record binds the same application id and policy revision",
            "one closed record shape: reject missing or extra fields",
            "never substitute a smaller checkpoint projection",
            "state, policy fingerprint, receiver, store",
            "are bounded and non-null in every record",
            "owning-system operation namespace",
            "operation namespace and operation id is globally unique",
            "new record names the previous `recovery_ref` as its predecessor",
            "validate every intermediate recovery record",
            "required operation-policy fingerprint never change within the chain",
            "either operation id may be allocated once",
            "successor's `checkpoint_state` must be one exact edge",
            "checkpoint entry state must equal its recovery head's state",
            "treat every lifecycle, checkpoint-state, terminal-outcome, and reconciliation state enum as a bounded string",
            "reconciliation ref if and only if an unknown predecessor state advances",
            "any other reconciliation ref is unused or spurious",
            "state-bearing successor and remains valid without reusing the prior reconciliation",
            "newly appended application starts with a root recovery record",
            "closed monotonic graph",
            "an unknown state is sticky",
            "codex.protected_policy_application_reconciliation.v1",
            "later revision is appended without replacing",
            "only independently proven terminal evidence may remove an active entry",
            "active and retired identities are globally unique",
            "operation-namespace-plus-operation-id pair",
            "entry that was active in the immediately preceding checkpoint",
            "exact recovery head whose `checkpoint_state` is `terminal`",
            "retiring a nonterminal active entry appends exactly that one terminal successor",
            "terminal head itself carries the required reconciliation edge",
            "terminal receipt's reconciliation ref equals the head recovery record's `reconciliation_receipt_ref`",
            "resolve the terminal receipt's producer authority",
            "evaluate that application receipt independently",
            "through the same immutable evidence store",
            "a separate built-in or substituted recovery cannot authorize retirement",
            "never drop or reuse an application id, revision id, recovery ref",
            "never interpret a v1 checkpoint directly as v2",
            "migration consumes the complete v1 checkpoint root",
            "selects exactly one nested `targets[]` entry",
            "provisional singular `protected_policy_application` field",
            "codex.protected_policy_application_migration.v1",
            "canonical full-checkpoint fingerprint, exact target identity",
            "exact migrated checkpoint state",
            "non-json constants rejected",
            "exact cutoff-bound immutable evidence inventory",
            "typed evidence count is the exact json integer zero",
            "replaying either proof against another checkpoint or target fails closed",
            "validate the branch-specific migration or pre-feature proof ref as a bounded non-null scalar",
            "a null-key evidence-map entry never supplies a missing ref",
            "resolve every active and retired recovery chain to its root",
            "preserve that exact prefix",
            "missing proof, malformed legacy state",
            "never overload `current_contract_revision` or `pending_intervention`",
            "persist each immutable content-addressed private `recovery_ref` before its adoption, intent, mutation, or readback attempt",
            "unknown outcome permits only exact owning-system reconciliation, never a new write",
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
