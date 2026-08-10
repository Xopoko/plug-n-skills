# Stack Snapshot Contract

Build the snapshot from fresh read-only Git and forge evidence. The guard
checks internal consistency; it cannot authenticate the collector.

## Required Bindings

The snapshot must bind:

- a schema version, canonical repository ID, forge adapter, stable stack ID,
  and declared delivery mode;
- the base branch and full current base object ID;
- ordered nodes from bottom to top;
- for every node: stable node and forge change IDs, source and target branches,
  full current head object ID, parent node or root, expected parent object ID,
  lifecycle state, resulting landing head or null, active worktree and writer
  identities or an explicit null pair, and proofs.
- for readiness or handoff: a complete active metadata inventory whose audit
  and record bindings match the exact current composition.

Use full lowercase, non-zero 40- or 64-hex object IDs. A shortened hash is
display data, not an identity; the all-zero deletion or unborn sentinel is not
an object. One snapshot uses one object-ID width. Keep human titles and
free-form bodies outside the validation contract.

Repository and forge scope are digest inputs, not display metadata. Use a
stable public-safe repository identifier or a stable digest when the canonical
name is sensitive. Never reuse a receipt across a different repository or
forge adapter merely because branches and object IDs happen to match.

## Metadata Inventory V2

`stacked_delivery.snapshot.v2` has the exact v1 stack fields plus the required
`metadata_inventory` field. It carries one complete audit of active
proof-bearing mutable records. The inventory has an opaque `audit_id` and
`evidence_id`, an exact `audited_kinds` array covering change descriptions,
status summaries, durable checkpoints, and handoff summaries, a `complete`
boolean, the current `composition_digest`, a content-addressed `audit_digest`,
and a bounded `records` array.

Compute `composition_digest` from canonical JSON after removing the top-level
`metadata_inventory` field rather than replacing it with null. The remaining
object still carries the v2 schema identifier. This avoids a self-reference
while binding repository and forge scope, stack and base, ordered nodes,
branches, heads, ownership, lifecycle state, and every accepted proof identity.
Compute `audit_digest` from the canonical inventory object after removing only
`audit_digest`; it therefore binds audited-surface coverage, the complete flag,
composition digest, evidence reference, and exact record list.

The records array contains active records only. Each record has:

- a stable `record_id`;
- kind `change-description`, `status-summary`, `durable-checkpoint`, or
  `handoff-summary`;
- an opaque exact-readback `evidence_id` and its non-zero SHA-256
  `evidence_hash`;
- either a binding containing the current `composition_digest`, or null when
  the record cannot be completely compared.

Sort records canonically by `(kind, record_id)` before computing
`audit_digest`. A different order is `metadata-unverified`; do not allow two
equivalent inventories to produce different ready snapshot digests. Duplicate
record IDs remain a separate structured gate failure.

A null binding is `metadata-unverified`. A binding or inventory composition
digest that differs from the current composition is `metadata-stale`.
Incomplete audited-surface coverage, an incomplete audit, duplicate active
record identity, or audit-digest mismatch is also fail-closed. Historical or
superseded non-proof records stay outside this active inventory.
When unverified audit integrity and a stale binding coexist, the aggregate
status is `metadata-unverified`; `blocking_statuses` retains both states. Only
an otherwise trustworthy audit may aggregate to `metadata-stale`.

Compatibility is deliberate and two-way strict. Exact legacy v1 snapshots do
not accept v2 fields; exact v2 snapshots require the inventory. V1 snapshots
remain parseable, keep their original canonical digest, and may still be used
for structural `validate-snapshot`, same-version `compare`, or
prepared-mutation inspection. Structural `validate-snapshot` retains its exact
legacy validation v1 output and does not add a metadata field. The current-state
gate in `next-action` classifies the missing inventory through
`legacy_snapshot_metadata_gate` and returns `blocked` with
`legacy_snapshot_requires_v2_metadata`; it cannot return `ready` or `complete`
until the collector creates an exact v2 snapshot with a complete
`metadata-current` inventory. `compare` reports a v1-to-v2 transition as
explicit schema drift. `validate-handoff` applies the corresponding exact
handoff-version gate described in `landing-and-handoff.md`.

Output schemas follow the same boundary. V1 structural validation and
`next-action` retain their exact v1 output field sets. V2 uses validation and
next-action v2 outputs with the structured metadata summary. A v1-to-v1 compare
retains exact `stacked_delivery.compare.v1`. Any comparison involving v2 emits
`stacked_delivery.compare.v2`, binds the before/after inventory digests, and
returns `fail` with `metadata_changes` when they differ. That metadata drift
does not by itself invalidate otherwise unchanged node proof.

## Linear Topology

The conservative portable shape is one chain:

```text
base <- node-1 <- node-2 <- node-3
```

- The bottom node targets the base branch and binds the base head.
- Every higher node targets its direct parent's source branch and binds that
  parent's exact current head.
- Node, change, and branch identities are unique.
- Each non-null active worktree identity is unique. A writer principal may own
  several distinct worktrees.
- The ordered list, parent links, and target branches must describe the same
  chain.

Do not silently coerce a fork or a multi-parent graph into a line. Model a
separate stack, or use a repository-specific integration node with its own
exact composition and proof.

## Ownership

Worktree administration and writer ownership are different concepts.

- Inventory worktrees read-only before assigning a writer.
- One active writable node maps to one canonical worktree and one writer.
- `writer_id` coordinates the local editor only. It is not forge change
  ownership, commit authorship, contribution attribution, or permission to
  rewrite or publish the source branch.
- Unassigned nodes use null for both identities. Landed nodes release both
  identities and retain landing provenance through their landing head.
- One writer may own multiple active nodes only through distinct worktrees.
- A writer handoff changes ownership through a new receipt; it does not reuse
  an ambiguous label.
- A branch checked out elsewhere is a stop condition until ownership is
  reconciled.

Hashes may identify canonical paths or principals in portable receipts. Keep
machine-specific paths and personal identifiers out of shared artifacts.

## Landing Provenance

Keep the source `head_sha` even when the forge creates a different merge or
squash result. A landed node also binds `landing_head_sha`, the base integration
head produced by that landing.

- In sequential mode, each landed node targets the base branch. Every landed
  node after the first binds the previous landed node's integration head.
- In atomic-prefix mode, landed nodes retain the parent-source topology of the
  accepted prefix. The landed tip's integration head must equal the current
  base head.
- The first landed node's historical dependency remains bound by its expected
  parent head and proof; it is not rewritten to the newer current base head.

## Snapshot Collection

1. Fetch or query current remote state without mutation.
2. Resolve full object IDs and verify ancestry with repository-native Git
   evidence.
3. Exhaust forge pagination and normalize stable IDs.
4. Capture twice when concurrent updates are possible.
5. Accept only equal consecutive topology, head, target, and proof snapshots.
6. Hash canonical JSON only after validation.

Bound input size, node count, proof count, and string lengths before parsing
untrusted payloads.
