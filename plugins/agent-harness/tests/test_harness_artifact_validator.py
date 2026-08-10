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
