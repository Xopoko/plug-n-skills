# munder-difflin external source audit

## Source identity

- Repository: <https://github.com/chaitanyagiri/munder-difflin>
- Reviewed snapshot: commit `57a6ce65cb6d0b72bebd17a4b4ae92e60446c979`
- Git tree: `7c52501ecb2f0ddc4dad4a69601e2dfe8775b398`
- Review date: 2026-08-21
- Reviewer: `capability-workbench`
- Root license: MIT for source code
- Exception: `src/renderer/src/assets` contains LimeZu FREE VERSION artwork
  restricted to non-commercial use

The static review extracted one-writer handoff, atomic-log, circuit-breaker,
and false-completion fixture ideas. They remain future negative-test material;
no upstream instruction, Electron package, script, installer, hook, PTY, test,
or service was run.

Electron postinstall behavior, PTY and hook control, webhooks, telemetry,
tunneling, and approval-bypass modes were rejected. Bundled visual assets were
also excluded from distillation and remain outside this repository.

The dependency is `reference-only`. The license exception is recorded as
`LicenseRef-LimeZu-Free-NonCommercial`; installation, execution, vendoring, and
activation are disabled.
