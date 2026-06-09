# Gradle And Android-KMP Guardrails

## Android-KMP Library Plugin

For KMP library modules targeting Android on AGP 9+:

- Apply `org.jetbrains.kotlin.multiplatform`.
- Apply `com.android.kotlin.multiplatform.library`.
- Configure Android inside `kotlin { android { ... } }`.
- Expect one Android variant.
- Enable resources, Java, and tests explicitly.
- Use source-set dependencies for ordinary dependencies.
- Use Android runtime classpath only for special runtime-only tooling when docs confirm it.

## Migration Risks

- `com.android.application` plus KMP in one module is not an AGP 9+ path.
- Top-level `android {}` leftovers often mean the module is half-migrated.
- `debugImplementation` and flavors/build types do not map cleanly to the single-variant KMP library plugin.
- `androidUnitTest` and `androidInstrumentedTest` names may need host/device test migration.
- Java sources need explicit Java compilation.
- Android resources need explicit opt-in.

## Version Policy

Do not guess versions. Check the version catalog and official docs. If a migration requires version movement, keep it as a separate, validated step where possible.
