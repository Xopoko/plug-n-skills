# Context Density

Use this reference when a skill, plugin, prompt, report, or agent memory surface affects repeated context loading.

## Load Paths

| Path | Meaning | Treatment |
| --- | --- | --- |
| Hot | `SKILL.md`, `AGENTS.md`, prompts, frontmatter, startup docs | Compact, directive, measured |
| Router | indexes, README, capability maps | Pointers and ownership |
| Reference | detailed variants, examples, specs | Open only when needed |
| Evidence | logs, raw payloads, reports, source packs | Link or archive, do not hot-load |

## Refactor Rules

- Preserve trigger precision, safety, validation commands, output contracts, and source-of-truth paths.
- Preserve capability commitments before reducing tokens: trigger semantics, exact trigger strings only when behavior depends on them, user-facing promises, safety boundaries, required commands, install scope, validation proof, provenance, and recovery pointers.
- Treat skill/plugin descriptions as routing contracts. They should trigger from task context, artifacts, source evidence, failures, or agent decisions, not only from literal user request phrasing.
- Preserve information scent, local vocabulary, negative boundaries, and adjacent-skill routing when compressing metadata. Do not save tokens by deleting the terms that make the skill retrievable.
- Keep workflow steps out of `description`; put procedure in the body or references so metadata triggers reading instead of replacing it.
- When token work exposes overlapping skills, cross-plugin responsibility overlap, overloaded boundaries, missing routers, obsolete skills, or repeated deterministic procedures in prose, use `capability-portfolio-architect` before editing. Context density is a signal; portfolio architecture decides keep, split, merge, delete, move, route, reference-extract, shared-capability, or script-extract actions.
- Keep candidate artifacts and recalled evidence separate from committed capability state until a validated decision row adopts, adapts, rejects, or defers them.
- Remove duplicated prose, stale history, task diaries, and examples that restate rules.
- Move rare details into directly linked references.
- Prefer strict JSON/schema/tool outputs over parsing generated prose.
- Do not add regex or substring patches over model explanations to recover machine state.
- Do not replace candidate evidence, audit findings, install decisions, or safety concerns with unattributed summaries; keep compact conclusions plus source refs.

## Compression Gate

Before compacting a skill/plugin or synthesis report, confirm:

- every must-keep capability maps to a final section, script, validator, or explicit deferral;
- high-authority instructions and install-scope rules are not paraphrased into ambiguity;
- evidence-heavy material is archived or linked, not hot-loaded;
- raw candidate notes can be recovered from ledgers, URLs, or file paths;
- the final artifact is shorter after including necessary metadata.
- efficiency claims include output-token/total-cost effects or explicitly say they were not measured.

## External Mechanism Applicability Gate

Adopt external mechanisms only when they map to at least one concrete target surface:

- skill hot-path rule;
- reference rule;
- validator/script;
- report field or ledger field;
- safety gate;
- install/visibility proof.

Otherwise record the mechanism as `deferred` or `reference-only`; do not import it as prose.

## Commands

```bash
python3 ../../scripts/context/token_count.py <files-or-dirs> --json --top 20
python3 ../../scripts/context/context_density_audit.py <files-or-dirs> --json --top 20
```

Report token totals, major hotspots, preserved invariants, commitment preservation, recall/state boundary, compression economics, changes made, validation, and remaining tradeoffs.
