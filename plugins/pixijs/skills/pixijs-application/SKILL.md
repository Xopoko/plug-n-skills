---
name: pixijs-application
description: "Use for PixiJS v8 Application setup, app.init, renderer/canvas/screen/stage, resizeTo, ticker/sharedTicker, CullerPlugin, app.start/stop/destroy, releaseGlobalResources."
license: MIT
---

Use this for creating, configuring, resizing, starting, stopping, or destroying a PixiJS `Application`.

## Fast Path

```ts
import { Application } from 'pixi.js';

const app = new Application();
await app.init({ width: 800, height: 600, background: 0x1099bb });
document.body.appendChild(app.canvas);
```

## Rules

- v8 requires `new Application()` plus async `await app.init(options)`. Do not pass options to the constructor.
- Use `app.canvas`, not `app.view`; use `app.stage`, `app.renderer`, and `app.screen` for the main scene.
- Use `resizeTo` for browser/container resizing, then rely on the resize plugin instead of manual canvas CSS hacks.
- Use `app.ticker.add((ticker) => ...)`; read `ticker.deltaTime`, `ticker.deltaMS`, or `ticker.FPS`.
- Use `app.destroy(rendererDestroyOptions, stageDestroyOptions)`. For same-tab re-init leaks or stale textures, include `releaseGlobalResources: true` where appropriate.
- `CullerPlugin` only helps when containers are marked `cullable`; add `cullArea` when bounds are expensive.
- `app.domContainerRoot` belongs next to `app.canvas` when using `DOMContainer` overlays.

## Related Reads

- Deep application details: [references/details.md](references/details.md)
- Full `ApplicationOptions`: [references/application-options.md](references/application-options.md)
- Render loop: `pixijs-ticker`
- Stage and children: `pixijs-scene-container`
- Non-browser runtime: `pixijs-environments`

## Common Fixes

- Constructor options in v7 style: move them into `await app.init(...)`.
- Missing canvas: append `app.canvas` after init.
- Recreated app flickers: destroy renderer/stage resources before creating the next app.
