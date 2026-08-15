# Install Scope

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

Use this reference whenever a request creates, synthesizes, improves, installs, or packages agent skills, plugins, MCP capabilities, or mixed capability packs.

## Core Rule

Separate source delivery from activation. Creating or improving a capability means writing the artifact to the selected source surface and validating it. Installing, cache-refreshing, or mutating global agent config happens only when the user asks for installed/global use, the mode is explicitly install/update, or the contract sets `install_required=true`.

Choose the delivery surface early, but keep the record proportional:

- Inline scope note: use only when the request is unambiguously `repo-local`, source-only, and `install_required=false`. Record the selected repository evidence, `install_required=false`, and that activation was not requested. Do not create `install-scope.json` for this path.
- Machine-readable ledger: required when scope is ambiguous, the request has global/install/update/activation intent, or the work targets a real machine consumer such as an agent home, marketplace registry, installed plugin source, cache, or machine configuration. Once any condition applies, do not downgrade to an inline note.

The early decision is not a demand for a speculative ledger. Persist the required ledger after destination paths and applicable host policy are stable, close to activation or final delivery. Validate it before any activation or other machine mutation, then run the final gate at delivery.

## Surface Selection

Choose one delivery surface:

- `repo-local`: current or named repository is the source of truth for plugin/skill artifacts.
- `global-agent`: requested output is an installed personal/global capability for the active agent (Codex, Claude, or Cursor; detect with `$PLUGIN_ROOT/scripts/agent_target.py`) or a local marketplace source without another selected repository. `global-codex` is a deprecated alias the gate still accepts.
- `workspace-snapshot`: partial synthesis, temporary draft, or source-only snapshot that is not the final artifact.
- `reference-only`: analysis, vetting, or recommendation with no created artifact.

Use `repo-local` when any applicable source selects the repository:

- latest user message says current repo/project/path, names a repository destination, asks for source work, or says not to install globally;
- repo instructions such as `AGENTS.md` define plugin/skill authoring in the current repository;
- workspace profile shows a plugin/skill source tree and the task is to create or improve those artifacts.

Use `global-agent` when the user asks to install, update an installed agent capability, make it globally visible/usable, or no repository source surface is selected and the requested artifact is meant for the user's personal marketplace or skills directory.

Dirty git state, a merely local candidate path, or the target feeling project-specific is not enough by itself. The evidence must connect the request to a repository source surface or to installed/global activation.

## Inline Source-Only Note

For the unambiguous repo-local source-only path, keep one short inline scope note in the working contract, changelog, or final report. For example:

```text
install scope: delivery_surface=repo-local; install_required=false; evidence=repository instructions select this plugin source tree; activation=not requested; install_scope_ledger=not required
```

This note replaces only `install-scope.json`. It does not waive external discovery, artifact validation, or any other applicable gate.

## Ledger Contract

When the ledger path applies, create `<output-dir>/install-scope.json` after target paths and policy are stable and validate it:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" --template > <output-dir>/install-scope.json
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" <output-dir>/install-scope.json
```

Before activation, validate the ledger. Before claiming final delivery, validate final state:

```bash
python3 "$PLUGIN_ROOT/scripts/synthesis/install_scope_gate.py" <output-dir>/install-scope.json --final
```

A complete ledger-path output requires the final artifact to be delivered to the validated surface. If `install_required=true`, final validation also requires installed/cache-backed proof. If the result remains a workspace snapshot, report it as `workspace-snapshot`, `reference-only`, or partial, not as delivered.

For `repo-local`, `local_request_evidence` should record why the repository is the source surface:

```json
[
  {
    "source": "latest_user_message",
    "quote": "exact user text containing the local-scope request",
    "matched_phrase": "in this repo"
  },
  {
    "source": "workspace_profile",
    "quote": "repo contains plugins/<name>/.codex-plugin/plugin.json and plugins/<name>/skills/",
    "matched_phrase": "plugin source repository"
  }
]
```

## Reporting

Final handoff must state:

- selected install scope and whether it used the inline source-only note or a validated ledger;
- exact source, installed path, or marketplace path;
- validation commands and results;
- whether anything was installed/cache-refreshed and whether the agent needs a new session or restart to load it;
- explicit reason for the chosen surface.
