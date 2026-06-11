---
name: sdd-implement
description: Execute SDD task lists safely, update task status, handle spec drift, and verify completion with fresh evidence before claiming done.
---

# SDD Implement

Use when tasks are ready and the user wants implementation, execution, continuation, or completion from SDD artifacts.

## Preflight

```bash
python3 "$PLUGIN_ROOT/scripts/sdd_surface_audit.py" <repo> --json
python3 "$PLUGIN_ROOT/scripts/sdd_traceability_check.py" <repo> --json
git status --short
```

Read active tasks, design/plan, spec/requirements, quickstart, evidence ledger if present, and relevant code. If core artifacts are missing, route to `sdd-plan-tasks` or `sdd-specify`. Preserve unrelated user changes.

## Execution

- Work by dependency order, task/story at a time.
- Respect parallel markers only for safe independent work.
- Write tests first when tasks request TDD/contracts/regression coverage.
- Keep edits inside task boundary.
- If code disproves plan/spec, update artifact or report drift before continuing.
- Complete a task only after fresh evidence.
- Never complete from intent, compilation hope, agent summary, LLM self-review, model confidence, or context-free LLM-as-a-judge.
- For `strict`/`regulated`, keep requirement/task IDs in notes, evidence, or commits.

## Evidence

Use the most relevant proof available: tests, build/typecheck, relevant lint, runtime/UI smoke, bug reproduction command, or labeled manual verification (reproducible by another human, scoped to the claim) when automation is unavailable.

Evidence must match the claim. Lint does not prove behavior; a unit test does not prove runtime boot; a checklist does not prove integration.

For `strict`/`regulated`, maintain `evidence.md`, `validation.md`, `proof.md`, or equivalent with command/manual path, current-run marker, outcome, covered IDs, and gaps/deferrals. If deterministic proof is unavailable for high-risk behavior, record risk acceptance instead of claiming full proof.

## Drift

When implementation contradicts artifacts: pause, identify artifact and code evidence, update intended artifact or implementation, then re-run relevant check.

## Completion Gate

- Completed tasks have evidence.
- No unchecked blocking task is hidden.
- Traceability is `PASS` or findings are disclosed.
- Tests/build/smoke commands and outcomes are reported.
- Final claim is no broader than evidence.
- LLM-generated or modified code has project-local proof; model judgment is advisory only.
