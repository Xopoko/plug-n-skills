---
name: visual-communication
description: "Improve hierarchy, scannability, visual emphasis, readability, grouping, density, attention, trust, and perceptual clarity. Do not use for CSS recipes, Figma operation, or decorative visual styling."
---

# Visual Communication

Use when users cannot tell what matters, where to look, what changed, or what to do next. Judge visual design as communication of structure and priority, not decoration.

## Core Principles

Communicate:

- Priority: most important item is visually first.
- Grouping: related items look related.
- Sequence: task-order scanning.
- Contrast: meaningful differences are visible.
- Balance: stable, readable layout.
- Recognition: familiar patterns look familiar.
- Comprehension: legible text, icons, numbers, data.

Use Gestalt principles carefully:

- proximity for grouping;
- similarity for shared meaning;
- continuity for scan paths;
- common region for scoped groups;
- closure only when ambiguity is low.

Ground recommendations in perception and task comprehension. Heuristic source -> likely perception risk; live/user evidence -> observed effect.

## Review Questions

- What is the first thing the user should notice?
- What is the first thing they actually notice?
- Does the hierarchy match task importance?
- Are labels, values, controls, and feedback visually connected?
- Is the amount of information proportionate to the task?
- Does the interface rely on color alone?
- Is typography readable and consistent with the product surface?
- Are dense tables, dashboards, forms, and lists structured for comparison?
- Do empty, loading, disabled, and error states communicate clearly?

## Surface-Specific Communication

- Forms: show question grouping, required versus optional meaning, current progress, validation scope, and repair path.
- Tables and data views: support comparison through stable labels, aligned values, scannable columns, clear sorting/filtering state, and meaningful summaries.
- Dashboards: separate monitoring, diagnosis, and action; avoid charts or metrics that are precise but not decision-useful.
- Search and browse: make result identity, relevance cues, active constraints, and no-results recovery visible.
- Empty and error states: explain system status, teach the model, preserve agency, and offer a direct next action.
- Responsive or adaptive layouts: preserve priority, grouping, labels, controls, and state visibility across viewport, zoom, localization, and density changes.

## Recommendations

Prefer before decoration:

1. Remove nonessential competing content.
2. Reorder by task priority.
3. Group related items.
4. Clarify labels and values.
5. Increase useful contrast.
6. Improve spacing and alignment.
7. Expose state and feedback.
8. Reduce unnecessary surface nesting.
9. Add visual affordance only where action is unclear.

Do not default to more cards, shadows, gradients, illustrations, or color. Those may help, but only after hierarchy and information structure are sound.

## Output

Produce:

1. **Hierarchy diagnosis**: what the design currently says.
2. **Intended priority**: what it should say.
3. **Attention conflicts**: where visual emphasis competes with user goals.
4. **Readability risks**: density, contrast, line length, labels, numbers, states.
5. **Recommended changes**: ordered by communication impact.
6. **Validation**: screenshot comparison, first-click test, comprehension test, task success, or accessibility check.

For durable visual hierarchy decisions, use `design_intelligence.decision.v1` from `references/contracts.md`.

## Red Flags

- Equal visual weight for all content.
- Primary action not tied to task.
- Nested cards/heavy decoration creates false structure.
- Important state shown only by color.
- Tables hide comparison criteria.
- Data is precise but not decision-useful.
- Marketing hierarchy used in operational surfaces.
