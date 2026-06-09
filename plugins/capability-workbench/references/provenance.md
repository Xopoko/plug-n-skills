# Provenance

This plugin distills and bundles mechanisms from inspectable sources:

| Source | Path | Adopted or adapted mechanisms |
| --- | --- | --- |
| `skill-synthesizer` | Codex: `${CODEX_HOME:-$HOME/.codex}/skills/skill-synthesizer`, Claude: `${CLAUDE_HOME:-$HOME/.claude}/skills/skill-synthesizer` | target contract, mode decision, mechanism scoring, coverage/loss ledger, synthesis reports, static candidate audit |
| `skill-creator` | Codex: `${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator`, Claude: `${CLAUDE_HOME:-$HOME/.claude}/skills/.system/skill-creator` | skill initialization, progressive disclosure, metadata generation, quick validation |
| `skill-installer` | Codex: `${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer`, Claude: `${CLAUDE_HOME:-$HOME/.claude}/skills/.system/skill-installer` | curated/GitHub listing and install helpers, restart communication, existing destination safety |
| `plugin-creator` | Codex: `${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator`, Claude: `${CLAUDE_HOME:-$HOME/.claude}/skills/.system/plugin-creator` | plugin scaffold, manifest validation, marketplace entry rules, install/cache visibility gate, agent app handoff |
| `context-density` | `${HOME}/plugins/context-density` | token measurement, load-path classification, prompt-contract risk scan, context-density refactor workflow |
| auxiliary heuristics | Prior local skill prototypes and the bundled `context-density` scripts | token-efficiency, context diagnostics, and schema-first prompt contract heuristics |

Bundled scripts are copied or lightly wrapped only when they are inspectable and self-contained enough for local use. Required paid APIs, API keys, telemetry, external generation services, and hidden network dependencies are not part of the core plugin.
