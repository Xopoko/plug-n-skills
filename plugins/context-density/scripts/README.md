# Plugin Scripts

Runtime scripts live with the `context-density` skill at:

`skills/context-density/scripts/`

Bundled helpers:

- `token_count.py`: count local file tokens with `tiktoken` when available and
  an approximate fallback otherwise.
- `context_density_audit.py`: report token hotspots and prompt/context risks in
  deterministic source files.
- `codex_context_report.py`: CLI-compatible, read-only runtime context report
  for Codex and Claude Code: installed skills, plugin manifests, project
  instructions, MCP config sections, ranked sources, exports, and latest session
  token usage when available.
