---
name: agent-guidance-factory
description: >-
  Create, refresh, audit, or migrate repository agent guidance files such as
  AGENTS.md, AGENTS.override.md, CLAUDE.md, .claude/rules, and Cursor rules.
  Use when a repo needs durable coding-agent instructions, instruction
  load-order decisions, nested guidance, or cleanup of bloated or stale agent
  docs. Do not use for ordinary human README or CONTRIBUTING docs unless they
  must feed agent guidance.
---

# Agent Guidance Factory

Create source-controlled instructions that coding agents actually load and can
follow. These files guide behavior; they do not replace linters, hooks, tests,
permissions, or other enforcement.

Read `references/agent-guidance-files.md` before creating, migrating, or
materially changing `AGENTS.md`, `CLAUDE.md`, `.claude/rules/`, or
`.cursor/rules/`.

## Route

1. Identify the target agents and existing surfaces. Prefer portable
   `AGENTS.md` for shared repository guidance. Use `CLAUDE.md` only for
   Claude Code-specific behavior, and Cursor rules when structured metadata,
   glob attachment, or Team/User/Project rule behavior is required.
2. Choose scope deliberately: root for every task in the repo, nested files for
   subtrees with different commands or constraints, and override files only
   when the target agent documents that override behavior.
3. Inspect the repo before writing: root layout, build/test/lint scripts, CI,
   docs, config, existing guidance files, PR templates, and recent commit
   messages. Verify commands from source files rather than inventing them.
4. Write concise, directive Markdown. Include only durable facts and workflows
   that matter in most relevant sessions: layout, exact commands, coding
   conventions, test expectations, security/configuration boundaries, review
   expectations, and completion proof.
5. Keep hot guidance small. Include repo evidence only when it changes an
   agent action, boundary, command, style rule, test rule, or contribution
   workflow. Move long procedures, architecture notes, release runbooks, and
   rare variants into linked docs or skills.
6. Preserve and reconcile existing rules. If instructions conflict, stop and
   ask unless source evidence makes one rule clearly stale.
7. Validate with the repo's normal checks and any agent-specific visibility
   proof that is cheap and safe for the current host.
8. For monorepos, many guidance files, or density/scale work, use the scale
   pipeline in `references/agent-guidance-files.md` before editing.

## Content Rules

- Use repository-relative paths and portable commands.
- Keep repository-facing text English and ASCII unless the file already has a
  clear different character set.
- Do not include secrets, private project names, personal names, local absolute
  paths, credentials, live tokens, or unverified service details.
- Do not promise automatic enforcement. Point to scripts, hooks, CI, tests, or
  review gates when a rule must be enforced.
- Add a rule after repeated agent mistakes, recurring review feedback, or a
  stable project convention that a new contributor would need.
- Remove stale guidance when commands, frameworks, ownership, or release flows
  change.

## Suggested Sections

Use only sections supported by evidence from the repository:

- Repository Map
- Build, Test, And Dev Commands
- Coding Style And Naming
- Testing And Verification
- Security And Configuration
- Git, Review, And Completion Rules
- Agent-Specific Notes

## Report

State the guidance files changed, why that scope was chosen, which source facts
were verified, which checks ran, whether any agent visibility was verified, and
what remains intentionally out of scope.
