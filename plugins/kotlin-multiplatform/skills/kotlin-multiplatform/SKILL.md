---
name: kotlin-multiplatform
description: Route and execute Kotlin Multiplatform tasks across architecture, Gradle diagnosis, Compose Multiplatform UI, Android-KMP migration, iOS interop, CocoaPods or SwiftPM migration, testing, performance, security, CI, publishing, and production readiness.
---

# Kotlin Multiplatform Router

Bundled commands use `$PLUGIN_ROOT`: set it once from the host plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise this plugin root's absolute path. Works under any host agent, including Codex/Claude/Cursor.

Use for Kotlin tasks mentioning Kotlin Multiplatform/KMP/KMM, Compose Multiplatform/CMP, Android-KMP, Kotlin/Native, cinterop, Gradle KMP source sets, shared iOS/Android logic, `commonMain`/`iosMain`/`androidMain`/`com.android.kotlin.multiplatform.library`, CocoaPods, or SwiftPM.

Skill-directory plugin root: `../..`.

## First Move

Existing repository: read before answering:

1. Inspect `settings.gradle(.kts)`, root `build.gradle(.kts)`, module build files, `gradle/libs.versions.toml`, `gradle.properties`, `gradle/wrapper/gradle-wrapper.properties`.
2. Run the offline inspector when available:
   ```bash
   python3 "$PLUGIN_ROOT/scripts/kmp_inspector.py" --root <project-root> --json
   ```
3. Use the inspector for triage only; read relevant files yourself.
4. For dependency coordinates, Gradle DSL, plugin versions, platform target support, or migration rules that may have changed, verify current official docs. Prefer Context7 for Kotlin/Compose/Ktor/SQLDelight/Android Gradle Plugin and related libraries when available.

## Routing

Use the matching skill:

- `kmp-gradle-doctor`: build failures/Gradle DSL/source sets/Android target/KGP/AGP/Compose plugin/dependency placement/static analysis/CI.
- `kmp-production-governance`: build governance/convention plugins/build logic/version catalogs/repository policy/module dependency hygiene/library release readiness/ABI/Klibs/production adoption risk.
- `kmp-production-readiness`: production readiness verdicts/scorecards/executive risk summaries/release-blocker triage/multi-area audits.
- `kmp-architecture`: module boundaries/shared logic/shared UI split/domain/data/presentation architecture/source-set hierarchy/library choice/Swift/Native API boundaries.
- `kmp-interop-bridges`: shared-to-platform bridges/`expect`/`actual`/cinterop/Swift API shape/SKIE/KMP-NativeCoroutines/SwiftPM export/XCFrameworks/KDoctor/iOS developer experience.
- `kmp-compose-ui`: Compose Multiplatform screens/state/resources/navigation/platform entry points/previews/performance/accessibility.
- `kmp-data-layer`: KMP data layers/repositories/source-of-truth/sync/offline-first/database choice/DTO/domain mapping/cache invalidation/main-safety.
- `kmp-ecosystem-selection`: library/tool/service selection across persistence/networking/DI/navigation/logging/observability/code quality/docs/resources/images/monetization/reference templates.
- `kmp-testing-quality`: KMP test strategy/`commonTest`/`kotlin.test`/Compose UI tests/screenshot tests/test doubles/refactor safety/review gates/regression harnesses.
- `kmp-performance-observability`: performance/observability/Compose jank/Kotlin/Native memory/GC logs/binary size/Gradle build time/Compose compiler metrics/baseline profiles/release-mode measurement.
- `kmp-security-privacy`: secrets/tokens/secure storage/privacy/logging redaction/Ktor auth/TLS/certificate pinning/runtime app protection/platform security boundaries.
- `kmp-publishing-ci`: Maven publishing/Gradle metadata/XCFramework/SwiftPM export/KMMBridge/CI matrices/artifact signing boundaries/app-store build gates/release automation.
- `kmp-migration-release`: AGP 9+/`com.android.kotlin.multiplatform.library`/monolithic `composeApp`/CocoaPods to SwiftPM/cinterop/iOS framework integration/CI/release/publishing/store builds.

If several apply, start with diagnosis, then architecture, then implementation, then validation.

## Operating Rules

- Preserve the repo's coherent architecture. Do not force MVI/Clean Architecture/Compose shared UI/Koin/Ktor/Room/SQLDelight/Decompose over the project's working pattern.
- Do not add dependencies to `commonMain` until every configured target has verified support.
- Treat ecosystem libraries as costly choices; do not prescribe Koin/Ktor/Room/SQLDelight/DataStore/Decompose/Voyager/Kermit/Napier/Datadog/Bugsnag/Sentry/RevenueCat/Coil/Moko/Detekt/Kover/Dokka/Fastlane/Amper without justified project need and target support.
- Prefer the 2026 KMP default for new work: shared KMP library module plus thin per-platform app modules. Use `sharedLogic` and `sharedUI` when some platforms use native UI.
- For AGP 9+ KMP library modules, prefer `com.android.kotlin.multiplatform.library`; configure Android inside `kotlin { android { ... } }`.
- Do not combine `com.android.application` with `org.jetbrains.kotlin.multiplatform` in one module for AGP 9+ work.
- For performance work, measure first, diagnose second, change narrowly, and verify in release-like conditions.
- Keep secrets and token material out of common code and logs; use common interfaces with platform-backed implementations.
- Do not run destructive cleanup/broad dependency upgrades/signing/publishing/store upload steps without explicit user request.
- Never put secrets/keystore material/App Store credentials/tokens/private provisioning data in examples.
- Treat optional ecosystem tools as gated choices:
  - `kdoctor` diagnoses macOS KMP mobile readiness; it does not replace static project inspection.
  - SKIE or KMP-NativeCoroutines can improve Swift API ergonomics; do not add them without verifying project needs and current docs.
  - Klibs.io can help verify library target support; do not treat it as a lockfile or automated source of truth.
  - ABI validation is for published libraries; do not force it on private app-only modules.

## Completion Standard

A KMP task is not done until proof matches the change:

- Static diagnosis: inspector output plus file references.
- Gradle/build config: smallest relevant Gradle task succeeds; blocker has exact command and error.
- Shared code: common tests or metadata compile succeeds if available.
- Android: Android compile/assemble/test task succeeds if available.
- iOS/Native: `compileKotlinIosSimulatorArm64`, link task, or `xcodebuild` simulator build succeeds if available.
- Compose UI: screenshot or platform run when practical, plus tests for changed state logic.
- Migration/release: before/after module classification, changed files, rollback-safe validation commands.
- Published library: API/ABI gate such as `checkKotlinAbi` when configured, publication dry run if available, target matrix evidence for all published variants.
- Production readiness audit: inspector readiness areas, risk verdict, release blockers, exact commands, explicit deferred checks.
- Performance/security audit: measured/inspectable evidence, redaction/platform-boundary review, no dependency/tooling addition without project fit.
