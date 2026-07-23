---
name: async-state-consistency
description: >-
  Use when designing, reviewing, debugging, or testing asynchronous state
  holders, caches, observers, subscriber notifications, memoized or coalesced
  loads, replay, or one-shot reads where invalidation, late subscribers, stale
  in-flight completion, read or publish races, out-of-order completion, or
  keyed/global ownership can expose stale state. Not for UI-only loading
  presentation, deployment topology, distributed consensus, or unrelated test
  flakiness.
---

# Async State Consistency

Use for language-neutral component state whose asynchronous work can race with
clear, invalidation, expiry, refresh, another publication, or a direct caller.

## Contract First

Before proposing a repair:

1. Name the authoritative state holder and every path that can return, publish,
   replay, or repopulate it: observers, late subscribers, warm cache, one-shot
   calls, memoization, request coalescing, persistence, and derived projections.
2. Model lifecycle states explicitly. Keep initial or unknown distinct from
   `Available(empty)`, and define invalidated, error, stale, and retry outcomes
   only where the contract needs them.
3. Name each ownership domain: global invalidation generation, keyed/domain
   generation, ordinary publication revision, operation identity, and any
   dependency revisions.
4. Choose and name the supersession policy for competing work:
   latest-start-wins or latest-success-wins. Define what happens to older work
   when a newer attempt fails or is cancelled.
5. Define the direct caller outcome when its work is rejected: authoritative
   reread, declared stale/retry/cancellation, or another explicit result.
6. Separate read-time freshness from active expiry. Elapsed time alone is not
   an observer emission trigger; name the timer, refresh, lifecycle, scheduler,
   or storage signal that re-evaluates state.

## Preserve State Meaning

- Preserve lifecycle discriminators through every projection. Do not map
  initial or invalidated to a valid domain value.
- Match projection modality to its inputs. A synchronous projection cannot
  depend on asynchronously unavailable state; pre-resolve it at an owned
  boundary or expose an asynchronous contract.
- Make late-subscriber replay semantics explicit. A cleared value cannot remain
  current merely because a replay container retained it.

## Map Authority

Build a compact table with one row per read, write, replay, and notification
path:

```text
path | candidate value | ownership evidence | invalidation domain |
linearization point | caller/subscriber outcome
```

Include every cache, memo, coalescer, retained observer state, persistence
layer, and projection able to bypass the main repository or state holder.

## Order And Linearize

- Keep invalidation generation separate from ordinary publication sequence.
  A clear revokes earlier work; a newer same-domain publication supersedes an
  older completion without implying `Invalidated`. Advance publication
  ownership at reservation for latest-start-wins, or at successful commit for
  latest-success-wins; do not mix the policies implicitly.
- Capture ownership before asynchronous work, then validate it at the final
  state/cache commit. Validation and commit must be one atomic or serialized
  transition against same-domain invalidation and publishers.
- Treat replay reads symmetrically. Read the candidate value and its authority
  from one atomic/serialized snapshot, or use a stamped snapshot and retry when
  the revision changes. Reading a value and validating it later is a read-side
  check-to-use race.
- Always validate the global or owning-domain revision. An empty dependency
  list must not pass vacuously unless the value is explicitly independent of
  invalidation.
- Atomically commit only owned data plus an owner-local, non-delivering
  emission revision or intent. The serialized owner must not run subscriber
  callbacks, user-supplied predicates or factories, or delivery that can
  synchronously resume or reenter, block, suspend, or apply backpressure. Run
  those outside the owner and revalidate authority before committing results
  computed by user code. Across durable boundaries, use an equivalent ordered,
  idempotent notification record.
- Cancellation is cooperative, not authority. Work that ignores cancellation
  still needs the same commit and caller-result guards.
- When invalidation wins, atomically detach revoked coalesced work from the
  current join and wait path. A later caller must neither join nor wait behind
  that work; it starts or joins current-generation work independently even
  when revoked work ignores cancellation.
- A rejected completion must not return its candidate as current to a one-shot
  caller. Reread authority or return the declared stale/retry/cancellation
  outcome.
- Ownership rejection alone must not emit or persist `Error` or `Invalidated`.

Do not hold a lock across remote or slow work merely to gain consistency.
Usually only token capture, snapshot acceptance, and the final commit need a
linearization point.

## Deterministic Proof

Use controllable gates, barriers, latches, virtual time, or a controlled
scheduler. Sleeps and scheduler luck are not race proof.

At minimum, cover:

- late collection after invalidation;
- work started before invalidation and completed afterward;
- same-domain A then B with B completing first;
- A held at the final pre-commit boundary while B wins, and while clear wins;
- both linearization winners: A commits before clear, and clear commits before A;
- a one-shot A rejected after B, including A's direct caller result;
- a replay read held between candidate capture and authority validation while
  clear wins, including the empty-dependency case;
- revoked coalesced A held blocked while post-invalidation B starts and
  finishes before A is released, including per-caller versus shared-work
  cancellation;
- A starts, B starts, B fails or is cancelled, then A completes under both the
  declared latest-start-wins and latest-success-wins policies;
- keyed invalidation that leaves unrelated-key work valid, plus global clear;
- TTL next-read behavior separately from active subscriber emissions;
- blocked delivery followed by reentrant subscriber code, and user-supplied
  predicate or factory hooks that perform nested mutation before the outer
  operation revalidates;
- failure between mutation and notification when those are separate surfaces.

Use `references/async-state-consistency.md` for state, authority, and race
matrices.

## Output

Report the state contract, authority map, failing interleaving, chosen
linearization point, minimal repair, deterministic proof schedules, and any
path whose authority remains unverified.

## Boundaries

- UI rendering, loading visuals, and interaction state belong to UI skills.
- Timer, lifecycle, deployment, and storage-signal discovery belongs to
  `architecture-runtime-topology`.
- Turn an accepted invariant into CI policy with
  `architecture-fitness-functions`.
- Use platform skills for framework APIs, source placement, and test harnesses.
- Distributed consensus, replicated databases, and generic async performance
  need their own specialist workflow.
