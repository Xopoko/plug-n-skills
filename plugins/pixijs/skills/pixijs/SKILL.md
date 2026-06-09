---
name: pixijs
description: "Use first for PixiJS v8 tasks. Router for Application/app.init, scene graph Container/Sprite/Graphics/Text/Mesh, Assets, events, Ticker, filters, shaders, performance, migration, and create-pixi."
license: MIT
---

Entry router for PixiJS v8 work. Load this first, then load the narrow skill that matches the task.

## Route

| Task signal | Load |
|---|---|
| `Application`, `app.init`, canvas, renderer, resize, stage, destroy | `pixijs-application` |
| renderers, render loop internals, WebGL/WebGPU/Canvas fallback | `pixijs-core-concepts` |
| new project, `create-pixi`, Vite/React templates | `pixijs-create` |
| workers, OffscreenCanvas, SSR, CSP, `DOMAdapter` | `pixijs-environments` |
| v7 upgrade, `@pixi/*`, `beginFill`, `DisplayObject`, `BaseTexture` | `pixijs-migration-v8` |
| scene graph model, transforms, render order, masks, layers | `pixijs-scene-core-concepts` |
| `Container`, children, bounds, z-order, coordinates, destroy | `pixijs-scene-container` |
| `Sprite`, `AnimatedSprite`, `NineSliceSprite`, `TilingSprite` | `pixijs-scene-sprite` |
| `Graphics`, paths, `fill`, `stroke`, gradients, SVG | `pixijs-scene-graphics` |
| `Text`, `BitmapText`, `HTMLText`, split text | `pixijs-scene-text` |
| `Mesh`, custom geometry, rope, plane, perspective mesh | `pixijs-scene-mesh` |
| many lightweight sprites, `ParticleContainer`, `Particle` | `pixijs-scene-particle-container` |
| HTML overlays on canvas, `DOMContainer`, `pixi.js/dom` | `pixijs-scene-dom-container` |
| animated GIFs, `GifSprite`, `GifSource`, `pixi.js/gif` | `pixijs-scene-gif` |
| HTML element snapshots as textures, `HTMLSource` | `pixijs-html-source` |
| `Assets`, bundles, manifests, cache, fonts, spritesheets | `pixijs-assets` |
| `Color`, hex/rgb/hsl conversion, premultiply, tint | `pixijs-color` |
| pointer/mouse/touch/wheel input, `eventMode`, drag, hit areas | `pixijs-events` |
| `Point`, `Matrix`, `Rectangle`, shapes, coordinate conversion | `pixijs-math` |
| per-frame logic, `Ticker`, delta values, FPS caps | `pixijs-ticker` |
| screen reader or keyboard navigation | `pixijs-accessibility` |
| blend modes and `pixi.js/advanced-blend-modes` | `pixijs-blend-modes` |
| shaders, uniforms, custom filters, custom batchers | `pixijs-custom-rendering` |
| visual effects, built-in/community filters | `pixijs-filters` |
| FPS, draw calls, GPU memory, culling, GC, pooling | `pixijs-performance` |

## Fallback

When no sub-skill covers a named class, option, or API:

1. Fetch `https://pixijs.download/release/docs/llms.txt`.
2. Fetch the linked `.html.md` page for the exact symbol.
3. Use [references/index.md](references/index.md) only when you need the long trigger index.
