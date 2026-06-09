# KMP Testing Quality Gates

## Placement

- `commonTest`: shared business logic, `kotlin.test`.
- Android local tests: Android/JVM behavior not needing a device.
- Android instrumented tests: behavior needing Android runtime.
- iOS/native: native target compile/link/tests or Xcode where needed.
- Compose UI: semantics and user-visible behavior.

## Review Questions

- Does the test prove behavior, not implementation detail?
- Can a lower-level test catch this faster?
- Are fakes clearer than mocks?
- Are failure, retry, cancellation, and stale-data cases covered?
- Are common tests free of JUnit-only APIs?
- Are platform tests isolated to platform source sets?

## Refactor Gates

- Single source of truth after the change.
- No old/new parallel paths without flag and removal plan.
- Regression test for the motivating issue.
- Idempotency for duplicate events/callbacks.
- Redacted logs for high-risk state transitions when useful.
