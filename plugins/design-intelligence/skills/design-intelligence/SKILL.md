---
name: design-intelligence
description: "Route UX/product judgment to focused skills for framing, IA, interaction, usability, accessibility, visual communication, design-system governance, and heuristics. Not for Figma, CSS, automation, or assets."
---

# Design Intelligence

Router for product and UX judgment. Use when the work is to improve, critique, frame, audit, or architect an experience, not to operate Figma, generate assets, or write CSS.

## Operating Stance

Start with:

1. User or segment.
2. Job, task, or outcome.
3. Available evidence.
4. Current decision or uncertainty.
5. Usability, accessibility, trust, and effectiveness criteria.

With thin context, make bounded assumptions and ask only one decision-critical question. Do not invent styling, design-system facts, analytics, research, or accessibility compliance; label known, assumed, and unverified claims.

## Technology-Agnostic UI/UX Coverage

Treat UI as product behavior made visible, not as a frontend technology. Work from the user's task, information, decisions, states, feedback, recovery, access needs, and trust obligations before naming components or implementation details.

Common UI surfaces to recognize:

- forms, validation, data entry, review, and submission;
- lists, tables, dashboards, feeds, cards, and detail views;
- search, browse, filters, sorting, saved views, and no-results states;
- onboarding, first-run education, permissions, consent, and account setup;
- empty, loading, disabled, partial-success, error, success, and recovery states;
- settings, preferences, admin controls, bulk actions, and destructive actions;
- notifications, status, activity, progress, and handoff between channels;
- content-heavy screens, help, policy, commerce, checkout, and transactional flows.

For any surface, inspect its anatomy: actor, task, object, content, primary decision, available actions, state transitions, feedback, recovery, accessibility floor, privacy/trust risk, and validation signal.

## Route

Use the smallest skill set:

- `product-framing`: problem, audience, outcome, product bet, discovery, success metric.
- `interface-architecture`: navigation, taxonomy, labels, findability, content model, screen structure, hierarchy.
- `interaction-design`: task flow, affordances, feedback, state coverage, errors, undo, empty/loading states, progressive disclosure, efficiency.
- `usability-accessibility-review`: heuristics, cognitive walkthrough, WCAG/APG/COGA risk, inclusive design, dark patterns.
- `visual-communication`: hierarchy, scannability, attention, grouping, readability, density, emphasis.
- `design-system-governance`: reusable decisions, patterns, contribution, accessibility proof, maturity, drift.

Dependency order: product framing -> interface architecture -> interaction design -> visual communication -> usability/accessibility review -> design-system governance.

For common UI surfaces, route by the unresolved design question rather than the component name. A form may need product framing, IA, interaction, content, accessibility, or governance; a table may be an IA, visual communication, or decision-quality problem.

## Evidence Rules

- Use provided screenshots, code, product docs, analytics, research notes, support tickets, and user quotes when available.
- For live or rendered UI, inspect the actual surface before claiming visual, interaction, or accessibility findings.
- Static accessibility review identifies risks only; compliance requires live testing of keyboard, focus, semantics, contrast, motion, and assistive technology behavior.
- Heuristics identify risks, not proven user behavior.
- Prefer primary standards, platform guidance, and inspected product evidence over inspiration galleries, generic UX laws, or taste claims.

## Output Shape

Lightweight advice: key judgment, 3-7 highest-impact recommendations, main risk/assumption, next validation step.

Reusable audits or product decisions: use `references/contracts.md`. Use `design_intelligence.decision.v1` for durable product/design-system decisions.

## Hard Boundaries

- Do not focus on Figma, design-tool operation, CSS, or component implementation unless the user explicitly asks.
- Do not recommend deceptive patterns, fake scarcity, manipulative consent, inaccessible friction, or engagement optimization that harms user agency.
- Do not treat a design system as a style kit only; it is a set of reusable decisions with evidence, ownership, usage rules, and accessibility constraints.
