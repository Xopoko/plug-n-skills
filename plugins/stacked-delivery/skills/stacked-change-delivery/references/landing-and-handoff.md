# Landing And Handoff

## Delivery Modes

Use `sequential` unless live forge evidence proves a stronger contract.

### Sequential

Only the lowest unlanded node is eligible. After it lands:

1. fetch the resulting base head;
2. record that merge, squash, or fast-forward result as the landed node's
   integration head and release its active ownership binding;
3. read back the remaining forge stack;
4. verify or repair the new bottom target;
5. restack if the new composition requires it and authorization permits;
6. rerun proof against the new base;
7. rebuild the snapshot before selecting another node.

### Atomic Prefix

Some forges can land a contiguous prefix as one stack-aware operation. Use this
mode only when the repository has the feature enabled and the live API exposes
the exact stack and prefix.

- The prefix starts at the lowest unlanded node.
- Every included node is current, proven, and landable.
- No lower node is omitted.
- The operation's preconditions and resulting integration identity are
  captured.
- A partial server-side result is reconciled as a new snapshot, never retried
  blindly.

Feature availability and semantics drift. Detect them live; do not encode a
vendor promise as a permanent portable rule.

## Retargeting

A target-branch update is metadata, not composition proof. After a lower node
lands, require the new bottom node to bind the current base head and prove the
resulting composition. If the forge cascades a rebase, read back every new head
and invalidate older proofs.

## Dirty Patch Preservation

A topology change can race with owned local edits. Do not reset, clean, rewrite,
or continue editing the dirty worktree. Preserve the local state in a bounded
patch receipt that binds:

- public-safe or digested repository, node, change, source-head, worktree, and
  writer identities;
- the snapshot digest under which editing began;
- separate declared coverage for staged, unstaged, untracked, file-mode,
  submodule, and unsupported state;
- one opaque digest over canonical receipt metadata and every declared covered
  content partition; keep patch bytes, machine paths, and personal identifiers
  local.

Fail closed when required dirty state is unsupported or omitted. After
refreshing topology, create a rebind record that references the unchanged
patch-receipt digest, the new snapshot digest, and the exact node, worktree,
and writer. This proves continuity of the pending work only. It does not make
the patch dependency-current, proof-current, review-ready, or landable.

If authorized editing resumes after the rebind, any content change supersedes
that patch receipt. Refresh it before proof, commit, or handoff; do not
checkpoint every line, and never claim an older digest describes the current
dirty state.

The current v1 snapshot and handoff schemas bind committed heads, not dirty
patches. Keep the patch receipt and rebind record as explicit companion
artifacts; do not add undeclared fields to v1 input. Reconcile the patch into a
current node head and rerun node-local proof before selecting a rewrite or
landing action.

## Handoff Receipt

A portable receipt binds:

- receipt and stack schema versions;
- repository identity and forge adapter;
- canonical snapshot digest;
- stack ID, base branch, and base head;
- ordered node IDs and exact heads;
- accepted proof IDs for each node;
- worktree and writer ownership identities;
- the explicit receiver identity.

Serialize canonical JSON with sorted keys and fixed separators before hashing.
Preserve the canonical bytes alongside the handoff digest returned by the
guard. Compute the next safe action separately from the same snapshot so a
receiver can re-run that decision after refreshing live state.
Reject extra nodes, missing nodes, incomplete ownership pairs, conflicting
active worktrees, stale heads, stale proof IDs, or a snapshot digest mismatch.

The receipt is content-addressed and tamper-evident. It becomes independently
immutable only when a trusted signature, transparency log, or append-only
verifier validates the same digest and records its authority. Never overstate a
local JSON file as immutable.

## Handoff Summary

Report:

- repository and forge scope, current base, and stack digest;
- current, stale, landed, and blocked nodes;
- proof IDs and dependency heads, not raw logs;
- worktree and writer ownership;
- any pending patch-receipt digest and its explicit unproven status;
- the one next safe action or explicit stop condition;
- any mutation still requiring authorization.
