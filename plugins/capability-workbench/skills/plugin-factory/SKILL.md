---
name: plugin-factory
description: Create, update, validate, optionally install/cache-refresh, and hand off marketplace-backed agent plugins. Use for plugin manifests, local marketplace entries, plugin-pack synthesis, triggerable skill bundles, install visibility gates, and Codex app deeplinks.
---

# Plugin Factory

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`. Works under any host agent, including Codex, Claude, and Cursor.

Build marketplace-ready plugin source first. Install or cache-refresh only when the user asked for an installed/global plugin or the validated contract has `install_required=true`.

## Scaffold

For a new requested plugin, choose the source destination deliberately:

- current plugin repository: when the latest user message, repo instructions, or workspace profile indicate this repo is where plugin source should be authored;
- explicit path: when the user gives one;
- user's local marketplace source: when no source repository is selected and the user wants a personal agent plugin.

For the user's local marketplace source, scaffold with:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/create_basic_plugin.py" <plugin-name> --with-skills --with-scripts --with-assets --with-marketplace
```

Defaults:

- plugin path: `$HOME/plugins/<plugin-name>`
- marketplace path: `$HOME/.agents/plugins/marketplace.json`
- marketplace source path: `./plugins/<plugin-name>`
- policies: `installation=AVAILABLE`, `authentication=ON_INSTALL`

This creates a marketplace-ready source path. It is installed globally as
`<plugin-name>@local` and cache-backed only after the install/visibility helper
runs. For repo-local plugin source work, create or update the plugin under that
repository and skip marketplace/cache mutation unless `install_required=true`.

For new marketplace-facing plugins, generate the icon through the system
`$imagegen` skill, not through hand-authored SVG templates. Use
`$PLUGIN_ROOT/references/plugin-icon-system.md`:

1. Scaffold with `--with-assets`.
2. Run `$PLUGIN_ROOT/scripts/plugin/prepare_plugin_icon_prompt.py` to produce the
   prompt contract.
3. Call built-in image generation with that prompt.
4. Save the selected bitmap to `assets/icon.png`.
5. Run `$PLUGIN_ROOT/scripts/plugin/wire_plugin_icon.py` to set
   `interface.composerIcon`, `interface.logo`, and `interface.brandColor`.

When the host has no imagegen skill (for example Claude Code), use a
user-supplied asset or host-native image generation when available; otherwise
skip generation, record the gap in the report, and keep delivering the plugin.
Never block plugin delivery on icon generation.

For MCP-backed capability requests, prefer packaging the MCP server inside the selected plugin source. Write global agent MCP configuration only for explicit installed/global activation work.

## Manifest Rules

Keep `.codex-plugin/plugin.json` validation-ready:

- `name` equals the outer folder name.
- Include `version`, `description`, `author`, `skills` when skills exist, and `interface` metadata.
- Do not include unsupported fields or empty MCP/app entries.
- Keep apps and MCP servers out of the manifest unless companion files exist.
- Do not leave TODO placeholders.
- For new marketplace-facing plugins, generate or preserve an icon under
  `assets/` and wire `interface.composerIcon`, `interface.logo`, and
  `interface.brandColor` when the target agent supports them. Use the system
  `$imagegen` skill plus `$PLUGIN_ROOT/references/plugin-icon-system.md`; avoid
  text-heavy, tiny, screenshot-based, photographic, API-key-only, or
  private/project-specific icons.

Use `$PLUGIN_ROOT/references/marketplace-validation.md` for the expected manifest and marketplace entry shapes.

## Plugin-Pack Shape

Use multiple plugin skills only when it improves trigger precision or context loading. Prefer:

- one router skill for ambiguous lifecycle tasks;
- focused skills for synthesis, authoring, install/vetting, plugin packaging, and audit;
- shared scripts at plugin root for reusable tooling;
- shared references for long contracts and validation guidance.

Design plugin skill descriptions for autonomous routing from task context,
artifacts, source evidence, and agent decision points. Avoid preserving upstream
micro-skill variants or request-phrase descriptions when one synthesized skill
covers the workflow better.

## Validate And Optionally Install

For every marketplace-backed plugin:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/validate_plugin.py" <plugin-dir>
```

When `install_required=true`:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir> --check-only
```

For installed updates to an existing marketplace-backed plugin:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/update_plugin_cachebuster.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir> --check-only
```

Installed work is incomplete if the plugin is only present in `marketplace.json`; it must be enabled and cache-backed. Source-only repository work is complete when the plugin validates and the install-scope contract records `install_required=false`. If this plugin was produced by the synthesizer, also run the final install-scope gate:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" <output-dir>/install-scope.json --final
```

## Handoff

When a marketplace entry was created, updated, or installed, finish with:

- validation results;
- installed plugin id, usually `<name>@local`, or `not installed` for source-only work;
- absolute plugin path;
- absolute marketplace path when applicable;
- Codex app View and Share deeplinks only for installed Codex marketplace entries.
