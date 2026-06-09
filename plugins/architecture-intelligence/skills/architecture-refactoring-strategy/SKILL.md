---
name: architecture-refactoring-strategy
description: "Use when code changes need staged structural design: boundary extraction, modularization, dependency inversion, migrations, anti-corruption layers, tests, rollout gates, and rollback."
---

# Architecture Refactoring Strategy

Use when improving architecture needs staged code change rather than a one-shot rewrite.

## Inputs

Gather current architecture map, hot paths, structure metrics, runtime topology, ownership topology, target quality attribute, constraints, tests, production signals, failure history, ADRs, and architecture principles.

For architecture-significant structural changes, require a baseline before code edits:
dirty-tree state, observed boundary evidence, pre-refactor probe or explicit
reason it was skipped, representative change/runtime scenario, and the focused
skills used from the router.

## Patterns

Use the smallest safe pattern:

- characterization tests before moving behavior;
- branch by abstraction behind stable interface;
- strangler fig for extracting flows;
- anti-corruption layer for old model or external API coupling;
- facade/adapter to stabilize callers;
- parallel run, shadow read, dual write for data migration risk;
- feature flag or compatibility window for reversibility;
- expand-contract migration for schema/API changes.

## Multi-Objective Frame

For every refactor name:

- primary quality attribute to improve;
- secondary attributes that must not regress;
- accepted tradeoff and threshold;
- evidence signal before and after each slice.

Do not recommend a pattern without the measurable quality attribute it improves.

## Slicing

Prefer one validated slice at a time: user flow, bounded-context seam, data ownership edge, dependency cycle, package boundary, ownership boundary, cross-owned dependency edge, runtime dependency, deployment boundary.

Avoid platform rewrites that do not reduce a named risk in the next increment.

## Plan Format

Return:

1. Current architecture risk.
2. Target boundary or quality attribute.
3. Migration slices in order.
4. Guardrails and fitness functions.
5. Tests and observability before each slice.
6. Rollback path and stop conditions.
7. ADRs to create/update.
8. Quality-attribute tradeoffs accepted.

Keep behavior-preserving moves separate from behavior changes. Lock public interfaces before moving internals. Treat data ownership changes as release/operations work.

## Proof Bundle

After implementation, report:

- architecture boundary moved or protected;
- before/after evidence, including post-probe when static structure was used;
- guardrail tests or fitness functions added;
- docs/ADR updated or explicit reason none was needed;
- runtime smoke, release gate, or explicit skip reason;
- dirty-tree separation for pre-existing changes;
- specialized architecture skills used and skipped with reasons.

Use `architecture_intelligence.refactor_report.v1` when the result should be saved or reviewed later.
