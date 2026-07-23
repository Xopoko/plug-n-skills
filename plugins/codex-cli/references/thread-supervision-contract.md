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
      "state": "progressing|attention|terminal|failed|ambiguous",
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

Keep only current claims, gates, and evidence needed for the next decision.
Limit each inline list to eight entries and keep at most five active capability
candidate references. Externalize superseded history to private evidence
artifacts rather than growing the checkpoint.

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

## State Classification

| State | Evidence | Observer action |
| --- | --- | --- |
| `progressing` | Active turn or new tool/activity marker | Update changed claims, then wait once |
| `attention` | Approval, user-input request, or explicit needs-attention signal | Surface it to the user; do not answer or approve |
| `terminal` | Completed latest turn and final task output | Verify bound completion claims once |
| `failed` | System error or terminal failure | Record exact failure class and smallest recovery owner |
| `ambiguous` | Missing host, unloaded state, or conflicting snapshot | Perform one bounded read-only disambiguation |

An unchanged timeout is not a transition.

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
4. Pass the saved cursor unchanged to the next wait.
5. Replace every returned target's cursor before reporting any transition.
6. Revalidate only current status and drift-prone external claims.
7. Preserve each target's last intervention and last-reported transition
   fingerprints.
8. Preserve the protected-contract fingerprint and any pending intervention
   delivery or acknowledgement state; never infer acknowledgement from target
   activity.
9. After emitting a transition, advance that target's report fingerprint.
10. Resume the single recorded next action.

If the checkpoint is missing a target, cursor, authorization, or open gate,
perform one bounded read to repair that field. Do not replay the entire
supervision history.
