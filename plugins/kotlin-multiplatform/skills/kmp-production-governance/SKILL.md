---
name: kmp-production-governance
description: Review Kotlin Multiplatform production readiness, build governance, convention plugins, version catalogs, repository policy, module API hygiene, Klibs target support, ABI validation, publishing, and adoption risk.
---

# KMP Production Governance

Commands use `$PLUGIN_ROOT`. Set once from the host plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), else this plugin root's absolute path. Works under any host agent, including Codex, Claude, Cursor.

Use for KMP build governance/production-readiness review of convention plugins, version catalogs, repository policy, module dependency hygiene, public API surface, library publishing, ABI validation, Klibs target support, adoption risk.

## Review

1. Read `settings.gradle(.kts)`, version catalogs, root/module build files, build-logic/buildSrc, publishing config.
2. Run:
   ```bash
   python3 "$PLUGIN_ROOT/scripts/kmp_inspector.py" --root <project-root>
   ```
   Use `--json --fail-on none` when reports need readiness scorecards.
3. Classify role:
   - app-only shared code
   - internal shared mobile library
   - public KMP library
   - many-module KMP monorepo
   - mixed native/shared UI app
4. Review governance before feature work.

## Build Governance

- Shared build logic: move meaningful repetition to role-based convention plugins.
- Convention plugin boundary: keep role setup clear; do not make it a stack-choice dump.
- Version catalogs: centralize versions/aliases; avoid module build-file drift.
- Plugin management: centralize plugin resolution/repository policy in settings.
- Repository policy: avoid module-local repositories unless documented.
- Module dependency hygiene: prefer `implementation`; use `api` only for consumer-exposed types.
- Public surface: keep shared/core modules small/intentional.
- Stack leakage: DI/database/obfuscation/publishing should not become universal defaults without product need.

## Dependency Targets

Before recommending a library:

- Check official docs first.
- Use Klibs.io for human target-support checks when helpful.
- Confirm Maven coordinates/target variants.
- Fill the target matrix mentally/in notes: Android, iOS device, iOS simulator, JVM/Desktop, JS/Wasm, Native host targets.
- Keep dependencies unsupported by any configured target out of `commonMain`.

## Release Gates

For published KMP libraries, consider:

- API ownership: identify stable public packages/classes.
- ABI validation: Kotlin Gradle Plugin `abiValidation`, `checkKotlinAbi`, `updateKotlinAbi` when appropriate.
- Publication shape: Maven publications, Android target artifacts, iOS XCFramework/SwiftPM export.
- Unsupported target behavior: decide if ABI inference for locally unsupported targets is acceptable.
- Release notes: document source/binary/Swift API compatibility impact.

Do not force ABI validation on private app modules. It is most useful when downstream consumers compile against your library.

## Output

For reviews, lead with:

- production readiness verdict
- inspector readiness scorecard areas when available
- high/medium/low issues
- build governance gaps
- dependency target-support risks
- release/API risks
- exact validation commands
- deferred checks and why
