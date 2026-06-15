---
name: codex-log-reader
description: Use when locating, summarizing, or debugging Codex session rollout JSONL logs by CODEX_THREAD_ID, cwd, query, issue key, project path, malformed or huge log symptoms, world-readable log concerns, or "what happened in this Codex thread" questions.
---

# Codex Log Reader

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.
On Windows PowerShell, set and read this as `$env:PLUGIN_ROOT`; translate shown POSIX-style `$PLUGIN_ROOT/...` paths to the same path under `$env:PLUGIN_ROOT`.

Use this skill to find the smallest useful slice of Codex logs before opening
raw JSONL. Session logs are useful evidence, but they can contain user prompts,
tool I/O, environment fragments, URLs, and secrets.

For deeper log locations, JSONL shape, manual `jq` fallbacks, and safety rules,
read `$PLUGIN_ROOT/references/log-reader-safety.md`.

## Fast Path

Primary tool:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" --help
```

Decision tree:

1. If the user provides `CODEX_THREAD_ID`, locate exactly:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" find --thread-id <thread-id>
   ```

2. If the user gives a project path, issue key, app name, or vague "find that run", rank likely sessions:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" find --cwd /path/to/project --query "ISSUE-123" --since-days 14 --limit 10
   ```

3. Summarize the best candidate without raw output:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" brief /path/to/rollout.jsonl
   ```

4. Reconstruct what happened with compact views:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" timeline /path/to/rollout.jsonl --tail 80
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" messages /path/to/rollout.jsonl --tail 40
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" commands /path/to/rollout.jsonl --tool exec_command --tail 80
   ```

5. Search narrowly, then open only the needed line window:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" search "Traceback" /path/to/rollout.jsonl --limit 20
   nl -ba /path/to/rollout.jsonl | sed -n '120,150p'
   ```

Only use raw `nl`, `sed`, or `jq` after the helper has identified a path and
line range.

## Health Checks

Use `doctor` when the Codex UI cannot see a thread, resume behaves strangely, or
a log may be too large:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" doctor --since-days 30 --limit 50
python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" doctor /path/to/rollout.jsonl
```

It checks malformed JSONL lines, very large rollout files, archived placement,
and loose Unix permissions. Treat findings as evidence for diagnosis, not as
permission to delete, move, chmod, or edit logs without explicit approval.

## Safety Rules

- Do not paste raw rollout lines unless the user explicitly needs that exact excerpt and you checked it for secrets.
- Default to snippets, line numbers, counts, tool names, cwd, timestamps, and summarized commands.
- Never expose raw secrets, cookies, Authorization headers, API keys, private keys, seed phrases, wallet material, `.env` values, or credential-bearing history.
- Build/tool `*-state.json` files may contain full environment dumps; do not treat them as safe logs.
- If searching for credentials, report indicators and line numbers only, not matched secret values.

## Tool Validation

The helper has local tests:

```bash
python3 -m unittest discover -s ../../tests -q
```
