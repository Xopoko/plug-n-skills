# Technology Intelligence Plugin

Technology Intelligence supports explicit software adoption decisions with a
small hot path and a versioned, inspectable evidence snapshot. It compares
candidate fit for a stated context; it does not publish a universal technology
ranking.

## Skills

- `technology-advisor`: compare or shortlist technologies for a new system,
  migration, or explicit adoption decision. It does not handle routine coding
  or invoke, install, or authenticate an already selected CLI, MCP server, app,
  SDK, or connector.
- `technology-evidence-maintainer`: validate, inspect, diff, or deliberately
  refresh the evidence snapshot. Refresh captures raw source material and a
  receipt outside the plugin tree; it never changes assessments automatically.

## Evidence Model

The versioned files under `data/` keep four concerns separate:

- candidate identity and aliases;
- dated observations from primary sources;
- context-specific assessments with hard gates and explicit gaps;
- publication, measurement, retrieval, and observation clocks kept separate;
- a schema for caller-supplied runtime capability state.

The researched snapshot contains 23 candidates across frontend/full-stack,
backend/data/infrastructure, and agent delivery modes. A positive assessment
must cite first-party evidence plus an independent signal or state a concrete
unverified gap. Popularity is never converted into an opaque universal score.

## Offline Tooling

From the repository root:

```bash
python3 plugins/technology-intelligence/scripts/technology_intelligence.py validate
python3 plugins/technology-intelligence/scripts/technology_intelligence.py query --family frontend-fullstack --stage startup --format markdown
python3 plugins/technology-intelligence/scripts/technology_intelligence.py stale --as-of 2026-08-11
python3 plugins/technology-intelligence/scripts/technology_intelligence.py evidence-window --since 2026-02-11 --as-of 2026-08-11
python3 plugins/technology-intelligence/scripts/technology_intelligence.py check-triggers
python3 -m unittest discover -s plugins/technology-intelligence/tests
```

Compare two complete data directories without network access:

```bash
python3 plugins/technology-intelligence/scripts/technology_intelligence.py diff --old-dir path/to/old/data --new-dir plugins/technology-intelligence/data
```

Optional source capture is deliberately separate and requires an allowlisted
source, explicit network acknowledgement, and an output directory outside this
plugin:

```bash
python3 plugins/technology-intelligence/scripts/technology_intelligence.py refresh --source-id mcp-spec-2026-07-28 --acknowledge-network --output-dir tmp/technology-intelligence-refresh
```

Review the hash-bound receipt and raw artifact before proposing any source
edit. Refresh does not normalize evidence and cannot modify recommendations.

## Validation

Plugin-local checks:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/technology-intelligence
python3 plugins/capability-workbench/scripts/skill/audit_description_prefixes.py plugins/technology-intelligence
python3 plugins/capability-workbench/scripts/context/context_density_audit.py plugins/technology-intelligence --json --top 20
python3 plugins/technology-intelligence/scripts/technology_intelligence.py validate
python3 -m unittest discover -s plugins/technology-intelligence/tests
```

This source tree does not install or activate the plugin and does not mutate a
runtime cache, marketplace, MCP configuration, or global skill surface.
