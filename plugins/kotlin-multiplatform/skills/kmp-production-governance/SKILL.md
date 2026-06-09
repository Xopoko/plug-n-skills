---
name: kmp-production-governance
description: Review Kotlin Multiplatform production readiness, build governance, convention plugins, version catalogs, repository policy, module API hygiene, Klibs target support, ABI validation, publishing, and adoption risk.
---

# KMP Production Governance

Use this skill for KMP build governance, production-readiness review, convention plugins, version catalogs, repository policy, module dependency hygiene, public API surface, library publishing, ABI validation, Klibs target support, and adoption risk.

## Review Flow

1. Read `settings.gradle(.kts)`, version catalogs, root build files, build-logic/buildSrc, module build files, and publishing configuration.
2. Run:
   ```bash
   python3 ../../scripts/kmp_inspector.py --root <project-root>
   ```
   Use `--json --fail-on none` when you need the readiness scorecard for a report.
3. Classify project role:
   - app-only shared code
   - internal shared mobile library
   - public KMP library
   - monorepo with many KMP modules
   - mixed native and shared UI application
4. Review governance before changing features.

## Build Governance Dimensions

- Shared build logic: repeated module setup should move into role-based convention plugins when repetition is meaningful.
- Convention plugin boundary: keep role setup clear, not a dumping ground for stack choices.
- Version catalogs: centralize versions and aliases; avoid drift in module build files.
- Plugin management: centralize plugin resolution and repository policy in settings.
- Repository policy: avoid module-local repositories unless there is a documented reason.
- Module dependency hygiene: prefer `implementation`; use `api` only when consumers need exposed types.
- Public surface: keep shared/core modules small and intentional.
- Stack leakage: DI/database/obfuscation/publishing choices should not become universal defaults without product need.

## Dependency Target Verification

Before recommending a library:

- Check official docs first.
- Use Klibs.io as a human verification surface for KMP target support when helpful.
- Confirm Maven coordinates and target variants.
- Fill the target matrix mentally or in notes: Android, iOS device, iOS simulator, JVM/Desktop, JS/Wasm, Native host targets.
- If any configured target is unsupported, keep the dependency out of `commonMain`.

## Library Release Gates

For published KMP libraries, consider:

- API ownership: which packages/classes are public and stable.
- ABI validation: Kotlin Gradle Plugin `abiValidation`, `checkKotlinAbi`, and `updateKotlinAbi` when appropriate.
- Publication shape: Maven publications, Android target artifacts, iOS XCFramework or SwiftPM export.
- Unsupported target behavior: know whether ABI inference for locally unsupported targets is acceptable.
- Release notes: document source, binary, and Swift API compatibility impact.

Do not force ABI validation on private app modules. It is most useful when downstream consumers compile against your library.

## Output

For reviews, lead with:

- production readiness verdict
- readiness scorecard areas from the inspector when available
- high/medium/low issues
- build governance gaps
- dependency target-support risks
- release/API risks
- exact validation commands
- deferred checks and why
