# Scheduled Run Proof Contract

Use this reference only when the task needs P3 or P4 proof, a scheduler canary,
a run receipt, or an authorized repair. Load the matching platform reference
separately.

## Evidence Handling

Treat definitions, status output, action arguments, crontabs, and logs as
potentially secret-bearing even when inspection is read-only. Capture raw
evidence only in a restrictive local artifact. Put allowlisted structural
fields, redacted values, or digests in model context and reports. Never paste a
raw plist, unit environment, task XML, crontab, action arguments, or complete
scheduler status into chat output.

## Production And Canary Claims

Keep separate ledgers for:

- the production job: exact target, effective definition, manager and domain,
  configured trigger, timestamps, native event chain, receipt, and effect;
- the canary: its own target, copied properties, configured trigger, native
  event chain, receipt, cleanup, and properties it could not reproduce.

A canary proves only its own P3. It can show that a scheduler mechanism and
replicated runtime properties work, but cannot prove that the production
definition's trigger fired. Production P3 requires the production job's own
configured non-demand trigger evidence and correlated receipt.

## Runtime Declaration

Compare:

- absolute executable or interpreter and tokenized arguments;
- explicit working directory and resource paths;
- allowlisted environment names and provenance;
- account, group, session, elevation, permissions, and resource access;
- stdout, stderr, receipt, and functional-effect destinations;
- overlap, retry, catch-up, sleep, and missed-trigger behavior.

Do not import an interactive shell profile wholesale. Preserve the primary
child exit status even if logging, notification, or receipt publication fails.

## Natural Trigger Wait

1. Resolve the next expected occurrence or native trigger window from the
   effective definition and current scheduler state.
2. Set one bounded deadline that includes the platform's documented tolerance
   or coalescing behavior.
3. Use a scheduler-native event wait or one transition check when available.
   Do not nest short polling loops.
4. On timeout, capture one final bounded state snapshot and leave P3 unproven.

For event, login, boot, path, queue, idle, or network triggers, bind the exact
condition and deadline rather than substituting a timer canary.

## Disposable Canary

Use a canary only when scheduler-mechanism or copied-context evidence is useful,
the production trigger cannot be safely awaited, and scheduler mutation is
authorized.

1. Capture production P0/P1/P2 evidence without upgrading its P3 claim.
2. Create a separate exact canary identifier and random nonce.
3. Reproduce only the required manager, identity, and runtime properties.
4. Make the payload side-effect-safe: write only a private receipt and bounded
   logs.
5. Schedule its own native trigger and set one bounded deadline.
6. When the scheduler lacks a disposable one-shot, enforce payload-level expiry
   and single consumption. This bounds repeated effects but does not remove an
   orphaned registration.
7. Correlate the canary's trigger event, native identifiers, nonce, definition
   fingerprint, terminal state, and receipt.
8. Remove only the exact canary, verify cleanup, and report any orphaned
   registration as unresolved.

Never rewrite the production job's schedule merely to test it.

## Effective Definition Fingerprint

Compute the expected fingerprint outside the scheduled payload. Record:

- every effective source used: base definition, loaded domain, drop-ins,
  overrides, normalized task XML, crontab source, wrapper version, and relevant
  manager state;
- deterministic ordering and canonicalization;
- secret reference identifiers and provenance, never secret values.

The receipt carries the independently computed expected fingerprint; it does
not define truth itself. If effective sources cannot be resolved or
canonicalized without losing meaningful distinctions, mark definition identity
partial or unproven instead of accepting a weak digest.

## Atomic Receipt

The wrapper sequence is:

1. Run the wrapped payload and capture its outcome and real exit status.
2. Write a temporary receipt in a private directory and atomically rename it.
3. Exit the wrapper while preserving the payload status.
4. Let the observer confirm the scheduler's later terminal/result evidence and
   compare it with the receipt.

The receipt cannot be published after the wrapper's own scheduler terminal
state because that state exists only after the wrapper exits. A useful versioned
receipt contains:

```json
{
  "schema": "scheduled-run-receipt.v1",
  "job_id": "resolved-job-id",
  "nonce": "random-per-run-value",
  "requested_at_utc": "RFC3339 timestamp",
  "started_at_utc": "RFC3339 timestamp",
  "finished_at_utc": "RFC3339 timestamp",
  "duration_ms": 0,
  "scheduler": "launchd|systemd|task-scheduler|cron",
  "domain": "sanitized manager or account",
  "invocation_id": "native id when available",
  "identity": "uid/gid or SID",
  "session_class": "sanitized session kind",
  "pid": 0,
  "parent": "sanitized parent evidence",
  "executable": "resolved absolute executable",
  "argv_digest": "digest of sanitized arguments",
  "cwd": "resolved working directory",
  "definition_fingerprint": "independently computed expected digest",
  "outcome": "succeeded|failed|cancelled",
  "exit_status": 0,
  "effect": {
    "assertion": "bounded effect description",
    "result": "passed|failed|not_checked",
    "artifact_digest": "optional"
  },
  "output_refs": ["private log or artifact reference"]
}
```

Never include credentials, secret-bearing URLs, full environments, or sensitive
payloads. A self-reported scheduler name is descriptive, not provenance.

Reject a receipt when it predates the baseline, lacks an issued nonce, omits an
available native invocation or activity identifier, cannot bind all correlation
keys to one trigger event chain, comes from another target or domain, has a
mismatched or weak definition fingerprint, was published before the payload
outcome was known, or disagrees with later available scheduler terminal state.

## Failure Interpretations

| Symptom | Proof gap |
| --- | --- |
| Works manually, scheduler exits before payload starts | executable, interpreter, permission, identity, or cwd mismatch |
| Scheduler reports success, expected effect is absent | process success was mistaken for P4 |
| Green receipt predates the request | freshness or nonce correlation is missing |
| Job exists but state is missing | wrong domain, user, path, or manager |
| Demand run passes, native trigger does not | P2 is proven; P3 remains unproven |
| Canary passes, production trigger is unseen | canary P3 is proven; production P3 remains unproven |
| Duplicate effects | overlap, retry, catch-up, or non-idempotent payload |
| No captured output | sink is missing, unwritable, or unsupported |

## Repair And Rollback

- Export or copy the exact effective definition and record state first.
- Change one runtime declaration at a time when practical.
- Preserve failure evidence before reset operations.
- Re-prove only levels invalidated by the change, then verify P4 separately.
- Restore prior enabled state and remove only task-scoped canary artifacts.
