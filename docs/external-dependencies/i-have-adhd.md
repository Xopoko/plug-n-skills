# i-have-adhd external source audit

## Source identity

- Repository: <https://github.com/ayghri/i-have-adhd>
- Reviewed snapshot: commit `2ed064090711586e0c97a2fbbf15465fe8f1808b`
- Git tree: `f3bcaa2cc34836bcba1d55bb7e3f3db76cfdae2d`
- Review date: 2026-08-13
- Reviewer: `capability-workbench`
- Root license: MIT, with no recorded exceptions

The source is a cross-harness bundle for ADHD-friendly response shaping. It
contains integrations and installation guidance for multiple agent runtimes;
the review therefore treats the repository as a source corpus, not as one
portable plugin that can be activated unchanged everywhere.

## Reviewed capability surface

The Codex manifest exposes one instruction skill from `skills/` and declares
only the `Instructions` capability. It does not expose Codex hooks, MCP servers,
or apps. The reviewed skill is an output-style instruction set and is configured
for explicit invocation rather than implicit model activation.

Other harness surfaces remain part of the upstream snapshot but are outside the
Codex capability surface:

- Claude Code includes a `SessionStart` command hook. Its documented behavior is
  opt-in through an always-on flag, and the hook was not installed or executed
  during this review.
- Pi includes `extensions/i-have-adhd.ts`, which manages session-persistent mode,
  commands, flags, and status. The extension was not installed or executed.
- Development evaluation tooling can invoke operator-selected model runners.
  The documented workflow accepts explicit trial and cost budgets, so running it
  may consume provider quota or incur cost. No evaluation runner was executed.

## Supply-chain findings

The upstream `.agents/plugins/marketplace.json` points its inner plugin source at
the mutable `main` branch. That marketplace declaration is not an immutable
receipt and is not used by this registry. This audit covers only the exact
commit and Git tree recorded above; later upstream revisions require a new
review and pin update.

The native plugin maintained in this repository is an independently authored
distillation of the useful interaction pattern. It is not a vendored copy of
the upstream cross-harness bundle, and this provenance record does not grant
permission to import upstream scripts, hooks, extensions, manifests, or install
instructions.

## Policy and verdict

Verdict: `isolate`.

The dependency is `reference-only`. Registration records provenance for the
reviewed snapshot but never installs, executes, vendors, or activates any
upstream file. Any future use must be distilled into reviewed first-party source
and validated independently under this repository's plugin contracts.
