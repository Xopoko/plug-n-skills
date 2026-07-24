#!/usr/bin/env python3
"""Validate local stacked-delivery evidence without changing external state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat as stat_module
import sys
from typing import Any, NoReturn, Sequence


SNAPSHOT_SCHEMA = "stacked_delivery.snapshot.v1"
HANDOFF_SCHEMA = "stacked_delivery.handoff.v1"
PREPARED_MUTATION_SCHEMA = "stacked_delivery.prepared_mutation_handoff.v1"
VALIDATION_SCHEMA = "stacked_delivery.validation.v1"
COMPARE_SCHEMA = "stacked_delivery.compare.v1"
NEXT_ACTION_SCHEMA = "stacked_delivery.next_action.v1"
HANDOFF_VALIDATION_SCHEMA = "stacked_delivery.handoff_validation.v1"
PREPARED_MUTATION_VALIDATION_SCHEMA = (
    "stacked_delivery.prepared_mutation_validation.v1"
)
ERROR_SCHEMA = "stacked_delivery.error.v1"

FORGE_MODES = {"sequential", "atomic-prefix"}
NODE_STATES = {"unlanded", "landed", "retargeted"}
PROOF_STATUSES = {"success", "failure", "running", "cancelled", "skipped"}
PREPARED_ACTION_KINDS = {"history-ref-update", "metadata-update"}
AUTHORITY_SOURCES = {"repository-policy", "user"}
LEASE_MODES = {"exact-remote-head"}
PATCH_EQUIVALENCE_METHODS = {"canonical-diff", "stable-patch-id"}
TREE_EQUIVALENCE_METHODS = {"canonical-tree-delta", "tree-object"}
TREE_EQUIVALENCE_PAIRS = {
    ("canonical-tree-delta", "node-delta"),
    ("tree-object", "result-tree"),
}
ATTRIBUTION_RELATIONS = {
    "preserve-author-and-committer",
    "preserve-author-allow-authorized-committer",
}
NEW_PREDECESSOR_KINDS = {"base", "node", "retarget"}
PROOF_GAP_BLOCKS = PREPARED_ACTION_KINDS | {"finalize"}
BACKUP_REF_PREFIX = "refs/stacked-delivery/backups/"
REQUIRED_EXCLUDED_ACTIONS = {
    "approve",
    "commit-content-edit",
    "delete-backup",
    "delete-source-ref",
    "merge",
    "resolve-review",
    "unrelated-ref-update",
}

MAX_INPUT_BYTES = 1024 * 1024
MAX_NODES = 64
MAX_PROOFS_PER_NODE = 32
MAX_TOTAL_PROOFS = 512
MAX_ACTIONS = MAX_NODES * 2
MAX_SCOPE_ACTIONS = 32
MAX_ISSUES = 128
MAX_IDENTIFIER_LENGTH = 128
MAX_BRANCH_LENGTH = 255

IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,127}$")
PRINTABLE_BRANCH_RE = re.compile(r"^[!-~]+$")
GIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

SNAPSHOT_KEYS = {
    "schema",
    "repository_id",
    "forge_adapter",
    "stack_id",
    "forge_mode",
    "base",
    "nodes",
}
BASE_KEYS = {"branch", "head_sha"}
NODE_KEYS = {
    "node_id",
    "change_id",
    "source_branch",
    "target_branch",
    "head_sha",
    "landing_head_sha",
    "parent_node_id",
    "expected_parent_head_sha",
    "worktree_id",
    "writer_id",
    "state",
    "proofs",
}
PROOF_KEYS = {
    "proof_id",
    "node_id",
    "node_head_sha",
    "dependency_head_sha",
    "status",
    "terminal",
    "superseded",
}
HANDOFF_KEYS = {
    "schema",
    "receiver_id",
    "snapshot_digest",
    "snapshot",
    "bindings",
}
PREPARED_MUTATION_KEYS = {
    "schema",
    "receiver_id",
    "snapshot_digest",
    "snapshot",
    "new_predecessor",
    "proof_wait_owner_ref",
    "authority",
    "attribution_policy",
    "proof_policy",
    "excluded_actions",
    "nodes",
    "actions",
    "history_receipts",
    "metadata_receipt",
}
PREPARED_AUTHORITY_KEYS = {
    "authority_id",
    "source",
    "evidence_id",
    "evidence_hash",
    "allowed_actions",
}
POLICY_KEYS = {"policy_id", "policy_hash"}
NEW_PREDECESSOR_KEYS = {
    "kind",
    "node_id",
    "source_ref",
    "head_sha",
    "evidence_id",
}
PREPARED_NODE_KEYS = {
    "node_id",
    "change_id",
    "source_branch",
    "old_head_sha",
    "new_head_sha",
    "old_parent_head_sha",
    "new_parent_head_sha",
    "patch_equivalence",
    "tree_equivalence",
    "attribution",
    "backup",
    "lease",
    "required_proof_surfaces",
    "proofs",
    "open_proof_gaps",
}
EQUIVALENCE_KEYS = {
    "method",
    "scope",
    "old_digest",
    "new_digest",
    "evidence_id",
    "equivalent",
}
ATTRIBUTION_KEYS = {
    "relation",
    "old_author_fingerprint",
    "new_author_fingerprint",
    "old_committer_fingerprint",
    "new_committer_fingerprint",
    "authorized_committer_fingerprint",
}
BACKUP_KEYS = {
    "ref",
    "expected_head_sha",
    "readback_head_sha",
    "confirmed",
}
LEASE_KEYS = {"remote_ref", "expected_remote_head_sha", "mode"}
PREPARED_PROOF_KEYS = {
    "proof_id",
    "surface_id",
    "node_head_sha",
    "dependency_head_sha",
    "status",
    "terminal",
    "superseded",
    "execution_nonempty",
}
OPEN_PROOF_GAP_KEYS = {
    "surface_id",
    "node_head_sha",
    "dependency_head_sha",
    "blocks_action",
    "evidence_id",
}
HISTORY_ACTION_KEYS = {
    "action_id",
    "kind",
    "node_id",
    "authority_id",
    "remote_ref",
    "expected_remote_head_sha",
    "new_head_sha",
    "backup_ref",
}
METADATA_ACTION_KEYS = {
    "action_id",
    "kind",
    "node_id",
    "authority_id",
    "old_target_branch",
    "new_target_branch",
    "expected_new_target_head_sha",
    "expected_node_head_sha",
}
HISTORY_RECEIPT_KEYS = {
    "receipt_id",
    "receipt_hash",
    "transaction_digest",
    "action_id",
    "node_id",
    "remote_ref",
    "expected_old_head_sha",
    "written_head_sha",
    "readback_head_sha",
    "backup_ref",
    "backup_readback_head_sha",
}
METADATA_RECEIPT_KEYS = {
    "receipt_id",
    "receipt_hash",
    "transaction_digest",
    "action_id",
    "node_id",
    "old_target_ref",
    "new_target_ref",
    "readback_target_ref",
    "expected_new_target_head_sha",
    "readback_new_target_head_sha",
    "expected_node_head_sha",
    "readback_node_head_sha",
}
BINDING_KEYS = {
    "node_id",
    "change_id",
    "head_sha",
    "proof_ids",
    "worktree_id",
    "writer_id",
    "receiver_id",
}

HELP_TEXT = f"""
All inputs are strict JSON objects. Unknown keys, duplicate JSON keys, mixed
shapes, unsafe identifiers, oversized collections, and uppercase or abbreviated
SHAs are rejected instead of normalized.

Snapshot schema ({SNAPSHOT_SCHEMA}):
  {{
    "schema": "{SNAPSHOT_SCHEMA}",
    "repository_id": "repository-1",
    "forge_adapter": "generic-v1",
    "stack_id": "stack-1",
    "forge_mode": "sequential" | "atomic-prefix",
    "base": {{"branch": "main", "head_sha": "<40-or-64-lower-hex>"}},
    "nodes": [<ordered bottom-to-top node>, ...]
  }}

Each node has exactly:
  node_id, change_id, source_branch, target_branch, head_sha,
  landing_head_sha (null until landed),
  parent_node_id (null only for the bottom node),
  expected_parent_head_sha, worktree_id and writer_id (both identifiers or
  both null), state, proofs.

Node state is "unlanded", "landed", or "retargeted". Landed nodes form a
bottom prefix and bind the resulting base integration head, including
merge-commit or squash results. After a non-empty landed prefix, the next node
is the only "retargeted" node and targets the current base. Other unlanded
nodes target their direct parent's source branch.

Each proof has exactly:
  proof_id, node_id, node_head_sha, dependency_head_sha, status, terminal,
  superseded.
Only status "success", terminal true, superseded false, and exact current
node/dependency heads are accepted. Proof IDs are unique across the stack.

Handoff schema ({HANDOFF_SCHEMA}):
  {{
    "schema": "{HANDOFF_SCHEMA}",
    "receiver_id": "receiver-1",
    "snapshot_digest": "<sha256-of-canonical-snapshot>",
    "snapshot": <snapshot object>,
    "bindings": [{{
      "node_id": "...", "change_id": "...", "head_sha": "...",
      "proof_ids": ["..."], "worktree_id": "..." | null,
      "writer_id": "..." | null,
      "receiver_id": "receiver-1"
    }}, ...]
  }}

Prepared mutation handoff schema ({PREPARED_MUTATION_SCHEMA}) is an additive
strict companion to the current-state handoff. It binds the old snapshot,
receiver, explicit predecessor, nullable external proof-wait owner, authority
and exclusions, opaque proof and attribution policy bindings, per-node old/new
history plus equivalence, attribution, backup, lease, proof or gap evidence,
separate ordered history-ref and optional metadata actions, and a bounded
content-addressed history-receipt prefix. See
references/prepared-mutation-handoff.md for the exact field contract.

The program reads only the named input files. It never invokes a forge, git,
network command, subprocess, or file-writing operation. Output is bounded JSON.
Exit status: 0 pass/ready/complete, 2 gate or drift failure, 1 malformed or
unreadable input.
"""


class InputError(ValueError):
    """Raised when an input cannot be read or does not match the strict shape."""


class JsonArgumentParser(argparse.ArgumentParser):
    """Turn command-line usage errors into the JSON error contract."""

    def error(self, message: str) -> NoReturn:
        raise InputError("argument error: " + message)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_digest(value: Any) -> str:
    """Return the SHA-256 digest of canonical JSON."""

    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> NoReturn:
    raise InputError("non-finite JSON number is not allowed")


def _reject_json_number(value: str) -> NoReturn:
    raise InputError("JSON numbers are not used by this schema")


def _read_text(path: str) -> str:
    try:
        if path == "-":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
            descriptor = os.open(path, flags)
            try:
                mode = os.fstat(descriptor).st_mode
                if not stat_module.S_ISREG(mode):
                    raise InputError("input must be a regular file")
                with os.fdopen(descriptor, "rb") as stream:
                    descriptor = -1
                    raw = stream.read(MAX_INPUT_BYTES + 1)
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
    except InputError:
        raise
    except OSError as exc:
        raise InputError("input is unreadable") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise InputError("input exceeds the byte limit")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError("input is not valid UTF-8") from exc


def load_json_file(path: str) -> Any:
    """Read one bounded strict-JSON document."""

    try:
        return json.loads(
            _read_text(path),
            object_pairs_hook=_strict_object,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_number,
            parse_int=_reject_json_number,
        )
    except InputError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise InputError("input is not valid JSON") from exc
    except (MemoryError, RecursionError) as exc:
        raise InputError("input JSON is too deeply nested") from exc


def _expect_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InputError(f"{label} must be an object")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        unknown = sorted(actual - keys)
        if missing:
            raise InputError(f"{label} is missing required fields")
        if unknown:
            raise InputError(f"{label} contains unknown fields")
    return value


def _identifier(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > MAX_IDENTIFIER_LENGTH
        or not IDENTIFIER_RE.fullmatch(value)
    ):
        raise InputError(f"{label} must be a safe identifier")
    return value


def _optional_identifier(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, label)


def _branch(value: Any, label: str) -> str:
    components = value.split("/") if isinstance(value, str) else []
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_BRANCH_LENGTH
        or not PRINTABLE_BRANCH_RE.fullmatch(value)
        or value.startswith("-")
        or value.endswith(".")
        or ".." in value
        or "//" in value
        or "@{" in value
        or any(character in "~^:?*[\\" for character in value)
        or any(
            not component or component.startswith(".") or component.endswith(".lock")
            for component in components
        )
    ):
        raise InputError(f"{label} must be a safe branch name")
    return value


def _git_ref(value: Any, label: str) -> str:
    ref = _branch(value, label)
    if not ref.startswith("refs/"):
        raise InputError(f"{label} must be a full refs/ Git ref")
    return ref


def _head_branch(value: Any, label: str) -> str:
    branch = _branch(value, label)
    if branch.startswith("refs/") and not branch.startswith("refs/heads/"):
        raise InputError(f"{label} must name a Git branch head")
    return branch


def _git_head_ref(value: Any, label: str) -> str:
    ref = _git_ref(value, label)
    if not ref.startswith("refs/heads/"):
        raise InputError(f"{label} must be a full refs/heads/ Git ref")
    return ref


def _git_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not GIT_SHA_RE.fullmatch(value):
        raise InputError(f"{label} must be an exact lowercase Git SHA")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise InputError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _boolean(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise InputError(f"{label} must be a boolean")
    return value


def _array(value: Any, label: str, limit: int) -> list[Any]:
    if not isinstance(value, list):
        raise InputError(f"{label} must be an array")
    if len(value) > limit:
        raise InputError(f"{label} exceeds its collection limit")
    return value


def _identifier_array(
    value: Any,
    label: str,
    limit: int,
    *,
    nonempty: bool = False,
) -> list[str]:
    raw = _array(value, label, limit)
    result = [
        _identifier(item, f"{label}[{index}]") for index, item in enumerate(raw)
    ]
    if nonempty and not result:
        raise InputError(f"{label} must not be empty")
    if result != sorted(set(result)):
        raise InputError(f"{label} must be sorted and unique")
    return result


def _parse_proof(value: Any, node_index: int, proof_index: int) -> dict[str, Any]:
    label = f"nodes[{node_index}].proofs[{proof_index}]"
    raw = _expect_object(value, PROOF_KEYS, label)
    status = raw["status"]
    if not isinstance(status, str) or status not in PROOF_STATUSES:
        raise InputError(f"{label}.status is unsupported")
    return {
        "proof_id": _identifier(raw["proof_id"], f"{label}.proof_id"),
        "node_id": _identifier(raw["node_id"], f"{label}.node_id"),
        "node_head_sha": _git_sha(raw["node_head_sha"], f"{label}.node_head_sha"),
        "dependency_head_sha": _git_sha(
            raw["dependency_head_sha"], f"{label}.dependency_head_sha"
        ),
        "status": status,
        "terminal": _boolean(raw["terminal"], f"{label}.terminal"),
        "superseded": _boolean(raw["superseded"], f"{label}.superseded"),
    }


def _parse_node(value: Any, index: int) -> dict[str, Any]:
    label = f"nodes[{index}]"
    raw = _expect_object(value, NODE_KEYS, label)
    parent = raw["parent_node_id"]
    if parent is not None:
        parent = _identifier(parent, f"{label}.parent_node_id")
    landing_head = raw["landing_head_sha"]
    if landing_head is not None:
        landing_head = _git_sha(landing_head, f"{label}.landing_head_sha")
    state = raw["state"]
    if not isinstance(state, str) or state not in NODE_STATES:
        raise InputError(f"{label}.state is unsupported")
    raw_proofs = _array(raw["proofs"], f"{label}.proofs", MAX_PROOFS_PER_NODE)
    proofs = [
        _parse_proof(proof, index, proof_index)
        for proof_index, proof in enumerate(raw_proofs)
    ]
    return {
        "node_id": _identifier(raw["node_id"], f"{label}.node_id"),
        "change_id": _identifier(raw["change_id"], f"{label}.change_id"),
        "source_branch": _branch(raw["source_branch"], f"{label}.source_branch"),
        "target_branch": _branch(raw["target_branch"], f"{label}.target_branch"),
        "head_sha": _git_sha(raw["head_sha"], f"{label}.head_sha"),
        "landing_head_sha": landing_head,
        "parent_node_id": parent,
        "expected_parent_head_sha": _git_sha(
            raw["expected_parent_head_sha"],
            f"{label}.expected_parent_head_sha",
        ),
        "worktree_id": _optional_identifier(raw["worktree_id"], f"{label}.worktree_id"),
        "writer_id": _optional_identifier(raw["writer_id"], f"{label}.writer_id"),
        "state": state,
        "proofs": proofs,
    }


def parse_snapshot(value: Any) -> dict[str, Any]:
    """Parse and normalize only the documented exact snapshot shape."""

    raw = _expect_object(value, SNAPSHOT_KEYS, "snapshot")
    if raw["schema"] != SNAPSHOT_SCHEMA:
        raise InputError("snapshot schema is unsupported")
    mode = raw["forge_mode"]
    if not isinstance(mode, str) or mode not in FORGE_MODES:
        raise InputError("snapshot forge_mode is unsupported")
    base_raw = _expect_object(raw["base"], BASE_KEYS, "snapshot.base")
    raw_nodes = _array(raw["nodes"], "snapshot.nodes", MAX_NODES)
    if not raw_nodes:
        raise InputError("snapshot.nodes must not be empty")
    nodes = [_parse_node(node, index) for index, node in enumerate(raw_nodes)]
    proof_count = sum(len(node["proofs"]) for node in nodes)
    if proof_count > MAX_TOTAL_PROOFS:
        raise InputError("snapshot proof count exceeds the collection limit")
    return {
        "schema": SNAPSHOT_SCHEMA,
        "repository_id": _identifier(raw["repository_id"], "snapshot.repository_id"),
        "forge_adapter": _identifier(raw["forge_adapter"], "snapshot.forge_adapter"),
        "stack_id": _identifier(raw["stack_id"], "snapshot.stack_id"),
        "forge_mode": mode,
        "base": {
            "branch": _branch(base_raw["branch"], "snapshot.base.branch"),
            "head_sha": _git_sha(base_raw["head_sha"], "snapshot.base.head_sha"),
        },
        "nodes": nodes,
    }


def _issue(
    issues: list[dict[str, Any]],
    code: str,
    *,
    node_id: str | None = None,
    proof_id: str | None = None,
    action_id: str | None = None,
    surface_id: str | None = None,
    field: str | None = None,
) -> None:
    if len(issues) >= MAX_ISSUES:
        return
    item: dict[str, Any] = {"code": code}
    if node_id is not None:
        item["node_id"] = node_id
    if proof_id is not None:
        item["proof_id"] = proof_id
    if action_id is not None:
        item["action_id"] = action_id
    if surface_id is not None:
        item["surface_id"] = surface_id
    if field is not None:
        item["field"] = field
    issues.append(item)


def _landed_prefix_length(nodes: list[dict[str, Any]]) -> int:
    length = 0
    for node in nodes:
        if node["state"] != "landed":
            break
        length += 1
    return length


def _topology_issues(snapshot: dict[str, Any], issues: list[dict[str, Any]]) -> int:
    nodes = snapshot["nodes"]
    base = snapshot["base"]
    landed_count = _landed_prefix_length(nodes)

    if nodes[0]["parent_node_id"] is not None:
        _issue(issues, "bottom_parent_not_null", node_id=nodes[0]["node_id"])
    if nodes[0]["target_branch"] != base["branch"]:
        _issue(issues, "bottom_target_mismatch", node_id=nodes[0]["node_id"])

    for index in range(1, len(nodes)):
        node = nodes[index]
        parent = nodes[index - 1]
        if node["parent_node_id"] != parent["node_id"]:
            _issue(issues, "nonlinear_parent", node_id=node["node_id"])

    id_to_parent = {node["node_id"]: node["parent_node_id"] for node in nodes}
    for node in nodes:
        seen: set[str] = set()
        current: str | None = node["node_id"]
        while current is not None and current in id_to_parent:
            if current in seen:
                _issue(issues, "parent_cycle", node_id=node["node_id"])
                break
            seen.add(current)
            current = id_to_parent[current]

    child_counts: dict[str, int] = {}
    node_ids = set(id_to_parent)
    for node in nodes[1:]:
        parent_id = node["parent_node_id"]
        if parent_id is not None:
            child_counts[parent_id] = child_counts.get(parent_id, 0) + 1
            if parent_id not in node_ids:
                _issue(issues, "unknown_parent", node_id=node["node_id"])
    for parent_id, count in child_counts.items():
        if count > 1:
            _issue(issues, "parent_fork", node_id=parent_id)

    if any(node["state"] == "landed" for node in nodes[landed_count:]):
        _issue(issues, "out_of_order_landed")

    retargeted_indexes = [
        index for index, node in enumerate(nodes) if node["state"] == "retargeted"
    ]
    if landed_count == 0:
        for index in retargeted_indexes:
            _issue(
                issues,
                "retarget_without_landed_prefix",
                node_id=nodes[index]["node_id"],
            )
    elif landed_count < len(nodes):
        candidate = nodes[landed_count]
        if candidate["state"] != "retargeted":
            _issue(
                issues,
                "missing_retarget_after_landing",
                node_id=candidate["node_id"],
            )
        for index in retargeted_indexes:
            if index != landed_count:
                _issue(
                    issues,
                    "retarget_position_mismatch",
                    node_id=nodes[index]["node_id"],
                )
        for node in nodes[landed_count + 1 :]:
            if node["state"] != "unlanded":
                _issue(
                    issues,
                    "state_sequence_mismatch",
                    node_id=node["node_id"],
                )
    elif retargeted_indexes:
        for index in retargeted_indexes:
            _issue(
                issues,
                "retarget_position_mismatch",
                node_id=nodes[index]["node_id"],
            )

    for node in nodes:
        if node["state"] == "landed":
            if node["landing_head_sha"] is None:
                _issue(
                    issues,
                    "landed_head_missing",
                    node_id=node["node_id"],
                )
            if node["worktree_id"] is not None or node["writer_id"] is not None:
                _issue(
                    issues,
                    "landed_ownership_not_released",
                    node_id=node["node_id"],
                )
        elif node["landing_head_sha"] is not None:
            _issue(
                issues,
                "unexpected_landing_head",
                node_id=node["node_id"],
            )

    if landed_count:
        landed_tip = nodes[landed_count - 1]
        if base["head_sha"] != landed_tip["landing_head_sha"]:
            _issue(
                issues,
                "landed_base_head_mismatch",
                node_id=landed_tip["node_id"],
            )

    if landed_count == 0:
        if nodes[0]["expected_parent_head_sha"] != base["head_sha"]:
            _issue(
                issues,
                "bottom_expected_head_mismatch",
                node_id=nodes[0]["node_id"],
            )

    for index in range(1, len(nodes)):
        node = nodes[index]
        parent = nodes[index - 1]
        if index < landed_count and snapshot["forge_mode"] == "sequential":
            expected_target = base["branch"]
            expected_head = parent["landing_head_sha"]
        elif landed_count and index == landed_count:
            expected_target = base["branch"]
            expected_head = base["head_sha"]
        else:
            expected_target = parent["source_branch"]
            expected_head = parent["head_sha"]
        if node["target_branch"] != expected_target:
            _issue(issues, "target_branch_mismatch", node_id=node["node_id"])
        if node["expected_parent_head_sha"] != expected_head:
            _issue(
                issues,
                "expected_parent_head_mismatch",
                node_id=node["node_id"],
            )
    return landed_count


def snapshot_issues(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return bounded semantic gate failures for a parsed snapshot."""

    issues: list[dict[str, Any]] = []
    nodes = snapshot["nodes"]

    uniqueness_fields = (
        ("node_id", "duplicate_node_id"),
        ("change_id", "duplicate_change_id"),
        ("source_branch", "duplicate_source_branch"),
    )
    for field, code in uniqueness_fields:
        seen: set[str] = set()
        for node in nodes:
            value = node[field]
            if value in seen:
                _issue(issues, code, node_id=node["node_id"], field=field)
            seen.add(value)

    active_worktrees: set[str] = set()
    for node in nodes:
        worktree_id = node["worktree_id"]
        writer_id = node["writer_id"]
        if (worktree_id is None) != (writer_id is None):
            _issue(
                issues,
                "incomplete_ownership_binding",
                node_id=node["node_id"],
                field="worktree_id",
            )
        if worktree_id is not None:
            if worktree_id in active_worktrees:
                _issue(
                    issues,
                    "duplicate_active_worktree",
                    node_id=node["node_id"],
                    field="worktree_id",
                )
            active_worktrees.add(worktree_id)
    for node in nodes:
        if node["source_branch"] == snapshot["base"]["branch"]:
            _issue(
                issues,
                "source_branch_conflicts_base",
                node_id=node["node_id"],
                field="source_branch",
            )

    landed_count = _topology_issues(snapshot, issues)

    seen_proofs: set[str] = set()
    for index, node in enumerate(nodes):
        if index < landed_count:
            dependency_head = node["expected_parent_head_sha"]
        elif index == 0 or (landed_count and index == landed_count):
            dependency_head = snapshot["base"]["head_sha"]
        else:
            dependency_head = nodes[index - 1]["head_sha"]
        for proof in node["proofs"]:
            proof_id = proof["proof_id"]
            if proof_id in seen_proofs:
                _issue(
                    issues,
                    "duplicate_proof_id",
                    node_id=node["node_id"],
                    proof_id=proof_id,
                )
            seen_proofs.add(proof_id)
            if proof["node_id"] != node["node_id"]:
                _issue(
                    issues,
                    "proof_node_mismatch",
                    node_id=node["node_id"],
                    proof_id=proof_id,
                )
            if proof["node_head_sha"] != node["head_sha"]:
                _issue(
                    issues,
                    "proof_node_head_stale",
                    node_id=node["node_id"],
                    proof_id=proof_id,
                )
            if proof["dependency_head_sha"] != dependency_head:
                _issue(
                    issues,
                    "proof_dependency_head_stale",
                    node_id=node["node_id"],
                    proof_id=proof_id,
                )
            if proof["status"] != "success":
                _issue(
                    issues,
                    "proof_not_successful",
                    node_id=node["node_id"],
                    proof_id=proof_id,
                )
            if proof["terminal"] is not True:
                _issue(
                    issues,
                    "proof_not_terminal",
                    node_id=node["node_id"],
                    proof_id=proof_id,
                )
            if proof["superseded"] is not False:
                _issue(
                    issues,
                    "proof_superseded",
                    node_id=node["node_id"],
                    proof_id=proof_id,
                )
    return issues


def validate_snapshot_data(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse a snapshot and build its validation result."""

    snapshot = parse_snapshot(value)
    issues = snapshot_issues(snapshot)
    proof_count = sum(len(node["proofs"]) for node in snapshot["nodes"])
    result = {
        "schema": VALIDATION_SCHEMA,
        "status": "pass" if not issues else "fail",
        "snapshot_digest": stable_digest(snapshot),
        "repository_id": snapshot["repository_id"],
        "forge_adapter": snapshot["forge_adapter"],
        "stack_id": snapshot["stack_id"],
        "node_count": len(snapshot["nodes"]),
        "proof_count": proof_count,
        "violations": issues,
    }
    return snapshot, result


def _change(
    changes: list[dict[str, Any]],
    kind: str,
    *,
    field: str,
    before: Any,
    after: Any,
    node_id: str | None = None,
) -> None:
    if len(changes) >= MAX_ISSUES:
        return
    item: dict[str, Any] = {
        "kind": kind,
        "field": field,
        "before": before,
        "after": after,
    }
    if node_id is not None:
        item["node_id"] = node_id
    changes.append(item)


def compare_snapshot_data(
    before_value: Any, after_value: Any
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Compare two strict snapshots and fail closed on topology or drift."""

    before = parse_snapshot(before_value)
    after = parse_snapshot(after_value)
    before_issues = snapshot_issues(before)
    after_issues = snapshot_issues(after)

    topology_changes: list[dict[str, Any]] = []
    branch_drift: list[dict[str, Any]] = []
    head_drift: list[dict[str, Any]] = []
    state_changes: list[dict[str, Any]] = []
    proof_changes: list[dict[str, Any]] = []
    changed_ancestors: list[dict[str, Any]] = []
    cause_indexes: list[tuple[int, str, bool]] = []

    for field in ("repository_id", "forge_adapter"):
        if before[field] != after[field]:
            _change(
                topology_changes,
                "identity",
                field=field,
                before=before[field],
                after=after[field],
            )
            cause_indexes.append((-1, "scope:" + field, True))
    if before["stack_id"] != after["stack_id"]:
        _change(
            topology_changes,
            "identity",
            field="stack_id",
            before=before["stack_id"],
            after=after["stack_id"],
        )
        cause_indexes.append((-1, "topology", True))
    if before["forge_mode"] != after["forge_mode"]:
        _change(
            topology_changes,
            "topology",
            field="forge_mode",
            before=before["forge_mode"],
            after=after["forge_mode"],
        )
        cause_indexes.append((-1, "topology", True))
    if before["base"]["branch"] != after["base"]["branch"]:
        _change(
            branch_drift,
            "branch",
            field="base.branch",
            before=before["base"]["branch"],
            after=after["base"]["branch"],
        )
        changed_ancestors.append(
            {"kind": "base", "fields": ["branch"], "node_id": None}
        )
        cause_indexes.append((-1, "base-branch", False))
    if before["base"]["head_sha"] != after["base"]["head_sha"]:
        _change(
            head_drift,
            "head",
            field="base.head_sha",
            before=before["base"]["head_sha"],
            after=after["base"]["head_sha"],
        )
        changed_ancestors.append(
            {"kind": "base", "fields": ["head_sha"], "node_id": None}
        )
        cause_indexes.append((-1, "base-head", False))

    before_ids = [node["node_id"] for node in before["nodes"]]
    after_ids = [node["node_id"] for node in after["nodes"]]
    if before_ids != after_ids:
        _change(
            topology_changes,
            "topology",
            field="node_order",
            before=before_ids,
            after=after_ids,
        )
        cause_indexes.append((-1, "topology", True))

    shared_count = min(len(before["nodes"]), len(after["nodes"]))
    for index in range(shared_count):
        old = before["nodes"][index]
        new = after["nodes"][index]
        node_id = new["node_id"]
        if old["node_id"] != new["node_id"]:
            continue
        for field in (
            "change_id",
            "parent_node_id",
            "worktree_id",
            "writer_id",
        ):
            if old[field] != new[field]:
                _change(
                    topology_changes,
                    "identity" if field != "parent_node_id" else "topology",
                    field=field,
                    before=old[field],
                    after=new[field],
                    node_id=node_id,
                )
                cause_indexes.append((index, "topology", True))
        for field in ("source_branch", "target_branch"):
            if old[field] != new[field]:
                _change(
                    branch_drift,
                    "branch",
                    field=field,
                    before=old[field],
                    after=new[field],
                    node_id=node_id,
                )
                changed_ancestors.append(
                    {
                        "kind": "node",
                        "node_id": node_id,
                        "fields": [field],
                    }
                )
                cause_indexes.append((index, node_id, True))
        if old["head_sha"] != new["head_sha"]:
            _change(
                head_drift,
                "head",
                field="head_sha",
                before=old["head_sha"],
                after=new["head_sha"],
                node_id=node_id,
            )
            changed_ancestors.append(
                {
                    "kind": "node",
                    "node_id": node_id,
                    "fields": ["head_sha"],
                }
            )
            cause_indexes.append((index, node_id, True))
        if old["landing_head_sha"] != new["landing_head_sha"]:
            _change(
                head_drift,
                "integration",
                field="landing_head_sha",
                before=old["landing_head_sha"],
                after=new["landing_head_sha"],
                node_id=node_id,
            )
            changed_ancestors.append(
                {
                    "kind": "node",
                    "node_id": node_id,
                    "fields": ["landing_head_sha"],
                }
            )
            cause_indexes.append((index, node_id, True))
        if old["expected_parent_head_sha"] != new["expected_parent_head_sha"]:
            _change(
                head_drift,
                "dependency",
                field="expected_parent_head_sha",
                before=old["expected_parent_head_sha"],
                after=new["expected_parent_head_sha"],
                node_id=node_id,
            )
            changed_ancestors.append(
                {
                    "kind": "node",
                    "node_id": node_id,
                    "fields": ["expected_parent_head_sha"],
                }
            )
            cause_indexes.append((index, node_id, True))
        if old["state"] != new["state"]:
            _change(
                state_changes,
                "state",
                field="state",
                before=old["state"],
                after=new["state"],
                node_id=node_id,
            )
            cause_indexes.append((index, "state:" + node_id, True))
        if old["proofs"] != new["proofs"]:
            proof_changes.append({"node_id": node_id})
            cause_indexes.append((index, "proof:" + node_id, True))

    invalidated: list[dict[str, Any]] = []
    for index, node in enumerate(after["nodes"]):
        causes: list[str] = []
        for cause_index, cause, include_self in cause_indexes:
            if index > cause_index or (include_self and index == cause_index):
                if cause not in causes:
                    causes.append(cause)
        if causes:
            invalidated.append({"node_id": node["node_id"], "caused_by": causes})

    violations: list[dict[str, Any]] = []
    for issue in before_issues:
        prefixed = dict(issue)
        prefixed["snapshot"] = "before"
        violations.append(prefixed)
    for issue in after_issues:
        if len(violations) >= MAX_ISSUES:
            break
        prefixed = dict(issue)
        prefixed["snapshot"] = "after"
        violations.append(prefixed)

    failed = bool(
        violations
        or topology_changes
        or branch_drift
        or head_drift
        or state_changes
        or proof_changes
    )
    result = {
        "schema": COMPARE_SCHEMA,
        "status": "fail" if failed else "pass",
        "repository_id": after["repository_id"],
        "forge_adapter": after["forge_adapter"],
        "stack_id": after["stack_id"],
        "before_digest": stable_digest(before),
        "after_digest": stable_digest(after),
        "topology_changes": topology_changes,
        "branch_drift": branch_drift,
        "head_drift": head_drift,
        "changed_ancestors": changed_ancestors,
        "invalidated_descendants": invalidated,
        "state_changes": state_changes,
        "proof_changes": proof_changes,
        "violations": violations,
    }
    return before, after, result


def _action_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": node["node_id"],
        "change_id": node["change_id"],
        "source_branch": node["source_branch"],
        "target_branch": node["target_branch"],
        "head_sha": node["head_sha"],
        "expected_parent_head_sha": node["expected_parent_head_sha"],
        "proof_ids": [proof["proof_id"] for proof in node["proofs"]],
    }


def next_action_data(value: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return only a structured, dependency-safe next landing action."""

    snapshot = parse_snapshot(value)
    issues = snapshot_issues(snapshot)
    base_result: dict[str, Any] = {
        "schema": NEXT_ACTION_SCHEMA,
        "repository_id": snapshot["repository_id"],
        "forge_adapter": snapshot["forge_adapter"],
        "stack_id": snapshot["stack_id"],
        "forge_mode": snapshot["forge_mode"],
        "snapshot_digest": stable_digest(snapshot),
    }
    if issues:
        result = dict(base_result)
        result.update(
            {
                "status": "blocked",
                "action": None,
                "nodes": [],
                "reasons": ["snapshot_gate_failed"],
                "violations": issues,
            }
        )
        return snapshot, result

    landed_count = _landed_prefix_length(snapshot["nodes"])
    if landed_count == len(snapshot["nodes"]):
        result = dict(base_result)
        result.update(
            {
                "status": "complete",
                "action": None,
                "nodes": [],
                "reasons": [],
                "violations": [],
            }
        )
        return snapshot, result

    candidate = snapshot["nodes"][landed_count]
    if not candidate["proofs"]:
        result = dict(base_result)
        result.update(
            {
                "status": "blocked",
                "action": None,
                "nodes": [],
                "reasons": ["lowest_unlanded_node_has_no_current_proof"],
                "violations": [],
            }
        )
        return snapshot, result

    selected = [candidate]
    if snapshot["forge_mode"] == "atomic-prefix":
        for node in snapshot["nodes"][landed_count + 1 :]:
            if not node["proofs"]:
                break
            selected.append(node)

    result = dict(base_result)
    result.update(
        {
            "status": "ready",
            "action": "land",
            "nodes": [_action_node(node) for node in selected],
            "reasons": [],
            "violations": [],
        }
    )
    return snapshot, result


def _parse_binding(value: Any, index: int) -> dict[str, Any]:
    label = f"bindings[{index}]"
    raw = _expect_object(value, BINDING_KEYS, label)
    raw_proof_ids = _array(raw["proof_ids"], f"{label}.proof_ids", MAX_PROOFS_PER_NODE)
    proof_ids = [
        _identifier(item, f"{label}.proof_ids[{proof_index}]")
        for proof_index, item in enumerate(raw_proof_ids)
    ]
    return {
        "node_id": _identifier(raw["node_id"], f"{label}.node_id"),
        "change_id": _identifier(raw["change_id"], f"{label}.change_id"),
        "head_sha": _git_sha(raw["head_sha"], f"{label}.head_sha"),
        "proof_ids": proof_ids,
        "worktree_id": _optional_identifier(raw["worktree_id"], f"{label}.worktree_id"),
        "writer_id": _optional_identifier(raw["writer_id"], f"{label}.writer_id"),
        "receiver_id": _identifier(raw["receiver_id"], f"{label}.receiver_id"),
    }


def parse_handoff(value: Any) -> dict[str, Any]:
    """Parse the exact self-contained handoff receipt shape."""

    raw = _expect_object(value, HANDOFF_KEYS, "handoff")
    if raw["schema"] != HANDOFF_SCHEMA:
        raise InputError("handoff schema is unsupported")
    bindings_raw = _array(raw["bindings"], "handoff.bindings", MAX_NODES)
    return {
        "schema": HANDOFF_SCHEMA,
        "receiver_id": _identifier(raw["receiver_id"], "handoff.receiver_id"),
        "snapshot_digest": _sha256(raw["snapshot_digest"], "handoff.snapshot_digest"),
        "snapshot": parse_snapshot(raw["snapshot"]),
        "bindings": [
            _parse_binding(binding, index) for index, binding in enumerate(bindings_raw)
        ],
    }


def handoff_issues(handoff: dict[str, Any]) -> list[dict[str, Any]]:
    """Return semantic binding failures for a parsed handoff."""

    issues = snapshot_issues(handoff["snapshot"])
    snapshot = handoff["snapshot"]
    bindings = handoff["bindings"]
    receiver_id = handoff["receiver_id"]

    if handoff["snapshot_digest"] != stable_digest(snapshot):
        _issue(issues, "stale_snapshot_digest")
    if len(bindings) != len(snapshot["nodes"]):
        _issue(issues, "binding_count_mismatch")

    unique_fields = (("node_id", "duplicate_binding_node_id"),)
    for field, code in unique_fields:
        seen: set[str] = set()
        for binding in bindings:
            value = binding[field]
            if value in seen:
                _issue(issues, code, node_id=binding["node_id"], field=field)
            seen.add(value)

    active_worktrees: set[str] = set()
    for binding in bindings:
        worktree_id = binding["worktree_id"]
        writer_id = binding["writer_id"]
        if (worktree_id is None) != (writer_id is None):
            _issue(
                issues,
                "incomplete_binding_ownership",
                node_id=binding["node_id"],
                field="worktree_id",
            )
        if worktree_id is not None:
            if worktree_id in active_worktrees:
                _issue(
                    issues,
                    "duplicate_binding_active_worktree",
                    node_id=binding["node_id"],
                    field="worktree_id",
                )
            active_worktrees.add(worktree_id)

    for index in range(min(len(bindings), len(snapshot["nodes"]))):
        binding = bindings[index]
        node = snapshot["nodes"][index]
        node_id = node["node_id"]
        for field, code in (
            ("node_id", "binding_node_mismatch"),
            ("change_id", "binding_change_mismatch"),
            ("head_sha", "binding_head_mismatch"),
            ("worktree_id", "binding_worktree_mismatch"),
            ("writer_id", "binding_writer_mismatch"),
        ):
            if binding[field] != node[field]:
                _issue(issues, code, node_id=node_id, field=field)
        expected_proof_ids = [proof["proof_id"] for proof in node["proofs"]]
        if binding["proof_ids"] != expected_proof_ids:
            _issue(issues, "binding_proof_mismatch", node_id=node_id)
        if len(set(binding["proof_ids"])) != len(binding["proof_ids"]):
            _issue(issues, "duplicate_binding_proof_id", node_id=node_id)
        if binding["receiver_id"] != receiver_id:
            _issue(issues, "binding_receiver_mismatch", node_id=node_id)
    return issues[:MAX_ISSUES]


def validate_handoff_data(
    value: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse a handoff and build its validation result."""

    handoff = parse_handoff(value)
    issues = handoff_issues(handoff)
    result = {
        "schema": HANDOFF_VALIDATION_SCHEMA,
        "status": "pass" if not issues else "fail",
        "repository_id": handoff["snapshot"]["repository_id"],
        "forge_adapter": handoff["snapshot"]["forge_adapter"],
        "stack_id": handoff["snapshot"]["stack_id"],
        "receiver_id": handoff["receiver_id"],
        "snapshot_digest": stable_digest(handoff["snapshot"]),
        "handoff_digest": stable_digest(handoff),
        "node_count": len(handoff["snapshot"]["nodes"]),
        "violations": issues,
    }
    return handoff, result


def _parse_prepared_authority(value: Any) -> dict[str, Any]:
    raw = _expect_object(value, PREPARED_AUTHORITY_KEYS, "authority")
    source = raw["source"]
    if not isinstance(source, str) or source not in AUTHORITY_SOURCES:
        raise InputError("authority.source is unsupported")
    allowed_actions = _identifier_array(
        raw["allowed_actions"],
        "authority.allowed_actions",
        len(PREPARED_ACTION_KINDS),
        nonempty=True,
    )
    if any(action not in PREPARED_ACTION_KINDS for action in allowed_actions):
        raise InputError("authority.allowed_actions contains an unsupported action")
    return {
        "authority_id": _identifier(raw["authority_id"], "authority.authority_id"),
        "source": source,
        "evidence_id": _identifier(raw["evidence_id"], "authority.evidence_id"),
        "evidence_hash": _sha256(raw["evidence_hash"], "authority.evidence_hash"),
        "allowed_actions": allowed_actions,
    }


def _parse_policy(value: Any, label: str) -> dict[str, Any]:
    raw = _expect_object(value, POLICY_KEYS, label)
    return {
        "policy_id": _identifier(raw["policy_id"], f"{label}.policy_id"),
        "policy_hash": _sha256(raw["policy_hash"], f"{label}.policy_hash"),
    }


def _parse_new_predecessor(value: Any) -> dict[str, Any]:
    label = "prepared.new_predecessor"
    raw = _expect_object(value, NEW_PREDECESSOR_KEYS, label)
    kind = raw["kind"]
    if not isinstance(kind, str) or kind not in NEW_PREDECESSOR_KINDS:
        raise InputError(f"{label}.kind is unsupported")
    return {
        "kind": kind,
        "node_id": _optional_identifier(raw["node_id"], f"{label}.node_id"),
        "source_ref": _git_head_ref(raw["source_ref"], f"{label}.source_ref"),
        "head_sha": _git_sha(raw["head_sha"], f"{label}.head_sha"),
        "evidence_id": _identifier(raw["evidence_id"], f"{label}.evidence_id"),
    }


def _parse_equivalence(
    value: Any,
    label: str,
    methods: set[str],
    scopes: set[str],
    allowed_pairs: set[tuple[str, str]],
) -> dict[str, Any]:
    raw = _expect_object(value, EQUIVALENCE_KEYS, label)
    method = raw["method"]
    scope = raw["scope"]
    if not isinstance(method, str) or method not in methods:
        raise InputError(f"{label}.method is unsupported")
    if not isinstance(scope, str) or scope not in scopes:
        raise InputError(f"{label}.scope is unsupported")
    if (method, scope) not in allowed_pairs:
        raise InputError(f"{label} method and scope are incompatible")
    return {
        "method": method,
        "scope": scope,
        "old_digest": _sha256(raw["old_digest"], f"{label}.old_digest"),
        "new_digest": _sha256(raw["new_digest"], f"{label}.new_digest"),
        "evidence_id": _identifier(raw["evidence_id"], f"{label}.evidence_id"),
        "equivalent": _boolean(raw["equivalent"], f"{label}.equivalent"),
    }


def _parse_attribution(value: Any, label: str) -> dict[str, Any]:
    raw = _expect_object(value, ATTRIBUTION_KEYS, label)
    relation = raw["relation"]
    if (
        not isinstance(relation, str)
        or relation not in ATTRIBUTION_RELATIONS
    ):
        raise InputError(f"{label}.relation is unsupported")
    authorized_committer = raw["authorized_committer_fingerprint"]
    if authorized_committer is not None:
        authorized_committer = _sha256(
            authorized_committer,
            f"{label}.authorized_committer_fingerprint",
        )
    return {
        "relation": relation,
        "old_author_fingerprint": _sha256(
            raw["old_author_fingerprint"],
            f"{label}.old_author_fingerprint",
        ),
        "new_author_fingerprint": _sha256(
            raw["new_author_fingerprint"],
            f"{label}.new_author_fingerprint",
        ),
        "old_committer_fingerprint": _sha256(
            raw["old_committer_fingerprint"],
            f"{label}.old_committer_fingerprint",
        ),
        "new_committer_fingerprint": _sha256(
            raw["new_committer_fingerprint"],
            f"{label}.new_committer_fingerprint",
        ),
        "authorized_committer_fingerprint": authorized_committer,
    }


def _parse_backup(value: Any, label: str) -> dict[str, Any]:
    raw = _expect_object(value, BACKUP_KEYS, label)
    return {
        "ref": _git_ref(raw["ref"], f"{label}.ref"),
        "expected_head_sha": _git_sha(
            raw["expected_head_sha"],
            f"{label}.expected_head_sha",
        ),
        "readback_head_sha": _git_sha(
            raw["readback_head_sha"],
            f"{label}.readback_head_sha",
        ),
        "confirmed": _boolean(raw["confirmed"], f"{label}.confirmed"),
    }


def _parse_lease(value: Any, label: str) -> dict[str, Any]:
    raw = _expect_object(value, LEASE_KEYS, label)
    mode = raw["mode"]
    if not isinstance(mode, str) or mode not in LEASE_MODES:
        raise InputError(f"{label}.mode is unsupported")
    return {
        "remote_ref": _head_branch(raw["remote_ref"], f"{label}.remote_ref"),
        "expected_remote_head_sha": _git_sha(
            raw["expected_remote_head_sha"],
            f"{label}.expected_remote_head_sha",
        ),
        "mode": mode,
    }


def _parse_prepared_proof(
    value: Any,
    node_index: int,
    proof_index: int,
) -> dict[str, Any]:
    label = f"prepared.nodes[{node_index}].proofs[{proof_index}]"
    raw = _expect_object(value, PREPARED_PROOF_KEYS, label)
    status = raw["status"]
    if not isinstance(status, str) or status not in PROOF_STATUSES:
        raise InputError(f"{label}.status is unsupported")
    return {
        "proof_id": _identifier(raw["proof_id"], f"{label}.proof_id"),
        "surface_id": _identifier(raw["surface_id"], f"{label}.surface_id"),
        "node_head_sha": _git_sha(raw["node_head_sha"], f"{label}.node_head_sha"),
        "dependency_head_sha": _git_sha(
            raw["dependency_head_sha"],
            f"{label}.dependency_head_sha",
        ),
        "status": status,
        "terminal": _boolean(raw["terminal"], f"{label}.terminal"),
        "superseded": _boolean(raw["superseded"], f"{label}.superseded"),
        "execution_nonempty": _boolean(
            raw["execution_nonempty"],
            f"{label}.execution_nonempty",
        ),
    }


def _parse_open_proof_gap(
    value: Any,
    node_index: int,
    gap_index: int,
) -> dict[str, Any]:
    label = f"prepared.nodes[{node_index}].open_proof_gaps[{gap_index}]"
    raw = _expect_object(value, OPEN_PROOF_GAP_KEYS, label)
    blocks_action = raw["blocks_action"]
    if (
        not isinstance(blocks_action, str)
        or blocks_action not in PROOF_GAP_BLOCKS
    ):
        raise InputError(f"{label}.blocks_action is unsupported")
    return {
        "surface_id": _identifier(raw["surface_id"], f"{label}.surface_id"),
        "node_head_sha": _git_sha(
            raw["node_head_sha"],
            f"{label}.node_head_sha",
        ),
        "dependency_head_sha": _git_sha(
            raw["dependency_head_sha"],
            f"{label}.dependency_head_sha",
        ),
        "blocks_action": blocks_action,
        "evidence_id": _identifier(raw["evidence_id"], f"{label}.evidence_id"),
    }


def _parse_prepared_node(value: Any, index: int) -> dict[str, Any]:
    label = f"prepared.nodes[{index}]"
    raw = _expect_object(value, PREPARED_NODE_KEYS, label)
    raw_proofs = _array(
        raw["proofs"],
        f"{label}.proofs",
        MAX_PROOFS_PER_NODE,
    )
    raw_gaps = _array(
        raw["open_proof_gaps"],
        f"{label}.open_proof_gaps",
        MAX_PROOFS_PER_NODE,
    )
    if len(raw_proofs) + len(raw_gaps) > MAX_PROOFS_PER_NODE:
        raise InputError(f"{label} proof evidence exceeds the collection limit")
    return {
        "node_id": _identifier(raw["node_id"], f"{label}.node_id"),
        "change_id": _identifier(raw["change_id"], f"{label}.change_id"),
        "source_branch": _head_branch(
            raw["source_branch"],
            f"{label}.source_branch",
        ),
        "old_head_sha": _git_sha(raw["old_head_sha"], f"{label}.old_head_sha"),
        "new_head_sha": _git_sha(raw["new_head_sha"], f"{label}.new_head_sha"),
        "old_parent_head_sha": _git_sha(
            raw["old_parent_head_sha"],
            f"{label}.old_parent_head_sha",
        ),
        "new_parent_head_sha": _git_sha(
            raw["new_parent_head_sha"],
            f"{label}.new_parent_head_sha",
        ),
        "patch_equivalence": _parse_equivalence(
            raw["patch_equivalence"],
            f"{label}.patch_equivalence",
            PATCH_EQUIVALENCE_METHODS,
            {"node-delta"},
            {
                ("canonical-diff", "node-delta"),
                ("stable-patch-id", "node-delta"),
            },
        ),
        "tree_equivalence": _parse_equivalence(
            raw["tree_equivalence"],
            f"{label}.tree_equivalence",
            TREE_EQUIVALENCE_METHODS,
            {"node-delta", "result-tree"},
            TREE_EQUIVALENCE_PAIRS,
        ),
        "attribution": _parse_attribution(
            raw["attribution"],
            f"{label}.attribution",
        ),
        "backup": _parse_backup(raw["backup"], f"{label}.backup"),
        "lease": _parse_lease(raw["lease"], f"{label}.lease"),
        "required_proof_surfaces": _identifier_array(
            raw["required_proof_surfaces"],
            f"{label}.required_proof_surfaces",
            MAX_PROOFS_PER_NODE,
            nonempty=True,
        ),
        "proofs": [
            _parse_prepared_proof(proof, index, proof_index)
            for proof_index, proof in enumerate(raw_proofs)
        ],
        "open_proof_gaps": [
            _parse_open_proof_gap(gap, index, gap_index)
            for gap_index, gap in enumerate(raw_gaps)
        ],
    }


def _parse_prepared_action(value: Any, index: int) -> dict[str, Any]:
    label = f"prepared.actions[{index}]"
    if not isinstance(value, dict):
        raise InputError(f"{label} must be an object")
    kind = value.get("kind")
    if kind == "history-ref-update":
        raw = _expect_object(value, HISTORY_ACTION_KEYS, label)
        return {
            "action_id": _identifier(raw["action_id"], f"{label}.action_id"),
            "kind": kind,
            "node_id": _identifier(raw["node_id"], f"{label}.node_id"),
            "authority_id": _identifier(
                raw["authority_id"],
                f"{label}.authority_id",
            ),
            "remote_ref": _head_branch(
                raw["remote_ref"],
                f"{label}.remote_ref",
            ),
            "expected_remote_head_sha": _git_sha(
                raw["expected_remote_head_sha"],
                f"{label}.expected_remote_head_sha",
            ),
            "new_head_sha": _git_sha(
                raw["new_head_sha"],
                f"{label}.new_head_sha",
            ),
            "backup_ref": _git_ref(raw["backup_ref"], f"{label}.backup_ref"),
        }
    if kind == "metadata-update":
        raw = _expect_object(value, METADATA_ACTION_KEYS, label)
        return {
            "action_id": _identifier(raw["action_id"], f"{label}.action_id"),
            "kind": kind,
            "node_id": _identifier(raw["node_id"], f"{label}.node_id"),
            "authority_id": _identifier(
                raw["authority_id"],
                f"{label}.authority_id",
            ),
            "old_target_branch": _head_branch(
                raw["old_target_branch"],
                f"{label}.old_target_branch",
            ),
            "new_target_branch": _head_branch(
                raw["new_target_branch"],
                f"{label}.new_target_branch",
            ),
            "expected_new_target_head_sha": _git_sha(
                raw["expected_new_target_head_sha"],
                f"{label}.expected_new_target_head_sha",
            ),
            "expected_node_head_sha": _git_sha(
                raw["expected_node_head_sha"],
                f"{label}.expected_node_head_sha",
            ),
        }
    raise InputError(f"{label}.kind is unsupported")


def _parse_history_receipt(value: Any, index: int) -> dict[str, Any]:
    label = f"prepared.history_receipts[{index}]"
    raw = _expect_object(value, HISTORY_RECEIPT_KEYS, label)
    return {
        "receipt_id": _identifier(raw["receipt_id"], f"{label}.receipt_id"),
        "receipt_hash": _sha256(raw["receipt_hash"], f"{label}.receipt_hash"),
        "transaction_digest": _sha256(
            raw["transaction_digest"],
            f"{label}.transaction_digest",
        ),
        "action_id": _identifier(raw["action_id"], f"{label}.action_id"),
        "node_id": _identifier(raw["node_id"], f"{label}.node_id"),
        "remote_ref": _head_branch(raw["remote_ref"], f"{label}.remote_ref"),
        "expected_old_head_sha": _git_sha(
            raw["expected_old_head_sha"],
            f"{label}.expected_old_head_sha",
        ),
        "written_head_sha": _git_sha(
            raw["written_head_sha"],
            f"{label}.written_head_sha",
        ),
        "readback_head_sha": _git_sha(
            raw["readback_head_sha"],
            f"{label}.readback_head_sha",
        ),
        "backup_ref": _git_ref(raw["backup_ref"], f"{label}.backup_ref"),
        "backup_readback_head_sha": _git_sha(
            raw["backup_readback_head_sha"],
            f"{label}.backup_readback_head_sha",
        ),
    }


def _parse_metadata_receipt(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    label = "prepared.metadata_receipt"
    raw = _expect_object(value, METADATA_RECEIPT_KEYS, label)
    return {
        "receipt_id": _identifier(raw["receipt_id"], f"{label}.receipt_id"),
        "receipt_hash": _sha256(raw["receipt_hash"], f"{label}.receipt_hash"),
        "transaction_digest": _sha256(
            raw["transaction_digest"],
            f"{label}.transaction_digest",
        ),
        "action_id": _identifier(raw["action_id"], f"{label}.action_id"),
        "node_id": _identifier(raw["node_id"], f"{label}.node_id"),
        "old_target_ref": _git_head_ref(
            raw["old_target_ref"],
            f"{label}.old_target_ref",
        ),
        "new_target_ref": _git_head_ref(
            raw["new_target_ref"],
            f"{label}.new_target_ref",
        ),
        "readback_target_ref": _git_head_ref(
            raw["readback_target_ref"],
            f"{label}.readback_target_ref",
        ),
        "expected_new_target_head_sha": _git_sha(
            raw["expected_new_target_head_sha"],
            f"{label}.expected_new_target_head_sha",
        ),
        "readback_new_target_head_sha": _git_sha(
            raw["readback_new_target_head_sha"],
            f"{label}.readback_new_target_head_sha",
        ),
        "expected_node_head_sha": _git_sha(
            raw["expected_node_head_sha"],
            f"{label}.expected_node_head_sha",
        ),
        "readback_node_head_sha": _git_sha(
            raw["readback_node_head_sha"],
            f"{label}.readback_node_head_sha",
        ),
    }


def parse_prepared_mutation(value: Any) -> dict[str, Any]:
    """Parse the exact prepared history-mutation handoff shape."""

    raw = _expect_object(value, PREPARED_MUTATION_KEYS, "prepared")
    if raw["schema"] != PREPARED_MUTATION_SCHEMA:
        raise InputError("prepared mutation schema is unsupported")
    raw_nodes = _array(raw["nodes"], "prepared.nodes", MAX_NODES)
    if not raw_nodes:
        raise InputError("prepared.nodes must not be empty")
    nodes = [_parse_prepared_node(node, index) for index, node in enumerate(raw_nodes)]
    proof_evidence_count = sum(
        len(node["proofs"]) + len(node["open_proof_gaps"])
        for node in nodes
    )
    if proof_evidence_count > MAX_TOTAL_PROOFS:
        raise InputError("prepared proof evidence exceeds the collection limit")
    raw_actions = _array(raw["actions"], "prepared.actions", MAX_ACTIONS)
    if not raw_actions:
        raise InputError("prepared.actions must not be empty")
    raw_receipts = _array(
        raw["history_receipts"],
        "prepared.history_receipts",
        MAX_NODES,
    )
    return {
        "schema": PREPARED_MUTATION_SCHEMA,
        "receiver_id": _identifier(raw["receiver_id"], "prepared.receiver_id"),
        "snapshot_digest": _sha256(
            raw["snapshot_digest"],
            "prepared.snapshot_digest",
        ),
        "snapshot": parse_snapshot(raw["snapshot"]),
        "new_predecessor": _parse_new_predecessor(raw["new_predecessor"]),
        "proof_wait_owner_ref": _optional_identifier(
            raw["proof_wait_owner_ref"],
            "prepared.proof_wait_owner_ref",
        ),
        "authority": _parse_prepared_authority(raw["authority"]),
        "attribution_policy": _parse_policy(
            raw["attribution_policy"],
            "attribution_policy",
        ),
        "proof_policy": _parse_policy(raw["proof_policy"], "proof_policy"),
        "excluded_actions": _identifier_array(
            raw["excluded_actions"],
            "prepared.excluded_actions",
            MAX_SCOPE_ACTIONS,
            nonempty=True,
        ),
        "nodes": nodes,
        "actions": [
            _parse_prepared_action(action, index)
            for index, action in enumerate(raw_actions)
        ],
        "history_receipts": [
            _parse_history_receipt(receipt, index)
            for index, receipt in enumerate(raw_receipts)
        ],
        "metadata_receipt": _parse_metadata_receipt(raw["metadata_receipt"]),
    }


def _prepared_equivalence_issues(
    issues: list[dict[str, Any]],
    node: dict[str, Any],
    field: str,
) -> None:
    evidence = node[field]
    if evidence["equivalent"] is not True:
        _issue(
            issues,
            f"{field}_not_equivalent",
            node_id=node["node_id"],
        )
    if evidence["old_digest"] != evidence["new_digest"]:
        _issue(
            issues,
            f"{field}_digest_mismatch",
            node_id=node["node_id"],
        )


def _prepared_attribution_issues(
    issues: list[dict[str, Any]],
    node: dict[str, Any],
) -> None:
    attribution = node["attribution"]
    node_id = node["node_id"]
    if (
        attribution["old_author_fingerprint"]
        != attribution["new_author_fingerprint"]
    ):
        _issue(issues, "author_attribution_drift", node_id=node_id)

    old_committer = attribution["old_committer_fingerprint"]
    new_committer = attribution["new_committer_fingerprint"]
    authorized_committer = attribution["authorized_committer_fingerprint"]
    if attribution["relation"] == "preserve-author-and-committer":
        if authorized_committer is not None:
            _issue(
                issues,
                "unexpected_authorized_committer",
                node_id=node_id,
            )
        if old_committer != new_committer:
            _issue(issues, "committer_attribution_drift", node_id=node_id)
        return

    if authorized_committer is None:
        _issue(issues, "authorized_committer_missing", node_id=node_id)
    elif new_committer != authorized_committer:
        _issue(issues, "unauthorized_committer_identity", node_id=node_id)
    if old_committer == new_committer:
        _issue(issues, "intentional_committer_change_missing", node_id=node_id)


def _full_head_ref(branch: str) -> str:
    return branch if branch.startswith("refs/") else f"refs/heads/{branch}"


def _receipt_payload(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }


def prepared_transaction_digest(prepared: dict[str, Any]) -> str:
    """Digest immutable mutation scope while proof evidence and receipts advance."""

    transaction = {
        "schema": prepared["schema"],
        "receiver_id": prepared["receiver_id"],
        "snapshot_digest": prepared["snapshot_digest"],
        "snapshot": prepared["snapshot"],
        "new_predecessor": prepared["new_predecessor"],
        "authority": prepared["authority"],
        "attribution_policy": prepared["attribution_policy"],
        "proof_policy": prepared["proof_policy"],
        "excluded_actions": prepared["excluded_actions"],
        "nodes": [
            {
                key: value
                for key, value in node.items()
                if key not in {"proofs", "open_proof_gaps"}
            }
            for node in prepared["nodes"]
        ],
        "actions": prepared["actions"],
    }
    return stable_digest(transaction)


def _prepared_git_object_ids(prepared: dict[str, Any]) -> list[str]:
    snapshot = prepared["snapshot"]
    values = [snapshot["base"]["head_sha"], prepared["new_predecessor"]["head_sha"]]
    for node in snapshot["nodes"]:
        values.extend((node["head_sha"], node["expected_parent_head_sha"]))
        if node["landing_head_sha"] is not None:
            values.append(node["landing_head_sha"])
        for proof in node["proofs"]:
            values.extend(
                (proof["node_head_sha"], proof["dependency_head_sha"])
            )
    for node in prepared["nodes"]:
        values.extend(
            (
                node["old_head_sha"],
                node["new_head_sha"],
                node["old_parent_head_sha"],
                node["new_parent_head_sha"],
                node["backup"]["expected_head_sha"],
                node["backup"]["readback_head_sha"],
                node["lease"]["expected_remote_head_sha"],
            )
        )
        for proof in node["proofs"]:
            values.extend(
                (proof["node_head_sha"], proof["dependency_head_sha"])
            )
        for gap in node["open_proof_gaps"]:
            values.extend(
                (gap["node_head_sha"], gap["dependency_head_sha"])
            )
    for action in prepared["actions"]:
        if action["kind"] == "history-ref-update":
            values.extend(
                (
                    action["expected_remote_head_sha"],
                    action["new_head_sha"],
                )
            )
        else:
            values.extend(
                (
                    action["expected_new_target_head_sha"],
                    action["expected_node_head_sha"],
                )
            )
    for receipt in prepared["history_receipts"]:
        values.extend(
            (
                receipt["expected_old_head_sha"],
                receipt["written_head_sha"],
                receipt["readback_head_sha"],
                receipt["backup_readback_head_sha"],
            )
        )
    metadata_receipt = prepared["metadata_receipt"]
    if metadata_receipt is not None:
        values.extend(
            (
                metadata_receipt["expected_new_target_head_sha"],
                metadata_receipt["readback_new_target_head_sha"],
                metadata_receipt["expected_node_head_sha"],
                metadata_receipt["readback_node_head_sha"],
            )
        )
    return values


def prepared_mutation_issues(prepared: dict[str, Any]) -> list[dict[str, Any]]:
    """Return bounded safety failures for a parsed prepared mutation."""

    issues = snapshot_issues(prepared["snapshot"])
    snapshot = prepared["snapshot"]
    nodes = prepared["nodes"]
    actions = prepared["actions"]
    authority = prepared["authority"]
    transaction_digest = prepared_transaction_digest(prepared)

    if prepared["snapshot_digest"] != stable_digest(snapshot):
        _issue(issues, "stale_prepared_snapshot_digest")
    if len({len(value) for value in _prepared_git_object_ids(prepared)}) != 1:
        _issue(issues, "mixed_git_object_id_width")

    allowed_actions = set(authority["allowed_actions"])
    excluded_actions = set(prepared["excluded_actions"])
    missing_exclusions = REQUIRED_EXCLUDED_ACTIONS - excluded_actions
    if missing_exclusions:
        _issue(issues, "required_exclusions_missing", field="excluded_actions")
    if allowed_actions & excluded_actions:
        _issue(issues, "allowed_action_is_excluded", field="excluded_actions")

    snapshot_nodes = snapshot["nodes"]
    snapshot_by_id = {node["node_id"]: node for node in snapshot_nodes}
    snapshot_ids = [node["node_id"] for node in snapshot_nodes]
    mapped_ids = [node["node_id"] for node in nodes]
    first_index: int | None = None
    if len(set(mapped_ids)) != len(mapped_ids):
        _issue(issues, "duplicate_prepared_node_id")
    if mapped_ids and mapped_ids[0] in snapshot_by_id:
        first_index = snapshot_ids.index(mapped_ids[0])
        if mapped_ids != snapshot_ids[first_index:]:
            _issue(issues, "rewrite_nodes_not_contiguous_suffix")
    else:
        _issue(issues, "unknown_prepared_node")

    predecessor = prepared["new_predecessor"]
    if predecessor["kind"] == "node" and predecessor["node_id"] is None:
        _issue(issues, "new_predecessor_node_id_missing")
    if predecessor["kind"] != "node" and predecessor["node_id"] is not None:
        _issue(issues, "new_predecessor_node_id_unexpected")
    if nodes and nodes[0]["new_parent_head_sha"] != predecessor["head_sha"]:
        _issue(
            issues,
            "first_new_parent_predecessor_head_mismatch",
            node_id=nodes[0]["node_id"],
        )

    unique_sets: tuple[tuple[str, str], ...] = (
        ("change_id", "duplicate_prepared_change_id"),
        ("source_branch", "duplicate_prepared_source_branch"),
        ("new_head_sha", "duplicate_prepared_new_head"),
    )
    for field, code in unique_sets:
        seen: set[str] = set()
        for node in nodes:
            value = node[field]
            if value in seen:
                _issue(issues, code, node_id=node["node_id"], field=field)
            seen.add(value)

    snapshot_heads = {node["head_sha"] for node in snapshot_nodes}
    protected_old_heads = snapshot_heads | {snapshot["base"]["head_sha"]}
    protected_old_heads.update(
        node["landing_head_sha"]
        for node in snapshot_nodes
        if node["landing_head_sha"] is not None
    )
    live_refs = {_full_head_ref(snapshot["base"]["branch"])}
    for snapshot_node in snapshot_nodes:
        live_refs.add(_full_head_ref(snapshot_node["source_branch"]))
        live_refs.add(_full_head_ref(snapshot_node["target_branch"]))
    live_refs.add(predecessor["source_ref"])
    for action in actions:
        if action["kind"] == "history-ref-update":
            live_refs.add(_full_head_ref(action["remote_ref"]))
        else:
            live_refs.add(_full_head_ref(action["old_target_branch"]))
            live_refs.add(_full_head_ref(action["new_target_branch"]))

    backup_refs: set[str] = set()
    equivalence_evidence_ids: set[str] = set()
    snapshot_proof_ids = {
        proof["proof_id"]
        for snapshot_node in snapshot_nodes
        for proof in snapshot_node["proofs"]
    }
    proof_ids: set[str] = set()
    gap_evidence_ids: set[str] = set()
    declared_action_kinds = {action["kind"] for action in actions}
    open_gap_count = 0
    for index, node in enumerate(nodes):
        node_id = node["node_id"]
        snapshot_node = snapshot_by_id.get(node_id)
        if snapshot_node is None:
            _issue(issues, "unknown_prepared_node", node_id=node_id)
        else:
            for prepared_field, snapshot_field, code in (
                ("change_id", "change_id", "prepared_change_mismatch"),
                ("source_branch", "source_branch", "prepared_source_mismatch"),
                ("old_head_sha", "head_sha", "prepared_old_head_mismatch"),
                (
                    "old_parent_head_sha",
                    "expected_parent_head_sha",
                    "prepared_old_parent_mismatch",
                ),
            ):
                if node[prepared_field] != snapshot_node[snapshot_field]:
                    _issue(
                        issues,
                        code,
                        node_id=node_id,
                        field=prepared_field,
                    )
            if snapshot_node["state"] == "landed":
                _issue(issues, "landed_node_cannot_be_rewritten", node_id=node_id)

        if node["old_head_sha"] == node["new_head_sha"]:
            _issue(issues, "prepared_head_not_rewritten", node_id=node_id)
        if node["new_head_sha"] in protected_old_heads:
            _issue(issues, "prepared_new_head_reuses_old_head", node_id=node_id)
        if node["new_head_sha"] == node["new_parent_head_sha"]:
            _issue(issues, "prepared_new_head_equals_parent", node_id=node_id)
        if index and node["new_parent_head_sha"] != nodes[index - 1]["new_head_sha"]:
            _issue(issues, "prepared_new_parent_chain_mismatch", node_id=node_id)

        for field in ("patch_equivalence", "tree_equivalence"):
            _prepared_equivalence_issues(issues, node, field)
            evidence_id = node[field]["evidence_id"]
            if evidence_id in equivalence_evidence_ids:
                _issue(
                    issues,
                    "duplicate_equivalence_evidence_id",
                    node_id=node_id,
                    field=field,
                )
            equivalence_evidence_ids.add(evidence_id)

        _prepared_attribution_issues(issues, node)

        backup = node["backup"]
        if backup["ref"] in backup_refs:
            _issue(issues, "duplicate_backup_ref", node_id=node_id)
        backup_refs.add(backup["ref"])
        if not backup["ref"].startswith(BACKUP_REF_PREFIX):
            _issue(issues, "backup_ref_outside_recovery_namespace", node_id=node_id)
        if backup["ref"] in live_refs:
            _issue(issues, "backup_ref_conflicts_live_ref", node_id=node_id)
        if backup["confirmed"] is not True:
            _issue(issues, "backup_not_confirmed", node_id=node_id)
        if backup["expected_head_sha"] != node["old_head_sha"]:
            _issue(issues, "backup_expected_head_mismatch", node_id=node_id)
        if backup["readback_head_sha"] != node["old_head_sha"]:
            _issue(issues, "backup_readback_head_mismatch", node_id=node_id)

        lease = node["lease"]
        if lease["remote_ref"] != node["source_branch"]:
            _issue(issues, "lease_ref_mismatch", node_id=node_id)
        if lease["expected_remote_head_sha"] != node["old_head_sha"]:
            _issue(issues, "lease_expected_head_mismatch", node_id=node_id)

        required_surfaces = set(node["required_proof_surfaces"])
        observed_surfaces: set[str] = set()
        for proof in node["proofs"]:
            proof_id = proof["proof_id"]
            surface_id = proof["surface_id"]
            if proof_id in snapshot_proof_ids:
                _issue(
                    issues,
                    "prepared_proof_id_reuses_snapshot_receipt",
                    node_id=node_id,
                    proof_id=proof_id,
                )
            if proof_id in proof_ids:
                _issue(
                    issues,
                    "duplicate_prepared_proof_id",
                    node_id=node_id,
                    proof_id=proof_id,
                )
            proof_ids.add(proof_id)
            if surface_id in observed_surfaces:
                _issue(
                    issues,
                    "duplicate_proof_surface",
                    node_id=node_id,
                    proof_id=proof_id,
                    surface_id=surface_id,
                )
            observed_surfaces.add(surface_id)
            if surface_id not in required_surfaces:
                _issue(
                    issues,
                    "unexpected_proof_surface",
                    node_id=node_id,
                    proof_id=proof_id,
                    surface_id=surface_id,
                )
            if proof["node_head_sha"] != node["new_head_sha"]:
                _issue(
                    issues,
                    "prepared_proof_node_head_stale",
                    node_id=node_id,
                    proof_id=proof_id,
                )
            if proof["dependency_head_sha"] != node["new_parent_head_sha"]:
                _issue(
                    issues,
                    "prepared_proof_dependency_head_stale",
                    node_id=node_id,
                    proof_id=proof_id,
                )
            if proof["status"] != "success":
                _issue(
                    issues,
                    "prepared_proof_not_successful",
                    node_id=node_id,
                    proof_id=proof_id,
                )
            if proof["terminal"] is not True:
                _issue(
                    issues,
                    "prepared_proof_not_terminal",
                    node_id=node_id,
                    proof_id=proof_id,
                )
            if proof["superseded"] is not False:
                _issue(
                    issues,
                    "prepared_proof_superseded",
                    node_id=node_id,
                    proof_id=proof_id,
                )
            if proof["execution_nonempty"] is not True:
                _issue(
                    issues,
                    "prepared_proof_execution_empty",
                    node_id=node_id,
                    proof_id=proof_id,
                )
        for gap in node["open_proof_gaps"]:
            surface_id = gap["surface_id"]
            evidence_id = gap["evidence_id"]
            open_gap_count += 1
            if surface_id in observed_surfaces:
                _issue(
                    issues,
                    "duplicate_proof_surface",
                    node_id=node_id,
                    surface_id=surface_id,
                )
            observed_surfaces.add(surface_id)
            if surface_id not in required_surfaces:
                _issue(
                    issues,
                    "unexpected_proof_surface",
                    node_id=node_id,
                    surface_id=surface_id,
                )
            if evidence_id in gap_evidence_ids:
                _issue(
                    issues,
                    "duplicate_proof_gap_evidence_id",
                    node_id=node_id,
                    surface_id=surface_id,
                )
            gap_evidence_ids.add(evidence_id)
            if gap["node_head_sha"] != node["new_head_sha"]:
                _issue(
                    issues,
                    "proof_gap_node_head_stale",
                    node_id=node_id,
                    surface_id=surface_id,
                )
            if gap["dependency_head_sha"] != node["new_parent_head_sha"]:
                _issue(
                    issues,
                    "proof_gap_dependency_head_stale",
                    node_id=node_id,
                    surface_id=surface_id,
                )
            if (
                gap["blocks_action"] != "finalize"
                and gap["blocks_action"] not in declared_action_kinds
            ):
                _issue(
                    issues,
                    "proof_gap_blocks_absent_action",
                    node_id=node_id,
                    surface_id=surface_id,
                )
        for missing_surface in sorted(required_surfaces - observed_surfaces):
            _issue(
                issues,
                "required_proof_surface_missing",
                node_id=node_id,
                surface_id=missing_surface,
            )

    if open_gap_count and prepared["proof_wait_owner_ref"] is None:
        _issue(issues, "proof_wait_owner_missing")
    if not open_gap_count and prepared["proof_wait_owner_ref"] is not None:
        _issue(issues, "unexpected_proof_wait_owner")

    action_ids: set[str] = set()
    action_kinds: set[str] = set()
    metadata_seen = False
    history_actions: list[dict[str, Any]] = []
    metadata_actions: list[dict[str, Any]] = []
    for action in actions:
        action_id = action["action_id"]
        if action_id in action_ids:
            _issue(issues, "duplicate_action_id", action_id=action_id)
        action_ids.add(action_id)
        action_kinds.add(action["kind"])
        if action["authority_id"] != authority["authority_id"]:
            _issue(
                issues,
                "action_authority_mismatch",
                action_id=action_id,
            )
        if action["kind"] == "history-ref-update":
            history_actions.append(action)
            if metadata_seen:
                _issue(
                    issues,
                    "history_action_after_metadata",
                    action_id=action_id,
                )
        else:
            metadata_seen = True
            metadata_actions.append(action)

    if not history_actions:
        _issue(issues, "history_actions_missing")
    if action_kinds != allowed_actions:
        _issue(issues, "action_kinds_not_exactly_authorized")

    if [action["node_id"] for action in history_actions] != mapped_ids:
        _issue(issues, "history_actions_do_not_match_rewrite_nodes")
    prepared_by_id = {node["node_id"]: node for node in nodes}
    for action in history_actions:
        action_id = action["action_id"]
        node = prepared_by_id.get(action["node_id"])
        if node is None:
            _issue(
                issues,
                "history_action_unknown_node",
                action_id=action_id,
            )
            continue
        for action_field, node_value, code in (
            ("remote_ref", node["lease"]["remote_ref"], "history_remote_ref_mismatch"),
            (
                "expected_remote_head_sha",
                node["old_head_sha"],
                "history_lease_head_mismatch",
            ),
            ("new_head_sha", node["new_head_sha"], "history_new_head_mismatch"),
            ("backup_ref", node["backup"]["ref"], "history_backup_ref_mismatch"),
        ):
            if action[action_field] != node_value:
                _issue(
                    issues,
                    code,
                    node_id=node["node_id"],
                    action_id=action_id,
                    field=action_field,
                )

    receipts = prepared["history_receipts"]
    if len(receipts) > len(history_actions):
        _issue(issues, "too_many_history_receipts")
    receipt_ids: set[str] = set()
    receipt_hashes: set[str] = set()
    for index, receipt in enumerate(receipts):
        if receipt["receipt_hash"] != stable_digest(
            _receipt_payload(receipt)
        ):
            _issue(
                issues,
                "history_receipt_digest_mismatch",
                action_id=receipt["action_id"],
            )
        if receipt["transaction_digest"] != transaction_digest:
            _issue(
                issues,
                "history_receipt_transaction_mismatch",
                action_id=receipt["action_id"],
            )
        if receipt["receipt_id"] in receipt_ids:
            _issue(
                issues,
                "duplicate_history_receipt_id",
                action_id=receipt["action_id"],
            )
        receipt_ids.add(receipt["receipt_id"])
        if receipt["receipt_hash"] in receipt_hashes:
            _issue(
                issues,
                "duplicate_history_receipt_hash",
                action_id=receipt["action_id"],
            )
        receipt_hashes.add(receipt["receipt_hash"])
        if index >= len(history_actions):
            continue
        action = history_actions[index]
        for receipt_field, action_field, code in (
            ("action_id", "action_id", "history_receipt_action_order_mismatch"),
            ("node_id", "node_id", "history_receipt_node_mismatch"),
            ("remote_ref", "remote_ref", "history_receipt_ref_mismatch"),
            (
                "expected_old_head_sha",
                "expected_remote_head_sha",
                "history_receipt_old_head_mismatch",
            ),
            (
                "written_head_sha",
                "new_head_sha",
                "history_receipt_written_head_mismatch",
            ),
            (
                "backup_ref",
                "backup_ref",
                "history_receipt_backup_ref_mismatch",
            ),
        ):
            if receipt[receipt_field] != action[action_field]:
                _issue(
                    issues,
                    code,
                    node_id=action["node_id"],
                    action_id=action["action_id"],
                    field=receipt_field,
                )
        if receipt["readback_head_sha"] != action["new_head_sha"]:
            _issue(
                issues,
                "history_receipt_readback_mismatch",
                node_id=action["node_id"],
                action_id=action["action_id"],
            )
        if (
            receipt["backup_readback_head_sha"]
            != action["expected_remote_head_sha"]
        ):
            _issue(
                issues,
                "history_receipt_backup_readback_mismatch",
                node_id=action["node_id"],
                action_id=action["action_id"],
            )
        node = prepared_by_id.get(action["node_id"])
        if node is not None and any(
            gap["blocks_action"] == "history-ref-update"
            for gap in node["open_proof_gaps"]
        ):
            _issue(
                issues,
                "history_receipt_bypasses_open_gate",
                node_id=action["node_id"],
                action_id=action["action_id"],
            )

    if len(metadata_actions) > 1:
        _issue(issues, "multiple_metadata_actions")
    if metadata_actions and (
        not mapped_ids or metadata_actions[0]["node_id"] != mapped_ids[0]
    ):
        _issue(issues, "metadata_action_not_first_rewritten_node")

    logical_predecessor: tuple[str, str | None, str, str] | None = None
    if first_index is not None:
        first_snapshot_node = snapshot_nodes[first_index]
        target_ref = _full_head_ref(first_snapshot_node["target_branch"])
        dependency_head = first_snapshot_node["expected_parent_head_sha"]
        if (
            target_ref == _full_head_ref(snapshot["base"]["branch"])
            and dependency_head == snapshot["base"]["head_sha"]
        ):
            logical_predecessor = (
                "base",
                None,
                target_ref,
                dependency_head,
            )
        else:
            predecessor_node = next(
                (
                    candidate
                    for candidate in snapshot_nodes[:first_index]
                    if (
                        _full_head_ref(candidate["source_branch"]) == target_ref
                        and candidate["head_sha"] == dependency_head
                    )
                ),
                None,
            )
            if predecessor_node is not None:
                logical_predecessor = (
                    "node",
                    predecessor_node["node_id"],
                    target_ref,
                    dependency_head,
                )
            else:
                _issue(issues, "snapshot_predecessor_binding_missing")

    if metadata_actions:
        if predecessor["kind"] != "retarget":
            _issue(issues, "metadata_requires_retarget_predecessor")
    elif logical_predecessor is not None:
        expected_kind, expected_node_id, expected_ref, expected_head = (
            logical_predecessor
        )
        if predecessor["kind"] != expected_kind:
            _issue(issues, "new_predecessor_kind_mismatch")
        if predecessor["node_id"] != expected_node_id:
            _issue(issues, "new_predecessor_node_mismatch")
        if predecessor["source_ref"] != expected_ref:
            _issue(issues, "new_predecessor_ref_mismatch")
        if predecessor["head_sha"] != expected_head:
            _issue(issues, "new_predecessor_head_mismatch")

    source_refs = {
        _full_head_ref(snapshot_node["source_branch"])
        for snapshot_node in snapshot_nodes
    }
    for action in metadata_actions:
        action_id = action["action_id"]
        node = prepared_by_id.get(action["node_id"])
        snapshot_node = snapshot_by_id.get(action["node_id"])
        if node is None or snapshot_node is None:
            _issue(
                issues,
                "metadata_action_unknown_node",
                action_id=action_id,
            )
            continue
        if action["old_target_branch"] != snapshot_node["target_branch"]:
            _issue(
                issues,
                "metadata_old_target_mismatch",
                node_id=node["node_id"],
                action_id=action_id,
            )
        if (
            _full_head_ref(action["new_target_branch"])
            == _full_head_ref(action["old_target_branch"])
        ):
            _issue(
                issues,
                "metadata_target_not_changed",
                node_id=node["node_id"],
                action_id=action_id,
            )
        if _full_head_ref(action["new_target_branch"]) in source_refs:
            _issue(
                issues,
                "metadata_target_topology_conflict",
                node_id=node["node_id"],
                action_id=action_id,
            )
        if (
            _full_head_ref(action["new_target_branch"])
            != predecessor["source_ref"]
        ):
            _issue(
                issues,
                "metadata_new_target_predecessor_ref_mismatch",
                node_id=node["node_id"],
                action_id=action_id,
            )
        if (
            action["expected_new_target_head_sha"]
            != predecessor["head_sha"]
        ):
            _issue(
                issues,
                "metadata_new_target_head_mismatch",
                node_id=node["node_id"],
                action_id=action_id,
            )
        if action["expected_node_head_sha"] != node["new_head_sha"]:
            _issue(
                issues,
                "metadata_expected_head_mismatch",
                node_id=node["node_id"],
                action_id=action_id,
            )

    metadata_receipt = prepared["metadata_receipt"]
    if metadata_receipt is not None:
        receipt = metadata_receipt
        if receipt["receipt_hash"] != stable_digest(_receipt_payload(receipt)):
            _issue(
                issues,
                "metadata_receipt_digest_mismatch",
                action_id=receipt["action_id"],
            )
        if receipt["transaction_digest"] != transaction_digest:
            _issue(
                issues,
                "metadata_receipt_transaction_mismatch",
                action_id=receipt["action_id"],
            )
        if receipt["receipt_id"] in receipt_ids:
            _issue(
                issues,
                "duplicate_action_receipt_id",
                action_id=receipt["action_id"],
            )
        if receipt["receipt_hash"] in receipt_hashes:
            _issue(
                issues,
                "duplicate_action_receipt_hash",
                action_id=receipt["action_id"],
            )
        if not metadata_actions:
            _issue(
                issues,
                "metadata_receipt_without_action",
                action_id=receipt["action_id"],
            )
        else:
            action = metadata_actions[0]
            expected_bindings = (
                (
                    "action_id",
                    action["action_id"],
                    "metadata_receipt_action_mismatch",
                ),
                (
                    "node_id",
                    action["node_id"],
                    "metadata_receipt_node_mismatch",
                ),
                (
                    "old_target_ref",
                    _full_head_ref(action["old_target_branch"]),
                    "metadata_receipt_old_target_mismatch",
                ),
                (
                    "new_target_ref",
                    _full_head_ref(action["new_target_branch"]),
                    "metadata_receipt_new_target_mismatch",
                ),
                (
                    "readback_target_ref",
                    _full_head_ref(action["new_target_branch"]),
                    "metadata_receipt_target_readback_mismatch",
                ),
                (
                    "expected_new_target_head_sha",
                    action["expected_new_target_head_sha"],
                    "metadata_receipt_target_head_mismatch",
                ),
                (
                    "readback_new_target_head_sha",
                    action["expected_new_target_head_sha"],
                    "metadata_receipt_target_head_readback_mismatch",
                ),
                (
                    "expected_node_head_sha",
                    action["expected_node_head_sha"],
                    "metadata_receipt_node_head_mismatch",
                ),
                (
                    "readback_node_head_sha",
                    action["expected_node_head_sha"],
                    "metadata_receipt_node_readback_mismatch",
                ),
            )
            for receipt_field, expected_value, code in expected_bindings:
                if receipt[receipt_field] != expected_value:
                    _issue(
                        issues,
                        code,
                        node_id=action["node_id"],
                        action_id=action["action_id"],
                        field=receipt_field,
                    )
            if len(receipts) != len(history_actions):
                _issue(
                    issues,
                    "metadata_receipt_before_history_complete",
                    node_id=action["node_id"],
                    action_id=action["action_id"],
                )
            if any(
                gap["blocks_action"] == "metadata-update"
                for node in nodes
                for gap in node["open_proof_gaps"]
            ):
                _issue(
                    issues,
                    "metadata_receipt_bypasses_open_gate",
                    node_id=action["node_id"],
                    action_id=action["action_id"],
                )
    return issues[:MAX_ISSUES]


def validate_prepared_mutation_data(
    value: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse and validate a future stacked-history mutation handoff."""

    prepared = parse_prepared_mutation(value)
    issues = prepared_mutation_issues(prepared)
    proof_count = sum(len(node["proofs"]) for node in prepared["nodes"])
    gaps = [
        gap
        for node in prepared["nodes"]
        for gap in node["open_proof_gaps"]
    ]
    proof_surface_count = sum(
        len(node["required_proof_surfaces"]) for node in prepared["nodes"]
    )
    history_actions = [
        action
        for action in prepared["actions"]
        if action["kind"] == "history-ref-update"
    ]
    metadata_actions = [
        action
        for action in prepared["actions"]
        if action["kind"] == "metadata-update"
    ]
    completed_history_count = len(prepared["history_receipts"])
    if issues:
        status = "fail"
        readiness = "blocked"
        next_action_id = None
    elif completed_history_count < len(history_actions):
        next_history = history_actions[completed_history_count]
        next_node = next(
            node
            for node in prepared["nodes"]
            if node["node_id"] == next_history["node_id"]
        )
        next_history_blocked = any(
            gap["blocks_action"] == "history-ref-update"
            for gap in next_node["open_proof_gaps"]
        )
        if next_history_blocked:
            status = "blocked"
            readiness = "blocked"
            next_action_id = None
        else:
            status = "ready"
            readiness = "history-ready" if gaps else "mutation-ready"
            next_action_id = next_history["action_id"]
    else:
        metadata_gap_open = any(
            gap["blocks_action"] == "metadata-update" for gap in gaps
        )
        if metadata_actions and prepared["metadata_receipt"] is None:
            if metadata_gap_open:
                status = "blocked"
                readiness = "proof-wait"
                next_action_id = None
            else:
                status = "ready"
                readiness = "metadata-ready"
                next_action_id = metadata_actions[0]["action_id"]
        elif gaps:
            status = "blocked"
            readiness = "proof-wait"
            next_action_id = None
        else:
            status = "complete"
            readiness = "complete"
            next_action_id = None
    result = {
        "schema": PREPARED_MUTATION_VALIDATION_SCHEMA,
        "status": status,
        "readiness": readiness,
        "next_action_id": next_action_id,
        "repository_id": prepared["snapshot"]["repository_id"],
        "forge_adapter": prepared["snapshot"]["forge_adapter"],
        "stack_id": prepared["snapshot"]["stack_id"],
        "receiver_id": prepared["receiver_id"],
        "proof_wait_owner_ref": prepared["proof_wait_owner_ref"],
        "attribution_policy_id": prepared["attribution_policy"]["policy_id"],
        "proof_policy_id": prepared["proof_policy"]["policy_id"],
        "snapshot_digest": stable_digest(prepared["snapshot"]),
        "transaction_digest": prepared_transaction_digest(prepared),
        "prepared_mutation_digest": stable_digest(prepared),
        "node_count": len(prepared["nodes"]),
        "action_count": len(prepared["actions"]),
        "completed_history_count": completed_history_count,
        "metadata_completed": prepared["metadata_receipt"] is not None,
        "proof_surface_count": proof_surface_count,
        "proof_count": proof_count,
        "open_proof_gap_count": len(gaps),
        "violations": issues,
    }
    return prepared, result


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(
        prog="stacked_delivery_guard.py",
        description="Read-only deterministic stacked-delivery JSON guard.",
        epilog=HELP_TEXT,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate-snapshot",
        help="validate one stack snapshot",
        description="Validate one exact-shape stack snapshot.",
    )
    validate.add_argument("--input", required=True, metavar="FILE")

    compare = subparsers.add_parser(
        "compare",
        help="compare snapshots and report drift invalidation",
        description="Compare strict before/after snapshots.",
    )
    compare.add_argument("--before", required=True, metavar="FILE")
    compare.add_argument("--after", required=True, metavar="FILE")

    next_action = subparsers.add_parser(
        "next-action",
        help="select the dependency-safe next landing node or prefix",
        description="Return a structured action, never a command string.",
    )
    next_action.add_argument("--input", required=True, metavar="FILE")

    handoff = subparsers.add_parser(
        "validate-handoff",
        help="validate a self-contained handoff receipt",
        description="Validate snapshot digest and exact receipt bindings.",
    )
    handoff.add_argument("--input", required=True, metavar="FILE")

    prepared = subparsers.add_parser(
        "validate-prepared-mutation",
        help="validate a prepared stacked-history mutation handoff",
        description=(
            "Validate exact rewrite, equivalence, attribution, backup, lease, "
            "proof, authority and action bindings."
        ),
    )
    prepared.add_argument("--input", required=True, metavar="FILE")
    return parser


def _emit(value: dict[str, Any]) -> None:
    print(_canonical_json(value))


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "validate-snapshot":
            _, result = validate_snapshot_data(load_json_file(args.input))
        elif args.command == "compare":
            _, _, result = compare_snapshot_data(
                load_json_file(args.before),
                load_json_file(args.after),
            )
        elif args.command == "next-action":
            _, result = next_action_data(load_json_file(args.input))
        elif args.command == "validate-handoff":
            _, result = validate_handoff_data(load_json_file(args.input))
        elif args.command == "validate-prepared-mutation":
            _, result = validate_prepared_mutation_data(load_json_file(args.input))
        else:
            raise InputError("unsupported command")
    except InputError as exc:
        _emit(
            {
                "schema": ERROR_SCHEMA,
                "status": "error",
                "error": str(exc)[:240],
            }
        )
        return 1
    _emit(result)
    return 0 if result["status"] in {"pass", "ready", "complete"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
