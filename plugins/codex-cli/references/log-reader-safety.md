# Codex Log Reader Safety Reference

Use this reference with `skills/codex-log-reader/SKILL.md` when raw session
evidence, manual `jq`, or log-health interpretation is needed.

## Log Locations

- Session logs: `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<timestamp>-<CODEX_THREAD_ID>.jsonl`
- Archived sessions: `$CODEX_HOME/archived_sessions/rollout-*.jsonl`
- Thread titles and UI state: `$CODEX_HOME/.codex-global-state.json`
- Shell snapshots and terminal support: `$CODEX_HOME/shell_snapshots/`
- Older/general TUI log: `$CODEX_HOME/log/codex-tui.log`

If `CODEX_HOME` is unset, tools usually use `~/.codex`.

## Session JSONL Shape

Common top-level `type` values:

- `session_meta`: session id, cwd, source, model/provider, git hints.
- `turn_context`: per-turn cwd/model/sandbox/current-date context.
- `event_msg`: runtime events such as `user_message`, `agent_message`, `token_count`, `task_started`, `task_complete`, `turn_aborted`.
- `response_item`: messages, reasoning, function calls, and tool outputs.
- `compacted`: context compaction marker.

Common `response_item.payload.type` values include `message`, `reasoning`,
`function_call`, `function_call_output`, `custom_tool_call`, and
`custom_tool_call_output`.

## Manual jq And rg Fallback

Use these only for exact follow-up after `codex_log_reader.py` narrows the target
file and line range.

Count record types:

```bash
jq -r '.type' /path/to/rollout.jsonl | sort | uniq -c | sort -nr | head
```

List assistant plaintext events:

```bash
jq -r 'select(.type=="event_msg" and .payload.type=="agent_message") | .payload.message' /path/to/rollout.jsonl | head
```

List executed shell commands only:

```bash
jq -r 'select(.type=="response_item" and .payload.type=="function_call" and .payload.name=="exec_command")
  | (.payload.arguments | fromjson | .cmd)' /path/to/rollout.jsonl | head
```

Search with line numbers:

```bash
rg -n --context 2 "ISSUE-123|Traceback|task_complete" /path/to/rollout.jsonl
```

Avoid `jq -s` on large rollout files. Stream line-by-line.

## Health Checks

Use `doctor` when the Codex UI cannot see a thread, resume behaves strangely, or
a log may be too large:

```bash
python3 ../../scripts/codex_log_reader.py doctor --since-days 30 --limit 50
python3 ../../scripts/codex_log_reader.py doctor /path/to/rollout.jsonl
```

It checks malformed JSONL lines, very large rollout files, archived placement,
and loose Unix permissions. Treat findings as evidence for diagnosis, not as
permission to delete, move, chmod, or edit logs without explicit approval.

## Secret Handling

- Do not paste raw rollout lines unless the user explicitly needs that exact excerpt and you checked it for secrets.
- Default to snippets, line numbers, counts, tool names, cwd, timestamps, and summarized commands.
- Never expose raw secrets, cookies, Authorization headers, API keys, private keys, seed phrases, wallet material, `.env` values, or credential-bearing history.
- Build/tool `*-state.json` files may contain full environment dumps; do not treat them as safe logs.
- If searching for credentials, report indicators and line numbers only, not matched secret values.
