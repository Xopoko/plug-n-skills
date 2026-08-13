#!/usr/bin/env python3
"""Regression tests for the migrated agent harness artifact validator."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "scripts"
FAILURES: list[str] = []
PASSES = 0


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd or PLUGIN_ROOT),
        env=merged_env,
        capture_output=True,
        text=True,
    )


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSES
    if ok:
        PASSES += 1
    else:
        FAILURES.append(label + (f": {detail}" if detail else ""))


def test_harness_artifact_validator() -> None:
    script = str(SCRIPTS / "harness" / "validate_harness_artifact.py")

    def system_tuple() -> dict:
        return {
            name: {"id": f"fixture-{name}", "version": "1.0.0"}
            for name in (
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
        }

    design = {
        "schema": "agent_harness.design.v1",
        "outcome": {
            "description": "Produce a verified record update.",
            "workload": "Interactive support workflow.",
            "mode": "interactive",
            "trust_boundaries": ["Operator input and external record data are distinct."],
            "side_effects": ["A scoped external record may change."],
        },
        "success_criteria": ["Post-state and approval event both pass."],
        "non_goals": ["Do not provide unrestricted record access."],
        "provider_boundary": {
            "required_capabilities": ["typed_tool_calls", "cancellation"],
            "unsupported_behavior": "Reject the run before execution.",
            "degraded_behavior": "Disable optional parallel reads.",
        },
        "control_loop": {
            "states": ["observe", "decide", "authorize", "execute", "record", "stop"],
            "transitions": [
                {"from": "observe", "event": "context.ready", "to": "decide", "guard": "context is valid", "effects": []},
                {"from": "decide", "event": "command.proposed", "to": "authorize", "guard": "command schema is valid", "effects": ["append proposal"]},
                {"from": "authorize", "event": "policy.allowed", "to": "execute", "guard": "approval is bound", "effects": ["append intent"]},
                {"from": "execute", "event": "executor.returned", "to": "record", "guard": "result schema is valid", "effects": ["append result"]},
                {"from": "record", "event": "oracle.passed", "to": "stop", "guard": "no unresolved effect", "effects": ["append terminal event"]},
            ],
            "invariants": [
                "No executor call occurs before a durable allowed intent.",
                "No new intent is accepted after cancellation or termination.",
            ],
            "terminal_outcomes": ["succeeded", "failed", "cancelled"],
            "bounds": {"max_steps": 12, "wall_time_seconds": 120, "max_concurrency": 2},
        },
        "tools": [
            {
                "name": "record.update",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "effect": "external_compensatable",
                "timeout_seconds": 20,
                "authority": "execute_scoped",
                "approval": "policy",
                "idempotency": "keyed",
                "reconciliation": "Query by effect ID before any retry.",
            }
        ],
        "state": {
            "state_schema": "agent_harness.fixture_state.v1",
            "canonical_log": "Append-only per-run event log.",
            "checkpoint": "Versioned projection through a durable sequence.",
            "replay": "Rebuild projections without re-executing recorded effects.",
            "resume": "Reconcile unresolved intents before a new model call.",
            "reconciliation": "Resolve every intent without a terminal result by effect ID.",
        },
        "context": {
            "sources": [
                {"name": "operator-request", "trust": "operator"},
                {"name": "record-snapshot", "trust": "authenticated_external"},
            ],
            "token_budget": 16000,
            "compaction": "Rebuild a provenance-preserving bounded projection.",
        },
        "policy": {
            "default_decision": "deny",
            "approval": "Bind approval to intent, arguments, scope, and expiry.",
            "isolation": "Run the executor through a scoped broker.",
        },
        "recovery": {
            "max_attempts": 2,
            "retryable_failures": ["provider_transient", "tool_timeout_before_effect"],
            "ambiguous_effect": "Stop and reconcile by effect ID.",
        },
        "cancellation": {
            "propagation": "Propagate to provider, tool, and child work.",
            "safe_stop": "Reject new intents and reconcile active effects.",
        },
        "observability": {
            "event_schema": "agent_harness.event.v1",
            "redaction": "Redact secrets before durable storage.",
        },
        "delegation": {
            "enabled": False,
            "rationale": "The workflow has no independent parallel task.",
        },
        "evaluation_handoff": {
            "claims": ["Cancellation prevents new external intents."],
            "scenarios": ["cancel-during-tool", "restart-after-intent"],
        },
        "risks": ["External reconciliation can be temporarily unavailable."],
    }

    reconfiguration_block = {
        "supported": True,
        "rationale": "The service changes provider and executor bindings without stopping admission.",
        "candidate_generation": {
            "id_schema": "agent_harness.runtime_generation.v1",
            "config_revision": "fixture-config@2",
            "config_digest": "sha256:fixture-config-v2",
            "compatibility_policy": "Require matching declared interface major versions.",
            "state_migration": "Validate a versioned projection migration before admission.",
            "provenance": ["fixture-source@2", "fixture-lock@2"],
            "components": [
                {
                    "id": "provider:fixture",
                    "kind": "provider_adapter",
                    "revision": "2.0.0",
                    "interface_version": "provider.v1",
                    "capabilities": ["typed_tool_calls", "cancellation"],
                },
                {
                    "id": "executor:record.update",
                    "kind": "executor",
                    "revision": "2.0.0",
                    "interface_version": "record.update.v1",
                    "capabilities": ["idempotency_key", "effect_reconciliation"],
                },
                {
                    "id": "tools:fixture",
                    "kind": "tool_registry",
                    "revision": "2.0.0",
                    "interface_version": "tools.v1",
                    "capabilities": [],
                },
                {
                    "id": "policy:fixture",
                    "kind": "policy",
                    "revision": "2.0.0",
                    "interface_version": "policy.v1",
                    "capabilities": [],
                },
                {
                    "id": "context:fixture",
                    "kind": "context_builder",
                    "revision": "2.0.0",
                    "interface_version": "context.v1",
                    "capabilities": [],
                },
                {
                    "id": "loop:fixture",
                    "kind": "control_loop",
                    "revision": "2.0.0",
                    "interface_version": "control-loop.v1",
                    "capabilities": [],
                },
                {
                    "id": "state:fixture",
                    "kind": "state_store",
                    "revision": "2.0.0",
                    "interface_version": "state.v1",
                    "capabilities": [],
                },
            ],
        },
        "activation": {
            "candidate_validation": "Validate schemas, dependencies, and capabilities before staging.",
            "attempt_id_schema": "agent_harness.activation_attempt.v1",
            "expected_active_generation": "Bind to the generation observed when candidate build started.",
            "compare_and_swap": True,
            "readiness_gate": "Await candidate startup and synthetic readiness probes before publication.",
            "readiness_timeout_seconds": 15,
            "commit_point": "Publish one active-generation pointer for new admissions.",
            "health_gate": "Exercise provider and executor probes before releasing the prior generation.",
            "health_window_seconds": 60,
            "pre_commit_failure_behavior": "preserve_expected_active_generation",
            "post_commit_failure_behavior": "rollback_via_compare_and_swap",
        },
        "run_binding": {
            "admission": "Bind a new run to the generation read at admission.",
            "binding_policy": "pin",
            "late_result_fencing": "Require matching run and generation IDs on every callback.",
            "lease_release": "Release the generation after its final terminal callback is durable.",
            "retirement": {
                "admission_closed_at_commit": True,
                "mode": "drain_then_cancel",
                "quiescence_condition": "No live leases or pending generation-bound callbacks remain.",
                "timeout_seconds": 30,
                "timeout_behavior": "cancel_and_fence",
                "cancel_acknowledgement": "Record acknowledgement or timeout for every cancelled run.",
                "teardown_completion": "Await every owned disposer and resource release.",
            },
        },
        "isolation": {
            "boundary_type": "process",
            "trust_model": "reviewed_trusted",
            "authority_surfaces": ["filesystem", "network", "credentials"],
            "failure_containment": "A candidate failure cannot mutate the active registry.",
            "quarantine": "Stop admission and retain diagnostics for a failed candidate.",
            "enforcement_evidence": "Record process policy and brokered authority probe results.",
        },
        "rollback": {
            "retain_prior_generation": True,
            "expected_failed_generation": "Use the generation published by this activation attempt.",
            "target_generation": "Use the retained predecessor of the failed generation.",
            "activation_attempt_binding": "Bind the rollback to one activation attempt ID.",
            "compare_and_swap": True,
            "timeout_seconds": 30,
            "trigger": "Candidate health gate fails during the rollback window.",
            "receipt": "Append the expected, failed, and restored generation IDs.",
            "failed_generation_runs": "Pin admitted runs or cancel and fence them under the recorded retirement policy.",
            "external_effects": "Reconcile effects by their original intent and effect IDs.",
            "release_condition": {
                "health_window_closed": True,
                "rollback_terminal": True,
                "leases_zero": True,
                "teardown_complete": True,
            },
        },
        "evidence": {
            "event_schema": "agent_harness.runtime_lifecycle_event.v1",
            "generation_binding": "Record the generation ID on every run event and result.",
            "activation_receipt": "Record candidate validation and the admission commit point.",
            "rollback_receipt": "Record trigger, outcome, timeout, and retained generation.",
        },
    }

    evaluation = {
        "schema": "agent_harness.evaluation_plan.v1",
        "system_tuple": system_tuple(),
        "task_suite": {
            "id": "fixture-suite",
            "version": "1.0.0",
            "scenario_ids": [
                "happy-noncoding",
                "policy-denial",
                "tool-error",
                "timeout",
                "context-pressure",
                "recovery",
                "cancellation",
                "untrusted-input",
            ],
            "reset_procedure": "Restore the versioned initial-state fixture before each trial.",
            "seed_policy": "Record the declared sampling seed for every trial.",
            "ordering_policy": "Use a predeclared balanced scenario order.",
        },
        "variants": [
            {"id": "candidate", "changes": ["Use bounded context projection."]}
        ],
        "baselines": ["baseline@1.0.0"],
        "oracles": [
            {
                "id": "post-state",
                "type": "deterministic",
                "target": "post_state_and_policy_events",
                "version": "1.0.0",
            }
        ],
        "repeated_trials": 3,
        "fault_injection": [
            {
                "id": "tool-timeout",
                "target": "record.update executor",
                "method": "Return a timeout before or after the effect boundary by fixture case.",
            }
        ],
        "analysis": {
            "uncertainty_method": "Report per-scenario empirical intervals and raw counts.",
            "exclusion_policy": "Exclude only predeclared invalid fixture setup runs.",
        },
        "residual_risks": ["The synthetic external record is simpler than a live service."],
        "metrics": [
            {
                "name": "task_success_rate",
                "definition": "Runs passing every required oracle divided by judged runs.",
                "denominator": "judged runs",
            }
        ],
        "scenarios": [
            {"id": "happy-noncoding", "classes": ["happy_path", "stateful", "noncoding"]},
            {"id": "policy-denial", "classes": ["policy_denial"]},
            {"id": "tool-error", "classes": ["tool_error"]},
            {"id": "timeout", "classes": ["timeout"]},
            {"id": "context-pressure", "classes": ["context_pressure"]},
            {"id": "recovery", "classes": ["recovery", "stateful"]},
            {"id": "cancellation", "classes": ["cancellation"]},
            {"id": "untrusted-input", "classes": ["untrusted_input"]},
        ],
        "release_gates": [
            {
                "metric": "task_success_rate",
                "operator": ">=",
                "threshold": 0.9,
                "blocking": True,
            }
        ],
        "provenance": ["fixture-suite@1.0.0", "evaluator@1.0.0"],
    }

    reconfiguration_classes = [
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
    ]
    reconfiguration_metrics = [
        "generation_misbinding_count",
        "generation_evidence_gap_count",
        "partial_activation_count",
        "unauthorized_capability_change_count",
        "stale_rollback_overwrite_count",
        "false_rollback_success_count",
        "external_effect_misreport_count",
        "isolation_leak_count",
    ]

    reconfiguration_evaluation = json.loads(json.dumps(evaluation))
    reconfiguration_evaluation["runtime_reconfiguration"] = {
        "claimed": True,
        "rationale": "The candidate design claims live generation replacement.",
        "design_ref": "sha256:fixture-design-with-reconfiguration",
        "result_schema": "agent_harness.run_result.v2",
    }
    for scenario_class in reconfiguration_classes:
        scenario_id = f"fixture-{scenario_class.replace('_', '-')}"
        injection_id = f"inject-{scenario_class.replace('_', '-')}"
        reconfiguration_evaluation["task_suite"]["scenario_ids"].append(scenario_id)
        reconfiguration_evaluation["fault_injection"].append(
            {
                "id": injection_id,
                "target": "runtime generation lifecycle",
                "method": f"Inject the declared {scenario_class} boundary condition.",
                "classes": [scenario_class],
            }
        )
        reconfiguration_evaluation["scenarios"].append(
            {
                "id": scenario_id,
                "classes": [scenario_class],
                "fault_injection_ids": [injection_id],
                "oracle_ids": ["post-state"],
            }
        )
    for metric_name in reconfiguration_metrics:
        reconfiguration_evaluation["metrics"].append(
            {
                "name": metric_name,
                "definition": f"Observed count for {metric_name}.",
                "denominator": "scheduled runtime-reconfiguration trials",
            }
        )
        reconfiguration_evaluation["release_gates"].append(
            {
                "metric": metric_name,
                "operator": "zero",
                "threshold": 0,
                "blocking": True,
            }
        )

    run_result = {
        "schema": "agent_harness.run_result.v1",
        "run_id": "run-fixture-001",
        "scenario_id": "happy-noncoding",
        "system_tuple": system_tuple(),
        "status": "succeeded",
        "metrics": {"task_success": True},
        "trace_ref": "sha256:fixture-trace",
        "terminal": {
            "reason": "All required oracles passed.",
            "started_at": "2026-08-06T12:00:00Z",
            "ended_at": "2026-08-06T12:00:01Z",
            "terminal_event_id": "evt-terminal-001",
            "integrity_digest": "sha256:fixture-integrity",
        },
        "failures": [],
        "evidence": {
            "oracle_results": [
                {
                    "id": "post-state",
                    "status": "passed",
                    "evidence_ref": "sha256:fixture-post-state",
                }
            ],
            "policy_events": [
                {"decision": "allow", "event_ref": "evt-policy-001"}
            ],
            "effect_records": [
                {
                    "intent_id": "intent-001",
                    "result_ref": "evt-result-001",
                    "effect_id": "effect-001",
                }
            ],
            "unresolved_effects": [],
            "post_state_ref": "sha256:fixture-post-state",
            "evidence_grade": "E2",
            "redactions": [],
        },
        "usage": {"tokens": 500, "latency_ms": 1200, "cost": 0.01},
        "artifact_versions": {
            "design": "1.0.0",
            "evaluation_plan": "1.0.0",
            "scenario": "1.0.0",
        },
    }
    reconfiguration_run_result = json.loads(json.dumps(run_result))
    reconfiguration_run_result["schema"] = "agent_harness.run_result.v2"
    reconfiguration_run_result["scenario_id"] = "fixture-reconfiguration-stale-rollback"
    reconfiguration_run_result["runtime_generation"] = {
        "design_ref": "sha256:fixture-design-with-reconfiguration",
        "evaluation_plan_ref": "sha256:fixture-reconfiguration-evaluation",
        "binding_policy": "pin",
        "admitted_generation_id": "generation-fixture-002",
        "terminal_generation_id": "generation-fixture-002",
        "activation_attempt_id": "activation-fixture-002",
        "activation_receipt_ref": "sha256:fixture-activation-receipt",
        "trace_generation_binding_ref": "sha256:fixture-generation-trace",
        "effect_generation_binding_ref": "sha256:fixture-generation-effects",
    }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        for name, artifact in (
            ("design", design),
            ("evaluation", evaluation),
            ("run-result", run_result),
        ):
            path = root / f"{name}.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            result = run([script, str(path), "--json"])
            payload = json.loads(result.stdout)
            check(
                f"harness validator: valid {name} passes",
                result.returncode == 0 and payload.get("valid") is True,
                result.stdout + result.stderr,
            )

        reconfigured = json.loads(json.dumps(design))
        reconfigured["runtime_reconfiguration"] = reconfiguration_block
        path = root / "reconfigured-design.json"
        path.write_text(json.dumps(reconfigured), encoding="utf-8")
        result = run([script, str(path), "--json"])
        payload = json.loads(result.stdout)
        check(
            "harness validator: complete runtime reconfiguration design passes",
            result.returncode == 0 and payload.get("valid") is True,
            result.stdout,
        )

        restart_only = json.loads(json.dumps(design))
        restart_only["runtime_reconfiguration"] = {
            "supported": False,
            "rationale": "This deployment replaces the process through a controlled restart.",
        }
        path = root / "restart-only-design.json"
        path.write_text(json.dumps(restart_only), encoding="utf-8")
        result = run([script, str(path), "--json"])
        payload = json.loads(result.stdout)
        check(
            "harness validator: explicit restart-only design passes",
            result.returncode == 0 and payload.get("valid") is True,
            result.stdout,
        )

        path = root / "reconfiguration-evaluation.json"
        path.write_text(json.dumps(reconfiguration_evaluation), encoding="utf-8")
        result = run([script, str(path), "--json"])
        payload = json.loads(result.stdout)
        check(
            "harness validator: complete runtime reconfiguration evaluation passes",
            result.returncode == 0 and payload.get("valid") is True,
            result.stdout,
        )

        path = root / "reconfiguration-run-result.json"
        path.write_text(json.dumps(reconfiguration_run_result), encoding="utf-8")
        result = run([script, str(path), "--json"])
        payload = json.loads(result.stdout)
        check(
            "harness validator: generation-bound v2 run result passes",
            result.returncode == 0 and payload.get("valid") is True,
            result.stdout,
        )

        migrated_run_result = json.loads(json.dumps(reconfiguration_run_result))
        migrated_run_result["runtime_generation"]["binding_policy"] = "explicit_migrate"
        migrated_run_result["runtime_generation"][
            "terminal_generation_id"
        ] = "generation-fixture-003"
        migrated_run_result["runtime_generation"][
            "migration_receipt_ref"
        ] = "sha256:fixture-migration-receipt"
        path = root / "migrated-reconfiguration-run-result.json"
        path.write_text(json.dumps(migrated_run_result), encoding="utf-8")
        result = run([script, str(path), "--json"])
        payload = json.loads(result.stdout)
        check(
            "harness validator: explicit migration result carries a receipt",
            result.returncode == 0 and payload.get("valid") is True,
            result.stdout,
        )

        partial_reconfiguration = json.loads(json.dumps(reconfigured))
        del partial_reconfiguration["runtime_reconfiguration"]["activation"]["health_gate"]
        path = root / "partial-reconfiguration.json"
        path.write_text(json.dumps(partial_reconfiguration), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: partial reconfiguration contract fails",
            result.returncode != 0 and "health_gate" in result.stdout,
            result.stdout,
        )

        incomplete_generation = json.loads(json.dumps(reconfigured))
        incomplete_generation["runtime_reconfiguration"]["candidate_generation"][
            "components"
        ] = [
            component
            for component in incomplete_generation["runtime_reconfiguration"][
                "candidate_generation"
            ]["components"]
            if component["kind"] != "state_store"
        ]
        path = root / "incomplete-generation.json"
        path.write_text(json.dumps(incomplete_generation), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: candidate generation covers required runtime seams",
            result.returncode != 0
            and "missing required runtime component kinds" in result.stdout
            and "state_store" in result.stdout,
            result.stdout,
        )

        capability_loss = json.loads(json.dumps(reconfigured))
        provider_component = next(
            component
            for component in capability_loss["runtime_reconfiguration"][
                "candidate_generation"
            ]["components"]
            if component["kind"] == "provider_adapter"
        )
        provider_component["capabilities"].remove("cancellation")
        path = root / "candidate-capability-loss.json"
        path.write_text(json.dumps(capability_loss), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: provider capability negotiation is generation-bound",
            result.returncode != 0
            and "provider adapters omit required capabilities" in result.stdout
            and "cancellation" in result.stdout,
            result.stdout,
        )

        unsupported_reconfiguration = json.loads(json.dumps(design))
        unsupported_reconfiguration["runtime_reconfiguration"] = {
            "supported": False,
            "rationale": "This host requires a controlled restart.",
            "activation": {"claim": "hot swap"},
        }
        path = root / "unsupported-reconfiguration.json"
        path.write_text(json.dumps(unsupported_reconfiguration), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: unsupported reconfiguration cannot claim activation",
            result.returncode != 0 and "cannot declare activation fields" in result.stdout,
            result.stdout,
        )

        unsafe_reconfiguration = json.loads(json.dumps(reconfigured))
        unsafe_reconfiguration["runtime_reconfiguration"]["activation"][
            "post_commit_failure_behavior"
        ] = "best_effort_cleanup"
        unsafe_reconfiguration["runtime_reconfiguration"]["rollback"][
            "retain_prior_generation"
        ] = False
        path = root / "unsafe-reconfiguration.json"
        path.write_text(json.dumps(unsafe_reconfiguration), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: unsafe activation and rollback fail",
            result.returncode != 0
            and "rollback_via_compare_and_swap" in result.stdout
            and "retain_prior_generation" in result.stdout,
            result.stdout,
        )

        implicit_migration = json.loads(json.dumps(reconfigured))
        implicit_migration["runtime_reconfiguration"]["run_binding"][
            "binding_policy"
        ] = "explicit_migrate"
        implicit_migration["runtime_reconfiguration"]["run_binding"]["retirement"][
            "mode"
        ] = "migrate"
        path = root / "implicit-migration.json"
        path.write_text(json.dumps(implicit_migration), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: migration needs an explicit contract",
            result.returncode != 0 and "migration_contract" in result.stdout,
            result.stdout,
        )

        stale_rollback_contract = json.loads(json.dumps(reconfigured))
        del stale_rollback_contract["runtime_reconfiguration"]["rollback"][
            "expected_failed_generation"
        ]
        path = root / "stale-rollback-contract.json"
        path.write_text(json.dumps(stale_rollback_contract), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: rollback is CAS-bound to the failed generation",
            result.returncode != 0 and "expected_failed_generation" in result.stdout,
            result.stdout,
        )

        open_old_admission = json.loads(json.dumps(reconfigured))
        open_old_admission["runtime_reconfiguration"]["run_binding"]["retirement"][
            "admission_closed_at_commit"
        ] = False
        path = root / "open-old-admission.json"
        path.write_text(json.dumps(open_old_admission), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: activation closes old admission atomically",
            result.returncode != 0 and "admission_closed_at_commit" in result.stdout,
            result.stdout,
        )

        untrusted_same_process = json.loads(json.dumps(reconfigured))
        untrusted_same_process["runtime_reconfiguration"]["isolation"][
            "trust_model"
        ] = "untrusted"
        untrusted_same_process["runtime_reconfiguration"]["isolation"][
            "boundary_type"
        ] = "same_process"
        path = root / "untrusted-same-process.json"
        path.write_text(json.dumps(untrusted_same_process), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: untrusted modules need an external boundary",
            result.returncode != 0
            and "untrusted modules cannot use same_process" in result.stdout,
            result.stdout,
        )

        result_without_generation = json.loads(json.dumps(reconfiguration_run_result))
        del result_without_generation["runtime_generation"]
        path = root / "result-without-generation.json"
        path.write_text(json.dumps(result_without_generation), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: run results carry generation evidence",
            result.returncode != 0 and "runtime_generation" in result.stdout,
            result.stdout,
        )

        misbound_pin_result = json.loads(json.dumps(reconfiguration_run_result))
        misbound_pin_result["runtime_generation"][
            "terminal_generation_id"
        ] = "generation-fixture-003"
        path = root / "misbound-pin-result.json"
        path.write_text(json.dumps(misbound_pin_result), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: pin binding preserves one generation through terminal",
            result.returncode != 0
            and "pin binding requires" in result.stdout,
            result.stdout,
        )

        unreceipted_migration_result = json.loads(json.dumps(migrated_run_result))
        del unreceipted_migration_result["runtime_generation"][
            "migration_receipt_ref"
        ]
        path = root / "unreceipted-migration-result.json"
        path.write_text(json.dumps(unreceipted_migration_result), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: migrated run result requires a migration receipt",
            result.returncode != 0 and "migration_receipt_ref" in result.stdout,
            result.stdout,
        )

        unknown_reconfiguration_field = json.loads(json.dumps(reconfigured))
        unknown_reconfiguration_field["runtime_reconfiguration"]["activation"][
            "silent_override"
        ] = True
        path = root / "unknown-reconfiguration-field.json"
        path.write_text(json.dumps(unknown_reconfiguration_field), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: runtime reconfiguration rejects unknown fields",
            result.returncode != 0
            and "unknown fields" in result.stdout
            and "silent_override" in result.stdout,
            result.stdout,
        )

        incomplete_reconfiguration_suite = json.loads(
            json.dumps(reconfiguration_evaluation)
        )
        missing_scenario = next(
            scenario_id
            for scenario_id in incomplete_reconfiguration_suite["task_suite"][
                "scenario_ids"
            ]
            if "invalid-candidate" in scenario_id
        )
        incomplete_reconfiguration_suite["task_suite"]["scenario_ids"].remove(
            missing_scenario
        )
        path = root / "incomplete-reconfiguration-suite.json"
        path.write_text(json.dumps(incomplete_reconfiguration_suite), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: claimed reconfiguration requires scheduled fault classes",
            result.returncode != 0
            and "runtime reconfiguration claim missing required classes" in result.stdout
            and "reconfiguration_invalid_candidate" in result.stdout,
            result.stdout,
        )

        unbound_fault_scenario = json.loads(json.dumps(reconfiguration_evaluation))
        target_scenario = next(
            scenario
            for scenario in unbound_fault_scenario["scenarios"]
            if "reconfiguration_late_result" in scenario["classes"]
        )
        del target_scenario["fault_injection_ids"]
        path = root / "unbound-fault-scenario.json"
        path.write_text(json.dumps(unbound_fault_scenario), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: each reconfiguration class binds fault and oracle evidence",
            result.returncode != 0
            and "fault_injection_ids" in result.stdout
            and "reconfiguration_late_result" in result.stdout,
            result.stdout,
        )

        llm_only_reconfiguration_scenarios = json.loads(
            json.dumps(reconfiguration_evaluation)
        )
        llm_only_reconfiguration_scenarios["oracles"].append(
            {
                "id": "llm-reconfiguration",
                "type": "llm",
                "target": "runtime_generation_trace",
                "version": "1.0.0",
            }
        )
        for scenario in llm_only_reconfiguration_scenarios["scenarios"]:
            if set(scenario["classes"]) & set(reconfiguration_classes):
                scenario["oracle_ids"] = ["llm-reconfiguration"]
        path = root / "llm-only-reconfiguration-scenarios.json"
        path.write_text(
            json.dumps(llm_only_reconfiguration_scenarios), encoding="utf-8"
        )
        result = run([script, str(path), "--json"])
        check(
            "harness validator: each reconfiguration scenario has a non-LLM oracle",
            result.returncode != 0
            and "requires a linked deterministic or human oracle" in result.stdout,
            result.stdout,
        )

        incomplete_reconfiguration_gates = json.loads(
            json.dumps(reconfiguration_evaluation)
        )
        incomplete_reconfiguration_gates["release_gates"] = [
            gate
            for gate in incomplete_reconfiguration_gates["release_gates"]
            if gate["metric"] != "false_rollback_success_count"
        ]
        path = root / "incomplete-reconfiguration-gates.json"
        path.write_text(json.dumps(incomplete_reconfiguration_gates), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: claimed reconfiguration requires blocking zero gates",
            result.returncode != 0
            and "runtime reconfiguration metrics need blocking zero gates" in result.stdout
            and "false_rollback_success_count" in result.stdout,
            result.stdout,
        )

        nonzero_zero_gate = json.loads(json.dumps(reconfiguration_evaluation))
        target_gate = next(
            gate
            for gate in nonzero_zero_gate["release_gates"]
            if gate["operator"] == "zero"
        )
        target_gate["threshold"] = 1
        path = root / "nonzero-zero-gate.json"
        path.write_text(json.dumps(nonzero_zero_gate), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: zero operator requires a numeric zero threshold",
            result.returncode != 0 and "zero operator requires numeric 0" in result.stdout,
            result.stdout,
        )

        unbounded = json.loads(json.dumps(design))
        unbounded["control_loop"]["bounds"]["max_steps"] = 0
        path = root / "unbounded.json"
        path.write_text(json.dumps(unbounded), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: unbounded design fails",
            result.returncode != 0 and "max_steps" in result.stdout,
            result.stdout,
        )

        unsafe = json.loads(json.dumps(design))
        unsafe["tools"][0]["approval"] = "never"
        path = root / "unsafe.json"
        path.write_text(json.dumps(unsafe), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: unapproved external effect fails",
            result.returncode != 0 and "cannot use never" in result.stdout,
            result.stdout,
        )

        llm_only = json.loads(json.dumps(evaluation))
        llm_only["oracles"] = [
            {
                "id": "judge",
                "type": "llm",
                "target": "final_text",
                "version": "1.0.0",
            }
        ]
        path = root / "llm-only.json"
        path.write_text(json.dumps(llm_only), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: LLM-only evaluation fails",
            result.returncode != 0 and "LLM-only" in result.stdout,
            result.stdout,
        )

        mismatched = json.loads(json.dumps(evaluation))
        mismatched["task_suite"]["scenario_ids"].append("missing-scenario")
        mismatched["release_gates"][0]["metric"] = "undefined_metric"
        path = root / "mismatched-evaluation.json"
        path.write_text(json.dumps(mismatched), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: mismatched scenarios and metrics fail",
            result.returncode != 0
            and "missing-scenario" in result.stdout
            and "not declared" in result.stdout,
            result.stdout,
        )

        unscheduled_safety = json.loads(json.dumps(evaluation))
        unscheduled_safety["task_suite"]["scenario_ids"] = ["happy-noncoding"]
        path = root / "unscheduled-safety.json"
        path.write_text(json.dumps(unscheduled_safety), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: unscheduled safety scenarios do not count as coverage",
            result.returncode != 0
            and "scheduled scenarios missing required classes" in result.stdout
            and "policy_denial" in result.stdout,
            result.stdout,
        )

        unscheduled_recommended = json.loads(json.dumps(evaluation))
        unscheduled_recommended["task_suite"]["scenario_ids"].remove(
            "untrusted-input"
        )
        path = root / "unscheduled-recommended.json"
        path.write_text(json.dumps(unscheduled_recommended), encoding="utf-8")
        result = run([script, str(path), "--json"])
        payload = json.loads(result.stdout)
        check(
            "harness validator: unscheduled scenario does not satisfy recommended coverage",
            result.returncode == 0
            and any(
                "scheduled scenarios do not cover recommended classes: untrusted_input"
                in warning
                for warning in payload.get("warnings", [])
            ),
            result.stdout,
        )

        contradictory = json.loads(json.dumps(evaluation))
        contradictory["scenarios"][0]["classes"].append("timeout")
        path = root / "contradictory-scenario.json"
        path.write_text(json.dumps(contradictory), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: contradictory scenario classes fail",
            result.returncode != 0 and "happy_path cannot share" in result.stdout,
            result.stdout,
        )

        incomplete_plan = json.loads(json.dumps(evaluation))
        del incomplete_plan["task_suite"]["reset_procedure"]
        del incomplete_plan["fault_injection"]
        del incomplete_plan["analysis"]
        path = root / "incomplete-plan.json"
        path.write_text(json.dumps(incomplete_plan), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: missing reset, fault, and uncertainty contracts fail",
            result.returncode != 0
            and "reset_procedure" in result.stdout
            and "fault_injection" in result.stdout
            and "analysis" in result.stdout,
            result.stdout,
        )

        unsupported_design = json.loads(json.dumps(design))
        del unsupported_design["non_goals"]
        del unsupported_design["control_loop"]["invariants"]
        path = root / "incomplete-design.json"
        path.write_text(json.dumps(unsupported_design), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: missing non-goals and invariants fail",
            result.returncode != 0
            and "non_goals" in result.stdout
            and "invariants" in result.stdout,
            result.stdout,
        )

        false_success = json.loads(json.dumps(run_result))
        false_success["evidence"]["oracle_results"][0]["status"] = "failed"
        false_success["evidence"]["unresolved_effects"] = ["effect-unknown"]
        false_success["failures"] = [
            {
                "code": "oracle_failed",
                "source": "post-state",
                "blocking": True,
                "evidence_ref": "sha256:fixture-failure",
            }
        ]
        path = root / "false-success.json"
        path.write_text(json.dumps(false_success), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: unsupported succeeded status fails",
            result.returncode != 0
            and "every oracle" in result.stdout
            and "blocking failure" in result.stdout
            and "unresolved effects" in result.stdout,
            result.stdout,
        )

        for index, constant in enumerate(("NaN", "Infinity", "-Infinity")):
            path = root / f"nonstandard-constant-{index}.json"
            path.write_text(
                '{"schema":"agent_harness.design.v1","value":' + constant + "}",
                encoding="utf-8",
            )
            result = run([script, str(path), "--json"])
            payload = json.loads(result.stdout)
            check(
                f"harness validator: non-standard JSON constant {constant} fails",
                result.returncode != 0
                and payload.get("artifact_schema") is None
                and "invalid JSON" in result.stdout
                and constant in result.stdout,
                result.stdout,
            )

        large_integer = json.loads(json.dumps(design))
        large_integer["control_loop"]["bounds"]["wall_time_seconds"] = 10**1000
        path = root / "large-integer.json"
        path.write_text(json.dumps(large_integer), encoding="utf-8")
        result = run([script, str(path), "--json"])
        payload = json.loads(result.stdout)
        check(
            "harness validator: large JSON integer does not overflow numeric validation",
            result.returncode == 0 and payload.get("valid") is True,
            result.stdout,
        )

        overflow_threshold = json.loads(json.dumps(evaluation))
        overflow_threshold["release_gates"][0]["threshold"] = "__OVERFLOW__"
        path = root / "overflow-threshold.json"
        path.write_text(
            json.dumps(overflow_threshold).replace('"__OVERFLOW__"', "1e100000"),
            encoding="utf-8",
        )
        result = run([script, str(path), "--json"])
        check(
            "harness validator: non-finite release threshold fails",
            result.returncode != 0
            and "threshold" in result.stdout
            and "finite number or boolean" in result.stdout,
            result.stdout,
        )

        boolean_threshold = json.loads(json.dumps(evaluation))
        boolean_threshold["release_gates"][0]["operator"] = "=="
        boolean_threshold["release_gates"][0]["threshold"] = True
        path = root / "boolean-threshold.json"
        path.write_text(json.dumps(boolean_threshold), encoding="utf-8")
        result = run([script, str(path), "--json"])
        payload = json.loads(result.stdout)
        check(
            "harness validator: boolean release threshold remains supported",
            result.returncode == 0 and payload.get("valid") is True,
            result.stdout,
        )

        invalid_boolean_threshold = json.loads(json.dumps(evaluation))
        invalid_boolean_threshold["release_gates"][0]["threshold"] = True
        path = root / "invalid-boolean-threshold.json"
        path.write_text(json.dumps(invalid_boolean_threshold), encoding="utf-8")
        result = run([script, str(path), "--json"])
        check(
            "harness validator: boolean release threshold requires equality",
            result.returncode != 0 and "boolean thresholds require ==" in result.stdout,
            result.stdout,
        )


class HarnessArtifactValidatorTests(unittest.TestCase):
    def test_migrated_validator_contract(self) -> None:
        global PASSES
        FAILURES.clear()
        PASSES = 0
        test_harness_artifact_validator()
        self.assertEqual([], FAILURES, "\n".join(FAILURES))
        self.assertGreaterEqual(PASSES, 20)


if __name__ == "__main__":
    unittest.main()
