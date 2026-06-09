# Contributing

This repository is maintained as the publication-ready source tree for Plug'n Skills. Contributions should keep the plugin packs installable, readable, and portable across machines.

## Standards

- Write user-facing content in English.
- Keep `.codex-plugin/plugin.json` valid and aligned with the folder name.
- Keep generated artifacts, caches, bytecode, and local machine paths out of commits.
- Prefer small focused skills with references for long contracts, ledgers, and evidence.
- Add or update validation when a plugin adds scripts, external sources, or installation behavior.

## Local Workflow

```bash
python3 scripts/validate-repository.py
python3 scripts/install-codex-plugins.py --dry-run
python3 scripts/install-codex-plugins.py --plugin <name>
```

Use the dry run before installing so marketplace/config changes are visible before they are written.
