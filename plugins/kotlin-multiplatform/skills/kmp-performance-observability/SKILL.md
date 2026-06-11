---
name: kmp-performance-observability
description: Diagnose Kotlin Multiplatform performance and observability across Gradle build time, Kotlin/Native memory and GC, Compose Multiplatform jank, binary size, startup, runtime logging, and release-mode verification.
---

# KMP Performance And Observability

Use this skill for KMP performance work: Compose jank, slow startup, Kotlin/Native memory pressure, binary size, Gradle build time, slow iOS framework builds, runtime observability, and release-mode measurement.

## Loop

1. Measure the symptom in a representative mode.
2. Diagnose the named cause.
3. Make the smallest targeted change.
4. Verify with the same measurement surface.

Do not start by changing dependencies, compiler flags, or architecture.

## Surfaces

- Gradle: build scans, task timings, configuration cache, build cache, worker count, Kotlin/Native incremental compilation.
- Kotlin/Native: GC logs, memory manager settings, `GC.lastGCInfo()`, binary options, framework export shape, `transitiveExport`.
- Compose: release-mode Android measurement, compiler metrics/reports, stability, recomposition tracing, lazy layout keys/content types, subcomposition, baseline profiles.
- iOS: framework size, Swift API shape, debug vs release framework builds, Xcode integration path.
- Runtime: redacted logs, crash breadcrumbs, performance telemetry, cold-start and first-screen timing where the app already has observability.
- Observability services: Datadog RUM, Bugsnag, Sentry, Firebase Crashlytics, CrashKiOS, NSExceptionKt, Kotzilla, Kermit, or Napier are optional project choices. Evaluate target support, privacy policy, symbolication, sampling, and operational ownership before adding one.

## Guardrails

- Treat `kotlin.native.binary.gc=noop` as a diagnostic-only setting, not a production fix.
- Treat `smallBinary` and aggressive binary options as project-specific experiments with before/after measurement.
- Do not add hot-reload, tracing, stability analyzer, or performance plugins unless the project already uses them or the user asks for that tooling.
- Do not benchmark debug Compose performance as production evidence.
- Do not add a third-party observability SDK when the request only needs a local performance diagnosis.

## Output

For performance work, report:

- symptom and measurement surface
- suspected cause
- changed file or proposed change
- verification command
- before/after evidence when available
- residual risk and what would measure it
