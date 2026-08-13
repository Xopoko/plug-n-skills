# Architecture

This repository separates plugin source from local runtime state. The Git tree
contains installable source packages; ChatGPT/Codex, Claude, and Cursor
generated state is derived from those packages.

## Source Of Truth

Across machines, a synchronized clone of this Git repository is the canonical
editable source. Changes flow from `plugins/<name>` through validation and Git
to each host's installation. Host-local marketplaces, caches, authentication,
and selection/exclusion policy are derived runtime state; they do not flow back
into source and must not be edited as a substitute for a repository change.

`plugins/<name>` is the editable source tree for a plugin. A typical plugin
contains:

- `.codex-plugin/plugin.json` for shared ChatGPT/Codex metadata;
- `.claude-plugin/plugin.json` for Claude Code metadata;
- `skills/` with `SKILL.md` entrypoints;
- `references/` for long contracts, source ledgers, scorecards, or runbooks;
- `scripts/` for deterministic helpers;
- `assets/` for icons and other media.

The root `.claude-plugin/marketplace.json` is the published Claude Code
marketplace for the collection and a compatibility discovery surface for
Codex when no repository-local `.agents/plugins/marketplace.json` exists.
Cursor has no plugin marketplace; `scripts/install-cursor-skills.py` copies
plugin skills into Cursor's global skills directory instead.

## Codex Install Model

The [OpenAI plugin documentation](https://developers.openai.com/plugins/build/plugins)
defines native `plugin marketplace`, `plugin list`, `plugin add`, and
`plugin remove` commands. A fresh clone can use the published marketplace
directly:

```bash
codex plugin marketplace add .
codex plugin list --available --json
codex plugin add capability-workbench@xopoko-plug-n-skills
```

The repository helper is the deterministic validation, bulk-refresh,
host-selection, and legacy-ID migration layer. It keeps the source of truth in
this checkout and registers a generated marketplace named `local`:

```bash
python3 scripts/install-codex-plugins.py
```

The helper writes `.agents/plugins/marketplace.json` as local generated state,
configures Codex so `[marketplaces.local]` points at the repository root, and
delegates normal installs to native `codex plugin add`. Its deterministic
config/cache materializer remains the compatibility fallback for older CLIs
and explicit marketplace/state-path recovery. The active Codex home is `$CODEX_HOME` when
nonempty, otherwise `~/.codex`; a configured home is canonicalized and must
already be a directory.

The generated `.agents/` directory is intentionally ignored by Git. It belongs
to the local machine, not to the published source.

## Standalone First-Party Plugin Model

Large domain systems can keep a separate public repository while remaining a
first-party part of this collection. `first-party-plugins.lock.json` is the
only activation-capable federation surface. Each entry binds the GitHub
repository to a full commit and tree, both manifest hashes, version, license,
selection policy, and a repository-owned receipt. The receipt supplies the
offline skill/token/dashboard metadata and binds its catalog icon snapshot by
SHA-256.

Default Codex and Cursor bulk installs select only local `plugins/` sources.
An exact `--plugin NAME` may select either kind; `--include-first-party` adds
only catalog entries with `selection.default=true`. Dry runs never fetch or
materialize. Check-only runs are implicitly offline and require the exact
verified source cache. Normal explicit selection materializes into the ignored
`.agents/first-party-sources/NAME/COMMIT` cache before host installation.

Claude Code uses the published marketplace directly. Local entries use
`./plugins/NAME`; standalone entries use the official GitHub source object with
the same full commit in `sha`. See [Standalone Plugins](STANDALONE_PLUGINS.md).

```mermaid
flowchart LR
  A["Standalone canonical repository"] --> B["Immutable commit and tree"]
  B --> C["Root lock and receipt"]
  C --> D["Verified local source cache"]
  D --> E["Codex or Cursor install"]
  C --> F["Claude GitHub source with sha"]
```

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

## Capability-Bound Tool Access

Domain workflows declare the operations they require instead of requiring one
CLI, MCP server, connector, or SDK. A deterministic selector validates a
task-local adapter inventory and emits a typed execution plan. Installation,
reachability, authentication, authorization, and operation support remain
separate states; an advertised tool is not automatically an eligible executor.

The first native implementation lives in `git-workflows`. It can bind GitHub or
GitLab operations to a host-exposed MCP tool, connector, authenticated CLI API
surface, or direct API client when that adapter proves the required semantics.
Provider-specific pagination, identity, exact-head, readback, and mutation
rules remain explicit. An opaque common-denominator adapter must degrade to a
read-only or report-only mode instead of claiming parity.

```mermaid
flowchart LR
  A["Workflow requirements"] --> B["Adapter inventory"]
  B --> C["Deterministic capability gate"]
  C --> D["Bound execution plan"]
  D --> E["Invocation receipt"]
  C --> F["Degraded or report-only result"]
```

The selector never installs tools, starts login flows, or probes a write by
performing it. Those effects remain explicit user-authorized lifecycle steps.
After an ambiguous mutation result, adapters cannot be switched to retry the
write; only authoritative readback may recover a unique receipt.

## Technology Evidence Model

`technology-intelligence` uses a four-entity decision graph:

- capabilities name the needed outcome without choosing a product;
- technologies are candidate products, frameworks, protocols, or patterns;
- interfaces are documented CLI, SDK, WASM, MCP, API, app, or skill access
  contracts exposed by a technology;
- runtime inventories are caller-supplied, short-lived facts about what is
  installed, enabled, authenticated, healthy, and callable in one environment.

That graph is wrapped by a separate evidence envelope: source snapshots record
provenance, editions, clocks, methodology, rights, and known bias; observations
preserve dated claims; reviewed assessments apply decision profiles and hard
gates. A catalog interface is therefore not proof of runtime availability.

Evidence refreshes may produce a proposed diff, but they never silently change
an adoption disposition. Published recommendations remain versioned and
reviewable. Runtime inventory is short-lived input and is never committed as a
universal fact. The plugin uses local deterministic queries and validators; it
does not require an MCP server or a network request for ordinary use.

## Plugin Identity Migration

`gitlab-review`, `stacked-delivery`, and `git-worktree-safety` were consolidated
into `git-workflows`. Their focused skill contracts remain independently
triggerable inside the new package. The Codex and Cursor installers accept each
legacy plugin name as an alias for `git-workflows`. A targeted Codex
`git-workflows` install replaces legacy marketplace entries and reports old
enabled config, cache, and copied-source residuals without removing them.
Existing host state requires an explicit install, disable, or uninstall
lifecycle action and is never changed by source validation.

`codex-cli`, `claude-code`, and `scheduled-automation` were consolidated into
`agent-harness`. Their focused skills, MCP identities, scripts, references, and
runtime-proof contracts remain inside the new package. The Codex and Cursor
helpers canonicalize all three legacy package names to `agent-harness`,
deduplicate mixed legacy/canonical selections, and apply exclusions at the
canonical target. A targeted migration removes only the matching repo-owned
marketplace entries; config, cache, and copied-source residuals remain
read-only findings until an explicit host lifecycle action removes them.
The `agent-harness-engineering` and `agent-harness-evaluation` skills and their
exclusive contracts moved from Capability Workbench into the same target;
Capability Workbench remains a separate install for capability lifecycle work.

General plugin retirement follows the same source/runtime boundary. During an
install write, the Codex installer removes a generated marketplace entry only
when it uses the standard repo-owned `./plugins/<name>` source shape and the
canonical checkout no longer contains that plugin directory. Unknown custom
entries are preserved. Enabled config, cache, and copied-source residuals are
read-only findings until the host's explicit lifecycle removes them.

Claude Code has no repository-defined alias. Each migration is an explicit
install of the canonical ID, followed by explicit uninstall of that group's old
IDs at the same scope and a plugin reload. Cursor has no plugin marketplace;
its aliases select the consolidated source while unchanged focused skill names
converge into the same flat skill destinations. Repository helper aliases are
selection conveniences, not runtime plugin aliases.

For Claude Code, the Agent Harness migration is therefore explicit:

```text
/plugin install agent-harness@xopoko-plug-n-skills
/plugin uninstall codex-cli@xopoko-plug-n-skills
/plugin uninstall claude-code@xopoko-plug-n-skills
/plugin uninstall scheduled-automation@xopoko-plug-n-skills
/reload-plugins
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
  B --> C["Codex native CLI: register published marketplace"]
  B --> D["Repository helper: generate local .agents marketplace"]
  C --> E["Codex: install or remove selected plugins"]
  D --> F["Codex: validate and refresh selected cache entries"]
  B --> G["Claude: root marketplace points at plugin source"]
  H["Edit external dependency lock"] --> I["Validate pin, policy, and review report"]
  I --> B
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
