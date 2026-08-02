# Maintenance Sweep Targets And Consolidation Criteria

Companion reference for the `code-maintenance-audit` skill.

## What To Check

- Unused imports, variables, constants, types, structs/classes, functions, hooks, components, extensions, fixtures, mocks, and test helpers.
- Old branches, flags, adapters, wrappers, callbacks, props, route cases, configuration entries, or conditionals that the new code replaced.
- Duplicate or almost-duplicate UI components, view models, presenters, reducers, services, validators, formatters, mappers, request builders, and tests.
- Dead files left after renames or migrations, including stale snapshots, generated references, assets, and barrel exports.
- Debug-only leftovers such as logs, temporary names, TODO scaffolding, commented-out code, fake data, forced states, and disabled assertions.
- Repeated logic that could be expressed through an existing local helper, base component, parameter, composition slot, or small shared function.

## Consolidation Criteria

Consolidate similar code only when the shared shape is real:

- There are at least two concrete implementations with mostly the same responsibility, lifecycle, data flow, error handling, and user-visible behavior.
- The differences can be represented clearly with parameters, composition, small strategy objects, or existing local patterns.
- The resulting abstraction has a specific domain name and is easier to read than the copies.
- The change deletes more complexity than it adds.
- Tests, previews, stories, or call-site checks can verify the affected variants.

If any criterion fails, keep the duplication and record the observation as a deferred finding. When the copies differ in business meaning rather than mechanics, route to `untangle-business-logic`.
