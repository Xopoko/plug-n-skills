# Token Diagnostics

Use deterministic measurements before arguing about context cost.

## Local File Measurement

```bash
python3 scripts/token_count.py AGENTS.md README.md --json
python3 scripts/token_count.py skills --json --top 20
python3 scripts/context_density_audit.py AGENTS.md skills --json --top 20
```

The bundled counter uses `tiktoken` when available and falls back to an approximate `chars / 4` estimate. Mark approximate counts as directional.

## Host Runtime Measurement

Use the bundled runtime reporter when the question is about real startup
context, active skills, MCP config, plugin manifests, source contributions,
exportable reports, or ranked raw context sources. It supports Codex and Claude
Code with `--agent codex|claude`.

| Question | Command |
| --- | --- |
| Installed agents | `python3 scripts/codex_context_report.py agents --json` |
| Overall startup/context pressure | `python3 scripts/codex_context_report.py brief --agent codex --project . --usage --json` |
| Largest skill metadata/body costs | `python3 scripts/codex_context_report.py skills --agent codex --limit 10 --ndjson` |
| One skill's body/metadata cost | `python3 scripts/codex_context_report.py skill SKILL_NAME --agent codex --json` |
| MCP config sections | `python3 scripts/codex_context_report.py mcp --agent codex --no-introspect-mcp --json` |
| MCP server tool filters | `python3 scripts/codex_context_report.py mcp --agent codex --tools SERVER --json` |
| Ranked raw sources | `python3 scripts/codex_context_report.py sources --agent codex --ndjson --limit 20` |
| Export all rows | `python3 scripts/codex_context_report.py export markdown --agent codex --project .` |

The reporter reads local files only: project `AGENTS.md`, installed
`SKILL.md` files, plugin manifests, Codex config, and MCP config sections. It
also reads Claude Code settings and skills when `--agent claude` is selected.
With `--usage` it additionally reads local session transcript files
(`~/.codex/sessions/**/*.jsonl`, `~/.claude/projects/**/*.jsonl`) but extracts
only token-usage counters and session IDs, never message content. Config and
MCP `env` values are token-counted, not printed; emitted MCP URLs are scrubbed
of userinfo and query values. It does not introspect live MCP tool schemas and
does not mutate host-agent configuration.

If another public host diagnostic command is available, it may be used for
runtime-only information the bundled reporter cannot see. When any host
diagnostic command can change configuration, require explicit user approval
before running it and report the mutation clearly.

## Diagnostic Report

Include command used, exact/approx mode, total tokens, top hotspots, source category, and whether changes affect hot context, reference context, runtime context, or only diagnostics.

For long-context or compression work, also include whether the diagnostic found middle-buried commitments, context-window assumptions, retrieval/provenance risks, token-only compression claims, total-cost gaps, or missing task validation.
