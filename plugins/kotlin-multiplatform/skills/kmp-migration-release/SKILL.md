---
name: kmp-migration-release
description: KMP migration and release execution for AGP 9 Android-KMP adoption, monolithic composeApp splits, CocoaPods-to-SwiftPM dependency-import moves, cinterop, iOS frameworks, CI, publishing, and app-store readiness.
---

# KMP Migration And Release

Use for AGP 9+ migration, Android-KMP plugin adoption, monolithic KMP module splits, CocoaPods to SwiftPM dependency import, cinterop and iOS framework integration, CI, publishing, signing boundaries, and release readiness.

## Migration Discipline

1. Diagnose before edits.
2. Classify modules; choose the smallest reversible path.
3. Separate version upgrades from structural migrations unless the migration requires them.
4. Preserve existing behavior and package names unless the migration explicitly requires a move.
5. Validate after each phase.
6. Record commands, changed modules, residual risks.

## AGP 9 Android-KMP Paths

Classify every module:

- Path A: `kotlin.multiplatform` + `com.android.library`.
  - For AGP 9+, migrate to `com.android.kotlin.multiplatform.library`.
  - Move Android config into `kotlin { android { ... } }`.
  - Move dependencies to source-set blocks.
  - Explicitly enable resources, Java, and Android tests only when used.
- Path B: `kotlin.multiplatform` + `com.android.application`.
  - AGP 9+ requires split.
  - Create pure `androidApp` module.
  - Convert the original module to a KMP library module.
  - Move `MainActivity`, app manifest, launcher resources, app ID, versioning, Android app concerns to `androidApp`.
- Path C: monolithic `composeApp` with multiple platform entry points.
  - Recommended full restructure: shared library + per-platform app modules.
  - Use only when it pays for itself or when AGP compatibility requires it.

## CocoaPods To SwiftPM

Treat `swiftPMDependencies {}` as dependency import, not KMP framework export.
The official integration is Alpha and may require a prerelease KGP, so confirm
that the project accepts that stability boundary and verify the project-pinned
KGP against the current official import guide before editing. Exporting a KMP
module that uses SwiftPM import as a Swift package is not currently supported;
keep any XCFramework/Swift-package delivery path separate and prove it.

Use phase gates:

1. Confirm current Kotlin/iOS build state when possible.
2. Confirm the current official `swiftPMDependencies` KGP requirement and Alpha constraints.
3. Inventory `cocoapods {}` blocks, `Podfile`, `import cocoapods.*`, framework names, deployment target, and Xcode build phases.
4. Add SwiftPM dependency-import configuration alongside CocoaPods first.
5. Preserve dependency versions unless the user requested upgrades.
6. Set an explicit Gradle `group`, verify the generated `swiftPMImport.<group>.<project>` namespace, and commit the generated `.swiftpm-locks`/`Package.resolved` state.
7. Move `cocoapods.framework {}` settings to `binaries.framework {}` and reconfigure Xcode direct integration with the generated integration task.
8. Transform imports only after confirming the generated namespace and bundled third-party klibs.
9. Build Kotlin and Xcode on the affected targets.
10. Remove CocoaPods only after Gradle and Xcode builds pass.
11. Produce a migration report with the accepted Alpha and export limitations.

The official transition temporarily declares the same dependency through both
CocoaPods and SwiftPM while imports move. Keep that overlap bounded to the
migration phase; do not treat a dual-linked release as complete, and remove the
old CocoaPods path only after the SwiftPM-backed Kotlin and Xcode builds pass.

Current primary references:

- [SwiftPM dependency import](https://kotlinlang.org/docs/multiplatform/multiplatform-spm-import.html)
- [CocoaPods-to-SwiftPM migration](https://kotlinlang.org/docs/multiplatform/multiplatform-cocoapods-spm-migration.html)

## iOS Framework And Interop

- Prefer static frameworks unless clear project reason exists for dynamic frameworks.
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
- Publishing/store: separate workflow with explicit secrets and signing material.

- Never print or commit signing credentials.
- Use environment variables, platform keychains, CI secret stores, or existing repo mechanisms.

- Route KMP publishing details to `kmp-publishing-ci`.
- Route broad release readiness to `kmp-production-readiness`.
