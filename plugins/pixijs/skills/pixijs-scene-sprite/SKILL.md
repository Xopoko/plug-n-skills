---
name: pixijs-scene-sprite
description: "PixiJS v8 sprites render Sprite, AnimatedSprite, NineSliceSprite, and TilingSprite with texture/anchor/tint for animation, scalable panels, and repeating backgrounds."
license: MIT
---

Use this for drawing image-based scene objects.

## Route

- Plain image display: [references/sprite.md](references/sprite.md)
- Frame animation from textures/spritesheets: [references/animated-sprite.md](references/animated-sprite.md)
- Scalable UI panels: [references/nineslice-sprite.md](references/nineslice-sprite.md)
- Repeating or scrolling textures: [references/tiling-sprite.md](references/tiling-sprite.md)
- Expanded entrypoint notes: [references/details.md](references/details.md)

## Rules

- Load remote textures with `Assets.load` before creating sprites.
- Use `anchor`, `scale`, `rotation`, `tint`, and `alpha` for cheap visual changes.
- Sprites are leaves; group them in a `Container` when you need children or shared transforms.
- Use `AnimatedSprite` for spritesheet animation, not GIF playback.
- Use `NineSliceSprite` for resizable panels and `TilingSprite` for repeated backgrounds.

## Common Fixes

- `Texture.from(url)` fails to load: use `Assets.load(url)` first.
- Child added to sprite: wrap sprite and child in a `Container`.
- Updated texture frame not reflected: update texture UVs and notify the sprite as required.
