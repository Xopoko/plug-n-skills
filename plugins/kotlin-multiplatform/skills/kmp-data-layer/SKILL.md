---
name: kmp-data-layer
description: Design and review KMP data layers, repositories, source-of-truth, DTO/domain mapping, sync, offline-first behavior, persistence choices, error handling, threading, and API exposure.
---

# KMP Data Layer

Use for KMP data-layer work: repositories, data sources, source-of-truth design, network/persistence boundaries, offline-first behavior, sync, DTO/domain mapping, database choice, error handling, main-safety, and data API exposure.

## Contract

Before implementing, identify:

- behavior: online-only, cache-first, offline-first, or local-only
- source of truth
- freshness/invalidation rules
- distinguish read-time TTL checks from active expiry; document which timer,
  refresh, lifecycle, or storage signal re-evaluates freshness and emits to
  existing observers, because elapsed time alone is not an emission trigger
- conflict resolution
- error model
- platform storage requirements
- persistence/network library target support
- test layer per behavior
- when absence has lifecycle meaning, model initial, available, and invalidated
  states explicitly at the shared source of truth; define fail-closed behavior
  there instead of patching individual consumers

## Boundaries

- Repositories expose project-owned domain models or result types, not raw platform SDK types.
- DTOs stay near network boundaries.
- Database entities stay near persistence boundaries.
- Keep policy-bearing mapping explicit and tested.
- Shared code should not depend on Android `Context`, UIKit, file handles, or platform callbacks.

## Libraries

Verify target support first:

- Ktor for shared HTTP when all targets need the same API client
- kotlinx.serialization when shared models are stable enough
- DataStore for small key-value settings when target support fits
- SQLDelight for SQL-first multiplatform persistence with broad target coverage
- Room KMP when current target support and KSP setup fit the project
- Platform-native persistence when shared persistence would add more risk than value

Use Klibs.io and official docs as target-support evidence. Do not put a library in `commonMain` because it works on Android.

## Reliability

- Keep repository methods main-safe
- Bound retries explicitly
- Separate recoverable failures from programmer/configuration errors
- Do not swallow cancellation.
- Use clocks, dispatchers, and platform services through injectable abstractions when tests need control
- Make sync idempotent and resilient to duplicate callbacks
- Make invalidation authoritative for active and late observers: work started
  before clear/invalidation must not republish stale data after it completes.
  Use generation/version ownership or an equivalent guard when cancellation
  alone is insufficient.

## Testing

- Test mappers and policies as pure functions
- Test repositories with fakes or controlled test doubles
- Test offline/cache invalidation explicitly
- Test failure paths, stale data, conflict resolution, and retry boundaries
- For shared state-contract changes, cover every allowed transition and each
  affected consumer projection
- Cover late collection after invalidation, pre-invalidation work completing
  afterward, and the declared initial-to-success/failure emission order
- With a controlled clock, assert the next-read result after TTL, no observer
  emission from clock advance alone, and the expected emission or non-emission
  for each supported expiry trigger
