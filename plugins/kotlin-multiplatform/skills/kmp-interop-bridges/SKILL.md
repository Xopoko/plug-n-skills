---
name: kmp-interop-bridges
description: Design and review KMP platform bridges, source-set placement, expect/actual, entry-point wiring, cinterop, Swift API readiness, SKIE, KMP-NativeCoroutines, KDoctor, XCFrameworks, and SwiftPM export.
---

# KMP Interop Bridges

Use this skill for platform-specific integrations, shared-to-native boundaries, `expect`/`actual`, cinterop, iOS framework exports, Swift API shape, SKIE, KMP-NativeCoroutines, KDoctor, XCFrameworks, and SwiftPM export.

## Bridge Decision Order

1. Can the code live in `commonMain` with no platform API?
2. Can an existing multiplatform library cover it?
3. Can an intermediate source set, such as `iosMain`, share one implementation?
4. Is a common interface plus platform entry-point wiring cleaner?
5. Is a narrow `expect`/`actual` function or property enough?
6. Only then consider broader `expect`/`actual` classes or generated interop.

Do not default to `expect`/`actual` for every platform dependency.

## Source-Set Placement

- Put code in the highest valid source set.
- Use `iosMain` for Apple-family code that covers iOS device and simulator.
- Keep SDK bootstrapping, lifecycle, and packaging in platform app modules.
- Do not leak Android, UIKit, Foundation, POSIX, or vendor SDK types into shared domain contracts unless that is the intentional public API.

## Swift API Readiness

Review Swift-facing APIs for:

- Kotlin `Flow`, `StateFlow`, and suspend functions.
- sealed classes/interfaces and enums.
- default arguments and overloaded API ergonomics.
- Kotlin collections, nullable types, and error handling.
- package/module naming and framework `baseName`.
- binary framework static/dynamic choice.
- exported dependencies and whether `transitiveExport` is intentional.

SKIE can improve Swift ergonomics by generating Swift wrappers for Flow, suspend functions, sealed hierarchies, enums, and default arguments. Treat it as an optional integration: verify current docs, build impact, team acceptance, and generated API before adding it.

KMP-NativeCoroutines can also help expose flows to Swift. Choose it only after comparing current project needs, existing API shape, and docs.

## cinterop And Native Libraries

For cinterop:

- Check `.def` files, headers, package names, include directories, compiler options, linker options, and architecture support.
- Prefer Objective-C-compatible APIs for Swift/Apple dependencies unless current Kotlin tooling supports the needed Swift import route.
- Keep generated bindings isolated behind project-owned facades when possible.
- Validate both simulator and device architectures.

## Environment Diagnosis

If the issue may be host setup rather than project code, consider KDoctor on macOS. KDoctor checks KMP mobile environment readiness, including OS, JDK/JAVA_HOME, Android Studio plugins, Xcode, Ruby, and CocoaPods. Do not treat KDoctor output as a project architecture review.

## SwiftPM And XCFramework Export

For remote iOS integration:

- Build an XCFramework for Apple targets.
- Validate `Package.swift`.
- Calculate and update checksum for binary targets.
- Use semantic version tags for SwiftPM consumers.
- Test import in Xcode.
- For multiple KMP modules, consider an umbrella module and be explicit about exported dependencies.
- Use a Swift wrapper target when a binary target must travel with Swift-only dependencies.
- Consider KMMBridge only when the team wants a maintained prebuilt-framework publishing workflow; verify `spm()` or `cocoapods()` mode, artifact hosting, versioning, and consumer docs.
