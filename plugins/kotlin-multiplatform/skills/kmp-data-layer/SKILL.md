---
name: kmp-data-layer
description: Design and review KMP data layers, repositories, source-of-truth, DTO/domain mapping, sync, offline-first behavior, persistence choices, error handling, threading, and API exposure.
---

# KMP Data Layer

Use this skill for KMP repositories, data sources, source-of-truth design, networking/persistence boundaries, offline-first behavior, sync, DTO/domain mapping, database choice, error handling, main-safety, and data API exposure.

## Data-Layer Contract

Before implementation, identify:

- online-only, cache-first, offline-first, or local-only behavior
- source of truth
- freshness and invalidation rules
- conflict resolution
- error model
- platform storage requirements
- target support for persistence/network libraries
- test layer for each behavior

## Boundaries

- Repositories expose project-owned domain models or result types, not raw platform SDK types.
- DTOs stay near network boundaries.
- Database entities stay near persistence boundaries.
- Mapping is explicit and tested when it carries policy.
- Shared code should not depend on Android `Context`, UIKit, file handles, or platform callbacks.

## Library Choices

Verify target support before choosing:

- Ktor for shared HTTP when all targets need the same API client.
- kotlinx.serialization when shared models are stable enough.
- DataStore for small key-value settings when target support matches.
- SQLDelight for SQL-first multiplatform persistence and broad target coverage.
- Room KMP when its current target support and KSP setup fit the project.
- Platform-native persistence when shared persistence would add more risk than value.

Use Klibs.io and official docs as target-support evidence. Do not put a library in `commonMain` because it works on Android.

## Reliability Rules

- Keep repository methods main-safe.
- Make retries bounded and explicit.
- Separate recoverable failures from programmer/configuration errors.
- Do not swallow cancellation.
- Use clocks, dispatchers, and platform services through injectable abstractions when tests need control.
- Make sync idempotent and resilient to duplicate callbacks.

## Testing

- Test mappers and policies as pure functions.
- Test repositories with fakes or controlled test doubles.
- Test offline/cache invalidation behavior explicitly.
- Test failure paths, stale data, conflict resolution, and retry boundaries.
