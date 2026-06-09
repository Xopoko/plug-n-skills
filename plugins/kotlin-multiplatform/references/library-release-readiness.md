# KMP Library Release Readiness

## Public Library Gates

- Confirm published modules and targets.
- Confirm public packages/classes and API ownership.
- Verify dependency target support for every published variant.
- Run ABI validation when configured:
  ```bash
  ./gradlew checkKotlinAbi
  ```
- Update ABI dumps only when intentional:
  ```bash
  ./gradlew updateKotlinAbi
  ```
- Run publication dry runs where available.
- Validate Android, JVM, iOS device/simulator, JS/Wasm, or native targets that are published.

## SwiftPM/XCFramework

- Assemble the XCFramework.
- Verify static/dynamic linkage and bundle identifiers.
- Review `export(...)` and avoid `transitiveExport=true` unless the public API requires it.
- Zip and compute checksum.
- Validate `Package.swift`:
  ```bash
  swift package reset && swift package show-dependencies --format json
  ```
- Tag the Swift package semantically.
- Test import in Xcode.
- Use a Swift wrapper target when Swift-only package dependencies must accompany a binary target.

## KMMBridge

- Verify plugin ID, version, artifact hosting, and release branch/tag flow.
- Choose and document `spm()` or `cocoapods()` distribution mode.
- Test iOS consumer import after publishing or dry-run generation.

## Caveats

- ABI validation is experimental in Kotlin docs as of the referenced page; check current docs before adding it.
- Do not force ABI validation on app-only private modules.
- Unsupported target inference behavior should be an explicit decision.
