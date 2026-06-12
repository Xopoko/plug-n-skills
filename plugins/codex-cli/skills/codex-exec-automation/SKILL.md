---
name: codex-exec-automation
description: Use when preparing, running, debugging, or reviewing non-interactive Codex CLI automation with `codex exec`, `codex exec resume`, `codex review`, JSONL events, output schemas, last-message files, cwd/profile/config flags, sandbox and approval modes, or CI-style agent runs.
---

# Codex Exec Automation

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use this skill for non-interactive Codex CLI work: `codex exec`, `codex e`,
`codex exec resume`, `codex exec review`, top-level `codex review`, JSONL event
streams, final-message capture, output schemas, prompt stdin, images, cwd
selection, and CI-like checks.

## Inspect First

Before relying on a flag, verify the installed CLI:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_cli_inspector.py" --commands exec review doctor --json
```

If the user supplied a binary path, pass `--codex "$CODEX_CLI_PATH"`.

## Command Assembly

Build commands from these decisions, in this order:

1. Working root: use `-C <repo>` or run from the intended repository.
2. Autonomy: choose `--sandbox` and `--ask-for-approval`.
3. Config stack: add `--profile`, `-c key=value`, `--enable`, `--disable`, or `--strict-config` only when needed.
4. Prompt input: pass a short prompt argument, read from stdin with `-`, or pipe a structured prompt.
5. Output contract: use `--json`, `--output-schema <file>`, or `-o <file>` when automation must parse results.
6. Persistence: use `--ephemeral` only when the run should not persist session files.

Common safe patterns:

```bash
codex exec -C "$PROJECT" --sandbox workspace-write --ask-for-approval on-request "Implement the requested fix and run targeted tests."
codex exec -C "$PROJECT" --sandbox read-only --ask-for-approval never --json "Inspect this repo and report risks only."
codex review -C "$PROJECT" --uncommitted
codex review -C "$PROJECT" --base main
codex exec resume --last "Continue from the last non-interactive session and verify the fix."
```

For prompts that contain shell metacharacters, quotes, YAML, JSON, or long
instructions, prefer stdin:

```bash
codex exec -C "$PROJECT" --sandbox workspace-write --ask-for-approval on-request - < prompt.md
```

## Review Runs

Use `codex review` when the user asks for code review findings, changed-file
risk, commit review, base-branch comparison, or uncommitted changes. Choose one
review target:

- `--uncommitted` for staged, unstaged, and untracked changes.
- `--base <branch>` for branch diff review.
- `--commit <sha>` for one commit.

Keep custom review instructions narrow and actionable. Do not ask `codex review`
to implement fixes; run a separate `codex exec` task if the user wants changes.

## Output Handling

Use `--json` for event streams and parse line-by-line. Do not load large JSONL
streams into memory as one array.

Use `--output-schema <file>` when downstream automation needs a typed final
answer. Keep schemas small, explicit, and versioned.

Use `-o <file>` when the last assistant message should be saved for a report or
handoff. Keep output files inside the intended workspace or an ignored output
directory.

## Safety Boundaries

- Do not use dangerous bypass flags unless the user explicitly selected an external sandbox boundary.
- Do not use `--ignore-user-config`, `--ignore-rules`, or `--skip-git-repo-check` casually. Explain what safety or reproducibility check is being bypassed.
- Do not pass secrets in prompt arguments. Use existing environment variables or ignored local files only when the user already owns that setup.
- For CI, prefer read-only or workspace-write with `--ask-for-approval never`; do not rely on interactive approval prompts.
- For network-dependent tasks, state whether web search, command network access, or both are required. They are separate concerns.

## Failure Triage

If a run fails:

1. Re-run the relevant `--help` check if the error mentions an unknown flag.
2. Check `codex doctor --summary --ascii` for installation/config/auth/runtime issues.
3. If a persisted session exists and the failure is unclear, use `codex-log-reader` to inspect the rollout file safely.
4. Reduce to a read-only inspection prompt before retrying an automated edit.

## Completion Standard

Report the exact command used or recommended, the sandbox and approval policy,
the cwd, whether session persistence was enabled, the output file/schema if any,
and the verification result or blocker.
