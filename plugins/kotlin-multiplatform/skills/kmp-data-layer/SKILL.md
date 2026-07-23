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
- Preserve state discriminators through projections: do not encode
  initial/unknown as a valid domain value such as an empty collection. Keep it
  distinct from `Available(empty)` so consumers can preserve pending intent.
- Match projection modality to its inputs: synchronous projections use only
  synchronously available state; otherwise pre-resolve at an owned asynchronous
  boundary or expose a suspend contract.
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
- Make invalidation authoritative for active and late observers, warm-cache
  reads, and one-shot reads: work started before clear/invalidation must not
  return, replay, or repopulate stale data after it completes.
  Use generation/version ownership or an equivalent guard that covers every
  cache, request-coalescing, or memoization layer able to replay or repopulate
  data. Scope it to the invalidation domain: a global clear invalidates every
  key, while key-level invalidation must not suppress valid work for unrelated
  keys.
- Keep publication ordering separate from invalidation state. When same-key
  mutations or fetched snapshots can complete out of order, assign monotonic
  ownership (revision, sequence, or equivalent) within that key/domain. An older
  completion must not overwrite, replay, or repopulate a newer published value.
  Advancing ownership for an ordinary write must not emit `Invalidated`;
  unrelated keys remain independent unless the operation is explicitly global.
- Linearize ownership validation with every replayable state or cache commit.
  The validation and commit it authorizes must be one atomic or serialized
  transition against clear/invalidation and competing publishers in the same
  domain (compare-and-set, a serialized owner, or equivalent). A successful
  check followed by an unguarded assignment is insufficient.
- A completion rejected by publication ownership must not return its stale
  snapshot as the current one-shot result: re-read the authoritative state or
  return a declared stale/retry outcome. Rejection alone must not emit or
  persist `Error` or `Invalidated` unless the state contract declares it.

## Testing

- Test mappers and policies as pure functions
- Test repositories with fakes or controlled test doubles
- Test offline/cache invalidation explicitly
- Test failure paths, stale data, conflict resolution, and retry boundaries
- For shared state-contract changes, cover every allowed transition and each
  affected consumer projection
- Cover late collection after invalidation, pre-invalidation work completing
  afterward, and the declared initial-to-success/failure emission order
- Exercise the same invalidation ownership and domain through observer,
  warm-cache, and one-shot paths across every replay/repopulation layer; prove
  key-level invalidation leaves valid unrelated-key work intact
- With controlled completion order, start same-key A before B, complete B
  before A, and prove B remains the observable and replayed value after A
  completes, with no `Invalidated` emission. Exercise every path able to
  publish, replay, or repopulate state, and prove unrelated-key work completes
  independently
- Add a deterministic last-pre-publication race proof: hold A at the final
  controllable boundary before its atomic or serialized state/cache commit
  attempt, let same-domain B or clear/invalidation complete and become
  authoritative, then release A. Prove A cannot publish, replay, or repopulate
  at any layer. Run both winner variants; changing ownership before A reaches
  this boundary does not cover the check-to-commit race
- When A is a rejected one-shot fetch, assert its caller receives re-read B or
  the declared stale/retry outcome, never A as current. Rejection alone must
  emit or persist neither `Error` nor `Invalidated` unless declared
- With a controlled clock, assert the next-read result after TTL, no observer
  emission from clock advance alone, and the expected emission or non-emission
  for each supported expiry trigger
