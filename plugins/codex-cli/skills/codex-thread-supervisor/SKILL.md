---
name: codex-thread-supervisor
description: Use when watching, monitoring, following, or supervising one or more live Codex tasks or threads by ID, including cursor-based transitions, completion or attention gates, claim checks, compact checkpoints, narrowly authorized skill handoffs or evidence corrections, and privacy-safe capability mining. Not for post-hoc rollout forensics, current-turn subagents, or external job polling.
---

# Codex Thread Supervisor

Bundled references use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell). Set it
to the host's plugin-root variable when defined, otherwise to this skill
folder's `../..`.

Supervise live Codex tasks without taking ownership of their work. Observation
is read-only by default. A message to a target thread is allowed only when the
user's intervention policy explicitly permits it.

Use native Codex task tools such as `list_threads`, `read_thread`,
`wait_threads`, and `send_message_to_thread`. If they are deferred, discover
them with tool search. Without native thread tools, live supervision is
unavailable. Offer `codex-log-reader` only when the user accepts a read-only
retrospective; it cannot provide live cursor or attention semantics.

Read `$PLUGIN_ROOT/references/thread-supervision-contract.md` when the run
crosses a compaction, covers multiple threads, permits interventions, or will
produce reusable capability changes.

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
4. If the task is already terminal, report that once and do not intervene.

Use `read_thread` only to disambiguate one named missing fact. Increase history
depth or include a bounded tool output only when that fact requires it. Route
persisted-history questions to `codex-log-reader` instead of repeatedly
expanding a live snapshot.

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

Use only the typed actions in the supervision contract. An unlisted message
type remains prohibited even if the target would probably benefit.

For `send-skill-handoff`, send one compact message containing only:

- the exact skill name;
- why it applies now;
- the smallest relevant mechanism or guardrail;
- a statement that task scope and mutation authority do not expand.

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
