# Review Transaction Contract

Load this reference when the task can push, wait for CI, write a reply, resolve
a discussion, or encounter concurrent MR activity or an uncertain write
receipt.

## State Machine

Treat one review response as this transaction:

```text
READ_STABLE(E0)
  -> TRIAGE
  -> PREPARE
  -> PREPUSH_COMPARE(E0)
  -> PUSH(H1)
  -> PROVE_EXACT_HEAD(H1)
  -> RECONCILE(E1)
  -> REPLY
  -> optional RESOLVE
  -> FINAL_READBACK
  -> DONE
```

Move to `REPORT_ONLY` when pagination is incomplete, stable reads cannot be
obtained within the bound, ownership is ambiguous, permissions are missing, a
required policy gate is unavailable, or exact-head CI cannot be proven. Move an
uncertain mutation to `READBACK`; never retry it blindly.

## Immutable Review Epoch

Record an accepted epoch as immutable data:

- hashes of the explicit GitLab host and visible authenticated account ID;
- source and target project numeric IDs;
- designated writer role, bound to the visible authenticated account ID;
- MR global ID and project-scoped IID;
- source project ID and canonical path, source branch, credential-free remote
  identity, and ref;
- target project ID, target branch, and target-ref SHA;
- MR source-head SHA and `diff_refs` base, start, and head SHAs;
- selected current diff-version ID plus its base, start, and head commit SHAs,
  with separate versions-list evidence that the selection is latest;
- opened MR state and the bound source and target branch identities;
- complete discussion digest and pagination-evidence digest;
- collection start and finish times plus pagination evidence;
- repository-required proof policy known at collection time.

Build the discussion digest from stable discussion IDs and, for every note,
the note ID, stable author ID, system flag, creation and update times,
resolvable and resolved state, position identity, and a body hash. Keep the
body available for classification in a restrictive artifact, but do not print
it from the guard or normal status output.

Do not use a mutable working JSON file as the epoch. Save the accepted snapshot
under a new task-local name or content hash, and derive later comparisons from
it.

## Stable Complete Snapshot

For each candidate snapshot:

1. Fetch the MR object and bound source and target refs as a fence.
2. Fetch every discussion page by following server pagination until no next
   page exists. Record page order, cursors or page numbers, counts, and
   completeness evidence.
3. Normalize discussions and notes by stable IDs. Reject conflicting duplicate
   IDs.
4. Fetch the MR object and bound refs again. Reject the candidate if identity,
   state, source head, target head, or diff refs changed during collection.
5. Collect a second complete candidate and require its normalized digest and MR
   fence to equal the first.

Do not accept page 1, a UI counter, `updated_at`, an MR overview, or a caller's
unchecked "all pages" claim as completeness proof. A raw discussion array is
incomplete by default. Use `--assume-complete-discussion-array` only after the
caller has exhausted pagination and recorded that proof outside the array.
Prefer an evidence-bearing complete pagination envelope or NDJSON page
envelopes.

Use:

```text
python3 $SKILL_ROOT/scripts/gitlab_review_guard.py snapshot --mr MR_JSON --discussions DISCUSSIONS_JSON --diff-version DIFF_VERSION_JSON --host HOST --actor-id ACCOUNT_ID --source-ref-head SHA --target-ref-head SHA
python3 $SKILL_ROOT/scripts/gitlab_review_guard.py compare --before SNAPSHOT_A --after SNAPSHOT_B
```

All snapshot inputs shown above are required. The MR must be open. The
source-ref head must equal the MR and diff head. The target-ref head is a
separate fence and is never substituted with the merge-base SHA. The full MR
`diff_refs` must match the selected diff-version commit identity. The caller
separately proves from a complete versions list that this selection is latest;
the guard binds the selected object but does not prove list position. A Git
commit identity must be exactly 40 or 64 hexadecimal characters.

The commands emit one deterministic JSON object. Exit `2` from `compare` means
the epochs drifted; it is not a prompt to weaken comparison.

## Pre-Push Compare

Immediately before push:

1. Fetch the exact source ref from the bound source project.
2. Build and accept another stable complete snapshot.
3. Require its MR head, diff refs, discussion digest, edits, replies, and
   resolved states to match the triaged epoch.
4. Require the remote source ref and MR head to equal the epoch source SHA, and
   require the target ref to equal the epoch target SHA.
5. Require the prepared local commit to descend from that exact SHA and contain
   only the reviewed plan.

Any new push, rebase, reviewer edit, reply, resolution change, or relevant
target/diff change invalidates the affected classification. Rebuild the epoch
and re-triage. Do not force-push unless both repository policy and the user
explicitly authorize it; use an exact lease when authorized.

## Exact-Head And CI Gate

After push, bind `H1` to the full local commit SHA. Within one bounded wait:

- fetch the source ref and MR again;
- require local HEAD = remote source-ref HEAD = MR head = `H1`;
- for direct source-head CI, select only a pipeline whose reported `sha` equals
  `H1`;
- for repository-required merged-results CI, separately prove that the
  synthetic pipeline commit binds the current `H1` and accepted target SHA;
- verify every required job, child/downstream result, approval-independent
  check, or merged-results provenance required by repository policy;
- invalidate the gate if the MR head changes while waiting.

Use:

```text
python3 $SKILL_ROOT/scripts/gitlab_review_guard.py verify-head --snapshot SNAPSHOT --expected-head SHA --local-head SHA --source-ref-head SHA --pipeline PIPELINE_JSON
```

Every shown input is required. Pipeline input must be an explicit complete
pagination envelope. A raw array or single pipeline object is incomplete
unless the caller passes `--assume-complete-pipelines` after separately proving
collection completeness. The selected direct pipeline must be successful and
its exact SHA must equal the expected, local, source-ref, MR, and diff head.
When the MR exposes `head_pipeline`, that exact pipeline ID is the selected
direct pipeline; older failed attempts at the same commit remain evidence but
do not override a successful current head pipeline.
Merged-results provenance requires additional repository-approved evidence. A
green parent, a pipeline for an ancestor, or "latest pipeline" without bound
provenance is insufficient.

Use one bounded watcher or native wait with transition-only output. On timeout,
collect one final state, leave proof unverified, and continue only in
report-only or accurately qualified reply mode.

## Mutation And Receipt Gate

Before any reply or resolution, validate a plan bound to the accepted snapshot:

```text
python3 $SKILL_ROOT/scripts/gitlab_review_guard.py validate-plan --snapshot SNAPSHOT --plan PLAN_JSON --expected-head SHA --local-head SHA --source-ref-head SHA --pipeline PIPELINE_JSON
```

The input plan schema is `gitlab_review_guard.plan.v2`. Each plan names exactly
one discussion and uses one mode: `plan-only`, `reply-only`, or `resolve-only`.
Its writer is exactly `{"id": "..."}`, and that ID must match the account
binding in the snapshot. Do not embed an exact-head proof in the plan. The
`validate-plan` command derives it from the separately supplied head and
pipeline inputs. The `expected` object contains exactly these bindings:

```text
host_hash
actor_id_hash
project_id
source_project_id
target_project_id
mr_iid
head_sha
diff_version_id
review_context_digest
epoch_digest
inventory_digest
discussion_id
discussion_digest
```

The top-level object contains only `schema`, `mode`, `writer`, `expected`, and
`actions`. `schema` is `gitlab_review_guard.plan.v2`; `actions` contains exactly
one object.

Reject missing, additional, or stale bindings. Every executable reply or
resolution write includes successful exact-head pipeline proof for the
expected head. A reply-only plan contains at most one reply write. A
resolve-only plan contains at most one resolution action and no reply write.

The exact reply action shape is:

```json
{
  "id": "reply-DISCUSSION_ID",
  "type": "reply",
  "operation": "post",
  "discussion_id": "DISCUSSION_ID",
  "addressed_note_ids": ["NOTE_ID"],
  "fix_commit": "FULL_HEAD_SHA_OR_no-change",
  "response_hash": "SHA256",
  "posted_body_hash": "SHA256",
  "dedupe_key": "SHA256",
  "dedupe": {
    "status": "clear",
    "matching_note_ids": [],
    "readback_complete": true,
    "readback_epoch_digest": "CURRENT_EPOCH_DIGEST"
  },
  "receipt": {"status": "not_attempted"},
  "delivery_head": "FULL_HEAD_SHA"
}
```

Only `no_change_evidence_hash` is optional, and it is required exactly when
`fix_commit` is `no-change`. Raw reply text is never a plan field.

For a reply action, derive the dedupe key from this canonical tuple:

```text
bound host hash
bound project, source-project, and target-project IDs
MR IID
expected head
bound review-context digest for the MR, source and target refs, and diff version
discussion ID
sorted unique addressed note IDs
normalized response hash
delivery head
fix commit and any no-change evidence hash
```

`fix_commit` is either the exact expected head or the literal `no-change`.
The latter requires a separate evidence hash. The delivery head must equal the
expected head. The expected epoch and discussion digests remain mandatory plan
fences, but are deliberately excluded from the response key so the same reply
is still discoverable after that reply changes the discussion epoch.

`response_hash` is SHA-256 of the guard's canonical JSON encoding of the
LF-normalized response text before the marker. Build the action with that hash,
then derive the key without printing the response:

```text
python3 $SKILL_ROOT/scripts/gitlab_review_guard.py hash-body --body-file RESPONSE_FILE
python3 $SKILL_ROOT/scripts/gitlab_review_guard.py dedupe-key --plan PLAN_WITHOUT_FINAL_KEY
```

Append exactly the returned marker to the normalized response, separated by two
LF characters, hash that complete body with `hash-body`, and record the result
as `posted_body_hash` in the transaction evidence ledger. Record the returned
key as `dedupe_key` in the same ledger. Omit both `dedupe_key` and
`posted_body_hash` from the helper input; add their derived hashes afterward,
so this construction is not circular.

Keep one designated writer for an MR transaction and re-verify the visible
authenticated account immediately before its first write. GitLab note and
resolution writes have no assumed compare-and-swap or client idempotency
guarantee. The guard validates plans only; it never POSTs, PUTs, resolves, or
otherwise performs a write.

For a reply:

1. Re-read the complete thread. The guard derives dedupe state and matching
   note IDs from the deterministic response key, writer hash, and body-free
   response binding in the snapshot; plan fields do not establish clearance.
2. POST only to that discussion.
3. Save the server-returned note ID as the receipt.
4. Re-read the complete thread and require that server note ID, writer ID,
   response key, response hash, and delivery head exactly once. The guard
   confirms note identity, writer hash, full body hash, fingerprint, readback
   epoch, and a body-free binding from the exact terminal marker to the hash of
   the normalized pre-marker response. The transaction ledger retains the
   response-key and delivery-head evidence.

For a resolution:

1. Complete and read back the reply first.
2. Fetch a fresh complete MR and discussion snapshot.
3. Build a separate resolve-only plan for exactly that discussion.
4. Bind `authorization` as
   `{"source": "user|repository-policy", "evidence_id": "...",
   "evidence_hash": "..."}`.
5. Require `reply_receipt` to contain `status`, `note_id`, `response_hash`,
   `posted_body_hash`, `response_key`, `delivery_head`, `fix_commit`,
   `addressed_note_ids`, `author_id_hash`, `note_fingerprint`,
   `readback_epoch_digest`, `reply_epoch_digest`,
   `reply_review_context_digest`, and
   `reply_discussion_digest`, plus a body-free `prewrite_discussion` proof;
   include `no_change_evidence_hash` only for a no-change reply. Its status must
   be `confirmed`. The current note must match the writer, full posted-body
   hash, semantic pre-marker response hash, fingerprint, and exactly one
   response-key marker across the discussion. Every addressed note must exist
   in the prewrite proof with the same fingerprint, while the returned reply
   note must not; the current note set must equal the prewrite set plus that one
   reply. The receipt retains the pre-write epoch and discussion digests to
   prove the write context even after the reply changes both.
6. PUT only that discussion's resolution state.
7. Re-read and verify the state before considering another thread.

The exact resolve action shape is:

```json
{
  "id": "resolve-DISCUSSION_ID",
  "type": "resolve",
  "operation": "resolve",
  "discussion_id": "DISCUSSION_ID",
  "authorization": {
    "source": "user",
    "evidence_id": "STABLE_EVIDENCE_ID",
    "evidence_hash": "SHA256"
  },
  "all_active_requests_addressed": true,
  "reread_discussion_digest": "CURRENT_DISCUSSION_DIGEST",
  "reply_receipt": {
    "status": "confirmed",
    "note_id": "SERVER_NOTE_ID",
    "response_hash": "SHA256",
    "posted_body_hash": "SHA256",
    "response_key": "SHA256",
    "delivery_head": "FULL_HEAD_SHA",
    "fix_commit": "FULL_HEAD_SHA_OR_no-change",
    "addressed_note_ids": ["NOTE_ID"],
    "author_id_hash": "SHA256",
    "note_fingerprint": "SHA256",
    "readback_epoch_digest": "CURRENT_EPOCH_DIGEST",
    "reply_epoch_digest": "PRE_REPLY_EPOCH_DIGEST",
    "reply_review_context_digest": "PRE_REPLY_REVIEW_CONTEXT_DIGEST",
    "reply_discussion_digest": "PRE_REPLY_DISCUSSION_DIGEST",
    "prewrite_discussion": {
      "id": "DISCUSSION_ID",
      "resolution_hash": "SHA256",
      "state_hash": "SHA256",
      "notes": [
        {"id": "ADDRESSED_NOTE_ID", "fingerprint": "SHA256"}
      ]
    }
  }
}
```

`prewrite_discussion.notes` contains every prewrite note ID and fingerprint,
sorted by ID, so the guard can recompute `reply_discussion_digest`. Include
`no_change_evidence_hash` in `reply_receipt` only when its `fix_commit` is
`no-change`. Before resolution, the current discussion state and resolution
hashes and every prewrite note fingerprint must still equal that proof. The
marker-bound reply review-context digest must also equal the current MR,
source-ref, target-ref, and diff-version context.

On connection loss, timeout, or ambiguous `5xx` after a POST, perform a fresh
complete readback. Accept recovery only when one current server note confirms
the planned discussion, writer, response key, response hash, and delivery head;
record that note ID as the recovered receipt. If none or more than one match,
stop. Never blindly retry an ambiguous POST. Apply the same fail-closed
readback rule to an ambiguous resolution PUT. If a reviewer reply races with
resolution, stop remaining resolutions and report the inconsistency; do not
toggle automatically.

## Completion Gate

Accept completion only when:

- the final MR head still equals the head used for proof;
- every posted note ID exists exactly once in the intended discussion;
- every resolution state matches its separately authorized action;
- no unrelated discussion was changed by this transaction;
- new or edited reviewer feedback is reported, not hidden by an old plan;
- local proof, branch CI, merged-results CI, approval state, and merge readiness
  remain separate claims.

Official GitLab documentation:

- REST API:
  https://docs.gitlab.com/api/rest/
- Merge requests API:
  https://docs.gitlab.com/api/merge_requests/
- Discussions API:
  https://docs.gitlab.com/api/discussions/
- REST pagination:
  https://docs.gitlab.com/api/rest/#pagination
