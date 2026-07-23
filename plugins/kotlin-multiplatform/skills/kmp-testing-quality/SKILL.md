---
name: kmp-testing-quality
description: Design and review KMP testing strategy, commonTest, kotlin.test, platform tests, Compose Multiplatform UI tests, screenshot tests, test doubles, refactor safety, code review gates, and regression validation.
---

# KMP Testing And Quality

Use for KMP test strategy/review: `commonTest`, `kotlin.test`, platform tests, Compose Multiplatform UI tests, screenshot tests, test doubles, refactor safety, code review gates, regression validation.

## Strategy

Favor confidence/speed over coverage vanity:

- Many shared/unit tests.
- Fewer integration tests.
- Fewer UI/end-to-end than lower-level tests.
- Behavior-focused assertions.
- Deterministic test data/fake dependencies.

## Placement

- Put shared business logic in `commonTest` first.
- Shared tests should use `kotlin.test`, not JUnit-only APIs.
- Android framework behavior belongs in Android-only local/instrumented tests.
- Robolectric is Android-only; never in `commonTest`.
- Non-shared iOS/native behavior should be validated via native target tasks/Xcode.
- Compose shared UI tests should focus on semantics/observable behavior.
- Compose Multiplatform UI tests should use current Compose testing API and target-specific setup.
- Verify source-set/dependency instructions against current docs before editing Gradle files.

## Proof Integrity

- For async state ownership and race invariants, also use
  `async-state-consistency` when available. This skill owns KMP source-set,
  harness, task, and result-proof placement and remains standalone.
- Match each claim to its proof seam. A screenshot or golden proves captured
  rendering only; use semantics/interaction tests for user behavior,
  saver/restoration tests for restored state, and state-holder or lifecycle
  adapter tests for lifecycle-driven effects.
- Confirm that the exact source set and harness support the required test API.
  Screenshot capture support does not imply interaction-test support.
- A green aggregate task is not proof when the relevant leaf task is
  `SKIPPED`, `NO-SOURCE`, executes zero tests, or produces no inspectable test
  result. Verify non-empty execution in the task trace and report.
- When changing a fixture or assertion to prove a new claim, inventory the
  existing regression claims first. Preserve them with explicit pre/post
  assertions or separate tests; do not trade one proof obligation for another.
- For exactly-once event claims, assert cardinality across creation,
  restoration, resume, and re-collection as applicable. Idempotency alone does
  not prove exactly-once delivery.

## Test First

- Business rules.
- DTO/domain/UI mapping.
- Repository coordination logic.
- State-holder transitions.
- Error/retry/cancellation/stale-data behavior.
- Navigation decisions/one-shot effects when important.
- Migration/refactor regressions.
- Security-sensitive flows: token refresh, logout, stale credentials, redaction, retry-loop guards.
- Performance-sensitive state reducers/mappers where deterministic tests catch regressions cheaply.

## Doubles

- Prefer fakes for repositories/data sources.
- Use stubs for simple fixed responses.
- Use mocks only when interaction is the tested behavior.
- Avoid real network/stores/clocks/platform services unless explicitly integration-level.
- For async ordering/race tests, block controllable fakes at explicit gates or
  barriers, attach observers, then release completions. Sleeps or delays are
  not synchronization proof.

## Refactors/Migrations

- Keep scope narrow.
- Do not keep old/new paths active without feature flag and removal plan.
- Preserve public contracts unless the goal requires breaking change.
- Move in phases: foundation, adoption, lock-in, cleanup.
- Add regression tests for the motivating failure.
- Make duplicate callbacks/retries idempotent.
- Add redacted observability for high-risk transitions when useful.

## Review

Lead reviews with:

- missing high-signal tests
- brittle/misplaced tests
- slow/flaky test risks
- platform mismatch in test source sets
- exact validation commands
- residual risk when platform tests cannot run locally
