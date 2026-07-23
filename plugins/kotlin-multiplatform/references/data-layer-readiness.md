# KMP Data Layer Readiness

## Source Of Truth

Choose one:

- network-only
- cache-first
- offline-first local store
- local-only
- platform-owned source with shared facade

Document freshness, invalidation, conflict resolution, and retry policy.

## Boundaries

- DTOs stay near network.
- Entities stay near persistence.
- Domain models stay platform-neutral.
- Platform SDK callbacks are adapted at the edge.
- Repositories expose project-owned results.

## Library Target Check

Before choosing Ktor, DataStore, Room KMP, SQLDelight, Koin, or another library, verify:

- Maven coordinates.
- Android target.
- iOS device and simulator.
- Desktop/JVM.
- JS/Wasm if configured.
- Native host targets if configured.

Use official docs and Klibs.io as evidence.

## Async State Consistency

Keep one authoritative lifecycle state and preserve it through KMP projections.
Use `StateFlow` or the project's equivalent without treating initial state as
`Available(empty)`.

| Concern | KMP contract | Deterministic proof |
| --- | --- | --- |
| Invalidation | Global and keyed/domain generations cover observers, cache, one-shot, persistence, memo, and coalescer paths | Start A, invalidate, complete A; attach a late collector |
| Publication order | A declared latest-start or latest-success policy is separate from invalidation | Complete same-key B before A; then fail/cancel B in a separate schedule |
| Final commit | `Mutex`, actor, compare-and-set, or transaction owns validation plus state/cache commit | Hold A at final pre-commit while B wins and while clear wins |
| Replay read | Candidate and authority come from one serialized or stamped snapshot | Clear between candidate capture and validation, including zero dependencies |
| Coalescing | Post-invalidation callers cannot join work created under revoked ownership | Start shared A, invalidate, then let B attempt to join |
| Caller result | Rejected work rereads authority or returns stale/retry/cancellation | Assert A's direct caller never receives A as current |
| Cancellation | Cancellation is not a commit fence; late failure has an observation policy | Let cancellation-ignoring A finish after B or clear wins |
| Notification | Commit emission intent/revision with state; invoke callbacks outside the owner | Inject failure at a durable mutation-notification boundary |
| Key isolation | Key invalidation leaves unrelated keys valid; global clear does not | Run x and y across key clear, then global clear |
| TTL | Read-time staleness is separate from active observer expiry signals | Advance a controlled clock, read, then fire each declared signal |

With latest-start-wins, reserving B rejects A even when B later fails or is
cancelled. With latest-success-wins, B's attempt alone does not reject A; only a
successful newer commit or invalidation fences it.

Across a durable persistence and notification boundary, use an ordered,
idempotent notification record. For process-local delivery, publish an immutable
snapshot or emission revision after the serialized commit without invoking
arbitrary callbacks while holding the owner.
