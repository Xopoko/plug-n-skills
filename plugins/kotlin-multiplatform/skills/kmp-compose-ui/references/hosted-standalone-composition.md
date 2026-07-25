# Hosted And Standalone UI Composition

Use this contract when one Compose UI feature must remain a standalone route
and also render as content inside a larger host.

## Recover The Existing Contract

Before moving code, record:

- the standalone facade signature, defaults, wrapper order, callbacks, effects,
  and user-visible refresh behavior;
- the current scroll and pull-to-refresh owner for each gesture axis;
- only the semantics IDs, `testTag`s, or accessibility identifiers that are
  published or consumed by external automation;
- the tests that characterize the standalone entry and its observable behavior.

Do not treat every internal test tag or incidental semantics-tree detail as a
public contract.

## Composition Boundary

- Shared content renders state and emits callbacks without installing a
  competing same-axis scroll or pull-to-refresh owner. It accepts the narrow
  layout inputs the host legitimately controls.
- The standalone facade keeps its existing public shape and wrapper behavior,
  then delegates to the shared content.
- The host mounts the shared content inside the host-owned scroll and refresh
  boundary. Do not mount the standalone wrapper inside that boundary.
- Default to one owner per same-axis or gesture boundary. This is not a blanket
  ban on nesting: orthogonal scrolling or deliberately coordinated same-axis
  behavior is valid when axis, gesture priority, state handoff, and expected
  user behavior are explicit and interaction-tested.
- If the production host crosses a module boundary, expose only the narrow
  production API that the host needs. Never widen production visibility or
  dependency exposure solely so a test can reach implementation details.

## Compatibility Rules

- Preserve the standalone facade's source shape, defaults, and observable
  behavior unless a breaking change is an explicit goal.
- Preserve externally consumed semantics identifiers, their meaning, supported
  lookup, and expected cardinality in both entry contexts. Internal-only tags
  may evolve with their owning tests.
- Keep refresh ownership separate from refresh state. Moving the gesture
  container must not silently change callback cardinality, loading state,
  retained content, or error behavior.
- Compare the shared supported states, actions, callbacks, and effects through
  both entry points. Document and test every intentional context-specific
  difference instead of treating wrapper parity as feature parity.
- Test the same public embedding entry point that production uses. Keep
  lower-level implementation tests in the module or source set that owns the
  implementation.

## Parity Proof

Use semantics and interaction tests; a screenshot alone cannot prove gesture
ownership or callback behavior.

| Context | Required proof |
| --- | --- |
| Standalone | The existing public facade still renders, scrolls, and performs its pull-to-refresh behavior with the expected callback cardinality. |
| Hosted | The host-owned scroll and pull gesture remain usable, and the embedded content does not install a competing same-axis owner. |
| Shared feature behavior | Both entry points render every supported shared state and preserve reachable actions, callbacks, and effects; every intentional context-specific difference is documented and tested. |
| External semantics | Each published or externally consumed identifier has the supported meaning, lookup behavior, and expected cardinality in both contexts. |
| Public API and modules | Compile or API checks show the standalone contract is preserved, and dependency or visibility review shows no production boundary was widened only for tests. |
| Coordinated nesting exception | A focused interaction test proves the documented axes, gesture priority, state handoff, and boundary behavior. |

Characterize the standalone path before extraction, then run the relevant
standalone and hosted proof against the final source revision.
