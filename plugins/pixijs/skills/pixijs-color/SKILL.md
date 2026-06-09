---
name: pixijs-color
description: "Use for PixiJS v8 Color: hex/CSS/rgb/hsl inputs, toHex/toNumber/toArray/toRgbaString, multiply, premultiply, alpha, tint, color-space conversion."
license: MIT
---

Use this for color parsing, conversion, tinting, alpha, premultiply, and color math.

## Fast Path

```ts
import { Color } from 'pixi.js';

const color = new Color('#3498db');
sprite.tint = color.toNumber();
```

## Rules

- `Color` accepts numeric hex, CSS strings/names, RGB/HSL-like objects, arrays, and typed arrays.
- Use `toNumber`, `toHex`, `toArray`, `toRgbArray`, and `toRgbaString` for output format changes.
- Use Pixi color helpers when handling premultiplied alpha or GPU-facing values.
- Keep alpha handling explicit; tint and alpha are separate display-object concerns.

## Deep Reads

- Full input/output formats, conversion methods, premultiply behavior, and examples: [references/details.md](references/details.md)
- Blend/compositing: `pixijs-blend-modes`
- Filters that alter color: `pixijs-filters`

## Common Fixes

- CSS string not accepted in a numeric-only field: convert with `new Color(value).toNumber()`.
- Washed output: verify alpha and premultiply expectations.
- Repeated conversions in a loop: cache numeric color values.
