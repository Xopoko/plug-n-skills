# cursor/plugins external source audit

## Source identity

- Repository: <https://github.com/cursor/plugins>
- Reviewed snapshot: commit `46125561306434d8a1d7745d540d8932ab0cd2a2`
- Git tree: `1d1795c88013daf2470a40892d72664ec71b5061`
- Review date: 2026-08-21
- Reviewer: `capability-workbench`
- Root license: `NOASSERTION`; the pinned tree has no repository-root license
- Path-level licenses: MIT files cover the reviewed first-party plugin
  directories (`agent-compatibility`, `cli-for-agent`, `continual-learning`,
  `create-plugin`, `cursor-sdk`, `cursor-team-kit`, `docs-canvas`, `orchestrate`,
  `pr-review-canvas`, `pstack`, `ralph-loop`, `teaching`, and `thermos`) and each
  reviewed directory under `third_party/` (`amplemarket`, `ashby`, `circleback`,
  `clay`, `docusign`, `github`, `gmail`, `gong`, `google-calendar`,
  `google-drive`, `hubspot`, `intercom`, `juicebox`, `navan`, `outreach`,
  `playwright`, `profound`, `salesforce`, `x`, and `zoom`)

The path-level MIT files do not establish a repository-wide license. Material
outside those directories remains `NOASSERTION` and was used only as a
reference during static inspection.

Static inspection established that Cursor has native plugin manifests and a
root marketplace format, contradicting the repository's former claim that
Cursor had no plugin marketplace. It also supplied useful evaluation-blinding
and terminal-handoff examples. No candidate plugin, hook, command, test, or
installer was run.

The first-party change only repairs documentation and hardens behavioral
evaluation against candidate-visible treatment labels. Native Cursor packaging
is deferred until this repository has schema validation and compatible-client
proof; direct Agent Skills export remains its only validated Cursor path.

Transcript-mining hooks, unbounded continuation loops, API-key orchestration,
Slack or Git side effects, and planner-authored shell measurement were rejected.
The pin is `reference-only`; it grants no installation, execution, vendoring,
or activation authority.
