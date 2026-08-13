# Plugin Source Index

This directory contains the source bundles authored directly in this repository.
Each local plugin is self-contained enough to validate and install, but
the repository root owns the shared marketplace, validation, and publication
workflow. A synchronized clone is the canonical editable source on every host;
global skill folders, marketplaces, and runtime caches are derived install
surfaces and must be refreshed from this tree rather than edited directly.

## Plugin Catalog

| Directory | Codex id | Claude marketplace id | Focus |
| --- | --- | --- | --- |
| `agent-harness` | `agent-harness@local` | `agent-harness@xopoko-plug-n-skills` | Design and evaluate agent harnesses; operate Codex and Claude runtimes, hand credentials from an operator or 1Password directly to target processes, and manage automation, diagnostics, MCP, sessions, and local schedulers. |
| `capability-workbench` | `capability-workbench@local` | `capability-workbench@xopoko-plug-n-skills` | Engineer reliable agent skills, plugins, guidance, trigger contracts, evaluations, and capability portfolios. |
| `context-density` | `context-density@local` | `context-density@xopoko-plug-n-skills` | Audit agent context cost, prompt contracts, typed state, compression, and structural overlap. |
| `git-workflows` | `git-workflows@local` | `git-workflows@xopoko-plug-n-skills` | Bind eligible GitHub/GitLab access, review code and feedback, deliver stacked changes, and recover worktrees or signed commits with fail-closed proof. |
| `engineering-hygiene` | `engineering-hygiene@local` | `engineering-hygiene@xopoko-plug-n-skills` | Audit changed code, untangle business logic, inspect rendered UI, and provision missing tools. |
| `scientific-research` | `scientific-research@local` | `scientific-research@xopoko-plug-n-skills` | Discover scholarly sources, deduplicate papers, extract claims, and validate evidence. |
| `technology-intelligence` | `technology-intelligence@local` | `technology-intelligence@xopoko-plug-n-skills` | Map capabilities to candidate technologies and documented interfaces through dated evidence, explicit profiles, and separate runtime facts. |
| `design-intelligence` | `design-intelligence@local` | `design-intelligence@xopoko-plug-n-skills` | Frame and critique product/UX architecture, interaction, accessibility, visual communication, and design systems. |
| `architecture-intelligence` | `architecture-intelligence@local` | `architecture-intelligence@xopoko-plug-n-skills` | Audit and evolve software architecture with AI-assisted code recovery, design, refactoring, topology, async state consistency, conformance, ADRs, and fitness proof. |
| `spec-driven-development` | `spec-driven-development@local` | `spec-driven-development@xopoko-plug-n-skills` | Specify, plan, implement, and audit traceable Spec-Driven Development work. |
| `kotlin-multiplatform` | `kotlin-multiplatform@local` | `kotlin-multiplatform@xopoko-plug-n-skills` | Design, build, diagnose, test, secure, publish, and release Kotlin Multiplatform systems. |
| `tauri` | `tauri@local` | `tauri@xopoko-plug-n-skills` | Build, secure, debug, test, package, and release Tauri 2 desktop/mobile apps. |
| `pixijs` | `pixijs@local` | `pixijs@xopoko-plug-n-skills` | Build and debug PixiJS v8 applications, scenes, assets, events, filters, performance, and migrations. |
| `game-design-intelligence` | `game-design-intelligence@local` | `game-design-intelligence@xopoko-plug-n-skills` | Design and critique gameplay, progression, economy, retention, onboarding, and live service. |

## Standalone First-Party Plugins

Large focused systems are maintained in their own canonical repositories and
are published here through immutable entries in `first-party-plugins.lock.json`.
They are not duplicated under `plugins/`.

| Plugin | Canonical repository | Codex id | Claude marketplace id |
| --- | --- | --- | --- |
| `build-swift-apps` | [Xopoko/build-swift-apps](https://github.com/Xopoko/build-swift-apps) | `build-swift-apps@local` | `build-swift-apps@xopoko-plug-n-skills` |
| `career` | [Xopoko/career-skills](https://github.com/Xopoko/career-skills) | `career@local` | `career@xopoko-plug-n-skills` |

See [Standalone First-Party Plugins](../docs/STANDALONE_PLUGINS.md) for pin,
receipt, offline-cache, and installer rules.

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
