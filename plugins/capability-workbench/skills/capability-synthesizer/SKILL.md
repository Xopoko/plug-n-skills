---
name: capability-synthesizer
description: Use when performing broad external-first discovery, vetting, scoring, distillation, or synthesis of agent skills or plugin packs from the public web, GitHub/public repositories, OpenClaw/ClawHub, marketplaces, research sources, community implementations, user references, or local skills. Use for well-vetted capability synthesis, cross-skill comparison, plugin-pack synthesis, global capability acquisition, skill strengthening, and adoption/rejection changelogs.
---

# Capability Synthesizer

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Build one cohesive result from a broad capability corpus. The internet and public repositories are the primary corpus; local skills are supplementary evidence and candidate implementations. Candidates are evidence, not merge targets.

## Target Contract

Before discovery, write a compact contract:

```json
{
  "capability": "short target",
  "primary_target": "named skill/plugin/MCP/capability to create or strengthen",
  "named_targets": ["@plugin-or-$skill explicitly named by the user"],
  "cwd_role": "workspace | source-reference | target",
  "mode": "new-skill | augment-existing | plugin-pack | source-import | reference-only",
  "artifact_type": "skill | plugin | mcp | mixed | report",
  "install_scope": "global-agent | repo-local | workspace-snapshot | reference-only",
  "install_required": false,
  "destination_path": "chosen source or install path",
  "marketplace_path": "only when global marketplace activation is required",
  "trigger_model": ["task context, artifacts, evidence, or agent decision point that should invoke the capability"],
  "core_workflows": ["workflow 1"],
  "non_goals": ["excluded behavior"],
  "must_keep_capabilities": ["capability that must survive distillation"],
  "safety_boundaries": ["no candidate execution", "no hidden network", "no credentials"],
  "validation_scenarios": [
    {"name": "happy path", "expected": "observable pass"},
    {"name": "safety case", "expected": "blocked or approval-gated"},
    {"name": "edge case", "expected": "covered or explicitly deferred"}
  ]
}
```

Use `$PLUGIN_ROOT/references/synthesis-contract.md` for the scoring rubric and coverage ledger. Use `$PLUGIN_ROOT/references/external-discovery.md` for broad public-source search waves and diminishing-return criteria.
Use `$PLUGIN_ROOT/references/install-scope.md` to choose the source/edit surface and whether installation is required.

For target binding, a named skill/plugin is the primary target by default. A current plugin/skill source repository may be the edit target when the request, repo instructions, or workspace profile indicate that capability artifacts should be authored there.

## Hard Gate

For `new-skill`, `augment-existing`, and `plugin-pack` synthesis, create installation-scope and external-discovery ledgers before editing the target skill/plugin:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" --template > <output-dir>/install-scope.json
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" <output-dir>/install-scope.json
```

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/external_discovery_gate.py" --template > <output-dir>/external-discovery-ledger.json
python3 "$PLUGIN_ROOT/scripts/synthesis/external_discovery_gate.py" <output-dir>/external-discovery-ledger.json
```

Do not call the result complete unless the gate validates `status=complete`, `breadth=external-broad`, and `stop_condition=diminishing_returns`. If the gate is partial or skipped, the final answer and reports must say `external_discovery_partial` or `local_only`, and must not claim broad validation.

Do not call an output complete until `install-scope.json` validates the selected delivery surface and `install_scope_gate.py --final` passes. Use `repo-local` for source artifacts in a selected repository and `install_required=false` unless the user asked for activation. Use `global-agent` when the requested result is an installed personal/global capability or no repository source surface is selected; detect the active agent (Codex, Claude, or Cursor) with `$PLUGIN_ROOT/scripts/agent_target.py`.

Official docs lookup, Context7 docs, or one search query is not enough. It can be one source family, but ready-made public skills/plugins/MCP servers/community implementations still need discovery unless blocked.

## Discovery

Choose discovery breadth explicitly from `$PLUGIN_ROOT/references/synthesis-contract.md`. For `new-skill`, `augment-existing`, `plugin-pack`, "well-vetted", "synthesize", "distill", "strengthen", or marketplace capability requests, default to `external-broad`.

Use `$PLUGIN_ROOT/references/external-discovery.md` for source families, search waves, query patterns, triage, and diminishing-return rules. The hot path is:

1. Search public web/repositories, skill/plugin marketplaces, implementation ecosystems, research/expert sources when relevant, user-provided sources, then local skills as supplementary evidence.
2. Record source families, skipped sources, recurring mechanisms, best-supported readable candidates, and stop condition in the external-discovery ledger.
3. Search local skills only as regression baselines or implementation candidates:
   ```bash
   python3 "$PLUGIN_ROOT/scripts/capability_inventory.py" --query "<topic>" --json
   ```
4. Mark `external_discovery_partial` when time, network, access, or safety blocks the required breadth.

Do not treat a strong local candidate set as enough to skip external discovery for synthesis/augmentation. Local candidates can win after scoring, but they do not define the search frontier.

For ClawHub/OpenClaw CLI use, disable telemetry when possible:

```bash
CLAWHUB_DISABLE_TELEMETRY=1 clawhub search "<topic>"
CLAWHUB_DISABLE_TELEMETRY=1 clawhub inspect <slug>
```

Skip sources that require login, paid access, opaque install, API keys, or telemetry just to inspect. Record the limitation and search for an inspectable alternative.

## Candidate Evaluation

Run the static helper for readable local candidates:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/audit_skill_candidate.py" <candidate-a> <candidate-b> --output candidate-audits.json
```

Then manually review the files that matter. For each candidate, record:

- core capability covered;
- autonomous trigger model: task contexts, files, evidence, or agent decisions that should invoke the capability;
- unique techniques;
- useful prompts or instructions;
- reusable scripts or utilities;
- processing pipeline;
- architecture pattern;
- quality-improvement mechanisms;
- dependencies and runtime requirements;
- security risks;
- external services, paid APIs, API-key requirements, telemetry, network calls, or vendor lock-in;
- project-specific assumptions that should not generalize.

Score mechanisms, not whole candidates. Prefer best-supported mechanisms after safety, dependency, portability, and validation costs are accounted for. Reject any required or hidden high-risk mechanism even if the rest of the candidate is strong.

## Distillation Rules

- Prefer the simplest self-contained mechanism that works offline.
- Prefer deterministic scripts over repeated fragile reasoning.
- Prefer typed contracts, validators, dry-run flows, and explicit outputs over prose parsing.
- Distill by preserving commitments, not by retaining prose: every must-keep workflow, exact trigger, safety boundary, install-scope decision, provenance source, and validation proof must map to a final artifact or an explicit deferral.
- Write skill/plugin descriptions for situation-triggered use: task context, artifacts, source evidence, and agent decision points. Do not synthesize trigger metadata as a list of literal user request phrasings. Preserve exact user wording only where it controls target binding, install consent, permissions, or behavior-specific output.
- For skill or plugin metadata, use the selection-card model: use-when, inputs/signals, do-not-use boundaries, failure symptoms, and adjacent skills. Preserve information scent and local vocabulary without leaking workflow steps into `description`.
- Apply the external mechanism applicability gate: an external idea is adopted only if it maps to a target workflow, skill hot path, reference, script/validator, report field, safety gate, or install proof. Otherwise keep it in reports as rejected, deferred, or reference-only.
- Put the final artifact on the selected delivery surface. For repository work, that means the plugin or skill source tree in the repository. For installed personal/global work, that means the agent's skills dir or marketplace source plus activation proof.
- Preserve source provenance in reports, not as copied bloat in the final skill.
- When several candidates solve the same problem, synthesize one practical version.
- Drop redundant variants, project-specific assumptions, telemetry, paid/keyed services, and optional integrations that do not improve the core capability.
- Do not optimize for local improvement when the external corpus exposes a better-supported architecture. Adapt the best-supported practical mechanism to the local skill/plugin shape.

## Output Package

If no output directory is provided, write reports and ledgers to `./skill-synthesis/<target-slug>/` in the current workspace. This is a report/work area, not the default installation target. Produce:

- `discovery-report.md`
- `safety-vetting-report.md`
- `capability-matrix.md`
- `distillation-plan.md`
- `install-scope.json`
- final skill/plugin/MCP capability path on the selected delivery surface, plus installed/cached proof only when `install_required=true`
- `synthesis-changelog.md`

Use `$PLUGIN_ROOT/references/synthesis-contract.md` and `$PLUGIN_ROOT/references/safety-vetting.md` for required sections.

## Convergence Gate

Before finalizing:

1. Map every target workflow to a final skill section, reference, script, or plugin skill.
2. Confirm each final skill/plugin description has a broad task/evidence trigger model, not only examples of user wording.
3. Confirm trigger metadata has positive and near-miss negative boundaries when adjacent skills share vocabulary.
4. List the best source mechanism per workflow and confirm it survived distillation or was intentionally dropped.
5. Check recovery: each adopted/rejected/deferred claim has a source ref, file path, URL, or ledger pointer.
6. Confirm external mechanisms have an applicability mapping or are explicitly deferred.
7. Search final artifacts for TODOs, duplicated logic, unsafe examples, and stale mode statements.
8. Confirm external discovery reached diminishing returns or mark the output partial.
9. Confirm the final artifact is delivered to the validated surface and installed only when `install_required=true`.
10. Run `python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" <output-dir>/install-scope.json --final`.
11. Run skill validators and resource tests.
12. For plugin-pack mode, run plugin manifest validation and install/visibility checks with `plugin-factory`.
