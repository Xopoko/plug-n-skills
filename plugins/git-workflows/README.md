# Git Workflows Plugin

Git Workflows consolidates exact-state Git review, delivery, and recovery
capabilities without flattening platform-specific semantics. GitHub and GitLab
reads share a capability-based adapter contract; GitLab discussion writes,
stacked-change delivery, worktree pointer recovery, and SSH commit-signing
recovery retain their own stricter state machines and guards.

## Skills

- `forge-code-review`: read-only review of a GitHub pull request or GitLab merge
  request link through a probed MCP, connector, CLI, or REST adapter. It never
  posts, approves, resolves, pushes, merges, or edits repository state.
- `gitlab-review-response`: the preserved GitLab transaction for complete
  discussion inventory, exact-head repair and CI proof, idempotent same-thread
  replies, ambiguous-write readback, and separately authorized resolution.
- `stacked-change-delivery`: the preserved stack snapshot, descendant
  invalidation, restack, proof-freshness, landing-order, and handoff contract.
- `git-worktree-recovery`: the preserved branch-retention audit and tightly
  gated POSIX convenience-symlink repair contract.
- `git-commit-signing-recovery`: the preserved exact-state, single-use SSH
  signed-commit retry and post-commit verification contract.

## Forge Adapter Boundary

`references/forge-adapter-contract.md` defines strict, versioned capability IDs
and evidence traits. `scripts/forge_adapter_selector.py` validates task-local
inventories and plans without network access. It selects transports by probed
operation and evidence coverage, never by the labels MCP, connector, `glab`, or
REST.

Opaque pagination cannot establish a complete review. A wrong actor is a stop
condition. Writes require no hidden retry, an exposed unknown-result state, and
a returned server receipt. After an ambiguous write, the selector permits only
readback; it never chooses another writer. Local Git publication, worktree
repair, commit signing, rebases, pushes, approvals, and merges remain outside
the shared selector.

## Migration Notes

This source tree is the consolidation target for three previous plugin IDs:

- `gitlab-review` -> `git-workflows`, with skill name
  `gitlab-review-response` unchanged;
- `git-worktree-safety` -> `git-workflows`, with skill names
  `git-worktree-recovery` and `git-commit-signing-recovery` unchanged;
- `stacked-delivery` -> `git-workflows`, with skill name
  `stacked-change-delivery` unchanged.

The unchanged skill names preserve trigger compatibility. Their scripts,
references, schemas, exit codes, and safety boundaries remain in the same
plugin-relative locations. `forge-code-review` and the adapter selector are
additive. The GitLab response skill uses the shared selector only to choose the
live REST-equivalent transport; its existing immutable epoch, push binding,
exact-head, dedupe, authorization, and readback guards remain authoritative.

Repository marketplace entries, root documentation, legacy source removal,
installation, and runtime cache refresh are separate migration steps. This
plugin source does not activate or uninstall anything by itself.

The consolidated icon prompt and inspected bitmap are present under `assets/`.
The Codex manifest wires both supported icon fields to `assets/icon.png`.

## Validation

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/git-workflows
python3 -m unittest discover -s plugins/git-workflows/tests -p 'test_*.py'
```

Platform-specific recovery and publication tests retain their original POSIX
requirements. Unsupported hosts must report or skip those paths rather than
silently substituting weaker behavior.
