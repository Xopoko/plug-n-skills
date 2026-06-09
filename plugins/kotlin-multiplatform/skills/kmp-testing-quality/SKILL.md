---
name: kmp-testing-quality
description: Design and review KMP testing strategy, commonTest, kotlin.test, platform tests, Compose Multiplatform UI tests, screenshot tests, test doubles, refactor safety, code review gates, and regression validation.
---

# KMP Testing And Quality

Use this skill for KMP test strategy, `commonTest`, `kotlin.test`, platform tests, Compose Multiplatform UI tests, screenshot tests, test doubles, refactor safety, code review gates, and regression validation.

## Test Strategy

Prefer confidence and speed over coverage vanity:

- Many shared/unit tests.
- Fewer integration tests.
- Fewer UI/end-to-end tests than lower-level tests.
- Behavior-focused assertions.
- Deterministic test data and fake dependencies.

## KMP Test Placement

- Shared business logic belongs in `commonTest` first.
- Shared tests should use `kotlin.test` APIs, not JUnit-only APIs.
- Android framework behavior belongs in Android-specific local or instrumented tests.
- Robolectric is Android-only and never belongs in `commonTest`.
- iOS/native behavior should be validated with native target tasks or Xcode when the behavior is not shared.
- Compose shared UI tests should focus on semantics and observable behavior.
- Compose Multiplatform UI tests should use the current Compose testing API and target-specific setup. Verify source-set and dependency instructions against current docs before editing Gradle files.

## What To Test First

- Business rules.
- DTO/domain/UI mapping.
- Repository coordination logic.
- State-holder transitions.
- Error, retry, cancellation, and stale-data behavior.
- Navigation decisions and one-shot effects where important.
- Migration or refactor regressions.
- Security-sensitive flows: token refresh, logout, stale credentials, redaction, and retry loop guards.
- Performance-sensitive state reducers and mappers where regressions are cheap to catch with deterministic tests.

## Test Doubles

- Prefer fakes for repositories and data sources.
- Use stubs for simple fixed responses.
- Use mocks only when interaction is the behavior under test.
- Avoid real network, real stores, real clocks, and real platform services unless the test is explicitly integration-level.

## Refactor Safety

For refactors and migrations:

- Keep scope narrow.
- Do not leave old and new paths active without a feature flag and removal plan.
- Preserve public contracts unless the goal requires a breaking change.
- Move in phases: foundation, adoption, lock-in, cleanup.
- Add regression tests for the motivating failure.
- Make duplicate callbacks and retries idempotent.
- Add redacted observability around high-risk transitions when useful.

## Review Output

Lead with:

- missing high-signal tests
- brittle or misplaced tests
- slow/flaky test risks
- platform mismatch in test source sets
- exact commands to validate
- residual risk if platform tests cannot run locally
