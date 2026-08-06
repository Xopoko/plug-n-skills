#!/usr/bin/env python3
"""Validate portable LLM agent harness design and evaluation artifacts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


DESIGN_SCHEMA = "agent_harness.design.v1"
EVALUATION_SCHEMA = "agent_harness.evaluation_plan.v1"
RUN_RESULT_SCHEMA = "agent_harness.run_result.v1"

TERMINAL_OUTCOMES = {
    "succeeded",
    "partial",
    "failed",
    "blocked",
    "denied",
    "cancelled",
    "timed_out",
    "budget_exhausted",
    "invalid",
}
REQUIRED_LOOP_OUTCOMES = {"succeeded", "failed", "cancelled"}
TRUST_CLASSES = {
    "control_plane",
    "operator",
    "authenticated_external",
    "untrusted_content",
    "unknown",
}
SIDE_EFFECTS = {
    "none",
    "ephemeral",
    "durable_reversible",
    "external_compensatable",
    "irreversible_or_destructive",
}
HIGH_EFFECTS = {"external_compensatable", "irreversible_or_destructive"}
APPROVAL_MODES = {"never", "policy", "always"}
IDEMPOTENCY_MODES = {"not_applicable", "keyed", "reconciled", "unsupported"}
AUTHORITY_CLASSES = {
    "none",
    "observe",
    "propose",
    "execute_scoped",
    "execute_elevated",
}
ORACLE_TYPES = {"deterministic", "human", "llm"}
ORACLE_STATUSES = {"passed", "failed", "not_run"}
REQUIRED_SCENARIO_CLASSES = {
    "policy_denial",
    "context_pressure",
    "recovery",
    "cancellation",
}
RECOMMENDED_SCENARIO_CLASSES = {
    "happy_path",
    "stateful",
    "tool_error",
    "timeout",
    "untrusted_input",
    "noncoding",
}
SYSTEM_COMPONENTS = (
    "harness",
    "provider",
    "model",
    "prompts",
    "tools",
    "policy",
    "context",
    "environment",
    "evaluator",
)


def is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def require_object(
    parent: dict[str, Any], key: str, path: str, errors: list[str]
) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        errors.append(f"{path}.{key}: must be an object")
        return {}
    return value


def require_list(
    parent: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
    *,
    nonempty: bool = True,
) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list):
        errors.append(f"{path}.{key}: must be an array")
        return []
    if nonempty and not value:
        errors.append(f"{path}.{key}: must not be empty")
    return value


def require_string(
    parent: dict[str, Any], key: str, path: str, errors: list[str]
) -> str:
    value = parent.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}.{key}: must be a non-empty string")
        return ""
    return value.strip()


def require_positive_number(
    parent: dict[str, Any], key: str, path: str, errors: list[str]
) -> float | int | None:
    value = parent.get(key)
    if not is_number(value) or value <= 0:
        errors.append(f"{path}.{key}: must be a positive number")
        return None
    return value


def require_positive_integer(
    parent: dict[str, Any], key: str, path: str, errors: list[str]
) -> int | None:
    value = parent.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        errors.append(f"{path}.{key}: must be a positive integer")
        return None
    return value


def validate_string_list(
    values: list[Any], path: str, errors: list[str], *, allow_empty: bool = False
) -> None:
    if not values and not allow_empty:
        return
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path}[{index}]: must be a non-empty string")


def validate_versioned_component(
    value: Any, path: str, errors: list[str]
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object with id and version")
        return
    require_string(value, "id", path, errors)
    require_string(value, "version", path, errors)


def validate_system_tuple(
    data: dict[str, Any], path: str, errors: list[str]
) -> None:
    system_tuple = require_object(data, "system_tuple", path, errors)
    for component in SYSTEM_COMPONENTS:
        if component not in system_tuple:
            errors.append(f"{path}.system_tuple.{component}: is required")
            continue
        validate_versioned_component(
            system_tuple[component], f"{path}.system_tuple.{component}", errors
        )


def validate_design(
    data: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    root = "$"
    outcome = require_object(data, "outcome", root, errors)
    require_string(outcome, "description", "$.outcome", errors)
    require_string(outcome, "workload", "$.outcome", errors)
    mode = require_string(outcome, "mode", "$.outcome", errors)
    if mode and mode not in {"interactive", "batch", "service", "scheduled", "embedded"}:
        errors.append("$.outcome.mode: must be interactive, batch, service, scheduled, or embedded")
    trust_boundaries = require_list(outcome, "trust_boundaries", "$.outcome", errors)
    validate_string_list(trust_boundaries, "$.outcome.trust_boundaries", errors)
    side_effects = require_list(
        outcome, "side_effects", "$.outcome", errors, nonempty=False
    )
    validate_string_list(
        side_effects, "$.outcome.side_effects", errors, allow_empty=True
    )

    success_criteria = require_list(data, "success_criteria", root, errors)
    validate_string_list(success_criteria, "$.success_criteria", errors)
    non_goals = require_list(data, "non_goals", root, errors)
    validate_string_list(non_goals, "$.non_goals", errors)

    provider = require_object(data, "provider_boundary", root, errors)
    capabilities = require_list(
        provider, "required_capabilities", "$.provider_boundary", errors, nonempty=False
    )
    validate_string_list(
        capabilities,
        "$.provider_boundary.required_capabilities",
        errors,
        allow_empty=True,
    )
    require_string(provider, "unsupported_behavior", "$.provider_boundary", errors)
    require_string(provider, "degraded_behavior", "$.provider_boundary", errors)

    loop = require_object(data, "control_loop", root, errors)
    states = require_list(loop, "states", "$.control_loop", errors)
    validate_string_list(states, "$.control_loop.states", errors)
    state_names = {value for value in states if isinstance(value, str)}
    transitions = require_list(loop, "transitions", "$.control_loop", errors)
    for index, transition in enumerate(transitions):
        path = f"$.control_loop.transitions[{index}]"
        if not isinstance(transition, dict):
            errors.append(f"{path}: must be an object")
            continue
        source = require_string(transition, "from", path, errors)
        target = require_string(transition, "to", path, errors)
        require_string(transition, "event", path, errors)
        require_string(transition, "guard", path, errors)
        effects = require_list(transition, "effects", path, errors, nonempty=False)
        validate_string_list(effects, f"{path}.effects", errors, allow_empty=True)
        if source and source not in state_names:
            errors.append(f"{path}.from: is not declared in $.control_loop.states")
        if target and target not in state_names:
            errors.append(f"{path}.to: is not declared in $.control_loop.states")
    invariants = require_list(loop, "invariants", "$.control_loop", errors)
    validate_string_list(invariants, "$.control_loop.invariants", errors)
    outcomes = require_list(loop, "terminal_outcomes", "$.control_loop", errors)
    validate_string_list(outcomes, "$.control_loop.terminal_outcomes", errors)
    outcome_set = {value for value in outcomes if isinstance(value, str)}
    unknown_outcomes = outcome_set - TERMINAL_OUTCOMES
    if unknown_outcomes:
        errors.append(
            "$.control_loop.terminal_outcomes: unknown values "
            + ", ".join(sorted(unknown_outcomes))
        )
    missing_outcomes = REQUIRED_LOOP_OUTCOMES - outcome_set
    if missing_outcomes:
        errors.append(
            "$.control_loop.terminal_outcomes: missing "
            + ", ".join(sorted(missing_outcomes))
        )
    bounds = require_object(loop, "bounds", "$.control_loop", errors)
    require_positive_integer(bounds, "max_steps", "$.control_loop.bounds", errors)
    require_positive_number(
        bounds, "wall_time_seconds", "$.control_loop.bounds", errors
    )
    if "max_tokens" in bounds:
        require_positive_integer(bounds, "max_tokens", "$.control_loop.bounds", errors)
    if "max_cost" in bounds:
        require_positive_number(bounds, "max_cost", "$.control_loop.bounds", errors)
    if "max_concurrency" in bounds:
        require_positive_integer(
            bounds, "max_concurrency", "$.control_loop.bounds", errors
        )

    tools = require_list(data, "tools", root, errors, nonempty=False)
    seen_tools: set[str] = set()
    if not tools:
        warnings.append("$.tools: no tools declared; confirm that a model-only harness is intentional")
    for index, tool in enumerate(tools):
        path = f"$.tools[{index}]"
        if not isinstance(tool, dict):
            errors.append(f"{path}: must be an object")
            continue
        name = require_string(tool, "name", path, errors)
        if name in seen_tools:
            errors.append(f"{path}.name: duplicate tool name {name}")
        seen_tools.add(name)
        for schema_key in ("input_schema", "output_schema"):
            schema_value = tool.get(schema_key)
            if not isinstance(schema_value, (dict, str)) or (
                isinstance(schema_value, str) and not schema_value.strip()
            ):
                errors.append(f"{path}.{schema_key}: must be a schema object or reference")
        effect = require_string(tool, "effect", path, errors)
        if effect and effect not in SIDE_EFFECTS:
            errors.append(f"{path}.effect: unknown side-effect class {effect}")
        require_positive_number(tool, "timeout_seconds", path, errors)
        authority = require_string(tool, "authority", path, errors)
        if authority and authority not in AUTHORITY_CLASSES:
            errors.append(f"{path}.authority: unknown authority class {authority}")
        approval = require_string(tool, "approval", path, errors)
        if approval and approval not in APPROVAL_MODES:
            errors.append(f"{path}.approval: must be never, policy, or always")
        idempotency = require_string(tool, "idempotency", path, errors)
        if idempotency and idempotency not in IDEMPOTENCY_MODES:
            errors.append(f"{path}.idempotency: unknown idempotency mode {idempotency}")
        if effect in HIGH_EFFECTS and approval == "never":
            errors.append(f"{path}.approval: external or irreversible effects cannot use never")
        if effect in HIGH_EFFECTS:
            require_string(tool, "reconciliation", path, errors)
            if idempotency == "not_applicable":
                errors.append(
                    f"{path}.idempotency: external or irreversible effects need keyed, reconciled, or unsupported with explicit reconciliation"
                )

    state = require_object(data, "state", root, errors)
    for key in (
        "state_schema",
        "canonical_log",
        "checkpoint",
        "replay",
        "resume",
        "reconciliation",
    ):
        require_string(state, key, "$.state", errors)

    context = require_object(data, "context", root, errors)
    sources = require_list(context, "sources", "$.context", errors)
    for index, source in enumerate(sources):
        path = f"$.context.sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{path}: must be an object")
            continue
        require_string(source, "name", path, errors)
        trust = require_string(source, "trust", path, errors)
        if trust and trust not in TRUST_CLASSES:
            errors.append(f"{path}.trust: unknown trust class {trust}")
    require_positive_number(context, "token_budget", "$.context", errors)
    require_string(context, "compaction", "$.context", errors)

    policy = require_object(data, "policy", root, errors)
    decision = require_string(policy, "default_decision", "$.policy", errors)
    if decision and decision not in {"deny", "ask", "allow"}:
        errors.append("$.policy.default_decision: must be deny, ask, or allow")
    if decision == "allow":
        warnings.append("$.policy.default_decision: allow requires a narrowly trusted deployment boundary")
    require_string(policy, "approval", "$.policy", errors)
    require_string(policy, "isolation", "$.policy", errors)

    recovery = require_object(data, "recovery", root, errors)
    attempts = recovery.get("max_attempts")
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
        errors.append("$.recovery.max_attempts: must be an integer of at least 1")
    retryable = require_list(
        recovery, "retryable_failures", "$.recovery", errors, nonempty=False
    )
    validate_string_list(
        retryable, "$.recovery.retryable_failures", errors, allow_empty=True
    )
    if isinstance(attempts, int) and attempts > 1 and not retryable:
        errors.append("$.recovery.retryable_failures: required when max_attempts is greater than 1")
    require_string(recovery, "ambiguous_effect", "$.recovery", errors)

    cancellation = require_object(data, "cancellation", root, errors)
    require_string(cancellation, "propagation", "$.cancellation", errors)
    require_string(cancellation, "safe_stop", "$.cancellation", errors)

    observability = require_object(data, "observability", root, errors)
    require_string(observability, "event_schema", "$.observability", errors)
    require_string(observability, "redaction", "$.observability", errors)

    delegation = require_object(data, "delegation", root, errors)
    enabled = delegation.get("enabled")
    if not isinstance(enabled, bool):
        errors.append("$.delegation.enabled: must be a boolean")
    require_string(delegation, "rationale", "$.delegation", errors)
    if enabled is True:
        require_positive_integer(delegation, "max_children", "$.delegation", errors)
        require_positive_integer(delegation, "max_depth", "$.delegation", errors)
        child = require_object(delegation, "child_contract", "$.delegation", errors)
        child_authority = require_string(
            child, "authority_ceiling", "$.delegation.child_contract", errors
        )
        if child_authority and child_authority not in AUTHORITY_CLASSES:
            errors.append(
                "$.delegation.child_contract.authority_ceiling: unknown authority class "
                + child_authority
            )
        require_string(child, "tool_scope", "$.delegation.child_contract", errors)
        require_string(child, "result_schema", "$.delegation.child_contract", errors)
        require_string(child, "cancellation", "$.delegation.child_contract", errors)

    handoff = require_object(data, "evaluation_handoff", root, errors)
    claims = require_list(handoff, "claims", "$.evaluation_handoff", errors)
    scenarios = require_list(handoff, "scenarios", "$.evaluation_handoff", errors)
    validate_string_list(claims, "$.evaluation_handoff.claims", errors)
    validate_string_list(scenarios, "$.evaluation_handoff.scenarios", errors)

    risks = require_list(data, "risks", root, errors)
    validate_string_list(risks, "$.risks", errors)


def validate_evaluation_plan(
    data: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    validate_system_tuple(data, "$", errors)

    suite = require_object(data, "task_suite", "$", errors)
    require_string(suite, "id", "$.task_suite", errors)
    require_string(suite, "version", "$.task_suite", errors)
    scenario_ids = require_list(suite, "scenario_ids", "$.task_suite", errors)
    validate_string_list(scenario_ids, "$.task_suite.scenario_ids", errors)
    require_string(suite, "reset_procedure", "$.task_suite", errors)
    require_string(suite, "seed_policy", "$.task_suite", errors)
    require_string(suite, "ordering_policy", "$.task_suite", errors)

    variants = require_list(data, "variants", "$", errors)
    for index, variant in enumerate(variants):
        path = f"$.variants[{index}]"
        if not isinstance(variant, dict):
            errors.append(f"{path}: must be an object")
            continue
        require_string(variant, "id", path, errors)
        changes = require_list(variant, "changes", path, errors)
        validate_string_list(changes, f"{path}.changes", errors)

    baselines = require_list(data, "baselines", "$", errors)
    validate_string_list(baselines, "$.baselines", errors)

    oracles = require_list(data, "oracles", "$", errors)
    oracle_types: set[str] = set()
    for index, oracle in enumerate(oracles):
        path = f"$.oracles[{index}]"
        if not isinstance(oracle, dict):
            errors.append(f"{path}: must be an object")
            continue
        require_string(oracle, "id", path, errors)
        oracle_type = require_string(oracle, "type", path, errors)
        if oracle_type and oracle_type not in ORACLE_TYPES:
            errors.append(f"{path}.type: must be deterministic, human, or llm")
        oracle_types.add(oracle_type)
        require_string(oracle, "target", path, errors)
        require_string(oracle, "version", path, errors)
    if oracles and not ({"deterministic", "human"} & oracle_types):
        errors.append("$.oracles: LLM-only judging is not sufficient; add a deterministic or human oracle")

    trials = data.get("repeated_trials")
    if not isinstance(trials, int) or isinstance(trials, bool) or trials < 1:
        errors.append("$.repeated_trials: must be a positive integer")
    elif trials < 2:
        warnings.append("$.repeated_trials: one trial cannot measure repeated reliability")

    injections = require_list(data, "fault_injection", "$", errors)
    for index, injection in enumerate(injections):
        path = f"$.fault_injection[{index}]"
        if not isinstance(injection, dict):
            errors.append(f"{path}: must be an object")
            continue
        require_string(injection, "id", path, errors)
        require_string(injection, "target", path, errors)
        require_string(injection, "method", path, errors)

    analysis = require_object(data, "analysis", "$", errors)
    require_string(analysis, "uncertainty_method", "$.analysis", errors)
    require_string(analysis, "exclusion_policy", "$.analysis", errors)
    residual_risks = require_list(data, "residual_risks", "$", errors)
    validate_string_list(residual_risks, "$.residual_risks", errors)

    metrics = require_list(data, "metrics", "$", errors)
    metric_names: set[str] = set()
    for index, metric in enumerate(metrics):
        path = f"$.metrics[{index}]"
        if not isinstance(metric, dict):
            errors.append(f"{path}: must be an object")
            continue
        name = require_string(metric, "name", path, errors)
        if name in metric_names:
            errors.append(f"{path}.name: duplicate metric {name}")
        metric_names.add(name)
        require_string(metric, "definition", path, errors)
        require_string(metric, "denominator", path, errors)

    scenarios = require_list(data, "scenarios", "$", errors)
    scenario_classes: set[str] = set()
    declared_scenario_ids: set[str] = set()
    for index, scenario in enumerate(scenarios):
        path = f"$.scenarios[{index}]"
        if not isinstance(scenario, dict):
            errors.append(f"{path}: must be an object")
            continue
        scenario_id = require_string(scenario, "id", path, errors)
        if scenario_id in declared_scenario_ids:
            errors.append(f"{path}.id: duplicate scenario {scenario_id}")
        declared_scenario_ids.add(scenario_id)
        classes = require_list(scenario, "classes", path, errors)
        validate_string_list(classes, f"{path}.classes", errors)
        class_set = {value for value in classes if isinstance(value, str)}
        if "happy_path" in class_set and class_set - {"happy_path", "stateful", "noncoding"}:
            errors.append(
                f"{path}.classes: happy_path cannot share a scenario with injected failure classes"
            )
        scenario_classes.update(class_set)
    missing_required = REQUIRED_SCENARIO_CLASSES - scenario_classes
    if missing_required:
        errors.append(
            "$.scenarios: missing required classes "
            + ", ".join(sorted(missing_required))
        )
    missing_recommended = RECOMMENDED_SCENARIO_CLASSES - scenario_classes
    if missing_recommended:
        warnings.append(
            "$.scenarios: recommended classes not covered: "
            + ", ".join(sorted(missing_recommended))
        )
    missing_suite_scenarios = {
        value
        for value in scenario_ids
        if isinstance(value, str) and value not in declared_scenario_ids
    }
    if missing_suite_scenarios:
        errors.append(
            "$.task_suite.scenario_ids: missing scenario definitions for "
            + ", ".join(sorted(missing_suite_scenarios))
        )

    gates = require_list(data, "release_gates", "$", errors)
    for index, gate in enumerate(gates):
        path = f"$.release_gates[{index}]"
        if not isinstance(gate, dict):
            errors.append(f"{path}: must be an object")
            continue
        gate_metric = require_string(gate, "metric", path, errors)
        if gate_metric and gate_metric not in metric_names:
            errors.append(f"{path}.metric: is not declared in $.metrics")
        operator = require_string(gate, "operator", path, errors)
        if operator and operator not in {">=", "<=", "==", "zero"}:
            errors.append(f"{path}.operator: must be >=, <=, ==, or zero")
        if "threshold" not in gate or not isinstance(gate["threshold"], (int, float, bool)):
            errors.append(f"{path}.threshold: must be numeric or boolean")
        if not isinstance(gate.get("blocking"), bool):
            errors.append(f"{path}.blocking: must be a boolean")

    provenance = require_list(data, "provenance", "$", errors)
    validate_string_list(provenance, "$.provenance", errors)


def validate_run_result(
    data: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    del warnings
    require_string(data, "run_id", "$", errors)
    require_string(data, "scenario_id", "$", errors)
    validate_system_tuple(data, "$", errors)

    status = require_string(data, "status", "$", errors)
    if status and status not in TERMINAL_OUTCOMES:
        errors.append(f"$.status: unknown terminal status {status}")

    metrics = data.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        errors.append("$.metrics: must be a non-empty object")
    require_string(data, "trace_ref", "$", errors)

    terminal = require_object(data, "terminal", "$", errors)
    for key in (
        "reason",
        "started_at",
        "ended_at",
        "terminal_event_id",
        "integrity_digest",
    ):
        require_string(terminal, key, "$.terminal", errors)

    failures = data.get("failures")
    if not isinstance(failures, list):
        errors.append("$.failures: must be an array")
        failures = []
    blocking_failures = 0
    for index, failure in enumerate(failures):
        path = f"$.failures[{index}]"
        if not isinstance(failure, dict):
            errors.append(f"{path}: must be an object")
            continue
        require_string(failure, "code", path, errors)
        require_string(failure, "source", path, errors)
        require_string(failure, "evidence_ref", path, errors)
        if not isinstance(failure.get("blocking"), bool):
            errors.append(f"{path}.blocking: must be a boolean")
        elif failure["blocking"]:
            blocking_failures += 1

    evidence = require_object(data, "evidence", "$", errors)
    oracle_results = require_list(evidence, "oracle_results", "$.evidence", errors)
    oracle_statuses: list[str] = []
    for index, oracle in enumerate(oracle_results):
        path = f"$.evidence.oracle_results[{index}]"
        if not isinstance(oracle, dict):
            errors.append(f"{path}: must be an object")
            continue
        require_string(oracle, "id", path, errors)
        oracle_status = require_string(oracle, "status", path, errors)
        if oracle_status and oracle_status not in ORACLE_STATUSES:
            errors.append(f"{path}.status: must be passed, failed, or not_run")
        oracle_statuses.append(oracle_status)
        require_string(oracle, "evidence_ref", path, errors)
    policy_events = require_list(
        evidence, "policy_events", "$.evidence", errors, nonempty=False
    )
    for index, event in enumerate(policy_events):
        path = f"$.evidence.policy_events[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{path}: must be an object")
            continue
        require_string(event, "decision", path, errors)
        require_string(event, "event_ref", path, errors)
    effect_records = require_list(
        evidence, "effect_records", "$.evidence", errors, nonempty=False
    )
    for index, effect in enumerate(effect_records):
        path = f"$.evidence.effect_records[{index}]"
        if not isinstance(effect, dict):
            errors.append(f"{path}: must be an object")
            continue
        require_string(effect, "intent_id", path, errors)
        require_string(effect, "result_ref", path, errors)
        require_string(effect, "effect_id", path, errors)
    unresolved_effects = require_list(
        evidence, "unresolved_effects", "$.evidence", errors, nonempty=False
    )
    validate_string_list(
        unresolved_effects,
        "$.evidence.unresolved_effects",
        errors,
        allow_empty=True,
    )
    require_string(evidence, "post_state_ref", "$.evidence", errors)
    grade = require_string(evidence, "evidence_grade", "$.evidence", errors)
    if grade and grade not in {"E0", "E1", "E2", "E3", "E4", "E5"}:
        errors.append("$.evidence.evidence_grade: must be E0, E1, E2, E3, E4, or E5")
    redactions = require_list(
        evidence, "redactions", "$.evidence", errors, nonempty=False
    )
    validate_string_list(redactions, "$.evidence.redactions", errors, allow_empty=True)

    if status == "succeeded":
        if any(value != "passed" for value in oracle_statuses):
            errors.append("$.status: succeeded requires every oracle result to be passed")
        if blocking_failures:
            errors.append("$.status: succeeded cannot contain a blocking failure")
        if unresolved_effects:
            errors.append("$.status: succeeded cannot contain unresolved effects")

    usage = require_object(data, "usage", "$", errors)
    for key in ("tokens", "latency_ms", "cost"):
        value = usage.get(key)
        if not is_number(value) or value < 0:
            errors.append(f"$.usage.{key}: must be a non-negative number")

    versions = data.get("artifact_versions")
    if not isinstance(versions, dict) or not versions:
        errors.append("$.artifact_versions: must be a non-empty object")
    elif any(not isinstance(value, str) or not value.strip() for value in versions.values()):
        errors.append("$.artifact_versions: every value must be a non-empty string")
    else:
        required_versions = {"design", "evaluation_plan", "scenario"}
        missing_versions = required_versions - set(versions)
        if missing_versions:
            errors.append(
                "$.artifact_versions: missing " + ", ".join(sorted(missing_versions))
            )


def validate(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    schema = data.get("schema")
    if schema == DESIGN_SCHEMA:
        validate_design(data, errors, warnings)
    elif schema == EVALUATION_SCHEMA:
        validate_evaluation_plan(data, errors, warnings)
    elif schema == RUN_RESULT_SCHEMA:
        validate_run_result(data, errors, warnings)
    else:
        errors.append(
            "$.schema: must be one of "
            + ", ".join((DESIGN_SCHEMA, EVALUATION_SCHEMA, RUN_RESULT_SCHEMA))
        )
    return errors, warnings


def load_artifact(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"$: cannot read artifact: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"$: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
    if not isinstance(data, dict):
        return None, "$: artifact must be a JSON object"
    return data, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a vendor-neutral LLM agent harness artifact."
    )
    parser.add_argument("artifact", help="Path to design, evaluation-plan, or run-result JSON")
    parser.add_argument("--json", action="store_true", help="Emit a JSON validation result")
    args = parser.parse_args()

    path = Path(args.artifact)
    data, load_error = load_artifact(path)
    if load_error:
        errors, warnings = [load_error], []
        artifact_schema = None
    else:
        assert data is not None
        errors, warnings = validate(data)
        artifact_schema = data.get("schema")

    result = {
        "schema": "agent_harness.validation_result.v1",
        "path": str(path),
        "artifact_schema": artifact_schema,
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif errors:
        print("Harness artifact is invalid:")
        for error in errors:
            print(f"- {error}")
        for warning in warnings:
            print(f"WARNING: {warning}")
    else:
        print("Harness artifact is valid")
        for warning in warnings:
            print(f"WARNING: {warning}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
