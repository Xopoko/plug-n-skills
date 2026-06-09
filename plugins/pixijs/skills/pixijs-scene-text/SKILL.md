---
name: pixijs-scene-text
description: "Use for PixiJS v8 text rendering: Text, TextStyle, BitmapText, HTMLText, SplitText, SplitBitmapText, dynamic labels, glyph atlas performance, styled markup."
license: MIT
---

Use this for labels, text blocks, bitmap-font text, HTML/SVG text, and split text effects.

## Route

- Standard canvas-rendered styled text: [references/text.md](references/text.md)
- High-performance dynamic text from glyph atlas: [references/bitmap-text.md](references/bitmap-text.md)
- Markup/CSS-style text rendered through SVG: [references/html-text.md](references/html-text.md)
- Character/word/line segmentation: [references/split-text.md](references/split-text.md)
- Split bitmap text: [references/split-bitmap-text.md](references/split-bitmap-text.md)
- Expanded entrypoint notes: [references/details.md](references/details.md)

## Rules

- Use options-object constructors in v8.
- Prefer `BitmapText` for frequently updated numeric/UI text.
- Use `HTMLText` only when markup support is worth its cost and limitations.
- Text objects are leaves; group them in `Container` for composition.
- Cache styles and avoid rebuilding text every frame.

## Common Fixes

- Text migration fails: convert constructor args to options object.
- Dynamic text hurts FPS: switch to `BitmapText` or reduce update frequency.
- Need animated letters/words: use split text variants.
