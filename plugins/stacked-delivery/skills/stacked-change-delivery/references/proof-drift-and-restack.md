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

## Unavailable Proof Surfaces

When a proof cannot start because an external precondition is unavailable,
record a public-safe task-local proof-gap sidecar containing:

- an opaque proof-surface ID, command identity, and exact node and dependency
  heads;
- a fingerprint of the relevant code, fixture, configuration, environment,
  and external dependency state, without copying their raw values;
- a generic bounded failure class and opaque evidence reference;
- the recovery role, not a personal identity;
- whether repository policy requires that local surface or explicitly permits
  an equivalent remote proof authority.

Keep this record out of the snapshot's accepted `proofs`. Unavailability is
neither a failed proof result nor a successful proof. The v1 guard treats a
non-empty proof list as landing-eligible, so use `proofs: []` while any
policy-required proof surface remains open. Partial or non-equivalent results
stay in task-local evidence until policy confirms every required surface is
satisfied or explicitly equivalent. Reinspect a drift-prone gate once when
needed, but do not rerun the same proof while its gate fingerprint is
unchanged. Retry only after a relevant input or external state changes.

Keep raw failure tails in a bounded private evidence artifact referenced by the
opaque ID. The sidecar and handoff must not contain local paths, private URLs,
dependency coordinates, credentials, raw log fragments, personal identities,
or private project names.

A remote proof that requires publishing does not authorize the publish; the
existing mutation and lease gates still apply. After an authorized publish,
read back the remote head before accepting a later result. Accept it only when
repository policy permits that proof authority, terminal success binds the
exact node and dependency heads, and any required execution is non-empty. It
does not satisfy a mandatory local surface unless policy explicitly declares
the two surfaces equivalent. A non-equivalent remote result remains task-local
evidence and must not enter landing-eligible snapshot proofs. `next-action`
remains blocked until every policy-required proof surface is satisfied or
explicitly equivalent. Preserve the open proof gap separately from a later
accepted remote proof in the task-local handoff summary, without copying
private dependency details into reusable source.

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
2. Confirm each affected worktree is clean, or stop with its dirty state
   preserved by a bounded patch receipt before any rewrite. Confirm exclusive
   writer ownership in either case.
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
