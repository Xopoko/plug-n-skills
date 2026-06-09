# Install Scope

Use this reference whenever a request creates, synthesizes, improves, installs, or packages agent skills, plugins, MCP capabilities, or mixed capability packs.

## Core Rule

Separate source delivery from activation. Creating or improving a capability means writing the artifact to the selected source surface and validating it. Installing, cache-refreshing, or mutating global agent config happens only when the user asks for installed/global use, the mode is explicitly install/update, or the contract sets `install_required=true`.

## Surface Selection

Choose one delivery surface:

- `repo-local`: current or named repository is the source of truth for plugin/skill artifacts.
- `global-codex`: requested output is an installed personal/global Codex capability or a local marketplace source without another selected repository.
- `workspace-snapshot`: partial synthesis, temporary draft, or source-only snapshot that is not the final artifact.
- `reference-only`: analysis, vetting, or recommendation with no created artifact.

Use `repo-local` when any applicable source selects the repository:

- latest user message says current repo/project/path, names a repository destination, asks for source work, or says not to install globally;
- repo instructions such as `AGENTS.md` define plugin/skill authoring in the current repository;
- workspace profile shows a plugin/skill source tree and the task is to create or improve those artifacts.

Use `global-codex` when the user asks to install, update an installed agent capability, make it globally visible/usable, or no repository source surface is selected and the requested artifact is meant for the user's personal marketplace or skills directory.

Dirty git state, a merely local candidate path, or the target feeling project-specific is not enough by itself. The evidence must connect the request to a repository source surface or to installed/global activation.

## Scope Contract

For Workbench synthesis, create `<output-dir>/install-scope.json` and validate it:

```bash
python3 ../../scripts/synthesis/install_scope_gate.py --template > <output-dir>/install-scope.json
python3 ../../scripts/synthesis/install_scope_gate.py <output-dir>/install-scope.json
```

Before claiming a complete installed result, validate final state:

```bash
python3 ../../scripts/synthesis/install_scope_gate.py <output-dir>/install-scope.json --final
```

A complete output requires the final artifact to be delivered to the validated surface. If `install_required=true`, final validation also requires installed/cache-backed proof. If the result remains a workspace snapshot, report it as `workspace-snapshot`, `reference-only`, or partial, not as delivered.

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

- validated install scope;
- exact source, installed path, or marketplace path;
- validation commands and results;
- whether anything was installed/cache-refreshed and whether the agent needs a new session or restart to load it;
- explicit reason for the chosen surface.
