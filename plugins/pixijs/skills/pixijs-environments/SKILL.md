---
name: pixijs-environments
description: "Use for PixiJS v8 environments outside normal browser pages: Web Workers, OffscreenCanvas, Node/SSR, CSP, DOMAdapter, BrowserAdapter, WebWorkerAdapter, unsafe-eval."
license: MIT
---

Use this for non-standard runtimes: workers, OffscreenCanvas, Node/SSR, or strict CSP.

## Rules

- Use `DOMAdapter.set(...)` to select or provide the environment adapter before creating renderer/application objects.
- Use `WebWorkerAdapter` and OffscreenCanvas patterns for worker rendering.
- In Node/SSR, avoid touching browser globals unless an adapter or mock is installed.
- For strict CSP, avoid code paths that require dynamic evaluation; only use `pixi.js/unsafe-eval` when policy allows it and the project accepts the tradeoff.
- Keep environment setup near the application bootstrap.

## Deep Reads

- Full adapter and runtime examples: [references/details.md](references/details.md)
- Standard application setup: `pixijs-application`
- Migration from `settings.ADAPTER`: `pixijs-migration-v8`

## Common Fixes

- `document`/`window` missing: set the right adapter before init.
- Worker canvas fails: verify OffscreenCanvas transfer and worker-side imports.
- CSP error: remove unsafe-eval-dependent imports or explicitly choose the unsafe build only when allowed.
