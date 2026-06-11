# Marketplace Validation

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

Use this reference for marketplace-backed plugin creation, update, optional installation, and handoff. Repository source work can validate a marketplace-ready plugin without mutating the user's global marketplace or cache.

The marketplace entry, cache, and install/visibility flow on this page is Codex-specific. Claude Code activates plugins through its own marketplace tooling, and Cursor consumes skills directly without a plugin marketplace; for those hosts, completion is the validated plugin source path, not this gate.

## Canonical Plugin Manifest

```json
{
  "name": "plugin-name",
  "version": "0.1.0",
  "description": "Short plugin purpose.",
  "author": {"name": "Plugin Author"},
  "skills": "./skills/",
  "interface": {
    "displayName": "Plugin Name",
    "shortDescription": "25-90 character marketplace summary.",
    "longDescription": "Detailed user-facing capability summary.",
    "developerName": "Plugin Author",
    "category": "Productivity",
    "capabilities": ["Capability"],
    "defaultPrompt": "Use this plugin to..."
  }
}
```

Keep `apps` and `mcpServers` out unless companion files actually exist. Omit unsupported fields.

## Marketplace Entry

Global agent personal marketplace path when installation or marketplace activation is required:

```text
$HOME/.agents/plugins/marketplace.json
```

Entry shape:

```json
{
  "name": "plugin-name",
  "source": {"source": "local", "path": "./plugins/plugin-name"},
  "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
  "category": "Productivity"
}
```

Append entries unless the user asks for reordering.

## Validation Gate

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/validate_plugin.py" <plugin-dir>
```

Install/visibility proof is required only when `install_required=true`:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir> --check-only
```

For updates:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/update_plugin_cachebuster.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir> --check-only
```

The final handoff should include the plugin path, validation result, install state, marketplace path when applicable, and Codex app View/Share links only for installed Codex marketplace entries.
