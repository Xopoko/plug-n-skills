---
name: kmp-publishing-ci
description: Design and verify Kotlin Multiplatform CI and publishing workflows for Maven publications, Gradle metadata, ABI validation, XCFramework, SwiftPM export, KMMBridge, artifact hosting, signing boundaries, and app release gates.
---

# KMP Publishing And CI

Use for KMP release automation: Maven publishing, Gradle metadata, public library releases, XCFramework, SwiftPM export, KMMBridge, CocoaPods migration, CI matrix design, and app-store build boundaries.

## Classify Shape

- Private app module only.
- Internal shared library consumed by platform apps.
- Public KMP Maven library.
- Prebuilt iOS framework via SwiftPM or CocoaPods.
- App-store release: shared code plus native app shells.

## Gates

- Maven/public library: metadata, publications, signing boundary, `checkKotlinAbi` when configured, target matrix, publication dry run.
- Maven Central: POM validation and signing configuration checks when the configured publishing plugin exposes them.
- XCFramework: device/simulator slices, bundle ID, static/dynamic linkage, exported dependencies, zip/checksum, consumer import test.
- SwiftPM: generated/maintained `Package.swift`, checksum validation, tag/version rule, wrapper target when Swift dependencies must accompany a binary target.
- KMMBridge: artifact hosting, `spm()` or `cocoapods()` mode, versioning, iOS consumer documentation.
- CI matrix: Android compile/test, common metadata compile/test, iOS simulator compile/link, Compose UI tests when configured, ABI/publishing dry run for libraries.
- GitHub Actions: Linux runners can cover many shared/Android tasks; iOS builds require macOS runners. Preserve artifacts only after successful validation.

## Safety

- Do not create/paste real signing secrets, Maven credentials, App Store Connect keys, keystores, provisioning profiles, or checksums from private artifacts.
- Do not publish/upload/notarize/submit without an explicit release request.
- Keep release commands dry-run/validation-only unless the user asks to publish.

## Output

For releases, provide:

- release shape
- artifact matrix
- CI tasks
- publishing gates
- secret/signing boundary
- exact validation commands
- blocker list

Configured validation tasks:

- `checkPomFileForMavenPublication`
- `checkSigningConfiguration`
- `publishToMavenCentral`
- `publishAndReleaseToMavenCentral`
- `./gradlew jvmTest`
- Android assemble/test tasks for Android targets
- iOS `xcodebuild` or Kotlin iOS simulator compile/link tasks

Use publish tasks only as dry-run/validation unless the user explicitly requests release execution.
