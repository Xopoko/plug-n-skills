# Compose Focus Traversal Testing

Use this reference when a Compose UI must support keyboard or D-pad focus
movement and the test needs to prove the order without changing the focus graph
it is meant to verify. Rotary and analog-controller input require separate,
modality-specific proof.

## Start With The Interaction Contract

Write the expected behavior in terms of user-visible controls:

- the real starting control;
- forward traversal destinations such as Tab;
- reverse traversal destinations such as Shift+Tab;
- two-dimensional destinations for arrow or D-pad input;
- wrap, stop, enter, exit, and restoration behavior where applicable;
- disabled, hidden, removed, or off-screen controls that must be skipped;
- activation behavior for Enter, Space, or the platform action key.

In simple one-dimensional layouts, Compose focus traversal usually follows the
real composable declaration order. That is not a universal ordering law:
`focusGroup()`, lazy or partially visible content, nested scopes, scrolling,
and parent focus properties can change the effective focus graph. Inspect that
graph before overriding it. Add `focusProperties` only when the product
contract intentionally changes the default; parent focus properties can
override descendant properties.

## Preserve The Real Focus Graph

Test the production focus graph, not a graph invented by the fixture.

- Use the same visible controls and hierarchy that the owning UI exposes.
- Prefer the target Compose test API's `requestFocus()` on the real semantics
  node when available.
- If a host fixture needs a `FocusRequester`, attach it to an existing
  interactive control. Keep the seam inside the test/preview host or an
  existing modifier parameter; do not widen production visibility or module
  APIs only for the test.
- Confirm the requester modifier is associated with the intended focus target
  by asserting that target is focused before sending input.
- Never add a blank `focusable()` sentinel, invisible wrapper endpoint, or
  test-only button merely to create a convenient start or destination. Such a
  node changes traversal order and lets the test prove its own fixture.
- Do not replace a full visual fixture with a reduced synthetic hierarchy when
  the claim includes scrolling, overlays, navigation, or hosted composition.

If no real control can receive initial focus, first decide whether that is the
product behavior under test. A test seam is not a substitute for a missing
user-reachable focus target.

## Execute Real Input

Use the APIs available in the project's pinned Compose version and target:

1. Render the faithful owning fixture and wait for its initial state.
2. Request keyboard input mode when the target requires it, then verify that
   the request succeeded or that the current mode is `InputMode.Keyboard`.
   If the target rejects the request, record the mode as unestablished and do
   not claim keyboard traversal proof.
3. Request focus on the real starting control and call `assertIsFocused()`.
4. Send the actual input with `performKeyInput`, for example
   `pressKey(Key.Tab)` for forward traversal.
5. Wait for idle only when focus movement, scrolling, or composition is
   asynchronous.
6. Call `assertIsFocused()` on the next real control.
7. Continue through the complete applicable sequence, including reverse and
   boundary behavior.
8. When activation is part of the claim, send a complete key press and assert
   the real callback or state transition. Avoid leaving a key-down state
   unfinished across assertions unless that state is itself under test.

Inject from the focused node or the root according to the target API and the
behavior being tested. The important boundary is that input reaches the real
focus system and assertions name actual user destinations.

A Tab or arrow-key receipt does not prove rotary or analog-controller input.
Use a rotary injection API such as `performRotaryScrollInput` when the pinned
target supports it, and use the owning target's controller input surface for
controller behavior. Keep those receipts separate from keyboard/D-pad proof.

For repeated or virtualized content, use stable semantic identity and prove
both the destination and the required scroll/reveal behavior. Do not infer
focus order from coordinates or a screenshot.

## Minimal Proof Shape

The exact syntax varies by Compose version, but a forward traversal test should
retain this shape:

```kotlin
start.requestFocus().assertIsFocused()
start.performKeyInput { pressKey(Key.Tab) }
next.assertIsFocused()
```

Request and verify keyboard input mode during fixture setup when required. Add
explicit assertions for disabled/hidden skips, reverse traversal, arrow/D-pad
movement, wrap or stop behavior, and activation only when those behaviors
belong to the screen's contract.

## Diagnose Failures Without Weakening The Test

| Symptom | Inspect before changing behavior |
| --- | --- |
| Nothing receives focus | Whether keyboard mode was established, fixture readiness, target focusability, requester attachment, and modifier order |
| Tab reaches the wrong node | Effective focus graph, `focusGroup()`, scrolling/visibility, synthetic nodes, parent `focusProperties`, and hosted wrappers |
| Test passes only with a wrapper or sentinel | The fixture changed the focus graph; move the seed to an existing control |
| Focus moves but action does not fire | Complete key press semantics, focused destination, callback wiring, and idle boundary |
| Screenshot is green but focus test fails | Keep the proofs separate; rendering does not establish keyboard interaction |
| One platform passes | Execute the owning target; do not infer Android, desktop, web, iOS, TV, or wearable parity |

Do not blindly retry a failing leaf task. Change the source, fixture, assertion,
configuration, or environment only after the failure identifies a new
testable hypothesis.

## Evidence And Handoff

Record:

- the delivered clean-at-SHA revision, or a base revision plus an affected-file
  manifest/content hash that covers staged, unstaged, and relevant untracked
  bytes and is explicitly marked uncommitted;
- exact source set, target, leaf task, and test filter;
- non-empty executed test count and failure/error/skip totals;
- the real start and destination controls covered;
- input mode and key sequence;
- any custom `focusProperties`, restoration, scrolling, or boundary behavior;
- separate screenshot or accessibility receipts when those claims also matter;
- target-specific gaps that remain unexecuted.

Do not clean, commit, stash, overwrite, or otherwise absorb existing user work
merely to manufacture a clean receipt. Stop at the uncommitted evidence
boundary unless the task grants the corresponding mutation authority.

A green aggregate task, a screenshot, or an assertion against a synthetic node
does not close the focus traversal claim.

## Public Sources

- [Focus in Compose](https://developer.android.com/develop/ui/compose/touch-input/focus)
- [Change focus traversal order](https://developer.android.com/develop/ui/compose/touch-input/focus/change-focus-traversal-order)
- [Keyboard focus management in Compose](https://developer.android.com/codelabs/large-screens/keyboard-focus-management-in-compose)
- [Compose key injection API](https://developer.android.com/reference/kotlin/androidx/compose/ui/test/KeyInjectionScope)
- [Testing Compose Multiplatform UI](https://kotlinlang.org/docs/multiplatform/compose-test.html)
- [Pinned real-control focus test example](https://github.com/android/large-screen-codelabs/blob/b303b534d3e712febe9490bb95872e75927d64a1/focus-management-in-compose/solution/src/androidTest/java/com/example/focusmanagementincompose/FocusTraversalOrderTabTest.kt)
