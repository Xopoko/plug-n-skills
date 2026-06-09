# Codex CLI Plugin

Codex CLI is an operations pack for working with the local `codex` executable,
Codex app project environments, and Codex session evidence.

## Skills

- `codex-cli`: router for local CLI inspection and workflow selection.
- `codex-exec-automation`: non-interactive `codex exec` and `codex review` runs.
- `codex-plugin-mcp-manager`: plugin marketplaces, installed plugins, and MCP servers.
- `codex-doctor-debugger`: `doctor`, `debug`, `sandbox`, feature flags, app-server, and remote-control diagnostics.
- `codex-log-reader`: redacted rollout JSONL lookup, summaries, timelines, searches, and log health checks.
- `codex-environments`: `.codex/environments/environment.toml` actions and long-running project commands.

## Scripts

```bash
python3 scripts/codex_cli_inspector.py --json
python3 scripts/codex_log_reader.py --help
```

`codex_cli_inspector.py` resolves the executable from `--codex`, `CODEX_CLI`, or
`PATH`, then reads `--version` and `--help` output without launching an agent
session.

`codex_log_reader.py` reads Codex rollout JSONL under `$CODEX_HOME` or
`~/.codex`, redacts likely secrets, and produces compact views before any raw
log line is opened.

## Validation

From this plugin directory:

```bash
python3 -m unittest discover -s tests -q
```

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/codex-cli
python3 scripts/validate-repository.py
python3 scripts/install-codex-plugins.py --plugin codex-cli --check-only
```
