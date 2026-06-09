---
name: skill-installer-vetter
description: Find, list, vet, install, or update agent skills from curated catalogs, GitHub repo paths, local folders, or user-provided references. Use when installation must be preceded by provenance, safety, dependency, and capability checks.
---

# Skill Installer Vetter

Install only after provenance and safety are clear. Discovery candidates are not executable until the user requested installation and the vetting result supports it.

## Source Types

- Curated OpenAI skills: list or install with bundled GitHub helpers.
- Explicit GitHub repo/path: inspect source, pin ref when possible, then install.
- Local folder: treat as a source candidate; audit and copy only if it is a valid skill and the destination is clear.
- Candidate reference in synthesis: inspect only; do not install during evaluation.

For explicit skill installation, use the active agent's skills dir unless the user or repo instructions select another destination — Codex: `${CODEX_HOME:-$HOME/.codex}/skills/<skill-name>`, Claude: `${CLAUDE_HOME:-$HOME/.claude}/skills/<skill-name>`. Detect the active agent with `scripts/agent_target.py`. For repository source work, audit and validate the skill in place instead of copying it globally unless installation was requested.

## List Curated Skills

```bash
python3 ../../scripts/install/list-skills.py
python3 ../../scripts/install/list-skills.py --format json
python3 ../../scripts/install/list-skills.py --path skills/.experimental
```

These commands use GitHub network access. If unavailable, report the error and continue with local inventory:

```bash
python3 ../../scripts/capability_inventory.py --query "<topic>" --json
```

## Vet Before Install

For every candidate, record:

- source path or URL and ref/commit if known;
- readable files and frontmatter;
- scripts, dependencies, network calls, install commands, writes, deletes, and secrets access;
- whether risky behavior is required, optional, example-only, advisory, or hidden;
- capability fit and project-specific assumptions.

Use:

```bash
python3 ../../scripts/synthesis/audit_skill_candidate.py <skill-dir> --output candidate-audit.json
python3 ../../scripts/skill/quick_validate.py <skill-dir>
```

Reject or isolate candidates that require paid APIs, API keys, telemetry, hidden network dependencies, unsafe shell execution, obscure installers, or unrelated infrastructure.

## Install From GitHub

Only run after user intent is clear:

```bash
python3 ../../scripts/install/install-skill-from-github.py --repo <owner>/<repo> --path <path/to/skill>
python3 ../../scripts/install/install-skill-from-github.py --url https://github.com/<owner>/<repo>/tree/<ref>/<path>
```

Private repos may use existing git credentials or optional `GITHUB_TOKEN`/`GH_TOKEN`. Never print or copy token values.

## Install From Local Folder

1. Validate the source with `quick_validate.py`.
2. Choose destination from the install-scope contract: agent global skills dir for installed personal skills, or a repo/plugin source path for source work.
3. Abort if destination exists unless the user requested an update.
4. Copy with metadata preserved and report exact source, destination, and whether the agent needs a new session/restart to load the skill.

## Update Existing Skill

Read current `SKILL.md`, inspect git status or existing modifications, and preserve user work. Prefer patching in place with a small diff over replacing the whole folder. Re-run validation and tell the user whether the agent must restart to pick up changes.
