---
name: signature-map
description: >-
  Signature Map indexes and queries `signatures.json` to locate declarations,
  survey medium or large repositories, open bounded source around symbols, or
  diagnose a stale index. Not for call-site search or a single small file.
---

# Signature Map

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

All commands below go through one entry point:

```bash
SIGMAP="$PLUGIN_ROOT/skills/signature-map/scripts/sigmap"
```

## When To Use

- Finding where a symbol (class, struct, protocol, function, method) is declared, without reading whole files.
- Surveying a module's API surface (declarations + doc comments) before editing it.
- Opening code around a declaration or a `file:line` location with bounded context.

Do not use it for call-site or usage search — use `rg` for that. Sigmap indexes declarations only. For a single small file, just read the file.

## Workflow

1. Refresh the index once per session (incremental; fast-skips when git HEAD is clean and unchanged):

```bash
"$SIGMAP" refresh --root <repo_root>
```

2. Query with `--no-refresh` so repeat lookups stay instant:

```bash
# Exact symbol name
"$SIGMAP" name <SymbolName> --root <repo_root> --no-refresh

# Regex over path/signature/comment
"$SIGMAP" search "<regex>" --field all --icase --root <repo_root> --no-refresh

# Full record(s) for one declaration key
"$SIGMAP" show "<relative/file/path::Symbol>" --root <repo_root> --no-refresh
```

3. Open source with context around what you found:

```bash
"$SIGMAP" open "<relative/file/path::Symbol>" --root <repo_root> --context 60 --no-refresh
"$SIGMAP" batch-open --entry "<a::X>" --entry "<b::Y>" --loc "<path:120-180>" --root <repo_root> --no-refresh
```

4. Diagnose when results look wrong (missing map, stale format, generator problems):

```bash
"$SIGMAP" doctor --root <repo_root>
```

## Useful Flags

- `--file <path_prefix>` (repeatable) — restrict `name`/`search` to a subtree.
- `--kind type|callable` — filter declarations by kind.
- `--limit N` — cap results (default 20).
- `--json` — machine-readable output with status and query metadata.
- `--strict-empty` — exit 1 on empty result (for scripted gates).
- `--map <file>` / `--generator <path>` — override index location or generator.
- Keep `--context` at or below 120; larger windows waste tokens (the CLI warns).

Exit codes: 0 success (including empty result), 1 unresolved selector or strict-empty, 2 usage error, 3 runtime/generator error.

## Requirements And Failure Modes

- First `refresh` builds the Go generator into `scripts/.bin/` automatically; it needs a Go toolchain (`go` on PATH or `GO_BIN`). No Go available: build the binary elsewhere and ship it with `SIGMAP_SKIP_GO_BUILD=1`.
- Queries need `python3` (or `python` / `PYTHON_BIN`).
- Without `--root`, sigmap resolves the git toplevel of the current directory, else `$PWD`. In multi-repo workspaces always pass `--root` explicitly.
- Generator "not found or not executable" or invalid-JSON map errors: run `doctor`, which checks the generator, map JSON, entry schema, and map format version.

Full command/flag reference, map schema, generator tuning env vars, and indexing behavior: `references/sigmap-reference.md`.
