#!/usr/bin/env python3
"""Validate provider-neutral capability artifact evaluation plans and receipts."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


SCHEMA = "capability.evaluation.v1"
RESULT_SCHEMA = "capability.evaluation.validation.v1"
STATUSES = {"planned", "complete", "blocked"}
ARTIFACT_KINDS = {"skill", "plugin", "agent-guidance", "trigger-metadata", "mixed"}
BASELINE_TYPES = {"no-artifact", "artifact"}
DIMENSIONS = {"trigger", "task-outcome", "constraints", "subjective", "overhead"}
PERSISTENCE_FACETS = {
    "presentation_brevity",
    "state_exactness",
    "atom_recall_by_category",
    "source_references",
    "successful_output_recovery",
    "failed_output_recovery",
    "repeated_work",
    "false_certainty",
    "authority",
    "complete_pipeline_cost",
}
NONCRITICAL_PERSISTENCE_FACETS = {
    "presentation_brevity",
    "complete_pipeline_cost",
}
CASE_CATEGORIES = {"foundational", "representative", "paraphrase", "edge", "anti-trigger"}
ASSERTION_TYPES = {"deterministic", "human", "model-judge"}
REVIEW_METHODS = {"none", "blind-human", "calibrated-model-judge", "hybrid"}
OUTCOMES = {"win", "loss", "tie", "inconclusive"}
VERDICTS = {"planned", "adopt", "revise", "reject", "inconclusive"}
NETWORK_POLICIES = {"disabled", "allowlisted", "enabled"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_METRIC_NUMBER = 10**18

TOP_LEVEL_KEYS = {
    "schema",
    "status",
    "target",
    "scope",
    "environment",
    "cases",
    "adoption_rule",
    "subjective_review",
    "results",
    "summary",
    "verdict",
    "rationale",
    "limitations",
    "rollback",
}


TEMPLATE: dict[str, Any] = {
    "schema": SCHEMA,
    "status": "planned",
    "target": {
        "kind": "skill",
        "name": "example-capability",
        "candidate": {
            "identity": "example-capability@candidate",
            "sha256": "a" * 64,
        },
        "baseline": {
            "type": "no-artifact",
            "identity": "none",
            "sha256": None,
        },
    },
    "scope": {
        "claim": "The candidate improves the declared task outcome without increasing false activation.",
        "dimensions": ["trigger", "task-outcome"],
        "artifact_behavior_only": True,
        "harness_reliability": "not-evaluated",
        "runtime_failures": "quarantine",
        "persistence_coverage": {
            "applicable": False,
        },
    },
    "environment": {
        "runner": "host-selected-runner",
        "runner_version": "record-before-run",
        "model": "host-selected-model",
        "model_version": "record-before-run",
        "configuration_sha256": "b" * 64,
        "fixture_sha256": "c" * 64,
        "tools_sha256": "d" * 64,
        "permissions_sha256": "e" * 64,
        "network_policy": "disabled",
        "timeout_seconds": 300,
        "isolation": "clean disposable workspace per arm",
        "parity_proved": False,
        "parity_evidence": [],
    },
    "cases": [
        {
            "id": "representative-1",
            "category": "representative",
            "critical": True,
            "prompt_sha256": "f" * 64,
            "repetitions": 3,
            "assertions": [
                {
                    "id": "required-output",
                    "type": "deterministic",
                    "criterion": "The output satisfies the declared artifact contract.",
                }
            ],
        }
    ],
    "adoption_rule": {
        "critical_cases_must_pass": True,
        "max_regressions": 0,
        "minimum_candidate_wins": 1,
    },
    "subjective_review": {
        "method": "none",
        "rubric_sha256": None,
        "reviewer_identity": "",
    },
    "results": [],
    "summary": {
        "case_count": 0,
        "candidate_wins": 0,
        "candidate_losses": 0,
        "ties": 0,
        "inconclusive": 0,
        "critical_regressions": 0,
        "quarantined_trials": 0,
    },
    "verdict": "planned",
    "rationale": "Evaluation cases and thresholds are frozen before execution.",
    "limitations": ["No behavioral runs have been executed."],
    "rollback": "Keep the immutable baseline available until an adoption decision is accepted.",
}


class StrictJsonError(ValueError):
    """Raised when JSON violates strict parsing requirements."""


def _reject_constant(value: str) -> None:
    raise StrictJsonError(f"non_finite_number:{value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate_key:{key}")
        result[key] = value
    return result


def load_strict_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, StrictJsonError) as exc:
        raise StrictJsonError(f"invalid_json:{path}:{exc}") from exc
    if not isinstance(data, dict):
        raise StrictJsonError("ledger_must_be_object")
    return data


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return isinstance(value, float) and math.isfinite(value)


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_list(value: Any, *, non_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (not non_empty or bool(value))
        and all(non_empty_string(item) for item in value)
    )


def check_keys(
    errors: list[str],
    value: Any,
    label: str,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{label}_must_be_object")
        return None
    allowed = required | (optional or set())
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - allowed)
    if missing:
        errors.append(f"{label}_missing_fields:{','.join(missing)}")
    if unknown:
        errors.append(f"{label}_unknown_fields:{','.join(unknown)}")
    return value


def check_sha(errors: list[str], value: Any, label: str) -> None:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        errors.append(f"{label}_must_be_lowercase_sha256")


def check_string(errors: list[str], value: Any, label: str) -> None:
    if not non_empty_string(value):
        errors.append(f"{label}_must_be_non_empty_string")


def check_non_negative_int(errors: list[str], value: Any, label: str) -> None:
    if not is_int(value) or value < 0:
        errors.append(f"{label}_must_be_non_negative_integer")


def validate_identity(
    errors: list[str], value: Any, label: str, *, allow_null_hash: bool = False
) -> dict[str, Any] | None:
    item = check_keys(errors, value, label, {"identity", "sha256"})
    if item is None:
        return None
    check_string(errors, item.get("identity"), f"{label}_identity")
    digest = item.get("sha256")
    if allow_null_hash and digest is None:
        return item
    check_sha(errors, digest, f"{label}_sha256")
    return item


def validate_target(errors: list[str], value: Any) -> None:
    target = check_keys(
        errors, value, "target", {"kind", "name", "candidate", "baseline"}
    )
    if target is None:
        return
    if target.get("kind") not in ARTIFACT_KINDS:
        errors.append("target_kind_invalid")
    check_string(errors, target.get("name"), "target_name")
    candidate = validate_identity(errors, target.get("candidate"), "candidate")
    baseline = check_keys(
        errors, target.get("baseline"), "baseline", {"type", "identity", "sha256"}
    )
    if baseline is None:
        return
    baseline_type = baseline.get("type")
    if baseline_type not in BASELINE_TYPES:
        errors.append("baseline_type_invalid")
    check_string(errors, baseline.get("identity"), "baseline_identity")
    if baseline_type == "no-artifact":
        if baseline.get("sha256") is not None:
            errors.append("no_artifact_baseline_sha256_must_be_null")
    elif baseline_type == "artifact":
        check_sha(errors, baseline.get("sha256"), "baseline_sha256")
        candidate_sha = candidate.get("sha256") if candidate else None
        baseline_sha = baseline.get("sha256")
        if (
            isinstance(candidate_sha, str)
            and SHA256_RE.fullmatch(candidate_sha)
            and isinstance(baseline_sha, str)
            and SHA256_RE.fullmatch(baseline_sha)
            and candidate_sha == baseline_sha
        ):
            errors.append("candidate_and_artifact_baseline_sha256_must_differ")


def validate_scope(
    errors: list[str], value: Any
) -> tuple[set[str], dict[str, Any] | None]:
    scope = check_keys(
        errors,
        value,
        "scope",
        {
            "claim",
            "dimensions",
            "artifact_behavior_only",
            "harness_reliability",
            "runtime_failures",
        },
        {"persistence_coverage"},
    )
    if scope is None:
        return set(), None
    check_string(errors, scope.get("claim"), "scope_claim")
    dimensions = scope.get("dimensions")
    dimension_set: set[str] = set()
    if not isinstance(dimensions, list) or not dimensions:
        errors.append("scope_dimensions_must_be_non_empty_array")
    else:
        for item in dimensions:
            if not isinstance(item, str) or item not in DIMENSIONS:
                errors.append(f"scope_dimension_invalid:{item}")
            else:
                if item in dimension_set:
                    errors.append(f"scope_dimension_duplicate:{item}")
                dimension_set.add(item)
    if scope.get("artifact_behavior_only") is not True:
        errors.append("scope_artifact_behavior_only_must_be_true")
    if scope.get("harness_reliability") != "not-evaluated":
        errors.append("scope_harness_reliability_must_be_not_evaluated")
    if scope.get("runtime_failures") != "quarantine":
        errors.append("scope_runtime_failures_must_be_quarantine")
    coverage = scope.get("persistence_coverage")
    if coverage is not None and not isinstance(coverage, dict):
        errors.append("scope_persistence_coverage_must_be_object")
        coverage = None
    return dimension_set, coverage


def validate_environment(errors: list[str], value: Any, status: Any) -> None:
    required = {
        "runner",
        "runner_version",
        "model",
        "model_version",
        "configuration_sha256",
        "fixture_sha256",
        "tools_sha256",
        "permissions_sha256",
        "network_policy",
        "timeout_seconds",
        "isolation",
        "parity_proved",
        "parity_evidence",
    }
    env = check_keys(errors, value, "environment", required)
    if env is None:
        return
    for field in ("runner", "runner_version", "model", "model_version", "isolation"):
        check_string(errors, env.get(field), f"environment_{field}")
    for field in (
        "configuration_sha256",
        "fixture_sha256",
        "tools_sha256",
        "permissions_sha256",
    ):
        check_sha(errors, env.get(field), f"environment_{field}")
    if env.get("network_policy") not in NETWORK_POLICIES:
        errors.append("environment_network_policy_invalid")
    timeout = env.get("timeout_seconds")
    if not is_int(timeout) or timeout <= 0:
        errors.append("environment_timeout_seconds_must_be_positive_integer")
    if not isinstance(env.get("parity_proved"), bool):
        errors.append("environment_parity_proved_must_be_boolean")
    if not string_list(env.get("parity_evidence")):
        errors.append("environment_parity_evidence_must_be_string_array")
    if status == "complete":
        if env.get("parity_proved") is not True:
            errors.append("complete_requires_proved_environment_parity")
        if not string_list(env.get("parity_evidence"), non_empty=True):
            errors.append("complete_requires_parity_evidence")


def validate_cases(errors: list[str], value: Any) -> tuple[dict[str, dict[str, Any]], set[str]]:
    cases_by_id: dict[str, dict[str, Any]] = {}
    assertion_types: set[str] = set()
    if not isinstance(value, list) or not value:
        errors.append("cases_must_be_non_empty_array")
        return cases_by_id, assertion_types
    for index, raw in enumerate(value):
        label = f"case_{index}"
        case = check_keys(
            errors,
            raw,
            label,
            {"id", "category", "critical", "prompt_sha256", "repetitions", "assertions"},
        )
        if case is None:
            continue
        case_id = case.get("id")
        check_string(errors, case_id, f"{label}_id")
        if isinstance(case_id, str):
            if case_id in cases_by_id:
                errors.append(f"case_id_duplicate:{case_id}")
            else:
                cases_by_id[case_id] = case
        if case.get("category") not in CASE_CATEGORIES:
            errors.append(f"{label}_category_invalid")
        if not isinstance(case.get("critical"), bool):
            errors.append(f"{label}_critical_must_be_boolean")
        check_sha(errors, case.get("prompt_sha256"), f"{label}_prompt_sha256")
        repetitions = case.get("repetitions")
        if not is_int(repetitions) or repetitions <= 0:
            errors.append(f"{label}_repetitions_must_be_positive_integer")
        assertions = case.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            errors.append(f"{label}_assertions_must_be_non_empty_array")
            continue
        seen_assertions: set[str] = set()
        for assertion_index, raw_assertion in enumerate(assertions):
            assertion_label = f"{label}_assertion_{assertion_index}"
            assertion = check_keys(
                errors,
                raw_assertion,
                assertion_label,
                {"id", "type", "criterion"},
            )
            if assertion is None:
                continue
            assertion_id = assertion.get("id")
            check_string(errors, assertion_id, f"{assertion_label}_id")
            if isinstance(assertion_id, str):
                if assertion_id in seen_assertions:
                    errors.append(f"{label}_assertion_id_duplicate:{assertion_id}")
                seen_assertions.add(assertion_id)
            assertion_type = assertion.get("type")
            if assertion_type not in ASSERTION_TYPES:
                errors.append(f"{assertion_label}_type_invalid")
            else:
                assertion_types.add(assertion_type)
            check_string(errors, assertion.get("criterion"), f"{assertion_label}_criterion")
    return cases_by_id, assertion_types


def resolve_assertion_ref(
    errors: list[str],
    value: Any,
    label: str,
    cases_by_id: dict[str, dict[str, Any]],
    *,
    require_critical: bool,
) -> tuple[str, str] | None:
    reference = check_keys(errors, value, label, {"case_id", "assertion_id"})
    if reference is None:
        return None
    case_id = reference.get("case_id")
    assertion_id = reference.get("assertion_id")
    check_string(errors, case_id, f"{label}_case_id")
    check_string(errors, assertion_id, f"{label}_assertion_id")
    if not isinstance(case_id, str) or not isinstance(assertion_id, str):
        return None
    case = cases_by_id.get(case_id)
    if case is None:
        errors.append(f"{label}_case_not_declared:{case_id}")
        return None
    assertion = next(
        (
            item
            for item in case.get("assertions", [])
            if isinstance(item, dict) and item.get("id") == assertion_id
        ),
        None,
    )
    if assertion is None:
        errors.append(f"{label}_assertion_not_declared:{case_id}:{assertion_id}")
        return None
    if assertion.get("type") != "deterministic":
        errors.append(f"{label}_assertion_must_be_deterministic")
    if require_critical and case.get("critical") is not True:
        errors.append(f"{label}_case_must_be_critical")
    return case_id, assertion_id


def validate_persistence_coverage(
    errors: list[str],
    value: dict[str, Any] | None,
    dimensions: set[str],
    cases_by_id: dict[str, dict[str, Any]],
) -> None:
    if value is None:
        return
    coverage = check_keys(
        errors,
        value,
        "persistence_coverage",
        {"applicable"},
        {"trajectories", "facet_assertions"},
    )
    if coverage is None:
        return
    applicable = coverage.get("applicable")
    if not isinstance(applicable, bool):
        errors.append("persistence_coverage_applicable_must_be_boolean")
        return
    if not applicable:
        if set(coverage) != {"applicable"}:
            errors.append("inapplicable_persistence_coverage_must_not_declare_details")
        return

    required_dimensions = {"task-outcome", "constraints", "overhead"}
    for missing in sorted(required_dimensions - dimensions):
        errors.append(f"persistence_coverage_requires_dimension:{missing}")

    trajectories = coverage.get("trajectories")
    if not isinstance(trajectories, list) or not trajectories:
        errors.append("persistence_coverage_trajectories_must_be_non_empty_array")
    else:
        seen_trajectory_ids: set[str] = set()
        for index, raw_trajectory in enumerate(trajectories):
            label = f"persistence_trajectory_{index}"
            trajectory = check_keys(
                errors,
                raw_trajectory,
                label,
                {"id", "full_history_control", "dependent_boundaries"},
            )
            if trajectory is None:
                continue
            trajectory_id = trajectory.get("id")
            check_string(errors, trajectory_id, f"{label}_id")
            if isinstance(trajectory_id, str):
                if trajectory_id in seen_trajectory_ids:
                    errors.append(f"persistence_trajectory_id_duplicate:{trajectory_id}")
                seen_trajectory_ids.add(trajectory_id)
            referenced: set[tuple[str, str]] = set()
            full_history = resolve_assertion_ref(
                errors,
                trajectory.get("full_history_control"),
                f"{label}_full_history_control",
                cases_by_id,
                require_critical=True,
            )
            if full_history is not None:
                referenced.add(full_history)
            boundaries = trajectory.get("dependent_boundaries")
            if not isinstance(boundaries, list) or len(boundaries) < 2:
                errors.append(f"{label}_requires_at_least_two_dependent_boundaries")
                continue
            for boundary_index, raw_boundary in enumerate(boundaries):
                boundary = resolve_assertion_ref(
                    errors,
                    raw_boundary,
                    f"{label}_dependent_boundary_{boundary_index}",
                    cases_by_id,
                    require_critical=True,
                )
                if boundary is not None:
                    if boundary in referenced:
                        errors.append(f"{label}_assertion_ref_duplicate:{boundary[0]}:{boundary[1]}")
                    referenced.add(boundary)

    facet_assertions = coverage.get("facet_assertions")
    if not isinstance(facet_assertions, list) or not facet_assertions:
        errors.append("persistence_coverage_facets_must_be_non_empty_array")
        return
    seen_facets: set[str] = set()
    seen_facet_refs: set[tuple[str, str]] = set()
    for index, raw_facet in enumerate(facet_assertions):
        label = f"persistence_facet_{index}"
        facet = check_keys(
            errors,
            raw_facet,
            label,
            {"facet", "case_id", "assertion_id"},
        )
        if facet is None:
            continue
        facet_name = facet.get("facet")
        if facet_name not in PERSISTENCE_FACETS:
            errors.append(f"{label}_invalid:{facet_name}")
            continue
        if facet_name in seen_facets:
            errors.append(f"persistence_facet_duplicate:{facet_name}")
        seen_facets.add(facet_name)
        reference = resolve_assertion_ref(
            errors,
            {
                "case_id": facet.get("case_id"),
                "assertion_id": facet.get("assertion_id"),
            },
            label,
            cases_by_id,
            require_critical=facet_name not in NONCRITICAL_PERSISTENCE_FACETS,
        )
        if reference is not None:
            if reference in seen_facet_refs:
                errors.append(
                    f"persistence_facets_must_use_separate_assertions:{reference[0]}:{reference[1]}"
                )
            seen_facet_refs.add(reference)
    for missing in sorted(PERSISTENCE_FACETS - seen_facets):
        errors.append(f"persistence_facet_missing:{missing}")


def validate_adoption_rule(errors: list[str], value: Any) -> dict[str, Any] | None:
    rule = check_keys(
        errors,
        value,
        "adoption_rule",
        {"critical_cases_must_pass", "max_regressions", "minimum_candidate_wins"},
    )
    if rule is None:
        return None
    if rule.get("critical_cases_must_pass") is not True:
        errors.append("adoption_rule_critical_cases_must_pass_must_be_true")
    check_non_negative_int(errors, rule.get("max_regressions"), "adoption_rule_max_regressions")
    minimum_wins = rule.get("minimum_candidate_wins")
    if not is_int(minimum_wins) or minimum_wins <= 0:
        errors.append("adoption_rule_minimum_candidate_wins_must_be_positive_integer")
    return rule


def validate_subjective_review(
    errors: list[str], value: Any, assertion_types: set[str]
) -> None:
    review = check_keys(
        errors,
        value,
        "subjective_review",
        {"method", "rubric_sha256", "reviewer_identity"},
    )
    if review is None:
        return
    method = review.get("method")
    if method not in REVIEW_METHODS:
        errors.append("subjective_review_method_invalid")
        return
    subjective_types = assertion_types & {"human", "model-judge"}
    if subjective_types and method == "none":
        errors.append("subjective_assertions_require_review_method")
    if "human" in subjective_types and method not in {"blind-human", "hybrid"}:
        errors.append("human_assertions_require_blind_human_or_hybrid_review")
    if "model-judge" in subjective_types and method not in {
        "calibrated-model-judge",
        "hybrid",
    }:
        errors.append("model_judge_assertions_require_calibrated_judge_or_hybrid_review")
    if method == "none":
        if review.get("rubric_sha256") is not None:
            errors.append("no_subjective_review_rubric_sha256_must_be_null")
        if review.get("reviewer_identity") not in {"", None}:
            errors.append("no_subjective_review_identity_must_be_empty")
    else:
        check_sha(errors, review.get("rubric_sha256"), "subjective_review_rubric_sha256")
        check_string(errors, review.get("reviewer_identity"), "subjective_review_reviewer_identity")


def validate_metrics(errors: list[str], value: Any, label: str) -> bool:
    metrics = check_keys(
        errors,
        value,
        label,
        set(),
        {"input_tokens", "output_tokens", "duration_ms", "cost_usd"},
    )
    if metrics is None:
        return False
    if not metrics:
        errors.append(f"{label}_must_not_be_empty")
        return False
    any_observed = False
    for field in ("input_tokens", "output_tokens", "duration_ms"):
        if field not in metrics or metrics[field] is None:
            continue
        any_observed = True
        check_non_negative_int(errors, metrics[field], f"{label}_{field}")
    if "cost_usd" in metrics and metrics["cost_usd"] is not None:
        any_observed = True
        if not is_number(metrics["cost_usd"]) or metrics["cost_usd"] < 0:
            errors.append(f"{label}_cost_usd_must_be_non_negative_finite_number")
        elif metrics["cost_usd"] > MAX_METRIC_NUMBER:
            errors.append(f"{label}_cost_usd_exceeds_supported_magnitude")
    if not any_observed:
        errors.append(f"{label}_requires_observed_value")
    return any_observed


def validate_arm(
    errors: list[str],
    value: Any,
    label: str,
    repetitions: Any,
    require_metrics: bool,
) -> dict[str, int] | None:
    arm = check_keys(
        errors,
        value,
        label,
        {"attempted", "passed", "failed", "quarantined", "evidence"},
        {"metrics"},
    )
    if arm is None:
        return None
    for field in ("attempted", "passed", "failed", "quarantined"):
        check_non_negative_int(errors, arm.get(field), f"{label}_{field}")
    attempted = arm.get("attempted")
    passed = arm.get("passed")
    failed = arm.get("failed")
    quarantined = arm.get("quarantined")
    if all(is_int(item) and item >= 0 for item in (attempted, passed, failed, quarantined)):
        if passed + failed + quarantined != attempted:
            errors.append(f"{label}_counts_do_not_sum_to_attempted")
        if is_int(repetitions) and attempted != repetitions:
            errors.append(f"{label}_attempted_must_equal_declared_repetitions")
    if not string_list(arm.get("evidence"), non_empty=True):
        errors.append(f"{label}_evidence_must_be_non_empty_string_array")
    if require_metrics:
        if "metrics" not in arm:
            errors.append(f"{label}_metrics_required_for_overhead_dimension")
        else:
            validate_metrics(errors, arm.get("metrics"), f"{label}_metrics")
    elif "metrics" in arm:
        validate_metrics(errors, arm.get("metrics"), f"{label}_metrics")
    if all(is_int(item) and item >= 0 for item in (attempted, passed, failed, quarantined)):
        return {
            "attempted": attempted,
            "passed": passed,
            "failed": failed,
            "quarantined": quarantined,
        }
    return None


def validate_results(
    errors: list[str],
    value: Any,
    cases_by_id: dict[str, dict[str, Any]],
    dimensions: set[str],
    status: Any,
) -> dict[str, int]:
    derived = {
        "case_count": 0,
        "candidate_wins": 0,
        "candidate_losses": 0,
        "ties": 0,
        "inconclusive": 0,
        "critical_regressions": 0,
        "quarantined_trials": 0,
    }
    if not isinstance(value, list):
        errors.append("results_must_be_array")
        return derived
    if status in {"planned", "blocked"}:
        if value:
            errors.append(f"{status}_results_must_be_empty")
        return derived
    seen: set[str] = set()
    require_metrics = "overhead" in dimensions
    for index, raw in enumerate(value):
        label = f"result_{index}"
        result = check_keys(
            errors,
            raw,
            label,
            {"case_id", "baseline", "candidate", "outcome", "decision_basis"},
        )
        if result is None:
            continue
        case_id = result.get("case_id")
        check_string(errors, case_id, f"{label}_case_id")
        if isinstance(case_id, str):
            if case_id in seen:
                errors.append(f"result_case_id_duplicate:{case_id}")
            seen.add(case_id)
        case = cases_by_id.get(case_id) if isinstance(case_id, str) else None
        if case is None:
            errors.append(f"result_case_id_not_declared:{case_id}")
            repetitions = None
        else:
            repetitions = case.get("repetitions")
        baseline_counts = validate_arm(
            errors, result.get("baseline"), f"{label}_baseline", repetitions, require_metrics
        )
        candidate_counts = validate_arm(
            errors, result.get("candidate"), f"{label}_candidate", repetitions, require_metrics
        )
        expected_outcome: str | None = None
        if baseline_counts and candidate_counts:
            derived["quarantined_trials"] += (
                baseline_counts["quarantined"] + candidate_counts["quarantined"]
            )
            if baseline_counts["quarantined"] or candidate_counts["quarantined"]:
                expected_outcome = "inconclusive"
            elif candidate_counts["passed"] > baseline_counts["passed"]:
                expected_outcome = "win"
            elif candidate_counts["passed"] < baseline_counts["passed"]:
                expected_outcome = "loss"
            else:
                expected_outcome = "tie"
            if (
                case
                and case.get("critical") is True
                and candidate_counts["failed"] > 0
            ):
                derived["critical_regressions"] += 1

        declared_outcome = result.get("outcome")
        if declared_outcome not in OUTCOMES:
            errors.append(f"{label}_outcome_invalid")
        elif expected_outcome is not None and declared_outcome != expected_outcome:
            errors.append(f"{label}_outcome_must_equal_{expected_outcome}")

        outcome = expected_outcome or (
            declared_outcome if declared_outcome in OUTCOMES else None
        )
        if outcome is not None:
            derived["case_count"] += 1
            key = {
                "win": "candidate_wins",
                "loss": "candidate_losses",
                "tie": "ties",
                "inconclusive": "inconclusive",
            }[outcome]
            derived[key] += 1
        check_string(errors, result.get("decision_basis"), f"{label}_decision_basis")
    declared_ids = set(cases_by_id)
    if seen != declared_ids:
        missing = sorted(declared_ids - seen)
        extra = sorted(seen - declared_ids)
        if missing:
            errors.append(f"complete_results_missing_cases:{','.join(missing)}")
        if extra:
            errors.append(f"complete_results_extra_cases:{','.join(extra)}")
    return derived


def validate_summary(errors: list[str], value: Any, derived: dict[str, int]) -> None:
    summary = check_keys(errors, value, "summary", set(derived))
    if summary is None:
        return
    for field, expected in derived.items():
        actual = summary.get(field)
        check_non_negative_int(errors, actual, f"summary_{field}")
        if is_int(actual) and actual != expected:
            errors.append(f"summary_{field}_must_equal_{expected}")


def validate_verdict(
    errors: list[str],
    status: Any,
    verdict: Any,
    derived: dict[str, int],
    rule: dict[str, Any] | None,
) -> None:
    if verdict not in VERDICTS:
        errors.append("verdict_invalid")
        return
    if status == "planned" and verdict != "planned":
        errors.append("planned_status_requires_planned_verdict")
    if status == "blocked" and verdict != "inconclusive":
        errors.append("blocked_status_requires_inconclusive_verdict")
    if status == "complete" and verdict == "planned":
        errors.append("complete_status_cannot_have_planned_verdict")
    if verdict != "adopt":
        return
    if status != "complete":
        errors.append("adopt_verdict_requires_complete_status")
    if derived["critical_regressions"]:
        errors.append("adopt_verdict_forbidden_with_critical_regressions")
    if derived["inconclusive"]:
        errors.append("adopt_verdict_forbidden_with_inconclusive_cases")
    if derived["quarantined_trials"]:
        errors.append("adopt_verdict_forbidden_with_quarantined_trials")
    if derived["candidate_wins"] <= 0:
        errors.append("adopt_verdict_requires_candidate_win")
    if rule:
        max_regressions = rule.get("max_regressions")
        minimum_wins = rule.get("minimum_candidate_wins")
        if is_int(max_regressions) and derived["candidate_losses"] > max_regressions:
            errors.append("adopt_verdict_exceeds_max_regressions")
        if is_int(minimum_wins) and derived["candidate_wins"] < minimum_wins:
            errors.append("adopt_verdict_below_minimum_candidate_wins")


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = sorted(TOP_LEVEL_KEYS - set(data))
    unknown = sorted(set(data) - TOP_LEVEL_KEYS)
    if missing:
        errors.append(f"top_level_missing_fields:{','.join(missing)}")
    if unknown:
        errors.append(f"top_level_unknown_fields:{','.join(unknown)}")
    if data.get("schema") != SCHEMA:
        errors.append(f"schema_must_be_{SCHEMA}")
    status = data.get("status")
    if status not in STATUSES:
        errors.append("status_invalid")
    validate_target(errors, data.get("target"))
    dimensions, persistence_coverage = validate_scope(errors, data.get("scope"))
    validate_environment(errors, data.get("environment"), status)
    cases_by_id, assertion_types = validate_cases(errors, data.get("cases"))
    validate_persistence_coverage(
        errors,
        persistence_coverage,
        dimensions,
        cases_by_id,
    )
    rule = validate_adoption_rule(errors, data.get("adoption_rule"))
    validate_subjective_review(errors, data.get("subjective_review"), assertion_types)
    derived = validate_results(
        errors, data.get("results"), cases_by_id, dimensions, status
    )
    validate_summary(errors, data.get("summary"), derived)
    validate_verdict(errors, status, data.get("verdict"), derived, rule)
    check_string(errors, data.get("rationale"), "rationale")
    limitations = data.get("limitations")
    if not string_list(limitations, non_empty=status in {"complete", "blocked"}):
        errors.append("limitations_must_be_string_array")
    check_string(errors, data.get("rollback"), "rollback")
    return errors


def emit_result(path: str, data: dict[str, Any] | None, errors: list[str], as_json: bool) -> None:
    result = {
        "schema": RESULT_SCHEMA,
        "path": path,
        "valid": not errors,
        "errors": errors,
        "status": data.get("status") if data else None,
        "verdict": data.get("verdict") if data else None,
    }
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    elif errors:
        print("Capability evaluation is invalid:")
        for error in errors:
            print(f"- {error}")
    else:
        print("Capability evaluation is valid.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a capability.evaluation.v1 plan or receipt."
    )
    parser.add_argument("evaluation", nargs="?", help="Path to an evaluation JSON file.")
    parser.add_argument("--template", action="store_true", help="Print a valid planned template.")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable result.")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(TEMPLATE, indent=2, ensure_ascii=False))
        return 0
    if not args.evaluation:
        parser.error("evaluation path is required unless --template is used")

    path = Path(args.evaluation)
    try:
        data = load_strict_json(path)
    except StrictJsonError as exc:
        emit_result(str(path), None, [str(exc)], args.json)
        return 1
    errors = validate(data)
    emit_result(str(path), data, errors, args.json)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
