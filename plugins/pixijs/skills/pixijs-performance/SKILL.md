---
name: pixijs-performance
description: "Use for PixiJS v8 performance: FPS, jank, draw calls, batching, GPU memory, destroy patterns, cacheAsTexture, GCSystem, PrepareSystem, Culler, pooling, resolution."
license: MIT
---

Use this when a PixiJS app is slow, memory-heavy, janky, or leaking resources.

## Triage Order

1. Measure FPS, frame time, draw calls, texture memory, and object counts before changing code.
2. Remove per-frame allocation, `Graphics.clear()` redraw loops, and unnecessary texture creation.
3. Fix batching blockers: many base textures, filters, masks, blend-mode switches, and render groups.
4. Cull offscreen work only when culling cost is lower than rendering cost.
5. Destroy and unload resources deliberately during screen/level transitions.

## Rules

- Static complex vector art: consider `cacheAsTexture`, then turn it off before destroy if needed.
- Dynamic repeated objects: pool containers/sprites; avoid creating/destroying in the hot loop.
- Many simple sprites: use atlases and, when feature tradeoffs fit, `ParticleContainer`.
- Dynamic text: prefer `BitmapText` or reduce text updates.
- GPU upload spikes: use `PrepareSystem` or preload before the object appears.
- Same-tab app recreation: coordinate `app.destroy(...)`, `Assets.unload(...)`, and `releaseGlobalResources`.

## Deep Reads

- Full performance checklist and examples: [references/details.md](references/details.md)
- Assets and atlases: `pixijs-assets`
- Culling and scene structure: `pixijs-scene-core-concepts`, `pixijs-scene-container`
- Custom batchers/shaders: `pixijs-custom-rendering`

## Common Fixes

- Redrawing `Graphics` every frame: animate transforms or move to sprites/mesh.
- Memory leak after scene swap: destroy display objects and unload assets that are no longer referenced.
- Culling makes things slower: remove it for small/simple object counts.
