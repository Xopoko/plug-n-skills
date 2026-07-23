# Proof, Drift, And Restack

## Node-Local Proof

A proof belongs to exactly one node composition:

```text
node head + exact parent/base head + command identity + result identity
```

Accept it only when:

- its node head equals the current node head;
- its dependency head equals the current expected parent head;
- its status is terminal success;
- it is not cancelled, skipped, neutral, superseded, or from an obsolete
  pipeline or merge group;
- its stable proof ID is unique in the snapshot.

Parent proof does not flow upward. Cached evidence is acceptable only when the
repository's cache key binds the same inputs and the receipt records that key.

## Invalidation

Any of these changes invalidates the affected node and its transitive
descendants:

- parent or base head changes;
- node head changes;
- source, target, parent, order, or stable identity changes;
- worktree or writer ownership becomes ambiguous;
- proof is replaced, superseded, or no longer bound to the live composition.

Distinguish:

- `dependency-current`: parent and target bindings are exact;
- `proof-current`: accepted proof matches the current composition;
- `review-ready`: forge review requirements currently pass;
- `landable`: policy and delivery-mode requirements currently pass.

No one flag implies the others.

## Authorized Restack

Restacking rewrites descendants. Do not do it as an incidental repair.

1. Record old base, parent, node, and remote object IDs.
2. Confirm clean worktrees and exclusive writer ownership.
3. Rebind the lowest affected node to the new parent.
4. Rewrite one node at a time from bottom to top.
5. Verify ancestry and the node-only delta.
6. Publish only with an explicit expected remote object ID.
7. Read back the remote head.
8. Repeat for the next descendant.
9. Rerun node-local proof and rebuild the snapshot.

On conflict, remote drift, lease failure, ambiguous state, or partial publish,
stop and preserve the last confirmed mapping. Do not retry the same rewrite
without new state or a changed resolution.

## External Mechanisms

The workflow adapts these public mechanisms without depending on their tools:

- cascading rebase or restack after ancestor mutation;
- compare-and-swap ref updates and explicit remote leases;
- feature-probed atomic multi-ref publication;
- merge-group or integration-object proof when the forge provides it.

Tool-specific commands remain optional adapters. Repository policy decides
which adapter is allowed.
