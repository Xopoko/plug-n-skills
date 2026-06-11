---
name: kmp-gradle-doctor
description: Diagnose and fix Kotlin Multiplatform Gradle, source-set, dependency, Android target, Compose plugin, KGP/AGP, testing, static-analysis, and CI issues.
---

# KMP Gradle Doctor

Set `$PLUGIN_ROOT` once: host plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), else this plugin root's absolute path. Bundled commands use it. Works under any host agent, including Codex, Claude, and Cursor.

Use for KMP build failures; Gradle DSL changes; plugin version alignment; target declarations; source-set hierarchy; Android-KMP plugin migration; dependency placement; KSP/KAPT; detekt/ktlint; Compose compiler; CI; test task selection.

## Diagnosis Flow

1. Read:
   - `settings.gradle(.kts)`
   - root/module `build.gradle(.kts)`
   - `gradle/libs.versions.toml`
   - `gradle.properties`
   - `gradle/wrapper/gradle-wrapper.properties`
2. Run:
   ```bash
   python3 "$PLUGIN_ROOT/scripts/kmp_inspector.py" --root <project-root>
   ```
3. Classify modules:
   - KMP library
   - Android app shell
   - pure Android library
   - iOS Xcode app
   - desktop/web/server app
   - convention plugin or build logic
4. Find smallest failing task. Avoid `clean` unless cache state is suspected.
5. Check official docs for current DSL/version-sensitive guidance before edits.
6. If the failure looks host-specific on macOS/iOS, separate project diagnosis from environment diagnosis. Use `kdoctor` only if installed or explicitly approved to install; scope: host/toolchain readiness.

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

Do not install/update KDoctor, CocoaPods, Ruby, Xcode, Android Studio, JDKs, or SDK tools unless the user explicitly asked for environment setup.

## Build Governance

Medium/large KMP projects: inspect whether repeated configuration is centralized.

- Prefer included-build `build-logic/` or `buildSrc/` convention plugins when many modules repeat setup.
- Prefer version catalogs for plugin/dependency coordinates.
- Prefer central `pluginManagement` and `dependencyResolutionManagement` in settings.
- Avoid ad hoc repositories in module build files.
- Keep stack-specific choices (DI, database, obfuscation, codegen, publishing) opt-in by module role.

## Source-Set Rules

- Prefer default hierarchy template when the target combination is covered.
- Manual `dependsOn()` edges can disable the default hierarchy template; keep them only for real non-default sharing needs.
- Declare targets before source-set references.
- Place dependencies in narrowest valid source sets:
  - shared/target-published libraries: `commonMain`
  - Android-only artifacts: `androidMain`
  - iOS-only bindings: `iosMain` or exact native source set
  - JVM/Desktop-only artifacts: `jvmMain` or named desktop source set
- Before moving to `commonMain`, verify every configured target publishes the artifact.

## Android-KMP Rules

Android-targeting KMP library modules on modern AGP:

- Prefer `com.android.kotlin.multiplatform.library`.
- Keep Android config in `kotlin { android { ... } }`.
- Do not use a top-level `android {}` block after Android-KMP library plugin migration.
- Android-KMP library plugin is single-variant: no `buildTypes` or `productFlavors` in that module.
- Enable only used features:
  - `androidResources { enable = true }` if Android resources or Compose resources need Android resource processing.
  - `withJava()` for Java sources.
  - host/device test builders for Android tests.
  - `localDependencySelection` for variant-rich Android library consumption.
- For Compose preview tooling in Android-KMP library modules, verify current workaround before using debug-only configurations.

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

Task names vary by module/target; use `./gradlew :module:tasks --all` when uncertain.

## Static Analysis

- detekt often needs explicit KMP source-set inputs/config; do not assume root `detekt` checks all `commonMain`, `iosMain`, and `androidMain` code.
- Type-resolution can explode runtime in large KMP monorepos; prefer scoped tasks; avoid enabling all Android variants unless required.
- KSP must match Kotlin versions; verify compatibility before bumping KGP or KSP.
- KAPT is modern Android/KMP migration risk; prefer KSP or isolate legacy processors.
- For published KMP libraries, check whether Kotlin ABI validation is configured or intentionally skipped.
- If a module exposes many `api(...)` dependencies, review whether public surface is too broad.

## CI Pattern

- Split jobs by cost/platform: common/JVM tests first on Linux; Android builds on Linux; iOS simulator/Apple framework checks on macOS.
- Use official Gradle setup action and one shared Java/Gradle setup path.
- Upload test reports/platform artifacts.
- Keep signing, notarization, and store publishing separate from ordinary PR validation.
