---
name: sdd-specify
description: Create or refine SDD requirements and specifications with explicit assumptions, non-goals, acceptance criteria, success metrics, and retrofit truth markers.
---

# SDD Specify

Use to turn an idea, feature, bug, or existing system into a behavior-first spec.

## Artifact Shape

Prefer the repo shape: Spec Kit `specs/<feature>/spec.md`; Kiro `.kiro/specs/<feature>/requirements.md` or `bugfix.md`; OpenSpec `openspec/specs/<capability>/spec.md` plus `openspec/changes/<change>/`; fallback `.sdd/<feature>/requirements.md`.

## Requirements Discipline

Keep specs at what/why level:

- source: user statement, code, runtime evidence, doc, regulation, or assumption
- users/goals/workflows and observable behavior
- acceptance, edge/failure cases, constraints, non-goals
- measurable success criteria

Avoid stack, classes, schemas, framework choices, and file paths unless bugfix/retrofit/design-first and explicitly labeled.

## Ambiguity Policy

Proceed with labeled low-risk assumptions. Clarify, constrain, or convert to non-goal when ambiguity changes scope, security/privacy, UX, data retention, integration contracts, compliance, or delivery risk. `[TO VERIFY]` needs owner, risk, next action. LLM-drafted requirements are drafts until checked against user input, code truth, or project context.

Ask at most three concrete questions only when needed.

## Required Content

Feature spec:

- problem, priority stories/journeys, non-goals
- requirement quality ledger: source, assumption status, ambiguity, reviewer/owner, evidence need
- stable functional IDs; measurable NFRs
- acceptance scenarios, edge/failure cases, assumptions/dependencies
- implementation-independent success criteria and readiness checklist

Bugfix spec:

- current, expected, unchanged behavior
- reproduction/evidence plus symptom source ledger
- suspected affected area, regression risk
- validation for original symptom and adjacent behavior

Retrofit spec:

- code/runtime behavior is truth
- inferred behavior is `[TO VERIFY]`
- separate current behavior from desired change
- record source per requirement: code, runtime proof, docs, or inference
- add initial "Spec Verification" task group
- do not invent schemas, endpoints, or deployment facts

## Done

No placeholders; buildable requirements are testable or deferred; success criteria measurable; non-goals constrain scope; assumptions/sources/review gaps visible; stable IDs support traceability; next step is clarify, plan, tasks, or direct implementation.
