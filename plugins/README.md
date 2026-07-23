# Plugin Source Index

This directory contains the source bundles for every plugin pack published by this
repository. Each plugin is self-contained enough to validate and install, but
the repository root owns the shared marketplace, validation, and publication
workflow.

## Plugin Catalog

| Directory | Codex id | Claude marketplace id | Focus |
| --- | --- | --- | --- |
| `build-swift-apps` | `build-swift-apps@local` | `build-swift-apps@xopoko-plug-n-skills` | Swift, iOS, macOS, Xcode, SwiftUI, App Store, TestFlight, profiling, and release workflows. |
| `pixijs` | `pixijs@local` | `pixijs@xopoko-plug-n-skills` | PixiJS v8 application, rendering, scene graph, assets, events, filters, migration, and performance workflows. |
| `tauri` | `tauri@local` | `tauri@xopoko-plug-n-skills` | Tauri 2 setup, migration, security, IPC, plugins, shell UI, debug/test, and distribution workflows. |
| `scientific-research` | `scientific-research@local` | `scientific-research@xopoko-plug-n-skills` | Scholarly discovery, deduplication, claim ledgers, source quality, and provenance gates. |
| `context-density` | `context-density@local` | `context-density@xopoko-plug-n-skills` | Context design, long-context placement, research-backed acceptance gates, skill compression, prompt contracts, structural handoff, and validation reporting. |
| `capability-workbench` | `capability-workbench@local` | `capability-workbench@xopoko-plug-n-skills` | Capability discovery, synthesis, cross-plugin portfolio architecture, agent guidance files, skill trigger metadata, vetting, repair, plugin packaging, imagegen-backed plugin icon workflows, install-scope, and visibility checks. |
| `codex-cli` | `codex-cli@local` | `codex-cli@xopoko-plug-n-skills` | Codex CLI operations, exec/review automation, live thread supervision, controlled skill handoffs and evidence corrections, doctor/debug/sandbox diagnostics, plugin and MCP lifecycle, normalized session trace audits, and local environment actions. |
| `scheduled-automation` | `scheduled-automation@local` | `scheduled-automation@xopoko-plug-n-skills` | Local launchd, systemd timer, cron, and Windows Task Scheduler diagnostics with native-trigger proof, safe canaries, correlated receipts, and rollback-aware repair. |
| `gitlab-review` | `gitlab-review@local` | `gitlab-review@xopoko-plug-n-skills` | Race-safe GitLab merge request review response, reviewer-owned resolution, idempotent thread replies, and exact-head handoff proof. |
| `claude-code` | `claude-code@local` | `claude-code@xopoko-plug-n-skills` | Claude Code CLI operations, print-mode automation, diagnostics, plugin and MCP lifecycle, hooks, settings, agents, sessions, and worktrees. |
| `architecture-intelligence` | `architecture-intelligence@local` | `architecture-intelligence@xopoko-plug-n-skills` | Codebase architecture audits, ownership topology, runtime topology, conformance/drift checks, structure metrics, module boundaries, ADRs, fitness functions, and refactoring strategy. |
| `design-intelligence` | `design-intelligence@local` | `design-intelligence@xopoko-plug-n-skills` | Product judgment, interface architecture, interaction design, visual hierarchy, usability, accessibility, and design systems. |
| `game-design-intelligence` | `game-design-intelligence@local` | `game-design-intelligence@xopoko-plug-n-skills` | Gameplay loops, systems, progression, economy, retention, onboarding, difficulty, and live-service critique. |
| `kotlin-multiplatform` | `kotlin-multiplatform@local` | `kotlin-multiplatform@xopoko-plug-n-skills` | KMP architecture, Gradle diagnosis, Compose Multiplatform, iOS interop, testing, security, publishing, and readiness. |
| `spec-driven-development` | `spec-driven-development@local` | `spec-driven-development@xopoko-plug-n-skills` | SDD lane selection, Spec Kit integration, requirements quality, traceability, implementation, and proof gates. |

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
