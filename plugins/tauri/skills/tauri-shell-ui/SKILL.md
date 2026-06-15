---
name: tauri-shell-ui
description: "Build or review Tauri 2 desktop shell features: windows, webviews, menus, tray icons, custom titlebars, resources, icons, state, sidecars, opener/shell APIs, deep links, and native-feeling desktop interactions."
---

# Tauri Shell UI

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use this skill for native app-shell behavior around a web frontend: windows,
menus, tray, titlebars, resources, icons, sidecars, opener/shell APIs, and deep
links.

## First Pass

Run the probe, then inspect window labels and app config:

```bash
python3 "$PLUGIN_ROOT/scripts/tauri_project_probe.py" .
```

Relevant files usually include `src-tauri/tauri.conf.*`,
`src-tauri/capabilities/*`, `src-tauri/src/lib.rs`, frontend window/menu/tray
code, and bundled resource paths.

## Windows And Webviews

- Capabilities target window/webview labels, not titles. Keep labels stable.
- Custom titlebars require both frontend UI behavior and native window config.
- Avoid layout shifts in custom chrome: fixed toolbar heights, clear drag
  regions, and accessible controls.
- Account for platform differences in close/minimize/fullscreen/menu behavior.

## Resources, Icons, Tray, Menu

- Store bundled resources in the configured Tauri resource location and access
  them through Tauri path/resource APIs.
- Keep icon generation and references in sync with `bundle.icon`.
- Menus and tray icons differ across macOS, Windows, and Linux; implement the
  platform-specific behavior users expect.
- Do not expose menu/tray actions that call privileged commands without matching
  capabilities and validation.

## Sidecars And Shell

- Prefer native Rust commands unless a sidecar materially reduces risk or
  complexity.
- Sidecars require bundled binaries, lifecycle handling, platform-specific
  paths, and explicit shell permissions.
- Treat sidecars, opener, and shell APIs as security-sensitive. Scope commands
  and arguments tightly.

## Verification

For visual shell changes, run the frontend path and the Tauri shell path when
possible. For sidecars/resources, verify packaged build behavior, not only dev
server behavior.
