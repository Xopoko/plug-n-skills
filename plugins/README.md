# Plugin Source Index

This directory contains the source bundles for every plugin pack published by this
repository. Each plugin is self-contained enough to validate and install, but
the repository root owns the shared marketplace, validation, and publication
workflow.

## Plugin Catalog

| Directory | Codex id | Claude marketplace id | Focus |
| --- | --- | --- | --- |
| `agent-harness` | `agent-harness@local` | `agent-harness@xopoko-plug-n-skills` | Design and evaluate agent harnesses; operate Codex and Claude runtimes, automation, diagnostics, MCP, sessions, and local schedulers. |
| `capability-workbench` | `capability-workbench@local` | `capability-workbench@xopoko-plug-n-skills` | Design, audit, synthesize, package, install, repair, and reshape agent skills and plugins. |
| `context-density` | `context-density@local` | `context-density@xopoko-plug-n-skills` | Audit agent context cost, prompt contracts, typed state, compression, and structural overlap. |
| `git-workflows` | `git-workflows@local` | `git-workflows@xopoko-plug-n-skills` | Bind eligible GitHub/GitLab access, review code and feedback, deliver stacked changes, and recover worktrees or signed commits with fail-closed proof. |
| `engineering-hygiene` | `engineering-hygiene@local` | `engineering-hygiene@xopoko-plug-n-skills` | Audit changed code, untangle business logic, inspect rendered UI, and provision missing tools. |
| `scientific-research` | `scientific-research@local` | `scientific-research@xopoko-plug-n-skills` | Discover scholarly sources, deduplicate papers, extract claims, and validate evidence. |
| `technology-intelligence` | `technology-intelligence@local` | `technology-intelligence@xopoko-plug-n-skills` | Compare technology adoption, trial, replacement, and delivery-mode options through dated evidence and explicit decision profiles. |
| `design-intelligence` | `design-intelligence@local` | `design-intelligence@xopoko-plug-n-skills` | Frame and critique product/UX architecture, interaction, accessibility, visual communication, and design systems. |
| `architecture-intelligence` | `architecture-intelligence@local` | `architecture-intelligence@xopoko-plug-n-skills` | Audit and evolve software architecture, topology, async state consistency, conformance, ADRs, and refactoring. |
| `spec-driven-development` | `spec-driven-development@local` | `spec-driven-development@xopoko-plug-n-skills` | Specify, plan, implement, and audit traceable Spec-Driven Development work. |
| `build-swift-apps` | `build-swift-apps@local` | `build-swift-apps@xopoko-plug-n-skills` | Build, debug, profile, test, refactor, and release Swift apps across Apple platforms. |
| `kotlin-multiplatform` | `kotlin-multiplatform@local` | `kotlin-multiplatform@xopoko-plug-n-skills` | Design, build, diagnose, test, secure, publish, and release Kotlin Multiplatform systems. |
| `tauri` | `tauri@local` | `tauri@xopoko-plug-n-skills` | Build, secure, debug, test, package, and release Tauri 2 desktop/mobile apps. |
| `pixijs` | `pixijs@local` | `pixijs@xopoko-plug-n-skills` | Build and debug PixiJS v8 applications, scenes, assets, events, filters, performance, and migrations. |
| `game-design-intelligence` | `game-design-intelligence@local` | `game-design-intelligence@xopoko-plug-n-skills` | Design and critique gameplay, progression, economy, retention, onboarding, and live service. |

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
