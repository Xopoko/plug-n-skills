# KMP Data Layer Readiness

## Source Of Truth

Choose one:

- network-only
- cache-first
- offline-first local store
- local-only
- platform-owned source with shared facade

Document freshness, invalidation, conflict resolution, and retry policy.

## Boundaries

- DTOs stay near network.
- Entities stay near persistence.
- Domain models stay platform-neutral.
- Platform SDK callbacks are adapted at the edge.
- Repositories expose project-owned results.

## Library Target Check

Before choosing Ktor, DataStore, Room KMP, SQLDelight, Koin, or another library, verify:

- Maven coordinates.
- Android target.
- iOS device and simulator.
- Desktop/JVM.
- JS/Wasm if configured.
- Native host targets if configured.

Use official docs and Klibs.io as evidence.

## Async State Consistency

Keep one authoritative lifecycle state and preserve it through KMP projections.
Use `StateFlow` or the project's equivalent without treating initial state as
`Available(empty)`.

Declare same-generation shared-work admission separately from publication
order: join/coalesce, queue/serialize, or independent attempts.

| Concern | KMP contract | Deterministic proof |
| --- | --- | --- |
| Invalidation | Global and keyed/domain generations cover observers, cache, one-shot, persistence, memo, and coalescer paths | Start A, invalidate, complete A; attach a late collector |
| Publication order | A declared latest-start or latest-success policy is separate from invalidation | Complete same-key B before A; then fail/cancel B in a separate schedule |
| Final commit | `Mutex`, actor, compare-and-set, or transaction owns validation plus state/cache commit | Hold A at final pre-commit while B wins and while clear wins |
| Replay read | Candidate and authority come from one serialized or stamped snapshot | Clear between candidate capture and validation, including zero dependencies |
| Causal receipt | `started(A)`, `released(A)`, `decision(A)`, and `terminated(A)` receipts are identity-bound; release is only schedule evidence, decision follows the real post-await commit or caller-outcome branch, and termination is separate | Await the bounded decision receipt and assert `released(A) < decision(A)` when late A must traverse the guarded path; a timeout or `finally` marker is not successful decision proof |
| Coordination composition | Every outer and inner mutex, actor, queue, single-flight, or coalescer layer detaches revoked work or permits current-generation progress; later callers neither join nor wait behind it | Run the blocked-A/B schedule layer-locally, then through the public data-layer entry require B to reach authoritative publication before releasing A; an inner-layer unit proof alone is insufficient |
| Shared-work admission | Current owning generation and matching joinable registry membership become authoritative in one transition; cross-generation bypass preserves declared same-generation admission and publication policies | Gate immediately before the whole atomic admission attempt and run invalidation-first and admission-first; for CAS, require the expected generation while atomically installing membership in the combined snapshot and retry on mismatch; then run a same-generation policy pair |
| Caller result | Rejected work rereads authority or returns stale/retry/cancellation | Assert A's direct caller never receives A as current |
| Cancellation | Cancellation is not a commit fence; late failure has an observation policy | Let cancellation-ignoring A finish after B or clear wins |
| Cancellation-atomic dispatcher hop | Preliminary admission remains cancellable; inside one outer same-dispatcher `NonCancellable` boundary, the nested IO transaction atomically revalidates final authority and durably commits, then its typed accepted receipt and awaited required publication stay protected; caller cancellation is checked immediately afterward | Revoke authority after preliminary admission but before the final IO transaction and prove no commit; then let accepted IO commit and queue its return on an instrumented caller dispatcher, cancel before that runnable executes, release it, and prove `wakeAccepted` names the exact receipt before cancellation emerges, the cancelled caller receives no typed return, and a later caller-owned effect does not run |
| Shared-entry cancellation | Cancelling one waiter does not detach healthy shared work. Cancellation requested for the shared entry atomically makes that exact membership non-joinable; join eligibility, termination, and commit authority remain separate. Late cleanup removes only the still-matching entry identity | Hold shared A nonterminal. Prove a one-waiter cancellation control, then gate B immediately before admission and run cancellation-first and admission-first. Cancellation-first gives B a distinct eligible entry; release A and prove its identity-bound cleanup cannot remove B. Admission-first preserves the declared same-generation outcome |
| Owner boundary | Commit only data plus non-delivering emission intent; run user hooks and potentially reentrant, blocking, suspending, or backpressured delivery outside the owner | Block delivery while B commits; let a callback or hook perform nested mutation before the outer path revalidates |
| Notification | Keep durable mutation and delivery ordered and recoverable | Inject failure at a durable mutation-notification boundary |
| Key isolation | Key invalidation leaves unrelated keys valid; global clear does not | Run x and y across key clear, then global clear |
| TTL | Read-time staleness is separate from active observer expiry signals | Advance a controlled clock, read, then fire each declared signal |

## Cancellation-Atomic Dispatcher Hops

A durable write and the receipt that authorizes its required publication form
one causal operation. A dispatcher-changing `withContext` has a
prompt-cancellable return dispatch. Even when its block succeeds, cancellation
of the original context can discard the result before the caller observes it.
Therefore a prompt-cancellable return dispatch can replace the caller's
observation of an accepted receipt with `CancellationException`; it does not
undo the durable authority.

Do not leave required caller-dispatcher publication after a combined
cancellation override and dispatcher:

```kotlin
val receipt = withContext(NonCancellable + ioDispatcher) {
    store.commit()
    AcceptedAuthorityCommit(revision)
}
publishRequired(receipt)
```

The combined context is not intrinsically invalid: protected work performed
inside its block still runs. The defect is consuming its result after the
dispatcher-changing block when cancellation can skip that consumption. When
required publication belongs on the caller dispatcher, use the nested shape.

Instead, keep the dispatcher hop and required publication inside an outer
same-dispatcher `NonCancellable` boundary:

```kotlin
val receipt = withContext(NonCancellable) {
    val committedReceipt: AcceptedAuthorityCommit = withContext(ioDispatcher) {
        store.transaction {
            requireAuthority(expectedAuthority)
            store.commit()
            AcceptedAuthorityCommit(revision)
        }
    }
    publishRequired(committedReceipt) // awaits WakeAccepted(revision)
    committedReceipt
}
currentCoroutineContext().ensureActive()
return receipt
```

Keep preliminary admission cancellable and reject an already-cancelled caller
before entering the outer boundary. Final authority validation belongs inside
the nested IO transaction and must be atomic with the durable commit; never
validate, switch dispatchers, and then commit from the stale decision. A
revocation between preliminary admission and that transaction must reject
without committing. Keep the boundary narrow. The protected publisher must be
a bounded local handoff or durable enqueue. Call it directly and await an
identity-bound `WakeAccepted`; do not detach it as fire-and-forget work. Remote
or retrying delivery belongs behind the ordered idempotent notification record.
If the local handoff needs another dispatcher, nest that switch inside the same
outer boundary. After required acceptance,
`currentCoroutineContext().ensureActive()` restores the caller's cancellation
contract before later caller-owned effects. A cancelled caller does not receive
the typed return. This proves direct publication acceptance, not downstream
observation or crash durability; use the notification record for those
stronger claims.

Test with controlled IO plus an instrumented caller dispatcher and
identity-bound receipts. First pause after preliminary admission, revoke
authority, then run the final IO transaction and prove it rejects without a
durable commit. In the accepted schedule, let that transaction emit
`finalAuthorityCheck`, `durableCommitted`, and `receiptReady` as one
non-interleavable step, then finish so the continuation is queued on the caller
dispatcher. Record `returnQueued` without running that continuation, cancel the
original caller, then release it. Prove `wakeAccepted` identifies the exact
typed receipt before cancellation emerges. The cancelled caller receives no
typed return and the later caller-owned effect does not run. A no-cancellation
control must return the same receipt after `wakeAccepted`.

With latest-start-wins, reserving B rejects A even when B later fails or is
cancelled. With latest-success-wins, B's attempt alone does not reject A; only a
successful newer commit or invalidation fences it.

Across a durable persistence and notification boundary, use an ordered,
idempotent notification record. For process-local delivery, atomically commit
an owner-local, non-delivering intent, then release the owner before invoking
callbacks, predicates, factories, or a primitive that may resume, reenter,
block, suspend, or apply backpressure. Revalidate authority before committing
results computed by user code.
