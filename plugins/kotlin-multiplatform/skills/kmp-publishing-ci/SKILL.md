---
name: kmp-publishing-ci
description: Design and verify Kotlin Multiplatform CI and publishing workflows for Maven publications, Gradle metadata, ABI validation, XCFramework, SwiftPM export, KMMBridge, artifact hosting, signing boundaries, and app release gates.
---

# KMP Publishing And CI

Use this skill for KMP release automation, Maven publishing, Gradle metadata, public library release, XCFramework, SwiftPM export, KMMBridge, CocoaPods migration, CI matrix design, and app-store build boundaries.

## Classify Release Shape

- Private app module only.
- Internal shared library consumed by platform apps.
- Public KMP Maven library.
- Prebuilt iOS framework consumed through SwiftPM or CocoaPods.
- App-store release using shared code and native app shells.

## Gates

- Maven/public library: metadata, publications, signing boundary, `checkKotlinAbi` when configured, target matrix, publication dry run.
- Maven Central: include POM validation and signing configuration checks when the configured publishing plugin exposes them.
- XCFramework: device and simulator slices, bundle ID, static/dynamic linkage, exported dependencies, zip/checksum, consumer import test.
- SwiftPM: generated or maintained `Package.swift`, checksum validation, tag/version rule, wrapper target when Swift dependencies must accompany a binary target.
- KMMBridge: artifact hosting, `spm()` or `cocoapods()` mode, versioning, and iOS consumer documentation.
- CI matrix: Android compile/test, common metadata compile/test, iOS simulator compile/link, Compose UI tests where configured, ABI/publishing dry run for libraries.
- GitHub Actions: Linux runners can cover many shared/Android tasks, but iOS builds require macOS runners. Preserve artifacts only after successful validation.

## Safety

- Do not create or paste real signing secrets, Maven credentials, App Store Connect keys, keystores, provisioning profiles, or checksums from private artifacts.
- Do not publish, upload, notarize, or submit without an explicit release request.
- Keep release commands dry-run or validation-only unless the user asks to publish.

## Output

For release work, provide:

- release shape
- artifact matrix
- CI tasks
- publishing gates
- secret/signing boundary
- exact validation commands
- blocker list

Useful validation tasks when configured:

- `checkPomFileForMavenPublication`
- `checkSigningConfiguration`
- `publishToMavenCentral`
- `publishAndReleaseToMavenCentral`
- `./gradlew jvmTest`
- Android assemble/test tasks for Android targets
- iOS `xcodebuild` or Kotlin iOS simulator compile/link tasks

Use publish tasks as dry-run or validation-only unless the user explicitly requests release execution.
