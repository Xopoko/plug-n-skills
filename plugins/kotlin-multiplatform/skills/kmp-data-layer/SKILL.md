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
- read-time TTL versus active expiry, including the signal that re-evaluates
  state for existing observers; elapsed time alone does not emit without a
  declared active trigger
- conflict resolution
- error model
- platform storage requirements
- persistence/network library target support
- test layer per behavior
- explicit initial, available, invalidated, error, and stale/retry meaning where
  absence or ownership has lifecycle significance

## Async State Consistency Adapter

For invalidation, replay, memoization, coalescing, one-shot results, or
competing async publishers, also use `async-state-consistency` when the
Architecture Intelligence plugin is available. This KMP skill remains
standalone: the minimum KMP contract and proof obligations are below.
Use `references/data-layer-readiness.md` for the standalone KMP readiness and
race matrix.

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
- Cancellation is not a commit fence. Cancellation-ignoring work still needs
  ownership and caller-result guards; define how its late failure is observed.
- Use clocks, dispatchers, and platform services through injectable abstractions when tests need control
- Make sync idempotent and resilient to duplicate callbacks
- Keep one authoritative `StateFlow` or project-equivalent lifecycle state and
  preserve its discriminator through KMP projections; unknown is not
  `Available(empty)`.
- Make invalidation authoritative across active and late observers, warm cache,
  one-shot reads, persistence, memoization, and request coalescing. Use global
  and keyed/domain generations so unrelated keys remain independent.
- Keep invalidation generation separate from ordinary publication sequence.
  Choose latest-start-wins or latest-success-wins for competing work, including
  the newer operation's failure or cancellation. Ordinary publication must not
  emit `Invalidated`.
- With latest-start-wins, reserving B rejects A even if B later fails or is
  cancelled; compare the reserved publication sequence. With
  latest-success-wins, B's attempt alone does not reject A; compare committed
  publication authority plus invalidation generation, so A may commit after B
  fails when no other authority intervenes.
- With `Mutex`, an actor, compare-and-set, or an equivalent owner, linearize
  final ownership validation plus state/cache commit. Also linearize replay
  candidate read plus authority validation; an empty dependency set still
  checks the owning-domain generation. Do slow fetches outside the owner.
- Commit state plus emission intent/revision atomically, but deliver arbitrary
  callbacks outside the serialized owner. Across a durable persistence and
  notification boundary, use an ordered, idempotent notification record.
- Do not let a post-invalidation caller join coalesced work created under
  revoked ownership. Declare per-caller versus shared-work cancellation.
- When a completion loses ownership, re-read authoritative state or return a
  declared stale/retry/cancellation result; never return its candidate as
  current or invent `Error`/`Invalidated`.

## Testing

- Test mappers and policies as pure functions
- Test repositories with fakes or controlled test doubles
- Test offline/cache invalidation explicitly
- Test failure paths, stale data, conflict resolution, and retry boundaries
- Put shared behavior in `commonTest` with `kotlin.test` when the harness fits.
- Use gates or barriers at the final controllable read/commit boundary; sleeps
  and delays are not synchronization proof.
- Cover state transitions and projections, late collection, pre-invalidation
  completion, same-key reverse completion, both final-boundary winners,
  read-side clear, post-invalidation coalescer join, newer failure under the
  declared supersession policy, keyed/global invalidation, direct caller
  outcomes, TTL read versus observer emission, and mutation-notification
  recovery across every replay/repopulation path.
