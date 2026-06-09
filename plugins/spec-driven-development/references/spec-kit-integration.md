# GitHub Spec Kit Integration Notes

GitHub Spec Kit is the canonical source for the constitution -> specify -> clarify -> plan -> tasks -> analyze -> implement lifecycle.

Primary upstream reference:

- `https://github.com/github/spec-kit`

Important project surfaces:

- `.specify/memory/constitution.md`
- `.specify/feature.json`
- `.specify/extensions.yml`
- `specs/<feature>/spec.md`
- `specs/<feature>/checklists/requirements.md`
- `specs/<feature>/plan.md`
- `specs/<feature>/research.md`
- `specs/<feature>/data-model.md`
- `specs/<feature>/contracts/`
- `specs/<feature>/quickstart.md`
- `specs/<feature>/tasks.md`

Do not assume a Spec Kit reference checkout is the project being modified. Use upstream and the target repository's own `.specify/` files as references unless the user asks to change Spec Kit itself.

When command files exist in the target repo, follow those command files because extensions, presets, and templates may override upstream defaults.
