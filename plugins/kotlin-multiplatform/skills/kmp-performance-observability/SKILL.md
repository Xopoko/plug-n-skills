---
name: kmp-performance-observability
description: Diagnose Kotlin Multiplatform performance and observability across Gradle build time, Kotlin/Native memory and GC, Compose Multiplatform jank, binary size, startup, runtime logging, and release-mode verification.
---

# KMP Performance/Observability

Use for: Compose jank, slow startup, Kotlin/Native memory pressure, binary size, Gradle build time, slow iOS framework builds, runtime observability, release-mode measurement.

## Loop

1. Measure symptom in representative mode.
2. Diagnose the named cause.
3. Make the smallest targeted change.
4. Verify on the same measurement surface.

Do not start by changing dependencies, compiler flags, or architecture.

## Surfaces

- Gradle: build scans/task timings, configuration/build cache, worker count, Kotlin/Native incremental compilation.
- Kotlin/Native: GC logs, memory-manager settings, `GC.lastGCInfo()`, binary options, framework export shape, `transitiveExport`.
- Compose: release-mode Android measurement, compiler metrics/reports, stability, recomposition tracing, lazy layout keys/content types, subcomposition, baseline profiles.
- iOS: framework size, Swift API shape, debug/release framework builds, Xcode integration path.
- Runtime: redacted logs, crash breadcrumbs, performance telemetry, cold-start/first-screen timing where observability already exists.
- Observability services: optional project choices, e.g. Datadog RUM, Sentry, Kotzilla, or Kermit. Evaluate target support, privacy policy, symbolication, sampling, and operational ownership before adding one.

## Guardrails

- `kotlin.native.binary.gc=noop` is diagnostic-only, not a production fix.
- `smallBinary` and aggressive binary options are project-specific experiments; measure before/after.
- Do not add hot-reload, tracing, stability analyzer, or performance plugins unless project already uses them or user asks.
- Do not benchmark debug Compose performance as production evidence.
- Do not add a third-party observability SDK for local-only performance diagnosis.

## Output

Report:

- symptom and measurement surface
- suspected cause
- changed file or proposed change
- verification command
- before/after evidence when available
- residual risk and what would measure it
