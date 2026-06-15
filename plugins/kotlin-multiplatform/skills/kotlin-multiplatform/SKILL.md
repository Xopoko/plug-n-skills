---
name: kotlin-multiplatform
description: Route and execute Kotlin Multiplatform tasks across architecture, Gradle diagnosis, Compose Multiplatform UI, Android-KMP migration, iOS interop, CocoaPods or SwiftPM migration, testing, performance, security, CI, publishing, and production readiness.
---

# Kotlin Multiplatform Router

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use this skill when the task mentions Kotlin Multiplatform, KMP, KMM, Compose Multiplatform, CMP, Android-KMP, Kotlin/Native, cinterop, Gradle KMP source sets, shared iOS/Android logic, `commonMain`, `iosMain`, `androidMain`, `com.android.kotlin.multiplatform.library`, CocoaPods, or SwiftPM in a Kotlin project.

## First Move

For an existing repository, read the local project before answering:

1. Inspect `settings.gradle(.kts)`, root `build.gradle(.kts)`, module build files, `gradle/libs.versions.toml`, `gradle.properties`, and `gradle/wrapper/gradle-wrapper.properties`.
2. Run the offline inspector when available:
   ```bash
   python3 "$PLUGIN_ROOT/scripts/kmp_inspector.py" --root <project-root> --json
   ```
3. Treat the inspector as a triage aid, not a substitute for reading relevant files.
4. For dependency coordinates, Gradle DSL, plugin versions, platform target support, or migration rules that may have changed, verify against current official docs. Prefer Context7 for Kotlin, Compose, Ktor, SQLDelight, Android Gradle Plugin, and related libraries when available.

## Routing

- Build failure, Gradle DSL, source sets, Android target, KGP/AGP/Compose plugin, dependency placement, static analysis, or CI: use `kmp-gradle-doctor`.
- Build governance, convention plugins, build logic, version catalogs, repository policy, module dependency hygiene, library release readiness, ABI, Klibs, or production adoption risk: use `kmp-production-governance`.
- Production readiness verdicts, readiness scorecards, executive risk summaries, release-blocker triage, or multi-area audits: use `kmp-production-readiness`.
- Module boundaries, shared logic/shared UI split, domain/data/presentation architecture, source-set hierarchy, library choice, or Swift/Native API boundaries: use `kmp-architecture`.
- Shared-to-platform bridges, `expect`/`actual`, cinterop, Swift API shape, SKIE, KMP-NativeCoroutines, SwiftPM export, XCFrameworks, KDoctor, or iOS developer experience: use `kmp-interop-bridges`.
- Compose Multiplatform screens, state, resources, navigation, platform entry points, previews, performance, or accessibility: use `kmp-compose-ui`.
- KMP data layers, repositories, source of truth, sync, offline-first, database choice, DTO/domain mapping, cache invalidation, or main-safety: use `kmp-data-layer`.
- Library/tool/service selection across persistence, networking, DI, navigation, logging, observability, code quality, docs, resources, images, monetization, or reference templates: use `kmp-ecosystem-selection`.
- KMP test strategy, `commonTest`, `kotlin.test`, Compose UI tests, screenshot tests, test doubles, refactor safety, review gates, or regression harnesses: use `kmp-testing-quality`.
- Performance, observability, Compose jank, Kotlin/Native memory, GC logs, binary size, Gradle build time, Compose compiler metrics, baseline profiles, or release-mode measurement: use `kmp-performance-observability`.
- Secrets, tokens, secure storage, privacy, logging redaction, Ktor auth, TLS/certificate pinning, runtime app protection, or platform security boundaries: use `kmp-security-privacy`.
- Maven publishing, Gradle metadata, XCFramework, SwiftPM export, KMMBridge, CI matrices, artifact signing boundaries, app-store build gates, or release automation: use `kmp-publishing-ci`.
- AGP 9+, `com.android.kotlin.multiplatform.library`, monolithic `composeApp`, CocoaPods to SwiftPM, cinterop, iOS framework integration, CI, release, publishing, or store builds: use `kmp-migration-release`.

If several apply, start with diagnosis, then architecture, then implementation, then validation.

## Operating Rules

- Preserve the repo's existing coherent architecture. Do not force MVI, Clean Architecture, Compose shared UI, Koin, Ktor, Room, SQLDelight, or Decompose if the project already has a different working pattern.
- Do not add dependencies to `commonMain` until target support is verified for every configured target.
- Treat ecosystem libraries as choices with costs. Do not prescribe Koin, Ktor, Room, SQLDelight, DataStore, Decompose, Voyager, Kermit, Napier, Datadog, Bugsnag, Sentry, RevenueCat, Coil, Moko, Detekt, Kover, Dokka, Fastlane, or Amper unless the project need and target support justify them.
- Prefer the 2026 KMP default shape for new work: shared KMP library module plus thin per-platform app modules. Use `sharedLogic` and `sharedUI` when some platforms use native UI.
- For AGP 9+ KMP library modules, prefer `com.android.kotlin.multiplatform.library` and configure Android inside `kotlin { android { ... } }`.
- Do not combine `com.android.application` with `org.jetbrains.kotlin.multiplatform` in one module for AGP 9+ work.
- For performance work, measure first, diagnose second, change narrowly, then verify in release-like conditions.
- Keep secrets and token material out of common code and logs. Use common interfaces with platform-backed implementations.
- Do not run destructive cleanup, broad dependency upgrades, signing, publishing, or store upload steps without an explicit user request.
- Never put secrets, keystore material, App Store credentials, tokens, or private provisioning data into generated examples.
- Treat optional ecosystem tools as gated choices:
  - `kdoctor` diagnoses macOS KMP mobile environment readiness; it does not replace project static inspection.
  - SKIE or KMP-NativeCoroutines can improve Swift API ergonomics; do not add them without verifying project needs and current docs.
  - Klibs.io can help verify library target support; do not treat it as a lockfile or automated source of truth.
  - ABI validation is for published libraries; do not force it on private app-only modules.

## Completion Standard

A KMP task is not done until there is proof appropriate to the change:

- Static diagnosis: inspector output plus file references.
- Gradle/build config change: the smallest relevant Gradle task succeeds, or the blocker is reported with exact command and error.
- Shared code change: common tests or metadata compile succeeds where available.
- Android change: Android compile/assemble/test task succeeds where available.
- iOS/Native change: `compileKotlinIosSimulatorArm64`, link task, or `xcodebuild` simulator build succeeds where available.
- Compose UI change: screenshot or platform run when practical, plus tests for state logic when changed.
- Migration/release change: before/after module classification, changed files, and rollback-safe validation commands.
- Published library change: API/ABI gate such as `checkKotlinAbi` when configured, publication dry run where available, and target matrix evidence for all published variants.
- Production readiness audit: inspector readiness areas, risk verdict, release blockers, exact commands, and explicit deferred checks.
- Performance/security audit: measured or inspectable evidence, redaction/platform-boundary review, and no dependency/tooling addition without project fit.
