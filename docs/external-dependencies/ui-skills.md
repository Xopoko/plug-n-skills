# ui-skills external source audit

## Source identity

- Repository: <https://github.com/ibelick/ui-skills>
- Reviewed snapshot: commit `33b35e7d13d4bce7e4358d2205e406c1b20263fc`
- Git tree: `8ee92fe60983596fba48851664914a5acbedea20`
- Review date: 2026-08-21
- Reviewer: `capability-workbench`
- Root license: MIT, with no recorded exceptions

The static review extracted a UI-finding proof and falsification pattern plus
small fixture ideas. No upstream instruction, script, hook, installer, analytics
path, or test was executed.

A frozen local instruction evaluation found useful signal but also critical
candidate failures, so no UI guidance was promoted. Mutable remote skill
loading and prebuild analytics synchronization were rejected outright.

The snapshot is retained only as provenance and future fixture material. Its
policy is `reference-only`: installation, execution, vendoring, and activation
are disabled, and later revisions require a new review.
