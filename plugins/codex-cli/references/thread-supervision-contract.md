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
          "observe"
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
  "authorized_actions": [
    "send-skill-handoff"
  ],
  "authorization_conditions": [
    "target is active",
    "handoff addresses the current next step"
  ],
  "authorization_expires_at": null,
  "evaluated_limit": {
    "action": "send-skill-handoff",
    "remaining_before": 1,
    "remaining_after": 0
  },
  "observed_gap": "generic evidence-backed gap",
  "skill": "exact-skill-name",
  "why_now": "current next step that benefits",
  "already_present": false,
  "attention_cost": "low|medium|high",
  "decision": "send|defer|reject",
  "reason": "short bounded rationale"
}
```

Reject the intervention when it duplicates existing guidance, arrives after the
relevant step, would interrupt a terminal proof, or needs authority the user did
not grant.

## Capability Evidence

Use one row per candidate:

```json
{
  "observation_class": "wait-friction|context-loss|proof-gap|routing-gap|safety-gap",
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
8. After emitting a transition, advance that target's report fingerprint.
9. Resume the single recorded next action.

If the checkpoint is missing a target, cursor, authorization, or open gate,
perform one bounded read to repair that field. Do not replay the entire
supervision history.
