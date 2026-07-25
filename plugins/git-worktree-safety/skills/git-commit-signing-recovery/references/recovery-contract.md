# Git Commit Signing Recovery Contract

Use this contract after an ordinary `git commit` reaches the signing layer and
fails at SSH signing before the branch ref advances. It preserves the observed
candidate state; it does not make signing policy.

## Failure Classification

| Evidence | Classification | Recovery authority |
| --- | --- | --- |
| Signer, agent, socket, signing helper, or configured key failed; `HEAD` is unchanged | `signer-failure` | Eligible after a state receipt |
| Hook exited non-zero or modified the index | `hook-failure` | None |
| Failed or retry command uses index-altering modes, pathspecs, hook bypass, commit-metadata environment, or unmodeled Git config/environment overrides | `invocation-override` | None |
| Merge, rebase, cherry-pick, revert, or sequencer state exists | `sequencer-operation` | None |
| Conflict, index lock/corruption, missing object, disk, or filesystem failure | `repository-failure` | None |
| Push, fetch, forge, or remote SSH authentication failed | `remote-auth-failure` | None |
| Error origin is ambiguous | `unknown-failure` | None |

Use a bounded error tail only to classify the layer. Do not copy raw
environment dumps, socket paths, key material, program paths, or configuration
values into tracked fixtures, public comments, or handoffs.

This workflow intentionally excludes initial/root commits, amend, merge
commits, empty commits, rebases, cherry-picks, reverts, and sequencer-owned
commits. Their parent and operation-state contracts require separate recovery
logic.

It also excludes editor, template, scissors, comment-cleanup, and other
message-transforming modes. The recorded `COMMIT_EDITMSG` must already be the
byte-exact message expected in the commit object.

## Signing Policy

Classify policy before choosing an action:

- `required`: repository, branch, delivery, or user policy requires a signed
  commit. Unsigned fallback is forbidden.
- `optional`: an authoritative repository or user policy explicitly permits an
  unsigned commit. This still requires explicit user authorization for the
  specific output.
- `unknown`: no authoritative policy receipt is available. Treat signing as
  required until policy becomes known.

Green tests, an available `--no-gpg-sign` option, or a local configuration value
does not establish optional policy. The helper never authorizes unsigned
output.

## Recovery Receipt

The audit helper creates a bounded private JSON receipt, a separate single-use
authorization file, and a deterministic baseline claim in a namespaced
directory under the Git common directory. Its public output contains no raw
paths or signing values. The state fingerprint binds:

- exact worktree/common-dir/Git-dir identity, pre-commit `HEAD`, and immediate
  plus fully resolved symbolic branch or detached-HEAD identity;
- staged binary-diff fingerprint and whether staged changes exist;
- a stable regular `COMMIT_EDITMSG` fingerprint for the intended message;
- index stage/object inventory plus semantic `skip-worktree` and
  `assume-unchanged` flags, and raw tracked-worktree path, type, mode, and
  bounded content fingerprints;
- non-ignored untracked path, type, mode, and bounded content fingerprints;
- active Git operation markers;
- replacement refs and legacy grafts, including presence and content evidence;
- configured hook path plus content and executable-state fingerprints for
  commit-relevant hooks;
- effective signing format, the configured public signing identity, program
  digests, and trust or revocation file content when present;
- fixed system Git and signature-verifier executable content identities.

The external files and the mode-`0700` journal are created with exclusive
creation. Authorization atomically creates one deterministic consumed-token
record keyed by the exact state, independent of caller-selected filenames.
Repeated snapshots cannot mint another authorization for that state. The
helper does not claim to prevent a caller from ignoring it and running a commit
directly.

Authorization snapshots the state again after token creation. Late drift burns
the token and returns a refusal. A process can still race after the helper
returns, so run the unchanged command immediately and rely on post-verification
to detect resulting drift.

The receipt proves only consistency with the state observed after the failure.
A hook may have changed files or the index before that receipt existed. A
hostile process running as the same local principal can replace private state,
so the files are not a cryptographic timestamp or hostile-principal
attestation. Review unexpected post-failure changes before accepting the
baseline.

The helper removes ambient `GIT_*` and dynamic-loader variables, replaces
ambient `PATH` with fixed system directories, disables optional locks, lazy
fetch, replacement objects, legacy graft application, paging, external diff,
and text conversion, and caps command output. It does not run worktree
`diff`/`status` probes: tracked and untracked content is read directly with
bounded no-follow operations, so repository-configured clean, smudge, and
process filters are not executed. This creates a stable baseline; it does not
reconstruct command-scoped `git -c` overrides used by the failed commit.

That limitation is an eligibility boundary, not merely missing evidence.
Failed and retry commands must use the current index exactly, without `-a`,
`--include`, `--only`, pathspecs, `--pathspec-from-file`, interactive/patch
selection, hook bypass, author/committer metadata overrides, or command-scoped
Git configuration/environment overrides. The sole retry exception is one
`gpg.ssh.program` command override independently proven to reach the recorded
trusted key. If the original invocation is unavailable, classify it as
`invocation-override` and stop.

Replacement refs and a default Git-common-directory `info/grafts` file are
authorization blockers even though every probe neutralizes their effect.
Unsupported tracked entry types, gitlinks, unsafe path topology, or exceeded
entry/content bounds make residual-state evidence unavailable and fail closed.

Authorization is available only on POSIX runtimes with owner/mode and
no-follow file primitives. Both `git` and `ssh-keygen` must resolve from the
runtime's fixed default system directories and pass regular-file,
non-writable, ownership, executable, and content-stability checks. Other hosts
and non-system tool layouts fail closed.

Post-commit verification never executes a repository-configured signer program
or an ambient-`PATH` wrapper. It overrides the verifier command with a fixed
system `ssh-keygen` executable, requires the executable identity and persistent
configuration to match the receipt, extracts the actual signing identity, and
snapshots repository state again after verification. A missing system verifier
or unresolvable configured identity makes signature evidence unavailable.

Keep the receipt private when its hashes or commit IDs should not leave the
local workflow. Hashing suppresses raw values; it is not anonymization against
an attacker with a small candidate set.

## Signer Recovery

Prefer restoring the configured signer, agent, or helper without changing Git
configuration. A valid state change is one of:

- the existing agent or socket becomes available again;
- the configured signing helper becomes executable again;
- an independent detached-signature probe succeeds with the same trusted key;
- a one-command helper-program override reaches the same trusted key and leaves
  global, system, and repository configuration unchanged.

Changing the signing key, trust policy, allowed-signers file, signing format,
or persistent signer program is not recovery. It is a separate trust change
that requires explicit authority and invalidates the baseline.

The `--signer-probe verified` and
`--commit-shape verified-plain-index` arguments record caller-supplied
evidence; the helper cannot authenticate agent health or the eventual commit
invocation. It proves that Git state, persistent hook policy, trust material,
and effective persistent signing configuration still match the baseline, then
consumes one authorization token. Do not pass either attestation without an
actual bounded check.

SSH recovery requires a public key literal, a `.pub` public-key file, or a
readable `.pub` sidecar so the helper can compute the configured identity
without reading or exporting a private key. OpenPGP and X.509 signing have
different keyring and trust-state contracts and are explicitly outside this
workflow.

## One-Retry Rule

A signed retry is eligible only when all conditions hold:

1. The failure is classified as signer-specific.
2. The private receipt and fresh authorization state exist.
3. The same worktree and symbolic branch or detached-HEAD identity are active,
   and `HEAD`, staged content, raw tracked-worktree content, untracked
   inventory, operation state, and persistent signing configuration still
   match its fingerprint.
4. No Git operation marker exists and staged changes are non-empty.
5. A relevant signer probe is verified.
6. The failed and retry command shapes are verified as plain-index operations,
   with only the eligible same-key signer-program override.
7. The helper can atomically consume the only authorization token.
8. The exact commit message, staged set, persistent hook policy, and signed
   intent remain unchanged.

If the retry fails again, stop. Do not alternate signer programs, cycle agents,
or progressively relax signing and hook policy.

## Post-Commit Proof

Verification requires:

- current `HEAD` differs from the receipt head;
- exact worktree and symbolic branch or detached-HEAD identity still match;
- the new commit has exactly the receipt head as its sole first parent;
- the binary diff from the old head to the new commit matches the staged-diff
  fingerprint in the receipt;
- the new commit message matches the recorded `COMMIT_EDITMSG` fingerprint;
- the index has no residual staged delta against the new commit;
- tracked-index object/stage/semantic-flag, tracked-worktree, and
  untracked-inventory fingerprints match the receipt;
- non-ignored untracked file and symlink content fingerprints match the
  receipt;
- effective persistent signing configuration matches the receipt;
- persistent hook policy matches the receipt;
- `git verify-commit` accepts the new commit under the current trust policy and
  the observed signer identity matches the recorded configured identity;
- the fixed verifier leaves repository state unchanged;
- no Git operation marker is active.

These checks prove consistency of one ordinary signed commit with the recorded
state and consumed token. The plain-index invocation is a caller attestation:
post-verification cannot prove which command or command-scoped overrides
created the object. The checks do not prove receipt chronology against a
hostile same-user process, commit-command causality, unrecorded author or
committer intent, remote publication, forge signature badges, CI, review,
approval, or landing.

## Explicit Exclusions

This workflow never:

- runs `git commit`, `commit --amend`, rebase, cherry-pick, revert, merge, push,
  fetch, reset, restore, checkout, stash, or update-ref;
- changes system, global, local, worktree, or command-scoped Git configuration;
- authorizes index-altering, pathspec, interactive/patch, hook-bypass, or
  commit-metadata-override invocation shapes;
- writes anywhere except the caller-selected private receipt and authorization
  files plus namespaced baseline and consumed-token records under the Git
  common directory;
- generates, imports, exports, rotates, trusts, or deletes signing keys;
- kills, restarts, unlocks, or reconfigures a credential or signing agent;
- authorizes OpenPGP or X.509 commit-signing recovery;
- authorizes editor/template or cleanup-transformed commit messages;
- bypasses hooks or signing policy;
- treats a source signature as CI, review, approval, publication, or runtime
  proof.
