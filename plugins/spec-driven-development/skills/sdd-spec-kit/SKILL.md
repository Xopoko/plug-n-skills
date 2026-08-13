---
name: sdd-spec-kit
description: >-
  GitHub Spec Kit projects route constitution, specify, clarify, plan,
  checklist, tasks, analyze, task-to-issue publication, implement, converge,
  extensions, and presets.
---

# SDD Spec Kit

Use for GitHub Spec Kit, Specify CLI, `/speckit.*`, `$speckit-*`, `.specify/`, extensions, presets, or Spec Kit command behavior.

## Source Model

Project workspace is source of truth. Upstream `https://github.com/github/spec-kit` and any user-provided Spec Kit reference checkout are references unless the user asks to edit Spec Kit itself.

## Preflight

PowerShell: use `$env:PLUGIN_ROOT` for `$PLUGIN_ROOT` command paths.

```bash
python3 "$PLUGIN_ROOT/scripts/sdd_surface_audit.py" <repo> --json
git status --short
```

Check `.specify/`, `.specify/feature.json`, `.specify/memory/constitution.md`, `specs/*/{spec.md,plan.md,tasks.md}`, and `.specify/extensions.yml`. Treat `.specify/feature.json` as the active feature unless `SPECIFY_FEATURE_DIRECTORY` explicitly overrides it; do not infer the active feature from the checked-out Git branch. State any init/install/upgrade/fetch before running it.

## Command Map

Follow project command files when present; otherwise use this layout:

- Constitution: `.specify/memory/constitution.md`
- Specify: `specs/<feature>/spec.md` plus `specs/<feature>/checklists/requirements.md`
- Clarify: resolve `[NEEDS CLARIFICATION]`
- Plan: `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, risk/evidence profile
- Checklist: generate requirement-quality checklists; do not treat checklist completion as implementation proof
- Tasks: `tasks.md` with dependency order, requirement links, paths, verification, expected evidence
- Analyze: read-only artifact consistency
- Tasks to issues: publish generated tasks as GitHub issues only when the user explicitly authorizes that external write
- Implement: execute tasks, update status, verify
- Converge: assess implementation against spec, plan, and tasks; append remaining work to `tasks.md`, then repeat implementation and proof until no material gap remains

## Extensions

For `.specify/extensions.yml`: read relevant `before_*`/`after_*`; skip disabled hooks; do not evaluate non-empty conditions yourself. Mandatory hooks surface `EXECUTE_COMMAND: <command>` and wait when supported. Optional hooks are reported unless requested.

## Gates

- `spec.md`: no implementation leakage unless template allows; sources/assumptions/ambiguity/review gaps visible for high-impact requirements.
- `plan.md`: decisions, rationale, alternatives, constitution gate, risk/evidence profile, traceability strategy.
- `tasks.md`: IDs, story labels when applicable, paths, dependencies, independent validation.
- Strict/regulated work: evidence ledger such as `evidence.md`, `validation.md`, `proof.md`, or equivalent in `quickstart.md`/`tasks.md`.
- LLM self-review, model confidence, or context-free LLM-as-a-judge is advisory only.
- Run `python3 "$PLUGIN_ROOT/scripts/sdd_traceability_check.py" <repo> --json` before implementation and before claiming done.

## Report

Return active feature directory, changed Spec Kit artifacts, unresolved risks, validation commands/outcomes, evidence updates, and next phase.
