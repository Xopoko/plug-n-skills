---
name: capability-auditor
description: Audit agent skills and plugins for safety, capability coverage, duplicated logic, token/context cost, prompt-contract risk, validation readiness, marketplace visibility, dependencies, network behavior, and install/update risks. For structural split/merge/move/delete/router decisions across skills or plugins, use capability-portfolio-architect instead.
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

Skill validation:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/quick_validate.py" <skill-dir>
```

Plugin validation and visibility:

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/validate_plugin.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/plugin/ensure_local_plugin_installed.py" <plugin-dir> --check-only
```

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
- Validation:
- Install scope:
- Verdict:
- Required fixes or rejected components:
```
