---
name: pixijs-filters
description: "Use for PixiJS v8 filters and visual effects: BlurFilter, ColorMatrixFilter, DisplacementFilter, NoiseFilter, Filter.from, padding/resolution, pixi-filters community effects."
license: MIT
---

Use this for applying built-in, custom, or community filters to display objects.

## Fast Path

```ts
import { BlurFilter } from 'pixi.js';

sprite.filters = [new BlurFilter({ strength: 6 })];
```

## Rules

- Filters render through offscreen passes; use them deliberately on small subtrees or cached outputs.
- Increase `padding` when an effect extends beyond object bounds.
- Use `ColorMatrixFilter` for many color operations before writing custom shaders.
- Use `Filter.from(...)` for custom fragment/vertex filter code.
- Import community filters from `pixi-filters/*`, not old `@pixi/filter-*` packages.
- Check filter resolution and multisample settings when quality or speed is off.

## Deep Reads

- Full filter examples and built-in/community notes: [references/details.md](references/details.md)
- Custom shader resources: `pixijs-custom-rendering`
- Performance tradeoffs: `pixijs-performance`
- Blend modes: `pixijs-blend-modes`

## Common Fixes

- Effect clipped: add filter padding.
- Performance drop: reduce filtered area, cache static output, or remove stacked passes.
- Old package import: use `pixi-filters` or `pixi.js` exports.
