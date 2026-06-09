# Performance And Observability

## Measure First

Use a Measure -> Diagnose -> Fix -> Verify loop. Record the measurement surface before changing code or Gradle flags.

## Gradle And Kotlin/Native

- Check build cache and configuration cache policy.
- For native projects, verify whether `kotlin.incremental.native=true` is appropriate.
- Use shared `konan.data.dir` only when the team understands cache ownership and CI behavior.
- Treat release native builds as inherently slower than debug builds.

## Kotlin/Native Memory

- GC logs can be enabled with `-Xruntime-logs=gc=info` for diagnostics.
- `kotlin.native.internal.GC.lastGCInfo()` can support leak investigation.
- `kotlin.native.binary.gc=noop` is diagnostic-only; it can increase memory consumption.
- Binary options such as `smallBinary` or allocator settings require before/after measurement.

## Compose

- Measure release-like Android builds when Android performance is affected.
- Use Compose compiler metrics/reports and stability evidence for recomposition problems.
- Inspect lazy layout keys, content types, subcomposition, state read phase, and stability before changing architecture.
- Baseline profiles and macrobenchmarks are Android-specific gates; do not represent iOS/Desktop performance.

## Native Binary Export

- Review `export(...)` and `transitiveExport=true` because exported dependencies affect public API, binary size, and compile time.
- Verify framework linkage and consumer import behavior after changes.

## Observability

Crash reporting, RUM, and logging are operational choices. Before adopting a service or library, verify target support, symbolication on Apple platforms, privacy redaction, sampling, ownership, and the team's incident workflow.
