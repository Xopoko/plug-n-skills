# Architecture Intelligence

Architecture Intelligence is a source-backed software architecture plugin for
audits, ADRs, fitness functions, ownership/runtime topology, conformance checks,
structure metrics, async state consistency, and incremental refactoring.

It focuses on architecture qualities in code:

- boundaries, dependency direction, cycles, domain/data ownership;
- CODEOWNERS/OWNERS coverage and cross-owned coordination risk;
- runtime topology, deployment, observability, resilience, integration style;
- async state lifecycle, invalidation, replay, cache, caller outcomes, and race proof;
- ADRs, documentation drift, fitness functions, CI guardrails;
- fan-in, fan-out, instability, migration slices, rollout gates, rollback paths.

## Skills

- `architecture-intelligence`: router and operating stance.
- `codebase-architecture-audit`: source-backed architecture audit.
- `architecture-conformance`: intended-vs-observed architecture checks.
- `architecture-ownership-topology`: ownership coverage and coordination risk.
- `architecture-runtime-topology`: runtime/deployment/operability architecture.
- `async-state-consistency`: async lifecycle, invalidation, replay, publication, and race consistency.
- `architecture-decisions`: ADR creation and review.
- `architecture-fitness-functions`: architecture tests and guardrails.
- `architecture-refactoring-strategy`: incremental architecture migration plans.

## Scripts

Collect conservative architecture facts:

```bash
python3 scripts/architecture_probe.py /path/to/repo --json
python3 scripts/architecture_probe.py /path/to/repo --json --git-history
python3 scripts/architecture_probe.py /path/to/repo --json --policy policy.json
```

Validate durable JSON outputs:

```bash
python3 scripts/validate_architecture_intelligence.py output.json
```

The probe is evidence collection only. JSON includes structure metrics,
runtime topology, ownership topology, optional git history, and optional policy
checks. These are warning signals, not automatic findings; runtime output avoids
secret values and ownership output does not infer actual team communication.

## Large Refactor Proof

For architecture-significant work, trigger from task context and code evidence.
Use the router's minimum chain when code work creates, preserves, or materially
changes system structure: audit, refactoring strategy, and fitness functions,
with conformance, runtime topology, and ownership topology added when source
evidence calls for them. Durable handoff should use
`architecture_intelligence.refactor_report.v1` so the before/after evidence,
skill usage, dirty-tree state, validation, docs, runtime proof, and residual
risks remain reviewable after the Codex session.
