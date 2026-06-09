#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


REVIEW_SCHEMA = "design_intelligence.review.v1"
DECISION_SCHEMA = "design_intelligence.decision.v1"
SEVERITIES = {"P0", "P1", "P2", "P3"}
LENSES = {
    "product-fit",
    "interface-architecture",
    "interaction",
    "accessibility",
    "cognitive-load",
    "visual-communication",
    "ethics-trust",
    "system-governance",
}
CONFIDENCE = {"low", "medium", "high"}
GATE_VALUES = {"pass", "risk", "unknown"}
SURFACE_TYPES = {
    "flow",
    "form",
    "data-view",
    "search-browse",
    "navigation",
    "onboarding",
    "permission-consent",
    "notification-status",
    "empty-error-recovery",
    "settings-admin",
    "content-screen",
    "transaction",
    "design-system-pattern",
}
OBLIGATION_STATUSES = {"met", "risk", "unknown", "not-applicable"}
FINDING_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DECISION_TYPES = {
    "product-framing",
    "interface-architecture",
    "interaction",
    "accessibility",
    "visual-communication",
    "design-system-governance",
    "ethics-trust",
}
DECISION_STATUSES = {"proposed", "accepted", "rejected", "superseded", "needs-validation"}
SOURCE_TYPES = {
    "observed-product",
    "user-research",
    "analytics",
    "support",
    "standard",
    "platform-guidance",
    "design-system",
    "scholarly",
    "benchmark",
    "heuristic",
    "stakeholder",
}


def fail(message: str) -> None:
    print(f"invalid: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def require_non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{path} must be a non-empty string")
    return value


def require_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        fail(f"{path} must be a list of non-empty strings")
    return value


def validate_optional_surface_fields(root: dict[str, Any]) -> None:
    surface_type = root.get("surface_type")
    if surface_type is not None and surface_type not in SURFACE_TYPES:
        fail(f"$.surface_type must be one of {sorted(SURFACE_TYPES)}")

    obligations = root.get("pattern_obligations")
    if obligations is not None:
        if not isinstance(obligations, list):
            fail("$.pattern_obligations must be a list")
        for index, value in enumerate(obligations):
            obligation = require_dict(value, f"$.pattern_obligations[{index}]")
            require_non_empty_string(
                obligation.get("obligation"),
                f"$.pattern_obligations[{index}].obligation",
            )
            if obligation.get("status") not in OBLIGATION_STATUSES:
                fail(
                    f"$.pattern_obligations[{index}].status must be one of "
                    f"{sorted(OBLIGATION_STATUSES)}"
                )
            require_non_empty_string(
                obligation.get("evidence"),
                f"$.pattern_obligations[{index}].evidence",
            )

    validation_limits = root.get("validation_limits")
    if validation_limits is not None:
        require_string_list(validation_limits, "$.validation_limits")


def validate_review(root: dict[str, Any]) -> None:
    require_non_empty_string(root.get("surface"), "$.surface")
    require_non_empty_string(root.get("summary"), "$.summary")
    validate_optional_surface_fields(root)

    context = require_dict(root.get("context"), "$.context")
    require_non_empty_string(context.get("user"), "$.context.user")
    require_non_empty_string(context.get("task"), "$.context.task")
    require_string_list(context.get("evidence"), "$.context.evidence")
    require_string_list(context.get("assumptions"), "$.context.assumptions")

    findings = root.get("findings")
    if not isinstance(findings, list):
        fail("$.findings must be a list")

    seen_ids: set[str] = set()
    for index, finding_value in enumerate(findings):
        finding = require_dict(finding_value, f"$.findings[{index}]")
        finding_id = require_non_empty_string(finding.get("id"), f"$.findings[{index}].id")
        if not FINDING_ID_RE.match(finding_id):
            fail(f"$.findings[{index}].id must be kebab-case")
        if finding_id in seen_ids:
            fail(f"duplicate finding id: {finding_id}")
        seen_ids.add(finding_id)

        if finding.get("severity") not in SEVERITIES:
            fail(f"$.findings[{index}].severity must be one of {sorted(SEVERITIES)}")
        if finding.get("lens") not in LENSES:
            fail(f"$.findings[{index}].lens must be one of {sorted(LENSES)}")
        if finding.get("confidence") not in CONFIDENCE:
            fail(f"$.findings[{index}].confidence must be one of {sorted(CONFIDENCE)}")
        if not isinstance(finding.get("requires_validation"), bool):
            fail(f"$.findings[{index}].requires_validation must be boolean")

        for field in ["evidence", "principle", "impact", "recommendation"]:
            require_non_empty_string(finding.get(field), f"$.findings[{index}].{field}")

    gates = require_dict(root.get("quality_gates"), "$.quality_gates")
    expected_gates = {"accessibility_floor", "task_success", "ethical_ux", "system_fit"}
    if set(gates) != expected_gates:
        fail(f"$.quality_gates must contain exactly {sorted(expected_gates)}")
    for key, value in gates.items():
        if value not in GATE_VALUES:
            fail(f"$.quality_gates.{key} must be one of {sorted(GATE_VALUES)}")

    require_string_list(root.get("next_actions"), "$.next_actions")


def validate_decision(root: dict[str, Any]) -> None:
    decision_id = require_non_empty_string(root.get("decision_id"), "$.decision_id")
    if not FINDING_ID_RE.match(decision_id):
        fail("$.decision_id must be kebab-case")
    validate_optional_surface_fields(root)

    require_non_empty_string(root.get("title"), "$.title")
    require_non_empty_string(root.get("surface"), "$.surface")
    require_non_empty_string(root.get("decision"), "$.decision")
    require_non_empty_string(root.get("rationale"), "$.rationale")
    require_non_empty_string(root.get("owner_or_review_path"), "$.owner_or_review_path")
    require_non_empty_string(root.get("expires_or_revisit_trigger"), "$.expires_or_revisit_trigger")

    if root.get("decision_type") not in DECISION_TYPES:
        fail(f"$.decision_type must be one of {sorted(DECISION_TYPES)}")
    if root.get("status") not in DECISION_STATUSES:
        fail(f"$.status must be one of {sorted(DECISION_STATUSES)}")

    context = require_dict(root.get("context"), "$.context")
    require_non_empty_string(context.get("user"), "$.context.user")
    require_non_empty_string(context.get("task"), "$.context.task")
    require_string_list(context.get("assumptions"), "$.context.assumptions")

    evidence_items = context.get("evidence")
    if not isinstance(evidence_items, list) or not evidence_items:
        fail("$.context.evidence must be a non-empty list")
    weak_only = True
    for index, evidence_value in enumerate(evidence_items):
        evidence = require_dict(evidence_value, f"$.context.evidence[{index}]")
        require_non_empty_string(evidence.get("source"), f"$.context.evidence[{index}].source")
        require_non_empty_string(evidence.get("claim"), f"$.context.evidence[{index}].claim")
        if evidence.get("source_type") not in SOURCE_TYPES:
            fail(f"$.context.evidence[{index}].source_type must be one of {sorted(SOURCE_TYPES)}")
        if evidence.get("strength") not in CONFIDENCE:
            fail(f"$.context.evidence[{index}].strength must be one of {sorted(CONFIDENCE)}")
        if evidence.get("source_type") not in {"heuristic", "stakeholder"} and evidence.get("strength") != "low":
            weak_only = False

    alternatives = root.get("alternatives_rejected")
    if not isinstance(alternatives, list):
        fail("$.alternatives_rejected must be a list")
    for index, alternative_value in enumerate(alternatives):
        alternative = require_dict(alternative_value, f"$.alternatives_rejected[{index}]")
        require_non_empty_string(alternative.get("alternative"), f"$.alternatives_rejected[{index}].alternative")
        require_non_empty_string(alternative.get("reason"), f"$.alternatives_rejected[{index}].reason")

    require_string_list(root.get("accessibility_requirements"), "$.accessibility_requirements")
    require_string_list(root.get("behavioral_requirements"), "$.behavioral_requirements")
    require_string_list(root.get("counter_metrics"), "$.counter_metrics")

    validation_plan = root.get("validation_plan")
    if not isinstance(validation_plan, list) or not validation_plan:
        fail("$.validation_plan must be a non-empty list")
    for index, validation_value in enumerate(validation_plan):
        validation = require_dict(validation_value, f"$.validation_plan[{index}]")
        require_non_empty_string(validation.get("method"), f"$.validation_plan[{index}].method")
        require_non_empty_string(validation.get("signal"), f"$.validation_plan[{index}].signal")
        require_non_empty_string(validation.get("pass_condition"), f"$.validation_plan[{index}].pass_condition")

    if weak_only and root.get("status") == "accepted":
        fail("$.status cannot be accepted when evidence is only heuristic, stakeholder, or low strength")


def validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    root = require_dict(data, "$")

    schema = root.get("schema")
    if schema == REVIEW_SCHEMA:
        validate_review(root)
    elif schema == DECISION_SCHEMA:
        validate_decision(root)
    else:
        fail(f"$.schema must be one of {[REVIEW_SCHEMA, DECISION_SCHEMA]}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_design_intelligence.py <review-output.json>", file=sys.stderr)
        return 2
    validate(Path(argv[1]))
    print("valid=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
