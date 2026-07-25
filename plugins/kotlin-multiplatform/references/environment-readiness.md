# KMP Environment And Private Dependency Readiness

Use this only when host setup or private dependency access may be the problem.
It does not replace project inspection.

## Host Signals

- Xcode or simulator tasks fail before project code compiles.
- CocoaPods/Ruby errors appear during iOS integration.
- Android Studio or KMP plugin setup is suspected.
- JDK or Gradle JVM mismatch appears.
- The project builds on CI but not locally.

## Host Checks

```bash
xcode-select -p
xcodebuild -version
java -version
./gradlew -version
kdoctor -v
kdoctor --all
```

KDoctor is macOS-only and checks OS, JDK/JAVA_HOME, Android Studio plugins, Xcode, Ruby, and CocoaPods. Do not install it or change host tools without explicit user approval.

## Private Dependency Access Gate

Use this gate when the smallest project-pinned Gradle task cannot materialize an
exact private Maven/Gradle dependency. Diagnose the local process and CI as
separate execution surfaces. Access proven in one does not prove the other.

Keep these evidence levels distinct:

1. A configured repository, credential variable, access request, approval, or
   secret binding is administrative evidence only. It does not prove that the
   current principal can read the artifact.
2. An offline success proves only that a compatible artifact is available in
   the selected cache. An offline miss proves only cache absence.
3. A warm online success can still be cache-backed. Report remote access as
   unproven unless the exact artifact was fetched or a trusted repository
   receipt proves the request.
4. Effective access requires the normal project credential path plus one
   project-pinned task that consumes the exact coordinate, version, and variant
   on a cache-miss path. Do not manufacture that path by deleting a shared
   cache. A temporary Gradle user home is valid only when it preserves the
   project's real credential injection; otherwise its failure is
   non-equivalent.

If no safe cache-miss proof is available, keep the result `unproven`. Do not
weaken the gate to obtain a green result.

### One-Probe Workflow

1. Identify the smallest failing artifact-consuming task and the exact
   coordinate, version, repository role, and target variant from authorized
   project evidence. Do not copy private coordinates or endpoints into public
   output.
2. Confirm only whether the expected credential binding is present. Never read,
   print, echo, serialize, or compare the credential value.
3. Capture the project wrapper once without streaming raw output into an agent,
   transcript, terminal attachment, or public build scan. Use a freshly created
   mode-`0700` directory and an exclusive, no-follow mode-`0600` file. POSIX
   example:

   ```bash
   KMP_ACCESS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kmp-access.XXXXXX")" || exit 1
   test -n "$KMP_ACCESS_DIR" || exit 1
   chmod 700 "$KMP_ACCESS_DIR" || exit 1
   KMP_ACCESS_LOG="$KMP_ACCESS_DIR/gradle-access.log"
   (umask 077; set -o noclobber; ./gradlew :module:<smallest-artifact-consuming-task> > "$KMP_ACCESS_LOG" 2>&1)
   ```

   On other hosts, use the project-approved equivalent with a user-only ACL.
   Do not use `tee`, `cat`, or a model-visible tool to read the raw file. Use a
   trusted project-owned sanitizer to create a second, redacted file before
   inspection. If no trusted sanitizer exists, keep the raw file private,
   report only the exit code, ask an authorized operator for a redacted failure
   fingerprint, and classify the result `unproven`. Do not add `--debug`, a
   public build scan, `clean`, cache deletion, dependency refresh, dependency
   upgrades, publishing, or interactive login.
4. Before sharing sanitized output, verify it omits private coordinates,
   repository endpoints, usernames, tokens, and signed URLs. If the tool itself
   emits a secret, stop and treat the raw output as sensitive.
5. Retain the exact private directory only for the bounded task. After an
   authorized sanitized receipt exists, remove that exact directory when policy
   permits; never use a wildcard or shared-path cleanup.
6. Retry only after a relevant change to project configuration, credential
   binding, authorization, repository/network state, or the exact artifact.

### Classification

Classify each execution surface as exactly one of:

- `ready`: the narrow project-pinned task materialized and consumed the exact
  artifact through the normal credential path at the stated cutoff, with an
  actual cache-miss fetch or a trusted exact-artifact repository receipt.
  Cache-only or warm-cache evidence is `unproven`, never `ready`.
- `auth-blocked`: the expected binding is absent, authentication is rejected
  (such as `401`), or authorization is denied (such as `403`). Preserve the
  subreason without exposing identities or credentials.
- `network/repository-blocked`: DNS, TLS, connection, timeout, or repository
  service failure prevented an access decision.
- `artifact-or-coordinate-unknown`: repository access may exist, but the exact
  coordinate, version, variant, or artifact cannot be established. A `404`
  alone is ambiguous: it can mean absence, a wrong repository, access
  filtering, or a hidden resource.
- `integrity-blocked`: the exact artifact was reached, but checksum, signature,
  or another integrity gate rejected it.
- `variant-incompatible`: Gradle metadata could not select a compatible target
  variant. Artifact materialization and remote access remain unproven unless a
  separate exact-fetch receipt exists.
- `unproven`: no equivalent narrow probe ran, the result was cache-only, the
  credential path differed, or the evidence cannot distinguish the states
  above.

Graph or metadata resolution does not prove artifact materialization.
Integrity and variant failures prove neither successful consumption nor broader
repository access.

### Bounded Receipt

Record:

- execution surface (`local` or `CI`) and cutoff;
- project-pinned task and target variant;
- repository by generic role and principal by non-identifying role;
- cache mode and whether an actual fetch was proven;
- classification, redacted failure fingerprint, and one next invalidating
  trigger.

Keep exact private coordinates only in an authorized private record. Never
claim repository-wide or durable access from one artifact receipt.
