---
name: kmp-production-readiness
description: Audit Kotlin Multiplatform production readiness with explicit scorecards, release blockers, risk ownership, validation commands, and deferred checks across architecture, build, testing, interop, security, performance, and publishing.
---

# KMP Production Readiness

Use `$PLUGIN_ROOT` for plugin root. Set it once from the host plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise to this plugin root's absolute path. Works in any host agent, including Codex, Claude, and Cursor.

Use for full KMP production readiness audits, release-blocker triage, readiness scorecards, executive summaries, and multi-area risk reviews.

## Flow

1. Inspect project structure, Gradle files, version catalog, `gradle.properties`, CI files, release scripts, and platform app shells.
2. Run:
   ```bash
   python3 "$PLUGIN_ROOT/scripts/kmp_inspector.py" --root <project-root> --json --fail-on none
   ```
3. Classify the project:
   - app-only shared code
   - internal mobile shared library
   - public KMP library
   - shared Compose UI app
   - mixed native UI plus shared logic
   - monorepo with multiple KMP modules
4. Map evidence to readiness areas:
   - project structure
   - build governance
   - testing quality
   - iOS/native interop
   - security/privacy
   - performance/observability
   - publishing/release

## Verdict Rules

- `ready`: area has no release-blocking gaps, validation commands exist, and residual risk is explicit.
- `watch`: shippable with known risk, owner, and follow-up command.
- `blocked`: missing validation, unsafe config, public API/publishing uncertainty, secret/security risk, or platform integration failure.

Do not average away a blocker; one blocked area can block the overall verdict.

## Output

Lead with:

- overall verdict
- blocked areas and exact blockers
- readiness scorecard
- validation commands already run
- validation commands still required
- release owner decisions needed
- deferred checks and why they are acceptable or not acceptable
