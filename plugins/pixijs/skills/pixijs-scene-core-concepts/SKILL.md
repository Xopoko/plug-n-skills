---
name: pixijs-scene-core-concepts
description: "Use for PixiJS v8 scene graph concepts: containers vs leaves, transforms, local/world coordinates, render order, masks, RenderLayer, render groups, culling, scene management."
license: MIT
---

Use this for the mental model of the PixiJS scene graph before choosing a concrete scene-object skill.

## Model

- `app.stage` is the root `Container`.
- Containers hold children; renderable leaves such as `Sprite`, `Graphics`, `Text`, and `Mesh` do not hold children.
- Every node has local transforms that compose into world transforms.
- Render order is parent traversal plus child order, `sortableChildren/zIndex`, layers, masks, filters, and render groups.
- Bounds, masks, culling, and coordinate conversion depend on this hierarchy.

## Route Deeper

- Constructor options: [references/constructor-options.md](references/constructor-options.md)
- Hierarchy operations: [references/container-hierarchy.md](references/container-hierarchy.md)
- Transforms and coordinates: [references/transforms.md](references/transforms.md)
- Render order/layers: [references/layers.md](references/layers.md)
- Masks: [references/masking.md](references/masking.md)
- Render groups: [references/render-groups.md](references/render-groups.md)
- Scene management: [references/scene-management.md](references/scene-management.md)
- Expanded entrypoint notes: [references/details.md](references/details.md)

## Common Fixes

- Need a group: use `Container`, not `Sprite`/`Graphics`/`Text` as a parent.
- Wrong position math: identify the local space first, then use `toLocal` / `toGlobal`.
- Overusing render groups: reserve them for independently moved large subtrees or layering needs.
