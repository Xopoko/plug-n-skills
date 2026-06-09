---
name: pixijs-scene-gif
description: "Use for PixiJS v8 animated GIFs: pixi.js/gif import, Assets.load to GifSource, GifSprite playback, autoPlay/loop, currentFrame, animationSpeed, callbacks, clone/destroy."
license: MIT
---

Use this for displaying animated GIF assets as PixiJS sprites.

## Fast Path

```ts
import 'pixi.js/gif';
import { Assets, GifSprite } from 'pixi.js';

const source = await Assets.load('loader.gif');
app.stage.addChild(new GifSprite({ source, autoPlay: true }));
```

## Rules

- Import `pixi.js/gif` before loading GIF assets.
- `Assets.load` returns a `GifSource`; pass it to `GifSprite`.
- Use `play`, `stop`, `currentFrame`, `animationSpeed`, `loop`, and callbacks for playback control.
- Share a `GifSource` when multiple sprites use the same GIF.
- `GifSprite` extends `Sprite`; it is a leaf and should be grouped in a `Container` when needed.

## Deep Reads

- Full GIF options and lifecycle: [references/details.md](references/details.md)
- Spritesheet animation alternative: `pixijs-scene-sprite`
- Asset cache/unload: `pixijs-assets`

## Common Fixes

- GIF loads as a normal texture: import the GIF extension first.
- Need per-frame spritesheet control: use `AnimatedSprite` instead.
- Memory grows after GIF removal: destroy sprites and unload unused assets.
