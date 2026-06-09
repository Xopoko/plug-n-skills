#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


AUDIT_SCHEMA = "architecture_intelligence.audit.v1"
CONFORMANCE_SCHEMA = "architecture_intelligence.conformance.v1"
DECISION_SCHEMA = "architecture_intelligence.decision.v1"
FITNESS_SCHEMA = "architecture_intelligence.fitness_plan.v1"
REFACTOR_REPORT_SCHEMA = "architecture_intelligence.refactor_report.v1"
RUNTIME_TOPOLOGY_SCHEMA = "architecture_intelligence.runtime_topology.v1"
STRUCTURE_METRICS_SCHEMA = "architecture_intelligence.structure_metrics.v1"
OWNERSHIP_TOPOLOGY_SCHEMA = "architecture_intelligence.ownership_topology.v1"
SEVERITIES = {"P0", "P1", "P2", "P3"}
CONFIDENCE = {"low", "medium", "high"}
GATE_VALUES = {"pass", "risk", "unknown"}
RISK_LEVELS = {"low", "medium", "high"}
DEBT_TYPES = {"smell", "debt", "erosion", "inconsistency", "knowledge-gap", "none"}
REVERSIBILITY = {"easy", "moderate", "hard"}
FINDING_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LENSES = {
    "system-shape",
    "module-boundary",
    "dependency-direction",
    "bounded-context",
    "data-ownership",
    "ownership-topology",
    "runtime-coupling",
    "quality-attribute",
    "testability",
    "operability",
    "documentation-drift",
    "migration-risk",
}
DECISION_STATUSES = {"proposed", "accepted", "rejected", "superseded", "needs-validation"}
DECISION_TYPES = {
    "module-boundary",
    "dependency-rule",
    "data-ownership",
    "ownership-governance",
    "runtime-topology",
    "platform-choice",
    "integration-style",
    "quality-attribute",
    "migration-strategy",
    "documentation-governance",
}
CADENCES = {"local", "pre-commit", "ci", "release", "scheduled", "production"}
ROLLOUT_MODES = {"measure", "warn", "enforce"}
INTENDED_RELATIONS = {"allowed", "forbidden", "required"}
OBSERVED_RELATIONS = {"present", "absent", "unknown"}
CONFORMANCE_CLASSIFICATIONS = {"convergence", "divergence", "absence", "unknown"}
STABILITY_ROLES = {"isolated", "stable", "balanced", "volatile", "unknown"}
RUNTIME_SURFACE_TYPES = {
    "deployment",
    "runtime-config",
    "observability",
    "resilience",
    "integration",
    "data-store",
    "runtime-adaptation",
}
GAP_RISKS = {"low", "medium", "high", "unknown"}
OWNERSHIP_SOURCE_TYPES = {
    "codeowners",
    "owners",
    "owners-aliases",
    "maintainers",
    "governance",
    "contributing",
    "ownership-document",
}
OWNERSHIP_COVERAGE = {"owned", "unowned", "unknown"}
DIRTY_TREE_STATES = {"clean", "dirty", "unknown"}


def fail(message: str) -> None:
    print(f"invalid: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{path} must be a non-empty string")
    return value


def require_string_list(value: Any, path: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        fail(f"{path} must be a list")
    if not allow_empty and not value:
        fail(f"{path} must not be empty")
    if not all(isinstance(item, str) and item.strip() for item in value):
        fail(f"{path} must contain only non-empty strings")
    return value


def require_kebab(value: Any, path: str) -> str:
    text = require_string(value, path)
    if not FINDING_ID_RE.fullmatch(text):
        fail(f"{path} must be kebab-case")
    return text


def require_non_negative_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or value < 0:
        fail(f"{path} must be a non-negative integer")
    return value


def require_probability(value: Any, path: str) -> float:
    if not isinstance(value, (int, float)) or value < 0 or value > 1:
        fail(f"{path} must be a number between 0 and 1")
    return float(value)


def validate_audit(root: dict[str, Any]) -> None:
    require_string(root.get("target"), "$.target")
    require_string(root.get("summary"), "$.summary")
    context = require_dict(root.get("context"), "$.context")
    require_string(context.get("system_boundary"), "$.context.system_boundary")
    require_string_list(context.get("quality_attributes"), "$.context.quality_attributes")
    require_string_list(context.get("evidence"), "$.context.evidence")
    scenarios = context.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        fail("$.context.scenarios must be a non-empty list")
    for index, value in enumerate(scenarios):
        scenario = require_dict(value, f"$.context.scenarios[{index}]")
        for field in (
            "scenario",
            "stimulus",
            "environment",
            "response",
            "response_measure",
            "quality_attribute",
        ):
            require_string(scenario.get(field), f"$.context.scenarios[{index}].{field}")
    require_string_list(context.get("assumptions"), "$.context.assumptions", allow_empty=True)
    require_string_list(context.get("unknowns"), "$.context.unknowns", allow_empty=True)

    findings = root.get("findings")
    if not isinstance(findings, list):
        fail("$.findings must be a list")
    seen: set[str] = set()
    for index, value in enumerate(findings):
        finding = require_dict(value, f"$.findings[{index}]")
        finding_id = require_kebab(finding.get("id"), f"$.findings[{index}].id")
        if finding_id in seen:
            fail(f"duplicate finding id: {finding_id}")
        seen.add(finding_id)
        if finding.get("severity") not in SEVERITIES:
            fail(f"$.findings[{index}].severity must be one of {sorted(SEVERITIES)}")
        if finding.get("lens") not in LENSES:
            fail(f"$.findings[{index}].lens must be one of {sorted(LENSES)}")
        if finding.get("confidence") not in CONFIDENCE:
            fail(f"$.findings[{index}].confidence must be one of {sorted(CONFIDENCE)}")
        if finding.get("debt_type") not in DEBT_TYPES:
            fail(f"$.findings[{index}].debt_type must be one of {sorted(DEBT_TYPES)}")
        if finding.get("propagation_risk") not in RISK_LEVELS:
            fail(f"$.findings[{index}].propagation_risk must be one of {sorted(RISK_LEVELS)}")
        if finding.get("reversibility") not in REVERSIBILITY:
            fail(f"$.findings[{index}].reversibility must be one of {sorted(REVERSIBILITY)}")
        for field in ("evidence", "impact", "recommendation", "validation"):
            require_string(finding.get(field), f"$.findings[{index}].{field}")
        require_string(finding.get("business_impact"), f"$.findings[{index}].business_impact")

    gates = require_dict(root.get("quality_gates"), "$.quality_gates")
    for field in ("modifiability", "reliability", "security", "operability", "testability"):
        if gates.get(field) not in GATE_VALUES:
            fail(f"$.quality_gates.{field} must be one of {sorted(GATE_VALUES)}")
    require_string_list(root.get("next_actions"), "$.next_actions")


def validate_decision(root: dict[str, Any]) -> None:
    require_kebab(root.get("decision_id"), "$.decision_id")
    require_string(root.get("title"), "$.title")
    if root.get("status") not in DECISION_STATUSES:
        fail(f"$.status must be one of {sorted(DECISION_STATUSES)}")
    if root.get("decision_type") not in DECISION_TYPES:
        fail(f"$.decision_type must be one of {sorted(DECISION_TYPES)}")

    context = require_dict(root.get("context"), "$.context")
    require_string(context.get("problem"), "$.context.problem")
    require_string_list(context.get("forces"), "$.context.forces")
    require_string_list(context.get("assumptions"), "$.context.assumptions", allow_empty=True)
    evidence_items = context.get("evidence")
    if not isinstance(evidence_items, list) or not evidence_items:
        fail("$.context.evidence must be a non-empty list")
    strong_evidence = False
    for index, value in enumerate(evidence_items):
        item = require_dict(value, f"$.context.evidence[{index}]")
        require_string(item.get("source"), f"$.context.evidence[{index}].source")
        require_string(item.get("claim"), f"$.context.evidence[{index}].claim")
        if item.get("strength") not in CONFIDENCE:
            fail(f"$.context.evidence[{index}].strength must be one of {sorted(CONFIDENCE)}")
        if item.get("strength") != "low":
            strong_evidence = True

    options = root.get("options_considered")
    if not isinstance(options, list) or not options:
        fail("$.options_considered must be a non-empty list")
    for index, value in enumerate(options):
        option = require_dict(value, f"$.options_considered[{index}]")
        require_string(option.get("option"), f"$.options_considered[{index}].option")
        require_string_list(option.get("pros"), f"$.options_considered[{index}].pros", allow_empty=True)
        require_string_list(option.get("cons"), f"$.options_considered[{index}].cons", allow_empty=True)

    for field in (
        "decision",
        "rationale",
        "owner_or_review_path",
        "expires_or_revisit_trigger",
    ):
        require_string(root.get(field), f"$.{field}")
    rationale_quality = require_dict(root.get("rationale_quality"), "$.rationale_quality")
    for field in ("alternatives_complete", "tradeoffs_named"):
        if rationale_quality.get(field) not in GATE_VALUES:
            fail(f"$.rationale_quality.{field} must be one of {sorted(GATE_VALUES)}")
    if rationale_quality.get("evidence_strength") not in CONFIDENCE:
        fail(f"$.rationale_quality.evidence_strength must be one of {sorted(CONFIDENCE)}")
    if rationale_quality.get("knowledge_vaporization_risk") not in RISK_LEVELS:
        fail(f"$.rationale_quality.knowledge_vaporization_risk must be one of {sorted(RISK_LEVELS)}")
    require_string_list(root.get("consequences"), "$.consequences")
    require_string_list(root.get("fitness_functions"), "$.fitness_functions", allow_empty=True)
    if root.get("status") == "accepted" and not strong_evidence:
        fail("$.status cannot be accepted with only low-strength evidence")


def validate_conformance(root: dict[str, Any]) -> None:
    require_string(root.get("target"), "$.target")
    require_string(root.get("intended_model_source"), "$.intended_model_source")
    require_string(root.get("observed_model_source"), "$.observed_model_source")

    mappings = root.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        fail("$.mappings must be a non-empty list")
    for index, value in enumerate(mappings):
        mapping = require_dict(value, f"$.mappings[{index}]")
        require_string(mapping.get("source"), f"$.mappings[{index}].source")
        require_string(mapping.get("target"), f"$.mappings[{index}].target")
        if mapping.get("intended_relation") not in INTENDED_RELATIONS:
            fail(f"$.mappings[{index}].intended_relation must be one of {sorted(INTENDED_RELATIONS)}")
        if mapping.get("observed_relation") not in OBSERVED_RELATIONS:
            fail(f"$.mappings[{index}].observed_relation must be one of {sorted(OBSERVED_RELATIONS)}")
        if mapping.get("classification") not in CONFORMANCE_CLASSIFICATIONS:
            fail(f"$.mappings[{index}].classification must be one of {sorted(CONFORMANCE_CLASSIFICATIONS)}")
        require_string(mapping.get("evidence"), f"$.mappings[{index}].evidence")

    findings = root.get("findings")
    if not isinstance(findings, list):
        fail("$.findings must be a list")
    seen: set[str] = set()
    for index, value in enumerate(findings):
        finding = require_dict(value, f"$.findings[{index}]")
        finding_id = require_kebab(finding.get("id"), f"$.findings[{index}].id")
        if finding_id in seen:
            fail(f"duplicate finding id: {finding_id}")
        seen.add(finding_id)
        if finding.get("severity") not in SEVERITIES:
            fail(f"$.findings[{index}].severity must be one of {sorted(SEVERITIES)}")
        if finding.get("classification") not in CONFORMANCE_CLASSIFICATIONS:
            fail(f"$.findings[{index}].classification must be one of {sorted(CONFORMANCE_CLASSIFICATIONS)}")
        if finding.get("confidence") not in CONFIDENCE:
            fail(f"$.findings[{index}].confidence must be one of {sorted(CONFIDENCE)}")
        for field in ("evidence", "impact", "recommendation", "validation"):
            require_string(finding.get(field), f"$.findings[{index}].{field}")

    drift_summary = require_dict(root.get("drift_summary"), "$.drift_summary")
    for field in ("convergences", "divergences", "absences", "unknowns"):
        value = drift_summary.get(field)
        if not isinstance(value, int) or value < 0:
            fail(f"$.drift_summary.{field} must be a non-negative integer")
    require_string_list(root.get("next_actions"), "$.next_actions")


def validate_fitness(root: dict[str, Any]) -> None:
    require_string(root.get("target"), "$.target")
    require_string(root.get("architecture_principle"), "$.architecture_principle")
    rules = root.get("rules")
    if not isinstance(rules, list) or not rules:
        fail("$.rules must be a non-empty list")
    seen: set[str] = set()
    for index, value in enumerate(rules):
        rule = require_dict(value, f"$.rules[{index}]")
        rule_id = require_kebab(rule.get("id"), f"$.rules[{index}].id")
        if rule_id in seen:
            fail(f"duplicate rule id: {rule_id}")
        seen.add(rule_id)
        for field in ("intent", "scope", "signal", "mechanism", "pass_condition", "owner", "failure_action"):
            require_string(rule.get(field), f"$.rules[{index}].{field}")
        require_string(rule.get("quality_attribute"), f"$.rules[{index}].quality_attribute")
        require_string(rule.get("tradeoff"), f"$.rules[{index}].tradeoff")
        if rule.get("cadence") not in CADENCES:
            fail(f"$.rules[{index}].cadence must be one of {sorted(CADENCES)}")

    rollout = require_dict(root.get("rollout"), "$.rollout")
    if rollout.get("mode") not in ROLLOUT_MODES:
        fail(f"$.rollout.mode must be one of {sorted(ROLLOUT_MODES)}")
    require_string_list(rollout.get("migration_notes"), "$.rollout.migration_notes", allow_empty=True)


def validate_refactor_report(root: dict[str, Any]) -> None:
    require_string(root.get("target"), "$.target")
    require_string(root.get("summary"), "$.summary")

    route = require_dict(root.get("route"), "$.route")
    require_string_list(route.get("skills_used"), "$.route.skills_used")
    skipped = route.get("skipped_skills")
    if not isinstance(skipped, list):
        fail("$.route.skipped_skills must be a list")
    for index, value in enumerate(skipped):
        item = require_dict(value, f"$.route.skipped_skills[{index}]")
        require_string(item.get("skill"), f"$.route.skipped_skills[{index}].skill")
        require_string(item.get("reason"), f"$.route.skipped_skills[{index}].reason")
    require_string_list(route.get("source_evidence"), "$.route.source_evidence")

    before = require_dict(root.get("before"), "$.before")
    if before.get("dirty_tree_state") not in DIRTY_TREE_STATES:
        fail(f"$.before.dirty_tree_state must be one of {sorted(DIRTY_TREE_STATES)}")
    require_string_list(before.get("baseline_evidence"), "$.before.baseline_evidence")
    require_string_list(before.get("architecture_risks"), "$.before.architecture_risks")
    require_string(before.get("pre_probe"), "$.before.pre_probe")

    refactor = require_dict(root.get("refactor"), "$.refactor")
    require_string(refactor.get("target_boundary"), "$.refactor.target_boundary")
    require_string_list(refactor.get("quality_attributes"), "$.refactor.quality_attributes")
    slices = refactor.get("slices")
    if not isinstance(slices, list) or not slices:
        fail("$.refactor.slices must be a non-empty list")
    seen: set[str] = set()
    for index, value in enumerate(slices):
        item = require_dict(value, f"$.refactor.slices[{index}]")
        slice_id = require_kebab(item.get("id"), f"$.refactor.slices[{index}].id")
        if slice_id in seen:
            fail(f"duplicate refactor slice id: {slice_id}")
        seen.add(slice_id)
        require_string(item.get("intent"), f"$.refactor.slices[{index}].intent")
        require_string_list(item.get("files_changed"), f"$.refactor.slices[{index}].files_changed")
        if not isinstance(item.get("behavior_preserving"), bool):
            fail(f"$.refactor.slices[{index}].behavior_preserving must be a boolean")
        require_string_list(item.get("validation"), f"$.refactor.slices[{index}].validation")
        require_string(item.get("rollback"), f"$.refactor.slices[{index}].rollback")

    proof = require_dict(root.get("proof"), "$.proof")
    require_string_list(proof.get("tests"), "$.proof.tests")
    require_string_list(proof.get("fitness_functions"), "$.proof.fitness_functions", allow_empty=True)
    require_string_list(proof.get("docs_updated"), "$.proof.docs_updated", allow_empty=True)
    require_string(proof.get("post_probe"), "$.proof.post_probe")
    require_string(proof.get("runtime_verification"), "$.proof.runtime_verification")

    risks = root.get("residual_risks")
    if not isinstance(risks, list):
        fail("$.residual_risks must be a list")
    seen_risks: set[str] = set()
    for index, value in enumerate(risks):
        item = require_dict(value, f"$.residual_risks[{index}]")
        risk_id = require_kebab(item.get("id"), f"$.residual_risks[{index}].id")
        if risk_id in seen_risks:
            fail(f"duplicate residual risk id: {risk_id}")
        seen_risks.add(risk_id)
        if item.get("severity") not in SEVERITIES:
            fail(f"$.residual_risks[{index}].severity must be one of {sorted(SEVERITIES)}")
        require_string(item.get("evidence"), f"$.residual_risks[{index}].evidence")
        require_string(item.get("mitigation"), f"$.residual_risks[{index}].mitigation")
    require_string_list(root.get("next_actions"), "$.next_actions", allow_empty=True)


def validate_structure_metrics(root: dict[str, Any]) -> None:
    require_string(root.get("target"), "$.target")
    require_string(root.get("observed_model_source"), "$.observed_model_source")

    components = root.get("components")
    if not isinstance(components, list):
        fail("$.components must be a list")
    seen: set[str] = set()
    for index, value in enumerate(components):
        component = require_dict(value, f"$.components[{index}]")
        name = require_string(component.get("name"), f"$.components[{index}].name")
        if name in seen:
            fail(f"duplicate component name: {name}")
        seen.add(name)
        require_non_negative_int(component.get("afferent_coupling"), f"$.components[{index}].afferent_coupling")
        require_non_negative_int(component.get("efferent_coupling"), f"$.components[{index}].efferent_coupling")
        require_non_negative_int(component.get("incoming_edges"), f"$.components[{index}].incoming_edges")
        require_non_negative_int(component.get("outgoing_edges"), f"$.components[{index}].outgoing_edges")
        require_probability(component.get("instability"), f"$.components[{index}].instability")
        if component.get("stability_role") not in STABILITY_ROLES:
            fail(f"$.components[{index}].stability_role must be one of {sorted(STABILITY_ROLES)}")
        require_string(component.get("evidence"), f"$.components[{index}].evidence")

    cycles = root.get("cycles")
    if not isinstance(cycles, list):
        fail("$.cycles must be a list")
    for index, value in enumerate(cycles):
        cycle = require_dict(value, f"$.cycles[{index}]")
        require_string_list(cycle.get("path"), f"$.cycles[{index}].path")
        require_non_negative_int(cycle.get("length"), f"$.cycles[{index}].length")
        require_string(cycle.get("evidence"), f"$.cycles[{index}].evidence")

    summary = require_dict(root.get("summary"), "$.summary")
    for field in (
        "component_count",
        "internal_edge_count",
        "cycle_count",
        "max_efferent_coupling",
        "max_afferent_coupling",
    ):
        require_non_negative_int(summary.get(field), f"$.summary.{field}")
    interpretation = require_dict(root.get("interpretation"), "$.interpretation")
    require_string(interpretation.get("summary"), "$.interpretation.summary")
    require_string(interpretation.get("limitations"), "$.interpretation.limitations")
    require_string_list(root.get("next_actions"), "$.next_actions")


def validate_runtime_topology(root: dict[str, Any]) -> None:
    require_string(root.get("target"), "$.target")
    require_string(root.get("observed_model_source"), "$.observed_model_source")

    surfaces = root.get("surfaces")
    if not isinstance(surfaces, list):
        fail("$.surfaces must be a list")
    for index, value in enumerate(surfaces):
        surface = require_dict(value, f"$.surfaces[{index}]")
        if surface.get("type") not in RUNTIME_SURFACE_TYPES:
            fail(f"$.surfaces[{index}].type must be one of {sorted(RUNTIME_SURFACE_TYPES)}")
        require_string(surface.get("name"), f"$.surfaces[{index}].name")
        require_string_list(surface.get("evidence"), f"$.surfaces[{index}].evidence")
        if surface.get("confidence") not in CONFIDENCE:
            fail(f"$.surfaces[{index}].confidence must be one of {sorted(CONFIDENCE)}")

    hypotheses = root.get("topology_hypotheses")
    if not isinstance(hypotheses, list):
        fail("$.topology_hypotheses must be a list")
    seen: set[str] = set()
    for index, value in enumerate(hypotheses):
        hypothesis = require_dict(value, f"$.topology_hypotheses[{index}]")
        hypothesis_id = require_kebab(hypothesis.get("id"), f"$.topology_hypotheses[{index}].id")
        if hypothesis_id in seen:
            fail(f"duplicate topology hypothesis id: {hypothesis_id}")
        seen.add(hypothesis_id)
        for field in ("claim", "evidence", "validation"):
            require_string(hypothesis.get(field), f"$.topology_hypotheses[{index}].{field}")
        if hypothesis.get("confidence") not in CONFIDENCE:
            fail(f"$.topology_hypotheses[{index}].confidence must be one of {sorted(CONFIDENCE)}")

    gaps = root.get("quality_attribute_gaps")
    if not isinstance(gaps, list):
        fail("$.quality_attribute_gaps must be a list")
    for index, value in enumerate(gaps):
        gap = require_dict(value, f"$.quality_attribute_gaps[{index}]")
        require_string(gap.get("attribute"), f"$.quality_attribute_gaps[{index}].attribute")
        require_string(gap.get("signal"), f"$.quality_attribute_gaps[{index}].signal")
        if gap.get("risk") not in GAP_RISKS:
            fail(f"$.quality_attribute_gaps[{index}].risk must be one of {sorted(GAP_RISKS)}")

    summary = require_dict(root.get("summary"), "$.summary")
    for field in (
        "deployment_artifacts",
        "runtime_config_files",
        "observability_signals",
        "resilience_signals",
        "integration_signals",
    ):
        require_non_negative_int(summary.get(field), f"$.summary.{field}")
    require_string_list(root.get("limitations"), "$.limitations")
    require_string_list(root.get("next_actions"), "$.next_actions")


def validate_ownership_topology(root: dict[str, Any]) -> None:
    require_string(root.get("target"), "$.target")
    require_string(root.get("observed_model_source"), "$.observed_model_source")

    sources = root.get("ownership_sources")
    if not isinstance(sources, list):
        fail("$.ownership_sources must be a list")
    for index, value in enumerate(sources):
        source = require_dict(value, f"$.ownership_sources[{index}]")
        require_string(source.get("path"), f"$.ownership_sources[{index}].path")
        if source.get("type") not in OWNERSHIP_SOURCE_TYPES:
            fail(f"$.ownership_sources[{index}].type must be one of {sorted(OWNERSHIP_SOURCE_TYPES)}")
        require_string(source.get("evidence"), f"$.ownership_sources[{index}].evidence")
        if source.get("confidence") not in CONFIDENCE:
            fail(f"$.ownership_sources[{index}].confidence must be one of {sorted(CONFIDENCE)}")

    areas = root.get("areas")
    if not isinstance(areas, list):
        fail("$.areas must be a list")
    seen_areas: set[str] = set()
    for index, value in enumerate(areas):
        area = require_dict(value, f"$.areas[{index}]")
        path = require_string(area.get("path"), f"$.areas[{index}].path")
        if path in seen_areas:
            fail(f"duplicate ownership area: {path}")
        seen_areas.add(path)
        require_string_list(area.get("owners"), f"$.areas[{index}].owners", allow_empty=True)
        require_string_list(area.get("evidence"), f"$.areas[{index}].evidence", allow_empty=True)
        if area.get("coverage") not in OWNERSHIP_COVERAGE:
            fail(f"$.areas[{index}].coverage must be one of {sorted(OWNERSHIP_COVERAGE)}")

    risks = root.get("coordination_risks")
    if not isinstance(risks, list):
        fail("$.coordination_risks must be a list")
    seen_risks: set[str] = set()
    for index, value in enumerate(risks):
        risk = require_dict(value, f"$.coordination_risks[{index}]")
        risk_id = require_kebab(risk.get("id"), f"$.coordination_risks[{index}].id")
        if risk_id in seen_risks:
            fail(f"duplicate coordination risk id: {risk_id}")
        seen_risks.add(risk_id)
        if risk.get("severity") not in SEVERITIES:
            fail(f"$.coordination_risks[{index}].severity must be one of {sorted(SEVERITIES)}")
        for field in ("evidence", "impact", "recommendation"):
            require_string(risk.get(field), f"$.coordination_risks[{index}].{field}")
        if risk.get("confidence") not in CONFIDENCE:
            fail(f"$.coordination_risks[{index}].confidence must be one of {sorted(CONFIDENCE)}")

    summary = require_dict(root.get("summary"), "$.summary")
    for field in (
        "ownership_sources",
        "owned_areas",
        "unowned_areas",
        "cross_owned_edges",
        "ownerless_runtime_or_code_surfaces",
    ):
        require_non_negative_int(summary.get(field), f"$.summary.{field}")
    require_string_list(root.get("limitations"), "$.limitations")
    require_string_list(root.get("next_actions"), "$.next_actions")


def validate(path: Path) -> None:
    root = require_dict(json.loads(path.read_text(encoding="utf-8")), "$")
    schema = root.get("schema")
    if schema == AUDIT_SCHEMA:
        validate_audit(root)
    elif schema == CONFORMANCE_SCHEMA:
        validate_conformance(root)
    elif schema == DECISION_SCHEMA:
        validate_decision(root)
    elif schema == FITNESS_SCHEMA:
        validate_fitness(root)
    elif schema == REFACTOR_REPORT_SCHEMA:
        validate_refactor_report(root)
    elif schema == RUNTIME_TOPOLOGY_SCHEMA:
        validate_runtime_topology(root)
    elif schema == STRUCTURE_METRICS_SCHEMA:
        validate_structure_metrics(root)
    elif schema == OWNERSHIP_TOPOLOGY_SCHEMA:
        validate_ownership_topology(root)
    else:
        fail(f"$.schema must be one of {[AUDIT_SCHEMA, CONFORMANCE_SCHEMA, DECISION_SCHEMA, FITNESS_SCHEMA, REFACTOR_REPORT_SCHEMA, RUNTIME_TOPOLOGY_SCHEMA, STRUCTURE_METRICS_SCHEMA, OWNERSHIP_TOPOLOGY_SCHEMA]}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_architecture_intelligence.py <output.json>", file=sys.stderr)
        return 2
    validate(Path(argv[1]))
    print("valid=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
