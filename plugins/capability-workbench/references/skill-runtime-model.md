# Skill Runtime Model

Use this reference when creating, synthesizing, refactoring, vetting, or
installing agent skills. It describes how skills are discovered, selected,
loaded, and activated across Codex, Claude Code, Cursor, and the open Agent
Skills format.

## Core Model

A skill is a versioned folder with a required `SKILL.md` file and optional
supporting resources:

```text
skill-name/
├── SKILL.md
├── scripts/
├── references/
├── assets/
└── agents/
    └── openai.yaml
```

Progressive disclosure is the reason this structure exists:

1. Startup or discovery loads compact metadata: usually `name`, `description`,
   and a path or command handle.
2. Selection happens from metadata. Explicit invocation always matters; implicit
   invocation depends on the `description` matching the task.
3. Activation loads the full `SKILL.md` body.
4. Execution may read references, execute scripts, or use assets only when the
   activated instructions call for them.

Design implication: the description is the trigger contract, not the procedure.
Put enough in metadata for the agent to decide to read the skill. Put workflow,
commands, safety boundaries, source references, and validation in the body or
in linked resources.

## Portable Skill Contract

Open Agent Skills:

- `SKILL.md` contains YAML frontmatter followed by Markdown.
- Required frontmatter: `name` and `description`.
- `name` is lowercase hyphen-case, max 64 characters, and should match the
  parent folder.
- `description` should say what the skill does and when to use it. Keep key
  triggers near the front because clients may shorten description listings.
- Optional directories have distinct roles: `scripts/` for deterministic code,
  `references/` for on-demand documentation, and `assets/` for templates or
  static resources.
- Keep the main `SKILL.md` under roughly 500 lines and 5,000 tokens. Move
  detailed variants to directly linked reference files.

This repository's plugin-contained skills should stay on the portable subset
unless the validator and target host explicitly support more:

- Required: `name`, `description`.
- Allowed by the local quick validator: `license`, `allowed-tools`,
  `metadata`.
- Do not add Claude- or Cursor-only frontmatter fields to shared plugin skills
  unless the repository validator is updated and the target behavior is
  intentional.
- The plugin validator currently rejects enabled `disable-model-invocation` in
  plugin skills. Keep invocation policy in host-specific wrappers or plugin
  metadata instead of silently breaking cross-agent publication.

## Codex Behavior

Codex skills are available in the CLI, IDE extension, and Codex app.

Selection:

- Codex starts with a list of available skill metadata: name, description, and
  file path.
- Codex loads the full `SKILL.md` only after selecting a skill.
- Explicit invocation works by mentioning a skill in the prompt, using `/skills`
  or `$` where supported.
- Implicit invocation depends on `description`; front-load the most important
  task words because the initial skill list is budgeted and descriptions can be
  shortened.

Catalog budget:

- The documented initial metadata list is capped at 2% of the model context
  window. If the context window is unknown, the fallback is 8,000 characters.
  This budget applies to discovery metadata, not to the selected `SKILL.md`
  body.
- In the audited core renderer, the token-mode limit is
  `max(floor(context_window * 2 / 100), 1)`. Metadata cost is estimated as
  `ceil(UTF-8 bytes / 4)`, not with the model tokenizer. Each description is
  first normalized to one whitespace-separated line and capped at 1,024
  characters. Plugin skills are rendered with their qualified
  `plugin-name:skill-name`, which also consumes budget.
- If full metadata does not fit but every minimum `name + path` line does,
  Codex distributes the remaining space across description prefixes one
  Unicode character at a time. Every skill name stays model-visible in this
  mode, but implicit matching can lose discriminative terms from later in a
  description.
- If the minimum lines do not fit, Codex removes all descriptions and omits
  whole entries. An omitted entry's name and path are absent from the model's
  initial discovery list. The enabled host inventory can still resolve an
  explicit unambiguous `$skill` mention and inject the selected instructions.
- `agents/openai.yaml` with `policy.allow_implicit_invocation: false` excludes
  that enabled skill from the implicit catalog while preserving explicit use.
  This is useful for rare or manually selected skills that should not consume
  discovery budget.
- Budget pressure is aggregate. A single description length cannot prove that
  a skill will be visible: the result also depends on every enabled implicitly
  invocable skill, locator lengths, aliases, scope ordering, model window, and
  any tighter host cap.

Use the bundled conservative audit against the broadest concrete enabled
inventory available:

```bash
python3 "$PLUGIN_ROOT/scripts/skill/codex_skill_catalog_audit.py" \
  <skill-roots-or-plugin-roots> --context-window <tokens> --json
```

The audit mirrors the core budget phases with absolute paths. Codex may choose
shorter path aliases and preserve more metadata. For a host-wide claim, include
System, Admin, Repo, and User skills; auditing one plugin proves only that
plugin's contribution. Pass `--metadata-token-cap` when a known host surface
sets a tighter ceiling than 2%.

Discovery and scope:

- The audited core recursively scans for exact `SKILL.md` filenames to depth
  six, skips hidden descendant directories, and bounds each root scan. Finding
  one `SKILL.md` does not stop descent: a nested example or fixture with that
  exact filename is another discovered skill. Directory symlink policy varies
  by scope.
- Current public Codex docs list repository skills under `.agents/skills` from
  the current working directory up to the repository root, user skills under
  `$HOME/.agents/skills`, admin skills under `/etc/codex/skills`, and bundled
  system skills.
- Existing local Codex installations and this repository's installer may also
  use `${CODEX_HOME:-$HOME/.codex}/skills` for personal skills. Verify the
  active environment before claiming a global skill is visible.
- If two skills share the same `name`, Codex does not merge them; both can
  appear in selectors.
- Codex follows symlinked skill folders.

Distribution:

- Direct skill folders are best for local authoring and repository-scoped
  workflows.
- Use plugins when distributing reusable skills, bundling multiple skills, or
  shipping MCP/app/hook integrations. A Codex plugin uses
  `.codex-plugin/plugin.json` and can point at a `skills/` directory.
- Installing a plugin makes Codex load the installed cache copy, not the source
  folder directly. Source edits need an install/cache refresh before the
  installed copy changes.

Codex-specific metadata:

- `agents/openai.yaml` can define app-facing interface metadata, invocation
  policy, icons, and tool dependencies.
- Generate or refresh it with `scripts/skill/generate_openai_yaml.py` when the
  displayed name, short description, or representative prompt changes.

## Claude Code Behavior

Claude Code uses skills as slash-invocable and model-invocable procedures.

Selection:

- Users invoke a skill directly with `/skill-name`.
- Claude can also load a skill automatically when task context matches the
  description.
- `disable-model-invocation: true` makes a Claude skill manual-only.
- `user-invocable: false` hides it from the slash menu but does not by itself
  block programmatic skill access.

Discovery and precedence:

- Enterprise skills can be managed for all users.
- Personal skills live under `~/.claude/skills/<skill-name>/SKILL.md`.
- Project skills live under `.claude/skills/<skill-name>/SKILL.md`.
- Plugin skills live under `<plugin>/skills/<skill-name>/SKILL.md` and use a
  `plugin-name:skill-name` namespace.
- When non-plugin skills share a name, enterprise overrides personal and
  personal overrides project.
- Project skills load from `.claude/skills/` in the starting directory and
  parents up to the repository root. Nested `.claude/skills/` below the
  starting directory can be discovered on demand when working in those
  subdirectories.
- `--add-dir` and `/add-dir` grant access and also load `.claude/skills/` from
  added directories. Settings-based additional directories grant file access
  but do not load skills.

Reload behavior:

- Claude Code watches existing skill directories. Adding, editing, or removing
  a `SKILL.md` under watched skill roots can take effect in the current
  session.
- Creating a top-level skills directory that did not exist at session start
  requires restarting Claude Code.
- If a skill folder is also a plugin, changes to hooks, MCP config, agents, or
  output styles require plugin reload, not only editing `SKILL.md`.

Claude-specific extensions:

- Frontmatter can include fields such as `when_to_use`, `argument-hint`,
  `arguments`, `allowed-tools`, `disallowed-tools`, `model`, `effort`,
  `context: fork`, `agent`, `hooks`, `paths`, and `shell`.
- Dynamic context injection can run shell snippets before the model sees the
  skill body. Treat this as host-specific behavior and audit commands carefully.
- Use `${CLAUDE_SKILL_DIR}` to reference bundled scripts or files from the
  skill directory regardless of current working directory.

## Cursor Behavior

Cursor supports Agent Skills as an open-standard capability alongside rules,
subagents, and hooks.

Selection:

- Cursor discovers skills at startup and presents them to Agent.
- Agent decides relevance from context and skill metadata.
- Users can manually invoke skills from Agent chat with `/`.
- `disable-model-invocation: true` makes a skill explicit-only.

Discovery and scope:

- Project skills load from `.agents/skills/` and `.cursor/skills/`.
- User-level skills load from `~/.agents/skills/` and `~/.cursor/skills/`.
- Cursor also reads compatible Claude and Codex skill directories:
  `.claude/skills/`, `.codex/skills/`, `~/.claude/skills/`, and
  `~/.codex/skills/`.
- Cursor walks skill roots recursively; category folders are organizational and
  the identity comes from the folder containing `SKILL.md`.
- Nested project skill directories are scoped to files inside that directory.
  A skill under `apps/web/.cursor/skills/` is surfaced for work under
  `apps/web/` without needing a `paths` frontmatter field.

Frontmatter:

- `name` and `description` are required.
- `name` must match the parent folder.
- `paths` scopes the skill to matching files; use it for file-type or subtree
  conditions when directory scoping is not enough.
- `disable-model-invocation` prevents automatic use.
- `metadata` is available for arbitrary extra data.
- Legacy `globs` may still be accepted, but new Cursor skills should use
  `paths`.

Distribution:

- Cursor can import skills from GitHub through its rules UI.
- Cursor has migration support for converting eligible dynamic rules and slash
  commands into skills.
- This repository's `scripts/install-cursor-skills.py` exports plugin-contained
  `SKILL.md` folders directly because Cursor has no plugin marketplace.

## Skill Versus Adjacent Mechanisms

Use a skill when:

- the workflow is reusable but not always needed;
- the agent needs a procedure, checklist, command sequence, template, or
  domain-specific method;
- details can be loaded progressively through references, scripts, or assets;
- the capability should be portable across compatible agents.

Use `AGENTS.md`, `CLAUDE.md`, or rules when:

- the instruction should affect every relevant session;
- the content is a durable repo or team convention, not a callable workflow;
- the target host needs structured rule metadata such as Cursor `.mdc` globs or
  Claude `.claude/rules/` path scoping.

Use a subagent when:

- the task needs a separate context window, parallel work, or independent
  verification;
- intermediate output is noisy and should not pollute the parent context;
- the workflow is broad enough that a one-shot skill would become an overloaded
  pseudo-agent.

Use a plugin when:

- the skill must be distributed as an installable unit;
- multiple skills belong together;
- the package also needs MCP config, app integrations, hooks, icons, or
  marketplace metadata;
- installed visibility and cache state are part of completion.

## Synthesis Workflow For New Skills

1. Bind the target surface: repo-local, plugin-contained, personal/global, or
   reference-only. Validate with the install-scope gate for synthesis work.
2. Gather concrete examples: prompts that should trigger, near misses that
   should not trigger, representative inputs, source documents, commands,
   existing runbooks, and expected output.
3. Decide whether the capability belongs in a skill, rule, agent guidance file,
   subagent, plugin, script, or plain documentation.
4. Write a selection card before frontmatter:

```text
Use when:
Inputs/signals:
Do not use when:
Failure symptoms:
Adjacent skills:
```

5. Keep `description` as the trigger contract. It must say when to read the
   skill, not how to execute the whole workflow.
6. Put core route and required steps in `SKILL.md`.
7. Put long tables, source ledgers, compatibility matrices, examples, and rare
   variants in directly linked `references/`.
8. Put deterministic repeated logic in `scripts/`; test scripts with
   representative inputs.
9. Put templates, images, boilerplate, or static data in `assets/`.
10. Generate or refresh `agents/openai.yaml` when Codex app-facing metadata
    should change.
11. Validate the skill folder and any plugin or install surface that exposes
    it.

## Installation And Visibility Checks

Before copying or installing:

- Vet provenance and safety. Inspect scripts, dependencies, writes, deletes,
  network calls, secrets access, and install commands.
- Reject or isolate skills that require hidden paid APIs, required tokens,
  telemetry, broad filesystem writes, dynamic shell payloads, or unrelated
  infrastructure.
- Do not execute candidate scripts during vetting unless the user asked for
  installation and the script has been inspected.

After source edits:

- Run `quick_validate.py` on the skill.
- Run context-density audit for material skill edits.
- Run plugin validation when the skill is plugin-contained.
- Regenerate README token tables in this repository with
  `scripts/token-report.py` when skill count or content changes materially.

After installed/global changes:

- Check the active agent's actual discovery surface, not just the source path.
- For Codex plugin installs, run the installer and `--check-only` visibility
  proof. Remember the installed cache copy is the user-facing copy.
- For direct Codex skills, verify the target root used by the current host
  (`.agents/skills`, configured user root, or legacy `${CODEX_HOME}/skills`).
- For Claude Code, confirm whether the skill appears in the current session or
  whether a restart or plugin reload is needed.
- For Cursor, confirm the target folder is one of Cursor's discovered roots or
  a supported compatible root.

## Failure Modes

Diagnose these with fresh visibility checks, trigger probes, and source
evidence rather than assumptions:

- A skill validates but does not appear: wrong discovery root, installed copy
  not refreshed, new top-level directory created after session start, disabled
  skill, explicit-only policy, or a budgeted listing that shortened
  descriptions or omitted whole entries.
- A skill appears but under-triggers: description lacks evidence-backed trigger
  terms from prompt probes, file types, symptoms, or adjacent skills.
- A skill over-triggers: description is too generic or lacks negative
  boundaries.
- An agent acts without reading the skill body: description contains too much
  procedure or the task was already solved from ambient context.
- A skill gets bloated: rare variants, tables, and examples stayed in
  `SKILL.md` instead of being routed to references.
- Installed behavior differs from source: the active agent loads a cache copy,
  marketplace copy, or older global skill. Refresh the install state and run a
  visibility check.

## Source Links

- Open Agent Skills specification:
  https://agentskills.io/specification
- Open Agent Skills best practices:
  https://agentskills.io/skill-creation/best-practices
- OpenAI Codex skills:
  https://developers.openai.com/codex/skills
- Audited Codex core renderer snapshot:
  https://github.com/openai/codex/blob/315195492c80fdade38e917c18f9584efd599304/codex-rs/core-skills/src/render.rs
- Audited Codex explicit skill injection snapshot:
  https://github.com/openai/codex/blob/315195492c80fdade38e917c18f9584efd599304/codex-rs/core-skills/src/injection.rs
- OpenAI Codex plugin build guide:
  https://developers.openai.com/codex/plugins/build
- Claude Code skills:
  https://docs.anthropic.com/en/docs/claude-code/skills
- Cursor skills:
  https://cursor.com/docs/skills
