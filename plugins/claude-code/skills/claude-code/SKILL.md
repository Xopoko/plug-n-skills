---
name: claude-code
description: Route Claude Code CLI work across local CLI inspection, interactive and print-mode automation, plugin and MCP lifecycle, diagnostics, hooks/settings, background agents, worktrees, sessions, remote control, and ultrareview.
---

# Claude Code Router

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.
On Windows PowerShell, set and read this as `$env:PLUGIN_ROOT`; translate shown POSIX-style `$PLUGIN_ROOT/...` paths to the same path under `$env:PLUGIN_ROOT`.

Use this skill when the user asks to operate, diagnose, automate, wrap, or
explain Claude Code CLI, including `claude`, `claude --print`, `claude plugin`,
`claude mcp`, `claude agents`, `claude doctor`, `claude auto-mode`, worktrees,
hooks, settings, permissions, custom agents, or ultrareview.

For the full command/safety matrix, read
`$PLUGIN_ROOT/references/cli-operation-contracts.md`.

## First Move

Prefer live local facts over memory. Inspect the installed CLI before building
commands or debugging version-sensitive behavior:

```bash
python3 "$PLUGIN_ROOT/scripts/claude_code_inspector.py" --json
```

If the user supplies a Claude executable path, use it for the current run:

```bash
python3 "$PLUGIN_ROOT/scripts/claude_code_inspector.py" --claude "$CLAUDE_CLI_PATH" --json
```

Do not commit personal absolute paths into source files, manifests, docs, or
examples. Use `CLAUDE_CLI`, `PATH`, `ANTHROPIC_API_KEY`, or user-provided runtime
arguments instead.

## Routing

- Non-interactive `--print`, JSON/stream-json, JSON schema, input streaming, prompt files/stdin, budget caps, fallback model, and no-persistence runs: use `claude-print-automation`.
- Plugin marketplaces, plugin install/update/remove/details/validate/tag/prune, session-only `--plugin-dir` or `--plugin-url`, and MCP server lifecycle: use `claude-plugin-mcp-manager`.
- Broken config, safe mode, bare mode, debug logs, doctor, update/install, auth/token setup, auto-mode classifier, IDE/Chrome startup issues: use `claude-doctor-debugger`.
- Background agents, `claude agents --json`, worktrees, tmux, resume/continue/from-pr, fork-session, session names, remote control, and ultrareview: use `claude-agent-worktrees`.
- Settings JSON, hooks, CLAUDE.md, tool allow/deny rules, custom agents, plugin customizations, and setting-source boundaries: use `claude-hooks-settings`.

If several apply, inspect the CLI first, diagnose the safety/config surface
second, then run or recommend the narrow workflow.

## Safety Rules

- Treat `--dangerously-skip-permissions`, `--allow-dangerously-skip-permissions`, and `--permission-mode bypassPermissions` as high-risk. Use them only with an explicit external sandbox boundary.
- Prefer default permission flow or `--permission-mode plan` for exploratory work.
- Use `--safe-mode` for broken customizations and `--bare` for minimal explicit-context troubleshooting.
- Do not run `doctor`, `project purge`, `setup-token`, `auth`, `install/update`, cloud `ultrareview`, plugin marketplace updates/removals, MCP removals/resets, or long-lived background sessions without clear user intent.
- Keep secrets out of command examples, settings snippets, MCP headers, debug files, hook logs, and final answers.

## Completion Standard

A Claude Code CLI task is done when the answer includes the exact command or
source change, the permission/tool/settings mode chosen, the cwd assumptions,
and proof appropriate to the request: inspector output, subcommand help,
`plugin validate`, plugin/MCP list/details output, safe-mode/bare comparison,
settings JSON validation, or a clearly reported blocker.
