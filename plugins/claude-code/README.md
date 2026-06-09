# Claude Code Plugin

Claude Code is an operations pack for working with the local `claude`
executable, Claude Code plugins, MCP servers, settings, hooks, sessions, agents,
and worktrees.

## Skills

- `claude-code`: router for local CLI inspection and workflow selection.
- `claude-print-automation`: non-interactive `claude --print` runs, JSON, stream-json, schemas, budgets, and prompt stdin.
- `claude-plugin-mcp-manager`: plugin marketplaces, validation, details, install/update/remove, MCP servers, transports, and approval state.
- `claude-doctor-debugger`: safe mode, bare mode, debug logs, doctor, auto-mode, auth, update, install, IDE, and Chrome troubleshooting.
- `claude-agent-worktrees`: background agents, worktrees, tmux, resumes, PR-linked sessions, remote control, and ultrareview.
- `claude-hooks-settings`: settings JSON, hooks, CLAUDE.md, rules, custom agents, tool permissions, and setting-source boundaries.

## Scripts

```bash
python3 scripts/claude_code_inspector.py --json
```

`claude_code_inspector.py` resolves the executable from `--claude`,
`CLAUDE_CLI`, or `PATH`, then reads `--version` and `--help` output without
starting a Claude Code session.

## Validation

From this plugin directory:

```bash
python3 -m unittest discover -s tests -q
```

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/claude-code
claude plugin validate plugins/claude-code --strict
python3 scripts/validate-repository.py
python3 scripts/install-codex-plugins.py --plugin claude-code --check-only
```
