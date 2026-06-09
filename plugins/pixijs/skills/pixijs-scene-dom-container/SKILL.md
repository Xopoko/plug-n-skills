---
name: pixijs-scene-dom-container
description: "Use for PixiJS v8 DOMContainer overlays: HTML elements attached to scene nodes, pixi.js/dom import, element/anchor options, CSS transforms, visibility and resize sync."
license: MIT
---

Use this when real DOM elements must visually follow PixiJS scene nodes above the canvas.

## Rules

- Import `pixi.js/dom` before using `DOMContainer`.
- Append `app.domContainerRoot` next to `app.canvas` so DOM overlays can be placed correctly.
- Use `DOMContainer` for live HTML interaction; use `HTMLSource` only for texture snapshots.
- Keep CSS and Pixi transforms in sync through the scene graph; test resize and visibility changes.
- Do not expect DOM elements to participate in WebGL batching, filters, masks, or canvas extraction.

## Deep Reads

- Full DOMContainer setup and limitations: [references/details.md](references/details.md)
- Application root: `pixijs-application`
- HTML snapshots as textures: `pixijs-html-source`

## Common Fixes

- Element not visible: check `pixi.js/dom` import and `app.domContainerRoot` placement.
- Pointer layering issue: inspect CSS `pointer-events` and z-order.
- Need filtered DOM: render it as a texture snapshot instead, accepting experimental limits.
