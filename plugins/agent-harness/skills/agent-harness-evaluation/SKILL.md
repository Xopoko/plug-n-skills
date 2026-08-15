---
name: agent-harness-evaluation
description: Evaluate agent harness reliability through replay, restart, cancellation, runtime reconfiguration, concurrent generations, rollback, context pressure, and release gates. Excludes generic tests, surveys, and prompt/model-only benchmarks.
---

# Agent Harness Evaluation

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Evaluate the behavior of the complete agent system, not just the final model answer. Use deterministic post-state and trace evidence wherever possible; use judgment only for residual qualitative questions.

Read `$PLUGIN_ROOT/references/agent-harness-evaluation.md` for suite and reporting guidance and `$PLUGIN_ROOT/references/agent-harness-contracts.md` for artifact, state, and event contracts. Use `$PLUGIN_ROOT/references/agent-harness-landscape.md` only when comparing systems or provider capability surfaces.

## Evidence Boundaries

- Model output is not proof that a side effect was authorized, executed, durable, or correct.
- A transcript is not a checkpoint and cannot prove restart or recovery behavior.
- Prompt instructions, skills, and scanners do not prove sandbox or policy enforcement.
- Do not infer exactly-once behavior from a clean run. Test duplicate delivery, idempotency, reconciliation, and partial effects.
- Compare providers by declared capabilities and degraded paths; do not score silent adapter substitutions as equivalent behavior.
- A completed unload callback does not prove that in-flight work stopped, and a runtime rollback does not prove that external effects were reversed.
- Evaluate multi-agent behavior only when delegation is part of the frozen system and justified by the workload.

## Evidence Surface And Stop Gate

Work sampled-first: use the cheapest representative scenario slice and direct
oracles before expanding coverage. Create persistent evaluation-plan and
run-result artifacts only for a repeated campaign, release gate, or durable
independent review with a named downstream consumer. Report a bounded incident
or sampled ablation inline with direct evidence when no such consumer exists.

Once external evidence establishes the requested outcome and no named
unresolved risk threatens it, latch terminal success and stop. Productization,
continuous monitoring, or a broader release campaign requires renewed scope.

## Evaluation Workflow

1. **State a falsifiable claim.** Define the behavior under test, population and workload, metric, threshold, allowed regressions, counterfactual, cheapest discriminator, and stop rule. Mark plan-only work as a plan, not a successful run.
2. **Freeze the complete system tuple.** Record harness revision and active runtime generation; configuration and component digests; provider, model, and sampling configuration; prompts and skills; tool schemas and fixtures; policy, permissions, approvals, and sandbox; context, memory, checkpoint, and compaction settings; budgets, timeouts, retries, cancellation, and delegation; environment and dependency versions; scenario corpus; and evaluator/oracle versions.
3. **Build the scenario suite.** Include happy path, stateful multi-step work, policy denial, tool errors and malformed results, timeouts, context pressure, restart from checkpoint, cancellation, untrusted input or prompt injection, and at least one noncoding workload. Add duplicate delivery and partial-effect cases when side effects exist. When runtime reconfiguration is claimed, also inject invalid candidates, capability loss, partial initialization, concurrent old/new runs, late results, post-activation failure, stale rollback racing a newer activation, external effects before failed health, and isolation leakage.
4. **Define oracles before trials.** Prefer deterministic post-state assertions plus event and policy invariants. When determinism is impossible, use a documented procedure or blinded human rubric. Use an LLM judge only as a secondary signal, with calibration cases and judge disagreement reported.
5. **Sample before scaling.** Run the smallest representative slice that can falsify the claim. For a justified repeated campaign, predeclare trial count, seeds or sampling controls, order, warm/cold state, and retry treatment. Report single-trial pass rate, `pass@k` (at least one success) and `pass^k` (all trials succeed) separately. If trials are dependent, report empirical grouped rates and do not apply independence formulas as facts.
6. **Capture causal traces.** Preserve typed state transitions, event and correlation IDs, capability negotiation, runtime-generation bindings and lifecycle, tool requests/results, policy decisions, checkpoints, budgets, timings, cancellation, recovery, and terminal reason. Redact secrets and personal data with a versioned rule while retaining stable hashes and causal structure.
7. **Use paired ablations.** Compare baseline and candidate on matched scenarios and trial controls. Change one named factor at a time where feasible; otherwise disclose the confounder. Separate quality, reliability, safety, latency, and cost effects.
8. **Attribute failures conservatively.** Classify evidence as model, harness control, provider adapter, tool, policy, context/memory, persistence/recovery, evaluator, infrastructure, or unknown. Do not assign root cause from the final answer alone.
9. **Apply release gates.** Enforce predeclared thresholds for task correctness, invariant violations, policy bypass, restart/cancel behavior, reliability, latency, and cost. When reconfiguration is claimed, bind every required fault class to declared injections and oracles, then require zero generation evidence gaps or misbindings, partial activation, unauthorized capability change, stale rollback overwrite, false rollback success, external-effect misreporting, and isolation leakage. Block release on critical safety regressions, invalid traces, incomplete required scenarios, or unexplained baseline regressions.

## Adjacent Routes

- Use `agent-harness-engineering` when the primary deliverable is a harness design or implementation change rather than empirical evidence.
- Use `architecture-intelligence` for broader architecture fitness, topology, or conformance questions outside harness behavior.
- Use `context-density` to measure and redesign context placement or compression; use this skill to evaluate its end-to-end harness impact.
- Use `scientific-research` for scholarly surveys, literature review, or evidence synthesis.
- Use `codex-cli` or `claude-code` for vendor-specific commands, configuration, logs, hooks, or session diagnostics.
- Use `capability-synthesizer` for broad external-first discovery and synthesis of evaluation skills, plugins, datasets, or public implementations.

## Conditional Evaluation Artifacts And Gate

When the persistent-artifact gate above is satisfied, produce an evaluation
plan with `schema: agent_harness.evaluation_plan.v1` as defined in
`$PLUGIN_ROOT/references/agent-harness-contracts.md`; name its downstream
consumer and acceptance action. Use its optional `runtime_reconfiguration`
claim only when the conditional scenarios, resolving injection/oracle bindings,
and zero gates are present. After execution, produce one or more results with
`schema: agent_harness.run_result.v1`, or `schema:
agent_harness.run_result.v2` when the result supports a reconfiguration claim;
each result links the frozen system tuple and scenario to outcomes, trace
evidence, failure attribution, usage, and artifact versions. V2 also binds
design, evaluation, activation, admitted and terminal generations, traces,
effects, and any explicit migration receipt. Aggregate those results into the
plan's metrics, ablations, uncertainty, and release-gate verdict. Never upgrade
a plan into a run result without recorded trials.

Validate each warranted final artifact:

```bash
python3 "$PLUGIN_ROOT/scripts/harness/validate_harness_artifact.py" <artifact-path> --json
```

Treat a nonzero result as a blocker. Validation proves required artifact structure and selected cross-field invariants, not claim truth; retained traces and oracle evidence must support the verdict.
