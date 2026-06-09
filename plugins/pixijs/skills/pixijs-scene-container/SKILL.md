---
name: pixijs-scene-container
description: "Use for PixiJS v8 Container: addChild/removeChild, transforms, sortableChildren/zIndex, boundsArea, culling, render groups, masks, coordinate conversion, destroy."
license: MIT
---

Use this for grouping display objects, managing children, transforms, bounds, z-order, culling, and lifecycle.

## Fast Path

```ts
import { Container, Sprite } from 'pixi.js';

const group = new Container({ label: 'enemy-layer', sortableChildren: true });
group.addChild(sprite);
group.position.set(100, 80);
app.stage.addChild(group);
```

## Rules

- `Container` is the scene-graph node that can have children; `Sprite`, `Graphics`, `Text`, and `Mesh` are leaves.
- Use `addChild`, `addChildAt`, `removeChild`, `removeChildren`, `swapChildren`, and `setChildIndex` for hierarchy changes.
- Use `zIndex` only when the parent has `sortableChildren = true`; otherwise child order is insertion order.
- Use `position`, `scale`, `rotation`, `pivot`, `skew`, and `alpha` on containers instead of redrawing children.
- Use `toGlobal` / `toLocal` for coordinate conversion.
- Set `boundsArea` or `cullArea` when automatic bounds are too expensive.
- Use `destroy({ children: true })` only when children should be destroyed too.

## Deep Reads

- Full Container API examples: [references/details.md](references/details.md)
- Core scene references: `pixijs-scene-core-concepts/references/constructor-options.md`, `container-hierarchy.md`, `transforms.md`, `render-groups.md`, `masking.md`
- Performance: `pixijs-performance`

## Common Fixes

- Adding children to a leaf: wrap the leaf in a `Container`.
- `zIndex` has no effect: enable `sortableChildren` on the parent.
- Wrong pointer math: convert from global to local before hit testing.
