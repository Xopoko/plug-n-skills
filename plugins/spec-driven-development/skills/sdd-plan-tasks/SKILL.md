---
name: sdd-plan-tasks
description: Convert approved SDD specs into technical plans, design artifacts, contracts, quickstart validation, and traceable task lists.
---

# SDD Plan And Tasks

Use after a spec is drafted/approved and the next step is design, planning, tasking, or implementation prep.

## Inputs

Load only needed artifacts: spec/requirements, constitution/steering/project context, architecture docs, brownfield code patterns, prior research/contracts/quickstart.

## Plan Must Include

- behavior summary; risk/evidence profile: `basic`, `standard`, `strict`, or `regulated`
- technical context, constraints, decisions, rationale, alternatives
- architecture/components; data/state model; contracts when relevant
- error handling, migration, security/privacy/performance/accessibility when relevant
- quickstart or validation scenarios
- traceability graph: requirement ID -> scenario -> decision -> task ID -> verification/evidence -> changed path
- LLM-use limits for generated code, privacy/memorization, proprietary code, credentials, or regulated data

Preserve Spec Kit layout when present: `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`. Preserve Kiro `design.md`. Use diagrams only for real boundaries.

## Tasks Must Include

- stable task IDs; requirement/story links; known file paths
- explicit dependencies; foundation tasks block dependent story work; parallel markers only for independent files/work
- verification step plus expected evidence artifact/command per task or small group
- bounded implementation surface and boundary notes for multi-component/long-running work

Avoid tasks like "implement feature" or "update tests" without path, expected behavior, and validation command.

## Brownfield Gap Pass

1. Search existing implementation, naming, tests, integration points.
2. Prefer extension over duplication; record options/trade-offs.
3. Mark implementation-time unknowns.
4. Save in `research.md` or equivalent.

## Gate

PowerShell: use `$env:PLUGIN_ROOT` for `$PLUGIN_ROOT` command paths.

```bash
python3 "$PLUGIN_ROOT/scripts/sdd_traceability_check.py" <repo> --json
```

Resolve `FAIL` before implementation or record why proceeding is acceptable. Do not proceed if core artifacts are missing. For `strict`/`regulated`, create or identify `evidence.md`, `validation.md`, `proof.md`, or equivalent before tasks can be completed. LLM self-review/model confidence is not verification.

## Done

Design satisfies the spec; every buildable requirement has tasks or deferral; tasks have dependency order, parallel boundaries, verification; traceability/evidence are audit-ready.
