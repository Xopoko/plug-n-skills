# KMP Build Governance

## Review Dimensions

- Shared build logic: role-based convention plugins for repeated setup.
- Build-logic location: prefer explicit `build-logic/` included builds for larger projects; `buildSrc/` is acceptable but can slow sync in large builds.
- Version catalogs: central plugin and dependency coordinates.
- Settings governance: `pluginManagement`, `dependencyResolutionManagement`, and repository policy.
- Module dependency hygiene: prefer `implementation`; use `api` only for exposed consumer types.
- Source-set correctness: common dependencies are truly common.
- Stack choices: DI, database, obfuscation, codegen, and publishing are opt-in, not universal.

## Warning Signs

- Same Kotlin/Android/Compose setup copied across many modules.
- Repositories declared inside module build files.
- Many `api(...)` dependencies in shared modules.
- Root `shared`, `core`, or `common` modules that own unrelated responsibilities.
- Hardcoded version strings outside catalogs.
