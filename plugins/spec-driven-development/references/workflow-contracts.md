# SDD Workflow Contracts

## Lanes

- `tiny-direct`: low-risk local fix; mini-spec plus proof.
- `spec-kit`: `.specify/`, `specs/<feature>/spec.md`, `plan.md`, `tasks.md`, Spec Kit commands.
- `kiro-lite`: `.kiro/specs/<feature>/requirements.md`, `design.md`, `tasks.md`, or equivalent trio.
- `bugfix-spec`: current/expected/unchanged behavior, root cause, fix plan, regression proof.
- `brownfield-gap`: compare desired behavior with code; mark inferred behavior `[TO VERIFY]`.
- `change-proposal`: current vs proposed specs for breaking, security/privacy, migration, deployed, or multi-repo work.
- `orchestrated-implementation`: explicit boundaries, dependencies, and per-task validation.

## Artifact Roles

- Requirements/spec: behavior, value, non-goals, acceptance, success.
- Design/plan: choices, architecture, contracts, data, validation.
- Tasks: file-level work, dependencies, boundaries, verification.
- Quickstart/validation: commands or manual proof.
- Research/gap analysis: evidence and options.

## Minimum Contract Before Code

- selected lane
- risk and evidence profile
- source-of-truth paths
- requirement IDs or stable requirement names
- implementation task list or mini-spec for tiny-direct
- verification command, evidence ledger path, or manual proof
