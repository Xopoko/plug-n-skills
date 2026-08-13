---
name: architecture-refactoring-strategy
description: "Architecture refactoring strategy plans and executes incremental code-boundary changes with characterization tests, per-slice proof, fitness functions, rollback, and before/after evidence; excludes routine cleanup and agent-runtime design."
---

# Architecture Refactoring Strategy

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use when improving the architecture of the application or library code needs
staged implementation rather than a one-shot rewrite. Module boundaries,
layers, dependency direction, APIs, domain/data ownership, extension points,
and runtime coupling are the subject. Coding agents are tools, not the
architecture being designed.

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

## AI-Assisted Code Architecture

Use `$PLUGIN_ROOT/references/ai-assisted-code-architecture.md` when Codex,
Claude Code, or another coding agent helps recover, design, implement, or
review the code architecture.

1. Classify the change and recover explicit intent separately from observed
   source conventions.
2. Map components, public seams, dependency edges, callers, implementations,
   importers, and downstream consumers affected by the proposed change.
3. Compare design options against source-grounded axes and name
   plausible-but-wrong paths before choosing a slice.
4. Implement one smallest behavior-preserving architecture slice.
5. Separate requested behavior from incidental refactoring; defer unrelated
   cleanup.
6. Run functional proof and architecture proof, then inspect the actual diff
   and before/after boundary evidence.
7. Produce independent review findings before mutation, apply accepted fixes
   in a separate pass, and rerun the affected proof.

Human- and agent-authored patches face the same architecture method. Stop on
an unexplained failure, unexpected file, new dependency direction, public API
drift, or unplanned scope expansion.

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
