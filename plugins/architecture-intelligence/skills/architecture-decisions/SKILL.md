---
name: architecture-decisions
description: "Use when structural code choices need durable rationale: ADRs, tradeoffs, consequences, reversibility, ownership, review triggers, and validation plans."
---

# Architecture Decisions

Use when making, documenting, reviewing, or revising an architecture decision.

## ADR Threshold

Create or review an ADR when a choice:

- shapes module boundaries, ownership, data ownership, runtime topology, or integration style;
- changes reliability, scalability, security, performance, operability, testability, or cost;
- introduces hard-to-reverse dependency, platform, data model, framework, or protocol;
- affects multiple teams, services, packages, apps, release trains, CODEOWNERS/OWNERS coverage, or cross-owned dependencies;
- needs a revisit trigger because evidence may change.

Skip ceremony for small local implementation choices unless asked.

## Contract

Capture status, context/forces, options, decision/rationale, consequences, affected components, migration plan, fitness functions, owner/review path, ownership exception path, expiry/revisit trigger.

Use `architecture_intelligence.decision.v1` for durable output.

## Review Questions

- What source/runtime evidence supports the decision?
- Which quality attribute improves and which gets worse?
- What is the smallest reversible step?
- What would make this decision wrong?
- How will drift be detected?
- Who owns implementation and later review?
- Which owners must review cross-owned dependency/runtime changes?
- Which tests, metrics, or operational signals prove it worked?
- What rationale would be lost if this stayed only in chat or PR comments?

## Verdict

- `accept`: evidence and validation are sufficient.
- `sharpen`: promising but missing constraints, options, owner, or validation.
- `block`: high-risk or unsupported.

Before `accepted`, require explicit alternatives, named tradeoffs, evidence stronger than preference/trend, ownership/revisit trigger, and drift-detection fitness functions.

Do not accept decisions backed only by preference, trend, or unsupported scale claims. Mark `needs-validation` until evidence and fitness functions are credible.
