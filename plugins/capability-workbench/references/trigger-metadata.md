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

## Codex Catalog Budget Pressure

Codex does not reserve a fixed character quota for each skill. Its initial
`name + description + path` catalog shares a host-wide budget: at most 2% of a
known model context window, or an 8,000-character fallback when the window is
unknown. Current core token-mode accounting estimates `ceil(UTF-8 bytes / 4)`.

Design for prefix survival:

1. Put the domain, task, artifact, or failure that distinguishes the skill in
   the first clause.
2. Put secondary synonyms and adjacent boundaries after the discriminative
   trigger terms.
3. Keep procedure out of metadata even when shortening the description.
4. Do not treat the 1,024-character per-description ceiling as a safe target;
   aggregate pressure can leave only a short prefix or omit the whole entry.
5. Do not claim visibility from an isolated skill audit. Include the broadest
   concrete enabled inventory and the target model window.

Use this description shape when Codex is a target host:

```yaml
description: Use when <specific task, artifact, or failure>. <Secondary synonyms and bounded adjacent cases>.
```

Audit the catalog after material metadata or portfolio changes:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/codex_skill_catalog_audit.py" \
  <skill-roots-or-plugin-roots> --context-window <tokens> --json
```

Interpret `full_metadata_visible`, `descriptions_shortened`, and
`skills_omitted` as inventory-level states. The audit uses a conservative
absolute-path model; actual Codex path aliases may preserve more metadata.
Rare manual skills can use `agents/openai.yaml` with
`policy.allow_implicit_invocation: false` to leave the implicit catalog while
remaining explicitly invocable.

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
