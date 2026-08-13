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
RUN_RESULT_RECONFIGURATION_SCHEMA = "agent_harness.run_result.v2"

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
RECONFIGURATION_SCENARIO_CLASSES = {
    "reconfiguration_invalid_candidate",
    "reconfiguration_capability_loss",
    "reconfiguration_partial_initialization",
    "reconfiguration_concurrent_generations",
    "reconfiguration_late_result",
    "reconfiguration_post_activation_failure",
    "reconfiguration_stale_rollback",
    "reconfiguration_rollback",
    "reconfiguration_external_effect_after_commit",
    "reconfiguration_isolation_leak",
}
RECONFIGURATION_ZERO_METRICS = {
    "generation_misbinding_count",
    "generation_evidence_gap_count",
    "partial_activation_count",
    "unauthorized_capability_change_count",
    "stale_rollback_overwrite_count",
    "false_rollback_success_count",
    "external_effect_misreport_count",
    "isolation_leak_count",
}
BINDING_POLICIES = {"pin", "explicit_migrate"}
RETIREMENT_MODES = {"drain", "cancel", "drain_then_cancel", "migrate"}
RETIREMENT_TIMEOUT_BEHAVIORS = {
    "cancel_and_fence",
    "fence_and_quarantine",
    "rollback_via_compare_and_swap",
}
ISOLATION_BOUNDARY_TYPES = {"same_process", "process", "vm", "container", "wasm"}
ISOLATION_TRUST_MODELS = {"reviewed_trusted", "untrusted"}
RUNTIME_COMPONENT_KINDS = {
    "provider_adapter",
    "tool_registry",
    "executor",
    "policy",
    "context_builder",
    "control_loop",
    "state_store",
    "memory_store",
    "sandbox",
    "module",
    "scheduler",
    "session",
}
REQUIRED_RUNTIME_COMPONENT_KINDS = {
    "provider_adapter",
    "tool_registry",
    "executor",
    "policy",
    "context_builder",
    "control_loop",
    "state_store",
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
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def reject_nonstandard_json_constant(value: str) -> Any:
    raise ValueError(f"non-standard JSON constant {value}")


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


def reject_unknown_keys(
    value: dict[str, Any], allowed: set[str], path: str, errors: list[str]
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append(f"{path}: unknown fields: " + ", ".join(unknown))


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


def validate_runtime_reconfiguration(
    data: dict[str, Any], errors: list[str]
) -> bool:
    """Validate the optional, backward-compatible live reconfiguration claim."""
    if "runtime_reconfiguration" not in data:
        return False

    value = data.get("runtime_reconfiguration")
    path = "$.runtime_reconfiguration"
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return False
    reject_unknown_keys(
        value,
        {
            "supported",
            "rationale",
            "candidate_generation",
            "activation",
            "run_binding",
            "isolation",
            "rollback",
            "evidence",
        },
        path,
        errors,
    )

    supported = value.get("supported")
    if not isinstance(supported, bool):
        errors.append(f"{path}.supported: must be a boolean")
    require_string(value, "rationale", path, errors)
    if supported is not True:
        if supported is False:
            unexpected = sorted(set(value) - {"supported", "rationale"})
            if unexpected:
                errors.append(
                    f"{path}: unsupported reconfiguration cannot declare activation fields: "
                    + ", ".join(unexpected)
                )
        return False

    candidate = require_object(value, "candidate_generation", path, errors)
    candidate_path = f"{path}.candidate_generation"
    reject_unknown_keys(
        candidate,
        {
            "id_schema",
            "config_revision",
            "config_digest",
            "compatibility_policy",
            "state_migration",
            "provenance",
            "components",
        },
        candidate_path,
        errors,
    )
    for key in (
        "id_schema",
        "config_revision",
        "config_digest",
        "compatibility_policy",
        "state_migration",
    ):
        require_string(candidate, key, candidate_path, errors)
    provenance = require_list(candidate, "provenance", candidate_path, errors)
    validate_string_list(provenance, f"{candidate_path}.provenance", errors)
    components = require_list(candidate, "components", candidate_path, errors)
    component_ids: set[str] = set()
    component_kinds: set[str] = set()
    provider_capabilities: set[str] = set()
    for index, component in enumerate(components):
        component_path = f"{candidate_path}.components[{index}]"
        if not isinstance(component, dict):
            errors.append(f"{component_path}: must be an object")
            continue
        reject_unknown_keys(
            component,
            {"id", "kind", "revision", "interface_version", "capabilities"},
            component_path,
            errors,
        )
        component_id = require_string(component, "id", component_path, errors)
        if component_id in component_ids:
            errors.append(f"{component_path}.id: duplicate component id {component_id}")
        component_ids.add(component_id)
        kind = require_string(component, "kind", component_path, errors)
        if kind and kind not in RUNTIME_COMPONENT_KINDS:
            errors.append(
                f"{component_path}.kind: unknown runtime component kind {kind}"
            )
        component_kinds.add(kind)
        for key in ("revision", "interface_version"):
            require_string(component, key, component_path, errors)
        capabilities = require_list(
            component, "capabilities", component_path, errors, nonempty=False
        )
        validate_string_list(
            capabilities,
            f"{component_path}.capabilities",
            errors,
            allow_empty=True,
        )
        if kind == "provider_adapter":
            provider_capabilities.update(
                capability
                for capability in capabilities
                if isinstance(capability, str) and capability.strip()
            )

    missing_component_kinds = REQUIRED_RUNTIME_COMPONENT_KINDS - component_kinds
    if missing_component_kinds:
        errors.append(
            f"{candidate_path}.components: missing required runtime component kinds "
            + ", ".join(sorted(missing_component_kinds))
        )
    provider_boundary = data.get("provider_boundary")
    required_provider_capabilities = (
        provider_boundary.get("required_capabilities", [])
        if isinstance(provider_boundary, dict)
        else []
    )
    missing_provider_capabilities = {
        capability
        for capability in required_provider_capabilities
        if isinstance(capability, str) and capability.strip()
    } - provider_capabilities
    if missing_provider_capabilities:
        errors.append(
            f"{candidate_path}.components: provider adapters omit required capabilities "
            + ", ".join(sorted(missing_provider_capabilities))
        )

    activation = require_object(value, "activation", path, errors)
    activation_path = f"{path}.activation"
    reject_unknown_keys(
        activation,
        {
            "candidate_validation",
            "attempt_id_schema",
            "expected_active_generation",
            "compare_and_swap",
            "readiness_gate",
            "readiness_timeout_seconds",
            "commit_point",
            "health_gate",
            "health_window_seconds",
            "pre_commit_failure_behavior",
            "post_commit_failure_behavior",
        },
        activation_path,
        errors,
    )
    for key in (
        "candidate_validation",
        "attempt_id_schema",
        "expected_active_generation",
        "readiness_gate",
        "commit_point",
        "health_gate",
    ):
        require_string(activation, key, activation_path, errors)
    require_positive_number(
        activation, "readiness_timeout_seconds", activation_path, errors
    )
    require_positive_number(
        activation, "health_window_seconds", activation_path, errors
    )
    if activation.get("compare_and_swap") is not True:
        errors.append(f"{activation_path}.compare_and_swap: must be true")
    pre_commit_failure = require_string(
        activation, "pre_commit_failure_behavior", activation_path, errors
    )
    if (
        pre_commit_failure
        and pre_commit_failure != "preserve_expected_active_generation"
    ):
        errors.append(
            f"{activation_path}.pre_commit_failure_behavior: "
            "must be preserve_expected_active_generation"
        )
    post_commit_failure = require_string(
        activation, "post_commit_failure_behavior", activation_path, errors
    )
    if post_commit_failure and post_commit_failure != "rollback_via_compare_and_swap":
        errors.append(
            f"{activation_path}.post_commit_failure_behavior: "
            "must be rollback_via_compare_and_swap"
        )

    run_binding = require_object(value, "run_binding", path, errors)
    run_binding_path = f"{path}.run_binding"
    reject_unknown_keys(
        run_binding,
        {
            "admission",
            "binding_policy",
            "late_result_fencing",
            "lease_release",
            "retirement",
            "migration_contract",
        },
        run_binding_path,
        errors,
    )
    for key in ("admission", "late_result_fencing", "lease_release"):
        require_string(run_binding, key, run_binding_path, errors)
    binding_policy = require_string(
        run_binding, "binding_policy", run_binding_path, errors
    )
    if binding_policy and binding_policy not in BINDING_POLICIES:
        errors.append(
            f"{run_binding_path}.binding_policy: must be pin or explicit_migrate"
        )
    retirement = require_object(run_binding, "retirement", run_binding_path, errors)
    retirement_path = f"{run_binding_path}.retirement"
    reject_unknown_keys(
        retirement,
        {
            "admission_closed_at_commit",
            "mode",
            "quiescence_condition",
            "timeout_seconds",
            "timeout_behavior",
            "cancel_acknowledgement",
            "teardown_completion",
        },
        retirement_path,
        errors,
    )
    if retirement.get("admission_closed_at_commit") is not True:
        errors.append(f"{retirement_path}.admission_closed_at_commit: must be true")
    retirement_mode = require_string(retirement, "mode", retirement_path, errors)
    if retirement_mode and retirement_mode not in RETIREMENT_MODES:
        errors.append(
            f"{retirement_path}.mode: must be drain, cancel, drain_then_cancel, or migrate"
        )
    require_string(retirement, "quiescence_condition", retirement_path, errors)
    require_positive_number(retirement, "timeout_seconds", retirement_path, errors)
    timeout_behavior = require_string(
        retirement, "timeout_behavior", retirement_path, errors
    )
    if timeout_behavior and timeout_behavior not in RETIREMENT_TIMEOUT_BEHAVIORS:
        errors.append(
            f"{retirement_path}.timeout_behavior: must be cancel_and_fence, "
            "fence_and_quarantine, or rollback_via_compare_and_swap"
        )
    require_string(retirement, "cancel_acknowledgement", retirement_path, errors)
    require_string(retirement, "teardown_completion", retirement_path, errors)
    if binding_policy == "explicit_migrate":
        require_string(run_binding, "migration_contract", run_binding_path, errors)
        if retirement_mode != "migrate":
            errors.append(
                f"{retirement_path}.mode: explicit_migrate binding requires migrate"
            )
    elif retirement_mode == "migrate":
        errors.append(
            f"{run_binding_path}.binding_policy: migrate retirement requires explicit_migrate"
        )

    isolation = require_object(value, "isolation", path, errors)
    isolation_path = f"{path}.isolation"
    reject_unknown_keys(
        isolation,
        {
            "boundary_type",
            "trust_model",
            "authority_surfaces",
            "failure_containment",
            "quarantine",
            "enforcement_evidence",
        },
        isolation_path,
        errors,
    )
    boundary_type = require_string(
        isolation, "boundary_type", isolation_path, errors
    )
    if boundary_type and boundary_type not in ISOLATION_BOUNDARY_TYPES:
        errors.append(
            f"{isolation_path}.boundary_type: must be same_process, process, vm, container, or wasm"
        )
    trust_model = require_string(isolation, "trust_model", isolation_path, errors)
    if trust_model and trust_model not in ISOLATION_TRUST_MODELS:
        errors.append(
            f"{isolation_path}.trust_model: must be reviewed_trusted or untrusted"
        )
    if trust_model == "untrusted" and boundary_type == "same_process":
        errors.append(
            f"{isolation_path}.boundary_type: untrusted modules cannot use same_process"
        )
    authority_surfaces = require_list(
        isolation, "authority_surfaces", isolation_path, errors
    )
    validate_string_list(
        authority_surfaces, f"{isolation_path}.authority_surfaces", errors
    )
    for key in ("failure_containment", "quarantine", "enforcement_evidence"):
        require_string(isolation, key, isolation_path, errors)

    rollback = require_object(value, "rollback", path, errors)
    rollback_path = f"{path}.rollback"
    reject_unknown_keys(
        rollback,
        {
            "retain_prior_generation",
            "expected_failed_generation",
            "target_generation",
            "activation_attempt_binding",
            "compare_and_swap",
            "timeout_seconds",
            "trigger",
            "receipt",
            "failed_generation_runs",
            "external_effects",
            "release_condition",
        },
        rollback_path,
        errors,
    )
    if rollback.get("retain_prior_generation") is not True:
        errors.append(f"{rollback_path}.retain_prior_generation: must be true")
    for key in (
        "expected_failed_generation",
        "target_generation",
        "activation_attempt_binding",
    ):
        require_string(rollback, key, rollback_path, errors)
    if rollback.get("compare_and_swap") is not True:
        errors.append(f"{rollback_path}.compare_and_swap: must be true")
    require_positive_number(rollback, "timeout_seconds", rollback_path, errors)
    for key in (
        "trigger",
        "receipt",
        "failed_generation_runs",
        "external_effects",
    ):
        require_string(rollback, key, rollback_path, errors)
    release_condition = require_object(
        rollback, "release_condition", rollback_path, errors
    )
    release_path = f"{rollback_path}.release_condition"
    release_keys = {
        "health_window_closed",
        "rollback_terminal",
        "leases_zero",
        "teardown_complete",
    }
    reject_unknown_keys(release_condition, release_keys, release_path, errors)
    for key in release_keys:
        if release_condition.get(key) is not True:
            errors.append(f"{release_path}.{key}: must be true")

    evidence = require_object(value, "evidence", path, errors)
    evidence_path = f"{path}.evidence"
    reject_unknown_keys(
        evidence,
        {
            "event_schema",
            "generation_binding",
            "activation_receipt",
            "rollback_receipt",
        },
        evidence_path,
        errors,
    )
    for key in (
        "event_schema",
        "generation_binding",
        "activation_receipt",
        "rollback_receipt",
    ):
        require_string(evidence, key, evidence_path, errors)

    return True


def validate_evaluation_reconfiguration_claim(
    data: dict[str, Any], errors: list[str]
) -> bool:
    if "runtime_reconfiguration" not in data:
        return False

    value = data.get("runtime_reconfiguration")
    path = "$.runtime_reconfiguration"
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return False
    reject_unknown_keys(
        value, {"claimed", "rationale", "design_ref", "result_schema"}, path, errors
    )
    claimed = value.get("claimed")
    if not isinstance(claimed, bool):
        errors.append(f"{path}.claimed: must be a boolean")
    require_string(value, "rationale", path, errors)
    if claimed is True:
        require_string(value, "design_ref", path, errors)
        result_schema = require_string(value, "result_schema", path, errors)
        if result_schema and result_schema != RUN_RESULT_RECONFIGURATION_SCHEMA:
            errors.append(
                f"{path}.result_schema: must be {RUN_RESULT_RECONFIGURATION_SCHEMA}"
            )
        return True
    if claimed is False:
        unexpected = sorted(set(value) - {"claimed", "rationale"})
        if unexpected:
            errors.append(
                f"{path}: an unclaimed evaluation cannot declare result bindings: "
                + ", ".join(unexpected)
            )
    return False


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

    validate_runtime_reconfiguration(data, errors)

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
    reconfiguration_claimed = validate_evaluation_reconfiguration_claim(data, errors)

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
    oracle_ids: set[str] = set()
    oracle_type_by_id: dict[str, str] = {}
    for index, oracle in enumerate(oracles):
        path = f"$.oracles[{index}]"
        if not isinstance(oracle, dict):
            errors.append(f"{path}: must be an object")
            continue
        oracle_id = require_string(oracle, "id", path, errors)
        if oracle_id in oracle_ids:
            errors.append(f"{path}.id: duplicate oracle {oracle_id}")
        oracle_ids.add(oracle_id)
        oracle_type = require_string(oracle, "type", path, errors)
        if oracle_type and oracle_type not in ORACLE_TYPES:
            errors.append(f"{path}.type: must be deterministic, human, or llm")
        oracle_types.add(oracle_type)
        if oracle_id and oracle_id not in oracle_type_by_id:
            oracle_type_by_id[oracle_id] = oracle_type
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
    injection_classes_by_id: dict[str, set[str]] = {}
    declared_injection_ids: set[str] = set()
    for index, injection in enumerate(injections):
        path = f"$.fault_injection[{index}]"
        if not isinstance(injection, dict):
            errors.append(f"{path}: must be an object")
            continue
        injection_id = require_string(injection, "id", path, errors)
        if injection_id in declared_injection_ids:
            errors.append(f"{path}.id: duplicate fault injection {injection_id}")
        declared_injection_ids.add(injection_id)
        require_string(injection, "target", path, errors)
        require_string(injection, "method", path, errors)
        classes: list[Any] = []
        if "classes" in injection:
            classes = require_list(injection, "classes", path, errors)
            validate_string_list(classes, f"{path}.classes", errors)
        if injection_id and injection_id not in injection_classes_by_id:
            injection_classes_by_id[injection_id] = {
                value for value in classes if isinstance(value, str)
            }

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
    scenario_classes_by_id: dict[str, set[str]] = {}
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
        if scenario_id and scenario_id not in scenario_classes_by_id:
            scenario_classes_by_id[scenario_id] = class_set
        reconfiguration_classes = class_set & RECONFIGURATION_SCENARIO_CLASSES
        if reconfiguration_claimed and reconfiguration_classes:
            fault_injection_ids = require_list(
                scenario, "fault_injection_ids", path, errors
            )
            validate_string_list(
                fault_injection_ids, f"{path}.fault_injection_ids", errors
            )
            scenario_oracle_ids = require_list(scenario, "oracle_ids", path, errors)
            validate_string_list(
                scenario_oracle_ids, f"{path}.oracle_ids", errors
            )
            linked_injection_ids = {
                value for value in fault_injection_ids if isinstance(value, str)
            }
            unknown_injection_ids = linked_injection_ids - declared_injection_ids
            if unknown_injection_ids:
                errors.append(
                    f"{path}.fault_injection_ids: unknown fault injections "
                    + ", ".join(sorted(unknown_injection_ids))
                )
            linked_classes: set[str] = set()
            for injection_id in linked_injection_ids:
                linked_classes.update(injection_classes_by_id.get(injection_id, set()))
            missing_injected_classes = reconfiguration_classes - linked_classes
            if missing_injected_classes:
                errors.append(
                    f"{path}.fault_injection_ids: linked injections do not exercise "
                    + ", ".join(sorted(missing_injected_classes))
                )
            linked_oracle_ids = {
                value for value in scenario_oracle_ids if isinstance(value, str)
            }
            unknown_oracle_ids = linked_oracle_ids - oracle_ids
            if unknown_oracle_ids:
                errors.append(
                    f"{path}.oracle_ids: unknown oracles "
                    + ", ".join(sorted(unknown_oracle_ids))
                )
            linked_oracle_types = {
                oracle_type_by_id.get(oracle_id, "")
                for oracle_id in linked_oracle_ids
            }
            if not ({"deterministic", "human"} & linked_oracle_types):
                errors.append(
                    f"{path}.oracle_ids: a runtime-reconfiguration scenario "
                    "requires a linked deterministic or human oracle"
                )
    scheduled_scenario_classes: set[str] = set()
    for scenario_id in scenario_ids:
        if isinstance(scenario_id, str):
            scheduled_scenario_classes.update(
                scenario_classes_by_id.get(scenario_id, set())
            )
    missing_required = REQUIRED_SCENARIO_CLASSES - scheduled_scenario_classes
    if missing_required:
        errors.append(
            "$.task_suite.scenario_ids: scheduled scenarios missing required classes "
            + ", ".join(sorted(missing_required))
        )
    missing_recommended = RECOMMENDED_SCENARIO_CLASSES - scheduled_scenario_classes
    if missing_recommended:
        warnings.append(
            "$.task_suite.scenario_ids: scheduled scenarios do not cover recommended classes: "
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
    if reconfiguration_claimed:
        missing_reconfiguration = (
            RECONFIGURATION_SCENARIO_CLASSES - scheduled_scenario_classes
        )
        if missing_reconfiguration:
            errors.append(
                "$.task_suite.scenario_ids: runtime reconfiguration claim missing required classes "
                + ", ".join(sorted(missing_reconfiguration))
            )

    gates = require_list(data, "release_gates", "$", errors)
    zero_blocking_gates: set[str] = set()
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
        threshold = gate.get("threshold")
        if isinstance(threshold, bool):
            if operator and operator != "==":
                errors.append(f"{path}.threshold: boolean thresholds require ==")
        elif not is_number(threshold):
            errors.append(f"{path}.threshold: must be a finite number or boolean")
        if operator == "zero" and (
            isinstance(threshold, bool) or not is_number(threshold) or threshold != 0
        ):
            errors.append(f"{path}.threshold: zero operator requires numeric 0")
        if not isinstance(gate.get("blocking"), bool):
            errors.append(f"{path}.blocking: must be a boolean")
        if (
            gate_metric in RECONFIGURATION_ZERO_METRICS
            and gate.get("blocking") is True
            and operator in {"zero", "=="}
            and not isinstance(threshold, bool)
            and threshold == 0
        ):
            zero_blocking_gates.add(gate_metric)

    if reconfiguration_claimed:
        missing_metrics = RECONFIGURATION_ZERO_METRICS - metric_names
        if missing_metrics:
            errors.append(
                "$.metrics: runtime reconfiguration claim missing zero-tolerance metrics "
                + ", ".join(sorted(missing_metrics))
            )
        missing_zero_gates = RECONFIGURATION_ZERO_METRICS - zero_blocking_gates
        if missing_zero_gates:
            errors.append(
                "$.release_gates: runtime reconfiguration metrics need blocking zero gates "
                + ", ".join(sorted(missing_zero_gates))
            )

    provenance = require_list(data, "provenance", "$", errors)
    validate_string_list(provenance, "$.provenance", errors)


def validate_run_result(
    data: dict[str, Any], errors: list[str], warnings: list[str], *, require_generation: bool
) -> None:
    require_string(data, "run_id", "$", errors)
    require_string(data, "scenario_id", "$", errors)
    validate_system_tuple(data, "$", errors)

    if not require_generation and "runtime_generation" not in data:
        generation = None
    else:
        generation = require_object(data, "runtime_generation", "$", errors)
    if generation is not None:
        validate_run_result_generation(generation, errors)
    validate_run_result_body(data, errors, warnings)


def validate_run_result_generation(
    generation: dict[str, Any], errors: list[str]
) -> None:
    generation_path = "$.runtime_generation"
    reject_unknown_keys(
        generation,
        {
            "design_ref",
            "evaluation_plan_ref",
            "binding_policy",
            "admitted_generation_id",
            "terminal_generation_id",
            "activation_attempt_id",
            "activation_receipt_ref",
            "trace_generation_binding_ref",
            "effect_generation_binding_ref",
            "migration_receipt_ref",
        },
        generation_path,
        errors,
    )
    for key in (
        "design_ref",
        "evaluation_plan_ref",
        "admitted_generation_id",
        "terminal_generation_id",
        "activation_attempt_id",
        "activation_receipt_ref",
        "trace_generation_binding_ref",
        "effect_generation_binding_ref",
    ):
        require_string(generation, key, generation_path, errors)
    binding_policy = require_string(
        generation, "binding_policy", generation_path, errors
    )
    if binding_policy and binding_policy not in BINDING_POLICIES:
        errors.append(
            f"{generation_path}.binding_policy: must be pin or explicit_migrate"
        )
    admitted_generation_id = generation.get("admitted_generation_id")
    terminal_generation_id = generation.get("terminal_generation_id")
    if binding_policy == "pin":
        if admitted_generation_id != terminal_generation_id:
            errors.append(
                f"{generation_path}.terminal_generation_id: pin binding requires "
                "the admitted and terminal generation IDs to match"
            )
        if "migration_receipt_ref" in generation:
            errors.append(
                f"{generation_path}.migration_receipt_ref: pin binding cannot claim migration"
            )
    elif binding_policy == "explicit_migrate":
        if admitted_generation_id == terminal_generation_id:
            errors.append(
                f"{generation_path}.terminal_generation_id: explicit_migrate requires "
                "a distinct terminal generation ID"
            )
        require_string(generation, "migration_receipt_ref", generation_path, errors)


def validate_run_result_body(
    data: dict[str, Any], errors: list[str], warnings: list[str]
) -> None:
    del warnings
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
        validate_run_result(data, errors, warnings, require_generation=False)
    elif schema == RUN_RESULT_RECONFIGURATION_SCHEMA:
        validate_run_result(data, errors, warnings, require_generation=True)
    else:
        errors.append(
            "$.schema: must be one of "
            + ", ".join(
                (
                    DESIGN_SCHEMA,
                    EVALUATION_SCHEMA,
                    RUN_RESULT_SCHEMA,
                    RUN_RESULT_RECONFIGURATION_SCHEMA,
                )
            )
        )
    return errors, warnings


def load_artifact(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_nonstandard_json_constant,
        )
    except OSError as exc:
        return None, f"$: cannot read artifact: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"$: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
    except ValueError as exc:
        return None, f"$: invalid JSON: {exc}"
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
