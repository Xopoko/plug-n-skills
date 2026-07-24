# Git Worktree Recovery Contract

This contract applies when the expected directory or convenience symlink is
gone but a replacement checkout may already preserve the branch. It does not
repair Git administrative state.

## Evidence Model

Use full object IDs and a full `refs/heads/...` input. Classify every expected
commit independently:

| Class | Evidence | Pointer authority |
| --- | --- | --- |
| `branch-reachable` | Commit object exists and is an ancestor of the live branch ref | Eligible |
| `reflog-only` | Not branch-reachable, but retained by the bounded branch reflog | Salvage only |
| `object-only` | Commit object exists without branch or reflog retention | Salvage only |
| `retention-unknown` | Bounded reflog evidence is incomplete | Salvage only |
| `non-canonical-oid` | Input is not the repository's full object-ID length | None |
| `not-commit` | The exact input object is another type, even if it peels to a commit | None |
| `missing` | Commit object cannot be verified | None |

A reflog may be disabled or expired. Its absence does not weaken a live branch
ref that already contains the expected commit. Conversely, object existence or
a reflog entry does not establish the current branch composition. Ref
restoration, branch selection, and history reconciliation are separate
authorized workflows.

Require at least one expected commit. Detect the repository object format and
require its canonical full object-ID length; do not accept an abbreviation.
Require the exact expected object itself to have type `commit`; an annotated
tag that peels to a commit is not accepted.

The helper does not fetch. Fetching can change local refs and would invalidate
the local evidence being classified. Every Git probe disables optional locks,
lazy fetch, replacement refs, legacy grafts, fsmonitor, and the untracked
cache, and scrubs ambient repository, worktree, index, object, replacement,
graft, namespace, shallow-file, discovery, and config semantics by discarding
all inherited `GIT_*` variables before adding only guard-owned safety values.
Subprocess stdout and stderr are drained concurrently into fixed-size buffers;
crossing the cap terminates the probe. Worktree and status evidence must have
the exact NUL framing, record order, and required headers emitted by the fixed
commands. Missing or malformed framing is unavailable evidence, never an empty
clean result.

For the native files ref backend, bounded reflog evidence reads both the old and
new object IDs from a stable regular branch-reflog file under the verified
common Git directory. Truncated, changing, malformed, or unsupported evidence
becomes `retention-unknown`; it can never prove `object-only` or repair
authority.

## Replacement Authority

All of these conditions are required:

1. The repository common directory for the surviving checkout and replacement
   is identical.
2. `git worktree list --porcelain -z --expire=now` contains exactly one entry
   for the requested full branch ref.
3. That entry names the exact replacement directory and is neither bare,
   detached, locked, prunable, nor structurally unsupported.
4. The replacement's symbolic `HEAD` equals the requested full ref.
5. The replacement `HEAD` object ID equals the live branch-ref object ID.
6. Porcelain-v2 status is empty apart from branch headers, with untracked files
   and submodule dirtiness included. Its `branch.oid` must equal the separately
   proven replacement `HEAD`, and `branch.head` must equal the requested short
   branch; `(initial)`, `(detached)`, and any mismatch are stop conditions.
7. No merge, cherry-pick, revert, rebase, bisect, or sequencer state is active.
   A clean porcelain status can coexist with these markers, so any indication
   that a Git operation is already in progress is a stop condition.
8. Every expected commit is `branch-reachable`.

These gates establish checkout identity and cleanliness. They do not establish
exclusive writer ownership, user intent, remote freshness, test proof, or
delivery authorization. Git object and reflog evidence covers committed
history only. Uncommitted, untracked, or ignored content from a missing target
cannot be proven or recovered, so a broken-target audit emits
`missing_target_uncommitted_state_unverifiable`.

## Link States

Inspect the pointer itself with `lstat` and `readlink`; do not follow it before
deciding its type.

The link must be outside every registered worktree and outside the common Git
directory. Repairing a pointer inside any protected checkout could itself
change the Git state that the audit promises to preserve.

- `current`: it is a symlink resolving to the registered replacement. Audit is
  an idempotent `noop`.
- `broken`: it is a symlink whose target does not exist. Repair remains possible
  only when its raw target exactly matches `--expected-old-target`.
- `live-other`: its target exists but is not the replacement. Stop.
- `missing`: no filesystem entry exists. Creating a new link is outside this
  workflow because there is no old pointer for an exact comparison.
- `file` or `directory`: stop without overwriting it.

The proposed `--new-target` may be absolute or relative. A relative value is
resolved from the convenience link's parent and must identify the exact
registered replacement.

## CAS-Style Repair

`repair-link` requires `--apply`, the prior audit fingerprint, the exact old raw
target, and the exact new raw target.

1. Re-run the complete audit.
2. Require the audit fingerprint to match.
3. Re-read the symlink and require the same device, inode, metadata timestamp,
   and raw target captured by the audit.
4. Create a uniquely named temporary symlink beside the pointer.
5. Re-read the original immediately before atomically replacing its directory
   entry.
6. Read the replaced entry through the parent descriptor and require the exact
   requested raw target, not merely an equivalent path to the replacement.
7. Re-audit and require `noop`, `repoint` authority, no decision reasons, the
   exact raw target, and the resolved replacement.
8. Recompute the Git fingerprint and require equality with the pre-repair
   fingerprint.

Audit is host-neutral. Repair is available only on POSIX runtimes that
feature-prove directory-relative no-follow stat/readlink/symlink/unlink and
atomic replace with source and destination directory descriptors. Unsupported
hosts, including Windows runtimes without these primitives or symlink
permissions, remain read-only.

This is a directory-anchored compare-and-swap-style guard, not a claim that
every filesystem offers an atomic predicate-and-replace primitive against a
hostile concurrent writer. The parent directory identity and link metadata are
rechecked immediately before replacement, but an unavoidable
predicate-to-replace race remains on portable POSIX APIs. If the link directory
is concurrently managed or untrusted, remain read-only.

The helper never rolls back by rewriting Git. If a postcondition fails after the
pointer replacement, report failure, preserve the evidence, and stop. If
immediate link inspection, parent-descriptor closure, or the full post-audit is
unavailable after atomic replacement, emit a repair-schema
`postcondition-unavailable` result with `mutation_performed: true`, the
pre-repair fingerprints, and only a digest of the immediate raw target when
one was observed. Never imply rollback.

## JSON Contract

The helper emits one bounded JSON object:

- `git_worktree_safety.audit.v1` for audit;
- `git_worktree_safety.repair.v1` for repair;
- `git_worktree_safety.error.v1` for malformed input or unavailable evidence.

Raw absolute paths still exist in command arguments and local filesystem
access, but raw absolute paths, raw symlink targets, command stderr, reflog
messages, and status paths are omitted from JSON. Paths and raw targets use
SHA-256 identifiers. Status and relevant Git state use stable fingerprints.
Full commit IDs and the requested branch ref remain explicit because they are
the identity proof.

Reason codes are a closed, bounded vocabulary. Exit `0` is a passing audit,
no-op, or completed repair; exit `2` is a safety refusal; exit `1` is malformed
input or unavailable evidence.

## Explicit Exclusions

This workflow never invokes or authorizes:

- `git worktree add`, `move`, `remove`, `prune`, `repair`, `lock`, or `unlock`;
- `git update-ref`, branch creation/deletion/force-update, checkout, switch,
  reset, restore, rebase, merge, cherry-pick, or stash;
- recursive filesystem deletion or broad symlink cleanup;
- stack restacking, writer assignment, session orchestration, or remote/forge
  mutation.
