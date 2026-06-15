---
name: tauri-debug-testing
description: Debug, test, or stabilize Tauri 2 apps, including Rust compile/runtime errors, frontend API mocks, permissions failures, dev/build mismatches, WebDriver, CI checks, logs, DevTools, and platform-specific test gaps.
---

# Tauri Debug And Testing

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.
On Windows PowerShell, set and read this as `$env:PLUGIN_ROOT`; translate shown POSIX-style `$PLUGIN_ROOT/...` paths to the same path under `$env:PLUGIN_ROOT`.

Use this skill when a Tauri app fails to compile, launch, call native APIs,
load frontend assets, pass tests, or behave consistently across dev/build.

## Triage Split

Classify the failure before changing code:

- Frontend build/test failure.
- Rust compile/test failure.
- Tauri config or capability failure.
- Plugin registration/import mismatch.
- Dev server vs packaged static asset mismatch.
- Platform WebView or OS dependency issue.
- Signing, updater, or distribution issue.

Run:

```bash
python3 "$PLUGIN_ROOT/scripts/tauri_project_probe.py" .
```

## Common Checks

```bash
cargo check --manifest-path src-tauri/Cargo.toml
cargo test --manifest-path src-tauri/Cargo.toml
pnpm test
pnpm build
pnpm tauri dev
pnpm tauri build
```

Use the package manager and scripts detected in the repo.

## Mocking Frontend Tauri APIs

Use `@tauri-apps/api/mocks` for frontend unit tests around wrappers:

```ts
import { mockIPC, clearMocks } from "@tauri-apps/api/mocks";
import { afterEach, expect, it } from "vitest";
import { invoke } from "@tauri-apps/api/core";

afterEach(() => clearMocks());

it("mocks a command", async () => {
  mockIPC((cmd, args) => {
    if (cmd === "add") return Number(args.a) + Number(args.b);
    throw new Error(`unexpected command: ${cmd}`);
  });

  await expect(invoke("add", { a: 2, b: 3 })).resolves.toBe(5);
});
```

## WebDriver

Use WebDriver when the native shell is part of the risk: windows, dialogs,
menus, permissions, packaged launch, or cross-process UI flows. Tauri WebDriver
coverage is practical on Linux and Windows; macOS WKWebView has tooling limits,
so use other proof there.

## Debugging Discipline

- Do not fix a missing permission by adding broad capabilities.
- Do not ignore Tauri package version mismatches unless official docs and the
  repo prove the mismatch warning is false.
- Capture exact error text and command output. Tauri failures are often caused
  by one missing config/key/import path.
- Verify the same path the user cares about: dev mode, packaged app, CI, or
  target platform.
