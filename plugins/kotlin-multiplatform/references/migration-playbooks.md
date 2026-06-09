# KMP Migration Playbooks

## AGP 9 Split

1. Find modules with KMP plus Android application/library plugins.
2. Split Android application entry points into a pure Android app module.
3. Convert shared code modules to KMP libraries.
4. Use the Android-KMP library plugin for Android-targeting KMP libraries.
5. Move Android app concerns out of shared modules.
6. Validate module by module.

## CocoaPods To SwiftPM

1. Inventory pods, Podfile-only dependencies, Kotlin imports, Xcode workspace, and build phases.
2. Add SwiftPM dependencies alongside CocoaPods.
3. Generate or validate linkage.
4. Transform imports only when namespace and bundled klibs are understood.
5. Build Kotlin and Xcode.
6. Remove CocoaPods integration.
7. Write a migration report.

## Rollback

Keep each phase reviewable. Avoid mixing structure, version bumps, resource namespace changes, and dependency replacement in one commit unless the user explicitly requests a bundled migration.
