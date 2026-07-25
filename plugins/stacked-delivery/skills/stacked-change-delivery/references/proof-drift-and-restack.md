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
neither a failed proof result nor a successful proof. At the proof layer, the
guard treats a non-empty accepted proof list as satisfied, so use `proofs: []`
while any policy-required proof surface remains open. `next-action` separately
requires snapshot v2 and its metadata audit. Partial or non-equivalent results
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
- `metadata-current`: every active proof-bearing mutable record matches the
  current composition and proof identities;
- `metadata-stale`: an active record contradicts the current identity tuple;
- `metadata-unverified`: an active record cannot be completely compared with
  the current tuple;
- `review-ready`: forge review requirements currently pass;
- `landable`: policy and delivery-mode requirements currently pass.

No one flag implies the others.

## Post-Rewrite Evidence Binding

Run one binding audit after a restack, non-fast-forward rewrite, or retarget
changes a base, parent, node head, target, pipeline, or accepted proof identity.
Complete it before any readiness claim, evidence reply, or handoff.

Freeze the refreshed current tuple from read-only live evidence:

- stable change and node identities;
- exact base or parent head and exact node head;
- source and target refs;
- each accepted proof ID, proof head, dependency head, and terminal status.

Then inventory every active mutable record that presents proof or current
delivery state. This includes a change description, status or check summary,
durable checkpoint, and handoff summary. Preserve its exact identity and
evidence references while comparing active bindings with the refreshed tuple.
Counts, labels such as "latest", a green badge, or a receipt that is internally
self-consistent do not establish live freshness.

Encode that completed audit in exact `stacked_delivery.snapshot.v2`
`metadata_inventory`. Bind the inventory and every comparable active record to
the canonical composition digest, bind audited-surface coverage and the exact
record list through `audit_digest`, and keep each exact readback behind an
opaque evidence ID and SHA-256 hash. Use a null record binding when comparison
is incomplete; do not invent a digest. `next-action` blocks an exact legacy v1
snapshot, and enforces the v2 audit before returning `ready` or `complete`.
`validate-handoff` fails an exact v1 receipt, and enforces an exact v2 snapshot
plus a separate digest of the inventory carried by handoff v2.
Sort active records canonically by kind and record ID before binding the audit.
If audit integrity is unverified and another binding is stale, report aggregate
`metadata-unverified` while retaining both blocking states; do not let an
untrusted audit make the stronger `metadata-stale` classification. When two v2
snapshots carry different canonical inventory digests, `compare` reports that
metadata drift and fails even when node composition and proof are unchanged.

If any active binding still names an old base, parent, head, target, pipeline,
or proof, classify that record as `metadata-stale`. Do not use it to support
`proof-current`, `review-ready`, or `landable`. A pending proof may be recorded
as pending, but it cannot replace terminal exact-composition proof. If an
active record cannot be completely compared with the refreshed tuple, classify
it as `metadata-unverified`. Both `metadata-stale` and `metadata-unverified`
block a readiness claim, evidence reply, or handoff; neither erases otherwise
current underlying proof.

The binding audit evaluates freshness only after another workflow or explicit
policy independently establishes that a conditional action applies. It does not
create a reply obligation. When the owning review workflow finds zero eligible
existing discussions, an evidence reply is `not-applicable`: do not add it as a
delivery gate and do not create a top-level note as a substitute. Keep stack
proof, review-thread eligibility, and write authority as separate decisions.

Obtain fresh authority for the exact record and update action before changing a
mutable record. Authority to push, restack, retarget, reply, or edit another
surface does not imply authority to edit a change description, checkpoint, or
status. Update an agent-maintained record only through its authorized owner.
Refresh a producer-owned check or status through its authoritative producer;
do not manually rewrite its result. Once the new proof state is known and the
surface-specific action is authorized, update or refresh the record, read back
the same surface, and compare again. Without that authority or producer path,
leave the record unchanged, report the blocking state, and keep readiness
blocked.

Old identities remain valid in immutable provenance, lease guards,
old-to-new mappings, append-only discussion history, or receipts explicitly
labelled historical or superseded and excluded from current proof. Do not erase
or relabel those records merely because they differ from the live tuple.

Do not parse arbitrary generated prose, trust a raw string search, or treat a
Markdown rewrite as semantic proof. Prefer repository-defined structured
fields or a canonical receipt block when one exists. Otherwise classify the
record as `metadata-unverified`; do not silently infer missing bindings. The
bundled guard validates the supplied structured inventory, its canonical audit
digest, each declared composition binding, and the handoff's inventory digest.
It does not fetch or authenticate forge descriptions, checkpoints, statuses,
or handoff summaries, and an internal receipt validation does not prove that a
live public record is current or that the declared inventory is complete.

## Independent Pre-Write Gates

A reconstructed branch or history rewrite needs three independent gates:

1. **Composition equivalence:** ancestry, ordered commit mapping, and the
   repository-required tree or patch behavior are preserved.
2. **Contribution provenance:** repository-selected author attribution remains
   valid for every rewritten commit. Record committer changes separately;
   creating a replacement commit does not transfer authorship.
3. **Mutation authority:** fresh read-only evidence binds the current owner,
   actor, exact action, repository and stack scope, validity window, and any
   revocation or veto.

Equal trees or patches, a clean worktree, a local writer binding, green
exact-head proof, an old-to-new object-ID table, or a safe lease cannot
substitute for the other gates. A prepared handoff records how replacement
history was produced; the receiver still refreshes action-specific authority
immediately before publication. If ownership is ambiguous, attribution
changed, authority expired, or a newer veto revoked or superseded it, stop
before mutation.

Collect commit topology and attribution without local replacement objects or
legacy grafts influencing the result. For example, read each named object with
`git --no-replace-objects cat-file commit <object-id>`, retain the complete
parent array, and derive public-safe repository-policy fingerprints rather than
embedding raw identities. Require every collector command to finish
successfully with bounded output before hashing evidence. The guard checks
declared digests and relationships; it does not run Git or authenticate the
collector.

## Authorized Restack

Restacking rewrites descendants. Do not do it as an incidental repair.

1. Record old base, parent, node, and remote object IDs.
2. Resolve current change ownership and action-specific authority from fresh
   read-only evidence; a local `writer_id` is not that authority.
3. Confirm each affected worktree is clean, or stop with its dirty state
   preserved by a bounded repository-native recovery mechanism before any
   rewrite. Confirm exclusive writer ownership in either case.
4. Rebind the lowest affected node to the new parent.
5. Rewrite one node at a time from bottom to top.
6. Verify ancestry, ordered contribution provenance, and the node-only delta.
7. Publish only with an explicit expected remote object ID and current
   publication authority.
8. Read back the remote head.
9. Repeat for the next descendant.
10. Rerun node-local proof and rebuild the snapshot.

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

Git keeps author and committer as distinct identities: the author identifies
the contribution, while the committer records who created the commit object.
Rebase creates replacement commits and can refresh committer metadata, so do
not silently recast that change as authorship. See the official
[`git-var`](https://git-scm.com/docs/git-var),
[`git-rebase`](https://git-scm.com/docs/git-rebase), and
[`git-replace`](https://git-scm.com/docs/git-replace) documentation.
