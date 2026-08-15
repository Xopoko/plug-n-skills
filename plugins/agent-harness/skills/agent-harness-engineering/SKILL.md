---
name: agent-harness-engineering
description: Design agent harnesses for typed loops, runtime reconfiguration, provider/tool/module hot swap, state, policy, cancellation, recovery, and delegation. Excludes prompt-only, generic architecture, vendor CLI/config, and evaluation-only work.
---

# Agent Harness Engineering

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Build a vendor-neutral control plane around an LLM. The harness, not generated text, owns state transitions, authority, resource limits, and recovery.

Read `$PLUGIN_ROOT/references/agent-harness-contracts.md` for the artifact and runtime contracts. Read `$PLUGIN_ROOT/references/agent-harness-patterns.md` before selecting control, persistence, or delegation mechanisms. Use `$PLUGIN_ROOT/references/agent-harness-landscape.md` only for build-versus-adopt or provider/runtime comparisons.

Choose the evidence surface before producing durable harness paperwork. A
bounded diagnosis or fix may use an inline checklist plus direct tests. Create
a versioned design artifact only for a new harness, a material control-plane
revision, or a durable release or handoff claim with a named downstream
consumer.

## Non-Negotiable Boundaries

- Model output is an untrusted proposal, never authority to mutate state or invoke a side effect.
- A transcript is evidence, not a checkpoint. Persist explicit typed state, pending work, policy decisions, budgets, and replay position.
- Prompt or skill text is not a sandbox. Enforce permissions, approvals, isolation, and side-effect policy outside the model.
- A scanner is one signal, not a safety guarantee.
- Do not promise exactly-once execution across process or network failures. Specify at-least-once risks, idempotency keys, deduplication, and reconciliation.
- Expose provider capabilities and limitations explicitly; do not fake parity behind a lowest-common-denominator interface.
- Runtime rollback restores a host generation; it does not reverse external effects. Reconcile or compensate those effects under their own contracts.
- Add multi-agent delegation only when parallelism, isolation, specialization, or independent review justifies its coordination and authority cost.

## Engineering Workflow

1. **Bind the outcome.** State the workload, desired outcome, falsifiable design hypothesis, cheapest discriminator, stop condition, non-goals, trust boundaries, side effects, and intended evidence consumer. Cover the real workload; do not assume a coding agent.
2. **Define typed contracts.** Specify state, event envelope, commands, effects, tool results, errors, approval records, checkpoints, and terminal outcomes. Give every durable event an identity and schema version.
3. **Make the loop explicit.** Design a deterministic spine such as `observe -> normalize -> decide -> authorize -> execute -> record -> transition -> stop or recover`. Keep nondeterminism inside recorded provider and tool results; make transition logic replayable.
4. **Separate provider capabilities.** Model tool calling, structured output, streaming, usage accounting, cancellation, parallel calls, and provider-specific limits as negotiated capabilities. Define unsupported and degraded paths rather than silently changing semantics.
5. **Bind runtime generations.** When configuration, providers, tools, modules, or the loop may change while the host stays live, build and validate a complete candidate before activation, including provider, tool, executor, policy, context, loop, state, interfaces, and required capabilities. Publish by expected-generation CAS, atomically close old admission, bind each run and late result, separate binding from bounded retirement, and bind post-health rollback by CAS to the failed generation and activation attempt. Retain the prior generation until health, rollback, leases, and teardown are terminal. Otherwise do not claim hot swap.
6. **Constrain tools and authority.** Validate typed arguments; attach provenance, permission scope, approval state, timeout, retry class, idempotency behavior, and result limits. Keep policy enforcement and side-effect execution outside model text.
7. **Design context and persistence.** Separate working context, durable state, episodic memory, retrieved untrusted content, and human decisions. Define compaction summaries with provenance and invalidation. Checkpoints must support restart without treating the transcript as executable state.
8. **Own lifecycle behavior.** Set turn, token, cost, time, tool, and delegation budgets. Propagate cancellation. Define retry eligibility, backoff, partial-effect reconciliation, crash recovery, leases or ownership, and terminal cleanup.
9. **Justify delegation.** If subagents exist, define their task contracts, authority ceilings, budgets, result schemas, cancellation propagation, merge policy, and parent accountability. Otherwise record why a single loop is sufficient.
10. **Plan observability and verification.** Emit typed, correlatable events for decisions, policy outcomes, effects, checkpoints, budgets, cancellation, recovery, and generation changes. Redact secrets while preserving causal evidence. Hand empirical claims and release gates to `agent-harness-evaluation`.

After direct external verification shows that the requested outcome is met,
latch terminal success and stop. Continue only for a named unresolved risk that
threatens the outcome. Productization, automation, generalization, or release
work needs renewed scope.

## Adjacent Routes

- Use `architecture-intelligence` for broader application boundaries, dependency direction, runtime topology, or conformance beyond the harness.
- Use `context-density` for measured context placement or compression with commitment preservation and task validation.
- Use `scientific-research` for a scholarly literature review or evidence synthesis rather than runtime construction.
- Use `codex-cli` or `claude-code` for exact vendor commands, configuration, hooks, sessions, or host-specific troubleshooting.
- Use `capability-synthesizer` for broad external-first discovery and synthesis of reusable skills, plugins, or public implementations.
- Use `agent-harness-evaluation` for benchmarks, replay, regression diagnosis, or release evidence after a harness boundary exists.

## Conditional Design Artifact And Gate

When the artifact gate above is satisfied, produce one artifact with `schema:
agent_harness.design.v1` as defined in
`$PLUGIN_ROOT/references/agent-harness-contracts.md`. Name the downstream
consumer and its acceptance action. Keep field details in that contract; the
artifact must make the following reviewable without relying on prose elsewhere:

- workload and outcome contract, non-goals, trust boundaries, and side effects;
- typed states, events, control loop, invariants, and terminal conditions;
- provider capability matrix and unsupported/degraded behavior;
- optional `runtime_reconfiguration` decision and, when claimed, snapshot,
  activation, run-binding, drain, isolation, rollback, and evidence contracts;
- tool, permission, approval, sandbox, and effect boundaries;
- context, memory, checkpoint, replay, restart, and reconciliation semantics;
- budgets, cancellation, retry/recovery, observability, and redaction;
- delegation decision and, when used, child authority and merge contracts;
- validation scenarios, unresolved risks, and handoff claims for evaluation.

Validate a warranted final artifact:

```bash
python3 "$PLUGIN_ROOT/scripts/harness/validate_harness_artifact.py" <artifact-path> --json
```

Treat a nonzero result as a design blocker. Validation proves the required artifact structure and selected cross-field invariants, not runtime safety or empirical quality.
