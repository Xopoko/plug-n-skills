---
name: kmp-compose-ui
description: Build and repair Compose Multiplatform UI, state, navigation, resources, platform entry points, previews, performance, accessibility, and UI tests in Kotlin Multiplatform projects.
---

# Compose Multiplatform UI

Use for Compose Multiplatform UI: screens, shared UI architecture, Android/iOS/Desktop/Web entry points, Compose resources, navigation, state modeling, previews, performance, accessibility, UI tests.

## Context First

Before UI changes:

1. Identify whether UI is shared by all client platforms or only some.
2. Read existing screen, route, ViewModel/state holder, theme, resources, navigation convention.
3. Verify Compose Multiplatform and Compose compiler setup before adding APIs/dependencies.
4. Preserve coherent existing MVI/MVVM/Redux/Decompose/Voyager/platform-native navigation.

## UI Boundary

Recommended shared Compose UI split:

- Route: gets state holder, collects state/effects, wires platform navigation/snackbar/permissions/lifecycle.
- Screen: stateless renderer for state plus callbacks.
- Leaf composables: small visual renderers with only visual-local state: scroll, focus, expansion, animation.
- State holder/ViewModel: owns business state transitions, async work, repositories, one-shot effects.

- Do not run network calls from composables.
- Do not store controllers, lambdas, `MutableState`, Android `Context`, UIKit objects, or platform handles in durable screen state.

## Platform Entry Points

Use local project convention; common patterns:

- Android: app module calls `setContent { App() }` from Activity.
- iOS shared UI: expose a `ComposeUIViewController { App() }` facade from an iOS source set.
- Desktop: app module opens Compose window and calls shared UI.
- Web/Wasm: web app module owns bootstrap and calls shared UI.

Do not put Android application packaging or launch configuration inside shared KMP library module for AGP 9+ work.

## Resources

- Use Compose Multiplatform resources for shared strings/images/files in shared UI.
- Use Android resources only for Android app-shell concerns or Android-specific integration.
- Treat `group`/package changes carefully; resource accessor namespaces can change.
- Keep strings localizable.
- Avoid hardcoded user-facing copy in composables.

## State And Effects

- Separate editable raw input from parsed/validated business values.
- Keep state immutable and equality-friendly.
- Derive values instead of storing duplicates when possible.
- Use one-shot effects for navigation/snackbar/share/permission request/platform intents.
- Preserve prior content during refresh unless product requirements say otherwise.

## Performance And Accessibility

- Use Measure -> Diagnose -> Fix -> Verify loop.
- Do not optimize from intuition when release-mode measurement path exists.
- Fix state shape/read boundaries first; API-level micro-optimizations come second.
- Pass narrow props to leaf composables.
- Key lazy items by stable domain IDs.
- For lazy layouts, verify stable keys, meaningful content types, item composable skippability before changing prefetch or cache windows.
- For recomposition issues, inspect state read phase, stability, Compose compiler reports, runtime recomposition evidence before rewriting UI.
- Measure startup and frame timing in release-like Android builds when Android is affected.
- Treat debug Compose performance as non-representative.
- Add semantics for icon-only controls and custom components.
- Keep touch targets and text scaling usable across platforms.
- Avoid platform-specific assumptions in shared UI unless guarded by source set or interface.
- On iOS, verify accessibility tree synchronization mode when accessibility behavior or performance is in scope.
- Use `testTag`/accessibility identifiers intentionally when native XCTest or platform automation must find shared Compose UI.

## Testing

- Test state holders and reducers in `commonTest`.
- Test validators and formatters as pure functions.
- Use Compose UI tests in source set supported by project and current Compose version.
- For Compose Multiplatform UI tests, verify current dependency/source-set setup in official docs before adding `ui-test` dependencies.
- For iOS accessibility-sensitive work, consider XCTest `performAccessibilityAudit` when platform test harness exists.
- For platform entry wiring, run the platform app or screenshot path where practical.
