# Technology Intelligence Plugin

Technology Intelligence supports explicit software adoption decisions with a
small hot path and a versioned, inspectable evidence snapshot. It starts from a
needed capability, compares candidate technologies and their interfaces, and
keeps current runtime availability separate. It does not publish a universal
technology ranking.

## Skills

- `technology-advisor`: compare or shortlist technologies for a new system,
  migration, or explicit adoption decision. It does not handle routine coding
  or invoke, install, or authenticate an already selected CLI, MCP server, app,
  SDK, or connector.
- `technology-evidence-maintainer`: validate, inspect, diff, or deliberately
  refresh the evidence snapshot. Refresh captures raw source material and a
  receipt outside the plugin tree; it never changes assessments automatically.

## Decision And Evidence Model

The decision graph keeps four entities separate:

- capability: the outcome or job that is needed;
- technology: a candidate product, framework, protocol, or pattern;
- interface: a documented CLI, SDK, WASM, MCP, API, app, or skill surface;
- runtime: caller-supplied, short-lived installation and health facts.

The evidence envelope remains separate from that graph:

- candidate identity and aliases;
- dated observations from primary sources;
- context-specific assessments with hard gates and explicit gaps;
- publication, measurement, retrieval, and observation clocks kept separate;
- a schema for caller-supplied runtime capability state.

The researched snapshot contains 24 candidates across frontend/full-stack,
backend/data/infrastructure, agent delivery, and document processing. AnyDoc is
the first complete capability-to-interface vertical slice: the
`document-to-markdown` capability maps to its CLI, Node.js, Python, Rust,
WebAssembly, and Agent Skill surfaces. A positive assessment
must cite first-party evidence plus an independent signal or state a concrete
unverified gap. Popularity is never converted into an opaque universal score.

## Offline Tooling

From the repository root:

```bash
python3 plugins/technology-intelligence/scripts/technology_intelligence.py validate
python3 plugins/technology-intelligence/scripts/technology_intelligence.py query --capability document-to-markdown --format markdown
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

Source validation does not install candidate technologies or mutate runtime
facts. Local plugin activation remains a separate repository installer step.
