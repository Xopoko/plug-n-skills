# Codex Log Reader Safety Reference

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

Use this reference with `skills/codex-log-reader/SKILL.md` when raw session
evidence, manual `jq`, or log-health interpretation is needed.

## Log Locations

- Session logs: `$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<timestamp>-<CODEX_THREAD_ID>.jsonl`
- Archived sessions: `$CODEX_HOME/archived_sessions/rollout-*.jsonl`
- Thread titles and UI state: `$CODEX_HOME/.codex-global-state.json`
- Shell snapshots and terminal support: `$CODEX_HOME/shell_snapshots/`
- Older/general TUI log: `$CODEX_HOME/log/codex-tui.log`

If `CODEX_HOME` is unset, tools usually use `~/.codex`.

Explicit file targets are restricted to regular `rollout-*.jsonl` files. This
keeps the helper from becoming a generic arbitrary-file printer; use a separate
purpose-built reader for other artifacts.

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

Modern child rollouts may start with the child's `session_meta`, followed by
copied ancestor metadata and history. Do not let a later copied `session_meta`
replace the rollout id from the filename or first metadata record. Use the
helper's active boundary and lineage fields; active views exclude the inherited
prefix unless `--include-inherited` is requested. If only a low-confidence
legacy boundary is available, the helper returns metadata-only
`boundary-undetermined` scope until all history is requested explicitly.

The runtime can mirror one logical user or assistant message as adjacent
`event_msg` and `response_item/message` records. The helper suppresses only
these adjacent cross-shape pairs, not a later repeated message. Some modern
records also use `response_item/agent_message`.

An orchestrator may record a `custom_tool_call` named `exec` whose input is
JavaScript that calls other tools. The outer call is evidence; nested calls are
not structured JSONL events and must not be presented as independently verified
tool calls.

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

List legacy executed shell commands only:

```bash
jq -r 'select(.type=="response_item" and .payload.type=="function_call" and .payload.name=="exec_command")
  | (.payload.arguments | fromjson | .cmd)' /path/to/rollout.jsonl | head
```

For current `shell_command` and outer `exec` records, prefer the helper because
their payload shapes differ and its output is redacted.

Search with line numbers:

```bash
rg -n --context 2 "ISSUE-123|Traceback|task_complete" /path/to/rollout.jsonl
```

Avoid `jq -s` on large rollout files. Stream line-by-line.

## Health Checks

Use `doctor` when the Codex UI cannot see a thread, resume behaves strangely, or
a log may be too large:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" doctor --since-days 30 --limit 50
python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" doctor /path/to/rollout.jsonl
```

It checks malformed JSONL lines, very large rollout files, archived placement,
and loose Unix permissions. Permission warnings are POSIX-only; Windows ACLs
cannot be inferred from Unix mode bits. Treat findings as evidence for
diagnosis, not as permission to delete, move, chmod, or edit logs without
explicit approval.

## Secret Handling

- The helper recursively redacts common sensitive structured keys, quoted and
  bare assignments, authorization and cookie headers, URL credentials, private
  key blocks, long token-like blobs, and terminal control characters. Treat
  this as defense in depth, not proof that an unknown credential format is safe.
- Do not paste raw rollout lines unless the user explicitly needs that exact excerpt and you checked it for secrets.
- Default to snippets, line numbers, counts, tool names, cwd, timestamps, and summarized commands.
- Never expose raw secrets, cookies, Authorization headers, API keys, private keys, seed phrases, wallet material, `.env` values, or credential-bearing history.
- Build/tool `*-state.json` files may contain full environment dumps; do not treat them as safe logs.
- If searching for credentials, report indicators and line numbers only, not matched secret values.
