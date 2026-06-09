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
