# Skill Refactor

Refactor skill packages for lower hot-path token cost without losing behavior.

This reference optimizes context placement inside an existing skill shape. When the right answer may be to split, merge, delete, move skills across plugins, add a router, extract shared mechanics, move logic into scripts, or redesign plugin boundaries, use Capability Workbench portfolio architecture instead of treating token reduction as the final objective.

## Workflow

1. Locate the authoritative skill path: repo-local, the agent's skills home (`~/.codex/skills`, `~/.claude/skills`), system skill, or plugin cache.
2. Measure `SKILL.md` before editing.
3. Read `SKILL.md`, `agents/openai.yaml` if present, and the top resource map.
4. Preserve triggers, defaults, commands, safety, output contract, validation, and non-obvious local invariants.
5. Identify high-authority commitments that are buried in long middle sections.
6. If the audit finds overlapping skills, cross-plugin responsibility overlap, overloaded responsibilities, missing routers, obsolete skills, or repeated deterministic procedures in prose, stop and run a portfolio-architecture decision pass.
7. For behavior-preserving compression, write critical atoms into a commitment ledger before editing.
8. Edit `SKILL.md` first; create references only for conditionally loaded detail.
9. Re-measure, validate frontmatter, and check preserved phrases or the commitment ledger.

## Cut

- narrative history, task diaries, changelogs, and repeated "why this changed" prose;
- repeated setup/troubleshooting text across sections;
- examples that restate a rule;
- long taxonomies when a slug, table, or reference link is enough;
- command blocks that differ only by variable values;
- obvious LLM common sense or motivational text;
- fallback detail in the hot path when it applies only after opt-in.
- long middle sections that mix safety, routing, examples, and history without anchors.

## Keep

- trigger semantics agents can detect from task context, artifacts, source evidence, failures, or decisions;
- exact trigger words only when behavior depends on them;
- hard routing decisions and permission boundaries;
- exact commands needed to measure, run, validate, publish, or recover;
- anchors for high-authority rules, safety boundaries, and recovery pointers;
- non-obvious versions, paths, flags, tool caveats, and auth boundaries;
- one small example when it prevents a likely mistake;
- proof requirements and final output expectations.

## Validation

```bash
python3 scripts/token_count.py <skill-dir>/SKILL.md --json
python3 scripts/context_density_audit.py <skill-dir> --commitment-ledger atoms.json --fail-on-missing-commitments
rg -n --fixed-strings '<critical preserved phrase>' <skill-dir>/SKILL.md
```

When the host agent ships a skill validator, run it too (for example
`${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py <skill-dir>`
on Codex). For plugin skills, also run plugin validation from the plugin root.

## Audit

Report path, before/after tokens, reduction, preserved invariants, moved/deleted material, verification commands, and any deferred duplication.

Also report placement changes when behavior depends on long-context recall: what remained hot, what moved behind a router, what gained an explicit state pointer, and what residual recall risk remains.
