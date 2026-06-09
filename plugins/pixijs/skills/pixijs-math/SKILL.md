---
name: pixijs-math
description: "Use for PixiJS v8 math: Point, ObservablePoint, Matrix, Rectangle, Circle, Ellipse, Polygon, Triangle, hit testing, bounds, toGlobal/toLocal, math-extras."
license: MIT
---

Use this for coordinates, affine transforms, geometry shapes, hit tests, and layout rectangles.

## Fast Path

```ts
import { Point, Rectangle } from 'pixi.js';

const local = container.toLocal(event.global);
const hit = new Rectangle(0, 0, 120, 80).contains(local.x, local.y);
```

## Rules

- Import math classes from `pixi.js`, not `@pixi/math`.
- Use `Container.toGlobal` / `toLocal` for scene coordinates; use `Matrix.apply` / `applyInverse` for raw affine transforms.
- `ObservablePoint` notifies owners on `set`, `copyFrom`, and property mutation; avoid bypassing its setters.
- `Rectangle`, `Circle`, `Ellipse`, `Polygon`, `RoundedRectangle`, and `Triangle` are useful for `hitArea`, culling, bounds, and layout.
- Import `pixi.js/math-extras` before using extended vector/rectangle helpers.
- Treat reused temporary objects as mutable; copy values if you need stable snapshots.

## Deep Reads

- Full examples for `Point`, `Matrix`, shapes, constants, and math-extras: [references/details.md](references/details.md)
- Transform model: `pixijs-scene-core-concepts/references/transforms.md`
- Event hit areas: `pixijs-events`

## Common Fixes

- Wrong package: replace `@pixi/math` imports with `pixi.js`.
- Extended method missing: add `import 'pixi.js/math-extras';` once before use.
- Hit test in wrong space: convert event global coordinates into the object's local space first.
