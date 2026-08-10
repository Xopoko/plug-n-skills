# Codex Skill Metadata Catalog Budget

Use this reference when a Codex task reports shortened skill descriptions,
omits skills from the model-visible catalog, or appears to disagree with the
installed skill/plugin inventory.

## Bind The Question First

These are different evidence requests:

- **Existing task:** what that task's model actually received.
- **Fresh render:** what one exact Codex executable, cwd, model, config, and
  current plugin state would render now.
- **Inventory:** what source, marketplace, cache, or discovery roots contain.
- **Mechanism:** why a matching Codex renderer allocated the catalog that way.

Do not use a fresh render as a replay of an old task. Do not use an installed
inventory count as proof of model visibility. A running task can retain an old
catalog and versioned locators after source or cache state changes.

## Current Pinned Mechanism

The implementation statements below are pinned to OpenAI Codex commit
`95c7265e849e6e360a7fa53ffeac70b25d6051a3`.

The model-visible entry is:

```text
- <name>: <description> (<locator-kind>: <locator>)
```

or, without a description:

```text
- <name>: (<locator-kind>: <locator>)
```

Host locators use `file`; executor, orchestrator, and custom skills use their
own resource labels. Host paths can be replaced with `r0`, `r1`, and later root
aliases plus a `### Skill roots` table.

The budget is:

```text
max(floor(resolved_context_window * 2 / 100), 1)
```

If the context window is missing, non-positive, or cannot be converted, Codex
uses an 8,000-Unicode-character fallback. Token mode is not a model tokenizer:
it estimates `ceil(UTF-8 bytes / 4)`.

Budget scope matters:

- included: rendered skill metadata lines and any root-alias-table overhead
  selected by the renderer;
- excluded: the surrounding headings, usage instructions, and the selected
  `SKILL.md` body loaded later;
- each catalog description is normalized by the loader and capped at 1,024
  characters before aggregate allocation;
- plugin namespace prefixes and locator text consume the budget too.

Allocation stages:

1. Keep all full metadata when it fits. Equality fits; `full_cost == budget`
   is not shortening.
2. If all minimum name-and-locator lines fit, distribute the remaining
   description characters round-robin so every entry keeps a prefix.
3. If the minimum lines do not fit, remove descriptions and include complete
   entries in catalog order when each one fits. A shorter later entry can still
   fit after a longer earlier one is omitted.
4. Extension catalogs can reserve an omission marker and remove additional
   already-included entries until the complete marker fits.
5. Overflow produces a warning/report rather than a catalog-rendering error.

For host skills, hard-omission order is System, Admin, Repo, User, then name and
main prompt path. This is deterministic order, not relevance ranking.

CoreCompatible host catalogs use the full normalized description and the host
ordering above. ExtensionCompatible catalogs use `metadata.short-description`
when present and preserve provider order. Codex Desktop/app-server can allocate
one budget across executor, orchestrator, and host catalogs, so an isolated host
calculation is not an exact replay of that combined surface.

## No Supported 2 Percent Override

On the pinned source, `SKILL_METADATA_CONTEXT_WINDOW_PERCENT = 2` is an
internal compile-time constant. No supported `config.toml` field, CLI flag,
environment variable, or feature flag changes it. Issue
`openai/codex#19679` requests configurability; the request is evidence that the
setting was missing, not evidence of a hidden override.

Before repeating this conclusion for another installed version:

1. bind the exact executable path and `codex --version`;
2. inspect local help and `codex features list`;
3. inspect the documented config schema or run a non-persistent strict-config
   check;
4. compare with a compatible source revision.

Do not add guessed persistent config keys. A permissive parser accepting a key
does not prove that the renderer consumes it.

Changing the constant requires a custom Codex build. A separately built CLI
does not automatically replace a Codex Desktop bundled/app-server runtime, and
an upgrade can restore upstream behavior.

## Diagnostic Workflow

Start with the local surface:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_cli_inspector.py" \
  --commands doctor debug "debug prompt-input" features plugin --json
codex features list
```

Treat `codex debug prompt-input` as sensitive and potentially stateful. It can
contain absolute paths, model/config details, and complete prompt fragments,
and a fresh render can initialize or refresh runtime caches. Inspect its help
first, bind the exact executable and cwd, and avoid pasting raw output.

For an existing task, use `codex-log-reader` to locate the exact rollout before
examining its recorded developer content. Record rollout id, timestamp, model,
originator/CLI version when present, and the selected catalog block. The absence
of a visible omission marker does not prove `omitted_count = 0`, and short
descriptions alone do not prove renderer truncation without session-time
source/cache evidence.

For source-only inventory modeling, run:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_skill_catalog_audit.py" \
  <enabled-skill-roots-or-plugin-roots> --context-window <tokens> --json
```

The script models an isolated CLI host/CoreCompatible scenario with absolute
locators. For identical renderer inputs, Codex selects a root-aliased candidate
only when its inclusion, retained-description, or cost comparator is better
than the absolute candidate. The script cannot reconstruct actual scope/source
kind, runtime display paths and roots, provider catalogs, or shared allocation;
it therefore reports `fidelity.exact: false` and an overall direction of
`unknown`. One plugin proves only that plugin's modeled contribution.

Malformed optional `agents/openai.yaml` metadata fails open in Codex and in the
audit: the skill remains implicitly visible. Missing or blank base names fall
back to the skill directory name. Treat `unique_plain_name_in_supplied_inventory`
as a local inventory fact, not proof that runtime plain-name selection is
unambiguous across connectors or other catalogs.

`--metadata-token-cap` is an analysis-only scenario input. It is not a Codex
runtime setting.

## Mitigation Ladder

Use the smallest supported change and verify it in a new task:

1. Remove duplicate discovery inputs or disable an unused plugin/skill through
   a verified current mechanism. Plugin state changes require explicit user
   intent.
2. For a rare source-owned skill that should be manual, set
   `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. This keeps
   the enabled skill out of the implicit catalog while preserving explicit
   selection.
3. Route metadata redesign to Capability Workbench. Front-load the
   discriminative trigger clause, shorten unnecessary metadata, and re-audit
   the full enabled inventory.
4. Use a model with a larger raw context window when the product exposes one;
   the percentage stays 2 but the absolute budget grows.
5. Treat a source patch that changes the percentage, allocator, warning
   threshold, or ordering as an unsupported custom build.

Never edit a runtime cache copy or rollout JSONL as mitigation. Change the
canonical source or supported installed/enabled state, refresh deliberately,
and verify source, cache, and new-session visibility separately.

## Primary Sources

- Budget constant and formula:
  https://github.com/openai/codex/blob/95c7265e849e6e360a7fa53ffeac70b25d6051a3/codex-rs/ext/skills/src/render.rs#L19-L29
- Budget fallback and allocation:
  https://github.com/openai/codex/blob/95c7265e849e6e360a7fa53ffeac70b25d6051a3/codex-rs/ext/skills/src/render.rs#L127-L142
  and
  https://github.com/openai/codex/blob/95c7265e849e6e360a7fa53ffeac70b25d6051a3/codex-rs/ext/skills/src/render.rs#L302-L431
- Root aliases and charged overhead:
  https://github.com/openai/codex/blob/95c7265e849e6e360a7fa53ffeac70b25d6051a3/codex-rs/ext/skills/src/render.rs#L907-L1107
- Approximate token counter:
  https://github.com/openai/codex/blob/95c7265e849e6e360a7fa53ffeac70b25d6051a3/codex-rs/utils/string/src/truncate.rs#L71-L74
- Explicit selection:
  https://github.com/openai/codex/blob/95c7265e849e6e360a7fa53ffeac70b25d6051a3/codex-rs/ext/skills/src/selection.rs
- Configurability request:
  https://github.com/openai/codex/issues/19679
