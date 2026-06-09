# KMP Testing, CI, And Release

## Minimal Local Proof

- Common logic: `compileKotlinMetadata` and relevant `commonTest` or JVM tests.
- Android app shell: `assembleDebug` or the narrow failing task.
- iOS: `compileKotlinIosSimulatorArm64`, framework link task, or `xcodebuild` simulator build.
- Compose UI: state-holder tests plus a platform run or screenshot when practical.

## CI Shape

- Linux fast path: checkout, Java setup, Gradle setup, metadata/JVM tests, Android build.
- macOS path: iOS simulator build, framework linkage, optional desktop macOS packaging.
- Artifact upload: test reports, APKs, app folders, desktop bundles.
- Release path: isolated workflow with explicit signing and secret handling.

## Reporting

Always report exact commands. If a command fails, include the smallest useful error, the task name, and whether the source change is still valid but unverified.
