---
name: codex-deferred-completion
description: Use when a long-running executable already publishes an atomic JSON terminal receipt and repeated native-session or remote-status polling would otherwise consume model turns; reserve a private receipt, launch the producer directly, and await it once.
---

# Codex Deferred Completion

Use this skill only for a non-interactive command with a producer-owned terminal
receipt. The MCP server coordinates receipt creation and validation; it never
launches, wraps, signals, or kills the command. Native Codex exec therefore
remains the command's sandbox and approval boundary.

This MCP requires POSIX safe-open support and is intended for current macOS and
Linux hosts. On another host, use one bounded native wait or yield.

## Preconditions

Inspect the producer's local `--help` and source-backed receipt contract first.
Proceed only when all of these are true:

- the command accepts an absolute result path through a native flag;
- it atomically replaces a mode-`0600` JSON file at that path;
- the receipt has the fixed envelope fields `schema`, `outcome`, `exitCode`,
  `startedAt`, `completedAt`, `elapsedSeconds`, and `transitionCount`;
- a known JSON Pointer inside the receipt equals the reserved result path;
- stable job identity can be checked with bounded JSON Pointer assertions;
- the command is non-interactive and its live output is not needed for a
  decision.

Do not invent a receipt adapter, shell wrapper, or nested subprocess merely to
use this skill. If the producer lacks a native receipt, leave the command direct
and use one long native wait.

## Reserve The Contract

Call `reserve_completion_receipt` immediately before launch. Supply:

- a compact `label` carrying the stable operation identity;
- the exact producer `schema`;
- `terminalOutcomes`, mapping each terminal outcome to its exit code;
- `resultPathPointer`, the JSON Pointer that must equal the server-owned path;
- bounded `assertions` for stable fields such as job id, project, or head SHA;
- the producer timeout, launch grace, and bounded completion-overrun grace.

Assertions without `outcomes` apply to running and terminal receipts. Use
conditional assertions when a field exists only for selected outcomes:

```json
{
  "label": "release-watch project!42 @0123456789abcdef",
  "schema": "example.release-watch-result.v1",
  "terminalOutcomes": {"ready": 0, "failed": 2, "timeout": 3},
  "resultPathPointer": "/request/artifacts/result",
  "assertions": [
    {"pointer": "/request/job", "value": 42},
    {
      "pointer": "/lastReport/headSha",
      "value": "0123456789abcdef",
      "outcomes": ["ready", "failed"]
    }
  ],
  "producerTimeoutSeconds": 7200,
  "launchGraceSeconds": 120,
  "completionGraceSeconds": 300
}
```

The combined deadline must not exceed 21,600 seconds. Launch grace covers the
interval from reservation to the first valid receipt. Producer timeout and
completion grace start when the waiter first observes `running`, so reservation
setup time does not consume the producer's budget.

## One-Wait Workflow

1. Reserve the receipt and keep its `handle` and `resultPath`.
2. Start the real producer directly through native Codex exec. Pass
   `resultPath` using the producer's own receipt flag and use a short initial
   yield only to obtain the native session id.
3. Call `await_completion_receipt` exactly once with the handle.
4. After a terminal result, collect the native exec session exactly once to
   confirm process closure. This is final collection, not polling.
5. Use the producer's durable workspace artifacts and bounded native failure
   tail as evidence. The private coordination receipt is consumed after
   validation and is not durable proof.

## Safety Rules

- Never pass command text, argv, environment, PID, session id, signal, cwd,
  workspace path, or an arbitrary receipt path to the MCP tools. They are not
  accepted.
- Bind success to immutable identity fields. For delivery watchers, assert the
  exact job/project identity and head revision on success outcomes.
- Use unique producer-owned durable artifact paths for parallel jobs; the MCP
  result path is already unique.
- Treat `wait_timeout` with stage `launch` as missing startup evidence and stage
  `producer` as missing terminal evidence. Neither proves the producer stopped.
- Cancellation stops only the waiter. It never signals the producer and does
  not consume the reservation.
- Do not layer `write_stdin`, process, log-tail, agent, or remote-status polling
  loops around an active receipt wait.
- If either MCP tool is unavailable, use one bounded native wait or yield.

## Completion Standard

Report the direct native command, its cwd and sandbox/approval context, the
reserved label, validated terminal outcome and exit code, the producer's
durable artifact paths, the final native session state, and explicit
blocked/unverified items. A receipt proves producer completion only; it does not
replace the producer's domain-specific proof contract.
