---
name: context-density
description: >-
  Use when designing, auditing, refactoring, measuring, or validating
  token-efficient context and prompt/output contracts. Trigger for AGENTS.md,
  prompts, skill packages, marketplace plugins, MCP/tool schemas,
  long-context placement, prompt/context compression, retrieval provenance,
  runtime context diagnostics, duplicated hot-path prose,
  brittle trigger descriptions, strict JSON/schema/tool-call output, validators,
  retry/repair loops, or behavior-preserving token reduction.
---

# Context Density

Optimize capability density through measured context, explicit contracts, and token-aware design.

## Hard Rules

- Preserve triggers, routing, safety, commands, output contracts, and validation proof before compressing wording.
- Preserve trigger semantics, not just trigger phrases.
- Descriptions should fire from task context, artifacts, source evidence, failures, and agent decision points; keep exact user wording only when it controls behavior, consent, or target binding.
- Compress prose, not commitments: goals, constraints, decisions, IDs, paths, dates, warnings, evidence refs, safety boundaries, and behavior-critical exact wording need verbatim text or typed recovery pointers.
- Treat raw logs, transcripts, reports, and source packs as evidence archives. Do not hot-load them; keep compact claims plus source refs.
- Do not let retrieval, memory recall, or archived artifacts become authoritative state without provenance, confidence, and validation.
- Do not bury action-critical commitments in the middle of large hot/router files; keep anchors, source order, or explicit state pointers.
- Do not call a compression change successful from input-token reduction alone; include output cost/length, task success, preserved atoms, and validation proof when available.
- Apply research-backed gates for material changes: long-context placement stress, compression break-even, schema plus task validation, retrieval/citation promotion, and cache-prefix economics.
- If a skill/plugin portfolio needs split, merge, delete, move, router, cross-plugin overlap review, reference extraction, shared-capability extraction, or script extraction, treat token pressure as a signal.
- Route structural work to Capability Workbench portfolio architecture when available.
- Do not treat context-window size as proof of reliable recall, relevance, or reasoning; state validation scope and residual risk.
- Do not summarize high-authority instructions, unresolved conflicts, or prompt-injection boundaries into vague prose.
- Merge overlapping prose instead of appending a second version.
- Keep exact commands only when operationally necessary.
- Treat generated natural language as human-facing content, not a machine interface.
- Machine decisions must come from strict JSON/schema, tool arguments/results, typed protocols, validators, or closed keys.
- Invalid structured output must reject, retry, repair under the same schema, fallback, or fail loudly.
- Do not add regex/substring patches over generated explanations to recover status, IDs, categories, scores, dates, or actions.
- Do not run host-agent config changes unless the user requested a config-changing action.

## Operating Model

Every audit or refactor follows the same spine:

1. Identify the consumer and load path.
2. Measure token/context cost when the surface is hot, large, or disputed.
3. Detect duplication, drift, low-value context, brittle prose parsing, and buried commitments.
4. Preserve behavioral invariants before editing.
5. Refactor toward one compact source of truth plus conditional detail.
6. Keep high-authority commitments easy to recover; do not rely on long-window capacity alone.
7. Move machine-consumed LLM values into explicit contracts.
8. Validate commitment preservation before replacing raw context: critical facts, exact instructions, evidence pointers, and recovery paths must survive.
9. Separate artifact recall from state commitment: retrieved or archived material stays evidence until a typed, validated claim promotes it into current state.
10. Validate compression economics with total cost and behavior, not input-token reduction alone.
11. Apply the relevant research-backed acceptance gates before claiming success.
12. Validate with token measurement, schema checks, contract scans, and skill/plugin validators.
13. Report adopted changes, rejected changes, token delta, risks, and tradeoffs.

Load paths:

| Path | Meaning | Default treatment |
| --- | --- | --- |
| Hot | Startup files, skill frontmatter/body, prompt templates, root agent rules | Directive, compact, measured |
| Router | Indexes, maps, READMEs, source-of-truth lists | Short pointers and ownership |
| Reference | Variant details, examples, recovery notes | Open only when needed |
| Evidence | Logs, raw API payloads, source packs, changelogs | Link or archive, do not hot-load |

## Choose The Module

| Need | Read |
| --- | --- |
| Shared terminology, workflow, source-of-truth layout | `references/operating-model.md` |
| Startup/context/token diagnostics and host-runtime measurement choices | `references/token-diagnostics.md` |
| SKILL.md or plugin skill package footprint reduction | `references/skill-refactor.md` |
| Skill/plugin portfolio split, merge, delete, move, router, cross-plugin overlap, or script-extract decisions | Capability Workbench `capability-portfolio-architect` when available |
| Prompt, model-output, tool-call, schema, retry, or prose-parsing review | `references/prompt-contracts.md` |
| Long-context placement, prompt compression, schema/task validity, retrieval citation, or cache-prefix acceptance gates | `references/research-backed-gates.md` |
| Final audit sections and JSON/Markdown report contracts | `references/report-contracts.md` |

Keep `SKILL.md` lean. Move rare detail to references only when it prevents repeated hot-path loading.

## Commands

Run from this skill directory or pass absolute paths:

```bash
python3 scripts/token_count.py <files-or-dirs> --json --top 20
python3 scripts/context_density_audit.py <files-or-dirs> --json --top 20
```

Use the bundled runtime reporter when the question is about local Codex or
Claude Code startup context, installed skills, MCP config, plugin manifests,
ranked raw context sources, exportable reports, or latest session token usage:

```bash
python3 scripts/codex_context_report.py agents --json
python3 scripts/codex_context_report.py brief --agent codex --project . --usage --json
python3 scripts/codex_context_report.py skills --agent codex --limit 10 --ndjson
python3 scripts/codex_context_report.py skill context-density --agent codex --json
python3 scripts/codex_context_report.py mcp --agent codex --no-introspect-mcp --json
python3 scripts/codex_context_report.py mcp --agent codex --tools SERVER --json
python3 scripts/codex_context_report.py sources --agent codex --ndjson --limit 20
python3 scripts/codex_context_report.py export markdown --agent codex --project .
```

The reporter is read-only and exposes a CLI-compatible reporting surface for
local file diagnostics. It estimates context from files on disk and does not
introspect live MCP tool schemas or mutate host-agent config.

## Output

For material work, include:

```markdown
Context density audit:
- Consumer/load path:
- Token measurement:
- Commitment preservation: critical atoms, verbatim strings, evidence refs, recovery pointers.
- Relevance/placement: what stayed hot, what moved to references, and any middle-buried commitments handled.
- Compression economics: input/output token effect, total cost, task validation, or why unavailable.
- Evidence boundary: artifact recall versus committed state.
- Existing context refactor:
- Preserved invariants:
- Contract discipline:
- Validation:
- Adopted/rejected changes:
- Remaining tradeoffs:
```

If the task touches LLM/model-output handling, also include the prompt-contract audit from `references/report-contracts.md`.
