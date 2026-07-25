# Async State Consistency Reference

Use this reference after `async-state-consistency` is selected. It expands the
state, authority, and deterministic race matrices without prescribing a
language or framework.

## State Matrix

| State | Domain meaning | Replay rule | Projection rule |
| --- | --- | --- | --- |
| Initial or unknown | No authoritative domain value has been established | Replay explicitly when the contract exposes lifecycle state | Preserve the discriminator; never map it to an empty or default value |
| Available empty | An authoritative value exists and is empty | Replay as a valid value | Preserve as available |
| Available value | An authoritative non-empty value exists | Replay only with current ownership | Preserve value and ownership semantics |
| Invalidated | Earlier ownership was revoked | Never replay the revoked value as current | Preserve invalidated or map through a declared fail-closed policy |
| Error | The contract exposes an operational failure | Do not invent it from ownership rejection alone | Preserve error separately from initial and invalidated |
| Stale or retry | A direct result lost ownership or could not be accepted | Return only when declared by the caller contract | Do not persist as shared error unless explicitly designed |

Loading may be a separate state or metadata. Decide whether a valid retained
value can coexist with loading instead of erasing it implicitly.

## Authority Matrix

| Authority | Scope | Advances when | Must protect |
| --- | --- | --- | --- |
| Global generation | All keys and domains | Global clear, reset, or equivalent revocation | Every read, replay, and commit |
| Key or domain generation | One key or declared invalidation domain | Key/domain invalidation | Work and cached values in that domain only |
| Publication revision | Competing ordinary publications in one domain | The declared policy reserves newer work or accepts a successful commit | Out-of-order completion without emitting invalidated |
| Operation identity | One async attempt or caller | An attempt or join begins | Direct caller, join, and cancellation outcome; final commit only when the supersession policy reserves ownership |
| Dependency revision vector | External owned inputs | A dependency changes | Derived memo or projection freshness |

An empty dependency vector is not global freshness. Validate the global or
owning-domain generation independently so clear cannot become invisible.

### Equality-conflating observers

An observable may retain only its latest snapshot and coalesce intermediate
updates. A sequence such as available V, invalidate, then available V again can
therefore look unchanged when snapshot identity contains only the payload.

If consumers must cancel, restart, or fence work across that transition, make
the owning authority epoch part of the retained snapshot identity or provide an
equivalent lossless revision receipt at their decision boundary. Do not rely on
an intermediate invalidated value being delivered before the equal replacement,
and do not make scheduler draining part of the production contract. A consumer
that publishes derived state must validate the current epoch at its commit
surface even when the payload compares equal. Payload equality is not authority
equality.

### Authority token preservation

A source-issued ownership token is authority evidence, not a consumer DTO.
Carry the exact token value through caches, projections, retained snapshots,
and commit fences, or wrap it without decomposing it. Do not synthesize a new
token from currently exposed generations, counters, or a consumer-chosen owner.
Reconstruction can collapse distinct owners and silently discard fields added
later by the authority source.

When a boundary cannot transport the token representation directly, define a
versioned lossless encoding owned by the authority contract. Its
authority-owned decoder must produce a complete valid token under the source
contract or reject the input. Fail closed on an unsupported version and on a
supported-version envelope that is malformed, truncated, noncanonical, or
missing an authority-bearing field. Preserve the complete token value; only the
source contract decides which fields participate in identity. Domain state may
pair its own payload with the source token, but comparisons and validation
still use the source-issued token contract.

Choose one supersession policy per operation family:

- latest-start-wins: reserving B immediately supersedes A. If B later fails or
  is cancelled, A remains rejected and callers receive their declared outcomes;
- latest-success-wins: starting B does not supersede A. B advances publication
  authority only if B commits successfully, so A may still commit when no
  invalidation or successful newer publication intervenes.

Attempt identity always distinguishes caller outcomes. For latest-start-wins,
the commit fence compares the reserved publication sequence. For
latest-success-wins, the commit fence compares committed publication authority
and invalidation generation; B's attempt identity alone does not reject A.

Do not infer this choice from whichever callback happens to finish first.

Choose a separate same-generation admission policy per operation family:

- join or coalesce callers onto one shared operation;
- queue or serialize distinct attempts;
- run attempts independently.

Cross-generation liveness repairs must preserve that policy. Admission policy
and latest-start/latest-success publication policy are separate decisions.

## Path Inventory

Audit every row that exists:

| Path | Typical stale escape | Required authority |
| --- | --- | --- |
| Active observer | Old completion publishes after clear or newer work | Final atomic ownership-and-publish transition |
| Late subscriber | Replay container retained a revoked value | Current lifecycle state and generation |
| Warm cache | Hit bypasses current invalidation state | Atomic candidate-and-authority read |
| One-shot caller | Shared publish is rejected but the function returns its own value | Explicit caller supersession outcome |
| Coordination stack | An outer mutex, actor, queue, single-flight, or coalescer still makes a post-invalidation caller join or wait behind revoked work | Where a layer admits or joins shared work, generation and entry membership change atomically; every layer detaches revoked work or permits current-generation progress |
| Memoized projection | Candidate is read before dependency or global validation | Stamped complete snapshot or retry |
| Persistence | Late work writes a value that later startup replays | Ownership checked in the persistent commit |
| Notification | Mutation commits but subscribers never learn it | Non-delivering intent in the state commit; delivery after release, or durable ordered notification |
| Projection | Initial or invalidated collapses into a domain default | Preserve state discriminator and modality |

## Linearization Patterns

### Serialized owner

A mutex, actor, event loop, serial executor, or transaction owns the final
transition:

1. perform slow work outside the owner;
2. enter the serialized owner;
3. compare captured ownership with current authority;
4. if current, commit owned state and cache plus non-delivering caller and
   notification intents;
5. if rejected, record only a non-delivering caller-outcome intent;
6. exit the owner;
7. deliver the accepted or rejected caller outcome and any notification.

Do not release the owner between validation and commit.

### Compare-and-set

Represent value and authority as one immutable snapshot. Replace the expected
snapshot with a new one atomically. On failure, reread and either retry or
return the declared non-current outcome.

### Stamped replay read

The complete candidate and its authority must come from one consistent read:

1. capture a non-invalid stamp or owning revision;
2. copy the complete candidate and required metadata;
3. validate the same stamp or revision;
4. retry or fall back to a serialized read when a writer intervened;
5. validate dependency revisions without skipping the owning-domain revision.

Do not read a candidate, release synchronization, then separately ask whether
it is current.

### Mutation and notification

The serialized owner may validate authority and atomically commit only owned
data plus an owner-local, non-delivering emission revision or intent. It must
not invoke subscriber callbacks, user-supplied predicates or factories, or any
delivery primitive that can synchronously resume or reenter, block, suspend, or
apply backpressure. Treat an observable primitive write as delivery unless its
contract proves otherwise. Run delivery and user code after releasing the
owner; when user code computes a candidate or decision, re-enter and revalidate
authority before committing it. Across a durable boundary, use an ordered,
idempotent notification record and prove recovery after an injected boundary
failure.

### Cancellation boundary

Cancellation is not a commit fence. Treat caller cancellation, underlying work
termination, shared-state publication authority, and late failure observation
as separate contracts.

### Coalesced-work invalidation

Admission to shared work must linearize against invalidation. In one atomic or
serialized transition, read the current owning generation and either join a
matching current-generation entry or install the new entry. Do not validate an
ownership token, release ownership, and later mutate the in-flight registry.

Invalidation must atomically advance the owning generation and detach matching
in-flight entries from the current lookup, join, and wait path. A caller whose
lookup linearizes afterward neither joins nor waits behind revoked work; it
starts or joins current-generation work independently. This bypass is
generation-scoped: preserve the declared same-generation join, queue,
serialization, coalescing, and publication-order policies. Cancelling revoked
work is cleanup, not the liveness fence.

Apply the rule at every outer and inner coordination layer on the component's
public path: mutex, actor, queue, single-flight, or coalescer. Inner-layer
correctness does not compensate for an outer layer that still serializes B
behind blocked A.

## Causal Receipts And Observable Traces

Race tests need separate evidence for scheduling, path completion, and
observation:

1. Attach the observer or caller-result recorder before the controlled
   interleaving and assign a monotonic sequence to every observable value,
   replay, error, caller outcome, commit attempt, and enqueue.
2. Bind every receipt to an operation identity. Record `started(A)` only after
   A enters the intended asynchronous path.
3. Apply the invalidating or superseding transition and record its committed
   receipt.
4. Release the late fake, continuation, or barrier. Treat `released(A)` or
   continuation resume as a schedule receipt only.
5. If the schedule requires A to traverse the guarded completion path, await a
   bounded `decision(A)` receipt placed after the real post-await commit
   decision or caller-outcome branch, and assert
   `released(A) < decision(A)`. A marker in the fake's release callback does
   not prove traversal through the tested component. A `finally` marker is a
   separate `terminated(A)` receipt and cannot substitute for `decision(A)`.
6. Close the observation horizon. Instrument commit, publish, replay,
   persistence, caller-result, and enqueue surfaces that the claim covers. Once
   every relevant operation is decided or terminated, drain or acknowledge
   each controlled output executor through a barrier ordered after its last
   enqueue opportunity.
7. Assert the complete ordered trace, not only its last value. Any forbidden
   transient publication, replay, cache write, error, or caller result fails
   even when the eventual state is safe. An empty downstream trace is not proof
   while an instrumented output queue can still contain work.
8. Run a permitted control schedule through the same observer and causal
   receipts so a disconnected probe or vacuously empty trace cannot pass.

A timeout may bound a failed wait, but it is diagnostic evidence rather than a
successful completion receipt.

This proof covers only the enumerated interleavings and instrumented surfaces.
Use platform-appropriate stress, race detectors, model checking, or runtime and
memory-order evidence for claims outside that boundary.

## Deterministic Race Matrix

Every test uses explicit gates at the last controllable boundary. Run both
winners where order is part of the contract.

| ID | Controlled schedule | Required assertions |
| --- | --- | --- |
| ASC-01 | Project initial, then publish available empty | Initial never appears as a domain value; empty remains valid |
| ASC-02 | Publish A, invalidate, then attach a subscriber | The subscriber never receives A as current |
| ASC-03 | Start A, invalidate, then complete A | A's real completion path finishes; the complete trace shows that A never publishes, replays, repopulates, or returns as current |
| ASC-04 | Start same-domain A then B; complete B then A | B remains observable and replayable; no false invalidated state |
| ASC-05 | Hold A at final pre-commit; let B commit; release A | A loses the atomic commit and B remains current |
| ASC-06 | Hold A at final pre-commit; let clear commit; release A | A cannot repopulate any layer |
| ASC-07 | Reject one-shot A after B wins | A's caller receives B or declared stale/retry/cancellation, never A |
| ASC-08 | Read candidate A; clear before authority validation | Read retries or rejects; empty dependencies cannot validate A |
| ASC-09 | Invalidate x while x and y are active; then repeat globally | Key invalidation rejects x only; global invalidation rejects both |
| ASC-10 | Advance controlled time past TTL, then read and fire each signal | Clock alone follows declared emission rules; next-read staleness is explicit |
| ASC-11 | Fail between mutation and notification | No committed value becomes permanently invisible; duplicates are safe if allowed |
| ASC-12 | Cancel A, let B win, then allow cancellation-ignoring A to finish | A's real completion path finishes; the complete trace has no A commit or current return, while late failure remains observable |
| ASC-13 | Run the blocked-A/B schedule layer-locally; then through the component's public entry point start shared A and hold it blocked, invalidate, start B, and keep A blocked until B reaches authoritative publication | Every coordination layer detaches revoked A or permits current-generation B to progress; B becomes authoritative before A is released; A cannot commit; cancellation follows the declared shared-work policy |
| ASC-14 | Start A, start B, let B fail or cancel, then complete A | Latest-start rejects A; latest-success may accept A; both callers receive the declared outcomes |
| ASC-15 | Block delivery, commit A, then attempt B; release delivery into subscriber code that synchronously mutates C | B commits before delivery unblocks; C can acquire the owner; delivery and user code follow the declared order outside the owner |
| ASC-16 | Enter a user-supplied predicate or factory, perform a nested mutation, return, then let the outer operation attempt commit | The hook runs outside the owner; nested mutation finishes first; the outer operation revalidates and cannot overwrite its winner |
| ASC-17 | Gate immediately before B's whole atomic admission attempt; run invalidation-first and admission-first, then a same-generation pair; for CAS, allow an earlier speculative snapshot, then CAS the combined generation-and-membership snapshot by requiring the expected generation while installing membership | Invalidation-first admits B only under the current generation; admission-first is subsequently detached or revoked, later callers neither join nor wait behind it, and its late commit is rejected; a mismatched CAS retries; the same-generation pair preserves the declared admission and publication-order policies |
| ASC-18 | Publish V, invalidate, then immediately publish equal-payload V again without draining an equality-conflating observer | The retained authority epoch advances and is observable at every decision boundary; revoked work remains fenced; no consumer depends on delivery of the intermediate invalidated value |
| ASC-19 | Carry source-issued token A through a projection, then issue token B with the same exposed counters but a different source-defined owner or authority field; also present malformed, truncated, noncanonical, and incomplete supported-version encodings | Every layer preserves the complete source token and compares through the source contract; genuine B survives the same path and authorizes B's commit; A and consumer-reconstructed tokens are rejected; every invalid encoding and unsupported version fails closed |

Holding A before its last ownership check does not prove the check-to-commit
boundary. The gate must be immediately before the atomic or serialized attempt.
For ASC-13, require B's start and finish markers in the layer-local proof, then
public-entry and authoritative-publication markers in the composed proof,
before opening A's blocking gate. An inner-layer completion or unit proof is
insufficient, and a timeout is not proof.

## Review Checklist

- Is there one authoritative lifecycle state rather than consumer-specific
  patches?
- Does every projection preserve initial, available empty, invalidated, and
  declared error meaning?
- Are invalidation and publication ordering separate authorities?
- Does every path that can replay or repopulate validate the same domain?
- Are candidate value and authority accepted from one snapshot on reads?
- Can an empty dependency set accidentally make a revoked value current?
- Is validation plus state/cache/emission-intent or notification-metadata commit
  one transition?
- Is the supersession policy explicitly latest-start-wins or
  latest-success-wins, including newer failure and cancellation?
- What does a rejected direct caller receive?
- Can any outer or inner coordination layer make a post-invalidation caller
  join or wait behind work created under revoked ownership?
- Do current generation and shared-work membership become authoritative in one
  admission transition, without split validate-then-registry mutation?
- Does cross-generation progress preserve the declared same-generation
  coordination and publication-order policies?
- Is every user hook and potentially reentrant, blocking, suspending, or
  backpressured delivery step outside the serialized owner?
- Can cancellation-ignoring work still reach a commit surface?
- Do tests control the final read or commit boundary without sleeps?
- Does a released late operation produce a distinct completion-path receipt?
- Does the assertion inspect the complete ordered trace rather than only the
  terminal state?
- Is the negative assertion ordered after commit/enqueue instrumentation and
  acknowledgement of every controlled output queue?
- Does a permitted control schedule prove that the observer and receipts are
  connected?
- Can an invalidation followed by an equal-payload replacement be
  distinguished by authority epoch without relying on delivery of an
  intermediate value?
- Does every projection and commit fence preserve the complete source-issued
  authority token instead of rebuilding it from visible fields?
- Are unrelated keys independent unless the operation is explicitly global?
- Are TTL next-read and active-emission semantics tested separately?
