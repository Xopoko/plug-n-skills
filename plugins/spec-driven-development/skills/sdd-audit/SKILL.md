---
name: sdd-audit
description: Audit SDD artifacts, requirement-task traceability, surface selection, and completion evidence before implementation or final delivery.
---

# SDD Audit

Use for SDD reviews, consistency checks, pre-implementation gates, completion proof, or questions like "is this spec ready", "are tasks traceable", or "can we claim done".

## Required Tools

```bash
python3 "$PLUGIN_ROOT/scripts/sdd_surface_audit.py" <repo> --json
python3 "$PLUGIN_ROOT/scripts/sdd_traceability_check.py" <repo> --json
```

Use `--feature-dir <path>` when active feature is not inferable.

## Check

- surface, lane, risk/evidence profile
- missing spec/design/tasks/quickstart/contracts
- placeholders, clarification markers, source/review gaps
- duplicate or missing requirement/task IDs
- requirements without tasks; tasks without paths/verification
- completed tasks without fresh evidence or ledger
- missing strict/regulated evidence ledger
- task refs to unknown requirement IDs
- LLM self-review/model confidence/context-free LLM-as-a-judge treated as proof
- scope/evidence mismatch; missing privacy/memorization/proprietary/credential/regulated-data constraints

## Severity

- `FAIL`: missing core artifact, unresolved high-impact clarification, buildable requirement without task, completed task without evidence, or LLM self-judgment used as proof.
- `WARN`: weak traceability, vague requirement, missing optional design detail, missing non-critical evidence ledger, or manual-only proof.
- `PASS`: artifacts are present and traceable enough for the chosen lane.

## Report

```md
## SDD Audit
- STATUS: PASS | WARN | FAIL
- LANE: <detected or selected lane>
- FEATURE_DIR: <path or none>
- BLOCKING_FINDINGS: <count and top findings>
- WARNINGS: <count and top findings>
- NEXT: <specific action>
```

Do not rewrite artifacts during an audit unless the user explicitly asks for fixes.
