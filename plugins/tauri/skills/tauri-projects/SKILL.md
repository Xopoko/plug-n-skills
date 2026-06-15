---
name: tauri-projects
description: Start, inspect, scaffold, migrate, or orient Tauri 2 projects. Use when a task mentions creating a Tauri app, adding Tauri to an existing frontend, src-tauri project structure, package-manager selection, framework selection, Tauri 1 to 2 migration, or "what shape is this Tauri repo in?"
---

# Tauri Projects

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.
On Windows PowerShell, set and read this as `$env:PLUGIN_ROOT`; translate shown POSIX-style `$PLUGIN_ROOT/...` paths to the same path under `$env:PLUGIN_ROOT`.

## First Pass

1. Read local instructions, README, package docs, and git status.
2. From the project root, run the plugin probe when possible:

```bash
python3 "$PLUGIN_ROOT/scripts/tauri_project_probe.py" .
```

If the current working directory is not inside the plugin, resolve the script path relative to this skill folder.

3. Inspect `package.json`, lockfiles, `src-tauri/Cargo.toml`,
   `src-tauri/tauri.conf.*`, `src-tauri/capabilities/*`, and
   `src-tauri/src/lib.rs` before editing.

## Scaffolding

- Prefer official package-manager scaffolding such as `pnpm create tauri-app@2`,
  `npm create tauri-app@2`, or `cargo create-tauri-app`; choose by repo/team convention.
- Do not run remote shell installers such as `curl | sh` as the default.
- Treat Rustup, Node, Xcode, Android SDK, WebView/system packages, and mobile
  SDK installation as environment mutations requiring explicit approval.
- For existing frontends, use project-local Tauri CLI initialization and align
  `build.devUrl`, `build.frontendDist`, `beforeDevCommand`, and
  `beforeBuildCommand` with the framework.

## Frontend Choice

- Default to Vite when there is no SSR/SSG requirement.
- For Next.js, Nuxt, SvelteKit, Qwik, or similar frameworks, verify static
  export mode and that `frontendDist` points to generated static assets.
- Do not assume browser-only APIs are available in the Tauri WebView. Check the
  target platform and WebView constraints.

## Migration

For Tauri 1 or Tauri 2 beta migration, check current official Tauri docs before editing. Pay attention to:

- Tauri 2 capability and permission files;
- namespaced `core:*` permissions;
- `@tauri-apps/api` import paths;
- plugin package/crate version alignment;
- `src/lib.rs` mobile entry point and desktop `main.rs` split;
- platform-specific config files.

## Verification

Use commands from the repo, not templates. Common checks:

```bash
cargo check --manifest-path src-tauri/Cargo.toml
cargo test --manifest-path src-tauri/Cargo.toml
pnpm tauri dev
pnpm tauri build
```

Use `npm`, `yarn`, `bun`, `deno`, or `cargo tauri` equivalents when the probe
shows those are local conventions.
