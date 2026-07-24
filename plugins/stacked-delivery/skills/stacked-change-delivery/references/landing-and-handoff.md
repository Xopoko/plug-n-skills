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

## Dirty Work Preservation

A topology change can race with owned local edits. Do not reset, clean, rewrite,
or continue editing the dirty worktree. Use a repository-native recovery
mechanism that explicitly covers every relevant state partition: staged,
unstaged, untracked, file mode, submodule, and any unsupported state. Keep raw
patch bytes, machine paths, and personal identifiers local.

Fail closed when the repository has no bounded recovery mechanism or when any
required partition is unsupported or omitted. In that case, preserve the
worktree in place and hand off the stop condition; do not rebind, rewrite, or
claim a portable receipt.

The current plugin does not define or validate a cross-repository dirty-work
receipt. A repository-native tool may call its artifact content-addressed only
when it specifies canonical bytes, partition order, bounds, and a validator.
Otherwise record it merely as a local recovery artifact with:

- public-safe or digested repository, node, change, source-head, worktree, and
  writer identities;
- the snapshot digest under which editing began;
- declared covered and unsupported partitions;
- the native tool and validation result, when available;
- a local digest labeled as unverified by this plugin.

After refreshing topology, a companion rebind note may reference the unchanged
artifact digest, the new snapshot digest, and the exact node, worktree, and
writer. This records recovery continuity only. It does not make the work
dependency-current, proof-current, review-ready, or landable, and the v1 guard
does not validate that note.

If authorized editing resumes, any content change supersedes the earlier
artifact. Refresh it with the same repository-native coverage and validation
before proof, commit, or handoff; never claim an older digest describes current
dirty state. The v1 snapshot and handoff schemas bind committed heads only, so
do not add undeclared dirty-work fields. Reconcile the work into a current node
head and rerun node-local proof before selecting a rewrite or landing action.

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
- any pending dirty-work recovery artifact, its coverage, validator status, and
  explicit unproven status;
- the one next safe action or explicit stop condition;
- any mutation still requiring authorization.
