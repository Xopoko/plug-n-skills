# Standalone First-Party Plugins

`first-party-plugins.lock.json` is the repository's activation-capable catalog
for reviewed first-party plugins that live in separate GitHub repositories. It
is deliberately separate from `external-dependencies.lock.json`: external
dependencies remain inert evidence, while a catalog entry may be materialized
or checked out only after all pinned-source gates pass.

Every entry binds a publisher, repository, full commit and Git tree, both
manifest byte hashes, the plugin version, MIT license, selection default, and a
repository-owned receipt. Receipts also bind the skill inventory, reference and
script file counts, publication-time token rollups, icon metadata, and the hash
of the small catalog-owned icon snapshot used by the offline README dashboard. Mutable
refs and abbreviated hashes are invalid. Token rollups are informational
snapshots; commit, tree, manifest, inventory, and source validation remain the
security gates.

## Commands

Run commands from this checkout:

```text
python scripts/first-party-plugins.py validate
python scripts/first-party-plugins.py list
python scripts/first-party-plugins.py verify-source [NAME ...]
python scripts/first-party-plugins.py receipt NAME --source PATH
python scripts/first-party-plugins.py materialize NAME [--offline] [--cache-root PATH]
python scripts/first-party-plugins.py status [NAME ...] [--cache-root PATH]
python scripts/first-party-plugins.py checkout NAME --dest PATH [--cache-root PATH]
```

`receipt` reads only the exact committed Git blobs from a matching local
checkout, calculates per-skill and aggregate token snapshots, and refreshes the
catalog icon snapshot. It validates the generated receipt but does not publish
or modify the standalone repository.

Materialization fetches the exact commit into a temporary Git repository,
checks commit and tree identity before checkout, rejects submodules and symbolic
links, validates both manifests and their hashes, runs the repository's generic
plugin validator, and atomically publishes the result below
`.agents/first-party-sources/NAME/COMMIT`. `--offline` never contacts a remote
and succeeds only for an already valid cache entry.

`checkout` creates a detached exact-commit workspace. A nonempty destination is
accepted only when it already matches every pin and receipt. Successful new
checkouts may be recorded in the ignored machine-local
`.agents/first-party-workspaces.json` file.

The resolver never executes source-owned scripts, hooks, installers, or remote
instructions. Catalog validation itself is local and read-only.

## Installation selection

Both repository installers default to every plugin still authored under
`plugins/` and do not fetch standalone sources implicitly. A standalone plugin
can be selected by name with `--plugin NAME`. `--include-first-party` adds only
catalog entries whose `selection.default` flag is true. `--exclude-plugin`
applies after either selection route and works for local and standalone names.

```text
python scripts/install-codex-plugins.py --plugin career
python scripts/install-cursor-skills.py --include-first-party
python scripts/install-codex-plugins.py --include-first-party --exclude-plugin build-swift-apps
```

`--dry-run` validates the local catalog and reports the pinned plan without
fetching, materializing, or writing. `--check-only` is implicitly offline and
requires a valid existing pinned-source cache. `--offline` applies the same
no-fetch rule to a normal install while still permitting the explicitly
requested local install-state writes. For Codex, `--offline` also forces the
deterministic manual cache/config path and never delegates to the native CLI.

Claude Code consumes the same catalog through the root marketplace. Standalone
entries use its official GitHub source object with the full immutable `sha`;
local entries continue to use `./plugins/NAME`.
