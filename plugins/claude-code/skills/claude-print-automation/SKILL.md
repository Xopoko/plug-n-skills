---
name: claude-print-automation
description: Use when preparing, running, or debugging non-interactive Claude Code with `claude --print`, output-format text/json/stream-json, input-format text/stream-json, JSON schema validation, budget caps, fallback model, no session persistence, prompt suggestions, or trusted-directory CI-style runs.
---

# Claude Print Automation

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use this skill for non-interactive Claude Code runs: `claude --print`, `-p`,
JSON output, stream-json input/output, partial messages, hook event streams,
JSON schema validation, budget caps, fallback model, prompt suggestions,
no-persistence runs, and CI-style reports.

## Inspect First

Verify the installed CLI:

```bash
python3 "$PLUGIN_ROOT/scripts/claude_code_inspector.py" --commands "plugin validate" doctor auto-mode --json
```

If the user supplied a binary path, pass `--claude "$CLAUDE_CLI_PATH"`.

## Command Assembly

Build commands from these decisions, in order:

1. Trust boundary: confirm the directory is trusted because print mode skips the workspace trust dialog.
2. Permission/tool surface: choose `--permission-mode`, `--tools`, `--allowedTools`, and `--disallowedTools`.
3. Context: add `--add-dir`, explicit files, `--mcp-config`, `--settings`, `--agents`, or `--plugin-dir` only when needed.
4. Prompt input: use an argument for short prompts or stdin for long structured prompts.
5. Output contract: choose `--output-format text|json|stream-json`, `--json-schema`, and partial-message/hook-event streaming.
6. Cost/session: choose `--max-budget-usd`, `--fallback-model`, and `--no-session-persistence`.

Common patterns:

```bash
claude --print --output-format json --permission-mode plan "Inspect this repo and report risks only."
claude --print --output-format json --json-schema "$SCHEMA" - < prompt.md
claude --print --output-format stream-json --include-partial-messages --input-format stream-json
claude --print --tools "Read,Grep,Glob" --permission-mode plan "Summarize this codebase."
```

Use `--bare` when startup customizations, plugin sync, hooks, keychain reads, or
CLAUDE.md auto-discovery could contaminate a reproducible run. Provide explicit
context in that mode.

Use `--safe-mode` when customizations are suspected to be broken but normal
auth/model/tool defaults should remain available.

## Structured Output

Use `--json-schema` for machine-consumed final answers. Keep the schema small
and validate it before use. For streaming automation, parse JSON lines
incrementally; do not load a large stream into memory as one array.

Use `--include-hook-events` only when auditing hook behavior. Hook events can
expose tool inputs or local paths, so summarize before sharing.

## Safety Boundaries

- Do not use dangerous skip-permissions flags unless the user explicitly selected an external sandbox.
- Do not pass secrets in prompt arguments, JSON schema, settings JSON, MCP config, or tool allow/deny examples.
- Do not use `--settings` JSON that embeds tokens; reference env vars or ignored local files.
- Do not set `--permission-mode dontAsk` or `bypassPermissions` for untrusted repositories.
- Do not run cloud or update workflows from print automation unless the task asks for them.

## Failure Triage

1. Re-run `claude --help` through the inspector if a flag is unknown.
2. Try `--safe-mode` if customization loading appears broken.
3. Try `--bare` with explicit context if keychain/plugin/hook/CLAUDE.md discovery is suspect.
4. Use `--debug-file <path>` only to a local ignored path and report indicators, not raw secrets.

## Completion Standard

Report the exact command, trust boundary, permission mode, tool restrictions,
input/output formats, budget/session persistence choices, and verification or
blocker.
