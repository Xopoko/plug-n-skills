# Git Safety Plugin

Git Safety provides bounded recovery workflows for two independent Git failure
classes: missing worktree pointers and failed ordinary SSH commit signing.
Both skills preserve refs, index, configuration, and worktree content, emit
redacted evidence, and keep mutation authority explicit.

## Skill

- `git-worktree-recovery`: classify commit retention, validate one exact clean
  registered replacement, inspect a convenience symlink with raw paths omitted
  from JSON, and optionally repair only that verified broken symlink.
- `git-commit-signing-recovery`: record the observed parent, staged diff, and
  candidate message after failure; atomically issue one helper authorization
  per exact observed state after verified signer recovery; and check the
  resulting parent, diff, hook policy, signer identity, and residual state.

The worktree helper defaults to a host-neutral read-only audit. Its repair mode
is separately gated by an audit fingerprint, the exact old raw symlink target,
an explicit replacement target, and `--apply`. Repair is available only on
POSIX runtimes that expose the required directory-relative stat, readlink,
symlink, unlink, and atomic-replace primitives; unsupported hosts remain
read-only.

The signing helper fingerprints the post-failure HEAD, staged diff, hook
policy, raw tracked and untracked worktree state, operation markers, object
substitution policy, signing identity, trust material, and fixed system
verification tools. It reads worktree entries directly with bounded no-follow
operations instead of invoking repository-configured content filters. It
writes caller-selected private files plus namespaced baseline and
consumed-token records under the Git common directory. It never changes refs,
index, configuration, hooks, or worktree content; commits; signs; restarts
agents; or authorizes unsigned output.

Runtime requirements are Python 3.10 or newer. Worktree recovery additionally
requires a Git build that supports
`worktree list --porcelain -z --expire=now` and
`rev-parse --show-object-format`; the helper feature-probes these surfaces.
Signing recovery requires a POSIX runtime with owner/mode and no-follow file
primitives plus fixed system `git` and `ssh-keygen` executables in the
runtime's default system directories. Replacement refs, legacy grafts,
unsupported tracked entry types, exceeded evidence bounds, unsupported hosts,
and non-system tool layouts are feature-probed and refused.

## Validation

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/skill/quick_validate.py \
  plugins/git-worktree-safety/skills/git-worktree-recovery
python3 plugins/capability-workbench/scripts/skill/quick_validate.py \
  plugins/git-worktree-safety/skills/git-commit-signing-recovery
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py \
  plugins/git-worktree-safety
python3 -m unittest discover -s plugins/git-worktree-safety/tests -p 'test_*.py'
```
