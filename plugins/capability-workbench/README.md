# Capability Workbench

Capability Workbench is the artifact authoring and governance plane of agent
capability engineering. It turns desired behavior and observed gaps into
reusable, validated skills, plugins, guidance, trigger contracts, and coherent
capability portfolios. In short: **Capability Workbench - Agent Capability Engineering.**

Use the adjacent `agent-harness` plugin for Codex or Claude runtime operation,
local scheduler proof, agent harness engineering, and harness reliability
evaluation.

## Lifecycle

| Lane | Question | Primary skills |
| --- | --- | --- |
| Frame | What behavior should change, and what artifact or boundary belongs here? | `capability-synthesizer`, `capability-portfolio-architect`, `skill-trigger-metadata` |
| Author | Which portable skill, plugin, or repository guidance should encode it? | `skill-factory`, `plugin-factory`, `agent-guidance-factory` |
| Assure and evolve | Is the artifact safe, coherent, current, and behaviorally better than its baseline? | `capability-auditor`, `capability-evaluation`, `capability-reality-repair` |
| Activate | Should a vetted artifact be installed or published on an explicitly selected surface? | `skill-installer-vetter`, `plugin-factory` |

## Included Skills

- `capability-workbench` routes the capability lifecycle.
- `capability-synthesizer` researches and distills capabilities.
- `capability-portfolio-architect` reshapes plugin and skill boundaries.
- `skill-factory` and `plugin-factory` create validated artifacts.
- `skill-trigger-metadata` designs discriminative discovery metadata.
- `agent-guidance-factory` authors repository guidance.
- `capability-auditor` reviews safety, coverage, contracts, and token cost.
- `capability-evaluation` compares capability artifacts with a baseline and
  produces a validated adoption receipt.
- `capability-reality-repair` repairs stale source contracts.
- `skill-installer-vetter` vets and installs selected capabilities.

## Validation

From this plugin directory:

```bash
python3 tests/run_smoke.py
```

The repository validator also checks manifest parity and publication surfaces.
