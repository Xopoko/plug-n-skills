# RTK external source audit

## Source identity

- Repository: <https://github.com/rtk-ai/rtk>
- Reviewed snapshot: commit `29f9bb7161775cd807565fd3041eb2b7d1be071c`
- Git tree: `deedf05df34a2e415a6cdc468ec8ae5d41c96276`
- Review date: 2026-08-21
- Reviewer: `capability-workbench`
- Root license: Apache-2.0, with no recorded exceptions

Static inspection supplied a failures-first, deterministic-output-projection
signal. Local behavioral evaluation rejected model-generated semantic
projection and retained only an independently authored contiguous
exact-duplicate helper with complete raw fallback. No RTK binary, installer,
hook, test, or command wrapper was run.

Global command interception, fail-open agent integration, default tracking, and
raw-output tee persistence were rejected. The first-party helper does not
import RTK code and does not intercept commands.

The dependency is `reference-only`; installation, execution, vendoring, and
activation are disabled, and later revisions require a new review.
