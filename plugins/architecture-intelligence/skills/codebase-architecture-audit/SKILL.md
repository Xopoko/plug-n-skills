---
name: codebase-architecture-audit
description: "Use before architecture-significant code work to recover the actual source-backed system shape: modules, dependencies, domain seams, runtime coupling, ownership, quality attributes, tests, docs, and risks."
---

# Codebase Architecture Audit

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory. Works under any host agent, including Codex, Claude, and Cursor.

Use to inspect the architecture that exists in code, not the architecture people intend it to have.

## Inputs

Gather repository guidance, product/domain context, top-level structure, entry points, manifests, ownership files, architecture docs, ADRs, API contracts, schemas, runtime/deployment evidence, tests, observability hooks, and recent changes.

Run the probe when useful:

```bash
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json --git-history
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json --policy <policy.json>
```

## Lenses

- System shape: monolith, modular monolith, service system, plugin, app/backend, library, CLI, data pipeline, mixed.
- Boundaries: module purpose, public APIs, ownership, dependency direction, leakage.
- Domain/data: bounded contexts, language, data ownership, transaction boundaries, anti-corruption layers.
- Coupling/cohesion: cycles, hubs, framework bleed, shared mutable state, duplicated domain rules, change amplification.
- Structure metrics: fan-in/out, instability, dependency cycles, co-change hotspots, intent fit.
- Ownership topology: CODEOWNERS/OWNERS, ownerless areas, cross-owned dependencies, review paths.
- Runtime: sync/async paths, queues, jobs, caches, persistence, external services, deployment topology, failure modes.
- Quality attributes: maintainability, modifiability, reliability, scalability, security, observability, performance, testability, cost.
- Validation: unit/integration/contract/architecture tests, migration tests, operational signals.
- Decisions: ADRs, diagrams, owners, tradeoffs, expiry/revisit triggers, drift.

## Scenario Frame

For major findings capture stimulus, environment, desired response, response measure, quality attribute, and tradeoff. If no scenario or quality attribute is affected, keep it as an investigation note.

## Debt Terms

- `smell`: structural warning such as cycles, hubs, shotgun surgery, unstable dependencies.
- `debt`: accepted or accidental shortcut with carrying cost and repayment path.
- `erosion`: drift from intended architecture or decisions.
- `inconsistency`: violation of documented rule, constraint, or ADR.
- `knowledge-gap`: missing rationale, owner, or decision history.

Severity: `P0` production/data/security/release failure, `P1` high-cost architecture blocker, `P2` meaningful debt, `P3` local gap or low-risk cleanup.

## Workflow

1. Build source map with evidence and unknowns.
2. Identify the actual architecture style.
3. Compare source, ownership, domain, and runtime boundaries.
4. Trace one or two representative change paths.
5. Use metrics/history to prioritize inspection, not replace judgment.
6. Score by severity, propagation risk, reversibility, business impact, confidence.
7. Recommend focused actions with validation signals.

For architecture-significant implementation work, hand the audit forward into a proof-oriented chain:
refactoring strategy, fitness functions, conformance when intent exists, runtime
topology when runtime paths change, and ownership topology when owner boundaries
matter. Record which specialized skills were used or safely skipped.

## Output

Compact: architecture summary, evidence inspected, risks by severity, next actions, validation gaps.

Durable: use `architecture_intelligence.audit.v1`; use `structure_metrics.v1`, `runtime_topology.v1`, or `ownership_topology.v1` when the main artifact is that evidence snapshot.

Do not turn taste preferences into findings. Require source evidence and concrete effect on changeability, reliability, scalability, security, operability, or delivery.
