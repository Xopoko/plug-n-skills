---
name: pixijs-scene-graphics
description: "Use for PixiJS v8 Graphics, GraphicsContext, vector shapes and paths: rect/circle/poly, moveTo/lineTo/arc, fill/stroke/cut, gradients, patterns, SVG import/export, hit testing."
license: MIT
---

Use this for vector drawing with `Graphics` and reusable `GraphicsContext` instructions.

## Fast Path

```ts
import { Graphics } from 'pixi.js';

const g = new Graphics()
  .rect(10, 10, 200, 100)
  .fill({ color: 0x3498db, alpha: 0.8 })
  .stroke({ width: 3, color: 0x2c3e50 });

app.stage.addChild(g);
```

## Rules

- v8 is shape-then-style: call `rect`, `circle`, `poly`, `moveTo`, `lineTo`, etc., then `fill()` and/or `stroke()`.
- Use `cut()` for holes after drawing the hole path; old `beginHole/endHole` is v7 API.
- Share stable geometry with `const ctx = new GraphicsContext(...); new Graphics(ctx)`.
- Do not clear and redraw every frame unless the shape really changes; prefer transforms, sprites, meshes, or `cacheAsTexture`.
- `Graphics` is a leaf. Group it in a `Container`; do not add children to it.
- Use drawing transforms (`translateTransform`, `rotateTransform`, `setTransform`, `save`, `restore`) only for geometry creation, not scene placement.
- Convert pointer coordinates to local space before `containsPoint`.

## Deep Reads

- Full shapes, gradients, patterns, SVG, transforms, and context utilities: [references/details.md](references/details.md)
- Scene graph basics: `pixijs-scene-core-concepts`
- Grouping and lifecycle: `pixijs-scene-container`
- Performance choices: `pixijs-performance`

## Common Fixes

- `beginFill/drawRect/endFill`: replace with `rect(...).fill(...)`.
- `lineStyle`: replace with `stroke({ width, color, ... })`.
- `GraphicsGeometry`: replace with `GraphicsContext`.
- Nested display objects: wrap graphics and children in a `Container`.
