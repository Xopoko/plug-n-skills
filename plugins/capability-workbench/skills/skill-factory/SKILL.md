---
name: skill-factory
description: Create, refactor, split, compress, validate, or package agent skills. Use for SKILL.md trigger design, agents/openai.yaml metadata, skill resources, progressive disclosure, token-efficient instructions, quick validation, and plugin-contained skills.
---

# Skill Factory

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Create skills that any host agent can actually use: clear trigger metadata, compact hot-path instructions, conditional resources, and executable validation.

Read `$PLUGIN_ROOT/references/skill-runtime-model.md` before creating,
synthesizing, materially refactoring, or installing skills across Codex,
Claude Code, Cursor, or the open Agent Skills format. It records startup
metadata, on-demand body loading, resource loading, host-specific discovery
paths, and install/reload behavior.

For material `name` or `description` work, use `skill-trigger-metadata` first. For portfolio-level split, merge, delete, router, reference-extract, or script-extract decisions across multiple skills, use `capability-portfolio-architect` first. This skill owns concrete skill structure, resources, scripts, packaging, and validation after the boundary decision is made.

## Create A Skill

Use the bundled initializer unless you are editing an existing skill. Choose the destination from the selected delivery surface: plugin-contained skills go under the plugin source tree; repo-local skills go under the current or named repository; installed personal skills go in the active agent's global skills dir. Example for an installed Codex skill:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/init_skill.py" <skill-name> --path "${CODEX_HOME:-$HOME/.codex}/skills" --resources scripts,references
```

Choose the destination deliberately:

- installed personal skill: agent's global skills dir — Codex: `${CODEX_HOME:-$HOME/.codex}/skills/<skill-name>`, Claude: `${CLAUDE_HOME:-$HOME/.claude}/skills/<skill-name>`, Cursor: `${CURSOR_HOME:-$HOME/.cursor}/skills/<skill-name>`; detect the active agent with `$PLUGIN_ROOT/scripts/agent_target.py`
- plugin-contained skill: `<plugin-root>/skills/<skill-name>` when the user requested a plugin/plugin pack or the current repository is a plugin source tree
- repo-local skill: when the user, repo instructions, or workspace profile selects the current/named repository as the source surface; record the evidence in `install-scope.json`
- synthesis snapshot: `<output-dir>/synthesized-skill` only for reference-only drafts, failed/partial synthesis, or an explicit no-install request

Keep names lowercase, hyphenated, and under 64 characters.
Do not infer repo-local output from dirty git state or a merely local candidate path. Repo instructions and recognizable plugin/skill source trees are valid evidence only when they apply to the current capability task and do not conflict with the latest user message.

## Write SKILL.md

Frontmatter must include only:

```yaml
---
name: skill-name
description: What the skill does and concrete trigger situations.
---
```

Body guidelines:

- Put routing and required workflow in `SKILL.md`.
- Make frontmatter descriptions agent-triggerable from task context, artifacts, source evidence, file types, failures, or decisions. Avoid descriptions that only say "when the user asks for X" unless explicit user consent is the safety boundary.
- Keep workflow steps out of `description` when they could let the agent act from metadata and skip `SKILL.md`; use `skill-trigger-metadata` for focused name/description audits.
- For adjacent skills, require a compact selection card: use-when, inputs/signals, do-not-use, failure symptoms, and adjacent skills. Preserve this in frontmatter without turning the description into a procedure.
- Move detailed variants, long examples, specs, and edge-case playbooks into directly linked `references/`.
- Add scripts only when deterministic reuse or validation is materially better than rewriting code.
- Do not add README, installation guides, changelogs, or task diaries inside a skill unless the ecosystem explicitly requires them.
- Preserve safety boundaries, exact commands, output contracts, and validation proof.

## Context-Density Pass

For material skill work, measure and audit:

```bash
python3 "$PLUGIN_ROOT/scripts/context/token_count.py" <skill-dir>/SKILL.md --json
python3 "$PLUGIN_ROOT/scripts/context/context_density_audit.py" <skill-dir> --json --top 20
```

Use the audit to remove duplicate hot-path prose, stale history, brittle request-phrase trigger design, and brittle parsing of generated model text. Do not shrink away trigger precision, safety rules, or required commands.

## Validate

Run:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/quick_validate.py" <skill-dir>
```

When `agents/openai.yaml` is present or desired, regenerate it after final SKILL.md edits:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/generate_openai_yaml.py" <skill-dir> \
  --interface display_name="<Display Name>" \
  --interface short_description="<25-64 chars>" \
  --interface default_prompt="<representative task prompt>"
```

Test any added scripts with representative inputs. For complex skills, forward-test with a realistic task if a fresh subagent or isolated session is available.

For complete installed skills, validate the install-scope contract:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" <output-dir>/install-scope.json --final
```

For lightweight edits confined to one existing skill's text or metadata — no new scripts, no installation, no new capability claims — `quick_validate.py` plus a one-line scope note in the report replaces the ledgers.

## Report

State:

- skill path and intended delivery/install surface;
- trigger behavior preserved or added;
- resources included and why;
- validation commands and results;
- residual risks or deferred variants.
