# GitLab API Compatibility

Load this reference when choosing an API client, authenticating to a non-default
host, collecting paginated state, handling fork MRs, or encountering CLI or
server-version differences.

## Supported Baseline

Use the documented GitLab REST API v4 as the compatibility baseline. Prefer
`glab api` as an authenticated REST transport when available. Keep the
transaction contract independent of high-level `glab mr` commands, GraphQL,
undocumented fields, and host-specific extensions.

Bind every request to an explicit hostname. Address MR endpoints through the
target project and project-scoped MR IID. After the first MR read, retain the
numeric target project ID, MR global ID, and IID to prevent path or context
confusion. Resolve the current account through `GET /user`, record its stable
numeric ID, and re-check it immediately before the first write.

For a fork MR, `source_project_id` can differ from the target project. Resolve
the source project separately, verify its canonical project path and clone
identity against the chosen Git remote, and fetch or push the source branch
there. If the source project or branch is unavailable, do not redirect a push
to the target project.

## REST v4 Surface

Use these documented operations:

| Purpose | Method and endpoint |
| --- | --- |
| Verify visible authenticated account | `GET /user` |
| Bind MR identity and current head | `GET /projects/:id/merge_requests/:merge_request_iid` |
| List all discussions | `GET /projects/:id/merge_requests/:merge_request_iid/discussions` |
| Read one discussion | `GET /projects/:id/merge_requests/:merge_request_iid/discussions/:discussion_id` |
| Reply in the same thread | `POST /projects/:id/merge_requests/:merge_request_iid/discussions/:discussion_id/notes` |
| Resolve one thread | `PUT /projects/:id/merge_requests/:merge_request_iid/discussions/:discussion_id` |
| List diff versions | `GET /projects/:id/merge_requests/:merge_request_iid/versions` |
| Read one diff version | `GET /projects/:id/merge_requests/:merge_request_iid/versions/:version_id` |
| List MR pipelines | `GET /projects/:id/merge_requests/:merge_request_iid/pipelines` |
| Read source project identity | `GET /projects/:source_project_id` |
| Read source branch head | `GET /projects/:source_project_id/repository/branches/:branch` |

URL-encode project paths, branch names, and other path parameters exactly once,
or use numeric project IDs. Never interpolate note text, paths, or discussion
content into an endpoint or shell command.

Use `sha` from the MR response as the current source head. Record `diff_refs`
and, when position mapping matters, the current diff version's
`head_commit_sha`, `base_commit_sha`, and `start_commit_sha`. Do not assume an
old note position belongs to the latest version. Commit identities accepted by
the guard are exactly 40 or 64 hexadecimal characters; abbreviations and other
lengths fail closed.

## Complete Pagination

GitLab list responses are paginated. Follow the server-provided next link or
next-page metadata until it is absent. Do not depend on total-count headers,
fixed page counts, default page size, or result ordering.

For stable collection:

- request a bounded supported page size;
- retain response pagination metadata for every page;
- reject conflicting top-level and nested pagination metadata;
- normalize by stable IDs after all pages arrive;
- reject conflicting duplicate IDs;
- collect twice and compare normalized digests;
- stop mutation mode when churn persists.

`glab api --paginate` is a convenience, not by itself an audit record. Preserve
enough page or header evidence to prove completion. When the installed CLI
cannot provide that evidence, use a REST client that can follow and record
pagination explicitly.

## glab API Transport

Inspect the installed surface before relying on flags:

```text
glab version
glab api --help
glab auth status --hostname HOST
```

Use `--hostname` for the bound host and specify `--method` explicitly for
writes. Some field flags change the default method. Keep tokens out of command
arguments, logs, and artifacts; use the CLI's authenticated host configuration
or another approved credential source.

Feature-probe conveniences such as pagination/output flags, typed field
handling, high-level MR commands, or GraphQL fields with `--help` and a harmless
read-only request. If unavailable, fall back to the documented REST v4
endpoint. An omitted or unknown response field is `unverified`, not `false`.

Do not parse human-formatted `glab` output when JSON REST output exists. Keep
the complete response as provenance-bearing evidence in a restrictive
task-local artifact and pass only the required structural fields or hashes to
model context.

## Reads, Writes, And Failures

- Treat `401` as an authentication failure and `403` as an authorization or
  policy failure; do not switch hosts or credentials implicitly.
- Treat `404` as ambiguous between absence and visibility until project and MR
  identity are independently confirmed.
- Honor server rate-limit and retry guidance within one bounded deadline.
- Treat a timeout, connection loss, or ambiguous `5xx` after POST or PUT as an
  unknown write result. Read back to recover one authoritative server receipt;
  if none or more than one match exists, stop rather than retrying.
- Do not assume the discussions API offers compare-and-swap or a client
  idempotency key. Implement response-key readback at the transaction layer.
- Separate POST reply from PUT resolution and verify each with a GET.

## Guard Input Contract

The deterministic guard is a read-only local validator. It emits one JSON
object, never prints note bodies, never fetches GitLab state, and never performs
a reply or resolution write:

```text
snapshot --mr FILE --discussions FILE --diff-version FILE --host HOST --actor-id ID --source-ref-head SHA --target-ref-head SHA
compare --before FILE --after FILE
verify-head --snapshot FILE --expected-head SHA --local-head SHA --source-ref-head SHA --pipeline FILE
validate-plan --snapshot FILE --plan FILE --expected-head SHA --local-head SHA --source-ref-head SHA --pipeline FILE
hash-body --body-file FILE
dedupe-key --plan FILE
```

Snapshot creation requires every shown input and binds host and account hashes,
source and target project IDs, open MR identity, branch identities, exact source
and target ref heads, full MR `diff_refs`, and one selected matching
diff-version identity. The caller must separately prove from the versions list
that the selected version is current; the guard does not establish list
position. A raw discussion array fails completeness unless
`--assume-complete-discussion-array` is present. Prefer complete JSON or NDJSON
pagination envelopes.
Accepted alias fields are compatibility inputs, not precedence rules: if two
non-empty aliases disagree, the guard rejects the record. Safety-relevant
scalar fields such as branches, discussion IDs, and pipeline status must retain
their documented JSON types; objects and arrays are never stringified into
identities. A nested wrapper and direct record fields must not be mixed in the
same input object, and direct records, single wrappers, page envelopes, and
collection envelopes are mutually exclusive. Positive numeric IDs are
canonicalized before duplicate detection.

Head verification requires every shown input. A raw pipeline array or single
pipeline object fails completeness unless `--assume-complete-pipelines` is
present. Prefer an explicit complete pagination envelope. Only a successful
pipeline at the exact expected head is write proof.

`validate-plan` also requires `--expected-head`, `--local-head`,
`--source-ref-head`, and `--pipeline`; use
`--assume-complete-pipelines` only with separately recorded pagination proof.
It accepts `gitlab_review_guard.plan.v2`, one discussion per plan, and derives
the exact-head proof from those separate evidence inputs rather than trusting a
proof embedded in the plan. It validates snapshot bindings, designated writer
identity, reply dedupe and receipt state, or the separate authorization and
confirmed reply receipt required for a resolution. It does not authenticate
the fetched JSON, authorize, or execute the planned API request.

Exit `0` means the requested gate passed, `2` means a comparison or safety gate
failed, and `1` means malformed or unreadable input.

Official GitLab documentation:

- REST API:
  https://docs.gitlab.com/api/rest/
- REST authentication:
  https://docs.gitlab.com/api/rest/authentication/
- Users API:
  https://docs.gitlab.com/api/users/
- REST pagination:
  https://docs.gitlab.com/api/rest/#pagination
- Merge requests API:
  https://docs.gitlab.com/api/merge_requests/
- Discussions API:
  https://docs.gitlab.com/api/discussions/
- Pipelines API:
  https://docs.gitlab.com/api/pipelines/
- Projects API:
  https://docs.gitlab.com/api/projects/
- Repository branches API:
  https://docs.gitlab.com/api/branches/
- GitLab CLI API command:
  https://docs.gitlab.com/cli/api/
- GitLab CLI authentication:
  https://docs.gitlab.com/cli/auth/login/
