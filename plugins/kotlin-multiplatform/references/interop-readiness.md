# KMP Interop Readiness

## Bridge Decision Ladder

1. `commonMain` with no platform API.
2. Existing multiplatform library.
3. Intermediate source set such as `iosMain`.
4. Common interface plus platform entry-point wiring.
5. Narrow `expect`/`actual` function or property.
6. Broader `expect`/`actual` class only when justified.
7. Generated or third-party interop enhancer after current-doc verification.

## Swift API Checks

- Flow and StateFlow shape.
- suspend function ergonomics and cancellation.
- sealed hierarchy and enum exposure.
- default arguments.
- Kotlin collection and nullability exposure.
- framework name, package/group, and public facade.
- simulator/device architecture support.
- exported dependencies and `transitiveExport` impact.
- SwiftPM wrapper target need when binary targets need Swift-only dependencies.

Optional tools:

- SKIE for Swift-friendly wrappers around flows, suspend functions, sealed hierarchies, enums, and defaults.
- KMP-NativeCoroutines for flow/native coroutine bridging.
- KMMBridge for publishing and integrating iOS frameworks.

These are choices, not defaults.

## cinterop

Review `.def` files, headers, package names, include directories, compiler options, linker options, and simulator/device architecture support. Keep generated bindings behind project-owned facades when possible.
