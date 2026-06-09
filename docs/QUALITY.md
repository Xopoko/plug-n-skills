# Quality Gates

The repository validator is the minimum bar before publishing changes:

```bash
python3 scripts/validate-repository.py
```

It checks:

- every required plugin directory exists;
- every plugin has both Codex and Claude manifests;
- each Codex manifest passes the plugin validator;
- manifest names match directory names;
- required metadata such as license and repository fields is present;
- the root Claude marketplace lists the complete plugin set;
- source text contains no Cyrillic characters in public-facing files;
- source text does not leak machine-specific home paths;
- generated artifacts and common secret patterns are absent.

The validator intentionally skips local-only ignored workspaces such as
`.agents/`, `research/`, `skill-synthesis/`, `docs/superpowers/`, and dependency
folders. If material from those folders should become public source, distill it
into tracked docs, references, scripts, or tests first.

## Manual Review Checklist

- Does the plugin name match the folder and both manifests?
- Does the skill trigger language describe when to use the capability?
- Are long references outside the hot `SKILL.md` path?
- Are scripts deterministic and runnable from the documented working directory?
- Are external APIs documented with fallback behavior?
- Does the install script report every local/global path it writes?
- Does the README describe the actual install flow rather than a stale local
  setup?
- Did the change avoid generated marketplaces, caches, dependency folders,
  bytecode, and local absolute paths?
