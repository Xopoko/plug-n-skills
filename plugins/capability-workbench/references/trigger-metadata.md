# Trigger Metadata Reference

Use this after `skill-trigger-metadata` is selected and detailed naming or description repair is needed.

## Name Design

Use names that are portable and searchable:

- lowercase letters, digits, and hyphens only;
- 1-64 characters;
- match the skill directory;
- include the subject area and action or input type;
- avoid vague catch-alls such as `helper`, `tools`, `workflow`, `assistant`, or `manager`;
- avoid clever brand names unless the brand is the user-facing trigger.

Treat an existing name as a public identifier. Rename only when the routing gain
justifies a migration across folder names, plugin references, documentation,
tests, deeplinks, and installed copies; description repair is the default.

Prefer names like `skill-trigger-metadata`, `reviewing-api-design`, or `processing-pdfs` over abstract nouns like `optimization`, `quality`, or `documents`.

## Description Inputs

Include enough concrete terms for matching:

- user intent: create, edit, audit, debug, migrate, publish;
- artifacts: `SKILL.md`, frontmatter, plugin manifest, `.xlsx`, OpenAPI, screenshots;
- symptoms: under-triggering, over-triggering, skipped steps, flaky tests, stale cache;
- source evidence: file paths, error classes, command names, framework names;
- synonyms and adjacent phrasing users may choose;
- bounded "even if..." clauses for important implicit cases;
- negative boundaries when nearby skills share vocabulary.

Avoid:

- first person: "I can help...";
- vague utility language: "helps with files", "does analysis";
- process summaries: "reads X, then runs Y, then reports Z";
- unsupported promises: "always", "guarantees", "perfectly";
- private examples, local machine paths, credentials, or private names.

## Runtime Catalog Pressure

Agent hosts do not share one skill-catalog policy. Read
`skill-catalog-runtime-comparison.md` before applying a numeric budget or an
overflow assumption. Some hosts hard-omit entries, some simplify descriptions
without enforcing a final cap, and some have no dedicated aggregate budget.

Design for prefix survival:

1. Put the domain, artifact, failure, or decision that distinguishes the skill
   first, followed immediately by the action the skill owns.
2. Remove generic lead-ins such as `Use when`, `Use for`, `Use this skill`,
   `Help with`, or `Agent skills for` when the concrete trigger can lead.
3. Put secondary synonyms and adjacent boundaries after the discriminative
   trigger terms.
4. Keep procedure out of metadata even when shortening the description.
5. Do not treat the 1,024-character per-description ceiling as a safe target;
   aggregate pressure can leave only a short prefix or omit the whole entry.
6. Do not claim visibility from an isolated skill audit. Include the broadest
   concrete enabled inventory and the target model window.

Use the first 40 characters as a repository review probe: they should normally
contain a concrete domain/artifact/failure cue plus an owned action. Forty is
not a Codex runtime guarantee; the surviving prefix is inventory- and
budget-dependent, and an entire entry can still be omitted.

Use this description shape when prefix survival matters:

```yaml
description: <Domain, artifact, or failure>: <owned action or decision>. <Secondary synonyms and bounded adjacent cases>.
```

After material metadata or portfolio changes, bind the target runtime, exact
version, enabled inventory, and model context before claiming visibility.
Interpret full metadata, shortened metadata, identity-only entries,
whole-entry omission, and empty output as distinct inventory-level states.
Route exact Codex budget and current-session diagnosis to `codex-cli`; return
here to repair the trigger prefix, vocabulary, or adjacent-skill boundary.

Audit a source inventory with:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/audit_description_prefixes.py" <roots> --json
```

The default 40-character and 240-character findings are portable review probes,
not claims about a host's runtime limits. Use `--strict` only when the portfolio
has adopted them as explicit release gates.

## Failure Repair

If the skill does not trigger:

1. Add missing concrete intent, artifacts, file types, error text, or domain synonyms.
2. Replace abstract words with the words users and source files actually contain.
3. Add a bounded "even if..." clause for important implicit cases.

If the skill triggers too often:

1. Add scope qualifiers or negative boundaries.
2. Remove generic nouns that match many workflows.
3. Consider a narrower skill name or split the skill.

If the skill triggers but the agent skips required steps:

1. Remove workflow steps from `description`.
2. Move critical constraints to the top of `SKILL.md`.
3. Shorten verbose body text that hides the required action.
