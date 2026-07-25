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
| `schema` | string | Must be `context_density.state_commitment.v2`. |
| `state_version` | positive integer | Producer-assigned snapshot version. |
| `cutoff_utc` | UTC timestamp | Latest observation admitted to this snapshot. |
| `entities` | non-empty array | Typed current state records. |
| `stop_scopes` | array | Explicit action stops, separate from authority. |
| `source_refs` | non-empty array | Typed provenance records. |
| `commitment_digest` | lowercase SHA-256 | Digest of the canonical commitment core. |
| `companions` | non-empty array | Exact Markdown snapshots bound to the core. |

Unknown or missing fields, duplicate JSON keys, duplicate IDs, unsafe IDs,
unsupported enums, invalid timestamps, and wrong JSON types reject.

The unpublished draft `context_density.state_commitment.v1` did not require
source `origin_id` and cannot prove declared review/proof origin separation.
Migrate a draft-v1 bundle by adding producer-attested origins, setting schema
`v2`, recomputing `commitment_digest`, and resealing every companion hash and
marker. The guard intentionally rejects draft-v1 input instead of silently
weakening the v2 invariant.

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
| source ref | `id`, `origin_id`, `kind`, `location`, `observed_at_utc` |
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
- One current `(kind, value)` pair belongs to exactly one entity. Combine
  aliases and shared state in that entity; use an entity-scoped identity kind
  when a contextual value such as a revision may legitimately repeat.
- Identity values have canonical ASCII outer whitespace, contain at least one
  visible letter, number, punctuation mark, or symbol, and contain no Unicode
  control, format, surrogate, private-use, unassigned, or non-ASCII separator
  character.
- A current identity has `superseded_by: null`. A superseded identity points to
  a current identity of the same kind.
- Review and proof bindings reference only current identities in their entity.
  Review acceptance never implies executable proof, and proof passage never
  implies review acceptance. Their statuses do not silently become a universal
  action-authorization policy.
- Identity, review, proof, authority, confidence, conflict, and stop evidence
  may reference only matching source kinds. Every referenced source exists and
  was observed no later than `cutoff_utc`.
- Source locations contain visible text and no Unicode control, format,
  surrogate, private-use, unassigned, or non-ASCII separator character.
- Those Unicode-category checks use the frozen Unicode 3.2 database exposed by
  Python as `unicodedata.ucd_3_2_0`; code points unassigned there reject even
  when a newer host Unicode database assigns them.
- `origin_id` is a portable, producer-attested identifier shared by
  role-specific source refs declared to derive from the same underlying
  artifact, execution, review event, or evidence-producing source. It is
  intentionally reusable across refs, unlike globally unique record `id`.
  Declared review and executable-proof origins for one entity must be disjoint.
  One location cannot declare multiple origins when its strings are equal after
  ASCII outer whitespace is trimmed; comparison remains case-sensitive and
  performs no URI, filesystem, or service-specific alias resolution.
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

The guard lexically normalizes the input to an absolute path, opens every
parent component without following symlinks, and pins the sidecar's parent
directory while reading the input. It then opens every companion directory and
leaf relative to that descriptor and never reopens a multi-component pathname.
For every regular-file read it compares identity, size, mode, ownership, link
count, modification time, and change time before and after the read, so an
observed same-size in-place mutation also fails closed.
The input path must therefore use its canonical, symlink-free host spelling;
resolve trusted host aliases before invocation. Platforms without
descriptor-relative no-follow traversal reject with exit `1` instead of using
a pathname fallback.

Every companion:

1. is a unique, safe relative `.md` path below the sidecar directory, with no
   embedded NUL, frozen-Unicode `C*`, or non-ASCII separator character;
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

The marker and byte hash prove that the exact bytes read by one successful
validation match the hashes and core digest declared by that bundle.
Equivalence to a previously reviewed snapshot additionally requires an
independently pinned seal or immutable storage. Validation is not a filesystem
lock: a later writer can still change a file after the guarded read completes,
and immediate revalidation only narrows that window. A strict action-time
consumer must use immutable storage or consume the validated bytes or
descriptors within the same trusted operation. The seal also does not prove
that prose was initially mapped to typed state correctly. Review that mapping
once before sealing the bundle; re-seal after any semantic or companion edit.

## Deliberate Boundaries

The guard does not parse Markdown prose, fetch live state, generate sidecars,
repair conflicts, authorize actions, or replace task-specific proof. It
validates the producer's explicit snapshot and fails closed on contradictions,
digest mismatch, or companion drift.

The guard cannot independently establish that two different `origin_id` or
`location` spellings refer to different real sources. Producers must assign
canonical origins honestly; consumers that require external provenance proof
must verify it before sealing.

Current identity ownership is compared by exact, case-sensitive `(kind, value)`
pairs. The guard cannot infer that different spellings or kinds are real-world
aliases. Producers must assign canonical, entity-scoped identities; consumers
that require external identity proof must verify it before sealing.

The guard does not compare a prior `state_version`, enforce a maximum snapshot
age, or re-fetch source locations. Monotonicity and live freshness are consumer
policies; a bundle may be internally valid but old.
