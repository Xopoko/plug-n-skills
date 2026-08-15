---
name: capability-reality-repair
description: >-
  Repair stale or false skill/script/plugin/MCP contracts when commands,
  schemas, paths, outputs, dependencies, install state, connector guidance,
  validators, or docs disagree with live reality.
---

# Capability Reality Repair

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path suffix) for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this skill folder's `../..`.

Treat a false skill, plugin, script, or MCP contract as a capability defect. The target is not to work around the bad instruction once; the target is to repair the source that made the agent wrong so the same failure does not recur, while keeping the user's requested outcome primary.

## Trigger

Use this when current work produces direct evidence of a mismatch between a capability artifact and reality:

- A `SKILL.md`, reference, `agents/openai.yaml`, plugin manifest, MCP schema, tool description, or connector instruction names a false command, flag, field, path, dependency, output shape, install state, auth flow, API contract, or workflow.
- A bundled script, validator, installer, generator, CLI wrapper, or helper gives false guidance, crashes on its documented input, parses the wrong output, uses a stale schema, or succeeds while checking the wrong thing.
- A plugin or MCP advertises capabilities that are missing, wired differently, not visible to the host agent, or only present in a cache copy while the canonical source differs.
- The agent has to invent a workaround because the capability instructions or helper code are inaccurate.
- The discrepancy was found while doing unrelated work. The trigger does not require the user to explicitly ask for maintenance.

Do not trigger on ordinary target-project bugs, third-party outages, missing user credentials, or ambiguous suspicions until the capability artifact itself is shown to be wrong or materially misleading.

## Priority Rule

The user's requested outcome remains primary.

Repair in the same turn only when a confirmed capability defect blocks or materially distorts that outcome and the canonical fix is bounded, authorized, and testable. Do not count capability maintenance as progress on the original task.

Otherwise finish or safely checkpoint the original task, preserve the exact contradiction, and leave a precise repair handoff. Also defer when the canonical source cannot be found, the source is read-only or externally owned, or the repair would require destructive migration or broader authority.

## Repair Loop

1. Identify the bad contract: exact artifact, claim, script behavior, schema, or helper output that contradicted reality.
2. Prove current reality with direct evidence: `--help`, `--version`, source, generated schema, manifest, installed config, validator output, minimal reproducer, official docs, or live tool output.
3. Find the editable source of truth, not only a generated cache. For installed plugins, locate the source path, patch source, then refresh the install/cache state and probe runtime discovery separately when needed.
4. Patch every reachable artifact that repeats the false claim: skill text, references, scripts, schemas, manifests, examples, expected outputs, router entries, and validators.
5. Add recurrence protection: validator, unit test, fixture, schema check, smoke command, install/cache check, runtime-discovery probe, or explicit validation command.
6. Validate the repaired surface and resume the original task from the corrected contract.

## Boundaries

- Do not change target product code merely to satisfy a false capability instruction.
- Do not add historical apology text like "this used to be wrong" inside the skill. Make the artifact simply correct.
- Do not create broad rewrites when a focused contract update and regression check solve the problem.
- Do not install unknown third-party code or run opaque candidate scripts just to compare behavior.
- Do not silently ignore a capability defect because the original user request was about something else.
- Do not spawn a repair agent from suspicion alone. Delegate only after the false claim, contradictory evidence, canonical source, allowed scope, and validation target are explicit.

## Done

The repair is complete only when:

- the false or broken capability source has been updated;
- the live behavior or authoritative proof is recorded in work notes or final response;
- the relevant validator, script test, smoke command, install/cache check, or runtime-discovery probe passed or the blocker is explicit;
- the original task can continue without relying on the stale contract.

A deferred repair is not complete. Report its exact evidence, source, smallest patch, and validation target without presenting maintenance as progress on the original task.

Use `$PLUGIN_ROOT/references/reality-repair.md` for source-selection order, repair examples, and defer/rollback details.
