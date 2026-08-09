# Skill Catalog Runtime Comparison

Use this reference when a skill audit, portfolio decision, or host migration
depends on what the model can see before a skill is selected. The catalog
budget, overflow policy, and body-loading boundary are host-specific. Do not
project Codex's 2 percent rule onto another agent.

## Comparison Contract

For every host, distinguish four states:

1. discovery reads files or remote metadata;
2. the runtime keeps metadata or complete bodies in process memory;
3. a compact catalog becomes model-visible;
4. a selected body becomes model-visible.

"Lazy loading" is ambiguous unless the report says whether it means disk I/O,
process memory, or model context. Also count the serialized catalog actually
sent to the model: wrappers, paths or locators, aliases, versions, warnings,
and namespace prefixes can cost as much as descriptions.

## Pinned Runtime Matrix

| Runtime snapshot | Initial model-visible catalog | Body boundary | Catalog budget and overflow | Runtime tuning |
| --- | --- | --- | --- | --- |
| OpenAI Codex `95c7265e849e6e360a7fa53ffeac70b25d6051a3` | `name`, description, locator kind, locator; optional root-alias table | Selected `SKILL.md` is injected after explicit or implicit selection | Hard metadata budget: `max(floor(context_window * 2 / 100), 1)` approximate tokens; fallback is 8,000 Unicode characters when the window is unavailable. Approximation is `ceil(UTF-8 bytes / 4)`. Descriptions are capped at 1,024 characters, then shortened round-robin; if minimum lines still do not fit, whole entries are omitted. Alias-table overhead is inside the budget, while the surrounding usage instructions are outside it. | No supported config key, CLI flag, environment variable, or feature flag for the 2 percent constant on this snapshot. Reduce the implicit inventory, shorten metadata, use a larger-window model, or carry an unsupported source patch. |
| `VineeTagarwaL-code/claude-code` `13fba341fc26bc60bd662f5a32aa843ec2fccd27` | `name`, description, optional `when_to_use` | Local bodies are read during discovery but become model-visible on invocation | Soft target: `floor(context_window * 4 * 0.01)` characters, fallback 8,000 characters. Descriptions are capped at 250 characters and non-bundled descriptions can become names-only, but entries are not dropped when the target is exceeded. | `SLASH_COMMAND_TOOL_CHAR_BUDGET` can override the target in this snapshot. |
| OpenClaw `aa7cf44c75a123a2724f20b05cd10d66cf7e65f3` | XML with `name`, description, location, optional location note and content version | Ordinary runs read the selected locator; Code Mode uses `skills.read` | Default hard prompt limit is 18,000 JavaScript characters and 150 skills. Overflow removes optional notes, switches to a compact format, preserves the largest alphabetical identity prefix, and can return an empty catalog if no complete identity fits. | Global and per-agent `maxSkillsPromptChars`; other discovery and prompt-count limits are separately configurable. |
| NousResearch Hermes Agent `1fe53bd1ab3bfce098a2161cad0622d436738476` | Category, name, description, and optional provenance annotations | Files are read during discovery for metadata; the body becomes model-visible through `skill_view`, slash invocation, or explicit preload | No dedicated aggregate catalog budget or context-window percentage was identified in the pinned source. Startup descriptions are capped at 60 characters. Catalog entries are not pruned in response to total context size. | Disable or remove unnecessary skills; plugin-registered skills stay out of the startup catalog and require explicit `plugin:skill` loading. |
| OpenCode `5347b5e0097bd912b3511e517d81c4ea5581c35f` | Current path: XML `name`, description, location. V2 path: name and description | Complete bodies are read and cached before the first model request, but injected into model context only through the skill tool or command | No dedicated skill-catalog percentage, character budget, ranking, or overflow pruning was identified in this snapshot. Permission filters decide eligibility; generic context compaction and tool-output limits are separate mechanisms. | No catalog-budget setting identified in either active implementation. |
| Qwen Code `18b925103ad01ae8f4435846bdac3a7be9c3ae0e` | XML with name, description, optional `when_to_use`, and storage level | Complete bodies are read into the manager cache during discovery and become model-visible on skill invocation | A soft 8,000 JavaScript-character trigger simplifies non-bundled entries to first-line descriptions and removes `when_to_use`. It does not re-check a hard cap and does not omit entries. | No context-window-relative catalog setting identified on this snapshot. |

## Codex-Specific Consequences

- Two percent is a hard allocation rule for the metadata lines and any selected
  root-alias-table overhead. It is not a cap on the complete
  `<skills_instructions>` fragment and not a cap on a subsequently loaded
  `SKILL.md` body.
- The constant is compile-time behavior on the pinned snapshot. Treat an issue
  asking for configurability as evidence that a supported override is missing,
  not as evidence that a hidden setting exists.
- Budget pressure is aggregate across the enabled, implicitly invocable
  inventory. A per-skill description-length rule cannot prove visibility.
- `agents/openai.yaml` with
  `policy.allow_implicit_invocation: false` removes an enabled skill from the
  model-visible catalog while preserving explicit selection. Use this for rare,
  intentionally manual skills, not as an automatic response to token pressure.
- Root aliases are an optimization, not free compression: Codex compares the
  aliased and absolute render and charges the alias table against the same
  metadata budget.
- In hard omission mode, catalog order matters. Host entries are ordered by
  System, Admin, Repo, then User scope, followed by name and prompt path. Do not
  describe omission as relevance ranking.

## Audit Rules

1. Pin the runtime repository, commit, product path, and model context window.
2. Identify the model-visible serialization and whether a catalog is injected
   once, per turn, or through a synthetic message.
3. Record whether the budget is hard, soft, or absent; state its unit exactly:
   tokenizer tokens, approximate tokens, Unicode characters, UTF-16 code units,
   UTF-8 bytes, entry count, or a combination.
4. Reproduce every degradation stage: full metadata, shortened metadata,
   names-only or identity-only, whole-entry omission, and empty catalog.
5. Separate a hidden or explicit-only skill from a budget-omitted skill.
6. Separate source, installed/cache, and live-session state. A valid source
   edit does not prove that an existing session rebuilt its catalog.
7. Prefer the installed binary and effective prompt for local behavior. Use a
   source snapshot to explain behavior only after version drift is bounded.

## Evidence And Trust Notes

The OpenAI Codex, OpenClaw, Hermes Agent, OpenCode, and Qwen Code rows use their
public repositories at the commits above. The `VineeTagarwaL-code/claude-code`
row is different: it is an unaffiliated one-commit source snapshot with no
upstream history, package manifest, README, or license, and it is not an
official Anthropic repository. Its observed 1 percent implementation is useful
only as evidence about that snapshot, not as a verified claim about any
official Claude Code release.

Primary implementation pointers:

- Codex renderer and budget:
  https://github.com/openai/codex/blob/95c7265e849e6e360a7fa53ffeac70b25d6051a3/codex-rs/ext/skills/src/render.rs
- Codex request for a configurable percentage:
  https://github.com/openai/codex/issues/19679
- Unofficial Claude snapshot formatter:
  https://github.com/VineeTagarwaL-code/claude-code/blob/13fba341fc26bc60bd662f5a32aa843ec2fccd27/tools/SkillTool/prompt.ts
- OpenClaw prompt limits and compact overflow:
  https://github.com/openclaw/openclaw/blob/aa7cf44c75a123a2724f20b05cd10d66cf7e65f3/src/skills/loading/workspace.ts
- Hermes startup catalog builder:
  https://github.com/NousResearch/hermes-agent/blob/1fe53bd1ab3bfce098a2161cad0622d436738476/agent/prompt_builder.py
- OpenCode current and V2 catalogs:
  https://github.com/anomalyco/opencode/blob/5347b5e0097bd912b3511e517d81c4ea5581c35f/packages/opencode/src/skill/index.ts
  and
  https://github.com/anomalyco/opencode/blob/5347b5e0097bd912b3511e517d81c4ea5581c35f/packages/core/src/skill/guidance.ts
- Qwen Code catalog simplification:
  https://github.com/QwenLM/qwen-code/blob/18b925103ad01ae8f4435846bdac3a7be9c3ae0e/packages/core/src/utils/environmentContext.ts
