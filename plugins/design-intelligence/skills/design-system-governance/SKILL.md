---
name: design-system-governance
description: "Govern reusable design decisions, patterns, components, accessibility proof, contribution models, maturity, drift, and system adoption. Do not use for CSS implementation, Figma libraries, or token tooling unless requested."
---

# Design System Governance

Use when a product needs coherent reusable design decisions, not merely a prettier component library. A design system is an operating model for consistency, accessibility, quality, and product speed.

## Decision Layers

Separate:

1. Principles: what the system optimizes for.
2. Patterns: reusable solutions to recurring product problems.
3. Components: reusable interface objects.
4. Content rules: labels, messages, empty states, help, tone.
5. Accessibility rules: keyboard, focus, semantics, contrast, motion, target size, cognitive support.
6. Usage guidance: when to use, when not, examples, anti-patterns.
7. Contribution process: proposal, review, validation, release, retirement.
8. Maturity/adoption: ownership, use, quality proof.

Tokens and component APIs can preserve decisions, but they are not the decisions themselves.

Record evidence classes: product use cases, accessibility obligations, adoption/drift signals, platform constraints, owner/review proof.

## Common Pattern Families

Govern recurring UI patterns as reusable decisions:

- forms and validation;
- search, filters, sorting, and no-results recovery;
- lists, tables, cards, dashboards, and detail pages;
- empty, loading, disabled, error, success, and partial-success states;
- onboarding, permissions, consent, account setup, and first-run education;
- notifications, progress, activity, alerts, and system status;
- destructive actions, bulk actions, undo, confirmation, and escalation;
- settings, preferences, admin controls, roles, and permissions.

For each pattern, preserve the product job, content rules, state model, accessibility obligations, usage constraints, anti-patterns, and validation evidence. Do not reduce the pattern to visual anatomy or component props.

## Governance Questions

- What repeated user problem does this pattern solve?
- What evidence shows it works?
- What variants are allowed, and why?
- What accessibility obligations come with it?
- What are the known failure modes and anti-patterns?
- Who owns changes and approvals?
- How do teams request new patterns or exceptions?
- How are breaking changes, deprecations, and migrations handled?
- How is adoption measured?

## Pattern Decision Record

For durable decisions, produce:

1. **Pattern name**.
2. **Problem solved**.
3. **User context**.
4. **When to use**.
5. **When not to use**.
6. **Anatomy and behavior**.
7. **Accessibility requirements**.
8. **Content rules**.
9. **Variants and constraints**.
10. **Evidence and validation**.
11. **Owner and review path**.
12. **Deprecation or exception policy**.

For reusable output, use `design_intelligence.decision.v1` from `references/contracts.md`.

## Maturity Lens

Evaluate maturity across:

- principles and guidance;
- accessibility built in;
- reusable patterns/components;
- source of truth;
- contribution model;
- adoption and support;
- measurement;
- retirement of weak or duplicated patterns.

## Output

Produce:

1. **System diagnosis**: consistency, adoption, accessibility, and governance risk.
2. **Decision inventory**: what reusable decisions exist or are missing.
3. **Recommended governance model**: ownership, contribution, review, validation, release.
4. **Pattern decision records**: for the most important gaps.
5. **Maturity roadmap**: smallest changes that increase quality and reuse.

## Red Flags

- Design system treated as Figma/component package only.
- Teams copy patterns without guidance.
- Accessibility verified per implementation instead of built into patterns.
- Exceptions undocumented.
- Components lack content rules.
- Tokens preserve values but not product intent.
- Deprecated patterns never disappear.
