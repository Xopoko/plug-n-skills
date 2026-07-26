# Thread Supervision Contract

Use this reference for multi-thread watches, compaction-safe continuation,
authorized interventions, and capability extraction.

## Checkpoint

Keep the checkpoint compact and machine-readable when possible:

```json
{
  "schema": "codex.thread_supervision.v1",
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
candidate references. Externalize superseded history to private evidence
artifacts rather than growing the checkpoint.

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
action, immutable intervention ID, payload fingerprint, revision ID when
applicable, delivery state, and acknowledgement state. Keep only one pending
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

```json
{
  "schema": "codex.thread_skill_handoff.v1",
  "handoff_id": "immutable-opaque-id",
  "payload_fingerprint": "stable-fingerprint",
  "skill": "exact-skill-name",
  "why_now": "current next step that benefits",
  "mechanism": "smallest relevant guardrail",
  "already_present": false,
  "scope_effect": "none",
  "authority_effect": "none"
}
```

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
9. Preserve the protected-contract fingerprint and any pending intervention
   delivery or acknowledgement state; never infer acknowledgement from target
   activity.
10. After emitting a transition, advance that target's report fingerprint.
11. Resume the single recorded next action.

If the checkpoint is missing the supervisor task or host, a target, cursor,
authorization, the `open_gates` field, a previously evidenced applicable gate,
continuation owner, heartbeat logical key, or heartbeat lifecycle state,
perform one bounded read to repair that field. A present empty `open_gates`
list is valid after a complete zero-eligible inventory and must not be
repopulated from prose. Do not replay the entire supervision history. While
heartbeat identity or lifecycle is ambiguous, do not create, update, or retire
a wakeup.
