# CI And Publishing Runbooks

## CI Matrix

Start with the smallest matrix that validates the changed surface:

- common metadata compile and common tests
- Android compile/test when Android source or Gradle config changed
- iOS simulator compile/link when iOS source, cinterop, framework, SwiftPM, or Native config changed
- Compose UI tests where configured
- ABI/publishing dry run for public libraries

## Maven/Public Library

Validate:

- Gradle metadata and publications
- target matrix
- `checkKotlinAbi` when ABI validation is configured
- POM validation when the publishing plugin exposes it
- signing configuration validation without exposing private keys
- signing boundary without exposing credentials
- publication dry run before real upload

## XCFramework And SwiftPM

Validate:

- device and simulator slices
- static/dynamic linkage
- bundle ID
- exported dependencies
- zipped XCFramework checksum
- `Package.swift` manifest and consumer import path

Use a Swift wrapper target when a binary target must travel with Swift-only package dependencies.

## KMMBridge

KMMBridge is optional. If present, review:

- plugin ID and version
- artifact hosting
- `spm()` or `cocoapods()` distribution mode
- versioning convention
- iOS consumer instructions

Do not publish or upload unless the user explicitly asks for release execution.
