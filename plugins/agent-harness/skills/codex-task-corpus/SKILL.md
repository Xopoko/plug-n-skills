---
name: codex-task-corpus
description: Build bounded cross-session Codex task corpora for last-N chat audits, recurring-work retrospectives, context recovery, and capability-gap evidence. Excludes single-rollout forensics, live supervision, and automatic skill edits.
---

# Codex Task Corpus

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path
suffix) for the plugin root. Set it once: use the host's plugin-root variable
when defined, otherwise the absolute path of this plugin's root directory.

Use this skill when the question spans many persisted Codex tasks: the newest
`N` chats, repeated work or failure patterns, cross-task context recovery, or a
traceable capability-gap audit. Use `codex-log-reader` for one exact task and
`codex-thread-supervisor` for a live task. This workflow gathers evidence; it
does not authorize source edits, installation, publication, or telemetry.

Read `$PLUGIN_ROOT/references/codex-task-corpus-contract.md` before filling the
typed ledgers or making an aggregate coverage claim.

## Freeze The Corpus

Create an ignored or otherwise private output directory. The helper reads only
leading session metadata, excludes internal subagent rollouts and the current
`CODEX_THREAD_ID` by default, keeps user-visible forks, and copies no messages
or cwd values:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" corpus \
  --count 150 \
  --cutoff 2026-01-31T18:00:00Z \
  --output-dir ./tmp/codex-task-corpus \
  --json
```

Pass `--exclude-thread-id <id>` when the current task id is known but not
exported in the environment. Use `--cwd <path>` for a project-bounded corpus;
the filter value is not emitted. Exact count is the default contract. If there
are too few eligible tasks, increase `--scan-limit` or fix the filters instead
of silently accepting a smaller sample. Use `--allow-partial` only when the
partial boundary is itself the declared claim.

Local ordering uses rollout modification time. If the claim depends on exact
Codex app ordering, reconcile the app's cursor-paginated task list with the
local index and record that second source in the manifest; do not claim UI
parity from filesystem order alone.

## Review To EOF

1. Freeze the manifest and task index before reading message content.
2. Read every selected task to EOF through the task/thread API when available.
   Record page count and terminal cursor state. With local JSONL, use
   `codex-log-reader` and the active child scope; do not count inherited prefix.
3. Keep one coding row per selected task. Record `complete`, `pending`, or
   `skipped` plus an explicit EOF or skip receipt.
4. Prefer user corrections, verified tool outcomes, external-state checks, and
   demonstrated recoveries over assistant self-description. Separate the
   observation, inference, counterevidence, and proposed discriminator.
5. Write compact summaries and recovery pointers. Do not copy prompts, raw
   excerpts, command payloads, tool outputs, email bodies, private paths,
   personal identifiers, or secret values into the ledgers.
6. Consolidate only after per-task coding is complete. Compare nearby successes
   and the current capability catalog before calling a pattern a missing skill.

Work aggregate-first and drill down in bounded batches. If context pressure
appears, persist the typed ledger and resume from its coverage receipt rather
than rereading completed tasks.

## Independence And Adoption Gate

Count independent user-owned tasks, not transcript rows. Collapse internal
subagents, retries, delegated branches, inherited fork history, and multiple
tasks from the same unresolved incident into one independence group.

A normal reusable candidate needs at least three independent tasks, a current
owner check, counterevidence, a falsifiable hypothesis, and the cheapest useful
discriminator. A direct contradiction of an existing capability contract may
route immediately to `capability-reality-repair`, but preserve the exact
contradictory evidence. Project repetition, ordinary model variance, missing
permission, stale factual reference, and generic task difficulty are not new
capabilities by themselves.

Validate before handing candidates to Capability Workbench:

```bash
python3 "$PLUGIN_ROOT/scripts/codex_log_reader.py" corpus-check \
  ./tmp/codex-task-corpus --final --json
```

`corpus-check` verifies the frozen task index, one-row-per-task coverage, EOF
receipts, independent-task thresholds, handoff coverage, non-authorization,
and common privacy indicators. It cannot prove that summaries are true or that
reviewers are independent; those remain review findings.

## Handoff

Send only validated candidate clusters to Capability Workbench. Preserve
rejected and deferred clusters in the private ledger so the same weak proposal
is not rediscovered. The handoff must name the existing owner or gap, historical
and current artifact state when relevant, evidence pointers, uncertainty,
counterevidence, cheapest discriminator, validation scenario, and residual
safety boundary.

Stop after the requested retrospective or authorized capability change is
complete. Do not turn this workflow into an always-on observer, hosted trace
store, autonomous skill editor, or transcript archive.
