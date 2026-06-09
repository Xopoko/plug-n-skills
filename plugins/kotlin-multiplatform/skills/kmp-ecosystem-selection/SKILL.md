---
name: kmp-ecosystem-selection
description: Select Kotlin Multiplatform ecosystem libraries, services, and tools for persistence, networking, DI, navigation, logging, observability, testing, code quality, resources, images, docs, payments, and reference templates without forcing a stack.
---

# KMP Ecosystem Selection

Use this skill when choosing KMP libraries, services, tools, or starter kits.

## Decision Flow

1. Identify the configured targets and product constraints.
2. Check the repo's existing stack and do not replace a coherent local choice without a reason.
3. Verify current official docs or primary repository support for every configured target.
4. Compare runtime, build-time, API, licensing, operational, and team-maintenance costs.
5. Prefer the smallest dependency that solves the actual problem.

## Common Categories

- Persistence: Room KMP, SQLDelight, DataStore, Multiplatform Settings.
- Networking: Ktor Client or an existing generated/client stack.
- DI: Koin or local/manual DI when simpler.
- Navigation: Decompose, Voyager, Appyx, platform-native navigation, or existing local routing.
- Logging and crash reporting: Kermit, Napier, Crashlytics, Bugsnag, Sentry, CrashKiOS, NSExceptionKt.
- RUM and performance monitoring: Datadog RUM or an existing observability platform.
- Testing and quality: `kotlin.test`, Kotest, Turbine, Kover, Detekt, dependency guards.
- Resources and media: Compose resources, Moko Resources, Coil, local platform resources.
- Publishing/docs: Dokka, Maven publish plugins, KMMBridge, Fastlane, existing CI.
- Monetization: RevenueCat or platform-native store flows.
- Reference templates: KaMPKit, official samples, KMPShip-like starters as references, not copy sources.

## Rules

- Do not add a library because it is popular.
- Do not put unsupported dependencies in `commonMain`.
- Do not introduce a service SDK without privacy, data ownership, and operations review.
- Do not replace existing DI/navigation/database choices unless the task is specifically a migration.
- Treat experimental build systems such as Amper as research unless the user explicitly asks for adoption.

## Output

For each candidate, report:

- problem solved
- target support
- integration surface
- operational cost
- risks
- validation command
- adopt/defer/reject decision
