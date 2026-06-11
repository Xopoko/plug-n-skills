---
name: kmp-architecture
description: Design or refactor Kotlin Multiplatform module boundaries, source-set hierarchy, shared logic/shared UI split, platform APIs, interop boundaries, and cross-platform library choices.
---

# KMP Architecture

Use this skill for KMP project structure, module design, source-set hierarchy, shared code boundaries, native UI versus shared UI decisions, library selection, API exposure to Swift, domain/data/presentation layering, and feature modularization.

## Architecture Contract

Start from target platforms and product intent, not from a favorite template:

1. Which platforms are first-class: Android, iOS, Desktop, Web/Wasm, JVM server, watchOS, tvOS, Linux, Windows, macOS.
2. What is shared: business logic only, presentation state, UI, resources, networking, persistence, validation, models, analytics.
3. Which platforms need native UI or native APIs.
4. Which modules produce runnable apps and which modules produce libraries.
5. What proof must pass on each platform.

## Default Project Shape

For new KMP apps, prefer:

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

Existing projects do not need to be rewritten just to match this shape. Migrate only when it removes real ambiguity, enables AGP compatibility, or reduces platform coupling.

## Boundary Rules

- `commonMain` owns platform-independent domain logic, presentation state, DTOs when stable, validation, and interfaces.
- Platform source sets own SDK calls, filesystem, sensors, platform lifecycle, native UI bridges, and interop wrappers.
- Prefer interfaces plus platform implementations when the platform behavior is coarse-grained or dependency-injected.
- Prefer `expect/actual` for small platform abstractions with stable signatures.
- Do not expose complex Kotlin implementation details directly to Swift if a smaller facade is enough.
- Keep generated resource access and platform resource namespaces stable during module moves.

## Library Choice

Do not add a cross-platform library by habit. Choose after target support is verified:

- Networking: Ktor client when shared HTTP is useful.
- Serialization: kotlinx.serialization when models are shared and stable.
- DI: Koin or manual DI for shared code; keep Hilt in Android-only app modules if already used.
- Persistence: DataStore for key-value settings; Room KMP or SQLDelight for relational persistence after target and migration support are verified.
- Navigation: Compose navigation, Decompose, Voyager, or platform-native navigation depending on UI sharing and existing conventions.
- Logging: use a project-owned logging facade; do not leak Kermit, Napier, OSLog, or Timber directly into domain code.

## Production Adoption Check

Before recommending broad KMP adoption in an existing codebase, classify risk:

- Team ownership: Android-only, iOS-only, or shared mobile team.
- UI approach: shared UI, native UI, or mixed.
- Existing app coupling: Android SDK leakage, Swift API expectations, repository shape, and test coverage.
- Release surface: app-only shared module, published library, internal binary, or public artifact.
- Rollout plan: one feature, one layer, one module, or full app shell split.

Prefer incremental adoption where one layer or feature can prove build, test, and release paths before a broad migration.

## Feature Shape

Use the repo's existing convention. If starting fresh:

```text
feature-x/
  domain/
  data/
  presentation/
  ui/
```

Keep use cases for policy-heavy, reused, or independently testable logic. Do not wrap every repository call in a class just to satisfy a diagram.

## Design Review Checklist

- Every dependency in `commonMain` supports all configured targets.
- Platform source sets contain only platform-owned code.
- Shared UI does not depend on Android-only APIs.
- Android app code is in an Android app module, not in a KMP library module.
- iOS exports are intentional and small.
- Tests exist at the level where the behavior is owned.
- Migration plan includes the smallest reversible step and validation command.
