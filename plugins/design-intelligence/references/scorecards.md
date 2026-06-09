# Design Intelligence Scorecards

Use these scorecards as shared language across the focused skills. They are not a substitute for user research, usability testing, accessibility testing, analytics, or domain expertise.

## Severity

| Severity | Meaning | Action |
| --- | --- | --- |
| P0 | Causes user harm, legal/accessibility risk, destructive data loss, deceptive UX, or blocks a critical task. | Must fix or explicitly reject before launch. |
| P1 | Blocks or seriously degrades a primary user task for a meaningful user segment. | Fix before launch or before the next high-risk release. |
| P2 | Causes avoidable friction, confusion, support load, or measurable task slowdown. | Plan and prioritize with nearby work. |
| P3 | Polish, consistency, or clarity issue with low task impact. | Fix opportunistically. |

## Core Lenses

| Lens | Strong Signal | Failure Signal |
| --- | --- | --- |
| Product fit | User, context, outcome, and success metric are explicit. | Screen solves an internal or aesthetic problem without user evidence. |
| IA and hierarchy | Users can predict where things live and what matters first. | Navigation mirrors org structure, labels are ambiguous, priority is flat. |
| Interaction | Actions have clear affordance, feedback, state, recovery, and closure. | Silent action, hidden state, no undo, weak error prevention, unclear next step. |
| Accessibility | WCAG/APG/COGA risks are considered before polish. | Keyboard, focus, target size, contrast, names, motion, or comprehension gaps. |
| Cognitive load | Users recognize options and make small decisions with context. | Excess choice, memory burden, dense jargon, unnecessary steps. |
| Visual communication | Scale, grouping, contrast, and spacing make importance obvious. | Decorative competition, weak scannability, unreadable density. |
| Ethics and trust | User agency, consent, transparency, and counter-metrics are protected. | Dark patterns, fake urgency, manipulative defaults, deceptive emphasis. |
| System governance | Reusable decisions have owner, rationale, accessibility proof, and adoption path. | Components/tokens exist without decision rules, contribution model, or evidence. |

## UI Surface Types

Use a surface type when it clarifies pattern obligations. A screen can have more than one, but choose the dominant risk.

| Surface Type | Typical Obligations |
| --- | --- |
| `form` | labels, instructions, input burden, validation timing, error repair, saved progress, review, submission, confirmation |
| `data-view` | comparison, sorting, filtering, grouping, density, summary/detail, row identity, action scope |
| `search-browse` | query intent, active constraints, relevance cues, no-results recovery, clear/reset, saved/shared state |
| `navigation` | location, origin, destination, labels, hierarchy, wayfinding, permission and hidden-state handling |
| `onboarding` | prerequisite knowledge, progressive disclosure, permission timing, skip/retry, first-task handoff |
| `permission-consent` | user agency, informed choice, reversibility, denial recovery, privacy expectation, legal/accessibility risk |
| `notification-status` | source, urgency, timestamp, channel, read/unread, actionability, interruption control |
| `empty-error-recovery` | system status, cause, user agency, repair path, prevention, escalation, support |
| `settings-admin` | scope, defaults, inheritance, roles, auditability, destructive change, rollback |
| `content-screen` | purpose, source, freshness, reading order, summaries, comprehension, next action |
| `transaction` | eligibility, review, commitment, confirmation, receipt, cancellation, recovery, trust |
| `design-system-pattern` | when to use, variants, state model, content rules, accessibility proof, owner, exceptions |

## Pattern Obligation Checklist

When a surface-specific recommendation matters, check:

1. What task, object, and decision does this surface support?
2. What content, labels, and help must be present for comprehension?
3. What states must be visible before, during, after, and after failure?
4. What input burden, memory burden, and motor burden can be removed?
5. What recovery path protects users from mistakes, latency, permissions, and partial success?
6. What accessibility obligations are testable, and what cannot be proven statically?
7. What privacy, consent, trust, or ethical risk could the pattern create?
8. What validation method will show whether the pattern improved task success?

## Output Contract

Every review finding should include:

- `id`: stable kebab-case finding id.
- `severity`: `P0`, `P1`, `P2`, or `P3`.
- `lens`: one of the core lenses above.
- `evidence`: what was observed, with file/screenshot/step/source reference when available.
- `principle`: source-backed heuristic, standard, or pattern.
- `impact`: why this matters to the user or product.
- `recommendation`: concrete change or decision.
- `confidence`: `low`, `medium`, or `high`.
- `requires_validation`: true when live user, accessibility, analytics, or technical proof is still required.

Surface-specific reviews may also include `surface_type`, `pattern_obligations`, and `validation_limits` from `references/contracts.md`.

## Design Quality Gate

Before calling a design decision ready, answer:

1. What user outcome does this decision improve?
2. What user segment and context is it for?
3. What evidence supports the decision?
4. What is the main usability or accessibility risk?
5. What could be removed without hurting task success?
6. What state, error, empty, loading, and recovery cases exist?
7. What metric or qualitative signal will show whether it worked?
8. What counter-metric protects the user from over-optimization?
9. What existing product pattern or design-system decision should it reuse?
10. What assumption would change the recommendation if disproved?

## Evidence Strength

| Strength | Evidence | Use |
| --- | --- | --- |
| High | Direct observation of target users, production analytics, usability test evidence, accessibility test results, primary standards applied to inspected behavior. | Can support accepted decisions when limitations are stated. |
| Medium | Closely related support tickets, research notes, benchmark studies, platform guidance, mature design-system guidance, expert heuristic review. | Can support proposed decisions and prioritized risks. |
| Low | Stakeholder opinion, inspiration examples, generic UX laws, unaudited screenshots, untested assumptions. | Use only as hypotheses or prompts for validation. |

## Synthesis Gate

Before adopting an external pattern, check:

1. The source is inspectable and does not require hidden accounts, paid APIs, or opaque installers.
2. The mechanism improves task success, accessibility, trust, reuse, or validation discipline.
3. Platform or domain assumptions fit the target product.
4. Behavioral, content, accessibility, and state obligations survive, not only visual shape.
5. A local validation method is named.
6. Rejected alternatives and evidence gaps are recorded.
