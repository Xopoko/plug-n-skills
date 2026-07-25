# State Commitment Contract

Use a state commitment when several companion artifacts describe current state
that can authorize work, stop work, or gate proof. The sidecar is the machine
authority; Markdown remains human-facing context.

This contract complements `commitment_ledger.v1`. The ledger checks whether
exact atoms survive a rewrite. It intentionally does not join records,
interpret JSON semantics, or decide which identity or proof is current.

## Command And Result

```bash
python3 "$PLUGIN_ROOT/skills/context-density/scripts/state_commitment_guard.py" \
  validate --input state-commitment.json
```

The command is read-only and emits one deterministic JSON object:

- exit `0`: the strict bundle, semantic bindings, and companion snapshots pass;
- exit `2`: the bundle is structurally valid but a semantic or snapshot
  commitment fails;
- exit `1`: the input is malformed, unsafe, unreadable, or outside parser
  bounds.

Do not infer a pass from companion prose or from a successful context-density
audit. Consume the guard's JSON and exit status.

## Closed Bundle Shape

The top-level object has exactly these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | string | Must be `context_density.state_commitment.v1`. |
| `state_version` | positive integer | Producer-assigned snapshot version. |
| `cutoff_utc` | UTC timestamp | Latest observation admitted to this snapshot. |
| `entities` | non-empty array | Typed current state records. |
| `stop_scopes` | array | Explicit action stops, separate from authority. |
| `source_refs` | non-empty array | Typed provenance records. |
| `commitment_digest` | lowercase SHA-256 | Digest of the canonical commitment core. |
| `companions` | non-empty array | Exact Markdown snapshots bound to the core. |

Unknown or missing fields, duplicate JSON keys, duplicate IDs, unsafe IDs,
unsupported enums, invalid timestamps, and wrong JSON types reject.

Each entity has exactly:

```text
id
identities
current_identity_ids
source_review
executable_proof
authority
confidence
conflict
```

Nested records use these closed shapes:

| Record | Required fields |
| --- | --- |
| identity | `id`, `kind`, `value`, `status`, `source_ref_ids`, `superseded_by` |
| source review | `status`, `identity_ids`, `source_ref_ids` |
| executable proof | `status`, `identity_ids`, `source_ref_ids`, `execution_count` |
| authority | `mode`, `actions`, `source_ref_ids` |
| confidence | `level`, `source_ref_ids` |
| conflict | `status`, `fallback`, `source_ref_ids` |
| stop scope | `id`, `status`, `entity_ids`, `actions`, `source_ref_ids` |
| source ref | `id`, `kind`, `location`, `observed_at_utc` |
| companion | `path`, `sha256` |

Closed enums:

- identity status: `current`, `superseded`;
- source-review status: `not_reviewed`, `in_progress`, `accepted`,
  `changes_requested`, `rejected`, `unavailable`;
- executable-proof status: `not_run`, `running`, `passed`, `failed`,
  `unavailable`;
- authority mode: `read_only`, `scoped_write`, `unknown`;
- confidence level: `high`, `medium`, `low`, `unknown`;
- conflict status: `none`, `resolved`, `unresolved`;
- conflict fallback: `none`, `fail_closed`, `revalidate`, `ask_user`;
- stop status: `active`, `inactive`;
- source kind: `identity`, `review`, `executable_proof`, `authority`,
  `confidence`, `conflict`, `stop`.

Status-dependent cardinality:

| State | Required bindings |
| --- | --- |
| Review `not_reviewed` | Empty identity and evidence arrays. |
| Any other review status | One or more current identities and review evidence refs. |
| Proof `not_run` | Count `0`; empty identity and evidence arrays. |
| Proof `running` | One or more current identities and proof evidence refs. |
| Proof `passed` or `failed` | Positive count, current identities, and proof evidence refs. |
| Proof `unavailable` | Count `0`, current identities, and proof evidence refs. |
| Confidence `unknown` | Empty evidence array. |
| Any known confidence | One or more confidence evidence refs. |
| Conflict `none` | Fallback `none`; empty evidence array. |
| Conflict `resolved` | Fallback `none`; one or more conflict evidence refs. |
| Conflict `unresolved` | Non-`none` fallback and conflict evidence refs. |

## Semantic Invariants

- Every identity kind in an entity has exactly one `current` identity.
  `current_identity_ids` must equal the set marked current.
- A current identity has `superseded_by: null`. A superseded identity points to
  a current identity of the same kind.
- Review and proof bindings reference only current identities in their entity.
  Review acceptance never implies executable proof, and proof passage never
  implies review acceptance. Their statuses do not silently become a universal
  action-authorization policy.
- Identity, review, proof, authority, confidence, conflict, and stop evidence
  may reference only matching source kinds. Every referenced source exists and
  was observed no later than `cutoff_utc`.
- `passed` and `failed` proof have a positive `execution_count`; `not_run` has
  zero. A passed proof has current identity bindings and proof evidence.
- `read_only` and `unknown` authority carry no actions. `scoped_write` carries
  one or more explicit actions. Authority evidence is mandatory.
- An inactive stop has no entity, action, or evidence bindings. An active stop
  has all three. Active stops subtract matching actions from the affected
  entities; they do not rewrite the recorded authority.
- An unresolved conflict uses a fail-closed fallback. The validator reports
  computed effective actions instead of asking consumers to reconstruct stop
  or conflict precedence.
- Confidence and conflict are explicit even when unknown or absent; omission is
  not interpreted as confidence or agreement.
- `has_effective_authority` describes only explicit authority after active stops
  and unresolved conflicts. Review, proof, and confidence remain separate
  observations unless a consumer applies its own typed policy.

## Digest And Companion Binding

Compute `commitment_digest` as SHA-256 over UTF-8 JSON for the top-level object
with `commitment_digest` and `companions` removed, serialized with sorted keys,
no insignificant whitespace, and unescaped Unicode.

Every companion:

1. is a unique, safe relative `.md` path below the sidecar directory;
2. resolves to a bounded regular file without traversal or symlink escape;
3. matches the exact SHA-256 of its file bytes; and
4. contains exactly one marker with the core digest:

```html
<!-- cda:state-commitment sha256:<commitment_digest> -->
```

The companion hash includes the marker. The core digest excludes companions,
so there is no hash cycle.

The validation output also emits `snapshot_digest`: SHA-256 over canonical JSON
containing the computed core digest and the companion manifest sorted by path.
Pin this value when a consumer must detect companion addition, removal,
or path/hash substitution independently of the sidecar location. Manifest order
does not change this seal.

The marker and byte hash prove that the reviewed snapshot did not drift. They
do not prove that prose was initially mapped to typed state correctly. Review
that mapping once before sealing the bundle; re-seal after any semantic or
companion edit.

## Deliberate Boundaries

The guard does not parse Markdown prose, fetch live state, generate sidecars,
repair conflicts, authorize actions, or replace task-specific proof. It
validates the producer's explicit snapshot and fails closed on contradictions,
digest mismatch, or companion drift.

The guard does not compare a prior `state_version`, enforce a maximum snapshot
age, or re-fetch source locations. Monotonicity and live freshness are consumer
policies; a bundle may be internally valid but old.
