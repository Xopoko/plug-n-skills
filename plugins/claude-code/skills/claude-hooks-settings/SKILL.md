---
name: claude-hooks-settings
description: Use when creating, editing, auditing, or debugging Claude Code settings, hooks, CLAUDE.md/rules loading, custom agents, tool allow/deny permissions, output styles, workflows, setting sources, safe-mode/bare-mode differences, or plugin-provided customizations.
---

# Claude Hooks And Settings

Use this skill for Claude Code settings and customization work: settings JSON,
hooks, CLAUDE.md or rules loading, custom agents, tool allow/deny rules, output
styles, workflows, setting sources, plugin-provided customizations, safe-mode
comparisons, and bare-mode explicit context.

From this skill directory, the plugin root is `../..`.
Read [../../references/hooks-settings.md](../../references/hooks-settings.md)
for hook lifecycle, setting-source boundaries, and safety details.

## First Move

Inspect the target files and scope before editing:

- user settings: machine-wide, do not commit;
- project settings: shareable only when the repo intentionally wants them;
- local project settings: machine-local, normally ignored;
- plugin settings: bundled with a plugin and active only when enabled;
- managed policy settings: admin-controlled and may override local changes.

Use CLI evidence when behavior differs from expectation:

```bash
python3 ../../scripts/claude_code_inspector.py --commands auto-mode --json
claude auto-mode config
claude auto-mode defaults
```

## Hook Design

Use hooks only when deterministic lifecycle automation is needed. Prefer narrow
events and matchers:

- tool gating or audit: `PreToolUse`, `PermissionRequest`, `PermissionDenied`;
- post-action validation: `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`;
- session startup/shutdown: `SessionStart`, `SessionEnd`;
- worktree hooks: `WorktreeCreate`, `WorktreeRemove`;
- config or instructions tracking: `ConfigChange`, `InstructionsLoaded`.

Keep hook scripts deterministic, reviewable, and low-output. Do not log full
prompts, secrets, or broad environment dumps.

## Tool Permissions

Use `--tools`, `--allowedTools`, and `--disallowedTools` for runtime scope:

```bash
claude --tools "Read,Grep,Glob"
claude --allowedTools "Bash(git *) Edit"
claude --disallowedTools "Bash(rm *)"
```

For durable rules, edit the appropriate settings file after confirming scope.
Do not use hooks as the only enforcement mechanism for high-risk actions.

## Settings Editing

Before editing:

1. Read the existing JSON and nearby project guidance.
2. Identify whether the file is committed or local-only.
3. Preserve unrelated keys.
4. Keep secrets out of JSON. Reference env vars or ignored local files.
5. Validate JSON syntax after the patch.

When troubleshooting, compare normal startup with `--safe-mode` and `--bare`
before deleting customizations.

## Safety Boundaries

- Do not add broad command hooks or HTTP hooks without a clear trust boundary.
- Do not store bearer tokens, API keys, OAuth secrets, cookies, or keychain values in settings or hook logs.
- Do not disable managed policy or weaken permissions just to make a workflow pass.
- Do not commit local-only machine settings unless the user explicitly asks and the repo policy allows it.

## Completion Standard

Report the setting scope, files changed, hook events/matchers/rules, validation
command, safe-mode or bare-mode comparison when used, and any residual risk.
