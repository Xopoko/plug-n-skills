# Codex CLI Operation Contracts

This reference captures stable operating contracts for the `codex-cli` plugin.
Use local CLI help as the installed-version source of truth, and use this file
for workflow shape and safety boundaries.

## Source Precedence

1. User-selected executable path for the current task.
2. `CODEX_CLI`, then `codex` on `PATH`.
3. `codex --version` and `codex --help`.
4. Relevant subcommand `--help`.
5. `codex doctor --json` or compact doctor output.
6. Official OpenAI Codex docs and the `openai/codex` repository.

When local help disagrees with documentation, local help wins for the installed
binary. Documentation remains useful for concepts, security posture, and
configuration intent.

## Command Families

| Family | Use | First checks |
| --- | --- | --- |
| Interactive TUI | Human-in-the-loop coding, images, remote TUI, resumes, forks | `codex --help`, `codex resume --help`, `codex fork --help` |
| Non-interactive exec | Automation, CI checks, bounded repo tasks, JSONL, output schemas | `codex exec --help` |
| Review | Review uncommitted changes, branch diffs, or one commit | `codex review --help`, git status/log |
| Doctor | Local install, config, auth, runtime, terminal, app-server, thread inventory | `codex doctor --summary --ascii`, then `--json` |
| Plugin | Marketplace source and installed plugin lifecycle | `codex plugin marketplace list`, `codex plugin list` |
| MCP | External MCP server config, login/logout, stdio or HTTP servers | `codex mcp list`, `codex mcp get <name>` |
| Sandbox | Reproduce command permissions and socket issues | `codex sandbox --help` |
| Debug | Model catalog, prompt input, app-server debug tooling | `codex debug --help` |
| App server | Local app/IDE integration and protocol work | `codex app-server --help` |
| Remote control | App-server daemon with remote-control enabled | `codex remote-control --help` |

## Safety Gate

Default safe modes:

- Ordinary local coding: `--sandbox workspace-write --ask-for-approval on-request`.
- Read-only CI or inspection: `--sandbox read-only --ask-for-approval never`.
- Automated workspace edits in CI: `--sandbox workspace-write --ask-for-approval never`, with tests and isolated checkout.

High-risk flags:

- `--dangerously-bypass-approvals-and-sandbox`
- `--dangerously-bypass-hook-trust`
- `--yolo`

Use high-risk flags only when the user explicitly identifies an external sandbox
or hardened automation boundary. Record that boundary in the final answer.

Mutation gates:

- `codex plugin remove`, `codex plugin marketplace remove`, and marketplace upgrades need explicit target confirmation.
- `codex mcp remove`, `codex mcp logout`, and MCP auth changes need explicit target confirmation.
- `codex features enable/disable` mutates configuration and needs a clear reason.
- `codex app-server` and `codex remote-control` can start listeners or daemons; report how to stop anything started.
- Archive/unarchive operations change session visibility; use exact IDs or names.

## Evidence Standards

For "is it installed/visible/live" questions, check actual local state rather
than manifests only. Good evidence includes:

- `codex plugin list` and marketplace list output.
- Repository installer `--check-only` output for plugins authored here.
- `codex mcp list` or `codex mcp get <name>`.
- `codex doctor --json` for health state.
- `codex_log_reader.py brief/timeline` for session history.
- Parsed `.codex/environments/environment.toml` and script syntax checks for local actions.

## Public-Safe Source Rules

Do not commit:

- personal absolute home paths;
- credentials, bearer token values, cookies, API keys, or private keys;
- local generated marketplace files;
- runtime cache output;
- raw rollout log excerpts;
- private project-specific examples.

Use placeholders such as `/path/to/project`, `$PROJECT`, `$CODEX_HOME`,
`CODEX_CLI`, and environment variable names without values.
