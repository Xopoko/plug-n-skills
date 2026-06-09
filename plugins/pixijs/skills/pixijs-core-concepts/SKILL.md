---
name: pixijs-core-concepts
description: "Use for PixiJS v8 renderer concepts: Application/Renderer relationship, WebGL/WebGPU/Canvas selection, render loop, systems, pipes, environment adapters, renderer fallback."
license: MIT
---

Use this for renderer-level understanding before debugging low-level render behavior.

## Model

- `Application` owns the high-level app lifecycle; the renderer draws the stage into a canvas.
- PixiJS can use WebGL, WebGPU, or Canvas fallback depending on build, options, and environment.
- The render loop is usually driven by the ticker plugin, but rendering can be manual.
- Renderer systems and pipes handle specialized work such as textures, batches, masks, filters, and extraction.
- Environment adapters decide how browser, worker, or headless primitives are provided.

## Deep Reads

- Renderer selection and renderer classes: [references/renderers.md](references/renderers.md)
- Render-loop behavior: [references/render-loop.md](references/render-loop.md)
- Expanded entrypoint notes: [references/details.md](references/details.md)
- Application lifecycle: `pixijs-application`
- Custom systems/shaders: `pixijs-custom-rendering`

## Common Fixes

- Need normal app setup: use `pixijs-application` first.
- Manual render loop conflicts with ticker: decide who owns render timing.
- Backend-specific issue: identify WebGL vs WebGPU vs Canvas before patching.
