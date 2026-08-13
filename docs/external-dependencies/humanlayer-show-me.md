# HumanLayer show-me external source audit

## Source identity

- Repository: <https://github.com/humanlayer/skills>
- Reviewed snapshot: commit `3c2629142c5d437428269b1b722b08c0b87f574d`
- Git tree: `2f7121eedbf48e98cf1b42dffae97be6815e1fe9`
- Reviewed subtree: `plugins/show-me` at tree `0b983b356b2a1b115f03137660c4f823ddc8cce0`
- Review date: 2026-08-13
- Reviewer: `capability-workbench`
- Root license: MIT, with no recorded exceptions

The reviewed source is a small Claude plugin whose instruction skill turns a
current topic into pseudocode, call or component trees, shallow file trees,
Mermaid diagrams, structural diffs, complete code blocks, or a generated HTML
artifact. This review was static. No upstream instruction, script, installer,
hook, or generated artifact was executed.

## Adopted mechanisms

The first-party `visual-explanation` skill independently distills these useful
mechanisms:

- choose the smallest view that explains the relevant relationship;
- prefer a focused structural diff when change shape is the point;
- keep supporting text adjacent and exclude irrelevant calls, files, props,
  states, or boundaries;
- use a richer artifact only when a compact inline form becomes too dense.

The first-party skill adds its own boundaries: evidence-linked observed views,
explicit proposed views, portable text fallback, accessibility requirements,
secret redaction, untrusted-label escaping, and positive plus near-miss trigger
fixtures.

## Rejected and deferred surface

The upstream HTML path invokes `Bash(open ...)`, which couples presentation to
a Claude tool name and the macOS `open` command. It does not define a portable
workspace output path, renderer fallback, artifact lifecycle, or escaping and
redaction contract. The snapshot also contains no behavioral tests for this
skill.

The repository therefore does not vendor the upstream plugin or adopt its
manifest, shell invocation, or HTML runtime. Typed visual buses, local viewers,
feedback servers, live annotations, and durable diagram compilers remain
separate future capabilities that require explicit demand and their own
security, lifecycle, and portability proof.

## Policy and verdict

Verdict: `isolate`.

The dependency is `reference-only`. Registration records provenance for the
reviewed immutable snapshot but never installs, executes, vendors, or activates
any upstream file. Later upstream revisions require a new review and pin.
