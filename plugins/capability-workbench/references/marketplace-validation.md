# Marketplace Validation

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

Use this reference for marketplace-backed plugin creation, update, optional installation, and handoff. Repository source work can validate a marketplace-ready plugin without mutating the user's global marketplace or cache.

The marketplace entry and install/cache flow on this page is Codex-specific. Claude Code activates plugins through its own marketplace tooling, and Cursor consumes skills directly without a plugin marketplace; for those hosts, completion is the validated plugin source path, not this gate.

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

Install/cache proof is required only when `install_required=true`:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir> --check-only
```

`--check-only` is read-only. It verifies the enabled plugin entry and exact
installable source/cache content, including the root entry, entry kinds, and
modes, while
excluding only the same `.git`, `__pycache__`, `*.pyc`, and `.DS_Store`
transients omitted during cache materialization. A successful receipt is bound
to the selected local marketplace source and reports runtime discovery as not
checked; it does not prove canonical branch provenance or runtime skill
discovery. When that source is a derived global copy, pass the repository source
with `--expected-source-path`; `scripts/install-codex-plugins.py --check-only`
does this automatically for `--global-source-root`.

Comparison keys use strict canonical UTF-8 encoding; invalid filesystem names
are rejected. Public receipts expose booleans and mismatch category counts, not
content-derived digests or relative filenames. Source validation, optional
expected-source parity, and cache parity are bound to one unchanged selected
source snapshot. Verification reads every participating tree twice and fails if
any changes, so the result is an instantaneous stable-read proof, not a
guarantee about later mutations. `--dry-run` never invokes the install CLI and
reports the install/cache state as unverified. Plugin and marketplace names
must be safe single path components.
Source and cache trees must be disjoint and contain only regular files and
directories. Symlinks present at roots, inside scanned trees, or along the cache
path are rejected before install/config mutation; regular files are opened
without following a swapped final-component symlink and the opened descriptor
is revalidated. An expected upstream source must also be outside the cache
version/deletion scope. Enabled config and marketplace selection are captured
before and revalidated after the anchored tree proof. Concurrent adversarial
directory replacement or change after the receipt returns is outside this
helper's guarantee.

For updates:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/update_plugin_cachebuster.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir> --check-only
```

The final handoff should include the plugin path, validation result,
install/cache state, separate runtime-discovery state, marketplace path when
applicable, and Codex app View/Share links only for installed Codex marketplace
entries.
