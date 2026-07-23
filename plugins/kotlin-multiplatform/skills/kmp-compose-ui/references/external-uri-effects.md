# External URI Effect Contract

Use this contract when shared Compose UI opens a browser, another application,
or a product-supported custom scheme and the caller needs policy, telemetry,
fallback, or a reliable launch-request outcome.

## Effect Delivery

- Collect the effect from a stable lifecycle-aware route owner. Never open a
  URI from the composable body or `SideEffect`.
- Give each effect identity and choose the acknowledgement policy explicitly.
  Acknowledging before open is at-most-once but can lose the action.
  Acknowledging after open can replay across cancellation or collector restart.
  Opening and acknowledgement are not atomic.
- Inject a narrow opener or callback. Do not retain `UriHandler`, Android
  `Context`, UIKit objects, or another platform handle in durable screen state.
- For `LinkAnnotation.Url`, provide a `linkInteractionListener` and route the
  click through the same opener when policy, telemetry, fallback, or outcome
  matters. The default path is only best-effort.

## Outcome Model

Use an app-owned result such as:

- `accepted`: the operating system accepted the launch request;
- `unsupported`: no handler is available for the allowed URI;
- `rejected`: the URI fails product trust policy;
- `failed`: an ordinary platform error prevented request acceptance.

Do not call `accepted` success. Android does not expose destination completion,
and the iOS completion callback still does not prove that the destination
finished its action.

Treat capability preflight as a hint, not authoritative rejection. Android
package visibility and iOS queried-scheme declarations can produce false
negatives. If product policy deliberately makes preflight a gate, classify the
negative result as a conservative policy rejection, not `unsupported`, and
document the false-negative risk. Prefer the actual launch result or failure.

## Native Adapter Rules

- Android: use an Activity-capable context or add
  `FLAG_ACTIVITY_NEW_TASK`. Map no-handler and security failures instead of
  crashing shared UI.
- iOS: create a valid URL, call the open API on the main thread, and classify
  its asynchronous Boolean result.
- Rethrow `CancellationException` before mapping ordinary exceptions to
  `failed`. Do not catch fatal errors.
- Verify behavior against the project's pinned Compose version. The common
  `LocalUriHandler.openUri` contract returns no result; target implementations
  can throw or fail silently.

## Trust And Telemetry

- Preserve the original URI, including product-supported custom schemes. Do
  not normalize every target to HTTP(S).
- Define policy per scheme and validate every action-bearing component:
  userinfo, host, port, path, query, and fragment. Permissive platform parsing
  is not trust validation.
- Log only allowlisted scheme, host, and result metadata. Omit userinfo, path,
  query, and fragment, which can contain secrets or personal data.
- Never report an exception-free, result-less common `LocalUriHandler` call or
  a swallowed failure as `accepted`. A successful native Android launch return
  or positive iOS completion result can support request acceptance.

## Verification Matrix

Cover:

- accepted request on the normal path;
- unsupported handler and security failure;
- malformed or policy-rejected input;
- exact original string delivery to the app-owned adapter plus policy-approved
  native parsing of an allowed custom scheme;
- annotated-link interception;
- throwing handler and silent best-effort failure;
- capability-preflight false negative that does not block an actual launch;
- optional policy-gated preflight classified as conservative rejection;
- Android Activity and application-context-with-new-task launch branches, plus
  application context without the required flag prevented or surfaced;
- negative iOS completion result;
- coroutine cancellation;
- recomposition without a duplicate open;
- replay and collector restart under the documented acknowledgement policy.

Use fakes at the app-owned seam. Add native adapter tests where platform result
mapping is implemented.

## Primary API Anchors

- [Compose `UriHandler`](https://developer.android.com/reference/kotlin/androidx/compose/ui/platform/UriHandler)
- [Compose `LinkAnnotation.Url`](https://developer.android.com/reference/kotlin/androidx/compose/ui/text/LinkAnnotation.Url)
- [Android `Context.startActivity`](<https://developer.android.com/reference/android/content/Context#startActivity(android.content.Intent)>)
- [Android package visibility use cases](https://developer.android.com/training/package-visibility/use-cases)
- [Apple open URL API](https://developer.apple.com/documentation/uikit/uiapplication/open(_:options:completionhandler:))
- [Apple custom URL schemes](https://developer.apple.com/documentation/xcode/defining-a-custom-url-scheme-for-your-app)
