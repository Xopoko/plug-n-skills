#!/usr/bin/env python3
"""Validate and select declared forge adapters without contacting a forge."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, NoReturn


INVENTORY_SCHEMA = "git_workflows.forge_adapter_inventory.v1"
PLAN_SCHEMA = "git_workflows.forge_adapter_plan.v1"
RESULT_SCHEMA = "git_workflows.forge_adapter_selection.v1"
ERROR_SCHEMA = "git_workflows.forge_adapter_error.v1"

ADAPTER_KINDS = {"mcp", "connector", "cli", "rest"}
FORGES = {"github", "gitlab"}
SUPPORT_STATES = {"probed", "declared", "unsupported"}

CAPABILITY_MODES = {
    "forge.auth.current-user.read.v1": "read",
    "forge.repository.read.v1": "read",
    "forge.repository.branch.read.v1": "read",
    "forge.change.read.v1": "read",
    "forge.change.files.list-complete.v1": "read",
    "forge.change.diff.read.v1": "read",
    "forge.change.discussions.list-complete.v1": "read",
    "forge.change.discussion.read.v1": "read",
    "forge.stack.changes.list-complete.v1": "read",
    "gitlab.change.diff-versions.list-complete.v1": "read",
    "gitlab.change.diff-version.read.v1": "read",
    "gitlab.change.pipelines.list-complete.v1": "read",
    "gitlab.change.discussion.reply.create.v1": "write",
    "gitlab.change.discussion.resolve.set.v1": "write",
}

LIST_CAPABILITIES = {
    "forge.change.files.list-complete.v1",
    "forge.change.discussions.list-complete.v1",
    "forge.stack.changes.list-complete.v1",
    "gitlab.change.diff-versions.list-complete.v1",
    "gitlab.change.pipelines.list-complete.v1",
}

PROFILE_REQUIREMENTS = {
    "forge-code-review": {
        "forge.change.read.v1",
        "forge.change.files.list-complete.v1",
        "forge.change.diff.read.v1",
        "forge.change.discussions.list-complete.v1",
    },
    "stacked-delivery-read": {
        "forge.repository.read.v1",
        "forge.repository.branch.read.v1",
        "forge.change.read.v1",
        "forge.stack.changes.list-complete.v1",
    },
    "gitlab-review-read": {
        "forge.auth.current-user.read.v1",
        "forge.repository.read.v1",
        "forge.repository.branch.read.v1",
        "forge.change.read.v1",
        "forge.change.discussions.list-complete.v1",
        "forge.change.discussion.read.v1",
        "gitlab.change.diff-versions.list-complete.v1",
        "gitlab.change.diff-version.read.v1",
    },
    "gitlab-review-reply": {
        "forge.auth.current-user.read.v1",
        "forge.repository.read.v1",
        "forge.repository.branch.read.v1",
        "forge.change.read.v1",
        "forge.change.discussions.list-complete.v1",
        "forge.change.discussion.read.v1",
        "gitlab.change.diff-versions.list-complete.v1",
        "gitlab.change.diff-version.read.v1",
        "gitlab.change.pipelines.list-complete.v1",
        "gitlab.change.discussion.reply.create.v1",
    },
    "gitlab-review-resolve": {
        "forge.auth.current-user.read.v1",
        "forge.repository.read.v1",
        "forge.repository.branch.read.v1",
        "forge.change.read.v1",
        "forge.change.discussions.list-complete.v1",
        "forge.change.discussion.read.v1",
        "gitlab.change.diff-versions.list-complete.v1",
        "gitlab.change.diff-version.read.v1",
        "gitlab.change.pipelines.list-complete.v1",
        "gitlab.change.discussion.reply.create.v1",
        "gitlab.change.discussion.resolve.set.v1",
    },
}

DEGRADED_PROFILES = {
    "gitlab-review-reply": ("gitlab-review-read",),
    "gitlab-review-resolve": ("gitlab-review-reply", "gitlab-review-read"),
}

HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*(?::[1-9][0-9]{0,4})?$"
)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class ContractError(ValueError):
    pass


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ContractError(message)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def read_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("input is not readable JSON") from exc


def exact_object(
    value: Any,
    *,
    required: set[str],
    optional: set[str] | None = None,
    label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    optional = optional or set()
    keys = set(value)
    if keys != required | (keys & optional):
        missing = sorted(required - keys)
        extra = sorted(keys - required - optional)
        raise ContractError(f"{label} fields invalid: missing={missing}, extra={extra}")
    return value


def nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ContractError(f"{label} must be a non-empty trimmed string")
    return value


def normalized_host(value: Any) -> str:
    host = nonempty_string(value, "host").lower()
    if "://" in host or "/" in host or not HOST_RE.fullmatch(host):
        raise ContractError("host must be an explicit hostname without a scheme or path")
    if ":" in host:
        port = int(host.rsplit(":", 1)[1])
        if port > 65535:
            raise ContractError("host port is invalid")
    return host


def validate_capabilities(value: Any, adapter_id: str) -> dict[str, dict[str, str]]:
    if not isinstance(value, dict):
        raise ContractError(f"adapter {adapter_id} capabilities must be an object")
    result: dict[str, dict[str, str]] = {}
    for capability_id, raw in sorted(value.items()):
        if capability_id not in CAPABILITY_MODES:
            raise ContractError(f"adapter {adapter_id} has unknown capability {capability_id}")
        item = exact_object(
            raw,
            required={"support", "operation"},
            label=f"adapter {adapter_id} capability {capability_id}",
        )
        support = item.get("support")
        if support not in SUPPORT_STATES:
            raise ContractError(f"adapter {adapter_id} capability support is invalid")
        operation = nonempty_string(item.get("operation"), "capability operation")
        result[capability_id] = {"support": support, "operation": operation}
    return result


def validate_adapter(value: Any) -> dict[str, Any]:
    adapter = exact_object(
        value,
        required={
            "id",
            "kind",
            "version",
            "forges",
            "host",
            "actor",
            "evidence",
            "capabilities",
        },
        label="adapter",
    )
    adapter_id = nonempty_string(adapter.get("id"), "adapter id")
    if not ID_RE.fullmatch(adapter_id):
        raise ContractError("adapter id is invalid")
    if adapter.get("kind") not in ADAPTER_KINDS:
        raise ContractError(f"adapter {adapter_id} kind is invalid")
    nonempty_string(adapter.get("version"), f"adapter {adapter_id} version")
    forges = adapter.get("forges")
    if (
        not isinstance(forges, list)
        or not forges
        or any(item not in FORGES for item in forges)
        or forges != sorted(set(forges))
    ):
        raise ContractError(f"adapter {adapter_id} forges are invalid")
    host = normalized_host(adapter.get("host"))

    actor = exact_object(
        adapter.get("actor"),
        required={"id", "verified"},
        label=f"adapter {adapter_id} actor",
    )
    if actor.get("id") is not None:
        nonempty_string(actor.get("id"), f"adapter {adapter_id} actor id")
    if not isinstance(actor.get("verified"), bool):
        raise ContractError(f"adapter {adapter_id} actor verified must be boolean")
    if actor.get("verified") and actor.get("id") is None:
        raise ContractError(f"adapter {adapter_id} verified actor requires an id")

    evidence = exact_object(
        adapter.get("evidence"),
        required={
            "explicit_host_per_call",
            "raw_structured_payload",
            "stable_object_ids",
            "full_commit_ids",
            "pagination",
            "change_diff_truncation",
            "write_retry",
            "unknown_write_result",
            "server_receipt_id",
        },
        label=f"adapter {adapter_id} evidence",
    )
    for key in (
        "explicit_host_per_call",
        "raw_structured_payload",
        "stable_object_ids",
        "full_commit_ids",
        "server_receipt_id",
    ):
        if not isinstance(evidence.get(key), bool):
            raise ContractError(f"adapter {adapter_id} evidence {key} must be boolean")
    if evidence.get("pagination") not in {"page-chain-v1", "opaque", "none"}:
        raise ContractError(f"adapter {adapter_id} pagination evidence is invalid")
    if evidence.get("change_diff_truncation") not in {"explicit", "hidden", "none"}:
        raise ContractError(
            f"adapter {adapter_id} change-diff truncation evidence is invalid"
        )
    if evidence.get("write_retry") not in {"never", "automatic", "unknown"}:
        raise ContractError(f"adapter {adapter_id} write retry evidence is invalid")
    if evidence.get("unknown_write_result") not in {"exposed", "hidden"}:
        raise ContractError(f"adapter {adapter_id} unknown-write evidence is invalid")

    return {
        **adapter,
        "host": host,
        "forges": list(forges),
        "actor": dict(actor),
        "evidence": dict(evidence),
        "capabilities": validate_capabilities(adapter.get("capabilities"), adapter_id),
    }


def validate_inventory(value: Any) -> dict[str, Any]:
    inventory = exact_object(
        value,
        required={"schema", "adapters"},
        label="inventory",
    )
    if inventory.get("schema") != INVENTORY_SCHEMA:
        raise ContractError("inventory schema is unsupported")
    raw_adapters = inventory.get("adapters")
    if not isinstance(raw_adapters, list) or not raw_adapters:
        raise ContractError("inventory adapters must be a non-empty array")
    adapters = [validate_adapter(item) for item in raw_adapters]
    ids = [item["id"] for item in adapters]
    if len(set(ids)) != len(ids):
        raise ContractError("inventory adapter ids must be unique")
    return {"schema": INVENTORY_SCHEMA, "adapters": sorted(adapters, key=lambda item: item["id"])}


def validate_plan(value: Any) -> dict[str, Any]:
    plan = exact_object(
        value,
        required={
            "schema",
            "profile",
            "forge",
            "host",
            "expected_actor_id",
            "preferred_adapter_ids",
            "allow_degraded_read",
            "write_state",
        },
        label="plan",
    )
    if plan.get("schema") != PLAN_SCHEMA:
        raise ContractError("plan schema is unsupported")
    profile = plan.get("profile")
    if profile not in PROFILE_REQUIREMENTS:
        raise ContractError("plan profile is unsupported")
    forge = plan.get("forge")
    if forge not in FORGES:
        raise ContractError("plan forge is unsupported")
    if profile.startswith("gitlab-") and forge != "gitlab":
        raise ContractError("GitLab review profiles require forge=gitlab")
    host = normalized_host(plan.get("host"))
    actor_id = plan.get("expected_actor_id")
    if actor_id is not None:
        actor_id = nonempty_string(actor_id, "expected_actor_id")
    if profile in {"gitlab-review-reply", "gitlab-review-resolve"} and actor_id is None:
        raise ContractError("write profiles require expected_actor_id")
    preferred = plan.get("preferred_adapter_ids")
    if (
        not isinstance(preferred, list)
        or any(not isinstance(item, str) or not ID_RE.fullmatch(item) for item in preferred)
        or len(set(preferred)) != len(preferred)
    ):
        raise ContractError("preferred_adapter_ids are invalid")
    if not isinstance(plan.get("allow_degraded_read"), bool):
        raise ContractError("allow_degraded_read must be boolean")
    write_state = exact_object(
        plan.get("write_state"),
        required={"operation", "outcome", "adapter_id"},
        label="write_state",
    )
    operation = write_state.get("operation")
    outcome = write_state.get("outcome")
    adapter_id = write_state.get("adapter_id")
    if operation not in {"none", "reply", "resolve"}:
        raise ContractError("write_state operation is invalid")
    if outcome not in {"not-attempted", "failed-before-send", "confirmed", "ambiguous"}:
        raise ContractError("write_state outcome is invalid")
    if adapter_id is not None and (
        not isinstance(adapter_id, str) or not ID_RE.fullmatch(adapter_id)
    ):
        raise ContractError("write_state adapter_id is invalid")
    if outcome in {"confirmed", "ambiguous"} and adapter_id is None:
        raise ContractError("confirmed or ambiguous writes require adapter_id")
    if outcome == "ambiguous" and operation == "none":
        raise ContractError("ambiguous write requires a write operation")
    return {
        **plan,
        "host": host,
        "expected_actor_id": actor_id,
        "preferred_adapter_ids": list(preferred),
        "write_state": dict(write_state),
    }


def base_evidence_ok(adapter: dict[str, Any]) -> bool:
    evidence = adapter["evidence"]
    return all(
        evidence[key]
        for key in (
            "explicit_host_per_call",
            "raw_structured_payload",
            "stable_object_ids",
            "full_commit_ids",
        )
    )


def capability_set(adapter: dict[str, Any]) -> set[str]:
    return {
        capability_id
        for capability_id, item in adapter["capabilities"].items()
        if item["support"] == "probed"
    }


def adapter_reasons(
    adapter: dict[str, Any],
    plan: dict[str, Any],
    profile: str,
) -> list[str]:
    reasons: list[str] = []
    if plan["forge"] not in adapter["forges"]:
        reasons.append("FORGE_UNSUPPORTED")
    if adapter["host"] != plan["host"]:
        reasons.append("HOST_MISMATCH")
    expected_actor = plan["expected_actor_id"]
    if expected_actor is not None and (
        not adapter["actor"]["verified"] or adapter["actor"]["id"] != expected_actor
    ):
        reasons.append("WRONG_IDENTITY")
    if not base_evidence_ok(adapter):
        reasons.append("EVIDENCE_INCOMPLETE")
    supported = capability_set(adapter)
    required = PROFILE_REQUIREMENTS[profile]
    if not required <= supported:
        reasons.append("CAPABILITY_MISSING")
    if required & LIST_CAPABILITIES and adapter["evidence"]["pagination"] != "page-chain-v1":
        reasons.append("PAGINATION_OPAQUE")
    if (
        "forge.change.files.list-complete.v1" in required
        and adapter["evidence"]["change_diff_truncation"] != "explicit"
    ):
        reasons.append("DIFF_TRUNCATION_OPAQUE")
    if any(CAPABILITY_MODES[item] == "write" for item in required):
        evidence = adapter["evidence"]
        if evidence["write_retry"] != "never":
            reasons.append("UNSAFE_WRITE_RETRY")
        if evidence["unknown_write_result"] != "exposed":
            reasons.append("UNKNOWN_WRITE_HIDDEN")
        if not evidence["server_receipt_id"]:
            reasons.append("SERVER_RECEIPT_UNAVAILABLE")
    return sorted(set(reasons))


def readback_reasons(adapter: dict[str, Any], plan: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if plan["forge"] not in adapter["forges"]:
        reasons.append("FORGE_UNSUPPORTED")
    if adapter["host"] != plan["host"]:
        reasons.append("HOST_MISMATCH")
    expected_actor = plan["expected_actor_id"]
    if expected_actor is not None and (
        not adapter["actor"]["verified"] or adapter["actor"]["id"] != expected_actor
    ):
        reasons.append("WRONG_IDENTITY")
    if not base_evidence_ok(adapter):
        reasons.append("EVIDENCE_INCOMPLETE")
    if "forge.change.discussion.read.v1" not in capability_set(adapter):
        reasons.append("READBACK_CAPABILITY_MISSING")
    return sorted(set(reasons))


def ordered_adapters(inventory: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    preferred = {adapter_id: index for index, adapter_id in enumerate(plan["preferred_adapter_ids"])}
    fallback_index = len(preferred)
    return sorted(
        inventory["adapters"],
        key=lambda item: (preferred.get(item["id"], fallback_index), item["id"]),
    )


def selection_result(
    *,
    status: str,
    requested_profile: str,
    selected_profile: str | None,
    selected_adapter_id: str | None,
    readback_adapter_ids: list[str],
    reason_codes: list[str],
    evaluated: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "status": status,
        "requested_profile": requested_profile,
        "selected_profile": selected_profile,
        "selected_adapter_id": selected_adapter_id,
        "readback_adapter_ids": sorted(readback_adapter_ids),
        "reason_codes": sorted(set(reason_codes)),
        "evaluated": sorted(evaluated, key=lambda item: item["adapter_id"]),
    }


def select_adapter(inventory_value: Any, plan_value: Any) -> dict[str, Any]:
    inventory = validate_inventory(inventory_value)
    plan = validate_plan(plan_value)
    adapters = ordered_adapters(inventory, plan)
    requested = plan["profile"]

    if plan["write_state"]["outcome"] == "confirmed":
        return selection_result(
            status="REPORT_ONLY",
            requested_profile=requested,
            selected_profile=None,
            selected_adapter_id=None,
            readback_adapter_ids=[],
            reason_codes=["WRITE_ALREADY_CONFIRMED"],
            evaluated=[],
        )

    if plan["write_state"]["outcome"] == "ambiguous":
        evaluated = []
        readback = []
        for adapter in adapters:
            reasons = readback_reasons(adapter, plan)
            evaluated.append({"adapter_id": adapter["id"], "reason_codes": reasons})
            if not reasons:
                readback.append(adapter["id"])
        status = "READBACK_ONLY" if readback else "REPORT_ONLY"
        return selection_result(
            status=status,
            requested_profile=requested,
            selected_profile=None,
            selected_adapter_id=None,
            readback_adapter_ids=readback,
            reason_codes=["AMBIGUOUS_WRITE_READBACK_ONLY"] + ([] if readback else ["READBACK_UNAVAILABLE"]),
            evaluated=evaluated,
        )

    profiles = [requested]
    if plan["allow_degraded_read"]:
        profiles.extend(DEGRADED_PROFILES.get(requested, ()))
    all_evaluated: dict[str, set[str]] = {adapter["id"]: set() for adapter in adapters}
    requested_failures: list[str] = []
    for profile_index, profile in enumerate(profiles):
        for adapter in adapters:
            reasons = adapter_reasons(adapter, plan, profile)
            all_evaluated[adapter["id"]].update(reasons)
            if profile_index == 0:
                requested_failures.extend(reasons)
            if not reasons:
                return selection_result(
                    status="READY" if profile == requested else "DEGRADED",
                    requested_profile=requested,
                    selected_profile=profile,
                    selected_adapter_id=adapter["id"],
                    readback_adapter_ids=[],
                    reason_codes=([] if profile == requested else ["DEGRADED_PROFILE_SELECTED"]),
                    evaluated=[
                        {"adapter_id": item["id"], "reason_codes": sorted(all_evaluated[item["id"]])}
                        for item in adapters
                    ],
                )
    return selection_result(
        status="REPORT_ONLY",
        requested_profile=requested,
        selected_profile=None,
        selected_adapter_id=None,
        readback_adapter_ids=[],
        reason_codes=requested_failures or ["NO_ELIGIBLE_ADAPTER"],
        evaluated=[
            {"adapter_id": item["id"], "reason_codes": sorted(all_evaluated[item["id"]])}
            for item in adapters
        ],
    )


def parser() -> JsonArgumentParser:
    root = JsonArgumentParser(
        description="Validate or select forge adapters from local JSON only; no network calls are made."
    )
    commands = root.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-inventory")
    validate.add_argument("--inventory", required=True)
    select = commands.add_parser("select")
    select.add_argument("--inventory", required=True)
    select.add_argument("--plan", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = parser().parse_args(argv)
        if arguments.command == "validate-inventory":
            inventory = validate_inventory(read_json(arguments.inventory))
            print(canonical({"schema": INVENTORY_SCHEMA, "ok": True, "adapter_ids": [item["id"] for item in inventory["adapters"]]}))
            return 0
        if arguments.command == "select":
            result = select_adapter(read_json(arguments.inventory), read_json(arguments.plan))
            print(canonical(result))
            return 0 if result["status"] in {"READY", "DEGRADED", "READBACK_ONLY"} else 2
        raise ContractError("unsupported command")
    except ContractError as exc:
        print(canonical({"schema": ERROR_SCHEMA, "ok": False, "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
