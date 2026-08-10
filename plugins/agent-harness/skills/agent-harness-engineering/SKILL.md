---
name: agent-harness-engineering
description: Design LLM agent harnesses with typed control loops, tools/state, context/memory, policy, cancellation, recovery, and delegation. Excludes prompt-only, generic app architecture, vendor CLI/config, evaluation-only work, and skill creation.
---

# Agent Harness Engineering

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Build a vendor-neutral control plane around an LLM. The harness, not generated text, owns state transitions, authority, resource limits, and recovery.

Read `$PLUGIN_ROOT/references/agent-harness-contracts.md` for the artifact and runtime contracts. Read `$PLUGIN_ROOT/references/agent-harness-patterns.md` before selecting control, persistence, or delegation mechanisms. Use `$PLUGIN_ROOT/references/agent-harness-landscape.md` only for build-versus-adopt or provider/runtime comparisons.

## Non-Negotiable Boundaries

- Model output is an untrusted proposal, never authority to mutate state or invoke a side effect.
- A transcript is evidence, not a checkpoint. Persist explicit typed state, pending work, policy decisions, budgets, and replay position.
- Prompt or skill text is not a sandbox. Enforce permissions, approvals, isolation, and side-effect policy outside the model.
- A scanner is one signal, not a safety guarantee.
- Do not promise exactly-once execution across process or network failures. Specify at-least-once risks, idempotency keys, deduplication, and reconciliation.
- Expose provider capabilities and limitations explicitly; do not fake parity behind a lowest-common-denominator interface.
- Add multi-agent delegation only when parallelism, isolation, specialization, or independent review justifies its coordination and authority cost.

## Engineering Workflow

1. **Bind the outcome.** State the workload, desired outcome, falsifiable design hypothesis, cheapest discriminator, stop condition, non-goals, trust boundaries, and side effects. Cover the real workload; do not assume a coding agent.
2. **Define typed contracts.** Specify state, event envelope, commands, effects, tool results, errors, approval records, checkpoints, and terminal outcomes. Give every durable event an identity and schema version.
3. **Make the loop explicit.** Design a deterministic spine such as `observe -> normalize -> decide -> authorize -> execute -> record -> transition -> stop or recover`. Keep nondeterminism inside recorded provider and tool results; make transition logic replayable.
4. **Separate provider capabilities.** Model tool calling, structured output, streaming, usage accounting, cancellation, parallel calls, and provider-specific limits as negotiated capabilities. Define unsupported and degraded paths rather than silently changing semantics.
5. **Constrain tools and authority.** Validate typed arguments; attach provenance, permission scope, approval state, timeout, retry class, idempotency behavior, and result limits. Keep policy enforcement and side-effect execution outside model text.
6. **Design context and persistence.** Separate working context, durable state, episodic memory, retrieved untrusted content, and human decisions. Define compaction summaries with provenance and invalidation. Checkpoints must support restart without treating the transcript as executable state.
7. **Own lifecycle behavior.** Set turn, token, cost, time, tool, and delegation budgets. Propagate cancellation. Define retry eligibility, backoff, partial-effect reconciliation, crash recovery, leases or ownership, and terminal cleanup.
8. **Justify delegation.** If subagents exist, define their task contracts, authority ceilings, budgets, result schemas, cancellation propagation, merge policy, and parent accountability. Otherwise record why a single loop is sufficient.
9. **Plan observability and verification.** Emit typed, correlatable events for decisions, policy outcomes, effects, checkpoints, budgets, cancellation, and recovery. Redact secrets while preserving causal evidence. Hand empirical claims and release gates to `agent-harness-evaluation`.

## Adjacent Routes

- Use `architecture-intelligence` for broader application boundaries, dependency direction, runtime topology, or conformance beyond the harness.
- Use `context-density` for measured context placement or compression with commitment preservation and task validation.
- Use `scientific-research` for a scholarly literature review or evidence synthesis rather than runtime construction.
- Use `codex-cli` or `claude-code` for exact vendor commands, configuration, hooks, sessions, or host-specific troubleshooting.
- Use `capability-synthesizer` for broad external-first discovery and synthesis of reusable skills, plugins, or public implementations.
- Use `agent-harness-evaluation` for benchmarks, replay, regression diagnosis, or release evidence after a harness boundary exists.

## Design Artifact And Gate

Produce one artifact with `schema: agent_harness.design.v1` as defined in `$PLUGIN_ROOT/references/agent-harness-contracts.md`. Keep field details in that contract; the artifact must make the following reviewable without relying on prose elsewhere:

- workload and outcome contract, non-goals, trust boundaries, and side effects;
- typed states, events, control loop, invariants, and terminal conditions;
- provider capability matrix and unsupported/degraded behavior;
- tool, permission, approval, sandbox, and effect boundaries;
- context, memory, checkpoint, replay, restart, and reconciliation semantics;
- budgets, cancellation, retry/recovery, observability, and redaction;
- delegation decision and, when used, child authority and merge contracts;
- validation scenarios, unresolved risks, and handoff claims for evaluation.

Validate the final artifact:

```bash
python3 "$PLUGIN_ROOT/scripts/harness/validate_harness_artifact.py" <artifact-path> --json
```

Treat a nonzero result as a design blocker. Validation proves the required artifact structure and selected cross-field invariants, not runtime safety or empirical quality.
