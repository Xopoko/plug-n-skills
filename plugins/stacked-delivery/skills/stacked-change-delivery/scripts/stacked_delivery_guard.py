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
VALIDATION_SCHEMA = "stacked_delivery.validation.v1"
COMPARE_SCHEMA = "stacked_delivery.compare.v1"
NEXT_ACTION_SCHEMA = "stacked_delivery.next_action.v1"
HANDOFF_VALIDATION_SCHEMA = "stacked_delivery.handoff_validation.v1"
ERROR_SCHEMA = "stacked_delivery.error.v1"

FORGE_MODES = {"sequential", "atomic-prefix"}
NODE_STATES = {"unlanded", "landed", "retargeted"}
PROOF_STATUSES = {"success", "failure", "running", "cancelled", "skipped"}

MAX_INPUT_BYTES = 1024 * 1024
MAX_NODES = 64
MAX_PROOFS_PER_NODE = 32
MAX_TOTAL_PROOFS = 512
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
    field: str | None = None,
) -> None:
    if len(issues) >= MAX_ISSUES:
        return
    item: dict[str, Any] = {"code": code}
    if node_id is not None:
        item["node_id"] = node_id
    if proof_id is not None:
        item["proof_id"] = proof_id
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
