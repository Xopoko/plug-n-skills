---
name: scheduled-automation-runtime
description: >-
  Use when a local launchd, systemd timer, cron, or Windows Task Scheduler job
  works manually but fails or differs under the scheduler, or when
  registration, runtime context, last-result evidence, missed runs, or a fresh
  scheduler-originated result needs proof. Not for vendor CLI command
  construction, architecture inventory, cloud schedulers, or job business
  logic.
---

# Scheduled Automation Runtime

Use this skill to prove what a local operating-system scheduler actually ran.
A successful interactive-shell run is inner-command evidence, not scheduler
evidence.

Resolve `$PLUGIN_ROOT` from the host when available; otherwise use the absolute
path of this skill folder's `../..`.

Load only the relevant reference:

- launchd: `$PLUGIN_ROOT/references/launchd-runtime-proof.md`
- systemd timers: `$PLUGIN_ROOT/references/systemd-timer-runtime-proof.md`
- Windows Task Scheduler:
  `$PLUGIN_ROOT/references/task-scheduler-runtime-proof.md`
- cron: `$PLUGIN_ROOT/references/cron-runtime-proof.md`
- P3/P4 proof, canaries, receipts, or repair:
  `$PLUGIN_ROOT/references/scheduled-run-proof-contract.md`

## Evidence Ladder

Keep these claims separate:

- **P0 - defined:** the job definition exists and parses.
- **P1 - registered:** the intended scheduler domain accepted the job, with
  enablement or armed state recorded separately.
- **P2 - demand-run:** the scheduler manager can start it with the saved runtime
  context.
- **P3 - triggered:** the configured native, non-demand trigger condition fired
  and produced a current correlated run.
- **P4 - effective:** the intended functional effect succeeded.

Only P3 proves the bound job's scheduling. A demand start proves at most P2.
A separate canary can prove its own P3 and copied runtime properties, but can
never promote the production job above its independently observed level.

## Workflow

### 1. Bind the target

Record before acting:

- platform and scheduler;
- exact label, unit, crontab source, or task path;
- system, user, GUI, account, or session domain;
- configured trigger and expected functional effect;
- definition and output locations;
- allowed mutation level.

Inspect read-only state first. Do not infer the target from a nearby file,
process name, or a successful run in another account.

### 2. Compare the real runtime

Compare the scheduled definition with the manual run:

- absolute executable or interpreter and tokenized arguments;
- explicit working directory and resource paths;
- allowlisted environment variable names and provenance;
- identity, session, permissions, and accessible resources;
- stdout, stderr, and receipt destinations;
- overlap, retry, catch-up, sleep, and missed-run behavior.

Do not fix a scheduler environment by sourcing an interactive shell profile.
Do not dump a complete environment: it can expose credentials.

### 3. Build the evidence chain

Capture P0 and P1 before triggering anything. Then choose the smallest proof:

1. For production P3, calculate the next expected native trigger and a bounded
   deadline. Use one scheduler-native wait or transition check. On timeout,
   report P3 as unproven; do not loop or fast-poll.
2. Use a manager-mediated demand run only for P2 diagnosis.
3. When scheduler-mechanism or copied-context proof is useful and authorized,
   create a separate, uniquely named, side-effect-safe canary. Keep production
   and canary evidence ledgers separate.

Give a canary a random nonce, private output directory, and bounded terminal
wait. If the scheduler lacks a disposable one-shot, make the payload expire and
refuse repeated effects, then remove only the exact canary and verify cleanup.
An orphaned registration remains unresolved even when the payload self-expires.

### 4. Accept a current run

Accept a run only when:

- trigger evidence is newer than the request or baseline and is specific to
  the configured non-demand trigger;
- the issued nonce and every available native invocation or activity identifier
  bind to the same event chain and receipt;
- executable, cwd, identity, domain, and an independently computed effective
  definition fingerprint match the target;
- the wrapped payload outcome was known before atomic receipt publication, the
  wrapper then exited preserving that status, and the observer confirmed later
  scheduler terminal evidence;
- every available scheduler-native terminal result, payload exit, and receipt
  outcome agree; unavailable native results are reported rather than invented;
- the P4 assertion is checked separately when effects matter.

A stale file, self-declared scheduler field, heartbeat, loaded state, generic
start event, or old green result is not current-run proof.

### 5. Repair and re-prove

Before an authorized repair, export or copy the exact current definition and
record enabled state. Make the smallest runtime declaration change, then rerun
only the invalidated proof levels. Preserve failure evidence before reset or
cleanup erases it.

## Safety Boundaries

- Do not register, enable, disable, delete, reschedule, or live-trigger a job
  without exact-target authority.
- Use a no-op, dry-run, or isolated canary for deliberate scheduler execution.
- Keep secrets out of definitions, arguments, logs, receipts, and examples.
- Keep raw definitions and status in restrictive local artifacts; put only
  redacted structural evidence or digests in model context and reports.
- Do not replace the scheduler or install a monitoring service as a diagnostic
  shortcut.
- Keep optional notification failures separate from the primary process exit.
- Never claim exactly-once behavior; require idempotency where retries or
  overlap can create effects.

## Completion

Report the bound target and domain, highest independently proven level, trigger
origin, runtime differences, freshness and correlation evidence, functional
effect, any authorized change and rollback, cleanup state, and remaining gap.
If a canary was used, report its evidence separately from the production job.
