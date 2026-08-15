---
name: plugin-factory
description: Build or update marketplace-backed agent plugins with manifests, skill bundles, local marketplace entries, packaging, validation, optional install/cache gates, runtime-discovery status, and Codex deeplinks.
---

# Plugin Factory

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

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

- plugin path: `$HOME/.codex/plugins/<plugin-name>`
- marketplace path: `$HOME/.agents/plugins/marketplace.json`
- marketplace source path: `./.codex/plugins/<plugin-name>`
- policies: `installation=AVAILABLE`, `authentication=ON_INSTALL`

This creates a marketplace-ready source path. It is installed globally as
`<plugin-name>@<marketplace-name>` only after the install helper enables it and verifies an
equivalent cache copy. That receipt does not prove runtime discovery. For
repo-local plugin source work, create or update the plugin under that repository
and skip marketplace/cache mutation unless `install_required=true`.

For new marketplace-facing plugins, generate the icon through the system
`$imagegen` skill, not through hand-authored SVG templates. Use
`$PLUGIN_ROOT/references/plugin-icon-system.md`:

1. Scaffold with `--with-assets`.
2. Generate the schema-v2 prompt contract with
   `$PLUGIN_ROOT/scripts/plugin/prepare_plugin_icon_prompt.py`. Start from the
   first-party catalog: one literal semantic hero and at most one support cue;
   unknown names use a deterministic concrete-object fallback.
3. Review the declared collision avoids and brand-source trademark/license
   provenance, then call built-in image generation with the emitted prompt.
4. Save an opaque 1024x1024 RGB PNG to `assets/icon.png` and wire identical
   `interface.composerIcon` and `interface.logo` paths plus `brandColor`.
5. Run `$PLUGIN_ROOT/scripts/plugin/validate_plugin_icons.py <plugin-dir>
   --require-prompt`; manually review meaning and monochrome silhouette at
   16/24/32/64 because quantitative thumbnail gates cannot prove semantics.

When the host has no imagegen skill (for example Claude Code), use a
user-supplied asset or host-native image generation when available; otherwise
skip generation, record the gap in the report, and keep delivering the plugin.
Never block plugin delivery on icon generation.

For MCP-backed capability requests, prefer packaging the MCP server inside the selected plugin source. Write global agent MCP configuration only for explicit installed/global activation work.

## Manifest Rules

Keep `.codex-plugin/plugin.json` validation-ready:

- `name` equals the outer folder name.
- Include `version`, `description`, `author`, `skills` when skills exist, and `interface` metadata.
- Treat `name` as a public namespace and installation identifier; rename only
  with an explicit migration. Lead `description`, `shortDescription`, and
  `longDescription` with the plugin's concrete domain and owned actions rather
  than `Agent skills for`, `Help with`, or another generic wrapper.
- Do not include unsupported fields or empty MCP/app entries.
- Keep apps and MCP servers out of the manifest unless companion files exist.
- Do not leave TODO placeholders.
- For new marketplace-facing plugins, generate or preserve an icon under
  `assets/` and wire `interface.composerIcon`, `interface.logo`, and
  `interface.brandColor` when the target agent supports them. Use the system
  `$imagegen` skill plus `$PLUGIN_ROOT/references/plugin-icon-system.md`; use one
  concrete semantic hero, no more than one support cue, explicit collision and
  brand provenance fields, and no text-heavy, tiny, screenshot-based,
  photographic, API-key-only, or private/project-specific icon.

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

Track three states independently:

1. `source_validated`: the selected plugin source passes manifest and resource
   checks; a derived global source also matches its expected repository source.
2. `install_cache_verified`: the selected marketplace entry is enabled and its
   filtered cache tree exactly matches the selected source.
3. `runtime_discovery`: a separate host/session probe reports `verified`,
   `failed`, or `not checked`.

For every marketplace-backed plugin:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/validate_plugin.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/skill/audit_description_prefixes.py" <plugin-dir>
```

For Codex plugins, add a structured quality-review pass:

```bash
python3 "$PLUGIN_ROOT/scripts/context/context_density_audit.py" <plugin-dir> --json --top 20
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

Installed work is incomplete if the plugin is only present in `marketplace.json`; it must be enabled and cache-backed. Unambiguous source-only repository work is complete when the plugin validates and an inline scope note records `install_required=false`; do not create `install-scope.json` for that path. If the plugin targets a real machine consumer, has ambiguous scope, or carries global/install/update/activation intent, persist the ledger after paths and policy are stable and run the final install-scope gate:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" <output-dir>/install-scope.json --final
```

The install helper proves only `install_cache_verified`. Check runtime discovery
through the current host's actual discovery surface when that lifecycle step is
in scope; otherwise record `runtime_discovery=not checked` rather than claiming
visibility.

## Handoff

When a marketplace entry was created, updated, or installed, finish with:

- validation results;
- `source_validated`, `install_cache_verified`, and `runtime_discovery` as
  separate states;
- installed plugin id, `<name>@<marketplace-name>`, or `not installed` for source-only work;
- absolute plugin path;
- absolute marketplace path when applicable;
- Codex app View and Share deeplinks only for installed Codex marketplace entries.
