# CI-Generated Screenshot Goldens

Use this lifecycle when CI is the authoritative renderer, a local dependency
blocks baseline generation, or review consumes generated screenshot artifacts.
Keep library and CI-provider commands project-specific.

## Mode Contract

- `record`: deliberately writes candidate reference images.
- `compare`: produces expected, actual, diff, and machine-readable review
  evidence without accepting candidates.
- `verify`: reads accepted references, fails on mismatch, and must not rewrite
  them.

Discover the target project's real tasks and confirm the screenshot work
actually executed for the intended tests. Do not infer task names or count
skipped, no-source, up-to-date, or cached task state as proof. A combined
verify-and-record mode can help refresh candidates but cannot be the final gate
because it mutates the evidence it checks.

## Generation Contract

1. Start from a clean, isolated checkout at the exact generator source
   revision, with an empty task-local output location. Record the accepted
   baseline tree and expected output paths.
2. Pin or record the rendering inputs: runner image or container, OS and
   architecture, wrapper and JDK, locked dependencies, Kotlin, Compose,
   screenshot renderer, locale, timezone, density, theme, fonts, and
   device/variant qualifiers. Record only allowlisted non-secret versions,
   values, or digests relevant to the renderer; never retain raw secret-bearing
   environment values, properties, init scripts, or configuration files.
3. Run the explicit record task for one target and expected test selection.
4. Build a review bundle containing the candidate references,
   expected/actual/diff images when available, report, test results, and a
   payload manifest. The payload manifest binds:
   - source revision and accepted-baseline tree;
   - exact task, mode, target, variant, and test filter;
   - generator and rendering inputs;
   - complete before/after path inventories and per-file SHA-256 values;
   - explicit added, modified, and deleted path sets.
   Compute the payload-manifest digest before upload.
5. After upload, obtain a provider-verified receipt that binds repository,
   workflow, run, job, attempt, source revision, artifact identifier, and
   archive digest. Fetch that exact artifact, not a mutable "latest" result,
   then verify the receipt and archive digest before opening it. Verify the
   included pre-upload payload manifest and its file hashes as failing steps; a
   trusted signed attestation may bind both layers directly. Treat in-bundle
   provenance alone as an untrusted claim. A checksum proves byte integrity,
   not trusted authorship or visual correctness.

If local generation is blocked, report the exact blocker and mark local proof
unavailable. CI may become the generator only when it satisfies the same
contract.

## Generator Routing And Review-Object State

Before publishing a generator revision, inspect the provider's actual workflow
and job rules. Determine whether an open review object suppresses the required
branch pipeline, changes its rule variables, or routes it to a different job.
Do not infer routing from a workflow filename or from an earlier run.

When the provider requires a branch-only generator:

- Use a dedicated authorized ref with no open review object only when that
  state is part of the declared generation procedure.
- Do not create, close, retarget, or mutate a review object merely to trigger a
  pipeline without separate authority for that state change.
- Treat the branch-only generator result as proof of generation and artifact
  provenance for its exact revision only. It does not prove review, approval,
  mergeability, landing, or the final accepted revision.
- Keep a temporary generator revision diagnostic and non-deliverable. A failed
  or corrected generator revision remains historical evidence; do not blindly
  retry it. A relevant source, fixture, workflow, or environment change must
  produce a new immutable revision and run.

Fetch the artifact by immutable job or run identifier and verify that the
provider receipt binds that identifier to the exact generator revision. A
mutable latest-by-ref lookup is discovery, not acceptance proof.

Before extraction, validate the downloaded ZIP and exact newline-delimited PNG
allowlist with the bundled guard:

```sh
python3 "$PLUGIN_ROOT/scripts/golden_artifact_guard.py" \
  --archive "$artifact_zip" \
  --allowlist "$expected_goldens" \
  --expected-archive-sha256 "$provider_archive_sha256" > "$guard_receipt"
```

Require exit status zero and a `status: accepted` receipt. Retain that receipt
with the provider receipt and payload manifest. The guard validates bounded ZIP
and PNG structure, exact paths, digests, and resource limits; it does not
extract files, establish trusted authorship, or authorize a visual change.
Acceptance is intentionally narrow: single-disk non-ZIP64 archives and 8-bit
truecolor or truecolor-with-alpha PNGs with portable metadata only. Normalize
other valid encodings in the trusted generator rather than weakening the
artifact boundary during review. ZIP archive and member comments are not
accepted because they are outside the bounded metadata contract. Every local
record is validated before any member payload is decoded.

## Review And Cleanup

- Do not create a downstream consumer extraction or import staging directory
  before the guard accepts the archive. If that later step fails or is
  interrupted, remove only the partial directory created for that attempt.
- Inspect archive entries before extraction. Reject absolute or parent paths,
  links, special files, case-fold collisions, duplicate paths, and payloads
  outside declared size limits. Extract to an isolated temporary directory and
  copy only allowlisted regular files.
- Import only the declared delta. Compare the before/after inventories, apply
  explicit additions, modifications, and deletions, and reject any undeclared
  change, path collision, or missing expected output. A deletion must belong to
  the executed test scope or receive separate explicit review.
- Do not enable broad old-screenshot cleanup during a filtered run. It can
  delete baselines for tests that did not run.
- Prefer transient task options over editing persistent project settings.
- Remove temporary workflow, dependency, property, or generator-only changes
  before final verification. Confirm the remaining diff contains only intended
  source and accepted baseline changes.
- Visual review authorizes meaning. Provenance and digests cannot decide
  whether a visual change is correct.

Give each recording target or variant a unique output namespace. Serialization
alone does not prevent later writers from replacing the same path. When unique
paths are impossible, declare exactly one record writer and make every other
target verify-only; fail on any path collision. If output isolation changes
baseline paths, migrate or re-record explicitly and review that move. A result
from one OS, renderer, or platform proves only that recorded environment.

## Final-Head Gate

After accepted baselines are committed:

1. Check out the exact intended final revision in a fresh isolated workspace
   and the pinned rendering environment. Use controlled project and build-tool
   homes where practical. Fingerprint only allowlisted, sanitized non-secret
   environment, init-script, user-property, and external-configuration inputs.
2. Compare the committed baseline tree, including deletions, with the approved
   after-inventory and hashes. Bind the review decision and manifest digest to
   this final commit and baseline tree.
3. Run non-recording verify for the complete affected target and variant. A
   filtered verify proves only that filter and must not authorize broader
   acceptance.
4. Require actual screenshot-task execution; a skipped, no-source, up-to-date,
   or cached result is stale unless an equally strong run-bound freshness proof
   covers every source, baseline, environment, configuration, and test input.
   Require fresh current-job result files and a nonzero expected-test count.
5. Confirm the tested revision still equals the final head, the complete
   expected tests and reference set were discovered, and no undeclared
   generated, untracked, ignored, or configuration residue remains in the
   checkout.
6. Before workspace cleanup, copy the verify report, results, payload manifest,
   provider receipt or attestation, sanitized environment/config fingerprint,
   and exact command to the declared external evidence location.

Evidence from the generator revision, a pre-baseline revision, or an older head
is stale. It does not prove the accepted final revision.

## Failure Contract

On a visual mismatch, retain expected, actual, diff, report, results, payload
manifest, and provider receipt; do not silently record over the mismatch. On
dependency, runner, renderer, artifact, or checksum failure, preserve the
smallest useful diagnostics and report the exact task, failure, artifact
reference, and `unverified` status. Copy failure evidence to the declared
external evidence location before cleaning the isolated workspace. Expiring CI
artifacts are review evidence, not the only accepted baseline store.
