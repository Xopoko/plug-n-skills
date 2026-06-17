---
name: capability-portfolio-architect
description: >-
  Use when auditing agent skill/plugin portfolio architecture for cross-plugin
  capability overlap, weak routing, duplicated or missing skills,
  split/merge/delete/move decisions, shared capability extraction,
  reference/script extraction, or plugin boundary redesign. For safety,
  coverage, or validation review of a single artifact without boundary
  changes, use capability-auditor instead.
license: MIT
---

# Capability Portfolio Architect

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Use this when a capability set may have the wrong shape.

This skill owns structural decisions across skills and plugins.

Decisions include keep, split, merge, remove, rename, route, move skills between plugins, extract shared capability patterns, move detail to references, extract deterministic scripts, or create a new skill/plugin boundary.

## Boundary

- Token or term overlap is never enough to delete, move, split, or merge.
- Transfer trigger coverage, safety boundaries, commands, output contracts, install surface, validators, and rollback paths before structural edits.
- Use `context-density` first when the primary problem is context cost, hot-path prose, prompt contracts, or measured placement.
- Use this skill when measurement exposes overlapping skills, missing routers, overloaded skills, duplicated workflows, bad plugin boundaries, or cross-plugin responsibility overlap.
- Also use it when hot-path examples belong in references, deterministic procedures hide in prose, or obsolete skills need review.
- Use `skill-trigger-metadata` for final name/description trigger wording after the target architecture is chosen.
- Use `skill-factory` or `plugin-factory` to perform the concrete edits after this skill produces the decision ledger.

## Workflow

1. Bind the portfolio scope: one skill, one plugin, multiple plugins, the whole repository, or a marketplace package.
2. Measure hot path and structure:
   ```bash
   python3 "$PLUGIN_ROOT/scripts/portfolio/portfolio_architecture_audit.py" <plugin-dir> --json
   python3 "$PLUGIN_ROOT/scripts/portfolio/portfolio_architecture_audit.py" plugins --json
   python3 "$PLUGIN_ROOT/scripts/context/context_density_audit.py" <plugin-dir> --json --top 20
   ```
3. Inventory current responsibilities:
   skill names, descriptions, router rows, references, scripts, validation commands, install surface, adjacent plugins, and cross-plugin overlap candidates.
4. Build a decision ledger with one row per candidate action:
   - `keep`: current boundary is coherent.
   - `metadata-review`: trigger scent or boundary wording is weak.
   - `reference-extract`: hot path contains rare details.
   - `script-extract`: repeated deterministic procedure should become a script.
   - `split-review`: one skill owns multiple independently triggerable workflows.
   - `merge-review`: two skills share the same trigger surface and workflow.
   - `delete-review`: capability is obsolete, unreachable, unsafe, or fully replaced.
   - `router-review`: plugin needs an explicit router or router repair.
   - `plugin-split-review`: one plugin contains multiple independently marketable or load-heavy families.
   - `plugin-merge-review`: two plugins are not independently coherent products.
   - `move-review`: a skill appears to belong in another plugin boundary.
   - `cross-plugin-overlap-review`: two plugins share a responsibility pattern that needs keep/move/merge/extract-shared/defer.
   - `shared-capability-review`: repeated workflow mechanics should become a shared script, reference, or Workbench pattern.
5. For each row, record evidence, intended final surface, preserved invariants, validation scenario, risk, and rollback path.
6. Sequence edits conservatively: route/metadata fixes first, then reference/script/shared extraction, then move/split/merge/delete only when validation and trigger coverage can be preserved.
7. Validate with skill/plugin validators, token measurement, trigger probes, and install/visibility checks when activation is required.

## Decision Rules

- Prefer routers and narrow skills when workflows trigger independently.
- Prefer references when workflows share a trigger and differ only by detail depth.
- Prefer shared scripts or references when domain plugins repeat lifecycle mechanics but remain separate products.
- Use `$PLUGIN_ROOT/references/portfolio-architecture.md` for full action proof rules.

## Outputs

For material work, produce:

```markdown
Portfolio architecture audit:
- Scope:
- Current architecture:
- Measurements:
- Cross-plugin candidates:
- Candidate actions:
- Decision ledger:
- Adopted edits:
- Rejected/deferred edits:
- Preserved invariants:
- Validation:
- Install/cache state:
- Residual risks:
```

Use `$PLUGIN_ROOT/references/portfolio-architecture.md` for the JSON ledger schema and action matrix.
