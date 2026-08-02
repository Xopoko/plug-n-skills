# Sigmap Reference

Entry point: `$PLUGIN_ROOT/skills/signature-map/scripts/sigmap` (bash wrapper around an embedded Python query engine and a Go index generator).

## Commands

| Command | Purpose |
| --- | --- |
| `refresh` / `ensure` | Regenerate `signatures.json` for the repo root (incremental). |
| `name <Symbol>` | Exact-name declaration lookup (matches `path::Symbol` key suffix). |
| `search <regex>` | Regex search over path, signature, and/or doc comment. |
| `show <path::symbol>` | Print full stored record(s) for one declaration key. |
| `open [<path::symbol>]` | Print source snippet(s) with line numbers and `>>` highlight. |
| `batch-open` | Like `open` but for many selectors, including from a file. |
| `doctor` | Health checks for generator, map JSON, schema, and instruction style. |

### Shared options

Every command accepts `--root <repo_root>`, `--map <signatures_json>` (alias `--sig-file`), and `--generator <path>`. Query commands also accept `--no-refresh` (require an existing valid map instead of regenerating), `--json`, and `--strict-empty`.

Root resolution order: `--root` > `SIGMAP_ROOT` > git toplevel of `$PWD` > `$PWD`.
Map resolution order: `--map` > `SIGMAP_FILE` > `<root>/signatures.json` (relative overrides resolve against root).
Generator resolution order: `--generator` > `SIGMAP_GENERATOR` > bundled `generate-signatures.sh`.

### name / search filters

- `--kind any|type|callable` — declaration kind filter (default `any`).
- `--file <path_prefix>` — repeatable subtree restriction (prefix match on the relative path).
- `--limit N` — result cap, default 20; `0` means unlimited (used internally by `show`).
- `search`-only: `--field path|signature|comment|all` (default `all`), `--icase`.

Results are sorted by `(path, line)` and truncated to the limit.

### open / batch-open selectors

- Positional or `--entry <relative/path::Symbol>` — resolved through the map (first match by line).
- `--loc <relative/path:line[-line]>` — direct file location, no map lookup needed.
- `--entries-file <file>` (`batch-open` only) — one selector per line; `::` lines become entries, `:N[-M]` lines become locs; `#` comments and blanks are skipped.
- `--context N` — lines of context around the highlight (default 40; warns above 120).

Unresolved selectors are reported per item on stderr; the command exits 1 if any selector failed, while still printing successful snippets (`status: partial` in `--json`).

### Exit codes

- `0` — success, including an empty query result without `--strict-empty`.
- `1` — unresolved selector for `open`/`batch-open`, or empty result with `--strict-empty`.
- `2` — usage/arguments error.
- `3` — runtime error (IO, JSON, generator, regex, internal); also `doctor` with errors.

## Map Schema

`signatures.json` is a JSON array of entries:

```json
{
  "path": "Sources/App/Login.swift::LoginViewModel",
  "signature": "final class LoginViewModel: ObservableObject {",
  "comment": "Handles login form state and validation.",
  "line": 42,
  "kind": "type"
}
```

- `path` — `relative/file/path::SymbolName` key. Multiple entries may share a key (overloads); they are distinguished by `line`.
- `kind` — `type` (class/struct/enum/protocol/interface/typedef/…) or `callable` (function/method/init/subscript/…). Older maps without `kind` are flagged by `doctor` as outdated; re-run `refresh`.
- `comment` — adjacent doc comment (`///`, `/** */`, `//`, `#`), normalized; empty when none or when comments are disabled.
- `signature` — declaration line(s), joined and whitespace-normalized, capped by `SIGMAP_MAX_SIGNATURE_LINES`.

## Generator Behavior

`generate-signatures.sh` builds `sigmapgen/main.go` into `scripts/.bin/sigmapgen` on first use and rebuilds when any `.go` source is newer than the binary, then execs it with `--root`/`--out`.

- Languages: Swift, Objective-C (`.m/.mm/.h`), C/C++, JavaScript/JSX, TypeScript/TSX, Python, Ruby, shell (`.sh/.bash/.zsh` plus shebang detection for extensionless files), Kotlin, Java/Groovy.
- File discovery: `git ls-files -co --exclude-standard` when the root is a git repo (source mode `git`), otherwise a directory walk (mode `walk`). Both modes skip common vendor/build dirs (`.git`, `build`, `DerivedData`, `Pods`, `Carthage`, `node_modules`, `.idea`, `.vscode`, …), any `*.xcworkspace`/`*.xcodeproj` container, `Tuist/Dependencies`, and hashed JS bundle assets (`name.<hex>.js`).
- Incremental: per-file size+mtime metadata is cached (keyed by sha1 of the root path) and unchanged files reuse previous entries. When git HEAD is unchanged and the tree is clean, the whole run fast-skips and keeps the existing map.
- Parsing is regex/heuristic line scanning, not a full AST: extremely long lines are skipped (`SIGMAP_MAX_LINE_LENGTH`), and forward declarations/control keywords are filtered for C-likes.

### Generator env vars

| Variable | Default | Effect |
| --- | --- | --- |
| `SIGMAP_WORKERS` | `min(12, NumCPU)` | Parallel parse workers. |
| `SIGMAP_MAX_LINE_LENGTH` | `2000` | Skip parse of longer lines (floor 80). |
| `SIGMAP_MAX_SIGNATURE_LINES` | `12` | Cap multi-line signature capture (floor 2). |
| `SIGMAP_DISABLE_COMMENTS` | `0` | Skip doc-comment extraction for speed. |
| `SIGMAP_INDEX_HASHED_BUNDLES` | `0` | Also index hashed JS bundle assets. |
| `SIGMAP_PROFILE` / `SIGMAP_PROFILE_TOP` | `0` / `20` | Print slowest-file parse profile. |
| `SIGMAP_CACHE_DIR` | `$XDG_CACHE_HOME/signature-map` or `~/.cache/signature-map` | Metadata cache location (falls back to `<root>/.sigmap-cache` if unresolvable). |
| `GO_BIN` | `go` on PATH | Go compiler used to build the generator. |
| `SIGMAP_SKIP_GO_BUILD` | `0` | `1` = never build; requires a prebuilt `scripts/.bin/sigmapgen`. |

Wrapper env vars: `SIGMAP_ROOT`, `SIGMAP_FILE`, `SIGMAP_GENERATOR`, `PYTHON_BIN`.

## Doctor Checks

`sigmap doctor [--json]` reports `ok`/`warn`/`error` per check and exits 3 on any error:

- `generator` — bundled (or overridden) generator exists and is executable.
- `map_json` — map file exists and parses as a JSON array (`warn` if missing: run `refresh`).
- `map_schema` — every entry has `path`, `signature`, `comment`, `line`.
- `map_format` — `warn` when entries lack `kind` (pre-kind map format): run `refresh`.
- `instruction_style` / `instruction_conflict` — scans the repo's `AGENTS.md`/`SKILL.md` (root and `.codex/.agents/.claude` skill dirs) for sigmap command patterns; warns when both repo-local `scripts/sigmap` and plugin-root/global command styles are documented at once.
- `local_cli` — warns when a repo-local `scripts/sigmap` exists but the docs reference only the plugin/global path.

## Troubleshooting

- `go compiler not found` — install Go, set `GO_BIN`, or ship the prebuilt binary with `SIGMAP_SKIP_GO_BUILD=1`.
- `map file not found` with `--no-refresh` — run `refresh` once first.
- Empty results for a symbol you can see in the file — the map may be stale (drop `--no-refresh` once) or the declaration form is not covered by the language heuristics; fall back to `rg` and report the gap.
- Two repos sharing a shell — always pass `--root`; the cache is keyed per root, so alternating roots is safe.
- Slow first run on a huge repo — expected; subsequent runs are incremental. Tune `SIGMAP_WORKERS`, or `SIGMAP_DISABLE_COMMENTS=1` for indexing speed at the cost of comment search.
