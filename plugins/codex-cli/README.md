# Codex CLI Plugin

Codex CLI is an operations pack for working with the local `codex` executable,
Codex app project environments, live task supervision, and Codex session
evidence.

## Skills

- `codex-cli`: router for local CLI inspection and workflow selection.
- `codex-exec-automation`: non-interactive `codex exec` and `codex review` runs.
- `codex-deferred-completion`: one validated producer-native terminal receipt without model-driven polling.
- `codex-thread-supervisor`: live multi-thread observation, transition waits,
  gated skill handoffs or versioned evidence corrections, and privacy-safe
  capability mining.
- `codex-plugin-mcp-manager`: plugin marketplaces, installed plugins, and MCP servers.
- `codex-doctor-debugger`: `doctor`, `debug`, `sandbox`, feature flags, app-server, and remote-control diagnostics.
- `codex-log-reader`: redacted rollout JSONL lookup, root/child normalization, active-scope views, deterministic trace audits, searches, and log health checks.
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
`~/.codex`, redacts likely secrets, separates active child work from inherited
history, and produces compact views and evidence-ledger audits before any raw
log line is opened.

## Deferred completion

The bundled POSIX MCP server exposes `reserve_completion_receipt` and
`await_completion_receipt`. It creates a private result path, validates a
producer-owned atomic JSON envelope plus exact identity assertions, and returns
only a fixed terminal projection. It never accepts or executes a command.

Start the real producer directly through native Codex exec, pass the reserved
path through the producer's own result flag, then await the handle once. This
preserves the native command sandbox and approval boundary while removing
repeated model turns around unchanged process or remote-status checks. The
coordination receipt is consumed after validation; producer-native workspace
artifacts remain the durable proof.

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
