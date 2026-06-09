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

## Deferral

Defer only when the canonical source is missing, read-only, externally owned, requires destructive migration, or conflicts with a higher explicit safety or production deadline.

When deferring, record:

- exact false claim;
- proof of current reality;
- source that needs editing;
- patch plan;
- validator or smoke test that should pass afterward.

## Examples

- A skill documents a `gh` flag that the installed CLI rejects. Verify with `gh --help`, patch the skill or wrapper, and add a smoke command or tested-version note.
- A plugin helper validates marketplace visibility but reads the wrong config table. Reproduce the false pass/fail, fix the parser or documented contract, and run the install check again.
- A skill script expects a JSON field that no longer exists. Update the script, fixture, and any skill text that still describes the old field.
- An MCP tool description says a parameter is optional while the schema requires it. Repair the schema or description at the source, reinstall/restart if needed, and test a matching call.

## Rollback

Keep repairs narrow. If the fix breaks validation, restore the previous source artifact, keep the proof record, and leave a precise blocker instead of broadening the patch without evidence.
