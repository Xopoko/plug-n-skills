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

Use full lowercase 40- or 64-hex object IDs. A shortened hash is display data,
not an identity. Keep human titles and free-form bodies outside the validation
contract.

Repository and forge scope are digest inputs, not display metadata. Use a
stable public-safe repository identifier or a stable digest when the canonical
name is sensitive. Never reuse a receipt across a different repository or
forge adapter merely because branches and object IDs happen to match.

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
