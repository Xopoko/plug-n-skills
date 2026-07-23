---
name: kmp-compose-ui
description: Build and repair Compose Multiplatform UI, state, navigation, external URI effects, resources, platform entry points, previews, performance, accessibility, and UI tests in Kotlin Multiplatform projects.
---

# Compose Multiplatform UI

Use this skill for Compose Multiplatform screens, shared UI architecture, Android/iOS/Desktop/Web entry points, Compose resources, navigation, external URI effects, state modeling, previews, performance, accessibility, and UI tests.

## Context First

Before changing UI:

1. Identify whether the project shares UI across all client platforms or only some.
2. Read the existing screen, route, ViewModel/state holder, theme, resources, and navigation convention.
3. Verify Compose Multiplatform and Compose compiler setup before adding APIs or dependencies.
4. Preserve existing MVI, MVVM, Redux, Decompose, Voyager, or platform-native navigation if coherent.

## UI Boundary

Recommended split for shared Compose UI:

- Route: obtains state holder, collects state/effects, wires platform navigation, snackbar, permissions, and lifecycle.
- Screen: stateless renderer with state plus callbacks.
- Leaf composables: small renderers with only visual-local state such as scroll, focus, expansion, or animation.
- State holder/ViewModel: owns business state transitions, async work, repositories, and one-shot effects.

Do not run network calls from composables. Do not store controllers, lambdas, `MutableState`, Android `Context`, UIKit objects, or platform handles in durable screen state.

## Platform Entry Points

Use the local project convention. Common patterns:

- Android: app module calls `setContent { App() }` from an Activity.
- iOS shared UI: expose a `ComposeUIViewController { App() }` facade from an iOS source set.
- Desktop: desktop app module opens a Compose window and calls shared UI.
- Web/Wasm: web app module owns bootstrap and calls shared UI.

Do not put Android application packaging or launch configuration inside the shared KMP library module for AGP 9+ work.

## Resources

- Use Compose Multiplatform resources for shared strings, images, and files when UI is shared.
- Use Android resources only for Android app-shell concerns or Android-specific integration.
- Treat `group` and package changes carefully: resource accessor namespaces can change.
- Keep strings localizable and avoid hardcoded user-facing copy in composables.

## State And Effects

- Model editable raw input separately from parsed/validated business values.
- Keep state immutable and equality-friendly.
- Derive values instead of storing duplicates when possible.
- Use one-shot effects for navigation, snackbar, share, permission request, and platform intents.
- Preserve previous content during refresh unless product requirements say otherwise.

## External URI Effects

- Treat URI opening as a one-shot route/platform effect. Collect it from a
  stable lifecycle-aware owner; do not open from the composable body or
  `SideEffect`. Inject a narrow opener; never retain a platform handler in
  durable state.
- `LocalUriHandler.openUri` and default `LinkAnnotation.Url` opening are
  best-effort. Use an app-owned adapter and annotated-link listener when policy,
  telemetry, fallback, or an explicit outcome matters.
- Preserve the original URI, including product-supported custom schemes. Apply
  per-scheme policy at the trust boundary; do not blindly rewrite custom
  schemes to HTTP(S).
- Read [External URI Effect Contract](references/external-uri-effects.md) before
  implementing adapter outcomes, replay behavior, validation, telemetry, or
  failure tests.

## Performance And Accessibility

- Use a Measure -> Diagnose -> Fix -> Verify loop. Do not optimize from intuition when a release-mode measurement path is available.
- First fix state shape and read boundaries; API-level micro-optimizations come second.
- Pass narrow props to leaf composables.
- Key lazy items by stable domain IDs.
- For lazy layouts, verify stable keys, meaningful content types, and item composable skippability before changing prefetch or cache windows.
- For recomposition issues, inspect state read phase, stability, Compose compiler reports, and runtime recomposition evidence before rewriting UI.
- Measure startup and frame timing in release-like Android builds when Android is an affected target; debug Compose performance is not representative.
- Add semantics for icon-only controls and custom components.
- Keep touch targets and text scaling usable across platforms.
- Avoid platform-specific assumptions in shared UI unless guarded by source set or interface.
- On iOS, verify accessibility tree synchronization mode when accessibility behavior or performance is in scope.
- Use `testTag`/accessibility identifiers intentionally when native XCTest or platform automation must find shared Compose UI.

## Testing

- Test state holders and reducers in `commonTest`.
- Test validators and formatters as pure functions.
- Use Compose UI tests in the source set supported by the project and current Compose version.
- For Compose Multiplatform UI tests, verify current dependency/source-set setup in official docs before adding `ui-test` dependencies.
- For iOS accessibility-sensitive work, consider XCTest `performAccessibilityAudit` when the platform test harness exists.
- For platform entry wiring, run the platform app or screenshot path where practical.
