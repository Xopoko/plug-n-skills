---
name: pixijs-html-source
description: "Use for PixiJS v8 experimental HTMLSource and ElementImageSource: render DOM/HTML snapshots as textures, pixi.js/html-source, requestPaint, feature detection, fallbacks."
license: MIT
---

Use this for the experimental browser path that turns HTML/DOM elements into PixiJS textures.

## Rules

- Import the extension side effect before use: `import 'pixi.js/html-source';`.
- Feature-detect browser support; this depends on experimental HTML-in-Canvas behavior and needs fallbacks.
- Use `HTMLSource` / `ElementImageSource` when you need a rendered DOM snapshot as a texture, not normal interactive DOM overlay.
- Call `requestPaint` / update hooks when DOM content changes and the texture must refresh.
- For live HTML UI above the canvas, prefer `DOMContainer` instead of texture snapshots.

## Deep Reads

- Full setup, limitations, update flow, and fallback patterns: [references/details.md](references/details.md)
- DOM overlays: `pixijs-scene-dom-container`
- Assets and texture lifecycle: `pixijs-assets`

## Common Fixes

- Blank texture: check feature detection, extension import, and whether the element is paintable.
- Expected live interactivity: use DOM overlay, not an HTML snapshot texture.
- Stale texture: request a repaint after DOM changes.
