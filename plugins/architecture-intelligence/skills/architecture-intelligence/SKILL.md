---
name: architecture-intelligence
description: "Use whenever code work has structural consequences: project architecture, module boundaries, dependency direction, runtime topology, ownership, ADRs, fitness functions, or architecture refactoring."
---

# Architecture Intelligence

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use for architecture quality in code. Trigger from task context and code
evidence: designing a new project or feature, choosing structure, changing
boundaries, moving behavior between layers, introducing runtime/integration
paths, protecting quality attributes, or reviewing code whose shape affects
changeability, reliability, scalability, security, operability, or testability.

## Evidence First

Before judging:

1. Define system boundary, users/workloads, and the delivery constraint.
2. Inspect source evidence: repo guidance, README, manifests, tests, ownership files, architecture docs, ADRs, dependency graph, runtime boundaries, and recent changes.
3. Name quality attributes under pressure: modifiability, reliability, scalability, performance, security, observability, testability, cost, operability.
4. Frame key scenarios: stimulus, environment, response, response measure.
5. Separate observed, inferred, assumed, and unknown.

If context is thin, inspect source first or ask one decision-critical question. Do not invent scale, teams, boundaries, compliance, or domain facts.

## Probe

From the plugin root:

```bash
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json --git-history
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json --policy <policy.json>
```

Probe output is an evidence map, not a verdict. It includes:

- structure metrics: fan-in/fan-out, instability, dependency cycles;
- runtime topology: deployment/config/observability/resilience/integration signals;
- ownership topology: CODEOWNERS/OWNERS sources, owner coverage, ownerless areas, cross-owned static dependency edges;
- git history when requested: churn and co-change signals;
- policy checks when provided: forbidden/required top-level edges and required docs.

## Route

Use the smallest focused skill set:

- `codebase-architecture-audit`: current architecture, risks, scorecards.
- `architecture-conformance`: intended vs observed rules, drift, erosion.
- `architecture-ownership-topology`: CODEOWNERS/OWNERS, ownership coverage, cross-owned coordination risk, governance paths.
- `architecture-runtime-topology`: deployment, runtime calls, observability, resilience, operability.
- `architecture-decisions`: ADR creation/review, tradeoffs, owner, revisit trigger.
- `architecture-fitness-functions`: executable guardrails, CI checks, review gates.
- `architecture-refactoring-strategy`: incremental migration, blast radius, rollback.

When the current work will create, preserve, or materially change architecture,
do not stop at the router. Use this minimum chain:

1. `codebase-architecture-audit` for observed architecture and risks.
2. `architecture-refactoring-strategy` for target boundary, slices, rollback.
3. `architecture-fitness-functions` for executable guardrails.

Add `architecture-conformance` when an architecture doc, ADR, policy, or
explicit constraint exists. Add `architecture-runtime-topology` when CLI, app
refresh, background work, deployment, integration, or operability paths change.
Add `architecture-ownership-topology` when owner files, package ownership, or
cross-owned dependencies affect the change.

Use adjacent plugins for UI/UX, game design, Kotlin/Tauri specifics, security threat modeling, or non-architecture cleanup.

## Evidence Rules

- Tie every finding to files, commands, docs, traces, dependency relations, tests, or decisions.
- Explain tradeoffs; architecture changes rarely improve every quality attribute.
- Recommendations need validation plus rollback or revisit trigger.
- Treat metrics, ownership files, and co-change as warning signals. Confirm against intent, scenarios, runtime evidence, and domain context.
- Do not infer team health, communication quality, production behavior, or branch-protection enforcement from repository files alone.

## Refactor Proof Gate

Before editing, capture dirty-tree state, the target boundary, and a pre-refactor
probe when the repo can be scanned. After editing, provide tests, docs/ADR
updates, runtime smoke or an explicit skip reason, and a post-probe comparison
when structural metrics informed the change. End with a skill-usage self-check:
skills used, specialized skills skipped, and the reason each skip was safe.

For durable handoff, emit `architecture_intelligence.refactor_report.v1`.

## Durable Contracts

Use `references/contracts.md` for:

- `architecture_intelligence.audit.v1`
- `architecture_intelligence.conformance.v1`
- `architecture_intelligence.decision.v1`
- `architecture_intelligence.fitness_plan.v1`
- `architecture_intelligence.refactor_report.v1`
- `architecture_intelligence.runtime_topology.v1`
- `architecture_intelligence.structure_metrics.v1`
- `architecture_intelligence.ownership_topology.v1`

## Boundaries

Do not approve high-risk architecture changes without validation.
Do not prescribe microservices, event sourcing, DDD, clean/hexagonal architecture, or new tooling by default.
Optimize codebase changeability and runtime qualities, not diagram polish.
