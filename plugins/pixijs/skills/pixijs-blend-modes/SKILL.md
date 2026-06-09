---
name: pixijs-blend-modes
description: "Use for PixiJS v8 blend modes and compositing: normal/add/multiply/screen/erase/min/max, advanced-blend-modes, overlay, color-burn, hard-light, alpha behavior."
license: MIT
---

Use this for display-object compositing with built-in or advanced blend modes.

## Rules

- Set `displayObject.blendMode` for standard modes such as `normal`, `add`, `multiply`, `screen`, `erase`, `min`, and `max`.
- Import `pixi.js/advanced-blend-modes` before using advanced modes.
- Test blend output against the real renderer background; alpha and premultiply affect perceived color.
- Blend modes can affect batching and performance; group or cache when stable.
- Use filters when the effect needs more than source/destination compositing.

## Deep Reads

- Full mode list, examples, and advanced imports: [references/details.md](references/details.md)
- Color handling: `pixijs-color`
- Filters and custom effects: `pixijs-filters`, `pixijs-custom-rendering`

## Common Fixes

- Advanced mode has no effect: import the side-effect extension.
- Output differs from design tool: check premultiplied alpha and background color.
- Performance drops: reduce state changes or cache static groups.
