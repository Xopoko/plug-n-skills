---
name: kmp-gradle-doctor
description: Diagnose and fix Kotlin Multiplatform Gradle, source-set, dependency, Android target, Compose plugin, KGP/AGP, testing, static-analysis, and CI issues.
---

# KMP Gradle Doctor

Use this skill for KMP build failures, Gradle DSL changes, plugin version alignment, target declarations, source-set hierarchy, Android-KMP plugin migration, dependency placement, KSP/KAPT, detekt/ktlint, Compose compiler, CI, or test task selection.

## Diagnosis Flow

1. Read the build surface:
   - `settings.gradle(.kts)`
   - root and module `build.gradle(.kts)`
   - `gradle/libs.versions.toml`
   - `gradle.properties`
   - `gradle/wrapper/gradle-wrapper.properties`
2. Run:
   ```bash
   python3 ../../scripts/kmp_inspector.py --root <project-root>
   ```
3. Classify each module:
   - KMP library
   - Android app shell
   - pure Android library
   - iOS Xcode app
   - desktop/web/server app
   - convention plugin or build logic
4. Identify the smallest failing task. Avoid `clean` unless cache state is the suspected issue.
5. Verify current DSL or version-sensitive guidance from official docs before editing.
6. If the failure looks host-specific on macOS/iOS, separate project diagnosis from environment diagnosis. Use `kdoctor` only when installed or explicitly approved to install; its scope is host/toolchain readiness.

## Environment Triage

Use project static inspection first. Then consider host diagnostics when symptoms include Xcode selection, CocoaPods/Ruby, Android Studio plugin, JDK/JAVA_HOME, simulator, or iOS Gradle task failures unrelated to source changes.

Useful checks:

```bash
xcode-select -p
xcodebuild -version
java -version
./gradlew -version
kdoctor -v
```

Do not install or update KDoctor, CocoaPods, Ruby, Xcode, Android Studio, JDKs, or SDK tools unless the user explicitly asked for environment setup.

## Build Governance

For medium or large KMP projects, inspect whether repeated configuration is centralized:

- Prefer `build-logic/` as an included build or `buildSrc/` for convention plugins when many modules repeat setup.
- Prefer version catalogs for plugin and dependency coordinates.
- Prefer centralized `pluginManagement` and `dependencyResolutionManagement` in settings.
- Avoid ad hoc repositories in module build files.
- Keep stack-specific choices, such as DI, database, obfuscation, codegen, and publishing, opt-in by module role.

## Source-Set Rules

- Prefer the default hierarchy template when the target combination is covered.
- Manual `dependsOn()` edges can disable the default hierarchy template; if the repo has manual edges, keep them only when they model a real non-default sharing need.
- Declare targets before referencing their source sets.
- Dependencies belong in the narrowest valid source set:
  - shared and target-published libraries: `commonMain`
  - Android-only artifacts: `androidMain`
  - iOS-only bindings: `iosMain` or the exact native source set
  - JVM/Desktop-only artifacts: `jvmMain` or a named desktop source set
- Before moving anything to `commonMain`, verify all configured targets publish the artifact.

## Android-KMP Rules

For KMP library modules targeting Android on modern AGP:

- Prefer `com.android.kotlin.multiplatform.library`.
- Keep Android configuration under `kotlin { android { ... } }`.
- Do not use a top-level `android {}` block in a module that has moved to the Android-KMP library plugin.
- Remember the Android-KMP library plugin is single-variant: no `buildTypes` or `productFlavors` in that module.
- Enable only what is used:
  - `androidResources { enable = true }` if Android resources or Compose resources need Android resource processing.
  - `withJava()` if Java source files exist.
  - host/device test builders if Android tests exist.
  - `localDependencySelection` when consuming variant-rich Android libraries.
- For Compose preview tooling on Android-KMP library modules, verify the current workaround before using debug-only configurations.

## Build And Test Commands

Prefer the narrowest proof:

```bash
./gradlew :shared:compileKotlinMetadata
./gradlew :shared:compileKotlinIosSimulatorArm64
./gradlew :shared:jvmTest
./gradlew :shared:allTests
./gradlew :androidApp:assembleDebug
./gradlew :desktopApp:run
```

Task names vary by module and target. Use `./gradlew :module:tasks --all` when uncertain.

## Static Analysis

- detekt needs explicit inputs/config for KMP source sets in many setups; do not assume root `detekt` checks all `commonMain`, `iosMain`, and `androidMain` code.
- Type-resolution analysis can explode runtime in large KMP monorepos. Prefer scoped tasks and avoid enabling all Android variants unless required.
- KSP must match Kotlin versions. Verify compatibility before bumping KGP or KSP.
- KAPT is a migration risk in modern Android/KMP projects; prefer KSP or isolate legacy processors.
- If a KMP library is published, check whether Kotlin ABI validation is configured or intentionally skipped.
- If a module exposes many `api(...)` dependencies, review whether the public surface is broader than needed.

## CI Pattern

- Split jobs by cost and platform: common/JVM tests first on Linux; Android builds on Linux; iOS simulator and Apple framework checks on macOS.
- Use the official Gradle setup action and one shared Java/Gradle setup path.
- Upload test reports and platform artifacts.
- Keep signing, notarization, and store publishing separate from ordinary PR validation.
