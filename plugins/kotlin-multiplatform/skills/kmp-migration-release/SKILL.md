---
name: kmp-migration-release
description: Plan and execute Kotlin Multiplatform migrations and release gates, including AGP 9 Android-KMP, monolithic composeApp splits, CocoaPods to SwiftPM, cinterop, iOS framework integration, CI, publishing, and app-store readiness.
---

# KMP Migration And Release

Use this skill for AGP 9+ migration, Android-KMP plugin adoption, splitting monolithic KMP modules, CocoaPods to SwiftPM, cinterop and iOS framework integration, CI, publishing, signing boundaries, and release readiness.

## Migration Discipline

1. Diagnose before editing.
2. Classify modules and pick the smallest reversible path.
3. Keep version upgrades separate from structural migrations unless the migration requires them.
4. Preserve existing behavior and package names unless the migration explicitly requires a move.
5. Validate after each phase.
6. Record commands, changed modules, and residual risks.

## AGP 9 Android-KMP Paths

Classify every module:

- Path A: `kotlin.multiplatform` plus `com.android.library`.
  - Migrate to `com.android.kotlin.multiplatform.library` when targeting AGP 9+.
  - Move Android config into `kotlin { android { ... } }`.
  - Move dependencies to source-set blocks.
  - Enable resources, Java, and Android tests explicitly only when used.
- Path B: `kotlin.multiplatform` plus `com.android.application`.
  - Split is mandatory for AGP 9+.
  - Create a pure `androidApp` module.
  - Convert the original module into a KMP library module.
  - Move `MainActivity`, app manifest, launcher resources, app ID, versioning, and Android app concerns to `androidApp`.
- Path C: monolithic `composeApp` with multiple platform entry points.
  - Recommended full restructure: shared library plus per-platform app modules.
  - Use only when it pays for itself or when AGP compatibility requires it.

## CocoaPods To SwiftPM

Use phase gates:

1. Confirm the current Kotlin/iOS build state when possible.
2. Inventory `cocoapods {}` blocks, `Podfile`, `import cocoapods.*`, framework names, deployment target, and Xcode build phases.
3. Add SwiftPM configuration alongside CocoaPods first.
4. Preserve dependency versions unless the user requested upgrades.
5. Transform imports only after confirming the generated namespace and bundled third-party klibs.
6. Reconfigure Xcode and embed/sign integration.
7. Remove CocoaPods only after Gradle and Xcode builds pass.
8. Produce a migration report.

Do not mix the same library suite across CocoaPods and SwiftPM during a migration; duplicate symbols and runtime linkage failures are common.

## iOS Framework And Interop

- Prefer static frameworks unless the project has a clear reason for dynamic frameworks.
- Keep exported Swift API small and stable.
- Verify `baseName`, package/group, deployment target, and architecture targets.
- For cinterop, check `.def` files, headers, linker options, transitive native dependencies, and simulator/device architecture.
- For Swift consumers, prefer a small facade around flows, callbacks, and Kotlin collections when direct exposure is awkward.

## CI And Release Gates

Suggested layers:

- PR fast path: metadata compile, common/JVM tests, lint/static checks.
- Android: assemble/test debug app or library artifact on Linux.
- iOS: simulator compile/link or `xcodebuild` on macOS.
- Desktop/Web: build entry-point artifacts if those platforms are in scope.
- Publishing/store steps: separate workflow with explicit secrets and signing material.

Never print or commit signing credentials. Use environment variables, platform keychains, CI secret stores, or existing repo mechanisms.

For KMP publishing details, route to `kmp-publishing-ci`. For broad release readiness, route to `kmp-production-readiness`.
