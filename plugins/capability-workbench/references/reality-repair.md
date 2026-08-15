# Reality Repair Reference

Use this after `capability-reality-repair` triggers and the hot path needs deeper source-selection or example guidance.

## Source Selection

Prefer editing these surfaces, in order:

1. Canonical plugin or skill source repository, or local marketplace source.
2. Installed personal skill source under the active agent home.
3. MCP server source, tool schema, adapter code, or generated manifest source.
4. Shared scripts and validators used by the skill/plugin.
5. Cache copies only when they are the only active source available.

If a cache copy must be edited, keep searching for the upstream source and state the limitation. If multiple artifacts repeat the same false claim, update all reachable copies that the agent may load.

## Priority And Deferral

Keep the user's requested outcome primary. Repair in the same turn only when a confirmed capability defect blocks or materially distorts that outcome and the canonical fix is bounded, authorized, and testable. Otherwise finish or safely checkpoint the original task before starting capability maintenance.

Also defer when the canonical source is missing, read-only, externally owned, requires destructive migration, or needs broader authority than the current task provides.

When deferring, record:

- exact false claim;
- proof of current reality;
- source that needs editing;
- patch plan;
- validator or smoke test that should pass afterward.

Do not count a repair handoff as progress on the original task. Keep it small enough that another task can verify the contradiction and start from the named canonical source without rereading the full transcript.

## Bounded Delegation

Use a repair subagent only after the exact false claim, contradictory evidence, canonical source, allowed files, and validation target are explicit. Give it no authority to redesign adjacent capabilities, edit the target product, install or publish artifacts, or broaden the repair. The parent reviews the result and resumes or completes the original task.

## Examples

- A skill documents a `gh` flag that the installed CLI rejects. Verify with `gh --help`, patch the skill or wrapper, and add a smoke command or tested-version note.
- A plugin helper validates marketplace visibility but reads the wrong config table. Reproduce the false pass/fail, fix the parser or documented contract, and run the install check again.
- A skill script expects a JSON field that no longer exists. Update the script, fixture, and any skill text that still describes the old field.
- An MCP tool description says a parameter is optional while the schema requires it. Repair the schema or description at the source, reinstall/restart if needed, and test a matching call.

## Rollback

Keep repairs narrow. If the fix breaks validation, restore the previous source artifact, keep the proof record, and leave a precise blocker instead of broadening the patch without evidence.
