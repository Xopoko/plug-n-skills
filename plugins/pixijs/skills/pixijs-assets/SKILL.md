---
name: pixijs-assets
description: "Use for PixiJS v8 Assets: Assets.init/load/add/unload, bundles, manifests, cache, onProgress, background loading, spritesheets, video, SVG, fonts, compressed textures, parser selection."
license: MIT
---

Use this for loading, resolving, caching, unloading, or preloading PixiJS assets.

## Fast Path

```ts
import { Assets, Sprite } from 'pixi.js';

await Assets.init({ basePath: '/assets' });
const texture = await Assets.load('bunny.png');
app.stage.addChild(new Sprite(texture));
```

## Rules

- Load remote files with `Assets.load(...)`; `Texture.from(url)` no longer performs network loading.
- Register aliases with object form: `Assets.add({ alias: 'bunny', src: 'bunny.png' })`.
- Use bundles/manifests when asset groups are known up front; use `backgroundLoad` for future screens.
- Use `onProgress` in load options for UI progress, and unload unused level assets to release memory.
- Use `parser` only to force a loader when extension/MIME inference is wrong.
- Import required extension side effects before loading special formats: bitmap fonts, GIF, SVG/graphics, compressed textures, video as needed.

## Reference Map

- Deep asset details and parser list: [references/details.md](references/details.md)
- Bundles: [references/bundles.md](references/bundles.md)
- Manifests: [references/manifests.md](references/manifests.md)
- Caching/unload: [references/caching.md](references/caching.md)
- Progress/background: [references/progress.md](references/progress.md), [references/background.md](references/background.md)
- Spritesheets, SVG, video, fonts, GIF, compressed textures, resolution: load the matching file in `references/`.

## Common Fixes

- Broken v7 `Assets.add('id', 'url')`: rewrite to object form.
- Level transitions leak memory: call `Assets.unload(...)` for assets no longer needed.
- Wrong parser selected: pass `data` or explicit `parser` after checking the format reference.
