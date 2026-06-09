---
name: usability-accessibility-review
description: "Review screens, flows, specs, or product ideas for usability heuristics, cognitive walkthrough failures, WCAG/APG/COGA accessibility risks, inclusive design, ethical UX, and dark patterns."
---

# Usability And Accessibility Review

Use for structured, evidence-tied critique, not taste.

## Evidence First

Identify:

- surface and task;
- user or segment;
- available evidence;
- what was not inspected;
- whether the claim needs live behavior, assistive technology, analytics, or user research.

Do not claim accessibility compliance from screenshots, mocks, or prose. Static review finds risks; compliance requires testable behavior.

With thin evidence, separate observed failures, heuristic risks, standards risks, and validation tasks.

## Review Lenses

Use these lenses:

- Nielsen: status visibility, real-world language, user control, consistency, error prevention, recognition over recall, flexibility, minimalist relevance, error recovery, help.
- Shneiderman: consistency, universal usability, feedback, closure, error prevention/handling, easy reversal, user control, reduced memory load.
- Cognitive walkthrough: for primary tasks, can users know the goal, notice the action, understand it, and see progress?
- Accessibility floor: WCAG 2.2 as testable baseline; APG/COGA as design guidance.

Accessibility checks:

- perceivable content and text alternatives;
- keyboard operation and focus order;
- visible focus;
- accessible names and roles;
- target size and pointer alternatives;
- contrast and non-color indicators;
- predictable navigation and help;
- reduced redundant entry;
- understandable language and recovery;
- motion, timeout, and seizure risks;
- cognitive support, memory burden, and clear instructions.

UI-specific accessibility floor:

- visible focus and focus appearance for keyboard users;
- target size and pointer alternatives for motor accessibility;
- keyboard operation and alternatives to dragging or path-based gestures;
- reduced redundant entry and copy-forward opportunities when safe;
- accessible authentication and recovery without cognitive traps;
- clear labels, instructions, error identification, suggestions, and help;
- predictable navigation, status changes, timeouts, motion, and interruption control.

Static review can flag these as risks. Only live testing can confirm focus order, semantics, announcements, contrast, target geometry, keyboard behavior, motion behavior, and assistive-technology experience.

Reject or flag ethical UX risks:

- fake urgency or scarcity;
- hidden costs;
- confirmshaming;
- confusing consent;
- prechecked or bundled consent;
- asymmetric opt-out;
- cancellation friction;
- inaccessible friction;
- deceptive emphasis;
- engagement loops that harm user agency.

## Severity

Use `references/scorecards.md`. P0/P1 lead; P3 polish must not bury task or accessibility risks.

## Output

For prose:

1. **Verdict**: short design judgment.
2. **Findings**: ordered by severity, with evidence, principle, impact, recommendation, confidence.
3. **Accessibility limits**: what was and was not checked.
4. **Validation needed**: live tests, users, analytics, or domain evidence.
5. **Next actions**: smallest useful sequence.

For reusable output, use `design_intelligence.review.v1` from `references/contracts.md`.

## Good Finding Shape

Use:

```text
P1 - Missing feedback after payment submission
Evidence: after tapping Pay, the button disables but no progress, status, or confirmation appears.
Principle: visibility of system status; Shneiderman informative feedback.
Impact: users may retry payment, abandon, or contact support.
Recommendation: show immediate progress, preserve form state, prevent duplicate submit, and provide success/failure recovery.
Confidence: medium; requires live slow-network validation.
```

Avoid vague findings: "make this cleaner", "improve accessibility", "feels confusing", "use better hierarchy", "add delight."
