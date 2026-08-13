# Contributing

This repository is maintained as the publication-ready canonical source tree
for Plug'n Skills across machines. Contributions should keep the plugin packs
installable, readable, and portable: edit and validate a synchronized clone,
propagate source through Git, then refresh host-local installs instead of
editing generated marketplaces or runtime caches.

## Standards

- Write user-facing content in English.
- Keep `.codex-plugin/plugin.json` valid and aligned with the folder name.
- Keep generated artifacts, caches, bytecode, and local machine paths out of commits.
- Prefer small focused skills with references for long contracts, ledgers, and evidence.
- Add or update validation when a plugin adds scripts, external sources, or installation behavior.
- Register external agent-skill sources in `external-dependencies.lock.json`
  with a full commit, Git tree, license boundaries, and public review report.
  Lock entries are reference-only and must not add install hooks.

## Local Workflow

```bash
python3 scripts/validate-repository.py
python3 scripts/external-dependencies.py validate
python3 scripts/install-codex-plugins.py --dry-run
python3 scripts/install-codex-plugins.py --plugin <name>
```

Use the dry run before installing so marketplace/config changes are visible before they are written.
For an external dependency pin change, also run
`python3 scripts/external-dependencies.py verify-source <dependency-id>`.
