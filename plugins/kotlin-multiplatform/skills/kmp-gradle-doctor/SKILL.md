---
name: kmp-gradle-doctor
description: "KMP Gradle diagnosis and repair for source sets, dependency failures including private dependency resolution or consumption failures, Android targets, Compose, KGP/AGP, tests, static analysis, and CI."
---

# KMP Gradle Doctor

Set `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) once: host plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), else this plugin root's absolute path. Bundled commands use it.

Use for KMP build failures; Gradle DSL changes; plugin version alignment; target declarations; source-set hierarchy; Android-KMP plugin migration; dependency placement; private Gradle/Maven dependency resolution or consumption failures; KSP/KAPT; detekt/ktlint; Compose compiler; CI; test task selection.

## Private Dependency Resolution

For a private dependency resolution or consumption failure, do not open
`gradle.properties` or run the generic inspection flow first. Go directly to
[`../../references/environment-readiness.md`](../../references/environment-readiness.md)
and check only whether the expected credential binding is present. If ordinary
non-secret Gradle-setting diagnosis is later needed, consume only
`gradle_properties_present`, `gradle_property_keys`, and relevant diagnostics
from schema-v3 inspector output; never read the raw property file into a
model-visible surface.
Use at most one narrow, artifact-consuming wrapper task. Keep cache availability
separate from effective remote access; an access request, credential binding,
approval record, offline hit, or `404` alone does not prove access. Never print
credential values or private endpoints, and do not configure authentication,
clear shared caches, run `clean`, publish, or retry until relevant code,
credentials, or external state changes.

Do not use this route for publishing-repository configuration, creating or
rotating credentials, or broad repository administration. Use the owning
publishing or security workflow instead.

## Diagnosis Flow

1. Read:
   - `settings.gradle(.kts)`
   - root/module `build.gradle(.kts)`
   - `gradle/libs.versions.toml`
   - `gradle/wrapper/gradle-wrapper.properties`
2. Run:
   ```bash
   python3 "$PLUGIN_ROOT/scripts/kmp_inspector.py" --root <project-root>
   ```
   Inspector report schema v3 exposes only allowlisted Gradle property names
   and presence; it does not serialize values, arbitrary property names, or
   local absolute project paths.
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

## Supplemental Native Source Proof

When any project-pinned build or test path is proven blocked before relevant
source compilation and supplemental local Native evidence would help, use
`kmp-testing-quality` with
`../../references/standalone-kotlin-harness.md`. The harness does not clear the
blocker or prove Gradle, project integration, or CI.

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

### Static-Analysis Failure Protocol

- For a static-analysis failure, first classify the outcome as a reported
  finding, task/configuration failure, environment/dependency failure, or tool
  crash. A parser exception or internal stack trace is not a lint finding and
  does not justify a style rewrite by itself.
- For a tool crash, record the exact task or entrypoint, tool/plugin version,
  JDK and Kotlin versions, config and baseline inputs, flags, and analyzed
  source scope from CI. Start with the project-pinned task. If CI invokes a
  standalone binary, reproduce with that exact binary and config in a
  disposable directory; do not change project pins merely to diagnose it.
- Minimize only after reproducing the same failure fingerprint. Compare the
  smallest crashing input with the last known-good input and separate a parser
  avoidance from a semantic code change. Suppressing a rule, excluding a
  source, disabling the analyzer, or making an unproven syntax-only edit is a
  diagnostic experiment, not acceptance proof.
- Before publishing another code head, require positive local evidence that the
  pinned analyzer executes and accepts the candidate, plus the narrow compile
  or behavior proof invalidated by the edit. A task that never executed is not
  proof. The candidate remains unproven until remote CI reports terminal
  success with non-empty execution of the same analyzer and config on the
  immutable exact published head.
- If that published head retains the same tool-crash fingerprint after a local
  pass, the local reproducer is non-equivalent. Stop further code publication
  until evidence identifies a relevant difference in the analyzer binary,
  plugins, JDK, config, flags, or source inputs and the corrected local
  reproducer explains the remote failure. Another source edit alone is not new
  evidence.
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
