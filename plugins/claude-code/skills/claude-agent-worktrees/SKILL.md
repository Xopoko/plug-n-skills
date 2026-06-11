---
name: claude-agent-worktrees
description: Use when coordinating Claude Code background agents, `claude agents --json`, dispatched-session defaults, git worktrees, tmux/iTerm panes, resume/continue/from-pr/fork-session, session names and IDs, remote control, prompt suggestions, or cloud ultrareview runs.
---

# Claude Agents And Worktrees

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory. Works under any host agent, including Codex, Claude, and Cursor.

Use this skill for Claude Code session orchestration: background agents,
worktrees, tmux/iTerm panes, resumes, PR-linked sessions, forked sessions,
session names and IDs, remote control, prompt suggestions, and cloud ultrareview.

## Inspect First

Check command surface and current background sessions:

```bash
python3 "$PLUGIN_ROOT/scripts/claude_code_inspector.py" --commands agents ultrareview --json
claude agents --json
```

Use `claude agents --json --all` only when completed sessions are relevant and
the extra transcript/session metadata is needed.

## Background Agents

Use `claude agents` for active background session state and dispatch defaults:

```bash
claude agents --json
claude agents --cwd /path/to/project --json
claude agents --model sonnet --permission-mode plan --add-dir /path/to/extra
```

Do not start or leave long-lived background sessions without a reason and a
cleanup plan. Use explicit model, permission mode, settings, plugin-dir, and MCP
config when reproducibility matters.

## Sessions

Use these root flags for session continuity:

```bash
claude --continue
claude --resume <session-id-or-search>
claude --from-pr <pr-number-or-url>
claude --fork-session --resume <session-id>
claude --session-id <uuid>
claude --name "display-name"
```

Prefer exact session IDs or PR URLs when the user wants a specific conversation.
Use search/pickers only for interactive use.

## Worktrees And Panes

Use worktrees when the task should be isolated from the current working tree:

```bash
claude --worktree
claude --worktree feature-name --tmux
claude --worktree feature-name --tmux=classic
```

Before creating worktrees, inspect git status and branch state. Do not create
extra worktrees for tiny one-off commands unless isolation is the point.

## Remote Control And Integrations

Remote control, IDE, and Chrome integration are interactive surfaces:

```bash
claude --remote-control
claude --remote-control "session-name"
claude --ide
claude --chrome
claude --no-chrome
```

Use them only when the user asks for those integrations. Report how to stop or
exit any interactive session started.

## Ultrareview

`claude ultrareview` is cloud-hosted and may consume time or quota. Run it only
when requested:

```bash
claude ultrareview
claude ultrareview main
claude ultrareview <pr-number-or-url> --json --timeout 30
```

Prefer local review or `--print` analysis for lightweight checks.

## Safety Boundaries

- Do not combine background dispatch with dangerous skip-permissions unless the user selected an external sandbox.
- Do not create worktrees, tmux sessions, or remote-control sessions without clear user intent.
- Do not purge or abandon background work without reporting the session state.
- Do not expose session IDs, PR URLs, or transcript snippets beyond what the user needs.

## Completion Standard

Report the current session/agent/worktree state inspected, exact command used,
permission/tool settings, any created session/worktree/pane name, and cleanup or
resume instructions when a process remains active.
