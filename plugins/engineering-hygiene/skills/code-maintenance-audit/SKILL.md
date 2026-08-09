---
name: code-maintenance-audit
description: >-
  Changed-code audits find dead or unused symbols, stale leftovers, duplicate
  logic, obsolete tests, and consolidation before completion. Not for
  speculative architecture, style churn, or performance optimization unless
  explicitly requested.
---

# Code Maintenance Audit

Avoid code tunnel vision after implementation. Treat every code change as a chance to clean up directly affected dead code, stale leftovers, and needless duplication without turning the task into an uncontrolled refactor.

## Operating Rule

Before claiming a code task is done, perform a maintenance sweep over the changed files and their immediate dependency neighborhood:

1. Scope pass: list the changed files, touched symbols, and direct callers/callees or imports/exports.
2. Dead-code pass: remove code made unused, unreachable, or obsolete by the current change when it is safe to prove.
3. Consolidation pass: look for near-duplicate components, classes, functions, branches, or test fixtures adjacent to the work.
4. Proof pass: run the existing relevant typecheck, lint, unit tests, build, or repository-specific verification.

Do not expand into broad architecture work unless the user requested it or the low-risk cleanup is clearly inside the touched surface.

Walk the full target inventory in `$PLUGIN_ROOT/references/maintenance-checklist.md`: unused symbols, replaced branches/flags/adapters, near-duplicate implementations, dead files after renames, debug leftovers, and repeated logic expressible through an existing local helper.

## Evidence Standard

- Use `rg` first for symbol references, imports, string identifiers, routes, feature flags, config keys, and test names.
- Prefer repo-native tools when present: compiler/typecheck, linter, dead-code checker, dependency checker, build graph, test runner, snapshot verification, or IDE/project warnings.
- Check dynamic access before deletion: reflection, serialization names, dependency injection, runtime selectors, routes, exported public APIs, localization keys, generated code, config files, and external package entry points.
- For public APIs or cross-module symbols, prove no external consumers or keep the change as a reported finding instead of deleting.
- Treat "search found nothing" as insufficient when the codebase uses dynamic registration or generated wiring.

## Action Policy

Apply the cleanup immediately when all are true:

- It is in a changed file, adjacent file, or symbol directly made obsolete by the current task.
- The code is proven unused, unreachable, duplicated, or replaced.
- The edit reduces net complexity and preserves behavior.
- Existing verification can be run, or the risk is small enough to state clearly.

Report instead of editing when any are true:

- The cleanup touches broad architecture, public contracts, migrations, generated files, or many unrelated call sites.
- The evidence depends on uncertain dynamic usage.
- The abstraction would be created for only one caller or makes names/flow less obvious.
- Tests are missing and the behavior is not trivially preserved.
- The code looks like user-owned unrelated work in a dirty tree.

## Consolidation Guardrail

Consolidate similar code only when the shared shape is real and the change deletes more complexity than it adds; the full criteria are in `$PLUGIN_ROOT/references/maintenance-checklist.md`. Do not create a generic component, helper, base class, protocol, hook, or utility just because two files look visually similar. Prefer duplication over a vague abstraction that hides important differences.

## Dirty Worktree Guard

Never delete or rewrite unrelated changes you did not make. If the worktree is dirty, separate:

- Cleanup caused by the current task: safe to apply with evidence.
- Existing unrelated debt: report as a finding.
- Unknown ownership: ask or leave it alone.

## Handoff To Untangle Business Logic

This sweep is mechanical: dead code, unused symbols, stale files, simple duplication. When the duplication is semantic — the same business rule, state transition, error policy, or domain invariant implemented in several places — or when cleanup reveals that the remaining complexity comes from misplaced business meaning, hand off to the sibling skill `untangle-business-logic` instead of forcing a mechanical consolidation.

## Output Format

At the end of code work, include a compact maintenance audit block:

```markdown
Code maintenance audit:
- Changed surface: files/symbols checked.
- Removed leftovers: dead code, stale branches, duplicate code, or "none found".
- Consolidation checked: reused/extracted/rejected with reason.
- Deferred findings: broader cleanup worth doing later, with evidence.
- Verification: commands run and result, or what could not be checked.
```

If no cleanup is made, state what was checked. Avoid a generic "no dead code" claim without the search/tool evidence that supports it.
