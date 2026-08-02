# Engineering Hygiene

Engineering Hygiene is a plugin pack of discipline gates for everyday development work. Each skill guards a specific moment where agents habitually cut corners: claiming code done without a cleanup sweep, "refactoring" style while leaving business meaning tangled, calling UI verified from a single glance, or reporting a missing tool as the final answer.

Core stance:

- Evidence before claims: every audit block cites searches, tool runs, or screenshots, never generic "looks good" / "no dead code" statements.
- Stay inside the touched surface: cleanup and refactors apply only where the current task creates them; broader debt is reported, not silently rewritten.
- Preserve behavior and ownership: dirty-worktree changes you did not make are never deleted, and behavior changes are labeled and tested.
- Finish end to end: missing SDKs, CLIs, simulators, and test utilities get provisioned and verified instead of downgrading the task.

Skills (no router: the four gates trigger in disjoint situations and route themselves through their descriptions):

- `code-maintenance-audit` — mechanical maintenance sweep over changed and adjacent code: dead code, stale leftovers, safe consolidation, proof pass.
- `untangle-business-logic` — behavior-preserving separation of domain rules from UI, IO, platform quirks, concurrency, lifecycle, and error policy.
- `ui-visual-audit` — skeptical visual QA of rendered UI and screenshots, with a forced ambient pass beyond the acceptance criteria.
- `provisioning-missing-tools` — install and verify missing toolchains instead of stopping at "this environment lacks X".

Division of labor: `code-maintenance-audit` handles mechanical duplication and dead code; `untangle-business-logic` handles semantic duplication and misplaced business meaning. `ui-visual-audit` produces the visual evidence; `provisioning-missing-tools` guarantees the capture and verification tooling exists to produce it.

References:

- `references/maintenance-checklist.md` — full sweep target inventory and consolidation criteria.
- `references/tangle-catalog.md` — tangle taxonomy and the catalog of behavior-preserving refactoring moves.
- `references/visual-suspicion-checklist.md` — ambient-pass checklist for visual defects by category.
