# Thread Skill Handoff Contract

Read this reference only when `send-skill-handoff` is selected or a pending
skill handoff must be reconciled. The general intervention authority,
reservation, delivery, privacy, and checkpoint rules remain in
`thread-supervision-contract.md`.

## Sender Envelope

New handoffs must use v2. A persisted v1 handoff may finish under its original
semantics, but v1 cannot prove exact source identity, receiver version,
consumption mode, or runtime activation. Never upgrade a v1 payload in place or
reuse its ID for v2.

```json
{
  "schema": "codex.thread_skill_handoff.v2",
  "handoff_id": "handoff-001",
  "payload_fingerprint": "sha256:dbcfff9818210904786c9a35b66af3ee69a871820729ce94307b2fc9d9a602ea",
  "skill": {
    "name": "example-skill",
    "source_repository": "git+https://example.invalid/example/skills",
    "source_version": "1.2.0",
    "source_revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "source_path": "skills/example/SKILL.md",
    "content_manifest": {
      "schema": "codex.skill_content_manifest.v1",
      "entries": [
        {
          "path": "skills/example/SKILL.md",
          "sha256": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
          "size": 123
        }
      ]
    },
    "content_digest": "sha256:85d278e62580cf3d03db79af06bfa2a625bcd0e1955619238a07b4cfc8a6a60c",
    "verification_state": "verified"
  },
  "why_now": "The next step needs the exact transferred guardrail.",
  "mechanism": "Apply only the version-bound guardrail.",
  "receiver_basis": {
    "catalog": {
      "version": "1.1.0",
      "source_repository": "git+https://example.invalid/example/skills",
      "source_revision": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "content_digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
      "relation_to_source": "older"
    },
    "cache": {
      "version": "1.1.0",
      "source_repository": "git+https://example.invalid/example/skills",
      "source_revision": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "content_digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
      "relation_to_source": "older"
    },
    "runtime": {
      "discovery": "inactive",
      "loaded": {
        "version": "absent",
        "source_repository": "absent",
        "source_revision": "absent",
        "content_digest": "absent",
        "relation_to_source": "absent"
      }
    }
  },
  "requested_consumption": "direct-source-read",
  "activation_authorized": false,
  "scope_effect": "none",
  "authority_effect": "none",
  "ack_required": true
}
```

The source repository and revision form one immutable namespace. The source
path is normalized and repository-relative. The content manifest includes the
entrypoint and every linked file required for the transferred mechanism.
Manifest entries are strictly sorted by path and contain the SHA-256 digest and
byte length of each exact file.

Canonicalize a content manifest as UTF-8 JSON with ASCII escaping, sorted object
keys, no insignificant whitespace, and the exact `entries` order. Prefix those
bytes with `codex.skill_content_manifest.v1\n`, hash with SHA-256, and store the
result as `skill.content_digest`. Canonicalize the complete handoff the same
way after removing `payload_fingerprint`, prefix with
`codex.thread_skill_handoff.v2\n`, and hash with SHA-256. The bundled validator
is the executable definition of both algorithms.

`verification_state` must be `verified`. A sender reads the complete content
set and validates every entry before reserving the intervention. A matching
skill name or version alone is never exact. Catalog, cache, and loaded runtime
identity each record repository, revision, and content digest:

- `exact` matches version, repository, revision, and digest.
- `older` or `newer` requires ordered semantic versions in the same repository
  and a different revision or digest.
- `absent` uses `absent` for every identity field.
- `unknown` preserves uncertainty rather than inferring a relation.

`runtime.discovery=active` is not proof of the loaded bytes. The nested
`runtime.loaded` identity names those bytes. A `runtime-loaded` request is
eligible only when the sender already observed an exact cache, active
discovery, and an exact loaded identity. Otherwise request
`direct-source-read` or do not send.

`activation_authorized` is a constant false safety marker. No field grants
installation, refresh, cache mutation, runtime configuration, scope, or
authority. Activation, if separately authorized, is a different workflow and
must finish before a later handoff records `runtime-loaded`.

## Receiver Reservation

Before reading or applying handed-off guidance, atomically reserve
`(handoff_id, payload_fingerprint)` in a durable receiver-local ledger:

1. A new ID becomes `reserved` before consumption.
2. The same ID and fingerprint returns the stored terminal acknowledgement
   without reading or applying again.
3. The same ID with a different fingerprint returns `conflict/id-conflict`
   without applying.
4. If atomic reservation is unavailable, return
   `conflict/reservation-unavailable` without applying.
5. Persist the terminal acknowledgement atomically with the reservation before
   emitting it.

If the receiver may have applied the guidance but cannot prove that the
terminal acknowledgement was stored, emit no acknowledgement and mark the
receiver operation outcome unknown. The sender keeps the intervention pending
and reconciles the same ID; neither side reapplies or blind-resends.

## Receiver Acknowledgement

The receiver returns one atomic acknowledgement:

```json
{
  "schema": "codex.thread_skill_handoff_ack.v1",
  "handoff_id": "handoff-001",
  "payload_fingerprint": "sha256:dbcfff9818210904786c9a35b66af3ee69a871820729ce94307b2fc9d9a602ea",
  "expected_source_content_digest": "sha256:85d278e62580cf3d03db79af06bfa2a625bcd0e1955619238a07b4cfc8a6a60c",
  "observed_source": {
    "name": "example-skill",
    "source_repository": "git+https://example.invalid/example/skills",
    "source_version": "1.2.0",
    "source_revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "source_path": "skills/example/SKILL.md",
    "content_digest": "sha256:85d278e62580cf3d03db79af06bfa2a625bcd0e1955619238a07b4cfc8a6a60c",
    "verification_state": "verified",
    "relation_to_source": "exact"
  },
  "receiver_record_fingerprint": "sha256:dbcfff9818210904786c9a35b66af3ee69a871820729ce94307b2fc9d9a602ea",
  "status": "applied",
  "reason": "exact-direct-source-read",
  "supersession_evidence_ref": null,
  "observed_receiver": {
    "catalog": {
      "version": "1.1.0",
      "source_repository": "git+https://example.invalid/example/skills",
      "source_revision": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "content_digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
      "relation_to_source": "older"
    },
    "cache": {
      "version": "1.1.0",
      "source_repository": "git+https://example.invalid/example/skills",
      "source_revision": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "content_digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
      "relation_to_source": "older"
    },
    "runtime": {
      "discovery": "inactive",
      "loaded": {
        "version": "absent",
        "source_repository": "absent",
        "source_revision": "absent",
        "content_digest": "absent",
        "relation_to_source": "absent"
      }
    }
  },
  "consumption_mode": "direct-source-read",
  "runtime_used": false,
  "install_attempted": false,
  "evidence_refs": [
    "receiver-local:exact-source-proof"
  ]
}
```

The expected digest always echoes the handoff. `observed_source` independently
records what the receiver verified, or is `null` when no source was available.
This permits a digest mismatch to be acknowledged without claiming that the
observed bytes matched. Evidence refs are stable receiver-local recovery refs,
not raw private evidence.

Use only these closed terminal combinations:

| Status | Reason | Required state |
| --- | --- | --- |
| `applied` | `exact-direct-source-read` | Requested and actual mode are `direct-source-read`; observed source is exact and verified; `runtime_used=false`; `install_attempted=false` |
| `applied` | `exact-runtime-loaded` | Requested and actual mode are `runtime-loaded`; cache and loaded runtime identities are exact; discovery is active; observed source is exact; `runtime_used=true`; `install_attempted=false` |
| `stale` | `newer-source-supersedes` | Actual mode equals the request; observed source has a greater semantic version and verified different content; a dedicated supersession evidence ref is present; nothing applies; runtime and install flags are false |
| `conflict` | `source-mismatch` | Expected and observed identities differ; nothing applies |
| `conflict` | `source-unavailable` | Observed source is null; nothing applies |
| `conflict` | `runtime-mismatch` | Requested mode is `runtime-loaded`; cache, discovery, and loaded-runtime states are concrete; at least one is non-exact; nothing applies |
| `conflict` | `ambiguous-evidence` | An observed source exists, but at least one source, catalog, cache, loaded-runtime, or discovery state is unknown; nothing applies |
| `conflict` | `reservation-unavailable` | No receiver record exists, no source is read, and nothing applies |
| `conflict` | `id-conflict` | Receiver record holds a different payload fingerprint; no source is read and nothing applies |
| `conflict` | `unauthorized-install-attempt` | The install flag is true, runtime use is false, and nothing applies |

Every conflict uses `consumption_mode=unavailable`; for every non-install
conflict, `install_attempted=false`. `unavailable` cannot accompany `applied` or
`stale`. An applied or stale acknowledgement must name the requested mode. A
greater version is not automatically compatible: `stale` also requires a
dedicated, stable supersession evidence ref; otherwise return `conflict`.

Ordinary activity, a partial acknowledgement, an invalid combination, or a
reply without the exact ID and payload fingerprint does not acknowledge the
handoff. Keep the sender intervention pending until the bundled validator
accepts the terminal acknowledgement.

## Compaction And Recovery

Before sending, persist an immutable, content-addressed private payload ref,
schema, handoff ID, payload fingerprint, expected source digest, requested
consumption, delivery state, and acknowledgement state in
`pending_intervention`. The payload ref must recover the complete exact
envelope after compaction; a digest is not a substitute for recoverable state.

After compaction, load and validate that payload before accepting an
acknowledgement. If the payload ref is missing, mutable, unreadable, or does not
match its fingerprint, preserve the pending state and reconcile it. Never
reconstruct the source, receiver basis, or requested mode from prose.

## Validation

Validate the sender envelope before reservation and validate the
acknowledgement before clearing the pending intervention:

```bash
python3 "$PLUGIN_ROOT/scripts/validate_thread_skill_handoff.py" \
  --handoff handoff.json \
  --ack acknowledgement.json
```

The deterministic validator is read-only. It rejects unknown fields, non-canonical content
manifests and payload fingerprints, invalid identity relations, unauthorized
activation, and every cross-field state outside the table above.
