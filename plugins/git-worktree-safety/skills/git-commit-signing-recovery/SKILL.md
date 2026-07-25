---
name: git-commit-signing-recovery
description: >-
  Use when an ordinary Git commit fails before ref advancement at SSH signing
  with signer, agent, socket, helper-program, or signing-key evidence. Preserves
  the staged state, records private recovery state, issues one single-use signed
  retry authorization after a relevant signer-state change, and verifies the
  resulting commit, parent, diff, signer identity, and residual worktree state.
  Do not use for hook failures or hook-mutated state, conflicts, index or
  object corruption, remote authentication, OpenPGP or X.509 commit signing,
  editor/template or cleanup-transformed commit messages, artifact or release
  signing, key generation or rotation, initial or root commits, amend, merge,
  empty commits, index-altering `-a`/pathspec/interactive commit modes,
  non-signer command-scoped Git configuration or commit-metadata environment
  overrides, rebase/cherry-pick sequencers, unsigned-policy changes, or
  ordinary commit creation.
---

# Git Commit Signing Recovery

Recover a failed signed commit without silently changing trust or committed
content. Resolve `$PLUGIN_ROOT` from the host's plugin-root variable when
defined; otherwise use the absolute path of this skill folder's `../..`.

Read
`$PLUGIN_ROOT/skills/git-commit-signing-recovery/references/recovery-contract.md`
before authorizing a retry, changing signer execution, or considering an
unsigned fallback.

## Safety Boundary

- Confirm that the failure is signer-specific and that the branch ref did not
  advance. Bind the exact worktree plus symbolic branch or detached-HEAD state;
  another linked worktree or ref at the same commit is not equivalent. A hook,
  conflict, index, object, disk, or remote-authentication failure belongs to
  another workflow.
- Require a non-interactive commit whose `COMMIT_EDITMSG` bytes are the intended
  stored message. Editor, template, scissors, comment cleanup, or other
  message-transforming modes require a separate recovery contract.
- Require an existing pre-commit `HEAD`. Initial or root commits need a
  separate parent-transition contract.
- Require caller evidence that both the failed command and retry are
  plain-index commits: no `-a`, `--include`, `--only`, pathspec,
  `--pathspec-from-file`, interactive/patch mode, hook bypass, author/committer
  override, or command-scoped Git configuration/environment override. The only
  eligible retry override is one `gpg.ssh.program` command override already
  proven to reach the same trusted key.
- Preserve the index and worktree. Do not reset, restore, re-stage, amend,
  stash, or rebuild the failed commit merely to make signing pass.
- Classify repository signing policy as `required`, `optional`, or `unknown`.
  Required and unknown policy fail closed. Optional policy still does not
  authorize an unsigned commit without explicit user approval.
- Never change global Git configuration, disable hooks, restart or kill a
  credential agent, export private keys, rotate signing identity, or print
  key, socket, program, or configuration values.
- Require POSIX owner/mode and no-follow file primitives plus fixed system
  `git` and `ssh-keygen` executables. Missing evidence is a stop condition.
- Prefer restoring the configured signer. A one-command signer-program
  override is eligible only when an independent probe proves the same trusted
  key identity and no persistent configuration changes.
- Retry the exact signed commit at most once, and only after a relevant
  signer-state change plus an unchanged recovery fingerprint and an atomically
  consumed authorization token. A second signing failure is a stop condition.
- After success, prove the same worktree and HEAD-ref identity, one expected
  first-parent advance, the exact staged diff, a valid commit signature from
  the recorded identity under the unchanged trust policy, unchanged hook and
  signing configuration identities, and raw tracked-worktree plus non-ignored
  untracked path, type, mode, and content.
- Refuse authorization when replacement refs or legacy grafts are present or
  cannot be inspected. All Git probes also disable object substitution.
- The helper writes only the explicit private receipt and authorization files
  plus namespaced baseline and consumed-token records under the Git common
  directory. It never changes refs, index, configuration, hooks, or worktree;
  commits; signs; restarts agents; or authorizes unsigned output. Post-commit
  verification invokes a fixed system verifier and then proves that repository
  state remained unchanged. It reads tracked and untracked worktree entries
  directly with bounded no-follow file operations instead of invoking
  repository-configured content filters.

## Workflow

1. Read repository policy. Record whether signed commits are required,
   optional, or still unknown.
2. Inspect only a bounded failure tail. Accept this workflow only when the
   evidence names the signing layer and `HEAD` still identifies the pre-commit
   commit, and when the message contract is byte-stable and non-interactive.
3. In a private owner-controlled directory, choose absent receipt and
   authorization paths. Record the baseline immediately after failure:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/git_commit_signing_guard.py" audit \
     --repo /path/to/checkout \
     --policy required \
     --receipt /private/path/signing-receipt.json \
     --authorization /private/path/signing-authorization.json
   ```

   The helper also claims the exact state in its namespaced Git common-directory
   journal. Repeating the snapshot under new filenames cannot mint another
   authorization for the same state.

4. Diagnose the signer without mutating Git state. Obtain a bounded,
   independently verified probe of the configured identity or restored agent
   path. Do not include raw key, socket, executable, or configuration values in
   a handoff.
5. Request the single-use authorization immediately before retry. State that
   the independent signer probe was verified:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/git_commit_signing_guard.py" authorize \
     --repo /path/to/checkout \
     --receipt /private/path/signing-receipt.json \
     --authorization /private/path/signing-authorization.json \
     --signer-probe verified \
     --commit-shape verified-plain-index
   ```

6. Proceed only when the helper reports `signed_retry_allowed: true`; that call
   atomically consumes the only helper-issued retry token. Repeat the same
   plain-index signed commit once. Do not add `-a`, a pathspec, metadata or
   configuration overrides, `--no-gpg-sign`, bypass hooks, alter the message,
   or change the staged set as part of recovery. The one verified same-key
   signer-program override is the sole exception. The helper always reports
   `unsigned_fallback_allowed: false`.
7. Verify the successful result against the private baseline receipt:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/git_commit_signing_guard.py" verify \
     --repo /path/to/checkout \
     --receipt /private/path/signing-receipt.json \
     --authorization /private/path/signing-authorization.json
   ```

8. Report the old and new commit IDs, signature verdict, committed-diff
   equality, residual-state verdict, retry count, and any remaining delivery
   gate. Keep the receipt private when even hashed repository or configuration
   identifiers are inappropriate for the destination.

Exit `0` means private baseline state was created, the single-use token was
consumed, or the post-commit receipt verified. Exit `2` is a safety refusal or
failed postcondition. Exit `1` means malformed input or unavailable evidence.

An unsigned commit is never an automatic recovery path. If repository policy
is explicitly optional and the user separately authorizes unsigned output,
treat that as a new commit decision outside this helper and record the policy
exception in the delivery receipt.
