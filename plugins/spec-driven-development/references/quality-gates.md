# SDD Quality Gates

## Risk And Evidence Profile Gate

- Lane matches risk, uncertainty, and blast radius.
- High-risk work records privacy, safety, compliance, migration, security, performance, or integration risk.
- Evidence profile is declared before implementation:
  - `basic`: local patch plus focused proof
  - `standard`: requirements/tasks plus automated checks or reproducible manual proof
  - `strict`: traceability ledger, tests/contracts, review, drift handling, evidence ledger
  - `regulated`: formal/model evidence or explicit risk acceptance
- Workflow stays light when possible but keeps traceability when claims span artifacts.

## Specification Gate

- Requirements are behavior-first.
- Requirement sources are visible: user input, code truth, runtime observation, product doc, regulation, or assumption.
- Non-goals are explicit; success criteria measurable; acceptance criteria testable.
- Clarification markers are limited and high-impact.
- Assumptions are visible; `[TO VERIFY]` has owner, risk, and next action.
- LLM-drafted requirements are reviewed against project context before being treated as source of truth.

## Planning Gate

- Technical choices have rationale; alternatives are recorded when trade-offs matter.
- Existing code patterns are checked for brownfield work.
- Contracts, data model, migration, and security implications are documented when relevant.
- Validation scenarios exist before implementation.
- Requirement IDs map to design decisions, changed areas, verification, and expected evidence.
- Privacy, memorization, proprietary-code, credential, and regulated-data constraints are recorded when LLMs or generated code are involved.

## Task Gate

- Task IDs are stable; buildable requirements map to tasks; tasks include known paths.
- Parallel markers are justified by file and dependency independence.
- Each task or task group has verification and expected evidence.
- Foundation tasks block dependent user-story work.
- Completed tasks cite fresh evidence, not intent, agent summary, or LLM self-review.
- Orchestrated tasks expose dependencies and per-unit proof.

## Implementation Gate

- Tests/checks run against current code; completed tasks have fresh evidence.
- Drift between implementation and spec is resolved or disclosed.
- The final claim does not exceed the evidence.
- LLM self-review, confidence, or context-free LLM-as-judge output is not completion proof.
- Manual verification is labeled, reproducible enough for another human, and scoped to the claim.
- High-risk executable behavior has automated, contract, model-checking, formal, or explicitly accepted evidence.

## Lightweight Exception

For tiny direct work, the full artifact set is not required. The agent still needs intent, non-goal, and proof.
