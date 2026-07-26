---
name: kmp-testing-quality
description: Design and review KMP testing strategy, commonTest, kotlin.test, platform tests, Compose Multiplatform UI tests, screenshot tests, test doubles, refactor safety, code review gates, and regression validation.
---

# KMP Testing And Quality

Use for KMP test strategy/review: `commonTest`, `kotlin.test`, platform tests, Compose Multiplatform UI tests, screenshot tests, test doubles, refactor safety, code review gates, regression validation.

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same
path suffix). Set it once from the host's plugin-root variable when available,
or to this plugin's absolute root path.

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
- Keyboard and D-pad tests should exercise real interactive controls and the
  owning target's input mode, not synthetic focus targets added by the fixture.
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
- Freeze each required platform leaf's JUnit XML selector and retained
  artifact/report path. After execution, reconcile the required, executed,
  reported, and retained leaf sets; accept only the current job's nonzero,
  parseable JUnit files, reject stale pre-existing results, and fail any set
  mismatch. A trace without retained, inspectable results proves scheduling
  only.
- When changing a fixture or assertion to prove a new claim, inventory the
  existing regression claims first. Preserve them with explicit pre/post
  assertions or separate tests; do not trade one proof obligation for another.
- For exactly-once event claims, assert cardinality across creation,
  restoration, resume, and re-collection as applicable. Idempotency alone does
  not prove exactly-once delivery.

## Keyboard And D-pad Focus

- Define the user-visible focus sequence before editing the fixture: start,
  forward/reverse destinations, boundaries, skipped disabled or hidden nodes,
  and activation callbacks.
- Seed focus on an existing interactive control. Prefer the target test API's
  focus request; otherwise attach a narrow requester seam to that same control
  inside the test host. Do not add blank focusable sentinels, wrapper endpoints,
  or test-only controls that change the graph being tested.
- Request and verify keyboard input mode when the target requires it; a rejected
  mode request is not proof. Inject the real key sequence with the current
  Compose test API and assert each actual destination. Preserve the real
  callbacks and assert their observable counts when activation is part of the
  claim.
- Treat the effective default traversal as the baseline. Simple
  one-dimensional layouts often follow declaration order, while focus groups,
  scrolling, visibility, and parent properties can change the graph. Use
  `focusProperties` only for an intentional product contract, never as a patch
  that makes a test pass.
- Keep interaction and rendering proof separate: a screenshot cannot prove
  keyboard traversal, while a focus assertion cannot prove visual meaning.
- Bind the receipt to exact source bytes, source set, target, leaf test task,
  and non-empty result: use clean-at-SHA for committed delivery, or a base
  revision plus an affected-file manifest/content hash covering staged,
  unstaged, and relevant untracked bytes, explicitly marked uncommitted. Never
  clean, commit, stash, or overwrite user work without authority. One target
  does not prove focus parity elsewhere.
- Keep modality claims separate. A Tab or arrow-key test does not prove rotary
  or analog-controller input; use the owning target's input API and receipt.

Use `../../references/compose-focus-testing.md` for fixture rules, a test
sequence, failure triage, and exact evidence requirements.

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

## Screenshot Goldens In CI

When CI records or refreshes screenshot baselines, local rendering is blocked,
or a baseline arrives as an artifact:

- Discover the project's actual record, compare, and verify tasks; do not invent
  task names.
- Treat record as baseline-mutating, compare as diagnostic, and verify as
  read-only. A mode that verifies and then records is not final proof.
- Bind candidates to the exact source revision, sanitized rendering inputs,
  task, target, test filter, payload manifest, and post-upload provider receipt.
- Before opening an artifact, run the bundled `golden_artifact_guard.py`
  against its exact PNG allowlist and require an `accepted` receipt. The guard
  does not download, extract, or authorize a visual change.
- Import only the expected file set; review additions, modifications, and
  deletions, and remove generator-only configuration before acceptance.
- After accepted goldens are committed, rerun non-recording verification on
  that exact final head and the complete affected target. Retain mismatch and
  infrastructure diagnostics.
- Give every baseline writer unique path ownership; serialization alone is not
  isolation. Never infer cross-platform pixel parity from one renderer.

Use `../../references/screenshot-golden-ci.md` for the full evidence, cleanup,
failure, filtered-run, and final-head contract.

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
