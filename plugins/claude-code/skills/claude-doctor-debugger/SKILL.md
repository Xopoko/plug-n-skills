---
name: claude-doctor-debugger
description: Use when diagnosing Claude Code install/update/auth/config/runtime health, broken customizations, safe mode, bare mode, debug logs, auto-mode classifier, settings validation, keychain or API-key auth boundaries, IDE/Chrome integration, doctor warnings, or update/install/setup-token issues.
---

# Claude Doctor And Debugger

Use this skill when Claude Code itself is failing or unclear: install/update
state, auth, settings, hooks, plugins, MCP startup, keychain/API-key boundaries,
safe-mode or bare-mode isolation, debug logs, auto-mode classifier behavior,
IDE/Chrome integration, or native build installation.

From this skill directory, the plugin root is `../..`.
For broader safety contracts, read
[../../references/cli-operation-contracts.md](../../references/cli-operation-contracts.md).

## Inspect First

Use the inspector and help output before running health checks:

```bash
python3 ../../scripts/claude_code_inspector.py --commands doctor auto-mode install auth --json
claude doctor --help
```

Avoid running `claude doctor` automatically in untrusted repositories because
its help warns that it skips the workspace trust dialog and may spawn stdio
servers from project MCP config.

## Isolation Lanes

Use `--safe-mode` when customizations may be broken:

```bash
claude --safe-mode
claude --safe-mode --print "Check whether startup works."
```

Use `--bare` when the task needs minimal startup behavior, no keychain reads, no
hooks, no plugin sync, no auto-memory, and no CLAUDE.md auto-discovery:

```bash
claude --bare --print --settings /path/to/settings.json --add-dir /path/to/project "Inspect explicit context only."
```

In bare mode, auth is explicit: `ANTHROPIC_API_KEY` or an `apiKeyHelper` from
settings. Do not print or store key values.

## Debug Logs

Use debug only for targeted failures:

```bash
claude --debug api,hooks
claude --debug-file /tmp/claude-debug.log --print "Reproduce the issue."
```

Debug output may contain local paths, prompt fragments, tool inputs, hook output,
or environment-derived details. Summarize issue names, timestamps, and error
classes rather than pasting raw logs.

## Auto Mode

Read classifier state before changing settings:

```bash
claude auto-mode defaults
claude auto-mode config
claude auto-mode critique
```

Use this evidence when `--permission-mode auto`, tool denials, or custom
auto-mode rules behave unexpectedly.

## Update, Install, Auth

Treat these as explicit user-request operations:

```bash
claude install stable
claude install latest --force
claude update
claude setup-token
claude auth
```

Do not run them speculatively. Report the intended target, version, and
credential boundary before changing anything.

## Safety Boundaries

- Do not weaken permissions, hooks, MCP config, managed policy, or settings just to make startup pass.
- Do not expose keychain contents, API keys, long-lived tokens, OAuth secrets, bearer headers, debug logs, or settings secrets.
- Do not run `doctor` in an untrusted directory unless the user selected that directory.
- Do not delete settings, transcripts, plugins, MCP entries, caches, or project state without explicit approval.

## Completion Standard

Report the diagnostic lane, commands run, exact issue names or error text,
version/help facts used, any config/auth/update/daemon state changed, and the
smallest next repair or verified healthy state.
