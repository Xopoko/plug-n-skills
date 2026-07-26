# Legacy Storage Migration

Use this reference for one-time imports from platform settings, old files, or
legacy databases into a canonical KMP repository. When product policy requires
one-time eligibility or no resurrection after reset, idempotent copying is not
enough: the migration must retain a durable terminal decision independently of
the current destination value.

## Authority Model

Name three different authorities:

1. The legacy source adapter owns source observations only.
2. The canonical destination owns active product state.
3. A durable migration record owns whether this migration epoch is still
   eligible to consult the legacy source.

Do not infer completion from destination absence or from the current
destination value. Destination data can be reset, cleared, or changed after a
successful migration. The migration record is durable provenance and remains
authoritative until an explicit, separately versioned re-import policy replaces
it.

A minimal migration record can use these states:

- `not-started`: no authoritative decision or source capture exists.
- `captured`: an optional, policy-safe source checkpoint, source schema,
  capture identity, and policy version are durable, but no final destination
  decision exists.
- `deferred`: no terminal decision exists; a declared retry condition or source
  watermark controls when the epoch may consult source again.
- `complete`: the migration is terminal for this epoch, with a reason such as
  `imported`, `destination-won`, or a policy-declared terminal source outcome.

Treat `corrupt` as an in-memory read classification, not a writable record
state: a declared migration-metadata key is present but its type or schema is
invalid, so no migration transition is eligible.

Use a separate `cleanup-pending` or cleanup receipt when legacy deletion is
required. Cleanup status must not erase or weaken the completed destination
decision.

## Presence And Capture

Check exact key presence, not whether a parsed value resembles a default.
Empty, unknown, or invalid destination payloads can still be authoritative
presence under the product policy.

Apply the same presence-first rule to checkpoints, receipts, epochs, and
cleanup metadata. A typed nullable getter returning `null` does not prove
absence when the key exists. Classify a present wrong-typed or malformed value
as `corrupt`; preserve it and fail before admission, source capture, projection,
destination writes, or cleanup. Only an explicit repair or separately
versioned epoch may replace it.

On Apple platforms, typed `UserDefaults` accessors and registered defaults can
return fallback values. A registered fallback is not persistent-domain
presence. Use a platform adapter that can prove whether the exact owning
persistent domain contains each key.

On Android, capture the exact configured store and key set through one
lifecycle-bound source adapter.

If a platform store cannot provide one atomic multi-key read, call the result
per-key observations, not an atomic snapshot. Record every requested slot as
missing, invalid, or valid. Do not partially parse a malformed aggregate into
an apparently valid order.

Source capture and policy projection are separate:

- capture records source-native facts and provenance in memory;
- projection is a pure, versioned mapping into candidate destination data;
- the record binds the policy version and snapshot identity used for that
  candidate.

Persist a source checkpoint only when recovery cannot atomically terminalize
the migration and must not re-read mutable source. Minimize the checkpoint,
classify it, encrypt it where required, and define retention. Preserve raw
invalid evidence only when an explicit repair or audit requirement justifies
it; otherwise retain bounded error metadata or a digest. Route migrations that
handle credentials, regulated data, or other sensitive payloads through
`kmp-security-privacy`.

## Transaction And Ownership Requirement

All canonical destination writes, resets, and deletes must share the repository
owner used by migration, or the destination must expose a conditional
transaction/CAS against an authoritative generation. A process-local mutex or
actor alone does not close crash or external-writer races.

To claim no resurrection, the terminal receipt must live in a destination-owned
generation or be committed atomically with the relevant presence/write
decision. Resets may remove active data but must preserve or advance that
generation. A value digest is not enough: equal-value ABA writes cannot prove
ownership. If the storage topology cannot provide this boundary, document
at-least-once import semantics and do not claim no resurrection across crashes
and resets.

## Resumable Protocol

1. Read the durable migration record and cleanup status.
2. If migration is `complete`, retry only idempotent `cleanup-pending` work
   when applicable, then return without capture or projection.
   If migration is `deferred` and its declared retry condition is not
   satisfied, return without consulting source. When it is satisfied,
   CAS-admit a new attempt and bind the resulting record token.
3. In the destination transaction/CAS, read exact destination presence and its
   generation. Bind the admission token to the migration epoch, record state,
   capture identity when present, policy version, and destination generation.
4. If the destination is present, atomically persist
   `complete(destination-won)` for that generation plus `cleanup-pending` when
   required, and return. Do not capture or project legacy data.
5. Reuse a durable `captured` checkpoint when policy permits and recovery
   requires it. Otherwise capture source observations and classify every
   required slot before projection. If a durable checkpoint is required,
   CAS-install its immutable capture identity and policy version against the
   admission token, then rebind to the resulting record token. A losing caller
   discards its local capture and restarts or uses the winning checkpoint.
6. Project the captured facts with the bound policy version outside the owner
   when the mapping can block or call user code.
7. Re-enter the destination transaction/CAS and re-check the migration epoch,
   record state, capture identity, policy version, exact destination presence,
   and generation. If the record is already `complete`, return without writing
   the candidate. If any other admission field changed, discard the candidate
   and restart the decision.
8. If a destination appeared, atomically persist
   `complete(destination-won)` for the winning generation plus
   `cleanup-pending` when required. Never overwrite it with the candidate.
9. If the destination is still absent, commit only through a CAS against the
   admission generation and unchanged record token. Atomically write the
   candidate, advance or retain the authoritative generation, and persist
   `complete(imported)` plus `cleanup-pending` when required.
10. Run optional cleanup only after the durable terminal decision exists.
    Make it idempotent and clear `cleanup-pending` only after success.

If no source exists, mark the epoch complete only when the observation is
authoritative for the declared source scope. If source data can arrive later
through sync or another process, persist `deferred` with an explicit retry
condition or source watermark instead of turning temporary absence into
terminal proof. Persist any terminal outcome and required `cleanup-pending` in
the same destination transaction.

For malformed or policy-invalid source, make the policy explicit:

- terminal policy: atomically persist a terminal outcome such as
  `complete(source-rejected)`, the minimum required audit metadata, and
  `cleanup-pending` when required;
- repairable policy: retain a policy-safe checkpoint and transition to
  `deferred` with an explicit repair/retry condition; do not write destination
  data or clean up the source.

## Recovery And Proof Matrix

| Scenario | Required decision and proof |
| --- | --- |
| Destination pre-exists | In the destination transaction/CAS, persist `complete(destination-won)` for the observed generation; do not capture or project legacy state. Then reset the destination through its real API and prove legacy data does not reappear. |
| Crash after durable checkpoint | Resume from the same policy-safe checkpoint and policy version; when no checkpoint is required, re-read only as the declared retry policy allows. |
| Crash at destination commit | Prove destination data and the terminal receipt commit together, or prove a destination-owned generation makes the commit recoverable without equal-value ABA ambiguity. |
| Authoritative source absence | Apply the declared terminal policy in the destination transaction, or persist an explicit deferred outcome when source data may still arrive. |
| Deferred source arrives | Before the retry condition, prove retries do not consult source. After the declared watermark or trigger, CAS-admit one new attempt; if destination appeared meanwhile, terminalize destination-won instead. |
| Malformed source, terminal policy | Persist `complete(source-rejected)` with policy-authorized, minimized, and protected evidence; otherwise keep bounded metadata or a digest. Never partially project a prefix or subset as valid data. |
| Malformed source, repairable policy | Keep a policy-safe quarantined/deferred checkpoint, preserve the source, and prove a retry cannot write partial data. |
| Wrong-typed or malformed migration metadata | Read presence before typed decoding and classify it `corrupt` in memory. Prove the original key and value remain unchanged while admission, source-capture, projection, destination-write, migration-metadata-write, and cleanup counts stay zero. |
| Concurrent callers | Gate both callers before admission; one repository owner produces at most one checkpoint and one durable terminal decision. |
| Concurrent durable captures | CAS-install one capture identity; prove a losing caller discards its local capture and cannot project or commit it. |
| Registered default only | Prove the fallback is not persistent presence and classify the requested source key as missing. |
| Destination appears during projection | Re-check presence and generation at final commit; atomically record `complete(destination-won)` without overwriting the newer destination. |
| External writer races final commit | Force a generation mismatch and prove CAS retries the decision instead of overwriting the external value. |
| Another importer completes, then reset occurs | Keep the first terminal receipt across reset; prove a stale projector sees the completed or changed admission token and cannot recommit its candidate. |
| Cleanup fails | Keep the durable destination decision, retain `cleanup-pending`, and retry only the idempotent cleanup step. |
| Crash before cleanup starts | Prove `cleanup-pending` committed with the terminal receipt and only cleanup resumes. |
| Explicit re-import | Require a new migration epoch or policy version; current destination absence alone never re-enables the old source. |

Test the platform adapters with real storage APIs where feasible and keep the
state machine and projection schedules in `commonTest`. Use barriers at
admission, pre-existing-destination terminalization, capture, final generation
re-check, the atomic destination-plus-receipt commit, reset, and cleanup.
Sleeps are not concurrency proof.

## Source Notes

- Android DataStore requires idempotent migration hooks and retries after
  migration, write, or cleanup failures:
  <https://developer.android.com/reference/androidx/datastore/core/DataMigration>
- AndroidX runs migrations inside the destination update and defers cleanup
  until after that update:
  <https://github.com/androidx/androidx/blob/3bad9ac4690c8fdea474dd009e5787e2d0533ab7/datastore/datastore-core/src/commonMain/kotlin/androidx/datastore/core/DataMigrationInitializer.kt>
- Apple documents persistent and volatile `UserDefaults` domains and registered
  fallback behavior:
  <https://developer.apple.com/documentation/foundation/userdefaults>
- SQLite exposes an application-owned durable version field:
  <https://www.sqlite.org/pragma.html#pragma_user_version>
- Flyway records applied, failed, baseline, and other decisions independently
  of current schema shape:
  <https://documentation.red-gate.com/flyway/flyway-concepts/migrations/flyway-schema-history-table>
- Room runs migration paths inside a transaction and binds them to explicit
  start and end versions:
  <https://developer.android.com/reference/androidx/room/migration/Migration>
