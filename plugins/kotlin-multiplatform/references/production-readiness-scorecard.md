# Production Readiness Scorecard

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

Use for KMP release decisions and broad audits — a decision aid, not a replacement for running the relevant Gradle, platform, or release commands.

## Areas

| Area | Ready Evidence | Blockers |
| --- | --- | --- |
| Project structure | settings file, version catalog, coherent modules, no mixed app/KMP module | missing settings, KMP mixed with Android app plugin, legacy source layout |
| Build governance | centralized plugin/repository policy, convention build logic when useful, API exposure is intentional | module-local repositories, broad public API, dependency target mismatch |
| Testing quality | `commonTest` uses `kotlin.test`, platform tests live in platform source sets, Compose UI tests where relevant | JUnit/Robolectric in `commonTest`, missing high-signal tests |
| iOS/native interop | explicit framework linkage, bundle IDs, cinterop definitions, Swift API review | missing cinterop definition, accidental transitive export, unclear SwiftPM metadata |
| Security/privacy | secrets behind platform-backed storage, redacted logging, refresh loop guard | token literals in common code, platform storage in `commonMain`, unsafe logs |
| Performance/observability | measured release-mode path, Native/Compose diagnostics, build cache policy | GC disabled, no measurement surface, debug-only evidence |
| Publishing/release | artifact matrix, ABI gate where needed, SwiftPM/KMMBridge validation, dry run | publishing without ABI/metadata validation, unsigned or unowned release boundary |

## Inspector

Run:

```bash
python3 "$PLUGIN_ROOT/scripts/kmp_inspector.py" --root <project-root> --json --fail-on none
```

Use the `readiness` array as a first-pass scorecard. The final verdict should still account for commands the inspector cannot run.
