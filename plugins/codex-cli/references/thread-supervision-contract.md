# Thread Supervision Contract

Use this reference for multi-thread watches, compaction-safe continuation,
authorized interventions, and capability extraction.

## Checkpoint

Keep the checkpoint compact and machine-readable when possible:

```json
{
  "schema": "codex.thread_supervision.v2",
  "goal": "bound supervision goal",
  "terminal_condition": "evidence-backed stop condition",
  "reporting_cadence": "transition-only or user-selected cadence",
  "supervisor_task_id": "opaque-supervisor-task-id",
  "supervisor_host_id": "opaque-supervisor-host-id",
  "continuation_owner": {
    "kind": "goal-runtime|heartbeat",
    "id": "opaque-native-heartbeat-id-or-null",
    "owner_task_id": "opaque-supervisor-task-id",
    "owner_host_id": "opaque-supervisor-host-id"
  },
  "heartbeat": {
    "id": "opaque-native-heartbeat-id-or-null",
    "owner_task_id": "opaque-supervisor-task-id",
    "owner_host_id": "opaque-supervisor-host-id",
    "logical_key": "stable-supervision-heartbeat-key",
    "definition_fingerprint": "stable-public-safe-fingerprint",
    "cadence": "user-bound-host-supported-cadence",
    "state": "create-pending|active|update-pending|result-unknown|retiring"
  },
  "private_data_boundary": [
    "data classes that stay ephemeral"
  ],
  "targets": [
    {
      "thread_id": "opaque-thread-id",
      "host_id": "opaque-host-id",
      "cursor": "opaque-cursor",
      "authorization": {
        "allowed_actions": [
          "observe",
          "send-skill-handoff"
        ],
        "conditions": [],
        "limits": [
          {
            "action": "send-skill-handoff",
            "remaining": 1
          }
        ],
        "expires_at": null
      },
      "state": "progressing|idle|attention|terminal|failed|ambiguous",
      "active_turn_id": "opaque-turn-id-or-null",
      "last_transition": "short factual transition",
      "verified_claims": [],
      "open_gates": [],
      "immutable_evidence": [],
      "protected_contract_fingerprint": "goal-policy-boundary-fingerprint",
      "protected_policy_application_state": {
        "schema": "codex.protected_policy_application_state.v1",
        "active_count": 1,
        "active_inline": [
          {
            "schema": "codex.protected_policy_application_checkpoint.v2",
            "application_id": "stable-opaque-application-id",
            "state": "mutation-outcome-unknown",
            "policy_revision_id": "opaque-user-authorized-revision",
            "operation_policy_fingerprint": "sha256:9dd14cec80c2351a274e120744602902aed7dfcb68f1fa8b9b21655cf17f6649",
            "recovery_ref": "opaque-protected-policy-application-recovery-ref",
            "intent_operation_id": "opaque-preallocated-intent-operation-id",
            "mutation_operation_id": "opaque-preallocated-mutation-operation-id"
          }
        ],
        "active_index_ref": null,
        "retired_index_ref": null
      },
      "current_contract_revision": null,
      "recent_revision_refs": [],
      "pending_intervention": null,
      "last_intervention_fingerprint": null,
      "last_reported_transition_fingerprint": null,
      "next_action": "one bounded observer action"
    }
  ],
  "prohibited_mutations": [],
  "private_evidence_refs": [],
  "capability_candidate_refs": []
}
```

Do not reconstruct a cursor, exact revision, approval state, or unresolved gate
from prose after compaction. Revalidate only drift-prone fields.

`continuation_owner` and `heartbeat` are `null` for a bounded current-turn
watch. An ongoing watch has exactly one continuation owner. When an active goal
runtime owns continuation, `continuation_owner.kind` is `goal-runtime` and
`heartbeat` is `null`. When a heartbeat owns continuation, its ID and owner
task and host must match `continuation_owner`, `supervisor_task_id`, and
`supervisor_host_id`. Keep exact IDs and the checkpoint recovery reference
ephemeral. The native heartbeat definition should load the checkpoint rather
than copy target IDs, private goal text, or evidence.

The heartbeat `logical_key` is stable for the life of the supervision run and
scoped to `supervisor_task_id` on `supervisor_host_id`. It is the fallback
identity when the stored native ID is absent or cannot be resolved. The
definition fingerprint records mutable desired configuration and must never be
used as heartbeat identity. During `create-pending` or `result-unknown`, the
heartbeat ID may be `null`; the owner, host, and logical key still reserve the
single continuation slot, so a second create is prohibited until the pending
result is reconciled.

Keep only current claims, gates, and evidence needed for the next decision.
Limit each inline list to eight entries and keep at most five active capability
candidate references. `protected_policy_application_state.active_inline` is
complete only while `active_count <= 8`. When the ninth application is captured,
set `active_inline=[]` and persist every active entry, in capture order, in the
typed content-addressed record named by `active_index_ref`; never truncate the
active set. Externalize superseded history to private evidence artifacts rather
than growing the checkpoint.

`open_gates` contains only currently applicable blockers. Bind every entry to a
current live subject or explicit policy requirement, eligibility evidence, and
an owner. Capability availability, mutation authority, or a possible workflow
step does not make an action required. When a complete inventory contains zero
eligible targets for a conditional action, keep that action out of
`open_gates`; record `not-applicable` in the transition or private evidence only
when the decision matters. Never create an external object or write merely to
make a checkpoint gate exist.

Represent each open gate as a structured claim:

```json
{
  "gate_id": "stable-public-safe-gate-id",
  "kind": "proof|policy|approval|input|external-action",
  "subject_ref": "opaque-current-live-subject-or-policy-ref",
  "eligibility_state": "eligible",
  "eligibility_evidence_ref": "opaque-current-evidence-ref",
  "eligibility_cutoff": "opaque-cursor-revision-or-timestamp",
  "eligibility_owner": "owning-workflow-or-policy",
  "owner": "target|user|reviewer|external-system",
  "required_transition": "bounded evidence-backed terminal condition"
}
```

For a domain-specific conditional action, the eligibility receipt comes from
the workflow or policy that owns that action. The supervisor may normalize the
receipt into the checkpoint, but it must not synthesize eligibility. Remove or
reclassify the gate after subject, cutoff, eligibility, or owner drift.

`pending_intervention` is either `null` or a compact object containing the
action, schema, immutable intervention ID, payload fingerprint, immutable
content-addressed payload recovery ref, revision ID when applicable, delivery
state, and acknowledgement state. A skill handoff also retains its expected
source digest and requested consumption mode. Keep only one pending
intervention per target. A second write requires proof that the first was not
delivered or a terminal acknowledgement. Local abandonment does not restore
the consumed limit or authorize a resend.
`recent_revision_refs` retains at most eight applied, conflicted, stale, or
superseded revision IDs; externalize older revision bodies to private evidence.

The protected contract contains the user goal, terminal condition, reporting
cadence, per-target authorization and limits, prohibited mutations,
private-data boundary, and task constraints. Evidence revisions never modify
it. Fingerprint that protected state separately so the receiver can reject a
message formed against different authority.

`protected_policy_application_state.active_count=0`, `active_inline=[]`, and
`active_index_ref=null` mean no affected policy application is active.
Otherwise the inline entries or resolved active index form one append-only,
capture-ordered collection with a unique `application_id`, policy revision, and
recovery ref per entry; never overload `current_contract_revision` or
`pending_intervention`. The active index has schema
`codex.protected_policy_application_active_index.v1`, exactly `active_count`
entries, and no duplicate application, revision, or recovery identity. Its
content-addressed ref changes on append or terminal removal.

A later revision is appended without replacing, coalescing, or reusing an
earlier nonterminal record. Persist each immutable content-addressed private
`recovery_ref` before its adoption, intent, mutation, or readback attempt. Its
typed `codex.protected_policy_application_recovery.v2` record binds the same
application ID and policy revision, its exact `checkpoint_state`, the
operation-policy fingerprint, the receiver, exact authorized intent-store
schema/ref/authorization, canonical intent ref, destination, subject,
owning-system operation namespace, and both operation IDs. This is one closed
record shape: reject missing or extra fields and never substitute a smaller
checkpoint projection. State, policy fingerprint, receiver, store,
authorization, intent, destination, subject, and operation namespace bindings
are bounded and non-null in every record; only operation IDs, the two chain-edge
refs, and the all-or-none migration-provenance fields may be null where the
lifecycle permits. The pair of
operation namespace and operation ID is globally unique across active and
retired applications. When a recovery head changes, the new record names the
previous
`recovery_ref` as its predecessor; the stable application identity is the
application ID plus policy revision, not the recovery-head ref. Validate every
intermediate recovery record. The application, revision, receiver, store,
intent, destination, subject, operation namespace, and required operation-policy
fingerprint never change within the chain. Migration ref, immutable source
checkpoint ref and fingerprint, and source target/host are all null for a native
v2 root. For an explicit v1 migration they are all non-null, bind the exact
migration attestation and resolved source checkpoint, and remain unchanged in
every successor. Either operation ID may be allocated once where the closed
lifecycle permits it; every later successor retains that exact value.
Every successor's `checkpoint_state` must be one exact edge on the closed state
graph, and the checkpoint entry state must equal its recovery head's state.
Treat every lifecycle, checkpoint-state, terminal-outcome, and reconciliation
state enum as a bounded string before membership checks; malformed composite
values fail closed rather than aborting validation.
Every non-null reconciliation ref resolves to the exact owning-system receipt
for that predecessor-successor edge. Require a reconciliation ref if and only
if an unknown predecessor state advances; it binds both recovery refs and their
exact stored states. Any other reconciliation ref is unused or spurious and
fails closed. A checkpoint transition that changes state appends exactly one
successor, so an intermediate edge cannot hide the real before/after pair. A
later ordinary advance appends another state-bearing successor and remains
valid without reusing the prior reconciliation.
A newly appended application starts with a root recovery record at
`revision-captured`: both `predecessor_ref` and
`reconciliation_receipt_ref` are null. An ordinary v2 append at any later state
fails closed. Only a later checkpoint transition may advance that recovery head.

Application state follows this closed monotonic graph:

- `revision-captured -> adoption-pending -> intent-pending`;
- `intent-pending -> intent-outcome-unknown|mutation-pending`;
- `mutation-pending -> mutation-outcome-unknown|readback-pending`;
- `intent-outcome-unknown -> mutation-pending` and
  `mutation-outcome-unknown -> readback-pending` only after reconciliation;
- any nonterminal state may become `terminal`; `terminal` cannot reopen.

A state may remain unchanged. It cannot move backwards or skip an unlisted
edge. When either write outcome is unknown, retain that exact application ID,
policy revision, operation-policy fingerprint, operation namespace, intent
operation ID, and mutation operation ID. An unknown state is sticky: it may
change or retire only through an exact
`codex.protected_policy_application_reconciliation.v1` receipt issued by the
owning system. The receipt binds the application and revision, before and after
states, before and after recovery refs, and both operation IDs. A later
revision may be captured and rebound, but it cannot authorize retrying or
discarding an earlier unknown operation.

Only independently proven terminal evidence may remove an active entry.
`retired_index_ref` names the newest immutable
`codex.protected_policy_application_retired_index.v1` record. Each record binds
its predecessor ref and at most eight typed terminal tombstones; the chain is
append-only. Every tombstone binds one application ID, policy revision,
recovery ref, and terminal receipt ref, and that terminal receipt independently
echoes all four identities. Active and retired identities are globally unique.
Never drop or reuse an application ID, revision ID, recovery ref, or
operation-namespace-plus-operation-ID pair. A transition may add a tombstone
only for an entry that was active in the immediately preceding checkpoint.
The terminal application receipt and tombstone name the exact recovery head
whose `checkpoint_state` is `terminal`. Retiring a nonterminal active entry
appends exactly that one terminal successor; no intermediate recovery may hide
the actual predecessor-terminal edge. If the predecessor state was unknown,
that terminal head itself carries the required reconciliation edge, and the
terminal receipt's reconciliation ref equals the head recovery record's
`reconciliation_receipt_ref`.
Resolve the terminal receipt's producer authority and its exact v2 application
receipt, evaluate that application receipt independently, and require its
closed result to equal `terminal_application`. If the predecessor state was
unknown, also resolve the owning-system reconciliation receipt. Resolve the
terminal recovery and application receipt through the same immutable evidence
store; a separate built-in or substituted recovery cannot authorize retirement.

### Checkpoint schema migration

Never interpret a v1 checkpoint directly as v2. Migration consumes the complete
v1 checkpoint root and selects exactly one nested `targets[]` entry by both
thread ID and host ID. A v1 target that contains the provisional singular
`protected_policy_application` field may be migrated only after loading its
immutable recovery record and persisting a typed
`codex.protected_policy_application_migration.v1` record. Its `migration_ref` is
the canonical `sha256:` fingerprint of that complete strict-JSON record. The
migration binds the immutable source-checkpoint ref, canonical full-checkpoint
fingerprint, exact target identity, legacy recovery ref, revision and operation
IDs to a new stable application ID, operation namespace, and new v2 recovery
ref whose record echoes the same identities plus the exact migrated checkpoint
state. The typed migration record's `migrated_recovery_ref` must equal the
actual recovery root ref being validated; a coherently rehashed record with
another schema or root ref still fails closed. The fingerprint is
`sha256:` plus lowercase SHA-256 of strict UTF-8
JSON with recursively sorted object keys, no insignificant whitespace, array
order preserved, and non-JSON constants rejected. A present `null` singular
field migrates to the explicit empty v2 state. A v1 checkpoint without the
singular field may migrate empty only when
an independently resolved source-contract revision proves that exact
checkpoint fingerprint predates protected-policy applications and an exact
cutoff-bound immutable evidence inventory for that target contains no
application recovery record. Its typed evidence count is the exact JSON integer
zero, never a boolean or floating-point substitute. Replaying either proof
against another checkpoint or target fails closed. Missing proof, malformed
legacy state, both singular and v2 state, or an unresolved migration write fails
closed; do not resume mutation. Validate the branch-specific migration or
pre-feature proof ref as a
bounded non-null scalar before evidence lookup. A null-key evidence-map entry
never supplies a missing ref. Only this exact migration attestation may preserve
a later-state recovery as the root of a v2 application. Resolve the retained
source-checkpoint ref, recompute its canonical fingerprint, and select exactly
one matching source target before accepting the legacy application. The
migration ref, source ref and fingerprint, and source target/host are retained
on the migrated root and every successor, so an unrelated ambient attestation
or a rebound source cannot validate the chain. Without that explicit
provenance, the later-state root is invalid. Validate the migration record's
operation IDs against that root record, not against a later recovery head;
when the migrated root has null IDs, the ordinary one-time allocation rule
still applies to its legal successors.

The private indexes and terminal proof use these closed projections:

```json
{
  "active_index": {
    "schema": "codex.protected_policy_application_active_index.v1",
    "active_count": 1,
    "applications": [
      {
        "schema": "codex.protected_policy_application_checkpoint.v2",
        "application_id": "stable-opaque-application-id",
        "state": "mutation-outcome-unknown",
        "policy_revision_id": "opaque-policy-revision",
        "operation_policy_fingerprint": "opaque-operation-policy-fingerprint",
        "recovery_ref": "opaque-v2-recovery-ref",
        "intent_operation_id": "opaque-intent-operation-id",
        "mutation_operation_id": "opaque-mutation-operation-id"
      }
    ]
  },
  "retired_index": {
    "schema": "codex.protected_policy_application_retired_index.v1",
    "predecessor_ref": null,
    "tombstones": [
      {
        "schema": "codex.protected_policy_application_terminal.v1",
        "application_id": "stable-opaque-application-id",
        "policy_revision_id": "opaque-policy-revision",
        "recovery_ref": "opaque-v2-recovery-ref",
        "terminal_receipt_ref": "opaque-terminal-receipt-ref"
      }
    ]
  },
  "terminal_receipt": {
    "schema": "codex.protected_policy_application_terminal_receipt.v1",
    "producer": "codex-thread-supervisor",
    "producer_authority_ref": "opaque-terminal-producer-authority-ref",
    "application_id": "stable-opaque-application-id",
    "policy_revision_id": "opaque-policy-revision",
    "recovery_ref": "opaque-v2-recovery-ref",
    "application_receipt_ref": "opaque-v2-application-receipt-ref",
    "reconciliation_receipt_ref": "opaque-owning-system-reconciliation-ref-or-null",
    "terminal_application": "applied"
  }
}
```

The active-index object above illustrates one entry's closed shape; a checkpoint
references this index only when its real count exceeds eight. Each
`applications` item is the exact checkpoint-entry object, not prose or a partial
identifier. Each retired-index record has one to eight tombstones, and
`terminal_application` is exactly one of
`invalid|blocked|applied|policy-drift`. Resolve and validate the predecessor
chain before accepting its identity set. A repacked list without the prior ref
is not a successor. Resolve `producer_authority_ref` and require it to authorize
this producer, terminal receipt, and exact application receipt. Evaluate the
resolved application receipt rather than trusting the terminal label. A
terminal receipt is not sufficient unless its tombstone identity was active in
the immediately preceding checkpoint.

## Protected Policy Application

A direct user revision to the protected contract is control-plane state, not
observer evidence. Capture it even when the target already has an unrelated
pending intervention. That pending intervention keeps its delivery and
acknowledgement state, but it neither serializes protected-policy capture nor
proves that the receiver adopted the new revision.

Before an affected external mutation can be accepted, require a receiver-owned
rebind to the exact protected revision and fingerprint. A rebind is not a new
intervention action: use only an already authorized typed receiver mechanism.
If no such mechanism exists, set
`receiver_adoption.status=capability-unavailable`, keep the affected mutation
blocked, and do not send an unlisted target message or smuggle policy through
`send-evidence-delta`.

The operation policy must enumerate every mandatory external-object field
before the write. Bind field refs, independently recoverable expectation
evidence, and keyed, non-reversible expected-value fingerprint envelopes rather
than private values. The only supported envelope is `hmac-sha256` with a
`sha256:` key-reference fingerprint and a lowercase 64-hex digest; a raw value
or bare digest is malformed. Derive it with an authorized key and a
domain-separated message that binds the schema and field ref. Never use an
unsalted digest for a low-entropy field. After the authorized mutation, read
back the exact object identity and
every mandatory field from the owning system at a current cutoff. Each readback
result binds its field ref, keyed observed-value fingerprint envelope, and an
opaque owning-system evidence ref. Independently resolve the expectation and
observation evidence to verify the authorized key, derivation scheme, field
subject, and digest. Object existence, a related field, actor intent, target
activity, or a pending intervention acknowledgement is not proof of policy
application.

Envelope equality and receipt- or evidence-supplied provenance are never
verification. Invoke a configured verifier whose trust root is selected outside
the receipt and its evidence map. That verifier resolves the authorized key
reference, independently obtains the normalized expectation or owning-system
observation bound to the evidence ref and field ref, recomputes
`HMAC-SHA-256(key, "codex.protected-policy-field.v1" || NUL ||
UTF8(field_ref) || NUL || normalized_value)`, and compares both the
key-reference fingerprint and digest in constant time. The verifier retains the
key and normalized value privately. Because NUL is the v1 delimiter,
`field_ref` must not contain U+0000 in policy, result, or verifier-source
records; reject it before derivation. Normalized values remain arbitrary bytes.
A caller-coordinated expectation,
observation, and evidence map with matching envelopes is still invalid. For a
verified `missing` result, the same owning-system resolver proves absence and
the observed fingerprint remains null; absence never fabricates an HMAC.

For a schema-valid `operation_policy`, let `C` be its
`codex.protected-policy-operation-json.v1` canonical bytes and fingerprint it
as `sha256:` plus lowercase hexadecimal SHA-256 of `C`. The recipe label names
the encoding and is not part of `C`. Reject duplicate object names at JSON
ingress and validate the exact closed schema before encoding. V1 object names
are only the schema's fixed ASCII names; emit them recursively in ascending
ASCII-byte order, with no whitespace or BOM, and preserve array order. In
strings, escape quotation mark and reverse solidus as `\"` and `\\`; use
`\b`, `\t`, `\n`, `\f`, and `\r` for those five controls; encode every other
U+0000 through U+001F control as lowercase `\u00xx`; never escape solidus; and
emit every other Unicode scalar literally before UTF-8 encoding. Preserve the
exact Unicode scalar sequence without normalization and reject unpaired
surrogates. The closed schema admits only objects, arrays, and strings, so
reject null, booleans, and all numbers. Canonicalize parsed values: literal
non-ASCII and equivalent valid `\uXXXX` or surrogate-pair input escapes produce
the same `C`; canonically equivalent but distinct scalar sequences such as NFC
and NFD remain distinct. Persist an
immutable pre-write intent after receiver adoption and before the mutation only
through an existing authorized intent store. Never create or emulate that store
with an ordinary write under supervision authority. If it is unavailable, keep
the affected external mutation blocked. If intent creation has an unknown
outcome, reconcile it before any external mutation. The intent receipt names the
fixed store schema, exact store, existing authorization, a preallocated
intent-store operation ID, the preallocated owning-system mutation operation
ID, receiver identity and acknowledgement, operation-policy fingerprint, and
immutability evidence. The external mutation uses that retained mutation
operation ID and binds it to the exact destination, subject, intent operation,
and intent ref. These operation IDs remain available when a write receipt is
missing after an unknown outcome. The complete readback binds both the exact
mutation operation ID and mutation receipt plus
owning-system evidence that the readback is post-mutation. Presence of these
refs is insufficient: independently resolve them and verify the named store,
authorization, receiver, subject, fingerprints, operation identities, and
ordering relation.

This example is a complete `applied` receipt:

```json
{
  "schema": "codex.protected_policy_application.v2",
  "application_id": "stable-opaque-application-id",
  "policy_revision_id": "opaque-user-authorized-revision",
  "authorizer": "user",
  "from_protected_contract_fingerprint": "prior-protected-fingerprint",
  "to_protected_contract_fingerprint": "current-protected-fingerprint",
  "receiver_thread_id": "opaque-receiver-thread-id",
  "operation_policy_fingerprint": "sha256:9dd14cec80c2351a274e120744602902aed7dfcb68f1fa8b9b21655cf17f6649",
  "recovery_ref": "opaque-protected-policy-application-terminal-recovery-ref",
  "receiver_adoption": {
    "status": "adopted",
    "receiver_thread_id": "opaque-receiver-thread-id",
    "acknowledgement_ref": "opaque-receiver-owned-ack-ref",
    "policy_revision_id": "opaque-user-authorized-revision",
    "from_protected_contract_fingerprint": "prior-protected-fingerprint",
    "to_protected_contract_fingerprint": "current-protected-fingerprint",
    "operation_policy_fingerprint": "sha256:9dd14cec80c2351a274e120744602902aed7dfcb68f1fa8b9b21655cf17f6649",
    "cutoff": "opaque-receiver-adoption-cutoff"
  },
  "operation_policy": {
    "destination_ref": "opaque-external-system-ref",
    "subject_ref": "opaque-action-intent-or-object-ref",
    "operation": "create",
    "eligibility_cutoff": "opaque-revision-or-timestamp",
    "mandatory_fields": [
      {
        "field_ref": "opaque-domain-field-ref",
        "expected_value_fingerprint": {
          "scheme": "hmac-sha256",
          "key_ref_fingerprint": "sha256:1807dbf17817a8d83d0b098f063b16bd2d904809e8cf0731ffa3ff2c68aa30dd",
          "digest": "8fab1805ae51245c10795c447a58e0196bc67352e4e2e8ba663979929778238c"
        },
        "expectation_evidence_ref": "opaque-keyed-expectation-proof-ref"
      }
    ]
  },
  "prewrite_intent": {
    "status": "created",
    "store_schema": "codex.authorized_immutable_intent_store.v1",
    "store_ref": "opaque-authorized-intent-store-ref",
    "store_authorization_ref": "opaque-intent-store-authorization-ref",
    "operation_id": "opaque-preallocated-intent-operation-id",
    "mutation_operation_id": "opaque-preallocated-mutation-operation-id",
    "intent_ref": "opaque-immutable-prewrite-intent-ref",
    "receiver_thread_id": "opaque-receiver-thread-id",
    "receiver_acknowledgement_ref": "opaque-receiver-owned-ack-ref",
    "operation_policy_fingerprint": "sha256:9dd14cec80c2351a274e120744602902aed7dfcb68f1fa8b9b21655cf17f6649",
    "relation": "after-adoption",
    "ordering_evidence_ref": "opaque-adoption-before-intent-proof-ref",
    "immutability_evidence_ref": "opaque-intent-immutability-proof-ref",
    "cutoff": "opaque-prewrite-intent-cutoff"
  },
  "mutation": {
    "state": "committed",
    "operation_id": "opaque-preallocated-mutation-operation-id",
    "destination_ref": "opaque-external-system-ref",
    "subject_ref": "opaque-action-intent-or-object-ref",
    "result_object_ref": "opaque-object-id",
    "receipt_ref": "opaque-owning-system-write-receipt",
    "prewrite_intent_operation_id": "opaque-preallocated-intent-operation-id",
    "prewrite_intent_ref": "opaque-immutable-prewrite-intent-ref",
    "cutoff": "opaque-mutation-cutoff"
  },
  "readback": {
    "state": "complete",
    "object_ref": "opaque-object-id",
    "cutoff": "opaque-post-mutation-cutoff",
    "mutation_operation_id": "opaque-preallocated-mutation-operation-id",
    "mutation_receipt_ref": "opaque-owning-system-write-receipt",
    "relation": "after-mutation",
    "ordering_evidence_ref": "opaque-mutation-before-readback-proof-ref",
    "field_results": [
      {
        "field_ref": "opaque-domain-field-ref",
        "observed_value_fingerprint": {
          "scheme": "hmac-sha256",
          "key_ref_fingerprint": "sha256:1807dbf17817a8d83d0b098f063b16bd2d904809e8cf0731ffa3ff2c68aa30dd",
          "digest": "8fab1805ae51245c10795c447a58e0196bc67352e4e2e8ba663979929778238c"
        },
        "evidence_ref": "opaque-owning-system-readback-ref",
        "status": "matched"
      }
    ]
  },
  "application": "applied"
}
```

Closed states are:

- `receiver_adoption.status`:
  `not-proven|adopted|conflict|capability-unavailable`;
- `prewrite_intent.status`:
  `not-created|created|capability-unavailable|outcome-unknown`;
- `prewrite_intent.store_schema`:
  `codex.authorized_immutable_intent_store.v1`;
- `prewrite_intent.relation`: `after-adoption`;
- `mutation.state`: `not-attempted|committed|outcome-unknown`;
- `readback.state`: `not-run|complete|unavailable`;
- `readback.relation`: `after-mutation`;
- each field result `status`: `matched|mismatched|missing|unavailable`;
- `application`:
  `invalid|blocked|applied|policy-drift|reconciliation-required`.

Every populated ref, cutoff, and fingerprint is a non-empty string of at most
1024 UTF-8 bytes. Reject oversized strings, objects, arrays, numbers, and
booleans before receipt construction. A null is allowed only for a field whose
closed state explicitly says that no observation was made. The keyed
fingerprint envelope is the sole structured exception: it has exactly
`scheme`, `key_ref_fingerprint`, and `digest`, all with the formats defined
above.

`mandatory_fields` is non-empty and unique by `field_ref`. An adopted receiver
acknowledgement echoes the top-level receiver identity, policy revision, and
both protected fingerprints, binds the operation-policy fingerprint, and
supplies a receiver-owned acknowledgement ref and cutoff. The independently
recovered pre-write intent must prove the fixed store schema, exact authorized store,
authorization, immutability, and `after-adoption`, and bind that exact receiver,
acknowledgement, policy fingerprint, and preallocated owning-system mutation
operation ID. The independently recovered mutation receipt must bind the exact
destination, subject, retained mutation operation ID, intent operation ID, and
intent ref plus the canonical object produced or targeted by that mutation.
`mutation.result_object_ref` echoes that owning-system object identity. A
claimed `mutation.state=committed` must carry that exact receipt ref and a
non-empty commit cutoff; either missing field makes the receipt invalid. If an
attempt has no durable commit receipt, retain `outcome-unknown` and its matching
nonterminal recovery head instead of claiming committed reconciliation. A
complete readback proves `after-mutation`, binds that exact mutation operation
ID and receipt, and has `readback.object_ref` exactly equal to the recovered
mutation result object. Merely reading another object with matching fields is
not causal evidence. The readback
contains exactly one result for every mandatory field and no others. Every
matched result has independently recoverable expectation and owning-system
observation evidence and an observed keyed fingerprint envelope equal to the
expected envelope.

Resolve evidence through the owning receiver, intent store, or external system,
not through receipt-supplied prose. The normalized resolved records must exactly
echo their subject bindings: receiver and policy fingerprints for adoption;
store schema, store identity, authorization, both operation IDs, receiver, and
policy for the intent; destination, subject, operation IDs, intent ref, and
cutoff for the mutation; and object, mutation identity, cutoff, field ref,
fingerprint envelope, and status for field readback. An unresolved,
substituted, or differently bound ref cannot support `application=applied`.
Independently load `recovery_ref` from the private immutable recovery store. Its
`codex.protected_policy_application_recovery.v2` record binds the application
ID, policy revision, exact checkpoint state, receiver, operation-policy
fingerprint, exact authorized intent-store schema/ref/authorization, canonical
intent ref, destination, subject, owning-system operation namespace, both
preallocated operation IDs, its predecessor recovery ref, and any
reconciliation receipt ref. The receipt cannot replace that record or supply
an alternate resolver. The generic evidence map is not a recovery resolver:
changing a receipt, its evidence echoes, and map entries under `recovery_ref`
cannot replace the independently loaded private record.
An unknown intent receipt must name the active `intent-outcome-unknown` recovery
head, and an unknown mutation receipt must name the active
`mutation-outcome-unknown` head. A terminal, crossed, substituted, or otherwise
stale recovery head is invalid; append and bind an owning-system reconciliation
successor before evaluating a later terminal receipt.
The evaluator receives the current checkpoint recovery-head ref independently
of the receipt and requires exact equality before classifying any result. A
receipt-supplied ref cannot declare itself current, and an older same-state
recovery is invalid after a successor becomes the retained head.
After receipt shape, closed states, bounded scalar formats, exact
recovery-to-receipt application, revision, receiver, recomputed
operation-policy, destination, and subject bindings, and durable operation IDs
are valid, an unknown intent or mutation outcome takes precedence over every
later semantic policy or evidence mismatch. Reconcile it before classifying
the remaining defect or permitting a retry. A malformed receipt whose unknown state,
recovery identity, or operation identity cannot be trusted remains `invalid`.
For an unknown mutation, the destination, subject, mutation operation ID,
retained intent operation ID, and retained intent ref must exactly equal the
corresponding identities in the immutable recovery record. Presence alone is
insufficient. For a committed mutation with incomplete or unavailable
readback, retain that same trusted mutation-to-intent identity and independently
resolve the canonical owning-system mutation receipt before returning
reconciliation. Any conflicting readback operation or receipt identity is
invalid rather than a reconciliation target. `readback.state=not-run` carries
no readback observation at all.
`readback.state=unavailable` carries only the exact retained mutation operation
ID and mutation receipt ref; object, cutoff, ordering, and field-result
observations remain null or empty. Only `complete` may carry those observations.
A non-complete state with populated observation fields is contradictory and
invalid, not a reconciliation target. An unknown intent-store write must use
the exact recovered store schema,
store ref, authorization ref, and preallocated intent operation ID; a
receipt-supplied store namespace is not a reconciliation target. That early
intent reconciliation is valid only with `mutation.state=not-attempted`, every
mutation observation null, `readback.state=not-run`, and every readback
observation null or empty. A claimed later mutation or readback makes the
receipt invalid; it cannot be hidden behind the earlier unknown intent.
This includes a simultaneous `mutation.state=outcome-unknown`.
Any committed mutation whose readback is not yet complete or contains an
unavailable field must bind the active `readback-pending` recovery head.
For a complete readback, an unavailable field reaches reconciliation only
after the exact object, mutation operation and receipt, `after-mutation`
ordering evidence, exact mandatory-field set, and owning-system unavailability
evidence are independently valid. A missing or conflicting causal binding
remains policy drift; the unavailable status cannot mask it.
Reserve `terminal` for a closed result whose terminal receipt can be retained
or retired; a recoverable readback cannot claim that state.
Every blocked pre-adoption or capability-unavailable state is canonical:
intent must remain unwritten, mutation must be cleanly `not-attempted`, and
readback must be cleanly `not-run`. Creating the intent before exact receiver
adoption is `policy-drift`; carrying any mutation or readback observation while
claiming `not-attempted` is `invalid`.
Incomplete or unavailable readback reaches reconciliation only after exact
receiver adoption and pre-write intent ordering and evidence are valid.
For every structurally valid receipt, the declared `application` must equal the
independently computed result below. A declaration never overrides the
evidence-derived result, and declaring `invalid` does not repair malformed
evidence.

Evaluate this precedence atomically:

| Condition | Required result |
| --- | --- |
| Direct user revision while unrelated evidence or skill intervention is pending | Capture the protected revision; preserve the pending intervention; keep the affected mutation blocked until receiver adoption |
| Malformed receipt, empty mandatory set, or duplicate mandatory or result field refs | `application=invalid` |
| Declared application differs from the independently computed closed result | `application=invalid` |
| No authorized typed receiver rebind with no intent, mutation, or readback observation | `receiver_adoption.status=capability-unavailable`, `mutation.state=not-attempted`, `application=blocked` |
| Receiver has not proven the exact revision and fingerprint, and intent, mutation, and readback remain unwritten | `receiver_adoption.status=not-proven`, `mutation.state=not-attempted`, `application=blocked` |
| Receiver reports a revision or protected-fingerprint conflict while intent, mutation, and readback remain unwritten | `receiver_adoption.status=conflict`, `mutation.state=not-attempted`, `application=blocked` |
| Intent is created before exact receiver adoption | `application=policy-drift` |
| A not-attempted mutation carries any mutation or readback observation | `application=invalid` |
| Mutation outcome is unknown after exact recovery and mutation identity validation, regardless of a later semantic or evidence defect | `mutation.state=outcome-unknown`, `application=reconciliation-required` |
| Intent creation outcome is unknown, regardless of another policy defect | `prewrite_intent.status=outcome-unknown`, `mutation.state=not-attempted`, `application=reconciliation-required` |
| Recovery application, revision, receiver, operation-policy, destination, or subject binding differs, or the claimed policy fingerprint does not equal canonical policy recomputation | `application=invalid` before any reconciliation request |
| Unknown mutation carries a different destination, subject, operation ID, intent operation ID, or intent ref | `application=invalid` |
| Mutation is attempted or committed without exact receiver adoption | `application=policy-drift` |
| Receiver acknowledgement names a different receiver, revision, or fingerprint | `application=invalid` |
| Operation-policy fingerprint or keyed fingerprint envelope is malformed or differs at adoption, intent, or readback | `application=invalid` |
| Matching fingerprint envelopes or evidence echoes lack independent authorized-verifier recomputation | `application=invalid` |
| No existing authorized immutable intent store | `prewrite_intent.status=capability-unavailable`, `mutation.state=not-attempted`, `application=blocked` |
| Created intent lacks exact store schema, store identity, authorization, either operation ID, or immutability evidence | `application=invalid` |
| Pre-write intent does not bind the exact receiver acknowledgement or prove `after-adoption` | `application=policy-drift` before mutation; committed mutation is invalid |
| Exact receiver adoption is proven but no mutation is attempted | `mutation.state=not-attempted`, `application=blocked` |
| Committed mutation lacks its exact receipt or cutoff, or the mutation receipt does not bind the exact destination, subject, operation ID, pre-write intent, or result object | `application=invalid` |
| A non-complete readback carries object, cutoff, ordering, or field-result observations | `application=invalid` |
| Readback object differs from the recovered mutation result object, does not bind the exact operation ID and receipt, or does not prove `after-mutation` | `application=policy-drift` |
| Committed mutation has canonical clean `not-run` or mutation-bound `unavailable` readback, or a causally bound complete readback has independently proven unavailable fields | `checkpoint_state=readback-pending`, `application=reconciliation-required` |
| Any mandatory field is missing, extra, mismatched, or has a different observed fingerprint | `application=policy-drift` |
| An independently proven field result is unavailable after exact causal binding and exact result-set validation | `application=reconciliation-required`; another missing, extra, or mismatched result remains `policy-drift` |
| Exact receiver adoption, committed mutation, object identity, cutoff, and every keyed field result match | `readback.state=complete`, `application=applied` |

This receipt is a supervision verdict, not mutation authority, intent-store
authority, or a canonical store implementation. Keep private field values and
raw provider payloads out of it.

## Canonical Checkpoint Adoption

A producer-owned transition receipt validates only the exact snapshots supplied
to that producer. It does not prove that its predecessor is the retained
canonical checkpoint or that any canonical pointer changed. Candidate-supplied
predecessor metadata is not authority.

Adoption is available only when the task has explicit mutation authority and an
existing canonical store interface that atomically compare-and-swaps a full
head token and records the CAS outcome under one operation ID. Never emulate this
with a read followed by an ordinary write. Without that interface, stop at
`pair=valid`, set `adoption=capability-unavailable`, and keep the candidate
noncanonical.

A canonical head token binds the store fingerprint, chain ID, unique monotonic
generation, snapshot fingerprint, predecessor head-token fingerprint, and
creating intent or baseline receipt fingerprint. Comparing only snapshot
content is insufficient: two forks may contain the same snapshot, and an
A-to-B-to-A sequence must not recreate an old head token. The store defines a
versioned canonical serialization and digest algorithm for that token. A
transition receipt used for adoption binds the resulting canonical
head-token fingerprint plus its schema version. A pair-only receipt without
that binding is valid only as pair evidence.

Treat canonical adoption as a separate consumer-owned commit:

1. Independently load the store fingerprint, chain ID, full current head token,
   and retained receipt named by that token.
2. Require the producer receipt's basis head-token fingerprint to equal the
   canonical fingerprint of the full current token under the named schema
   version. Require its `from.snapshot_fingerprint` to equal that token's
   snapshot fingerprint, its protected-contract fingerprint to match the
   retained contract, and its `to.snapshot_fingerprint` to equal the candidate.
3. Reject a store or chain mismatch as `namespace-mismatch`. Reject protected
   goal or authority drift as `protected-mismatch`; ordinary adoption never
   edits the protected contract. A separately authorized, typed new-chain or
   rebind receipt must name its authorizer, policy, old contract, new contract,
   and destination chain. It cannot repair a namespace mismatch.
4. Build an immutable pre-CAS adoption intent, then ask the authorized store to
   atomically replace the full expected token with the fresh candidate token
   and persist the native operation result under the intent's operation ID. A
   different observed token is `head-conflict`; preserve it and perform at most
   one bounded read-only reconciliation.
5. Read back the full token and native operation result, then emit a terminal
   adoption receipt. Report `adopted` only when both match. If the commit
   outcome or readback is unknown, report
   `reconciliation-required`; never report `not-adopted` or retry the mutation
   until the operation ID is reconciled.

Keep pair, lineage, protection, commit, readback, and adoption as independent
closed verdict fields:

```json
{
  "schema": "codex.checkpoint_adoption.v1",
  "pair": "valid|invalid|unknown",
  "lineage": "valid|baseline-valid|unbound|mismatch|namespace-mismatch|unknown",
  "protection": "valid|mismatch|authorized-new-chain|unknown",
  "commit": "not-attempted|committed|conflict|id-conflict|outcome-unknown",
  "readback": "not-run|matched|different|unavailable",
  "adoption": "not-eligible|capability-unavailable|adopted|already-adopted|head-conflict|protected-mismatch|namespace-mismatch|id-conflict|reconciliation-required"
}
```

Use this deterministic failure schedule:

| Condition | Required verdict |
| --- | --- |
| Valid pair, but no authorized atomic store | `pair=valid`, `commit=not-attempted`, `adoption=capability-unavailable` |
| Missing basis head-token binding | `lineage=unbound`, `commit=not-attempted`, `adoption=not-eligible` |
| Wrong retained predecessor, generation, or ABA token | `lineage=mismatch`, `commit=not-attempted`, `adoption=not-eligible` |
| Store or chain differs | `lineage=namespace-mismatch`, `commit=not-attempted`, `adoption=namespace-mismatch` |
| Protected goal or authority differs | `protection=mismatch`, `commit=not-attempted`, `adoption=protected-mismatch` |
| Compare-and-swap observes another full head token | `commit=conflict`, `adoption=head-conflict` |
| Store confirms commit but readback is unavailable | `commit=committed`, `readback=unavailable`, `adoption=reconciliation-required` |
| Native commit outcome and readback are unavailable | `commit=outcome-unknown`, `readback=unavailable`, `adoption=reconciliation-required` |
| Store confirms commit but readback names a different token | `commit=committed`, `readback=different`, `adoption=reconciliation-required` |
| Exact operation replay and matching readback | `commit=committed`, `readback=matched`, `adoption=already-adopted` |
| Same operation ID with different intent | `commit=id-conflict`, `adoption=id-conflict` |
| Atomic commit and exact readback both succeed | `commit=committed`, `readback=matched`, `adoption=adopted` |

The pre-CAS intent binds the immutable operation ID, token schema and digest
version, store and chain fingerprints, expected full token, candidate head
core, producer receipt and basis-token fingerprints, protected-contract
fingerprint, and the pair, lineage, and protection verdicts. The candidate head
core contains everything except the intent fingerprint; fingerprint the intent,
then construct the full candidate token from that core plus the intent
fingerprint. This order is non-circular.

The terminal adoption receipt binds the intent fingerprint, exact candidate
token, native commit result, commit, readback, and adoption verdicts, and final
readback. It is created after commit and is never an input to the candidate
token. Exact replay of the same operation ID and intent is idempotent. The same
ID with a different intent is an atomic conflict. A new chain starts only from
a separately authorized baseline receipt and cannot claim earlier continuity.
Keep raw snapshots, goal text, paths, and private evidence out of public
receipts; expose only stable opaque refs and closed verdicts.

A successful producer exit, `validated_step`, operator prose, or a stale
adoption receipt never substitutes for the canonical compare-and-swap and
readback.

## State Classification

| State | Evidence | Observer action |
| --- | --- | --- |
| `progressing` | Active turn or new tool/activity marker | Update changed claims, then wait once |
| `idle` | No active turn, no attention or failure signal, and the bound terminal condition is unproven | Preserve gates and the single continuation owner; wait at the next wake |
| `attention` | Approval, user-input request, or explicit needs-attention signal | Surface it to the user; do not answer or approve |
| `terminal` | The bound terminal condition itself is verified | Verify bound completion claims once, then retire the stored heartbeat |
| `failed` | System error or terminal failure | Record exact failure class and smallest recovery owner |
| `ambiguous` | Missing host, unloaded state, or conflicting snapshot | Perform one bounded read-only disambiguation |

Classify `attention` and `failed` before `idle`. A completed latest turn or no
active turn is `idle` only when no approval, input, explicit attention, system
error, or terminal failure signal exists.

An unchanged timeout is not a transition and preserves the prior state. It does
not itself imply `idle`, `terminal`, healthy, progressing, or blocked. A
completed latest turn alone is `idle`, not `terminal`, and does not retire a
long-lived watch.

## Recurring Wake Contract

Use this only when the user requested ongoing supervision:

1. Resolve the existing native continuation owner. An active goal continuation
   takes precedence: record `goal-runtime`, keep `heartbeat` null, and create no
   heartbeat unless a verified handoff retires or defers the goal continuation.
2. Only when no goal continuation owns the watch, inspect existing wakeups.
   Resolve the stored heartbeat ID first. If it is absent or unresolved, match
   the exact `supervisor_host_id`, `supervisor_task_id`, and `logical_key`;
   never use the mutable definition fingerprint as identity.
3. With zero matches, persist `create-pending`, the logical key, and desired
   definition fingerprint before creating one heartbeat. On confirmed success,
   store its exact ID and mark it `active`. On an ambiguous result, persist
   `result-unknown` and perform one read-only reinspection by returned ID when
   present, otherwise by owner plus logical key. Never blind-retry create.
4. With one match, reuse that exact ID. Persist `update-pending` before an
   update; an ambiguous update becomes `result-unknown` and permits one
   read-only reinspection, never a blind update retry or create. With multiple
   or ambiguous matches, create nothing and reconcile exact IDs before
   mutation.
5. Bind the heartbeat only to the supervisor task. Its definition loads this
   checkpoint; it does not embed private target or evidence content.
6. On each goal continuation or heartbeat wake, validate the stored owner and
   any definition fingerprint, load the saved opaque cursors, perform exactly
   one bounded wait, and persist every returned cursor plus the checkpoint
   before reporting or yielding.
7. If the wait is unchanged, update no claims, emit no report, and yield. This
   proves only that the supervisor wake ran; it proves nothing about target
   health or progress.

Timeout, unchanged state, continued work, and `idle` are not by themselves goal
blockers. Goal `blocked` is a status report, not a pause or polling control.
Use it only for a genuine external impasse after every strict precondition of
the active goal runtime is satisfied. If neither goal continuation nor native
recurring wakeups are available, record a capability gate instead of emulating
recurrence with cron, an OS scheduler, a watcher subagent, or repeated polling.

On user stop, verified terminal state for every target, or a genuine blocker
that prevents further observation, retire only the stored heartbeat ID when
`continuation_owner.kind` is `heartbeat`. Change goal-runtime state only
through its own goal contract.

## Intervention Decision

Record this before a write:

```json
{
  "schema": "codex.thread_intervention.v1",
  "target_thread_id": "opaque-thread-id",
  "intervention_id": "immutable-opaque-id",
  "payload_fingerprint": "stable-fingerprint",
  "authorized_actions": [
    "send-skill-handoff"
  ],
  "authorization_conditions": [
    "target is active",
    "handoff addresses the current next step"
  ],
  "authorization_expires_at": null,
  "selected_action": "send-skill-handoff",
  "evaluated_limit": {
    "action": "send-skill-handoff",
    "remaining_before": 1,
    "remaining_after": 0
  },
  "observed_gap": "generic evidence-backed gap",
  "payload_ref": "inline typed payload or private evidence ref",
  "attention_cost": "low|medium|high",
  "decision": "send|defer|reject",
  "reason": "short bounded rationale"
}
```

Reject the intervention when it duplicates existing guidance, arrives after the
relevant step, would interrupt a terminal proof, or needs authority the user did
not grant.

The only defined write actions are:

- `send-skill-handoff`: transfer an existing skill without expanding scope or
  mutation authority.
- `send-evidence-delta`: amend, supersede, or retract source-backed claim atoms
  without turning the correction into a task directive.

Any other target-thread message needs a future contract revision and explicit
authorization. Do not reinterpret a broad `observe` permission as a write
allowlist.

### Skill Handoff Payload

New handoffs use `codex.thread_skill_handoff.v2`. Bind canonical source content,
sender-observed catalog/cache/loaded-runtime identity, requested consumption,
and constant no-activation authority. Before consumption, the receiver
atomically reserves the handoff ID and payload fingerprint; it then returns one
validated `applied`, `conflict`, or `stale` acknowledgement. A direct source
read applies guidance without proving installation or runtime activation.

Read `$PLUGIN_ROOT/references/thread-skill-handoff-contract.md` for the complete
envelopes, canonical digest algorithms, receiver reservation, closed terminal
matrix, compaction recovery, and deterministic validator. Keep the
content-addressed payload ref pending until that validator accepts the
acknowledgement.

### Evidence Delta Payload

Use this only when `send-evidence-delta` is separately authorized:

```json
{
  "schema": "codex.thread_evidence_delta.v1",
  "revision_id": "opaque-observer-revision",
  "payload_fingerprint": "stable-fingerprint",
  "base_revision_id": "last-applied-revision-or-null",
  "protected_contract_fingerprint": "matching-goal-policy-boundary-fingerprint",
  "relation": "amends|supersedes|retracts",
  "supersedes_revision_ids": [],
  "claims": [
    {
      "claim_id": "stable-public-safe-key",
      "operation": "add|replace|withdraw",
      "status": "verified|hypothesis|withdrawn",
      "value": "compact current claim or null",
      "authority": "user|primary-source|verified-tool-output|observer-inference",
      "evidence_refs": [
        "target-local-private-recovery-ref"
      ]
    }
  ],
  "scope_effect": "none",
  "authority_effect": "none",
  "ack_required": true
}
```

`base_revision_id` must equal the receiver's last applied revision, or be
`null` for the first delta. Validate the relation and operations atomically:

| Relation | Allowed operations | Additional rule |
| --- | --- | --- |
| `amends` | `add`, `replace` | `supersedes_revision_ids` is empty |
| `retracts` | `withdraw` | `supersedes_revision_ids` is empty |
| `supersedes` | `add`, `replace`, `withdraw` | Name earlier revisions and include every claim ID they changed |

Supersession replaces only the named revisions' observer evidence-ledger
effects. Unrelated claim atoms and the protected contract remain unchanged.
Reject the whole delta when any relation, operation, claim set, protected
fingerprint, constant `scope_effect`, or constant `authority_effect` is
invalid. Prefer `amends` for ordinary corrections.

Use stable claim IDs so a receiver can reconcile deltas without matching prose.
Do not promote a hypothesis to `verified` without a source ref and authority.
Do not put raw history, credentials, private URLs, or unrelated context into
the envelope. Claim values and evidence refs must fit the receiving target's
recorded private-data boundary. Use target-local opaque refs; cross-target
provenance requires separate authorization for both source and destination.

The receiver acknowledgement is:

```json
{
  "schema": "codex.thread_evidence_ack.v1",
  "revision_id": "matching-revision",
  "payload_fingerprint": "matching-fingerprint",
  "status": "applied|conflict|stale",
  "current_revision_id": "receiver-current-revision-or-null",
  "applied_claim_ids": [],
  "conflict_claim_ids": [],
  "evidence_refs": []
}
```

Acknowledgements are atomic:

- `applied`: `applied_claim_ids` exactly equals the delta's claim-ID set,
  `conflict_claim_ids` is empty, and `current_revision_id` equals the delta
  revision.
- `conflict`: `applied_claim_ids` is empty, at least one conflicting claim is
  named, nothing from the delta applies, and `current_revision_id` remains the
  receiver's prior revision.
- `stale`: both claim-ID lists are empty, nothing applies, and
  `current_revision_id` returns the receiver's actual current base.

Ordinary activity, an unrelated reply, a partial acknowledgement, or continued
file changes do not acknowledge a delta.

On `applied`, advance `current_contract_revision`, append its compact ref, and
clear the pending intervention. On `conflict`, preserve the prior base, retain
the conflicting atoms as an open gate, append the revision ref, and clear the
pending intervention. On `stale`, preserve the receiver-returned current base,
append the revision ref, clear the pending intervention, and construct a new
revision only if authority and a positive action limit still remain. An invalid
or incomplete acknowledgement stays pending.

Fingerprint the target ID, selected action, revision and base IDs, relation,
protected-contract fingerprint, stable claim IDs and values, and evidence refs.
Do not hash or copy raw private evidence content into reusable source. Treat
the revision ID as the idempotency key: the same ID and fingerprint replays the
stored acknowledgement without reapplying; the same ID with a different
fingerprint is an atomic `conflict`.

Persist the consumed limit, pending record, immutable ID, and fingerprint
before calling the message tool. After a confirmed send, mark it delivered; an
evidence delta remains pending until acknowledgement. If the tool proves
non-delivery, record that proof before clearing the pending state. An ambiguous
result remains `delivery-unknown`, consumes its limit, and permits only one
bounded read for the immutable ID, not a blind resend.

When the message surface cannot enforce structured output, include the exact
envelope and request the closed acknowledgement shape. Inspect the receiver's
response semantically; do not recover status with regex or substring parsing.
Leave the revision pending when the acknowledgement is absent or ambiguous.

## Capability Evidence

Use one row per candidate:

```json
{
  "observation_class": "wait-friction|context-loss|handoff-drift|proof-gap|routing-gap|safety-gap",
  "occurrences": 2,
  "severity": "low|medium|high",
  "confidence": "low|medium|high",
  "generic_trigger": "public-safe task context",
  "mechanism": "concrete behavior or validator",
  "candidate_surface": "metadata|skill|reference|script|validator|plugin|guidance",
  "existing_overlap": [],
  "validation_scenario": "behavior that would falsify the improvement",
  "decision": "adopt|adapt|defer|reject"
}
```

Counts alone do not prove waste. Inspect the surrounding state before assigning
cause. Prefer changed behavior or proof gates over better-sounding prose.

## Public-Safe Distillation

Keep two layers:

- Ephemeral operational state may retain exact opaque IDs and immutable
  revisions needed to continue the watch.
- Tracked plugin source and public reports retain only generic triggers,
  mechanisms, safety boundaries, synthetic examples, and validation results.

Replace private task names with a role such as `target task`, private repository
names with `target repository`, private URLs with the evidence class, and local
paths with portable variables or synthetic paths. Remove personal names,
credentials, organization-specific identifiers, and raw message excerpts
entirely.

Do not weaken the mechanism while sanitizing it. Preserve facts such as
"immutable revision", "approval required", "producer-owned receipt", or
"private dependency unavailable" when they control the workflow.

## Resume Gate

After compaction or a later wake:

1. Load the checkpoint, not the full transcript.
2. Confirm the goal, terminal condition, reporting cadence, and private-data
   boundary.
3. Confirm target, host, and per-target authorization fields, including expiry.
4. Confirm the single continuation owner. When it is a heartbeat, confirm its
   owner task and host, cadence, definition fingerprint, and stored ID; when it
   is the goal runtime, confirm `heartbeat` remains null.
5. Pass the saved cursor unchanged to the next wait.
6. Replace every returned target's cursor before reporting any transition.
7. Revalidate only current status and drift-prone external claims.
8. Preserve each target's last intervention and last-reported transition
   fingerprints.
9. Preserve the protected-contract fingerprint and every pending intervention's
   exact payload recovery ref, digest or revision identity, requested mode,
   delivery state, and acknowledgement state. Load and validate the immutable
   payload before accepting an acknowledgement; never infer it from activity or
   reconstruct it from prose.
10. Resolve and validate `protected_policy_application_state`. When
    `active_count <= 8`, require the inline list to be the complete active set
    and `active_index_ref` to be null. When it is larger, require an empty inline
    list and load the complete typed active index. Load the full retired-index
    predecessor chain. Reject duplicate or reused application, revision,
    recovery, and operation-namespace-plus-operation-ID identities across both
    sets. Preserve every active entry separately; append a later revision
    without replacing an earlier entry. Resolve every active and retired
    recovery chain to its root. Require each root either to be an ordinary fresh
    v2 `revision-captured` record or to carry the exact v1 migration attestation
    for that later-state root. Then require every updated recovery head to
    preserve that exact prefix and reach its prior recovery ref. Enforce the
    closed monotonic application-state graph. An unknown outcome permits only
    exact owning-system reconciliation, never a new write. Pass the independently
    resolved current checkpoint recovery-head ref into application-receipt
    evaluation; never infer currentness from the receipt itself.
11. Remove an active entry only when a new retired-index record has the prior
    retired ref as predecessor and every new tombstone names an application
    active in the immediately preceding checkpoint. Resolve the terminal
    receipt's producer authority, exact v2 application receipt, v2 recovery
    record, and any required unknown-state reconciliation; evaluate the
    application receipt independently and require all evidence to bind that
    exact application, revision, and recovery identity.
12. After emitting a transition, advance that target's report fingerprint.
13. Resume the single recorded next action.

If the checkpoint is missing the supervisor task or host, a target, cursor,
authorization, the `open_gates` field, a previously evidenced applicable gate,
continuation owner, heartbeat logical key, heartbeat lifecycle state, or a
previously active protected-policy application recovery record, state, active
index, retired-index chain, or collection entry,
perform one bounded read to repair that field. A present empty `open_gates`
list is valid after a complete zero-eligible inventory and must not be
repopulated from prose. Do not replay the entire supervision history. While
heartbeat identity or lifecycle is ambiguous, do not create, update, or retire
a wakeup.
