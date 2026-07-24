# Git Worktree Safety Plugin

Git Worktree Safety diagnoses an expected worktree path or convenience symlink
that has disappeared, become stale, or broken. It proves whether one existing
registered checkout still owns the exact live branch before allowing any
pointer repair.

## Skill

- `git-worktree-recovery`: classify commit retention, validate one exact clean
  registered replacement, inspect a convenience symlink with raw paths omitted
  from JSON, and optionally repair only that verified broken symlink.

The bundled standard-library helper defaults to a host-neutral read-only audit.
Its repair mode is separately gated by an audit fingerprint, the exact old raw
symlink target, an explicit replacement target, and `--apply`. Repair is
available only on POSIX runtimes that expose the required directory-relative
stat, readlink, symlink, unlink, and atomic-replace primitives; unsupported
hosts remain read-only. The helper does not create, remove, prune, repair, move,
or unlock Git worktrees; restore refs; change branches; check out or reset
files; or perform stack operations.

Runtime requirements are Python 3.10 or newer and a Git build that supports
`worktree list --porcelain -z --expire=now` and
`rev-parse --show-object-format`. The helper feature-probes these surfaces
instead of assuming a Git version.

## Validation

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/skill/quick_validate.py \
  plugins/git-worktree-safety/skills/git-worktree-recovery
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py \
  plugins/git-worktree-safety
python3 -m unittest discover -s plugins/git-worktree-safety/tests -p 'test_*.py'
```
