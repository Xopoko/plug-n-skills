# KMP Source-Set Architecture

## Default Preference

Prefer the Kotlin Gradle plugin default hierarchy template unless the project has a real non-default sharing need. Manual `dependsOn()` edges can disable the default template and should be intentional.

## Placement

| Code or dependency | Default home |
| --- | --- |
| Pure domain logic | `commonMain` |
| Shared presentation state | `commonMain` |
| Android SDK, Activity, Manifest app concerns | Android app module or `androidMain` for library bindings |
| UIKit, Foundation, Darwin, cinterop bindings | `iosMain` or exact native source set |
| Compose shared UI | shared UI KMP module `commonMain` |
| Android-only Compose tooling | Android app module or Android source set |
| JVM/Desktop-only APIs | `jvmMain` or desktop source set |
| Tests for shared logic | `commonTest` |
| Android host/device tests | Android host/device test source sets configured by the plugin |

## Review Questions

- Does every `commonMain` dependency publish variants for all configured targets?
- Are platform APIs hidden behind interfaces or `expect/actual`?
- Is a source set shared only where its APIs are valid?
- Are target declarations present before source-set access?
- Does any manual hierarchy edge duplicate the default template?
