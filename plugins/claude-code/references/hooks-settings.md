# Claude Code Hooks And Settings Reference

Use this reference when editing Claude Code settings, hooks, tool rules, custom
agents, or project/user/local configuration.

## Setting Sources

Common source scopes:

- user settings: applies across projects and should not be committed;
- project settings: can be committed when the repo intentionally shares them;
- local project settings: machine-local and normally ignored;
- managed policy settings: organization-controlled and may override user intent;
- plugin settings: active when the plugin is enabled;
- CLI `--settings` and `--setting-sources`: explicit runtime override surfaces.

Use `--safe-mode` to disable customizations while preserving auth, model
selection, built-in tools, and permissions. Use `--bare` for a minimal mode that
skips hooks, plugin sync, keychain reads, auto-memory, CLAUDE.md auto-discovery,
and other dynamic startup behavior.

## Hook Lifecycle

High-signal hook events include:

- `SessionStart` and `SessionEnd`
- `UserPromptSubmit` and `UserPromptExpansion`
- `PreToolUse`, `PermissionRequest`, `PermissionDenied`, `PostToolUse`, and `PostToolUseFailure`
- `PostToolBatch`
- `SubagentStart` and `SubagentStop`
- `TaskCreated` and `TaskCompleted`
- `WorktreeCreate` and `WorktreeRemove`
- `ConfigChange`, `InstructionsLoaded`, `CwdChanged`, and `FileChanged`
- `PreCompact` and `PostCompact`
- `Stop` and `StopFailure`

Tool events can match built-in tools such as `Bash`, `Edit`, and `Write`, and
MCP tools named like `mcp__<server>__<tool>`.

## Hook Safety

- A hook is not a substitute for permission rules. Use permission rules for hard allow/deny boundaries.
- Do not add hooks that run broad shell commands without a matcher and a narrow `if` condition.
- Treat HTTP hooks as data exfiltration risks unless the endpoint is trusted and retention is documented.
- Do not write secrets or full prompts to hook logs.
- Use command hooks with scripts in the repository only when they are reviewable and deterministic.
- Keep local-only hooks in local settings, not committed project settings.

## Tool And Permission Rules

Use `--tools` to restrict the built-in tool surface for a session. Use
`--allowedTools` and `--disallowedTools` to express finer allow/deny rules, for
example `Bash(git *)`, `Edit`, or MCP tool names.

Avoid:

- enabling `bypassPermissions` for ordinary work;
- allowing broad `Bash(*)` in untrusted repositories;
- storing bearer headers or token values in settings;
- relying on silently ignored settings in non-interactive print mode.

## Verification

Before claiming a settings or hook change is safe:

1. Validate JSON syntax.
2. Check the setting scope and whether the file is committed or local-only.
3. Run a safe-mode or bare-mode comparison when troubleshooting.
4. Use `claude auto-mode config` or `claude auto-mode defaults` when permission classification changed.
5. Report any setting file, hook script, or plugin source path changed.
