# Agent Guidance Files

Use this reference for `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`,
`.claude/rules/`, `.cursor/rules/`, and related coding-agent instruction
surfaces.

## Source Behavior And Precedence

General:

- Agent guidance files are prompt context. They shape behavior, but they do
  not replace higher-priority runtime instructions, user prompts, permissions,
  hooks, CI, tests, or policy controls.
- More specific guidance should only be treated as overriding broader guidance
  when the target agent documents that merge behavior.
- Treat edits to startup-loaded guidance as future-session changes. When in
  doubt, start a fresh run or session before verifying visibility.
- The open `AGENTS.md` format is plain Markdown with no required fields. Its
  common rule is "closest file wins," but target-agent documentation is the
  source of truth when behavior differs.

Codex:

- `AGENTS.md` is project guidance that Codex reads before work starts.
- Codex builds an instruction chain once per run or launched TUI session.
- Global guidance lives under `CODEX_HOME`, defaulting to `~/.codex`. At that
  level Codex reads `AGENTS.override.md` if present, otherwise `AGENTS.md`,
  and uses only the first non-empty file.
- Project discovery starts at the project root, usually the Git root, and
  walks down to the current working directory. If no project root is found,
  Codex only checks the current directory.
- In each project directory Codex checks `AGENTS.override.md`, then
  `AGENTS.md`, then configured names in `project_doc_fallback_filenames`.
  Codex includes at most one guidance file per directory, so an override file
  suppresses a sibling `AGENTS.md`.
- Merge order is global first, then project files from root down to the
  current working directory. More specific files appear later in the combined
  prompt and override earlier guidance by position.
- Codex skips empty files and stops when combined project guidance reaches
  `project_doc_max_bytes`, which defaults to 32 KiB. Change
  `project_doc_fallback_filenames` or `project_doc_max_bytes` in Codex config,
  then start a new command or session.
- Use `AGENTS.override.md` for intentional temporary overrides. Avoid
  committing override files unless that stronger same-directory behavior is
  meant to be part of the repository contract.

Claude Code:

- `CLAUDE.md` files are Markdown instructions for managed policy, user,
  project, or local scope. Claude Code reads them at the start of every
  session.
- Claude treats these files as context, not enforced configuration. Use
  PreToolUse hooks, permissions, managed settings, scripts, CI, or tests for
  behavior that must be blocked or guaranteed.
- Broad scopes load before specific scopes. Managed policy guidance loads
  before user guidance, user-level rules load before project rules, and
  project guidance appears after user guidance.
- Common locations are managed policy `CLAUDE.md`, `~/.claude/CLAUDE.md`,
  repository `CLAUDE.md`, repository `.claude/CLAUDE.md`, and local
  `CLAUDE.local.md`. Keep local files out of version control.
- From the current working directory, Claude walks up the directory tree and
  loads discovered `CLAUDE.md` and `CLAUDE.local.md` files in full at launch.
  Ordering is filesystem root down to the working directory; within the same
  directory, `CLAUDE.local.md` is appended after `CLAUDE.md`.
- `CLAUDE.md` and `CLAUDE.local.md` files below the working directory load on
  demand when Claude reads files in those subdirectories.
- `CLAUDE.md` can import additional files with `@path/to/file`. Relative paths
  resolve from the file containing the import, absolute paths are allowed, and
  recursive imports are capped at four hops.
- Claude Code reads `CLAUDE.md`, not `AGENTS.md`. For portable repositories,
  create a small `CLAUDE.md` that imports `@AGENTS.md` and then adds only
  Claude-specific deltas. A symlink can work when no deltas are needed.
- Use `.claude/rules/*.md` for larger or path-scoped Claude rules. Rules
  without path frontmatter load at launch; path-scoped rules load when Claude
  works with matching files.
- Use `claudeMdExcludes` in large repositories when ancestor or unrelated
  subtree guidance would pollute the current task. Managed policy guidance
  cannot be excluded.
- Keep each `CLAUDE.md` concise; Claude's official guidance targets under
  200 lines per file.
- Move multi-step procedures or narrow subtree behavior to skills or scoped
  rules instead of making one large startup file.

Cursor:

- Cursor supports Project, Team, and User Rules plus `AGENTS.md`.
- Cursor rules are prompt context added when a rule applies.
- `AGENTS.md` is a plain Markdown alternative to `.cursor/rules` for simple,
  readable project instructions.
- Cursor supports `AGENTS.md` in the project root and subdirectories.
- Nested `AGENTS.md` files are combined with parent guidance; more specific
  instructions take precedence for work in that subtree.
- Project Rules live in `.cursor/rules/*.mdc`. Plain `.md` files in that
  directory are ignored by Cursor's project-rule system.
- Cursor Project Rules can always apply, attach by glob, attach by relevance
  description, or apply only when mentioned manually.
- Cursor's documented Team/Project/User rule precedence is Team Rules,
  then Project Rules, then User Rules. Applicable rules are merged, and earlier
  sources take precedence on conflicts.
- Team Rules can be enforced from Cursor's dashboard on supported plans. User
  Rules are global to Agent Chat and do not apply to Inline Edit.
- Use `.cursor/rules/*.mdc` when you need structured rule metadata, glob-based
  attachment, intelligent attachment descriptions, remote rules, or Team/User
  rule distribution.

Open format:

- `AGENTS.md` is plain Markdown, with no required fields.
- Its purpose is to be a predictable README-like place for agent-specific
  instructions that would clutter human-facing README files.
- Common sections include setup commands, build/test commands, code style,
  testing instructions, security considerations, and PR or review rules.

## File Selection

Prefer `AGENTS.md` when:

- the guidance should be portable across several coding agents;
- the repo has no agent-specific instruction file yet;
- the rules are simple Markdown and should be versioned with the repository;
- nested subproject instructions are enough for scope control.

Prefer `AGENTS.override.md` only when:

- Codex is a target agent;
- a same-directory `AGENTS.md` or fallback file must be intentionally
  suppressed;
- the stronger behavior is temporary or explicitly part of the repository
  contract.

Prefer `CLAUDE.md` when:

- the instruction is Claude Code-specific;
- the repo already uses Claude Code project context conventions;
- the guidance depends on Claude-only workflows such as hooks, slash commands,
  or Claude-specific settings.

Prefer `.claude/rules/*.md` when:

- Claude needs path-scoped guidance that should not load for every task;
- a topic is large enough that keeping it in startup `CLAUDE.md` would reduce
  adherence;
- the rule is Claude-specific but should stay modular and versioned.

Prefer `.cursor/rules/*.mdc` when:

- Cursor needs metadata, descriptions, glob rules, or auto-attachment behavior;
- the rule should be imported, distributed, or managed through Cursor's rule UI;
- the rule is too specific to always load through `AGENTS.md`.

Use both only when the overlap is intentional:

- keep shared, portable guidance in `AGENTS.md`;
- put tool-specific deltas in `CLAUDE.md`, `.claude/rules/`, or Cursor rules;
- avoid duplicating the same rule in several files unless one file exists only
  as a compatibility pointer.

## Load-Order Design Patterns

Portable baseline:

- Put shared repository guidance in root `AGENTS.md`.
- For Claude Code, add `CLAUDE.md` containing `@AGENTS.md` plus a short
  `## Claude Code` section for Claude-only behavior.
- For Cursor, use root `AGENTS.md` for simple guidance and add
  `.cursor/rules/*.mdc` only for globs, manual rule invocation, intelligent
  attachment, or Team/User distribution.

Monorepo or multi-package baseline:

- Put repo-wide invariants at the root.
- Put different commands, package managers, test suites, release boundaries,
  or ownership expectations in nested guidance files near the subtree.
- Do not repeat root rules in every child file. Child files should contain only
  the delta that matters under that directory.

Personal or machine-local baseline:

- Put durable personal Codex preferences in global Codex guidance, not in a
  repository file.
- Put personal Claude project notes in `CLAUDE.local.md` or a user-level
  Claude file and keep local files ignored.
- Keep public repositories free of local paths, private URLs, credentials,
  tenant names, and host-specific assumptions.

Conflict handling:

- Prefer deleting stale rules over adding exceptions around them.
- If two same-scope files disagree, do not rely on model interpretation. Merge
  the intent into one clear instruction or remove the weaker rule.
- If two tools need different behavior, keep the portable rule in `AGENTS.md`
  and put only the tool-specific delta in that tool's file.

## Authoring Workflow

1. Inventory guidance surfaces:
   `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`, `.claude/rules/`,
   `.cursor/rules/`, `.cursorrules`, README, CONTRIBUTING, docs, CI, package
   manifests, makefiles, scripts, and PR templates.
2. Identify source-of-truth commands from package scripts, makefiles,
   task runners, CI jobs, or documented local workflow. Prefer existing
   command names over inferred commands.
3. Inspect conventions from source files and configured formatters/linters.
4. Check testing patterns from test directories, CI, and recent commits.
5. Scan recent commit messages or contribution docs for review and commit
   expectations. Do not invent a convention if evidence is weak.
6. Decide root versus nested scope. Use nested files only for real differences:
   separate package managers, tests, language stacks, security boundaries, or
   ownership/review expectations.
7. Draft the smallest useful file. Every bullet should be actionable, durable,
   and tied to a repo fact or explicit user rule.
8. Link to longer docs instead of copying them. Startup guidance should route
   the agent to detail, not become the detail dump.
9. Validate the content: no secrets, no private/local paths, no speculative
   commands, no outdated names, no conflicts with existing guidance.
10. Run repo checks and, when safe, an agent visibility probe.

## Recommended Shape

```markdown
# Agent Guidance

## Repository Map
- `src/`: application code.
- `tests/`: unit and integration tests.

## Commands
- Install: `...`
- Test: `...`
- Lint: `...`

## Coding Rules
- ...

## Verification
- Before finishing, run the narrowest relevant check.

## Safety
- Do not commit secrets or generated local state.
```

Keep names and headings aligned with the existing repository style. If an
existing `AGENTS.md` already has a title and section vocabulary, preserve that
shape unless it is misleading.

## Maintenance

Add or update guidance when:

- an agent repeats the same mistake;
- review feedback repeats;
- setup, build, test, lint, or release commands change;
- a new directory has different workflow rules;
- a source-of-truth doc moves;
- the file grows large enough that detail should move to references.

Do not add guidance for:

- one-off task context;
- unresolved plans or guesses;
- volatile live service state better checked with tools;
- instructions that only one current user needs;
- behavior that must be enforced by permissions or hooks.

## Verification Probes

Codex:

- Start a fresh run or session after changing guidance.
- Ask Codex to summarize active instruction sources:
  `codex --ask-for-approval never "Summarize the current instructions."`
- For nested guidance, run from the target subdirectory and confirm parent plus
  child guidance appears in order:
  `codex --cd subdir --ask-for-approval never "Show which instruction files are active."`
- If available, enable a plaintext log with `codex -c log_dir=./.codex-log`
  and inspect the loaded instruction sources. If instructions look stale,
  restart Codex; there is no manual guidance cache to clear.

Claude Code:

- For evidence, use Claude Code's official `/memory` diagnostic command, when
  available, to inspect which `CLAUDE.md`, `CLAUDE.local.md`, and rule files
  are loaded.
- Restart the session after changing `CLAUDE.md` if current context does not
  reflect the update.
- For imported `AGENTS.md`, verify that `CLAUDE.md` imports the file rather
  than duplicating stale text.
- Use hooks or settings validation for enforced behavior, not guidance text
  alone.

Cursor:

- Confirm whether the repo uses `AGENTS.md` or `.cursor/rules`.
- For Project Rules, ensure `.mdc` frontmatter, descriptions, and globs match
  the intended files.
- For `AGENTS.md`, place the file at root or the specific subtree and test from
  a file under that scope.

## Source Links

- OpenAI Codex AGENTS.md guide:
  https://developers.openai.com/codex/guides/agents-md
- OpenAI Codex customization guide:
  https://developers.openai.com/codex/concepts/customization
- OpenAI Codex best practices:
  https://developers.openai.com/codex/learn/best-practices
- Claude Code docs:
  https://docs.anthropic.com/en/docs/claude-code
- Cursor rules guide:
  https://cursor.com/docs/rules
- AGENTS.md open format:
  https://agents.md/
