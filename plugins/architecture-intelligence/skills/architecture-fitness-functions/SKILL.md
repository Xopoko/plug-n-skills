---
name: architecture-fitness-functions
description: "Architecture fitness functions turn intended boundaries into dependency rules, cycle checks, ownership gates, ADR conformance, runtime/resilience checks, and staged CI enforcement."
---

# Architecture Fitness Functions

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use when architecture quality should become observable, testable, or CI-enforced.

## Rule Shape

Each rule needs: intent, scope, owner, signal, mechanism, pass condition, cadence, failure action, exception path, related ADR/principle, protected quality attribute, and tradeoff.

Cadence: `local`, `pre-commit`, `ci`, `release`, `scheduled`, `production`.

Rollout: `measure -> warn -> enforce` for legacy systems.

## Common Guardrails

- Dependency direction: domain, UI, adapters, shared packages, and apps import only allowed layers.
- Cycle prevention: package, namespace, module, service, or workspace cycles.
- Boundary API: imports only through public entry points.
- Data ownership: one bounded context owns writes for a table/topic/entity family.
- Runtime coupling: sync calls, queues, cache, external APIs follow approved directions.
- Observability/resilience: critical flows expose logs/metrics/traces/health checks and timeout/retry/fallback/idempotency policies.
- Deployment safety: migration order, feature flags, rollback readiness, compatibility windows.
- Documentation drift: architecture-changing code links ADRs, diagrams, ownership docs.
- Ownership topology: architecture-significant paths have owner coverage; cross-owned changes request both owner paths or documented waiver.
- Change amplification: co-change hotspots or touched-file width stay below agreed thresholds.
- Conformance/metrics: forbidden edges stay absent, required edges/docs exist, cycles stay absent, high fan-out requires review.

## Tooling Preference

Prefer existing project tools; add dependencies only when the boundary is important and cost is explicit.

Examples: ArchUnit/jQAssistant, NetArchTest/NDepend, dependency-cruiser/eslint/Nx graph, import-linter/pytest checks, `go list`, cargo metadata/clippy, SwiftPM target graph/XCTest.

Lightweight start:

```bash
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json --policy <policy.json>
```

The probe covers top-level coupling, instability, cycles, runtime signals, ownership topology, and simple policy checks.

## AI-Produced Change Gate

For code produced or refactored with a coding agent, combine functional proof
with at least one architecture-specific signal for every architecture claim.
Examples: public-entry-point imports, forbidden edges, cycle absence, API
compatibility, ownership, cross-module consumers, runtime dependency, or an
ADR/policy relation. A green unit test does not prove module, layer, or
dependency conformance.

Derive the rule from explicit intent when possible. If only source convention
exists, start in `measure` or `warn` mode and avoid calling deviation a
violation. See `$PLUGIN_ROOT/references/ai-assisted-code-architecture.md` for
the source-grounded review axes and per-slice proof loop.

## Workflow

1. State architecture principle in one sentence.
2. Pick the smallest measurable signal.
3. Choose cheapest existing mechanism.
4. Name protected quality attribute and tradeoff.
5. Define pass/fail threshold and exception policy.
6. Tie to ADR/rule and rollout mode.

## Output

Use `architecture_intelligence.fitness_plan.v1` or a compact table: Rule, Signal, Tool, Pass condition, Cadence, Owner.

Do not create brittle gates that block delivery without migration path.
