# Architecture

This repository separates plugin source from local runtime state. The Git tree
contains installable source packages; Codex, Claude, and Cursor generated
state is derived from those packages.

## Source Of Truth

`plugins/<name>` is the editable source tree for a plugin. A typical plugin
contains:

- `.codex-plugin/plugin.json` for Codex metadata;
- `.claude-plugin/plugin.json` for Claude Code metadata;
- `skills/` with `SKILL.md` entrypoints;
- `references/` for long contracts, source ledgers, scorecards, or runbooks;
- `scripts/` for deterministic helpers;
- `assets/` for icons and other media.

The root `.claude-plugin/marketplace.json` is the published Claude Code
marketplace for the collection. Cursor has no plugin marketplace;
`scripts/install-cursor-skills.py` copies plugin skills into Cursor's global
skills directory instead.

## Codex Install Model

Codex local plugins are loaded through a marketplace named `local`. The default
repository helper keeps the source of truth in this checkout:

```bash
python3 scripts/install-codex-plugins.py
```

The helper writes `.agents/plugins/marketplace.json` as local generated state,
configures Codex so `[marketplaces.local]` points at the repository root, and
materializes cache entries below the active Codex home
(`$CODEX_HOME` when nonempty, otherwise `~/.codex`). A configured home is
canonicalized and must already be a directory; explicit config/cache paths
remain the recovery override.

The generated `.agents/` directory is intentionally ignored by Git. It belongs
to the local machine, not to the published source.

For compatibility with older local layouts, the installer can still copy source
to `~/plugins/<name>`:

```bash
python3 scripts/install-codex-plugins.py --global-source-root ~/plugins
```

That compatibility mode is explicit; it is not the default repository workflow.

## External Dependency Model

`external-dependencies.lock.json` records external agent-skill sources that are
relevant to first-party capability work but are not part of the published
plugin tree. Each entry binds provenance to a full Git commit and tree, names a
first-party reviewer, records license boundaries and a review report, and
declares an enforced policy.

Schema version 1 supports only `reference-only` dependencies. The trusted
repository validator rejects mutable refs, unknown executable fields, automatic
installation, execution, vendoring, unsafe paths, missing reviewers, and missing
review reports. Lock validation is offline and never fetches or runs candidate
code. The separate `verify-source` command performs one read-only GitHub API
lookup per selected dependency and proves that each pinned commit resolves to
its declared Git tree.

The lockfile is deliberately separate from Codex and Claude manifests because
neither host manifest provides a portable external Agent Skills dependency
contract. Codex, Claude Code, and Cursor installers ignore the lockfile. A
future activation flow must be designed and reviewed separately; changing a
lock entry alone cannot activate external code.

```mermaid
flowchart LR
  A["Pinned external source"] --> B["Offline lock validation"]
  B --> C["Reference-only review"]
  C --> D["Optional native distillation PR"]
  D --> E["Normal plugin validation and install"]
```

## Claude Code Install Model

Claude Code uses the root marketplace:

```text
/plugin marketplace add Xopoko/plug-n-skills
/plugin install capability-workbench@xopoko-plug-n-skills
```

Each marketplace entry points to `./plugins/<name>`, where Claude reads that
plugin's `.claude-plugin/plugin.json` and shared `skills/` directory.

## Flow

```mermaid
flowchart LR
  A["Edit plugins/<name> source"] --> B["Validate repository"]
  B --> C["Codex: generate local .agents marketplace"]
  C --> D["Codex: refresh plugin cache"]
  B --> E["Claude: root marketplace points at plugin source"]
  F["Edit external dependency lock"] --> G["Validate pin, policy, and review report"]
  G --> B
```

## Publication Boundary

Commit:

- plugin source under `plugins/<name>/`;
- the inert external dependency lock and its public review reports;
- root documentation and validation scripts;
- `.claude-plugin/marketplace.json`;
- plugin manifests, references, scripts, tests, and assets.

Do not commit:

- `.agents/`;
- `~/.codex/plugins/cache/...`;
- bytecode, dependency folders, build output, or temporary files;
- local research corpora or synthesis scratch folders unless distilled into
  public source documentation.
