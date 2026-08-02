# Tangle Catalog And Refactoring Moves

Companion reference for the `untangle-business-logic` skill.

## Tangles To Detect

- Business rule in the wrong layer: UI/API/CLI/service code decides thresholds, sorting, filtering, eligibility, rounding, permissions, deduplication, or display policy.
- Duplicated business meaning: the same domain fact or rule exists in multiple components/services/tests with small differences.
- Hidden invariants: nullable values that are actually required, string keys with required formats, "call only once", "must be on main thread", "must happen before X", implicit timezone/currency/locale assumptions.
- Temporal coupling: correctness depends on callback order, stale async responses, lifecycle timing, unowned subscriptions, request races, or side effects between state updates.
- Split state ownership: several places mutate the same feature state or derive competing versions of truth.
- Error-policy drift: integration errors, domain errors, retry/timeout/offline behavior, and presentation states are mapped inconsistently.
- Platform workaround leakage: framework/runtime/OS/API quirks are spread through feature code or influence business decisions.
- Semantic enum/model drift: multiple types or enum cases represent the same domain concept without a clear reason.

## Refactoring Moves

Use only the moves that directly fit the hotspot:

- Extract pure rules/policies for domain decisions such as validation, eligibility, sorting, filtering, fee/price formatting, deduplication, and display classification.
- Replace magic strings and ambiguous booleans with narrow enums, typed keys, small value objects, or explicit state when it reduces ambiguity.
- Move IO/framework/platform details behind an adapter or capability so domain code does not know about SDK quirks, lifecycle hooks, HTTP clients, UI frameworks, or storage APIs.
- Introduce a single writer for feature state: reducer, transition function, view model method, command handler, or service method that owns mutation.
- Add request generation, cancellation ownership, idempotency, or stale-response guards when ordering causes incorrect state.
- Normalize error flow as Integration error -> Domain error -> Presentation state, keeping retry/timeout/offline policy in one place.
- Reuse an existing domain helper before creating a new one.
