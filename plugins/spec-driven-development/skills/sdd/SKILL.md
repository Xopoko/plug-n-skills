---
name: sdd
description: Route Spec-Driven Development work across lightweight, Spec Kit, Kiro-style, OpenSpec-style, brownfield, bugfix, planning, implementation, and audit lanes.
---

# SDD Router

Use first for Spec-Driven Development, Spec Kit, specs, requirements, design docs, task breakdown, Kiro-style work, implementation from a spec, or ambiguous planning-to-code work.

## Contract

Pick the smallest lane that preserves intent, traceability, and proof. Tiny work stays light; ambiguous, risky, cross-boundary, orchestration, or LLM-heavy work cannot jump straight to code.

PowerShell: use `$env:PLUGIN_ROOT` for `$PLUGIN_ROOT` command paths.

Preflight when a repo path exists:

```bash
python3 "$PLUGIN_ROOT/scripts/sdd_surface_audit.py" <repo> --json
```

Before major edits state: `LANE`, `EVIDENCE_PROFILE`, source-of-truth paths, assumptions/open questions, next gate, and proof.

## Evidence Profiles

- `basic`: local low-risk change; one focused proof.
- `standard`: normal feature/bugfix; requirements/tasks plus reproducible check or smoke path.
- `strict`: cross-module, contract/user-visible, inferred brownfield, LLM-generated, or orchestrated work; require traceability and evidence ledgers.
- `regulated`: safety, compliance, financial, privacy, security, credentials, migrations, or high-impact data; require stronger proof, formal/model evidence when feasible, or explicit risk acceptance.

## Lanes

- `tiny-direct`: local, low-risk, clear. Use 3-line mini-spec: intent, non-goal, proof. Never use for ambiguous/cross-boundary/security/privacy work.
- `spec-kit`: `.specify/`, GitHub Spec Kit, `specify`, `/speckit.*`, `$speckit-*`, or constitution -> specify -> plan -> tasks -> analyze -> implement.
- `kiro-lite`: `.kiro/specs/` or `requirements.md` + `design.md` + `tasks.md`.
- `brownfield-gap`: desired behavior depends on existing code; mark inferred behavior `[TO VERIFY]`.
- `bugfix-spec`: meaningful regression risk; capture current/expected/unchanged behavior, root-cause hypothesis, regression proof.
- `change-proposal`: cross-repo, API-breaking, migration-heavy, security/privacy-sensitive, or deployed behavior contract change; use OpenSpec-style current/proposed sections when present.
- `orchestrated-implementation`: many independent tasks with explicit boundaries, dependencies, per-unit proof; profile must be `strict` or `regulated`.

## Route

- `sdd-spec-kit`: Spec Kit setup/lifecycle.
- `sdd-specify`: requirements/spec writing.
- `sdd-plan-tasks`: design, planning, contracts, quickstart, tasks.
- `sdd-implement`: task execution.
- `sdd-audit`: traceability/completion review.

## Invariants

- Requirements say what/why; design says how.
- High-risk assumptions are clarified, constrained, marked, or justified.
- Buildable requirements map to tasks or explicit deferral.
- Completed tasks require fresh evidence.
- Spec/plan/code drift is updated or disclosed before completion claims.
- LLM self-review, model confidence, or context-free LLM-as-a-judge is not proof.
- Do not run installers, upgrades, or network-backed setup unless requested or project-required.

## Output

```md
## SDD Route
- LANE: <lane>
- EVIDENCE_PROFILE: basic | standard | strict | regulated
- SOURCE_OF_TRUTH: <paths>
- ARTIFACTS: <paths>
- BLOCKERS: <none or concrete blockers>
- NEXT: <focused skill/workflow step>
- PROOF: <validator or expected verification>
```
