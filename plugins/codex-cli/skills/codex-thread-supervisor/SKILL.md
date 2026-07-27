---
name: codex-thread-supervisor
description: "Use for live Codex task or thread supervision by ID: cursor transitions, attention gates, bounded claims, checkpoint adoption, authorized skill or evidence handoffs, and privacy-safe capability mining. Not for rollout forensics, current-turn subagents, or external jobs."
---

# Codex Thread Supervisor

Bundled references use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell), set to
the host plugin root or this skill folder's `../..`.

Supervise live Codex tasks without taking ownership of their work. Observation
is read-only by default. A message to a target thread is allowed only when the
user's intervention policy explicitly permits it.

Use native `list_threads`, `read_thread`, `wait_threads`, and
`send_message_to_thread`; discover deferred tools with tool search. Without
them, live supervision is unavailable. `codex-log-reader` is only for
user-accepted retrospectives and has no live cursor or attention semantics.

Read `$PLUGIN_ROOT/references/thread-supervision-contract.md` when the run
crosses a compaction, covers multiple threads, permits interventions, or will
produce reusable capability changes.
When selecting or reconciling `send-skill-handoff`, also read
`$PLUGIN_ROOT/references/thread-skill-handoff-contract.md`.

## Bind The Watch

Record:

- exact supervisor task ID and host ID;
- exact thread ID and host ID for every target;
- the user's goal, terminal condition, and reporting cadence;
- a per-target authorization allowlist, conditions, limits, and expiry;
- prohibited mutations and private-data boundaries;
- the cursor returned for each target.

If host identity is unknown, use an unfiltered recent-thread list first and
match the exact ID. Do not resume, open, fork, or move a thread merely to
observe it.

## Establish A Bounded Baseline

1. Prefer `wait_threads` with `timeoutMs: 0` for a compact current snapshot.
2. Separate observed state from inferred progress.
3. Record the active turn, latest transition, open gates, and immutable proof
   identities that matter to the target's own completion claim.
4. Bind each open gate to a current live subject or explicit policy requirement,
   its eligibility evidence, and its owner. A possible action or available
   authority is not a gate. When a complete inventory finds zero eligible
   targets for a conditional action, record it as `not-applicable` outside
   `open_gates`; never create a discussion, note, approval, or other external
   write solely to satisfy a checkpoint.
5. If the task is already terminal, report that once and do not intervene.

Use `read_thread` only to disambiguate one named missing fact. Increase history
depth or include a bounded tool output only when that fact requires it. Route
persisted-history questions to `codex-log-reader` instead of repeatedly
expanding a live snapshot.

## Adopt Typed Checkpoints

Validating a supplied `previous -> current` pair is not canonical adoption. A
receipt proves that pair, not the retained head or store advance.
This skill supplies guardrails, not a canonical store or adopter. Use with
explicit mutation authority and an existing store interface
with atomic full-token CAS. Never emulate CAS with read plus ordinary write.
Without it, keep `pair=valid`, `adoption=capability-unavailable`, and the
candidate noncanonical.

Adoption checks:

1. Independently load the full retained head token, store, chain, and origin
   receipt.
2. Match the producer receipt's basis head-token fingerprint and schema version
   to that token, plus its `from`, candidate `to`, and protected fingerprint.
   A pair-only receipt is ineligible.
3. Reject store or chain mismatch. Protected drift needs separate typed
   new-chain or rebind authority.
4. Create the immutable pre-CAS intent; CAS the full token, including its
   generation and creating-intent fingerprint. This prevents fork and ABA adoption.
5. Read the token and native result before the terminal receipt. Unknown commit
   or readback is `reconciliation-required`, not `not-adopted`; reconcile the
   operation ID before retrying.

Keep pair, lineage, protection, commit, readback, and adoption as independent
closed verdicts. Separate producer and adoption receipts. Details are in
`$PLUGIN_ROOT/references/thread-supervision-contract.md`.

## Rebind Protected Policy Before External Mutations

When direct user input changes a protected goal, authority, task constraint, or
required external-object field, capture a new protected policy revision. Do not
encode that control-plane change as an evidence delta.

Before accepting an affected target's external mutation:

1. Require receiver-owned adoption of the exact policy revision and protected
   fingerprint, bound to the exact receiver identity, with an acknowledgement
   ref and receiver cutoff. If no authorized typed rebind exists, keep the
   mutation blocked as
   `capability-unavailable`; do not send an unlisted message.
2. Bind the authorized operation, destination, subject, cutoff, and every
   mandatory field to that revision. Persist a receiver-bound immutable
   pre-write intent only through an existing authorized intent store, then bind
   the mutation receipt to it. Require the fixed store schema, exact store,
   existing authorization, preallocated intent-store and owning-system mutation
   operation IDs, and immutability evidence. Retain both IDs in the immutable
   intent before the external write. If that store is unavailable, keep the
   external mutation blocked; never emulate it with an ordinary local write.
3. Read back the exact external object and one keyed, evidence-bound result for
   every mandatory field after the write. Use only the closed HMAC fingerprint
   envelope; raw values and bare digests are malformed. Preallocate the
   owning-system operation ID, bind it to the destination, subject, and intent,
   and bind the readback to both that operation ID and the exact mutation
   receipt with owning-system ordering evidence. Missing, extra, or duplicate
   field results fail closed. Object existence, a related field, target
   activity, or intent is not policy adoption.
4. Keep missing or mismatched fields as `policy-drift`. Any unknown mutation
   or intent outcome, or incomplete/unavailable/ambiguous readback, is
   `reconciliation-required` after receipt shape and durable operation IDs
   validate, regardless of another semantic policy defect. Reconcile by the
   preallocated operation ID; require the mutation operation ID and both
   retained intent identities to exactly match the immutable recovery record,
   and require an unknown intent write to match its recovered authorized store
   namespace while mutation remains exactly `not-attempted` with no mutation or
   readback observations; a simultaneous unknown mutation is invalid. Before
   reconciling unavailable readback,
   independently resolve the canonical owning-system mutation receipt.
   Presence alone is insufficient. Do not infer success from a retained
   receipt field.

An unrelated pending evidence or skill intervention neither blocks recording
the direct user revision nor proves receiver adoption. It still retains its
ordinary delivery and acknowledgement rules. See the protected policy
application receipt and failure schedule in the supervision contract.
Before yielding or compaction, persist the separate immutable application
recovery ref plus both operation IDs; never hide them in the evidence-delta
revision or ordinary pending-intervention slot.

## Watch Transitions

- Wait on up to eight targets in one `wait_threads` call. For more targets, use
  stable batches of at most eight on successive turns; do not build a rapid
  batch-polling loop.
- Pass each batch target's opaque cursor unchanged as `afterCursor`; never
  derive or edit it.
- Use one bounded wait, normally at least 60 seconds. Do not nest short polling
  loops or alternate repeated `read_thread` and `wait_threads` calls.
- Before reporting, atomically replace every returned target's saved cursor
  with the exact cursor from that wait, including timeout and non-waking
  targets.
- Commentary does not wake the wait. On an unchanged timeout, update no claims
  and emit no duplicate status.
- Re-read a thread only after a material transition or when the compact wait
  result cannot classify the state.
- Treat completion, system failure, approval, and user-input requests as
  distinct states. Leave approval and requested input for the user.
- If no independent work remains, yield after the bounded wait rather than
  inventing work or polling again.

Report transitions, not elapsed time. A useful update states what changed, the
evidence class, the remaining gate, and whether observer action is allowed.

## Bound Aggregate Claims

When a target claims that every member of a set was reviewed, audited, or
validated, separate universe breadth from per-item evidence depth. Bind the
item set and cutoff, name the required dimensions, and reject counts or
percentages as substitutes for exact item-by-dimension coverage.

When `capability-workbench:capability-auditor` is already available, route the
claim through its evidence coverage gate. Do not install or activate another
plugin merely to perform the check. If the gate is unavailable, its ledger is
invalid, or any required pair is missing, failing, or blocked, report the claim
as bounded or partial. Never promote a supplied universe to real-world
completeness without independent enumeration evidence.

## Continue An Ongoing Watch

When the user requests a nonterminal ongoing watch, keep exactly one native
continuation owner for the supervisor task:

- Prefer an already active native goal continuation. Record it as the owner and
  do not add a heartbeat while it remains active; switching owners requires a
  verified handoff that retires or defers the prior continuation.
- If no goal continuation owns the watch, inspect existing native wakeups
  before any create. Resolve the stored heartbeat ID first, then fall back to
  the supervisor task and host plus stable logical key. The definition
  fingerprint is mutable configuration, not heartbeat identity.
- Before creating, persist `create-pending`, the stable logical key, and the
  desired definition fingerprint. If the result is ambiguous, persist
  `result-unknown`, perform one read-only reinspection, and never blind retry.
  With multiple or ambiguous matches, create nothing until exact IDs are
  reconciled.
- Before updating the one exact match, persist `update-pending`. An ambiguous
  update becomes `result-unknown` and permits one read-only reinspection, not a
  replacement create or blind update retry.
- Attach the heartbeat to the supervisor task, never a target task or an OS
  scheduler. Store its opaque ID, owner task and host, cadence, and definition
  fingerprint in the checkpoint.
- Each goal continuation or heartbeat wake loads the checkpoint, passes saved
  cursors unchanged, performs one bounded wait, persists every returned cursor
  and the checkpoint, then reports a material transition or yields silently.

Continuation cadence controls observer re-entry; reporting remains
transition-only. An unchanged wait confirms only that the supervisor heartbeat
ran, not target health or progress, and must not mark the supervision goal
blocked. A completed latest turn is `idle`, not `terminal`, until the bound
terminal condition is proven.

Never use goal `blocked` as a pause, yield, or no-change outcome. It requires a
genuine external impasse and every strict precondition of the active goal
runtime. If native recurring wakeups are unavailable, record that capability
gate; do not emulate them with cron or another monitoring service.

## Gate Interventions

Send a target-thread message only when every condition holds:

1. The per-target allowlist includes the selected action, every condition is
   met, the authorization is unexpired, and its remaining limit is positive.
2. The target is active and not already waiting for the user.
3. A concrete capability or evidence gap affects the target's current next
   step.
4. The action has its required source: a relevant existing skill whose full
   instructions were read, or verified evidence with stable recovery refs.
5. The target is not already applying the same skill or reconciling the same
   evidence revision.
6. The benefit exceeds the interruption and context cost.

Use only typed actions in the supervision contract. Unlisted target messages
remain prohibited.

For `send-skill-handoff`, use the versioned handoff payload and
acknowledgement. Bind immutable source, canonical content, and receiver
catalog/cache/loaded-runtime identity. Separate `runtime-loaded` from
`direct-source-read`: direct reading applies guidance without proving installed
or runtime-active capability. Never install or refresh; scope and authority
stay unchanged.

For `send-evidence-delta`, use the versioned envelope and acknowledgement
states in the supervision contract. For `amends` or `retracts`, send only
changed or withdrawn claim atoms plus stable evidence refs. A `supersedes`
delta must include the complete affected claim set required by the contract.
The delta cannot expand task scope or mutation authority. Target activity is
not acknowledgement: keep the revision pending until the receiver explicitly
marks it `applied`, `conflict`, or `stale`.

Do not send generic coaching, status requests, repeated context, model changes,
task directives, or implementation instructions disguised as either action.
Before sending, atomically reserve the intervention in the checkpoint: persist
its immutable ID and payload fingerprint, decrement that action's remaining
limit, and mark it pending. Then send it once. An ambiguous send result stays
pending and must be disambiguated by one bounded read; never blind-resend it.
A later intervention requires a new relevant transition, no unresolved pending
intervention, and positive unexpired authorization. Renew authority only after
the original allowance is exhausted or expired.

## Mine Durable Capabilities

Treat thread content as private evidence, not reusable prose.

1. Capture an observation and its confidence separately from the inferred
   workflow problem.
2. Prefer a repeated pattern across runs. A one-off may qualify only when it
   exposes a high-severity safety or correctness gap.
3. Reduce the evidence to a generic trigger, mechanism, safety boundary, and
   validation scenario.
4. Audit existing skills and plugin boundaries before adding a new capability.
5. Choose the smallest durable surface: metadata, skill rule, reference,
   deterministic script, validator, plugin boundary, or agent guidance.
6. Treat supervision authority as permission to produce a public-safe
   candidate report only.
7. Edit or commit capability source only when the user separately authorized
   that repository change. Installation or cache refresh requires its own
   explicit scope.

Never copy personal names, private repository or task names, private URLs,
credentials, organization-specific data, machine paths, or raw transcript
excerpts into tracked capability source. Keep exact operational identities only
in ephemeral supervisor state when they are necessary to continue the live
watch.

## Completion

Close the supervision run only when the user stops it, every target reaches the
bound terminal state, or a genuine external blocker prevents further
observation. Retire only the heartbeat recorded in the checkpoint; do not scan
or remove unrelated wakeups. When the continuation owner is the goal runtime,
change its status only through that runtime's goal contract.
Report target states, verified claims, residual gates, interventions made, and
capability changes produced. Distinguish source commits from installation or
cache visibility.
