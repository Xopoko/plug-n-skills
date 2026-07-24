---
name: git-worktree-recovery
description: >-
  Use when an expected Git worktree path or convenience symlink is missing,
  stale, or broken and a registered replacement may already hold the branch.
  Classifies branch-ref, reflog-only, object-only, or missing retention and
  guards POSIX-only exact symlink repair when directory-relative primitives are
  available. Do not use for Git administrative worktree repair after moving a
  main or linked worktree, ordinary worktree creation/removal/pruning, ref
  restoration, checkout/reset, stacked-change restacking, host-specific session
  orchestration, recovery of unsaved content from a vanished checkout, or
  arbitrary non-Git symlink repair.
---

# Git Worktree Recovery

Recover the pointer only after proving that Git state is already safe. Resolve
`$PLUGIN_ROOT` from the host's plugin-root variable when defined; otherwise use
the absolute path of this skill folder's `../..`.

Read
`$PLUGIN_ROOT/skills/git-worktree-recovery/references/recovery-contract.md`
before interpreting salvage evidence or authorizing repair.

## Safety Boundary

- Start with `audit`; it is the default mode and performs only allowlisted
  read-only Git inspection.
- Treat a live `refs/heads/...` ref containing every expected commit as repair
  authority. Reflog-only or object-only retention is salvage evidence, never
  authority to repoint a convenience link.
- Require one unique registered replacement with the exact symbolic branch,
  `HEAD` equal to the live branch ref, a clean porcelain-v2 status including
  untracked files whose `branch.oid` and `branch.head` headers still equal that
  `HEAD` and requested short branch, no in-progress Git operation, and no
  locked or prunable annotation. Require at least one canonical full expected
  commit ID whose object type is directly `commit`.
- Do not infer writer ownership from a worktree lock or a clean checkout.
- Treat ref, reflog, and object evidence as committed-history evidence only.
  Uncommitted, untracked, or ignored content from a missing target cannot be
  proven or recovered; report that limit and never call pointer repair content
  recovery.
- Repair only a verified broken symlink outside the common Git directory and
  every registered worktree, after explicit authorization. Never
  overwrite a regular file, directory, live symlink target, missing pointer, or
  link whose raw target changed after audit.
- Never create, add, move, remove, prune, repair, unlock, or delete worktrees;
  restore or update refs; check out, reset, switch, rebase, or restack branches;
  recursively delete paths; or execute a shell.
- Raw absolute paths remain present in command arguments and local filesystem
  access, but are omitted from JSON. The helper emits path digests, stable
  state codes, full object IDs, and bounded fingerprints instead.
- Audit is host-neutral. Repair is limited to POSIX runtimes that feature-prove
  directory-relative no-follow inspection and atomic replacement; unsupported
  hosts remain read-only.

## Workflow

1. Read repository policy and identify a surviving checkout from the same
   repository, the full `refs/heads/...` ref, the registered replacement
   directory, the convenience link, and any full expected commit IDs.
2. Run the read-only audit with the exact current raw link target and proposed
   new raw target. Relative symlink targets are resolved from the link parent.
3. Accept `ready` only when authority is `repoint` and every Git, worktree,
   cleanliness, link, and target gate passes. `salvage-only`, `blocked`, or an
   evidence error is a stop condition.
4. If pointer repair is authorized, pass the unchanged audit fingerprint to
   `repair-link`. The helper re-audits immediately, compares the fingerprint and
   raw target, replaces only the exact symlink, then proves relevant Git state
   remained unchanged.
5. Re-run `audit` independently and report the final link state, branch/ref
   object ID, Git fingerprint, and any remaining stop condition.

Read-only audit:

```bash
python3 "$PLUGIN_ROOT/scripts/git_worktree_recovery_guard.py" \
  --repo /path/to/surviving-checkout \
  --branch-ref refs/heads/example-branch \
  --replacement /path/to/registered-replacement \
  --link /path/to/convenience-link \
  --expected-old-target ../missing-checkout \
  --new-target ../registered-replacement \
  --expected-commit 0123456789abcdef0123456789abcdef01234567
```

Separately authorized repair:

```bash
python3 "$PLUGIN_ROOT/scripts/git_worktree_recovery_guard.py" \
  --mode repair-link \
  --repo /path/to/surviving-checkout \
  --branch-ref refs/heads/example-branch \
  --replacement /path/to/registered-replacement \
  --link /path/to/convenience-link \
  --expected-old-target ../missing-checkout \
  --new-target ../registered-replacement \
  --expected-commit 0123456789abcdef0123456789abcdef01234567 \
  --expected-fingerprint AUDIT_FINGERPRINT \
  --apply
```

Exit `0` means `ready`, `noop`, or `repaired`; exit `2` is a safety refusal;
exit `1` means malformed input or unavailable evidence. A successful repair is
pointer-only proof, not permission for any later Git or delivery mutation.
