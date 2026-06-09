# Ecosystem Selection

This reference is a shortlist of common KMP ecosystem categories. It is not a default stack.

## Selection Rule

Choose tools by configured targets, existing architecture, maintenance cost, and validation evidence. Verify current docs or primary repository support before editing Gradle files.

## Categories

| Category | Examples | Main Risk |
| --- | --- | --- |
| Persistence | Room KMP, SQLDelight, DataStore, Multiplatform Settings | target support, migrations, threading |
| Networking | Ktor Client, generated clients | auth, retries, TLS, platform engines |
| DI | Koin, manual DI | startup cost, testability, lifecycle |
| Navigation | Decompose, Voyager, Appyx, platform-native | lifecycle mismatch, deep links |
| Logging/crash | Kermit, Napier, Crashlytics, Bugsnag, Sentry, CrashKiOS, NSExceptionKt | privacy, symbolication, noise |
| RUM/perf | Datadog RUM, existing telemetry | data policy, sampling, ownership |
| Testing/quality | `kotlin.test`, Kotest, Turbine, Kover, Detekt | slow CI, false confidence |
| Resources/images | Compose resources, Moko Resources, Coil | platform packaging, memory |
| Publishing/docs | Dokka, Maven publish plugins, KMMBridge, Fastlane | credentials, release mistakes |
| Monetization | RevenueCat, platform-native stores | entitlement sync, store review |

## Decision Labels

- adopt: target support verified and cost is justified.
- defer: plausible, but current task does not need it.
- reject: target mismatch, high operational cost, or conflicts with existing stack.
