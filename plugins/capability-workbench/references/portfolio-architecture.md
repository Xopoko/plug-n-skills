# Capability Portfolio Architecture

Use this reference when refactoring the structure of skills and plugins, not just their wording.

## Action Matrix

| Action | Use when | Required proof |
| --- | --- | --- |
| `keep` | Boundary is coherent and validation is current. | Measurement and no material overlap/loss risk. |
| `metadata-review` | Skill exists but the agent may under-trigger, over-trigger, or act from metadata without reading the body. | Trigger probes and updated description/name. |
| `reference-extract` | Rare detail sits in hot `SKILL.md`. | Link from hot path, token delta, preserved detail. |
| `script-extract` | A repeated deterministic procedure is described in prose. | Script test and skill command update. |
| `split-review` | One skill owns independently triggerable workflows. | New boundaries, router update, validation for each new skill. |
| `merge-review` | Skills duplicate the same responsibility and trigger surface. | Surviving trigger route, redirected references, no validation loss. |
| `delete-review` | Skill is obsolete, unsafe, unreachable, or fully replaced. | Replacement path, removed routing, install/cache validation. |
| `router-review` | A plugin has many adjacent skills or weak first-hop routing. | Router table and trigger boundary probes. |
| `plugin-split-review` | One plugin contains independently marketable or load-heavy capability families. | Proposed product boundaries, manifest/catalog plan, validation for each resulting plugin. |
| `plugin-merge-review` | Two plugins are not coherent standalone products. | Unified trigger surface, dependency/install compatibility, migration route, catalog update. |
| `move-review` | A skill appears to belong in another plugin boundary. | Source route, destination route, preserved triggers, updated references, validation in both plugins. |
| `cross-plugin-overlap-review` | Two plugins repeat a responsibility pattern or adjacent workflow. | Decision to keep separate, move, merge, or extract shared mechanics, with rationale. |
| `shared-capability-review` | Several plugins repeat lifecycle mechanics but should remain separate domain products. | Shared script/reference/Workbench pattern and plugin-local usage proof. |

## Decision Ledger

Use strict JSON when the result feeds scripts, review, or later implementation:

```json
{
  "schema": "codex.capability_portfolio_decision.v1",
  "scope": "plugins/<plugin-name>|plugins",
  "decisions": [
    {
      "subject": "skill-or-plugin-name",
      "action": "keep|metadata-review|reference-extract|script-extract|split-review|merge-review|delete-review|router-review|plugin-split-review|plugin-merge-review|move-review|cross-plugin-overlap-review|shared-capability-review",
      "evidence": ["file path, metric, trigger probe, validator output"],
      "rationale": "short reason",
      "preserved_invariants": ["trigger", "command", "safety", "output", "validation"],
      "final_surface": "hot-path|reference|script|router|plugin|shared|moved|removed|deferred",
      "validation": ["command or scenario"],
      "rollback": "how to restore behavior if the change is wrong",
      "status": "adopted|rejected|deferred"
    }
  ]
}
```

## Review Heuristics

- Start from user/task trigger surfaces, not file count.
- Treat token cost as a symptom, not a sufficient reason to split or merge.
- Review the whole plugin portfolio when overlap may cross plugin boundaries.
- Treat cross-plugin overlap as a review queue, not an automatic merge command.
- Prefer router plus narrow skills when workflows are independently triggered.
- Prefer one skill plus references when workflows share the same trigger and differ only by detail depth.
- Prefer separate plugins when the audience, install surface, runtime dependencies, or release cadence differ.
- Prefer shared scripts or Workbench references when several domain plugins repeat the same lifecycle mechanics.
- Prefer scripts for deterministic, repeatable operations that users will ask for again.
- Prefer references for bulky examples, matrices, troubleshooting, and source ledgers.
- Keep deletion rare and reversible; transfer trigger coverage before removal.
