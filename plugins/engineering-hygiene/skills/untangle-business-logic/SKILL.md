---
name: untangle-business-logic
description: "Targeted refactoring workflow for tangled business logic in code. Use when working on code where business rules, UI/presentation, API/IO, persistence, platform quirks, concurrency, lifecycle, state transitions, or error policy are mixed together; when the same domain rule is implemented in several places; when a bug depends on event ordering or stale state; or when a feature works but the business meaning is spread across components/services. Complements code-maintenance-audit: this skill is for semantic logic boundaries, hidden invariants, duplicated business meaning, and behavior-preserving logic untangling, not generic dead-code cleanup or performance tuning."
---

# Untangle Business Logic

Make code easier to reason about from the business-logic side. The goal is not to "clean up" style, but to separate domain decisions from UI, IO, platform workarounds, lifecycle, concurrency, config, and error presentation while preserving user-visible behavior and public contracts.

## Operating Rule

When a task touches business behavior or a bug smells like tangled responsibility, run a narrow logic-boundary sweep before completion:

1. Baseline behavior: identify the user-visible behavior, public API, persisted data shape, and tests that must not change.
2. Map domain meaning: list the domain facts, rules, states, transitions, and error cases involved in the touched code.
3. Find tangles: mark where business decisions are mixed with UI/API/IO/platform/concurrency/config/error-policy code. Use the tangle catalog in `$PLUGIN_ROOT/references/tangle-catalog.md`: wrong-layer rules, duplicated business meaning, hidden invariants, temporal coupling, split state ownership, error-policy drift, platform workaround leakage, and semantic enum/model drift.
4. Choose one hotspot: refactor the smallest area that materially improves clarity with low behavior risk. Expand to two or three only when they are tightly connected.
5. Anchor behavior: add or run characterization tests before moving logic when behavior could drift.
6. Untangle locally: centralize duplicated rules, make invariants explicit, isolate adapters/workarounds, or create a single state/error transition point. Pick only the moves that directly fit the hotspot from the moves catalog in `$PLUGIN_ROOT/references/tangle-catalog.md`.
7. Verify: run the relevant build, typecheck, lint, and tests.

Do not perform a full architecture rewrite. Prefer a small behavior-preserving refactor over a broad abstract design. Reuse an existing domain helper before creating a new one.

## Action Policy

Apply the refactor immediately when all are true:

- The hotspot is inside the changed surface or directly explains the bug/feature being worked on.
- Current behavior can be characterized by tests, existing call sites, repository docs, fixtures, or clear code evidence.
- The refactor reduces mixed responsibility or duplicated domain meaning without broad public API churn.
- Verification can be run or the residual risk can be stated precisely.

Report instead of editing when any are true:

- The change would alter business behavior but the intended behavior is unclear.
- The logic is public API, persisted data, migration-sensitive, or used by external consumers.
- The fix requires a multi-module architecture migration.
- Dynamic wiring, reflection, generated code, or runtime configuration prevents confident usage analysis.
- The code is unrelated user-owned work in a dirty tree.

If a behavior change is clearly a bug fix, label it explicitly as `behavioral change`, explain why the old behavior was wrong, and cover it with tests.

## Relationship To Code Maintenance Audit

- Use the sibling skill `code-maintenance-audit` for mechanical cleanup: dead code, unused symbols, stale files, and simple duplication.
- Use this skill when duplication is semantic: two places encode the same business rule, state transition, error policy, or domain invariant.
- Use this skill after code maintenance if cleanup reveals that the remaining complexity is caused by misplaced business meaning rather than leftover code.

## Output Format

At the end of work, include a compact logic-boundary block when this skill influenced the change:

```markdown
Business logic audit:
- Hotspot: files/symbols and business concept checked.
- Tangle found: mixed layers, hidden invariant, duplicated rule, state race, error-policy drift, or "none".
- Change made: extracted/centralized/isolated/guarded, or "reported only".
- Behavior: preserved / behavioral change, with evidence.
- Deferred findings: broader untangling worth doing later.
- Verification: commands run and result, or what could not be checked.
```

If no refactor is made, state the hotspot and evidence checked instead of writing a generic "logic is fine".
