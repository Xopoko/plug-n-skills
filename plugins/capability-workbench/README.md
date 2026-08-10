# Capability Workbench

Capability Workbench is the lifecycle toolkit for agent skills and plugins. It
discovers, synthesizes, creates, audits, installs, repairs, packages, and
reshapes capability portfolios while keeping trigger metadata, evidence,
validation, and activation scope explicit.

Use the adjacent `agent-harness` plugin for Codex or Claude runtime operation,
local scheduler proof, agent harness engineering, and harness evaluation.

## Included Skills

- `capability-workbench` routes the capability lifecycle.
- `capability-synthesizer` researches and distills capabilities.
- `capability-portfolio-architect` reshapes plugin and skill boundaries.
- `skill-factory` and `plugin-factory` create validated artifacts.
- `skill-trigger-metadata` designs discriminative discovery metadata.
- `agent-guidance-factory` authors repository guidance.
- `capability-auditor` reviews safety, coverage, contracts, and token cost.
- `capability-reality-repair` repairs stale source contracts.
- `skill-installer-vetter` vets and installs selected capabilities.

## Validation

From this plugin directory:

```bash
python3 tests/run_smoke.py
```

The repository validator also checks manifest parity and publication surfaces.
