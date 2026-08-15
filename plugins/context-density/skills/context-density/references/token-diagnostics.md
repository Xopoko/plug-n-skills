# Token Diagnostics

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

Use deterministic measurements before arguing about context cost.

## Local File Measurement

```bash
python3 "$PLUGIN_ROOT/skills/context-density/scripts/token_count.py" AGENTS.md README.md --json
python3 "$PLUGIN_ROOT/skills/context-density/scripts/token_count.py" skills --json --top 20
python3 "$PLUGIN_ROOT/skills/context-density/scripts/context_density_audit.py" AGENTS.md skills --json --top 20
```

The bundled counter uses `tiktoken` when available and falls back to an approximate `chars / 4` estimate. Mark approximate counts as directional.

## Host Context Inventory

Use the bundled reporter when the question is about discovered local context,
configured enabled plugin IDs, model-visible startup evidence, MCP config,
plugin manifests, source contributions, exportable reports, or ranked raw
context sources. It supports Codex and Claude Code with `--agent codex|claude`.

| Question | Command |
| --- | --- |
| Installed agents | `python3 "$PLUGIN_ROOT/skills/context-density/scripts/agent_context_report.py" agents --json` |
| Discovered corpus and startup evidence | `python3 "$PLUGIN_ROOT/skills/context-density/scripts/agent_context_report.py" brief --agent <codex|claude> --project . --usage --json` |
| Largest skill metadata/body costs | `python3 "$PLUGIN_ROOT/skills/context-density/scripts/agent_context_report.py" skills --agent <codex|claude> --limit 10 --ndjson` |
| One skill's body/metadata cost | `python3 "$PLUGIN_ROOT/skills/context-density/scripts/agent_context_report.py" skill SKILL_NAME --agent <codex|claude> --json` |
| MCP config sections | `python3 "$PLUGIN_ROOT/skills/context-density/scripts/agent_context_report.py" mcp --agent <codex|claude> --no-introspect-mcp --json` |
| MCP server tool filters | `python3 "$PLUGIN_ROOT/skills/context-density/scripts/agent_context_report.py" mcp --agent <codex|claude> --tools SERVER --json` |
| Ranked raw sources | `python3 "$PLUGIN_ROOT/skills/context-density/scripts/agent_context_report.py" sources --agent <codex|claude> --ndjson --limit 20` |
| Export all rows | `python3 "$PLUGIN_ROOT/skills/context-density/scripts/agent_context_report.py" export markdown --agent <codex|claude> --project .` |

The reporter reads project `AGENTS.md`, discovered `SKILL.md` files, plugin
manifests, the selected agent's config, and MCP config sections. For Codex it
parses explicit `enabled = true` entries under
`[plugins."name@marketplace"]` in `$AGENT_HOME/config.toml`. It does not invoke
Codex or another subprocess. A complete config inventory can exclude cache
entries for plugin IDs not configured as enabled, but it cannot select among
multiple cached versions: cache versions, runtime activation, and model
visibility remain unverified unless separate read evidence proves them.

File presence is not prompt evidence. `startupTokens` and
`modelVisibleStartupTokens` are therefore `null` until a source has direct
model-visible evidence. `discoveredMetadataTokens` measures routing records on
disk, while `onDemandCorpusTokens` measures available skill bodies.
`loadedBodyTokens` remains zero unless body-read evidence exists; a nonzero
`bodyTokens` value alone never means that body was loaded.
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
