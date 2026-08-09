---
name: pixijs-accessibility
description: "PixiJS v8 AccessibilitySystem configures screen-reader overlays, keyboard focus, roles, accessibleTitle, accessibleHint, tabIndex, and activation behavior."
license: MIT
---

Use this when PixiJS content needs screen reader, keyboard, role, or focus support.

## Rules

- Enable and configure the `AccessibilitySystem` at the application/renderer level when needed.
- Add per-object accessibility metadata such as title, hint, role, and tab index.
- Keep keyboard focus order intentional; do not mirror every decorative object into accessibility overlays.
- Pair accessible canvas objects with equivalent semantic HTML when complex interaction exceeds Pixi's accessibility layer.
- Test with keyboard and a screen reader, not only visual inspection.

## Deep Reads

- Full accessibility options and per-container examples: [references/details.md](references/details.md)
- DOM overlays for semantic UI: `pixijs-scene-dom-container`
- Input handling: `pixijs-events`

## Common Fixes

- Screen reader sees noise: mark only meaningful interactive or informative objects.
- Keyboard focus order is wrong: set tab order deliberately.
- Overlay position wrong: check scene transforms and renderer resize behavior.
