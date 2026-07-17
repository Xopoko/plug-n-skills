---
name: codex-log-reader
description: Use when locating, summarizing, auditing, or debugging Codex session rollout JSONL logs by CODEX_THREAD_ID, cwd, query, issue key, project path, child or inherited-history symptoms, malformed or huge log symptoms, permission concerns, or "what happened in this Codex thread" questions.
---

# Codex Log Reader

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

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

   Once exact lookup succeeds, do not broaden to filesystem search, SQLite, or
   raw JSONL unless a specific missing fact requires it.

2. If the user gives a project path, issue key, app name, or vague "find that run", rank likely sessions:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" find --cwd /path/to/project --query "ISSUE-123" --since-days 14 --limit 10
   ```

3. Summarize the best candidate and measure trace quality without raw output:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" brief /path/to/rollout.jsonl
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" audit /path/to/rollout.jsonl --json
   ```

4. Reconstruct what happened with compact views:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" timeline /path/to/rollout.jsonl --tail 80
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" messages /path/to/rollout.jsonl --tail 40
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" commands /path/to/rollout.jsonl --tool shell_command --tail 80
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" commands /path/to/rollout.jsonl --tool exec --tail 80
   ```

   Child rollout views default to the active child scope. Add
   `--include-inherited` only when copied ancestor history is part of the
   question. `brief` and `audit` report the child, parent, root, boundary basis,
   confidence, and inherited line/byte cost explicitly. A low-confidence legacy
   boundary returns metadata-only `boundary-undetermined` scope; request
   `--include-inherited` explicitly before treating any content as relevant.

5. Search narrowly, then open only the needed line window:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" search "Traceback" /path/to/rollout.jsonl --limit 20
   nl -ba /path/to/rollout.jsonl | sed -n '120,150p'
   ```

Only use raw `nl`, `sed`, or `jq` after the helper has identified a path and
line range.

## Audit Interpretation

`audit` reports deterministic evidence: logical message counts, suppressed
mirror pairs, outer tool calls, call/output pairing, explicit failures,
normalized-input repeat candidates, compaction markers, and inherited-prefix
cost. Treat repeat
candidates as review leads, not proof of waste; validate the surrounding state
before recommending a different tactic. Signatures intentionally normalize
whitespace and redacted values, so their potential-savings count is an upper
bound, not a causal conclusion.

Modern orchestrator logs may store a JavaScript `exec` wrapper as one custom
tool call. The helper shows that captured outer source after redaction but does
not invent structured nested calls that the JSONL did not record.

For a session retrospective, turn each supported finding into this compact
contract:

1. observation with rollout id plus line or timestamp and measured count;
2. inference and confidence, kept separate from the observation;
3. concrete alternative tactic and estimated impact;
4. durable remediation surface, if warranted: global or repo `AGENTS.md` for a
   stable invariant, script for deterministic measurement, skill for a
   conditional workflow, or MCP only after repeated indexed cross-session use.

Do not manufacture a tactic for an unsupported semantic claim. Report the
telemetry limitation and the smallest instrumentation change instead.

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
python3 -m unittest discover -s "$PLUGIN_ROOT/tests" -q
```
