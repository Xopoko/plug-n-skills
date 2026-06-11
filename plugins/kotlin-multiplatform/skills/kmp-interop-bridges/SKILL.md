---
name: kmp-interop-bridges
description: Design and review KMP platform bridges, source-set placement, expect/actual, entry-point wiring, cinterop, Swift API readiness, SKIE, KMP-NativeCoroutines, KDoctor, XCFrameworks, and SwiftPM export.
---

# KMP Interop Bridges

Use for KMP bridges, shared-native boundaries, Swift/native export reviews.

## Decision Order

1. `commonMain` if no platform API needed.
2. Existing multiplatform library if one covers it.
3. Intermediate source set, such as `iosMain`, for one shared implementation.
4. Common interface plus platform entry-point wiring if cleaner.
5. Narrow `expect`/`actual` function or property if enough.
6. Consider broader `expect`/`actual` classes or generated interop only after 1-5 fail.

Do not default to `expect`/`actual` for every platform dependency.

## Source Sets

- Use highest valid source set.
- Use `iosMain` for Apple-family code covering iOS device/simulator.
- SDK bootstrapping, lifecycle, and packaging stay in platform app modules.
- Do not leak Android/UIKit/Foundation/POSIX/vendor SDK types into shared domain contracts unless intentionally public.

## Swift API

Review:

- Kotlin `Flow`, `StateFlow`, suspend functions.
- sealed classes/interfaces, enums.
- default arguments, overload ergonomics.
- Kotlin collections, nullability, error handling.
- package/module names, framework `baseName`.
- binary framework static/dynamic choice.
- exported dependencies; intentional `transitiveExport`.

SKIE can improve Swift ergonomics via wrappers for Flow, suspend functions, sealed hierarchies, enums, and default arguments. Optional: verify current docs, build impact, team acceptance, generated API before adding.

KMP-NativeCoroutines can expose flows to Swift; choose only after comparing current project needs, existing API shape, and docs.

## cinterop

- Check `.def`, headers, package names, include directories, compiler/linker options, and architecture support.
- Prefer Objective-C-compatible APIs for Swift/Apple dependencies unless current Kotlin tooling supports the needed Swift import route.
- Put generated bindings behind project-owned facades when possible.
- Validate simulator/device architectures.

## Environment

If host setup may be at fault, consider KDoctor on macOS. It checks KMP mobile readiness: OS, JDK/JAVA_HOME, Android Studio plugins, Xcode, Ruby, CocoaPods. Do not treat output as project architecture review.

## SwiftPM/XCFramework

Remote iOS:

- Build XCFramework for Apple targets.
- Validate `Package.swift`.
- Calculate/update checksum for binary targets.
- Use semantic version tags for SwiftPM consumers.
- Test import in Xcode.
- For multiple KMP modules, consider umbrella module and state exported dependencies.
- Use Swift wrapper target when a binary target must travel with Swift-only dependencies.
- Consider KMMBridge only when the team wants maintained prebuilt-framework publishing; verify `spm()`/`cocoapods()` mode, artifact hosting, versioning, consumer docs.
