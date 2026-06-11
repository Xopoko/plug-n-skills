# Synthesis Contract

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

Use this reference for capability synthesis, plugin-pack synthesis, and retrospective improvement of generated skills/plugins.

## Mode Decision

| Mode | Use when | Required output |
| --- | --- | --- |
| `new-skill` | One cohesive capability fits in one skill plus optional resources. | Final skill folder, reports, validator proof. |
| `augment-existing` | User names an existing skill/plugin and wants it improved. | In-place patch on the selected surface or explicit no-patch rationale, reports, validation. |
| `plugin-pack` | Capability naturally splits into multiple triggerable skills. | Plugin manifest, skills, shared resources, validation, and marketplace visibility proof when installation is required. |
| `source-import` | User wants existing skills mirrored with minimal transformation. | Provenance, safety/import report, delivery proof, and install proof only when required. |
| `reference-only` | Sources are unsafe, thin, or not inspectable enough. | Reports and recommendation; no fake synthesis claim. |

If the mode changes, update discovery, matrix, distillation, changelog, and validation notes before final delivery.

## Target Binding

When the user names a skill or plugin with `$...` or `@...`, bind that named capability as the primary target for create/augment/synthesize/strengthen/install requests. Then choose the edit surface from the latest user message, repo instructions, and workspace profile.

Use the current repo/project/path as the target when it is selected by user wording, applicable repo instructions, or a recognizable plugin/skill source tree for the requested capability. Dirty worktree state and unrelated local paths do not override the latest user message.

## Discovery Breadth Gate

Record one discovery breadth before candidate review:

| Breadth | Default? | Criteria |
| --- | --- | --- |
| `local-only` | no | User explicitly says local/offline, the change is a tiny project-local patch, network/search is unavailable, or external inspection would require credentials/telemetry/install. Do not claim global optimum. |
| `external-light` | no | Use only for quick/time-boxed follow-up checks where the user does not want a full synthesis pass. |
| `external-broad` | yes | Use for synthesis, augmentation, marketplace capability work, "well-vetted", "strengthen", "distill", or global capability acquisition. Search public sources first and local sources second. |

For `new-skill`, `augment-existing`, and `plugin-pack` requests that use words like synthesize, distill, strengthen, improve, well-vetted, or marketplace capability, use `external-broad` by default. Skipping it requires an explicit reason in `discovery-report.md`.

External discovery is the primary corpus. Local skills are supplementary evidence, regression baselines, implementation candidates, and installation targets, not the default search boundary.

Before editing the target, create `<output-dir>/external-discovery-ledger.json` and validate it with `$PLUGIN_ROOT/scripts/synthesis/external_discovery_gate.py`. This ledger is the machine-readable source for breadth, source families, search waves, candidates, blockers, and stop condition. Markdown reports are summaries, not the gate.

## Install Scope Gate

Record one installation scope before implementation:

| Scope | Default? | Criteria |
| --- | --- | --- |
| `global-agent` | no | Requested skills, plugins, MCP capabilities, or plugin packs should be installed for global agent use (Codex, Claude, Cursor, or another supported agent), or no repo source surface is selected for a personal marketplace artifact. |
| `repo-local` | no | Current or named repository is the source surface according to user wording, repo instructions, or workspace profile. |
| `workspace-snapshot` | no | Only for partial synthesis, reference drafts, or explicit no-install output. |
| `reference-only` | no | Use when sources are unsafe/thin/uninspectable or the user only wants analysis. |

Before editing the target, create `<output-dir>/install-scope.json` and validate it with `$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py`. Before claiming a complete result, validate the same file with `--final`.

For `repo-local`, include `local_request_evidence` from the latest user message, repo instructions, or workspace profile. Dirty worktree state, plugin mentions, or target-specific context are not valid local-scope evidence by themselves.

Global agent destinations:

- skill: agent's global skills dir — Codex: `${CODEX_HOME:-$HOME/.codex}/skills/<skill-name>`, Claude: `${CLAUDE_HOME:-$HOME/.claude}/skills/<skill-name>`, Cursor: `${CURSOR_HOME:-$HOME/.cursor}/skills/<skill-name>`. Detect the active agent with `$PLUGIN_ROOT/scripts/agent_target.py` and use its dir; other agents follow the same `<agent-home>/skills` convention.
- plugin: `$HOME/plugins/<plugin-name>` plus `$HOME/.agents/plugins/marketplace.json`; cache-backed as `<plugin-name>@local` only when installation is required. The marketplace/cache flow is Codex-specific; Claude installs plugins through its own marketplace tooling, and Cursor consumes skills directly without a plugin marketplace;
- MCP capability: global agent plugin/configuration, not repo-local `.mcp.json` unless explicitly requested.

The output directory may hold reports, ledgers, candidate audits, and temporary snapshots. It is not the final destination unless the install-scope contract selects it.

## Lightweight Lane

For edits confined to one existing skill's text or metadata — no new scripts, no new capability claims, no installation — the JSON ledgers are not required. Run `python3 "$PLUGIN_ROOT/scripts/skill/quick_validate.py" <skill-dir>` and record a one-line scope note in the final report. Any new script, new skill, new trigger surface, installation, or synthesis claim leaves the lightweight lane and requires the full gates.

## External-Broad Stop Condition

Continue search waves until diminishing returns are evident. A stop is justified when two consecutive waves add no new high-scoring mechanism, architecture pattern, safety control, validation method, or implementation technique that changes the distillation plan.

Each external-broad pass should cover at least three available source families:

- public repositories and source search;
- skill/plugin marketplaces and catalogs;
- docs, benchmarks, expert/community implementations, or adjacent framework ecosystems.

If network/search/source access prevents this, mark `external_discovery_partial` and avoid "broadly validated" language.

## Mechanism Scoring

Score mechanisms, not whole repositories:

| Field | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| capability_fit | off-target | adjacent | useful partial | directly covers target workflow |
| evidence_strength | unsupported | plausible | sourced | sourced and locally verified |
| maturity | sketch | prompt only | working pattern | tested script or proven workflow |
| safety_cost | none | manageable | significant | high or reject |
| dependency_cost | none | common local tool | added package/service | paid/key/complex stack |
| portability | project-only | narrow | adaptable | general |
| validation_leverage | none | checklist | command/probe | deterministic test/validator |

Mechanisms with `safety_cost=3` or `dependency_cost=3` require rejection, isolation, or explicit user-approved optional extension.

## Coverage And Loss Ledger

Every core workflow from the target contract needs a row:

| Target workflow | Must-keep capability | Best source mechanism | Source ref | Final location | Decision | Validation scenario | Capability loss/tradeoff | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Use the ledger to catch capability loss, over-preserved source bloat, duplicated variants, and local-optimum bias.

## Trigger Design Gate

Before finalizing a skill or plugin, check that trigger metadata answers:

- What task contexts should make an agent load this capability?
- What files, artifacts, source evidence, failures, or decisions are signals?
- What adjacent work should route elsewhere?
- Which exact user phrases matter only for target binding, install consent, permissions, or behavior-specific output?

Reject descriptions that only enumerate likely user requests. They under-trigger
when the agent should invoke the capability autonomously and overfit future
skills to one user's wording.

For material metadata changes, use this selection card:

- use when;
- inputs/signals;
- do not use when;
- failure symptoms;
- adjacent skills.

Keep information scent strong, local vocabulary concrete, and workflow steps out
of `description`. Add positive and near-miss negative trigger probes when
adjacent skills share vocabulary or the trigger surface is safety-sensitive.

## External Mechanism Applicability Gate

When external sources are part of synthesis, every adopted mechanism must map to at least one concrete artifact:

- hot-path rule;
- reference rule;
- deterministic script or validator;
- report/ledger field;
- safety gate;
- install or visibility proof.

If the mapping is only "better wording" or "interesting background", mark it `deferred` or `reference-only`. Keep the record/URL in reports instead of importing source prose into the final skill/plugin.

## Required Reports

- `discovery-report.md`: sources searched, candidates, provenance, skipped sources.
- `safety-vetting-report.md`: files reviewed, dependencies, observed behavior, risk classification, verdicts.
- `capability-matrix.md`: mechanism comparison and scores.
- `distillation-plan.md`: adopted/adapted/rejected/deferred components and final architecture.
- `install-scope.json`: validated target surface and final delivery/install state.
- `synthesis-changelog.md`: final decisions, validation commands, residual tradeoffs.

For plugin outputs, add plugin validation and install/visibility proof only when `install_required=true`.
