# Prepared Mutation Handoff

Use this contract when one task prepares exact replacement history for another
task to publish later. It is an additive companion to the current-state
`stacked_delivery.handoff.v1` receipt. It does not authorize a ref update,
metadata change, merge, approval, cleanup, or proof retry.

The deterministic guard accepts:

```text
stacked_delivery.prepared_mutation_handoff.v1
```

Run:

```bash
python3 "$SKILL_ROOT/scripts/stacked_delivery_guard.py" \
  validate-prepared-mutation --input PREPARED_JSON
```

Exit `0` means the package is internally consistent and reports one ready
action or `complete`. Readiness distinguishes `history-ready`,
`mutation-ready`, `metadata-ready`, and `complete`. Exit `2` means the next
action is blocked by an open gap or a safety gate failed. Exit `1` means the
document is malformed or does not match the strict schema.

## Top-Level Bindings

The exact top-level fields are:

- `schema`, `receiver_id`, `snapshot_digest`, and the complete old `snapshot`;
- an explicit new predecessor with kind, optional node ID, full
  `refs/heads/` source ref, exact head, and opaque evidence ID;
- `proof_wait_owner_ref`, which is either one scalar opaque owner reference or
  null;
- `authority`, containing an opaque authority ID, `user` or
  `repository-policy` source, opaque evidence ID, evidence hash, and the sorted
  unique allowed action kinds;
- `attribution_policy`, containing the opaque attribution-policy ID and
  fingerprint selected by repository policy;
- `proof_policy`, containing the opaque ID and SHA-256 fingerprint of the
  repository policy that defines the complete required proof-surface set;
- sorted unique `excluded_actions`;
- ordered `nodes` describing the rewritten suffix;
- ordered `actions`;
- ordered `history_receipts`, initially empty;
- `metadata_receipt`, initially null.

The old snapshot must pass the existing snapshot validator, and
`snapshot_digest` must equal its canonical digest. The rewrite nodes must be one
contiguous unlanded suffix in the same bottom-to-top order. Every mapping binds
the snapshot's node ID, change ID, source branch, old node head, and old parent
head. All Git object IDs in one package use one Git object-ID width. The old
snapshot remains the immutable transaction baseline while strict history
receipts record a completed action prefix. The guard derives one immutable
transaction digest over repository and stack scope, baseline, receiver,
authority, policies, predecessor, rewrite, backup and lease bindings,
exclusions, and actions. Proof evidence, watcher ownership, and receipts do not
change that transaction digest.

Keep authority evidence, owner references, and recovery references opaque.
Never put names, email addresses, credentials, local paths, private URLs, raw
logs, or untrusted command text in the portable package.

## Per-Node Rewrite Evidence

Every rewritten node contains:

- exact full old and new node heads;
- exact full old and new parent heads;
- required patch and tree equivalence records;
- an author and committer attribution record;
- one confirmed backup record;
- one exact remote lease;
- sorted unique required proof-surface IDs;
- accepted proofs and explicit open proof gaps whose disjoint union covers
  every required surface exactly once.

Every higher rewritten node's new parent must be the preceding rewritten node's
new head. The first rewritten node's new parent must equal the explicit new
predecessor head. An unchanged predecessor binds the exact base or preceding
stack dependency named by the first rewritten node's current target and
expected parent head. This treats a retargeted node after a landed prefix as
depending on the current base. An intentional retarget uses the `retarget`
kind, exact new target ref and head, and requires the separate metadata action.
A replacement head must differ from every old stack, base, and landing head.

### Patch And Tree Equivalence

Patch and tree evidence are separate mandatory records. Each record binds:

- a supported method and declared scope;
- SHA-256 digests of the old and new evidence;
- an opaque evidence ID;
- `equivalent: true`.

The old and new digests must match. Hash the repository-selected method's
bounded output instead of embedding patch text, paths, or tree listings. The
guard validates the evidence binding; it does not invoke Git, compute a patch
ID, judge the repository's equivalence method, or authenticate the collector.

Use `stable-patch-id` or `canonical-diff` for a `node-delta` patch record. Use
`canonical-tree-delta` for a node delta, or `tree-object` when repository policy
requires an exact result-tree identity.

### Attribution Policy

Store SHA-256 fingerprints of repository-selected author and committer identity
fields, never raw identity values. The top-level opaque attribution-policy ID
and fingerprint bind the repository rule used to evaluate every node. Choose
exactly one built-in relation:

- `preserve-author-and-committer`: old and new author fingerprints match, old
  and new committer fingerprints match, and no authorized replacement
  committer is present.
- `preserve-author-allow-authorized-committer`: author fingerprints still
  match, the committer actually changes, and the new committer fingerprint
  equals the separately authorized committer fingerprint.

A replacement commit object ID alone does not establish acceptable attribution.
A successful proof or green remote pipeline cannot override attribution drift.
Any author drift, unapproved committer drift, missing authorized committer, or
unexpected identity fails the whole package and invalidates mutation readiness.

### Backup And Lease

Before a package can become ready, every old head has one unique full `refs/`
backup under `refs/stacked-delivery/backups/` whose expected and read-back heads
both equal that old head. The dedicated recovery namespace prevents an
incomplete inventory from treating an unrelated head, tag, remote-tracking
ref, or prefix lookalike as a backup. A backup ref also cannot collide with the
base, any stack source or target, any new target, or another known live ref.
Keep every backup after a later conflict, lease failure, partial publish,
attribution failure, or rejected proof. Backup deletion stays excluded unless a
later task separately authorizes and proves cleanup.

The lease record uses `exact-remote-head`, names the source branch, and binds the
expected remote head to the old snapshot head. Each history action repeats that
ref, expected old head, new head, and backup ref. Immediately before the real
write, fetch live state, re-read the backup, and compare both with the bound
snapshot and lease. Drift is a stop condition; never replace the expected old
head merely to make a retry proceed.

### History Progress Receipts

`history_receipts` is an ordered, contiguous prefix of completed history
actions. Every receipt has an opaque receipt ID and SHA-256 receipt
digest of every other receipt field. It repeats the exact action ID, node ID,
source ref, expected old head, written head, read-back head, backup ref, backup
read-back head, and immutable transaction digest. The written and read-back
heads must both equal the action's prepared new head, and the backup read-back
must still equal the old head. A digest mismatch, transaction mismatch,
duplicate, skipped, reordered, or stale receipt fails the package.

A receipt cannot bypass a history-blocking proof gap on its node. The guard
validates the canonical digest and receipt bindings but cannot authenticate the
external collector or opaque receipt ID; the receiver must do that separately.
History receipts are bounded evidence, not a watcher cursor: they contain no
scheduler, heartbeat, host, time, retry, or polling state.

### New-Composition Proof Surfaces

Every required proof surface has exactly one accepted proof or one explicit
open gap. Each proof binds the new node head and new parent head and must be
terminal success, non-superseded, and non-empty. Each gap binds the same exact
heads, one opaque evidence ID, and the action kind it blocks. A proof for the
old head, old parent, missing surface, skipped execution, unrelated pipeline,
duplicate surface, or a receipt ID reused from the old snapshot fails the
package.

The opaque proof-policy ID and fingerprint bind the declared surface lists to a
specific external repository policy. The guard does not decide whether that
policy is adequate or authentic; the receiver must verify it before treating
the surface lists as complete.

When a pre-publish gap blocks `history-ref-update`, it blocks that node's
history action. A higher node's gap does not block the lower next action. When
all gaps on the next node block only later metadata or finalization, the result
is `history-ready` and returns only that next history action.

After every history action has an exact receipt, a `metadata-update` gap
produces `proof-wait` with no next action. A `finalize` gap does not block
metadata: it waits only after metadata has its exact receipt. Replacing a gap
with its accepted proof and setting the owner to null yields `metadata-ready`
when optional metadata remains, or `complete` when no action or finalization
gap remains. A `finalize` gap also represents a post-publish proof required for
a history-only package. This lets a required remote proof be collected after
the authorized mutation without pretending that the phase it gates is ready.

`proof_wait_owner_ref` is one scalar reference exactly while at least one gap
is open. `proof_wait_owner_ref` is null when no gap is open. Multiple owners
and collections are malformed. The stack package does not embed scheduler,
heartbeat, cursor, host, or polling state. Agent-specific supervision remains
owned by that agent's supervision contract.

## Ordered Actions And Scope

Only two action kinds exist:

1. `history-ref-update`
2. `metadata-update`

All history actions appear first, one per rewritten node in bottom-to-top order.
Metadata actions are optional. At most one may appear afterward, only for the
first rewritten node, with a disjoint strict shape and separate authorization.
It binds the old and new target branches, the exact new target head, and the
expected new node head. Prepared source and target refs must be branch heads:
short names normalize to `refs/heads/`, while tags, notes, and remote-tracking
refs are rejected. The new target ref and head must equal the explicit retarget
predecessor, and a stack source ref is rejected to prevent self-target and
cyclic topology. A metadata update is not composition proof and must never be
combined with a ref update.

After metadata changes, `metadata_receipt` must bind the immutable transaction
digest, action and node, old/new/read-back target refs, expected and read-back
new-target heads, and expected and read-back node heads. Its canonical receipt
digest must match. Metadata cannot become terminal while its own gap remains,
before all history receipts exist, or when either read-back drifts. With the
receipt present, metadata is not exposed again after a restart.

Every action repeats the one authority ID. The authority's allowed action set
must equal the action kinds present. The package must explicitly exclude at
least approval, merge, review resolution, commit-content edits, unrelated ref
updates, source-ref deletion, and backup deletion. Unknown or additional work
requires a separately authorized package.

## Receiver Gate And Failure Handling

The receiver must:

1. validate the package and preserve its canonical digest;
2. authenticate authority, policy, evidence, and any action receipt collector
   or opaque ID;
3. independently refresh live state: incomplete history refs must still equal
   their old leases, while completed refs must equal their exact receipt
   read-backs; before metadata, the retarget predecessor ref must equal its
   bound head and the node's current target must equal `old_target_branch`;
4. confirm the external proof-wait owner remains current when gaps are open;
5. perform only the returned `next_action_id`;
6. read back the affected source ref and backup, or the metadata target, source
   node head, and new target branch head;
7. append the action's exact receipt and validate the new canonical package
   before another action;
8. stop on drift, conflict, ambiguous receipt, attribution failure, proof
   rejection, or partial publication.

On failure, preserve backups and the last confirmed old/new mapping. Do not run
metadata actions, delete recovery refs, create a second watcher, or blindly
retry. A changed head, parent, equivalence result, attribution policy, proof,
authority, or action requires a new canonical package.
