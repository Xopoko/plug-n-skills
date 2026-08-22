# revfactory/harness external source audit

## Source identity

- Repository: <https://github.com/revfactory/harness>
- Reviewed snapshot: commit `cceac68ea1d0ad198ef4b7b906cd238375836387`
- Git tree: `b88c5ce9b73461bf6d92224863a9db91b6cedace`
- Review date: 2026-08-21
- Reviewer: `capability-workbench`
- Root license: Apache-2.0, with no recorded exceptions

Static inspection found a Claude-oriented harness factory but little portable
capability beyond contracts already owned by the first-party Agent Harness. No
upstream agent, script, installer, hook, test, or harness process was run.

The advertised compatibility surface and Agent Teams defaults were not adopted.
The review supported the decision to avoid a duplicate plugin rather than a
runtime or source import.

The pin is `reference-only`. It records the exact rejected/deferred source
snapshot while keeping installation, execution, vendoring, and activation
disabled.
