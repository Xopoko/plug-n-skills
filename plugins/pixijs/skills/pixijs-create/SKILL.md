---
name: pixijs-create
description: "Use for PixiJS v8 project scaffolding with create-pixi: npm/yarn/pnpm/bun create commands, Vite templates, React template, non-interactive flags, existing project setup."
license: MIT
---

Use this for creating a new PixiJS project or adding PixiJS to a frontend project.

## Fast Path

```bash
npm create pixi.js@latest my-pixi-app
cd my-pixi-app
npm install
npm run dev
```

## Rules

- Prefer the official `create-pixi` flow for new projects.
- Choose the template that matches the app stack; do not add React wrappers unless the project needs React.
- For existing apps, install `pixi.js` directly and wire `Application` lifecycle into the host framework.
- Verify the dev server renders a nonblank canvas after setup.
- Keep package-manager commands consistent with the existing repo.

## Deep Reads

- Full CLI commands, package-manager variants, templates, and non-interactive setup: [references/details.md](references/details.md)
- Application setup after scaffolding: `pixijs-application`
- Assets and bundling: `pixijs-assets`

## Common Fixes

- Blank first screen: check `await app.init(...)`, canvas append, and dev-server asset paths.
- Wrong package manager: use the repo lockfile as the source of truth.
- React lifecycle leak: destroy the app on component unmount.
