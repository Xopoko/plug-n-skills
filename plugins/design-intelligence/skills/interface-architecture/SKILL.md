---
name: interface-architecture
description: "Design or critique information architecture, navigation, taxonomy, labeling, screen structure, content priority, findability, search and browse strategy, and information hierarchy."
---

# Interface Architecture

Use when information structure, navigation, or screen priority is the design problem. Navigation is one expression of IA; work from structure first.

## Separate The Decisions

Analyze separately:

1. Conceptual model: user understanding of domain.
2. Content model: objects, attributes, states, relationships, lifecycle.
3. Taxonomy: categories and grouping logic.
4. Labels: user-facing terms.
5. Navigation: movement through structure.
6. Search/browse: recovery when navigation fails.
7. Screen hierarchy: primary, secondary, supporting, hidden.
8. Wayfinding: location, origin, next actions.

## Common UI Surface Checks

- Forms and transactions: object lifecycle, question order, grouping, review step, confirmation, and where users recover from mistakes.
- Search and browse: query intent, result metadata, filtering criteria, sorting, no-results recovery, saved state, and reset behavior.
- Lists, tables, and dashboards: comparison model, row/card identity, summary versus detail, density, grouping, and decision threshold.
- Settings and admin: scope, ownership, defaults, inheritance, permission boundaries, and reversible versus irreversible change.
- Content-heavy screens: purpose, source, freshness, reading order, summaries, help placement, and next action.
- Onboarding and setup: prerequisite knowledge, progressive disclosure, permission timing, skip/retry paths, and handoff to the first real task.

## Diagnostic Questions

- Does the structure match user mental models or internal org structure?
- Can the user predict where a target item belongs?
- Are labels mutually exclusive, familiar, and scoped?
- Is the primary path visible without burying secondary paths?
- Are search, filters, and sorting designed around user criteria?
- Do no-results, empty, archived, hidden, permission-denied, and filtered-out states explain where content went?
- Does the screen expose one clear next action for the current task?
- Does the hierarchy survive mobile, long text, localization, empty states, and dense data?

## Validation Methods

Match method to uncertainty:

- **Content inventory**: when the scope is unknown.
- **Open card sort**: when grouping language is unknown.
- **Closed card sort**: when category fit is uncertain.
- **Tree test**: when findability of a proposed IA must be checked.
- **First-click test**: when screen navigation priority is uncertain.
- **Search-log/support-ticket review**: when users already reveal missed labels.
- **Cognitive walkthrough**: when the path through structure must be checked step by step.

External guidance can inform structure; only local user language and task evidence can confirm labels and grouping.

## Output

Produce:

1. **Architecture diagnosis**: the structural issue in one paragraph.
2. **Decision map**: conceptual model, content model, taxonomy, labels, navigation, hierarchy.
3. **Recommended structure**: proposed grouping and priority.
4. **User-facing labels**: with rejected alternatives when important.
5. **Findability risks**: where users may look first and fail.
6. **Validation plan**: tree test/card sort/first-click/usability test/log analysis.
7. **Implementation notes**: only conceptual; do not drift into CSS or Figma steps.

For reusable IA or taxonomy decisions, use `design_intelligence.decision.v1` from `references/contracts.md`.

## Red Flags

- Top navigation mirrors departments.
- Every feature is same-level.
- Search compensates for bad structure.
- Labels mirror database nouns.
- Novices and experts are forced through the same path.
- Empty states do not teach content location.
- Hierarchy is size-only rather than task-based.
