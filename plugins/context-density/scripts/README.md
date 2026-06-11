# Plugin Scripts

Runtime scripts live with the `context-density` skill at:

`skills/context-density/scripts/`

Bundled helpers:

- `token_count.py`: count local file tokens with `tiktoken` when available and
  an approximate fallback otherwise.
- `context_density_audit.py`: report token hotspots and prompt/context risks in
  deterministic source files.
- `agent_context_report.py`: CLI-compatible, read-only runtime context report
  for Codex and Claude Code: installed skills, plugin manifests, project
  instructions, MCP config sections, ranked sources, exports, and latest session
  token usage when available.
- `description_overlap.py`: rank skill-description pairs competing for routing
  by token overlap.
- `compression_invariants.py`: deterministic original-vs-compressed invariant
  check (frontmatter, fenced blocks, code spans, placeholder inventories) for
  the compression pipeline.
