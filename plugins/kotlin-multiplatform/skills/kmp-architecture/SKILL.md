---
name: kmp-architecture
description: Design or refactor Kotlin Multiplatform module boundaries, source-set hierarchy, shared logic/shared UI split, platform APIs, interop boundaries, and cross-platform library choices.
---

# KMP Architecture

Use for KMP project/module/source-set structure, shared boundaries, native/shared UI, library selection, Swift API exposure, domain/data/presentation layering, and feature modularization.

## Contract

Start from target platforms/product intent, not favorite templates:

1. First-class platforms: Android/iOS, Desktop, Web/Wasm, JVM server, watchOS/tvOS, Linux/Windows/macOS.
2. Shared scope: business logic only, presentation state, UI/resources, networking/persistence, validation, models, analytics.
3. Platforms needing native UI or native APIs.
4. Runnable-app modules versus library modules.
5. Proof that must pass per platform.

## Default Shape

New KMP apps, prefer:

```text
project/
  shared/        # KMP library with common logic and shared UI if all client platforms use it
  androidApp/    # thin Android application shell
  iosApp/        # Xcode app consuming the shared framework/package
  desktopApp/    # desktop entry point when present
  webApp/        # web entry point when present
```

When some platforms use native UI:

```text
sharedLogic/     # consumed by all clients, no Compose dependency
sharedUI/        # consumed only by Compose Multiplatform clients
androidApp/
iosApp/
```

When server is included, isolate client/server ownership:

```text
core/            # models and validation shared between client and server
sharedLogic/
app/androidApp/
app/iosApp/
server/
```

Do not rewrite existing projects just for this shape. Migrate only to remove ambiguity, enable AGP compatibility, or reduce platform coupling.

## Boundary Rules

- `commonMain` owns platform-independent domain logic, presentation state, DTOs when stable, validation, interfaces.
- Platform source sets own SDK calls/filesystem/sensors/platform lifecycle, native UI bridges, and interop wrappers.
- Prefer interfaces plus platform implementations for coarse-grained or dependency-injected platform behavior.
- Prefer `expect/actual` for small platform abstractions with stable signatures.
- Do not expose complex Kotlin implementation details directly to Swift if a smaller facade is enough.
- Keep generated resource access and platform resource namespaces stable during module moves.

## Library Choice

Do not add cross-platform libraries by habit. Choose after target support is verified:

- Networking: Ktor client when shared HTTP helps.
- Serialization: kotlinx.serialization for shared stable models.
- DI: Koin or manual DI in shared code; keep Hilt in Android-only app modules if already used.
- Persistence: DataStore for key-value settings; Room KMP or SQLDelight for relational persistence after target/migration support is verified.
- Navigation: Compose navigation, Decompose, Voyager, or platform-native navigation by UI sharing/existing conventions.
- Logging: use a project-owned logging facade; do not leak Kermit, Napier, OSLog, or Timber directly into domain code.

## Adoption Check

Before recommending broad KMP adoption in an existing codebase, classify risk:

- Team ownership: Android-only, iOS-only, or shared mobile team.
- UI approach: shared UI, native UI, or mixed.
- Existing app coupling: Android SDK leakage, Swift API expectations, repository shape, test coverage.
- Release surface: app-only shared module, published library, internal binary, public artifact.
- Rollout plan: one feature, one layer, one module, full app shell split.

Prefer incremental adoption: one layer or feature proves build/test/release before broad migration.

## Feature Shape

Use repo convention. If starting fresh:

```text
feature-x/
  domain/
  data/
  presentation/
  ui/
```

Keep use cases for policy-heavy, reused, or independently testable logic. Do not wrap every repository call in a class just to satisfy a diagram.

## Design Review Checklist

- Every `commonMain` dependency supports all configured targets.
- Platform source sets contain only platform-owned code.
- Shared UI does not depend on Android-only APIs.
- Android app code stays in an Android app module, not in a KMP library module.
- iOS exports are intentional and small.
- Tests exist at the level where behavior is owned.
- Migration plan includes the smallest reversible step and validation command.
