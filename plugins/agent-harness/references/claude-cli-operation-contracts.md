# Claude Code Operation Contracts

Use this reference with the `claude-code` skills. The installed `claude` binary
is the command source of truth; official docs provide concepts, safety framing,
and longer examples.

## Source Precedence

1. User-selected executable path for the current task.
2. `CLAUDE_CLI`, then `claude` on `PATH`.
3. `claude --version` and `claude --help`.
4. Relevant subcommand `--help`.
5. Official Anthropic Claude Code docs.
6. Release notes for feature maturity and recent behavior.

When local help and docs disagree, trust local help for the installed binary.

## Command Families

| Family | Use | First checks |
| --- | --- | --- |
| Interactive session | Normal terminal work, IDE/Chrome, remote control, resume/continue/from-pr | `claude --help` |
| Print mode | Non-interactive output, JSON, stream-json, JSON schema, budget caps, fallback model | `claude --help` |
| Plugins | Marketplace, install/update/remove, details, validation, token cost, release tag | `claude plugin --help` |
| MCP | Stdio/HTTP/SSE servers, project approvals, strict config, server import, serve mode | `claude mcp --help` |
| Agents | Background sessions, JSON active-session list, dispatched-session defaults | `claude agents --help` |
| Project | Claude project state, transcripts, tasks, file history, config entry | `claude project --help` |
| Doctor/debug | Auto-updater health, debug logs, safe-mode, bare mode, auto-mode classifier | `claude doctor --help`, `claude auto-mode --help` |
| Worktrees | Isolated git worktree sessions and optional tmux/iTerm panes | `claude --help` |
| Ultrareview | Cloud-hosted multi-agent review of branch, PR, or base branch | `claude ultrareview --help` |

## Safety Gate

Default safe modes:

- Exploratory work: `--permission-mode plan` or the default permission flow.
- Automated trusted-directory read/report: `--print --output-format json` with restricted tools when possible.
- Broken customization troubleshooting: `--safe-mode`.
- Minimal explicit-context troubleshooting: `--bare` with explicit `--settings`, `--mcp-config`, `--plugin-dir`, and context dirs as needed.

High-risk flags and modes:

- `--dangerously-skip-permissions`
- `--allow-dangerously-skip-permissions`
- `--permission-mode bypassPermissions`

Use high-risk modes only when the user explicitly identifies an external sandbox
or isolated environment. Record that boundary in the final answer.

Mutation gates:

- `project purge` deletes Claude project state and needs explicit target confirmation.
- `install`, `update`, `upgrade`, `setup-token`, and auth commands need explicit user intent.
- `plugin install/update/uninstall/prune`, marketplace add/update/remove, and tag creation need explicit target confirmation.
- `mcp add/remove/reset-project-choices` and auth-bearing MCP changes need explicit target confirmation.
- `ultrareview` is cloud-hosted and can spend time or quota; run only when requested.

## Evidence Standards

For "is it installed/visible/live" questions, check actual local state:

- `claude plugin list`
- `claude plugin details <name>`
- `claude plugin validate <path> --strict` when source validation matters
- `claude plugin marketplace list`
- `claude mcp list` or `claude mcp get <name>`
- `claude agents --json` for background session state
- `claude auto-mode config` or `defaults` for classifier rules

Avoid running `claude doctor` automatically in untrusted directories because
help text warns it may spawn stdio servers from project MCP config.

## Public-Safe Source Rules

Do not commit:

- personal absolute home paths;
- credentials, bearer token values, cookies, API keys, keychain material, long-lived tokens, or OAuth secrets;
- debug logs;
- local generated marketplace files;
- runtime cache output;
- private project-specific examples.

Use placeholders such as `/path/to/project`, `$PROJECT`, `$CLAUDE_CLI`,
`CLAUDE_CLI`, `ANTHROPIC_API_KEY`, and environment variable names without
values.
