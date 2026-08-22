# Caveman external source audit

## Source identity

- Repository: <https://github.com/JuliusBrussee/caveman>
- Reviewed snapshot: commit `2f49f0e1a352aa810e70056b7930aeb0b3d219b4`
- Git tree: `603ece15f092a82703cb6e86d102050502775f25`
- Review date: 2026-08-21
- Reviewer: `capability-workbench`
- License boundary: MIT by default, with Engine-linked directories under
  Business Source License 1.1 (`BUSL-1.1`)

Static inspection identified content-typed context records, exact-source
recovery, and evidence taxonomy as portable ideas. A separate first-party
repeated-compaction campaign then tested the relevant behavior; upstream code
was not installed, imported, executed, or used as the benchmark runtime.

The source change adopts only independently authored typed-state and recovery
contracts. Provider credentials, subprocess and installer paths, opt-out
telemetry, and the BSL engine/runtime are rejected. A general compression
runtime remains deferred.

The lock records the upstream per-directory BSL boundary and the MIT overrides
for the thin `mem/js` and `mem/py` clients. The pinned licensing map also
preserves third-party notice boundaries: MIT chromedp modules under `browse`,
and MIT, BSD-2-Clause, plus OFL-1.1/GPL font material under `engine/pixel`.
Nothing from those surfaces is vendored here, but their notices remain part of
the reviewed snapshot. The dependency is `reference-only`, with installation,
execution, vendoring, and activation disabled.
