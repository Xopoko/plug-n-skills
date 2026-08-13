---
name: visual-explanation
description: "Visual explanations for coding and technical work: choose the smallest useful table, tree, pseudocode, call flow, state view, structural diff, or wireframe. Not for UI screenshot audits, data charts, image assets, or architecture recovery."
---

# Visual Explanation

Turn a relationship-heavy technical explanation into the smallest visual form
that makes the relevant structure easier to understand. Keep prose when a
sentence or short list is already clearer.

## Selection Card

Use this skill for an explicit request to show the current technical topic
visually, or when mappings, branching effects, dependent steps, state changes,
hierarchy, ownership, layout, or a structural delta are hard to follow in prose.

Inputs: the question to clarify, inspected evidence or supplied assertions, the
target audience, and the host's rendering capabilities.

Do not use it for a simple fact, one-step action, decorative diagram, general
data visualization, UI screenshot audit, generated image asset, or codebase
architecture recovery.

## Representation-Fit Gate

1. Name the exact comparison, relationship, sequence, state change, hierarchy,
   or layout the reader must understand.
2. If concise prose is equally clear, stop and use concise prose.
3. Choose one smallest useful form. Add a second view only when it answers a
   different necessary question.
4. Put the visual next to one short takeaway. Do not repeat the whole visual in
   prose.

## Form Selector

| Need | Prefer |
| --- | --- |
| Repeated-field mapping or comparison | Table |
| Hierarchy, ownership, nesting, component shape, or shallow file responsibility | Tree |
| Branching logic or algorithm | Pseudocode |
| Caller/callee structure without chronology | Call tree |
| Runtime order or dependent steps | Short call flow or sequence diagram |
| State transitions | State table, short timeline, or state diagram |
| Before/after structural change | Focused structural diff |
| Interface or data shape | Types or signatures |
| Screen or spatial layout | Wireframe |

Use Mermaid only when it clarifies cross-links or transitions better than a
text form and the host can render it. Do not create standalone HTML, viewers,
servers, hooks, or feedback runtimes in this skill; route an explicitly
requested rich artifact to a dedicated artifact workflow with its own path,
lifecycle, sanitization, inspection, and fallback contracts.

## Truth Boundary

- Label a view `Observed` only when it describes inspected code, traces, or
  other verified evidence. Bind important nodes and edges to adjacent file
  paths, symbols, trace events, or evidence references.
- Label unverified user-supplied material `Given` or `Reported`. Preserve what
  was supplied without elevating it to observed behavior.
- Label a view `Proposed` when it describes a design. State assumptions and do
  not present it as current behavior.
- Label an inference without adequate verification `Assumed`. In a mixed view,
  make the `Observed` / `Given` / `Proposed` / `Assumed` boundary explicit
  before the visual. Do not let plausible layout substitute for evidence.
- When provenance and lifecycle differ, state both, for example
  `Given (Proposed design)` or `Observed (Current behavior)`.
- Omit or redact secrets, credentials, private payloads, and unrelated source
  details. Escape untrusted labels in generated artifacts.

## Rendering And Accessibility

- Prefer portable Markdown and text forms. If Mermaid support is unknown or
  absent, provide a readable text fallback rather than a broken diagram.
- Give Mermaid diagrams a specific `accTitle` and `accDescr`.
- Use labels, symbols, line styles, or position in addition to color. Never make
  color the only carrier of meaning.
- Keep labels readable and details adjacent to the element they explain. Split
  a dense view instead of shrinking text or adding decorative noise.
- Preserve copyable code, paths, types, and signatures when exact syntax is the
  point.

## Output Contract

When a visual is justified, return one smallest useful visual first and one
short takeaway after it. State `Observed`, `Given`, `Proposed`, or `Assumed`
whenever that distinction could be ambiguous. When no visual materially helps,
return concise prose and do not announce a missing diagram.

## Adjacent Routes

- Use `visual-communication` for hierarchy, readability, capture-state, or
  test-harness findings in UI screenshots, golden images, and visual diffs.
- Use `architecture-intelligence` to recover or audit codebase architecture;
  use this skill only to present an already-supported result more clearly.
- Route quantitative charts and analytical dashboards to data visualization.
- Route illustrations, icons, and other image assets to image generation.
- If `i-have-adhd` was explicitly activated, it continues to own pacing,
  progress, time boxes, and the next-action format; this skill changes only the
  explanatory representation.
