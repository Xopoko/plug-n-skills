# KMP Migration Playbooks

## AGP 9 Split

1. Find modules with KMP plus Android application/library plugins.
2. Split Android application entry points into a pure Android app module.
3. Convert shared code modules to KMP libraries.
4. Use the Android-KMP library plugin for Android-targeting KMP libraries.
5. Move Android app concerns out of shared modules.
6. Validate module by module.

## CocoaPods To SwiftPM

`swiftPMDependencies {}` imports dependencies into KMP modules; it is not the
XCFramework/Swift-package export path. The official import integration is
Alpha and may require a prerelease KGP. Before migration, verify the
project-pinned KGP against the current official import guide and get explicit
acceptance of that stability boundary. A KMP module that uses SwiftPM import
cannot currently be assumed to export successfully as a Swift package.

1. Inventory pods, Podfile-only dependencies, Kotlin imports, Xcode workspace, and build phases.
2. Confirm the official current KGP requirement and SwiftPM-import limitations.
3. Add SwiftPM dependencies alongside CocoaPods.
4. Set an explicit Gradle `group`; validate the `swiftPMImport.<group>.<project>` namespace.
5. Commit the generated `.swiftpm-locks`/`Package.resolved` state.
6. Move `cocoapods.framework {}` settings to `binaries.framework {}`.
7. Reconfigure Xcode direct integration with the generated integration task.
8. Transform imports only when namespace and bundled klibs are understood.
9. Build Kotlin and Xcode on affected targets.
10. Remove CocoaPods integration only after both paths pass.
11. Write a migration report including the Alpha and export limitations.

Primary references:

- [SwiftPM dependency import](https://kotlinlang.org/docs/multiplatform/multiplatform-spm-import.html)
- [CocoaPods-to-SwiftPM migration](https://kotlinlang.org/docs/multiplatform/multiplatform-cocoapods-spm-migration.html)

## Rollback

Keep each phase reviewable. Avoid mixing structure, version bumps, resource namespace changes, and dependency replacement in one commit unless the user explicitly requests a bundled migration.
