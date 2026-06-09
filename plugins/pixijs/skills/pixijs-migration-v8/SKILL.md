---
name: pixijs-migration-v8
description: "Use for PixiJS v7 to v8 migration: app.init, pixi.js package imports, Graphics fill/stroke/cut, Texture/BaseTexture changes, events, ticker, shaders, filters, adapters."
license: MIT
---

Use this when upgrading v7 code or diagnosing code that broke after moving to PixiJS v8.

## First Pass Checklist

- Replace `new Application(options)` with `new Application()` plus `await app.init(options)`.
- Replace core `@pixi/*` package imports with `pixi.js` imports.
- Replace `app.view` with `app.canvas`.
- Convert Graphics to shape-then-style: `rect(...).fill(...)`, `stroke(...)`, `cut()`.
- Replace `DisplayObject` inheritance with `Container` or a concrete renderable type.
- Replace `interactive = true` with `eventMode = 'static'` or `'dynamic'`.
- Update ticker callbacks to receive the `Ticker` object.
- Replace old shader/filter constructors with v8 `{ gl, gpu, resources }` and typed uniforms.
- Replace `settings.ADAPTER` with `DOMAdapter.set(...)`.
- Audit texture, mesh, text, particle, enum, and culling changes before shipping.

## Deep Reads

- Full migration checklist and code examples: [references/details.md](references/details.md)
- Graphics API: `pixijs-scene-graphics`
- Application init: `pixijs-application`
- Events: `pixijs-events`
- Shaders/filters: `pixijs-custom-rendering`, `pixijs-filters`

## Common Fixes

- `beginFill`, `drawRect`, `lineStyle`: use `Graphics` v8 methods.
- `Texture.from(url)`: load with `Assets.load(url)` first.
- `BaseTexture` assumptions: inspect v8 `TextureSource` behavior.
- Old enum constants: use the new string values where v8 expects strings.
