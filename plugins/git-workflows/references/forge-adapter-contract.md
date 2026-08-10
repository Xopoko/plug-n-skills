# Forge Adapter Contract

Use this contract when a workflow needs live GitHub or GitLab state. The
workflow owns sequencing, authorization, classification, and readback. An
adapter only declares concrete operations and the evidence semantics it can
actually preserve.

## Boundary

`mcp`, `connector`, `cli`, and `rest` identify invocation surfaces, not trust
levels. Select by probed capabilities. Do not prefer `glab`, a connector, or an
MCP server merely because it exists. A high-level tool is eligible only when it
preserves the required full identifiers, exact commit IDs, host and actor
binding, pagination proof, and write outcome.

Keep platform-specific semantics explicit. GitLab discussion resolution,
GitHub review-thread resolution, merged-results pipelines, GitHub merge queues,
stack landing, and exact Git ref publication are not interchangeable. A
generic capability is shared only when its evidence and failure semantics are
the same.

The deterministic selector is:

```bash
python3 "$PLUGIN_ROOT/scripts/forge_adapter_selector.py" validate-inventory \
  --inventory ADAPTERS_JSON
python3 "$PLUGIN_ROOT/scripts/forge_adapter_selector.py" select \
  --inventory ADAPTERS_JSON --plan PLAN_JSON
```

It reads local JSON only. It never discovers tools, contacts a forge, obtains
credentials, changes Git state, or executes a selected adapter.

## Inventory

Schema: `git_workflows.forge_adapter_inventory.v1`.

The top-level object contains exactly `schema` and non-empty `adapters`.
Adapter IDs are unique. Each adapter contains exactly:

- `id`: stable lowercase inventory ID;
- `kind`: `mcp`, `connector`, `cli`, or `rest`;
- `version`: observed adapter or tool version;
- `forges`: sorted unique subset of `github`, `gitlab`;
- `host`: explicit lowercase hostname, optionally with a port, never a URL;
- `actor`: exactly `id` and `verified`; public read adapters may use null and
  false, but write plans require an exact verified identity;
- `evidence`: the exact evidence traits below;
- `capabilities`: known capability IDs mapped to `support` and `operation`.

`support` is `probed`, `declared`, or `unsupported`. Only `probed` satisfies a
plan. A probe is a harmless read that establishes the response shape and
evidence behavior; catalog prose is only `declared`.

Evidence contains exactly:

```json
{
  "explicit_host_per_call": true,
  "raw_structured_payload": true,
  "stable_object_ids": true,
  "full_commit_ids": true,
  "pagination": "page-chain-v1",
  "change_diff_truncation": "explicit",
  "write_retry": "never",
  "unknown_write_result": "exposed",
  "server_receipt_id": true
}
```

List-complete capabilities require `page-chain-v1`: retain page order,
cursor/page identity, record count, payload digest, and terminal next-page
evidence. `opaque` aggregate results never prove completeness. Write
capabilities additionally require `write_retry=never`, exposed unknown outcome,
and a server-returned receipt ID.

`forge.change.files.list-complete.v1` additionally requires
`change_diff_truncation=explicit`. Its live receipt enumerates every changed
file and exposes whether any patch, hunk, or file content was truncated. A
selector-ready adapter can detect truncation; it does not prove a particular
response was untruncated. The workflow must reject a complete-review claim when
any live record is truncated, missing, or cannot be matched to the bound head.

## Capability IDs

Shared reads:

- `forge.auth.current-user.read.v1`
- `forge.repository.read.v1`
- `forge.repository.branch.read.v1`
- `forge.change.read.v1`
- `forge.change.files.list-complete.v1`
- `forge.change.diff.read.v1`
- `forge.change.discussions.list-complete.v1`
- `forge.change.discussion.read.v1`
- `forge.stack.changes.list-complete.v1`

GitLab-specific operations:

- `gitlab.change.diff-versions.list-complete.v1`
- `gitlab.change.diff-version.read.v1`
- `gitlab.change.pipelines.list-complete.v1`
- `gitlab.change.discussion.reply.create.v1`
- `gitlab.change.discussion.resolve.set.v1`

An inventory `operation` is the exact MCP/connector tool name, CLI/API command
shape, or REST method and endpoint template used to implement that capability.
Never interpolate note text, branch names, or untrusted review content into a
shell command.

## Plans And Profiles

Schema: `git_workflows.forge_adapter_plan.v1`. The exact fields are:

```json
{
  "schema": "git_workflows.forge_adapter_plan.v1",
  "profile": "forge-code-review",
  "forge": "github",
  "host": "github.example.test",
  "expected_actor_id": null,
  "preferred_adapter_ids": [],
  "allow_degraded_read": false,
  "write_state": {
    "operation": "none",
    "outcome": "not-attempted",
    "adapter_id": null
  }
}
```

Profiles:

- `forge-code-review`: read one change, a complete paginated changed-file
  inventory with explicit truncation evidence, its untruncated diff, and the
  complete discussion collection;
- `stacked-delivery-read`: read repository and branch identity plus a complete
  stack collection;
- `gitlab-review-read`: collect the full GitLab review-response epoch inputs;
- `gitlab-review-reply`: add exact-head pipeline evidence and one reply write;
- `gitlab-review-resolve`: add one separately authorized resolution write.

Selection is deterministic. `preferred_adapter_ids` is an explicit order;
unlisted candidates sort by ID. The selector never ranks transports by name.
The result is `READY`, `DEGRADED`, `READBACK_ONLY`, or `REPORT_ONLY`.

## Fallback And Degraded Rules

- Use one primary remote adapter for an accepted immutable epoch. A change of
  adapter, host, actor, response shape, or evidence traits invalidates the
  candidate epoch and requires a fresh bind and stable collection.
- Read fallback is permitted before epoch acceptance. `401` or `403` never
  authorizes implicit host or credential switching. A wrong verified actor is
  a stop condition, not a fallback hint.
- `gitlab-review-reply` may degrade to `gitlab-review-read` only when the plan
  explicitly permits read degradation. `gitlab-review-resolve` may degrade to
  reply, then read. Report the selected profile; never claim the requested
  mutation occurred.
- Opaque pagination, hidden or observed diff truncation, truncated IDs,
  human-formatted output, missing raw structure, abbreviated SHAs, or an
  unprobed capability is `REPORT_ONLY` for completeness-sensitive work.
- After a timeout, connection loss, or ambiguous write response, never select a
  fallback writer. The only eligible transition is `READBACK_ONLY`. Fetch the
  exact object and accept only one unique matching server receipt; zero or more
  than one remains unresolved.
- A confirmed write is not permission to repeat it. Resolve one discussion only
  after its separate authorization and fresh readback.
- Local Git publication, expected-old-OID leases, signing recovery, worktree
  repair, rebases, pushes, retargets, approvals, and merges stay outside this
  adapter selector and retain their workflow-specific contracts.

## Receipt Limits

The selector proves only that local declarations satisfy this schema. It does
not prove that an adapter implementation is honest, that live credentials
match a later Git push credential, that pagination evidence is authentic, that
a forge write is authorized, or that a review conclusion is correct. Preserve
raw responses in restrictive task-local artifacts and pass only bounded
projections and hashes into normal output.
