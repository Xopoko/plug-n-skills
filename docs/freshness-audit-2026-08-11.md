# Plugin Freshness Audit - 2026-08-11

## Outcome

This audit reviewed the full repository plugin portfolio as of 2026-08-11:

- 15 plugin packages;
- 176 `SKILL.md` entrypoints;
- 717 tracked plugin paths;
- 577 unique URL literals triaged for mutable claims;
- 10 plugins repaired and patch-versioned;
- 5 plugins verified without a new audit-owned source change.

The source snapshot is based on Git head
`2648633dd68fa6ca1403c30ad8ef78f8f0997ece` plus working-tree repairs. The
audited plugin/shared-code diff, including three pre-existing untracked
architecture-intelligence files, is bound to SHA-256
`8ec63c1a4b8daa6126cb10961e1039ebc37af6adf5b82c6c67b50f5bd8d5fdaa`.

The binding uses this canonical PowerShell serialization from the repository
root. It intentionally excludes this report and its coverage ledger so the
receipt binds the reviewed source/code snapshot rather than itself:

```powershell
$scope = @(
  'plugins',
  'scripts',
  '.claude-plugin/marketplace.json',
  'AGENTS.md',
  'README.md',
  'docs/ARCHITECTURE.md'
)
$diff = (& git diff --binary -- $scope) -join "`n"
$untracked = @(
  & git ls-files --others --exclude-standard -- plugins scripts |
    Sort-Object
)
$extra = foreach ($path in $untracked) {
  "`n--UNTRACKED:$path--`n"
  [System.IO.File]::ReadAllText((Join-Path (Get-Location) $path))
}
$payload = $diff + ($extra -join '')
$bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
$sha = [System.Security.Cryptography.SHA256]::HashData($bytes)
[Convert]::ToHexString($sha).ToLowerInvariant()
```

The working tree already contained architecture-intelligence and shared
catalog/validator edits before this audit. They were preserved and reviewed,
not attributed to this freshness pass. No installed plugin cache, global
Codex/Claude/Cursor state, commit, stage, or push was created.

## Method

For each plugin, the audit:

1. inventoried manifests, skills, references, scripts, tests, and mutable URLs;
2. separated stable conceptual guidance from commands, schemas, paths,
   versions, lifecycle states, and platform support claims that can drift;
3. checked high-drift claims against current primary documentation, current
   upstream source, or the locally installed CLI when the runtime contract was
   the claim;
4. changed only claims with decisive evidence, preserving ambiguous statements
   as explicit residuals;
5. synchronized manifest versions and token tables when source changed;
6. ran plugin-local, repository, installer, and independent diff-review gates.

Primary evidence was preferred over release summaries or third-party tutorials.
The audit does not claim that every external URL was live-executed or that
platform-specific Apple tooling was run on Windows.

## Portfolio Disposition

| Plugin | Version | Disposition | Main result |
| --- | --- | --- | --- |
| `agent-harness` | 0.1.1 | Repaired | Current Codex root-option ordering, review cwd, sandbox flag, marketplace syntax, and prompt-array manifest contract. |
| `architecture-intelligence` | 0.1.11 | Verified, no audit-owned change | Existing 2026-08-11 AI-assisted architecture evidence and stable architecture contracts remained current. |
| `build-swift-apps` | 0.3.9 | Repaired | Current App Store locales/screenshots, Xcode modules, transitions, CocoaPods status, XcodeBuildMCP logs, ETTrace, App Intents, and SwiftPM contracts. |
| `capability-workbench` | 0.5.1 | Repaired | Current plugin schema, `openai.yaml`, skill roots, marketplace lifecycle, generator, validator, and cache-locator behavior. |
| `context-density` | 0.4.4 | Repaired | Current Codex skill roots and canonical prompt-caching references; platform-limited guard remains fail-closed. |
| `design-intelligence` | 0.1.2 | Verified, no change | WCAG 2.2 remains the current Recommendation and WCAG 3 remains a draft; no mutable recipe drift found. |
| `engineering-hygiene` | 0.1.1 | Verified, no change | Evidence-first maintenance contracts are version-neutral and current. |
| `game-design-intelligence` | 0.1.2 | Verified, no change | Frameworks remain explicitly framed as design lenses rather than mutable engine/tool claims. |
| `git-workflows` | 0.1.1 | Repaired | Prompt-array manifest contract and current exact-state Git/GitHub/GitLab guidance. |
| `kotlin-multiplatform` | 0.3.18 | Repaired | Current SwiftPM dependency-import migration, AGP/KGP gates, lock evidence, Apple URI, Windows path handling, and inspector schema v3. |
| `pixijs` | 0.1.3 | Repaired | Current create-pixi/Vite guidance, async bootstrap, and PixiJS v8 bitmap-font namespace. |
| `scientific-research` | 0.3.4 | Repaired | Canonical OpenCitations Meta v1 endpoint and matching user-agent version. |
| `spec-driven-development` | 0.2.5 | Repaired | Current Spec Kit stages and active-feature selection contract. |
| `tauri` | 0.1.4 | Repaired | Current config names, capability enablement semantics, JSON5 uncertainty handling, scaffolding, and WebDriver guidance. |
| `technology-intelligence` | 0.2.0 | Verified, policy hold | 23 technologies, 59 observations, 23 assessments, zero stale sources, and zero expired assessments; refresh policy correctly blocked automatic recommendation changes. |

## Material Repairs

### ChatGPT, Codex, and plugin packaging

- Treated `.codex-plugin/plugin.json` as the shared ChatGPT/Codex manifest.
- Converted remaining scalar `interface.defaultPrompt` values to non-empty
  arrays and added regression coverage.
- Required documented `./` component paths; accepted current hooks and MCP
  companion shapes; validated current `agents/openai.yaml` metadata bounds.
- Moved active user/repository skill guidance to `.agents/skills` while
  retaining `.codex/skills` and `$HOME/plugins` only as labeled legacy
  audit/provenance surfaces.
- Updated repository documentation to the native
  `codex plugin marketplace add/list` and `codex plugin add/remove`
  lifecycle.
- Made the repository installer delegate normal installs to the native CLI,
  while explicit marketplace/state paths remain deterministic manual recovery.
- Preserved manifest-version cache locators for current Codex CLI behavior.
  OpenAI's packaging page separately describes a literal `local` directory
  for ChatGPT desktop local installs, so the host distinction is documented
  rather than collapsed into one false path.

Primary evidence:

- https://developers.openai.com/plugins/build/plugins
- https://learn.chatgpt.com/docs/build-skills
- https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/store.rs
- https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/plugin-creator/references/installing-and-updating.md

### Swift and Apple delivery

- Added the 11 App Store locales introduced in 2026 and routed automation to
  live `asc localizations supported-locales` discovery.
- Corrected `asc` output from unconditional JSON to TTY-aware output and made
  automation request JSON explicitly.
- Replaced the old 6.5-inch screenshot anchor with the current 6.9-inch slot
  contract while retaining accepted fallback behavior and live size discovery.
- Corrected matched transitions to iOS 18, explicit modules to current Xcode
  settings/defaults, CocoaPods to maintenance mode, and SwiftPM package cycles
  to tools-version 6.0+ with target cycles still invalid.
- Replaced removed standalone XcodeBuildMCP log tools, updated ETTrace to the
  v1.1.x processed-node contract, repaired an App Intents URL, and aligned
  manifests/package metadata at 0.3.9.
- Extended the too-short `ios-simulator-browser` OpenAI metadata description
  after the final repository validator exposed the integration mismatch.

Primary evidence:

- https://developer.apple.com/help/app-store-connect/release-notes/
- https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications/
- https://developer.apple.com/documentation/xcode-release-notes/xcode-26-release-notes
- https://developer.apple.com/documentation/xcode/building-your-project-with-explicit-module-dependencies
- https://docs.swift.org/swiftpm/documentation/packagemanagerdocs/6.4/
- https://blog.cocoapods.org/CocoaPods-Support-Plans/
- https://www.xcodebuildmcp.com/docs/changelog
- https://github.com/EmergeTools/ETTrace/releases/tag/v1.1.1

### Kotlin, PixiJS, and Tauri

- Kotlin guidance now distinguishes SwiftPM dependency import from export,
  keeps bounded CocoaPods/SwiftPM overlap during migration, records the Alpha
  KGP gate and lock evidence, and exposes changed inspector vocabulary as
  schema v3 rather than silently breaking schema v2 consumers.
- Kotlin ZIP/path tests now exercise raw archive names and pass on Windows.
- PixiJS guidance removed an unsupported Vite cutoff, uses current async
  bootstrap, and references `text.BitmapFont` rather than the stale scene
  namespace.
- Tauri guidance recognizes `Tauri.toml` and current JSON/JSON5 config names,
  treats an empty capability list as automatic file enablement, reports
  unparsed JSON5 security mode as unknown instead of guessing, and updates
  scaffolding and WebDriver expectations.

Primary evidence:

- https://kotlinlang.org/docs/multiplatform/multiplatform-cocoapods-spm-migration.html
- https://kotlinlang.org/docs/multiplatform/swift-package-export.html
- https://pixijs.com/8.x/guides/components/scene-objects/text/bitmap
- https://v2.tauri.app/security/capabilities/
- https://v2.tauri.app/develop/tests/webdriver/

### Research, specifications, and maintained evidence

- Scientific Research now calls the canonical OpenCitations Meta v1 metadata
  endpoint instead of relying on the legacy redirect.
- Spec-Driven Development reflects current optional Spec Kit
  `clarify`, `checklist`, `taskstoissues`, and `converge` stages and the
  current active-feature file/override behavior.
- Technology Intelligence passed its own dated validation and staleness gates.
  Evidence-window gaps remain gaps, not authority to mutate assessments.

Primary evidence:

- https://api.opencitations.net/meta/v1
- https://github.com/github/spec-kit
- https://github.github.com/spec-kit/reference/core.html

## Deliberately Unchanged or Host-Limited

- Public Apple sources did not decisively prove screenshot-caption OCR
  indexing, the exact 24-48 hour crash-data lag, or one Task Backtraces floor;
  those statements were not rewritten speculatively.
- Full Xcode, Simulator, signing, and App Store runtime checks are unavailable
  on this Windows host. The Swift doctor reported those gaps explicitly.
- The screenshot crop helper passed Node syntax validation but was not executed
  because its optional `sharp` dependency is not installed.
- The context-density descriptor-relative state guard remains fail-closed on
  Windows; the platform limitation is documented rather than weakened.
- Technology Intelligence's evidence window contains coverage gaps, but no
  source or assessment was stale/expired on the audit date.

## Validation Receipts

- Repository validator: PASS.
- External dependency lock: PASS, 0 dependencies.
- Codex installer dry-run: PASS for all 15 plugins.
- Cursor installer dry-run: PASS for all 176 skills.
- Root unit suite: 146 passed, 2 expected skips.
- Agent Harness: 97 passed, 17 platform skips.
- Capability Workbench smoke: 127 passed, 0 failed.
- Git Workflows: 443 passed, 109 platform skips.
- Scientific Research: 31 passed.
- Kotlin Multiplatform: 42 passed.
- Tauri project-probe self-test: PASS.
- Technology Intelligence: 33 passed; validation, staleness, and evidence-window
  commands completed.
- Build Swift package/manifest/JSON/Python/Node/shell/token checks: PASS.
- Token table: current.
- Independent final diff review: CLEAN.

The machine-local install/visibility checks were intentionally not run because
the request authorized source freshness work, not global cache mutation.

## Next Review

Run a focused review when any of these occurs:

- Codex or ChatGPT changes plugin manifest, marketplace, cache, or skill-root
  contracts;
- Apple ships a new Xcode/App Store requirement cycle;
- Kotlin SwiftPM import leaves Alpha or changes its KGP gate;
- PixiJS or Tauri publishes a major version;
- Spec Kit changes command stages or active-feature state;
- Technology Intelligence reports stale sources or expired assessments.

Absent an event trigger, repeat the portfolio pass by 2026-11-11.
