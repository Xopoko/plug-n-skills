# Plugin Source Index

This directory contains the source bundles for every plugin pack published by this
repository. Each plugin is self-contained enough to validate and install, but
the repository root owns the shared marketplace, validation, and publication
workflow.

## Plugin Catalog

| Directory | Codex id | Claude marketplace id | Focus |
| --- | --- | --- | --- |
| `build-swift-apps` | `build-swift-apps@local` | `build-swift-apps@xopoko-plug-n-skills` | Build, debug, profile, test, refactor, and release Swift apps across Apple platforms. |
| `pixijs` | `pixijs@local` | `pixijs@xopoko-plug-n-skills` | Build and debug PixiJS v8 applications, scenes, assets, events, filters, performance, and migrations. |
| `tauri` | `tauri@local` | `tauri@xopoko-plug-n-skills` | Build, secure, debug, test, package, and release Tauri 2 desktop/mobile apps. |
| `scientific-research` | `scientific-research@local` | `scientific-research@xopoko-plug-n-skills` | Discover scholarly sources, deduplicate papers, extract claims, and validate evidence. |
| `context-density` | `context-density@local` | `context-density@xopoko-plug-n-skills` | Audit agent context cost, prompt contracts, typed state, compression, and structural overlap. |
| `capability-workbench` | `capability-workbench@local` | `capability-workbench@xopoko-plug-n-skills` | Design, audit, synthesize, and package agent skills/plugins and LLM harnesses. |
| `codex-cli` | `codex-cli@local` | `codex-cli@xopoko-plug-n-skills` | Diagnose and operate Codex CLI, skill catalogs, automation, tasks, plugins/MCP, logs, and environments. |
| `scheduled-automation` | `scheduled-automation@local` | `scheduled-automation@xopoko-plug-n-skills` | Diagnose and prove local scheduler runs across launchd, systemd, cron, and Windows Task Scheduler. |
| `git-workflows` | `git-workflows@local` | `git-workflows@xopoko-plug-n-skills` | Bind eligible GitHub/GitLab access, review code and feedback, deliver stacked changes, and recover worktrees or signed commits with fail-closed proof. |
| `technology-intelligence` | `technology-intelligence@local` | `technology-intelligence@xopoko-plug-n-skills` | Compare technology adoption, trial, replacement, and delivery-mode options through dated evidence and explicit decision profiles. |
| `claude-code` | `claude-code@local` | `claude-code@xopoko-plug-n-skills` | Operate and diagnose Claude Code CLI automation, plugins/MCP, hooks, agents, sessions, and worktrees. |
| `architecture-intelligence` | `architecture-intelligence@local` | `architecture-intelligence@xopoko-plug-n-skills` | Audit and evolve software architecture, topology, async state consistency, conformance, ADRs, and refactoring. |
| `design-intelligence` | `design-intelligence@local` | `design-intelligence@xopoko-plug-n-skills` | Frame and critique product/UX architecture, interaction, accessibility, visual communication, and design systems. |
| `game-design-intelligence` | `game-design-intelligence@local` | `game-design-intelligence@xopoko-plug-n-skills` | Design and critique gameplay, progression, economy, retention, onboarding, and live service. |
| `kotlin-multiplatform` | `kotlin-multiplatform@local` | `kotlin-multiplatform@xopoko-plug-n-skills` | Design, build, diagnose, test, secure, publish, and release Kotlin Multiplatform systems. |
| `spec-driven-development` | `spec-driven-development@local` | `spec-driven-development@xopoko-plug-n-skills` | Specify, plan, implement, and audit traceable Spec-Driven Development work. |
| `engineering-hygiene` | `engineering-hygiene@local` | `engineering-hygiene@xopoko-plug-n-skills` | Audit changed code, untangle business logic, inspect rendered UI, and provision missing tools. |

## Expected Plugin Shape

```text
plugins/<plugin-name>/
  .codex-plugin/plugin.json
  .claude-plugin/plugin.json
  assets/
  skills/
  references/
  scripts/
```

Not every plugin needs every optional directory, but each published plugin must
have both manifests and at least one skill entrypoint.

## Update Checklist

When a plugin changes:

- keep the folder name and manifest `name` fields identical;
- update both Codex and Claude manifest metadata when positioning changes;
- keep large evidence, ledgers, and source maps in `references/`, not in hot
  `SKILL.md` files;
- put deterministic helpers in `scripts/` and keep them runnable from the plugin
  root;
- store icons and media in `assets/`, prefer the Capability Workbench plugin icon
  system for new generated plugin icons, and reference media from the Codex
  manifest when appropriate;
- run the root validator before committing:

  ```bash
  python3 scripts/validate-repository.py
  ```
