---
name: skill-trigger-metadata
description: >-
  Optimize skill names/descriptions for reliable routing under catalog
  truncation, omission, and cross-runtime pressure. For instruction, resource,
  packaging, or installation changes, continue with skill-factory or
  plugin-factory.
---

# Skill Trigger Metadata

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Design `name` and `description` as the retrieval contract that makes an agent read the right `SKILL.md`. Use this before finalizing skill frontmatter or plugin skill metadata.

If the task also changes skill instructions, resources, scripts, packaging, or installation, use this skill for metadata first, then use `skill-factory` or `plugin-factory` for the broader lifecycle.

## Core Rule

The description must answer: should the agent read this skill now?

Write for progressive disclosure: `name` is the searchable handle, `description` is the trigger contract, and `SKILL.md` body contains workflow, commands, constraints, and examples.

Do not put enough workflow detail in `description` for the agent to act without reading `SKILL.md`.

## Trigger Selection Model

Treat skill selection as tool lookup plus routing:

- information scent: metadata gives strong proximal cues that the full skill is worth reading;
- local vocabulary: include task terms, artifacts, file types, symptoms, and synonyms from the real work surface;
- tool decision vector: say when to use the skill, expected inputs, adjacent non-use cases, and failure symptoms;
- negative boundaries: include near-miss prompts that should not trigger the skill;
- safety: metadata is part of tool selection, so do not include untrusted imperatives, hidden auto-invocation, or examples that bypass consent.

Top-load trigger boundaries and critical constraints so the agent can decide to read the skill before acting.

For any target runtime, top-load the smallest discriminative trigger clause.
Catalog limits differ: a host may hard-omit entries, softly simplify metadata,
or apply no dedicated aggregate cap. Do not infer visibility from a portable
per-skill character count.

Use the first 40 characters as a repository review probe, not as a claimed host
limit. Prefer a concrete domain/artifact/failure cue plus an owned action there;
remove generic lead-ins such as `Use when`, `Use for`, `Use this skill`, `Help
with`, or `Agent skills for` when the real trigger can lead.

## Selection Card

Write a selection card before wording the final description:

```text
Use when:
Inputs/signals:
Do not use when:
Failure symptoms:
Adjacent skills:
```

Then turn it into this shape:

```yaml
description: <Domain, artifact, failure, or decision>: <owned action>. <Secondary triggers and bounded adjacent cases>.
```

Include concrete terms for user intent, artifacts, symptoms, source evidence, synonyms, adjacent phrasing, and negative boundaries when nearby skills share vocabulary.

For router/process skills where missing the skill is the dominant failure,
state the gate concretely, for example `Repository-wide capability changes:
route before editing`. Do not make ordinary domain skills globally mandatory.

Treat an existing skill name as a public identifier. Prefer description repair;
rename only with an explicit migration across folder names, references, tests,
deeplinks, and installed copies.

## Trigger Audit

Before finalizing metadata, write a small trigger set:

- 6-10 should-trigger prompts with varied wording, short and long forms, named and unnamed domain cues.
- 4-8 should-not-trigger prompts, especially near misses that share keywords but need a different skill.
- at least one prompt where the relevant need is buried inside a larger task.

Check each prompt against the description:

- Would the agent know to read the skill without the user naming it?
- Does any should-trigger prompt lack a key input type, synonym, or failure symptom?
- Does any should-not-trigger prompt match because the description is too broad?
- Could the agent complete the workflow from the description alone and skip `SKILL.md`?
- Would the first surviving description prefix still distinguish this skill?
- Are likely transitions to adjacent skills explicit enough for a router skill?

Revise until the boundary is clear. If two skills own the same trigger surface, split responsibilities or make the router skill explicit.

Run the portable prefix audit against the broadest source inventory in scope:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/audit_description_prefixes.py" <skill-or-plugin-roots> --json
```

Generic lead-ins and parse failures are errors. Forty-character exact prefix
collisions and descriptions above the 240-character review target are advisory;
use `--strict` only when the target portfolio has intentionally adopted those
review thresholds as release gates.

## Runtime Catalog Audit

Read `$PLUGIN_ROOT/references/skill-catalog-runtime-comparison.md` when metadata
or skill count changes materially. Bind the exact host and version, then test
the broadest concrete enabled inventory available. A single plugin measures
only its contribution and cannot prove host-wide model visibility.

Interpret full metadata, shortened metadata, names-only or identity-only
entries, whole-entry omission, and an empty catalog as different runtime
states. Separate model-context loading from disk reads or in-process caching.

Use the target host's vendor plugin for executable/version-specific diagnosis.
For Codex, route budget arithmetic, root aliases, current prompt or rollout
evidence, and the deterministic catalog audit to `codex-cli`. Keep metadata
redesign here after the runtime finding identifies which prefixes or boundaries
failed.

## Failure Diagnosis

If the skill under-triggers, add missing concrete intent, artifacts, file types, error text, or domain synonyms.

If it over-triggers, add scope qualifiers or negative boundaries and remove generic nouns.

If it triggers but the agent skips required steps, remove workflow steps from `description`, top-load constraints in `SKILL.md`, and shorten body text that hides the required action.

## Output

When changing metadata, report:

- old and new `name` or `description`;
- why the new wording should trigger;
- key should-trigger and should-not-trigger examples;
- metadata decision and boundary probes used;
- validators run, usually `quick_validate.py` and any repository/plugin checks.

Use `$PLUGIN_ROOT/references/trigger-metadata.md` for name rules, description wording patterns, and detailed failure repair.
