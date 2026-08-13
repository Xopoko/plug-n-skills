---
name: tauri-config-security
description: Tauri 2 configuration and security review for tauri.conf, capabilities, permissions, CSP, scoped filesystem/network/shell access, window labels, plugin permissions, and frontend-exposed native APIs.
---

# Tauri Config And Security

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use this skill when changing `tauri.conf.json`, optional `tauri.conf.json5` or
`Tauri.toml`, `src-tauri/capabilities/*`, permissions, CSP, plugin access, or
any frontend-callable native API.

## Security Baseline

- Every frontend-accessible native API needs an explicit permission story.
- Grant the minimum permission to the minimum window/webview label.
- Scope filesystem, shell, HTTP, opener, deep-link, and sidecar access.
- Never add broad `$HOME/**`, unrestricted shell, or unbounded network access as
  a convenience fix.
- Do not print, move, commit, or invent signing keys, tokens, `.env` values,
  cookies, Keychain data, or updater private keys.

## Files To Inspect

```bash
python3 "$PLUGIN_ROOT/scripts/tauri_project_probe.py" .
```

Then inspect:

- `src-tauri/tauri.conf.json`; `tauri.conf.json5` requires the `config-json5`
  Cargo feature, and `Tauri.toml` requires `config-toml`;
- JSON platform configs such as `tauri.macos.conf.json`,
  `tauri.windows.conf.json`, `tauri.linux.conf.json`,
  `tauri.android.conf.json`, `tauri.ios.conf.json`;
- when the TOML format is active, the matching names are
  `Tauri.macos.toml`, `Tauri.windows.toml`, `Tauri.linux.toml`,
  `Tauri.android.toml`, and `Tauri.ios.toml`;
- `src-tauri/capabilities/*.json` or `*.toml`;
- `src-tauri/Cargo.toml`;
- Rust window creation labels and plugin registration.

## Capability Pattern

Prefer file-based capabilities under `src-tauri/capabilities/`:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "main-window",
  "description": "Main window permissions",
  "windows": ["main"],
  "permissions": [
    "core:path:default",
    "core:event:default",
    "core:window:default",
    {
      "identifier": "fs:allow-exists",
      "allow": [{ "path": "$APPDATA/*" }]
    }
  ]
}
```

By default, every JSON/TOML file under `src-tauri/capabilities/` is enabled. An
absent or empty `app.security.capabilities` list keeps that default. A non-empty
list becomes the explicit selection and only those entries are used; keep it
synchronized with capability identifiers. Window labels are case-sensitive
and are not titles.

## Review Checklist

- Are `core:*` permissions namespaced correctly for Tauri 2?
- Does each window have only the permissions it needs?
- Are remote URLs, filesystem scopes, and shell commands scoped?
- Are plugin permissions registered in capabilities after adding a plugin?
- Does CSP allow only required script, style, image, asset, IPC, and network
  sources?
- Did a build/runtime error get "fixed" by adding permissions that are too
  broad? If so, replace with a narrower permission or command.

## Verification

Run schema/build checks available in the project. At minimum, use:

```bash
cargo check --manifest-path src-tauri/Cargo.toml
```

Then run the local Tauri dev/build command if the changed permission affects
runtime frontend calls.
