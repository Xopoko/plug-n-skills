---
name: capability-auditor
description: Audit agent skills/plugins for safety, evidence coverage, duplication, context cost, prompt contracts, dependencies, and install risk. Excludes code line/branch/mutation/test coverage; use portfolio architect for structural changes.
---

# Capability Auditor

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Use this for independent review before adopting, installing, publishing, or relying on a skill or plugin.

## Audit Spine

1. Identify the subject: skill folder, plugin folder, marketplace entry, synthesis package, or candidate source.
2. Inventory files and metadata.
3. Classify risks as `required`, `optional`, `example`, `advisory`, or `hidden`.
4. Measure context density when the subject affects hot context or repeated agent behavior.
5. If audit findings imply split, merge, delete, router, reference-extract, or script-extract decisions, hand off to `capability-portfolio-architect` before changing structure.
6. Validate structure and run deterministic self-tests.
7. For synthesized or installed outputs, validate install scope, source surface, install requirement, and whether any required activation proof exists.
8. Produce a verdict: eligible, eligible with adaptation, reference-only, reject, or needs user approval.

## Commands

Skill candidate audit:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/audit_skill_candidate.py" <skill-dir> --output candidate-audit.json
```

Context and prompt-contract audit:

```bash
python3 "$PLUGIN_ROOT/scripts/context/token_count.py" <paths> --json --top 20
python3 "$PLUGIN_ROOT/scripts/context/context_density_audit.py" <paths> --json --top 20
```

Structured quality review for Codex skills or plugins:

```bash
python3 "$PLUGIN_ROOT/scripts/context/token_count.py" <skill-or-plugin-dir> --json --top 20
python3 "$PLUGIN_ROOT/scripts/context/context_density_audit.py" <skill-or-plugin-dir> --json --top 20
```

For model-visible catalog pressure, read
`$PLUGIN_ROOT/references/skill-catalog-runtime-comparison.md` and use the target
host's vendor diagnostics. Route Codex-specific source modeling and exact
live-prompt or rollout budget evidence to the `codex-cli` skill in
`agent-harness`; keep this audit focused
on portable artifact quality and the resulting trigger repair.

Aggregate evidence coverage:

```bash
python3 "$PLUGIN_ROOT/scripts/audit/evidence_coverage_gate.py" \
  <evidence-coverage-ledger.json> --json
```

Skill validation:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/quick_validate.py" <skill-dir>
```

Plugin source plus install/cache validation:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/validate_plugin.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir> --check-only
```

Treat runtime discovery as a separate probe and report it as `not checked` when
the audit scope stops at source or installed cache state.

Install-scope validation:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" <output-dir>/install-scope.json --final
```

## Risk Review

Always check for:

- credential, token, cookie, SSH, cloud-config, Keychain, `.env`, or private-path access;
- network calls, telemetry, external services, paid APIs, API-key requirements, vendor lock-in;
- package installs, `curl | sh`, obfuscation, base64 payloads, `eval`, dynamic shell execution;
- broad deletes, writes outside the skill/plugin/workspace, hidden daemons, or install hooks;
- project-specific assumptions that would break general use.
- accidental global installation, cache refresh, or MCP config mutation when the request only needed source-repository work.
- brittle trigger design: descriptions or routing rules that depend on exact user phrasing instead of task context, source evidence, artifacts, failures, or agent decision points.
- weak trigger metadata: missing information scent, missing local vocabulary/synonyms, no near-miss negative boundary, generic `helper/tools/workflow` naming, or workflow summaries inside `description` that let the agent skip `SKILL.md`.
- runtime catalog pressure: discriminative trigger terms appear only in metadata tails that the target host can shorten, a host-wide inventory was mistaken for an isolated per-skill limit, disk/cache loading was confused with model visibility, or another runtime's budget policy was assumed without version-pinned evidence.
- tool-selection attack surface: untrusted imperative examples, hidden auto-invocation, broad "always use" phrasing, or metadata that bypasses consent, permissions, install scope, or destructive-action gates.

Advisory warnings are usually positive safety signals. Required or hidden risky behavior controls the verdict.

## Coverage Review

For synthesis outputs, create a workflow ledger:

- target workflow;
- must-keep capability;
- best source mechanism;
- final location;
- adopted, adapted, rejected, or deferred;
- validation scenario;
- capability loss or tradeoff;
- reason.

This catches over-preserved source bloat and under-synthesized capability loss.

For a claim over multiple skills, plugins, candidates, files, or other items,
read `$PLUGIN_ROOT/references/evidence-coverage-contract.md`. Freeze the
declared universe and cutoff, name the evidence dimensions, and validate the
exact item-by-dimension matrix. A complete inventory does not prove review
depth, and complete evidence for one dimension does not prove another.

Use `full_matrix` only when the item set and dimension set exactly match a
complete declared universe. Use `bounded_matrix` for honest subsets. If the
gate is unavailable, invalid, or unsupported, downgrade the claim to bounded
or partial instead of estimating completeness from counts or percentages.

The gate validates the supplied contract, not the truth of the universe,
evidence, reviewer independence, or review quality. Those remain separate
audit findings.

Do not use the gate for line, branch, mutation, or test coverage metrics, a
plain inventory without an aggregate completeness claim, or a single-artifact
review. Route those cases to the relevant domain tool or ordinary audit.

## Commitment Preservation Review

When auditing compression, synthesis, or report distillation, check that compact output still preserves:

- trigger semantics, exact trigger strings only when behavior depends on them, install scope, safety boundaries, required commands, and validators;
- trigger semantics broad enough for the host agent to invoke the skill without the user naming it directly;
- source provenance for adopted, adapted, rejected, and deferred mechanisms;
- recovery pointers for raw candidate evidence, logs, reports, or source packs;
- unresolved conflicts, high-risk findings, and capability gaps.

Flag summaries that reduce tokens by deleting evidence links, authority/provenance, or must-keep workflow coverage.

## External Mechanism Applicability Review

For external augmentations, require an adoption ledger:

- source mechanism and record/URL;
- target workflow or risk;
- final surface: hot-path rule, reference, validator/script, report field, safety gate, or install proof;
- decision: adopted, adapted, rejected, deferred, or reference-only;
- validation scenario and residual tradeoff.

Reject or defer external content that only improves prose and does not change a concrete workflow, validation gate, or safety control.

For trigger metadata changes, map the adopted mechanism to one of:

- information scent or local vocabulary rule;
- selection card field;
- positive/near-miss-negative trigger probe;
- adjacency/router boundary;
- safety rule for tool or skill selection;
- validator/audit signal.

For structured quality-review findings, read the JSON fields directly. Use
token hotspots, measured risk entries, duplication clusters, research-gate
summaries, blocking flags, and validator results as evidence, then verify any
adopted change with Workbench validators.

## Report

Use concise sections:

```markdown
Capability audit:
- Subject:
- Files reviewed:
- Capability coverage:
- Unique useful mechanisms:
- Commitment preservation:
- External mechanism applicability:
- Dependencies/runtime:
- Safety risks:
- Context-density findings:
- Quality-review findings:
- Validation:
- Install scope:
- Verdict:
- Required fixes or rejected components:
```
