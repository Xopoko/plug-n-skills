# Token Diagnostics

Use deterministic measurements before arguing about context cost.

## Local File Measurement

```bash
python3 scripts/token_count.py AGENTS.md README.md --json
python3 scripts/token_count.py skills --json --top 20
python3 scripts/context_density_audit.py AGENTS.md skills --json --top 20
```

The bundled counter uses `tiktoken` when available and falls back to an approximate `chars / 4` estimate. Mark approximate counts as directional.

## Codex Runtime Measurement

Use `codex-token-lens` only when the question is about Codex runtime context, startup pressure, skills/MCP/tool schemas, source contributions, or latest session usage.

| Question | Command |
| --- | --- |
| Overall startup/context pressure | `codex-token-lens brief --no-introspect-mcp` |
| Largest skill metadata/body costs | `codex-token-lens skills --limit 10` |
| One skill's body/metadata/observed reads | `codex-token-lens skill SKILL_NAME` |
| MCP schema totals | `codex-token-lens mcp --no-introspect-mcp` |
| One MCP server's tool-level cost | `codex-token-lens mcp --tools SERVER_NAME` |
| Ranked raw sources | `codex-token-lens sources --ndjson --limit 20` |

Add `--project PATH` for project-local `.codex` context. Add `--usage` only when session-log usage is part of the question. Keep `--no-introspect-mcp` for low-side-effect diagnostics.

## Controls

Only run controls after explicit user approval or a request to change Lens estimates/config:

```bash
codex-token-lens disable skill SKILL_NAME
codex-token-lens enable skill SKILL_NAME
codex-token-lens disable mcp-tool SERVER_NAME TOOL_NAME
codex-token-lens enable mcp-tool SERVER_NAME TOOL_NAME
```

Skill controls affect Lens policy estimates. MCP tool controls mutate Codex config, so report that clearly.

## Diagnostic Report

Include command used, exact/approx mode, total tokens, top hotspots, source category, and whether changes affect hot context, reference context, or only diagnostics.

For long-context or compression work, also include whether the diagnostic found middle-buried commitments, context-window assumptions, retrieval/provenance risks, token-only compression claims, total-cost gaps, or missing task validation.
