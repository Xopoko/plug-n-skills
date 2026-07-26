# Standalone Kotlin Harness Proof

Use this reference only after one project-pinned build or test command is
proven blocked before the relevant source compilation begins. A standalone
Kotlin/Native harness can add bounded local evidence; it never
clears the blocker or replaces the project build, Gradle/KGP wiring, or CI.

## Contents

- Applicability And Classification
- Freeze The Inputs
- Preserve Compilation Boundaries
- Compile And Execute
- Reconcile The Receipt
- Claim Boundary
- Public Sources

## Applicability And Classification

Retain the attempted project command, wrapper and tool versions, exit status,
sanitized failure fingerprint, and task trace showing that the relevant
compiler task did not start. If changed build logic, generators, dependency
declarations, or project configuration may have caused the failure, the
harness cannot offset it.

Report independent state fields so harness validity, a negative test result,
and proof strength cannot hide one another:

| Field | Allowed values | Meaning |
| --- | --- | --- |
| `PROJECT_BUILD` | `BLOCKED_PRECOMPILATION` | The retained project command stopped before relevant compilation. |
| `PROJECT_SOURCE_COMPILE` | `NOT_RUN` | No project-owned compile task reached source compilation. |
| `HARNESS_VALIDITY` | `INVALID`, `VALID` | Inputs, declared closure, controls, and retained evidence are or are not trustworthy for the stated scope. |
| `HARNESS_OUTCOME` | `NOT_RUN`, `COMPILE_FAIL`, `TEST_FAIL`, `COMPILE_PASS`, `TEST_PASS` | The furthest observed standalone outcome. |
| `PARITY` | `NOT_ESTABLISHED`, `CANARY`, `INPUT_PARITY` | How closely the standalone inputs and compiler model match a trusted project-owned baseline. |
| `CI` | `UNVERIFIED` | No CI claim follows from the local harness. |

A valid harness may expose a real compiler error or failing assertion; report
that as `VALID` plus `COMPILE_FAIL` or `TEST_FAIL`, not `INVALID`.
`COMPILE_PASS` means the declared compile/link phases succeeded but no valid
nonzero test run completed. `TEST_PASS` requires the full reconciliation below.
Neither standalone pass authorizes merge, release, or product acceptance.

## Freeze The Inputs

Use a fresh task-local run directory and record:

- a clean commit plus verified clean state, or a base revision plus a manifest
  covering relevant staged, unstaged, untracked, ignored-but-consumed,
  generated, submodule, and LFS-materialized bytes;
- pre-run and post-run hashes for every consumed source and control input;
- the harness and compiler distribution version and digest;
- canonical argument files, target, language/API versions, opt-ins, compiler
  plugins and options, dependencies, linker inputs, SDK, and toolchain;
- the expected test identities and intended invocation cardinality.

Do not clean, stash, reset, or overwrite user work to manufacture a receipt.
Do not use mutable cache paths or filenames as artifact identity.

Keep raw arguments, manifests, and runner events in an access-controlled local
run directory. Never retain credential values. Before making any receipt
model-visible or public, build it from an explicit allowlist: replace absolute
home/cache paths, usernames, machine names, private coordinates or endpoints,
internal source/test names, and logged product data with logical relative names,
counts, or content digests. Keep exact identities only in restricted evidence
when they are required for reconciliation.

## Preserve Compilation Boundaries

Build an explicit manifest for every applicable production and test source set,
including intermediate/refined sets, custom directories, `expect`/`actual`
sources, fixtures, and local project-source dependencies. Record justified
exclusions and require the consumed set to match the declared set.

Compile production first, using production dependencies only, into a fresh
artifact. Compile and link tests against that artifact with the project's
friend-module rules and test-only dependencies. Do not flatten production and
tests into one compiler invocation: test libraries can hide production errors.

Likewise, a flat union of common, intermediate, and platform sources can admit
platform APIs where the project source-set model forbids them. Such a run is
only `PARITY=CANARY`, even when it is green.

`PARITY=INPUT_PARITY` requires a trusted project-owned compiler/model baseline
bound to the same source revision. Require equality of the source-set and
refinement graph, per-fragment compiler arguments, friend associations, and
production and test library closures. If that baseline or any equality check is
missing, cap the result at `PARITY=CANARY`.

Inventory generated code and resources, compiler-plugin transformations,
cinterop inputs, build constants, and selected dependency variants. Regenerate
them from pinned authorized inputs or bind retained outputs to matching provenance
and content hashes. Any missing, stale, or behavior-relevant input hidden
behind the blocked build path prevents `PARITY=INPUT_PARITY`.

## Compile And Execute

Use the pinned compiler's documented standard options where possible. Treat
every advanced `-X` option as version-coupled and retain its exact spelling and
compiler version.

For Kotlin/Native:

1. Confirm the target with the pinned compiler's `-list-targets`.
2. Compile production separately, then link tests with
   `-generate-test-runner`; do not replace discovery with a hand-written
   `main` that calls selected test functions.
3. Hash the final executable and execute that exact binary on the declared
   target runtime with a bounded timeout.
4. For Apple Simulator execution, use an explicit UDID rather than an
   ambiguous `booted` alias. Record Xcode, SDK, runtime/build, device type, and
   architecture. Boot, reset, shut down, or delete only a simulator the
   harness owns; otherwise record the pre-existing state and isolation limit.

One simulator run proves neither a physical device, another architecture or OS,
application hosting, resources, framework embedding, signing, entitlements,
performance, nor another KMP target.

## Reconcile The Receipt

Set `HARNESS_OUTCOME=TEST_PASS` only when:

```text
inputs_before == inputs_after
declared_sources == consumed_sources
production_compile == success
test_link == success
N > 0
required_tests == discovered == started == completed == reported == retained
failures == errors == required_skips == timeouts == crashes == 0
compiled_target == execution_target
```

For `PARITY=INPUT_PARITY`, additionally require:

```text
baseline_source_graph == enforced_source_graph
baseline_fragment_args == enforced_fragment_args
baseline_friend_associations == enforced_friend_associations
baseline_production_libraries == enforced_production_libraries
baseline_test_libraries == enforced_test_libraries
```

Use exact test identities as a multiset so duplicate execution cannot hide.
Retain current-run raw runner events, exit status, executable hash, structured
results, and artifact hashes in the initially empty run directory. If a
versioned converter produces JUnit XML, retain the raw input plus the converter
version and digest. Console text or exit zero alone is insufficient.

## Claim Boundary

State every result field, exactly which enumerated bytes compiled, and which
tests ran on which target/runtime. Keep these unproven unless the project-owned
gates later execute: Gradle configuration and task wiring, dependency resolution
and variant selection, uncovered generation/cinterop, packaging and integration,
other targets, retained project JUnit, CI, review, and delivery readiness.

A standalone pass does not reduce the severity of the blocked project build.
After a source, compiler, harness, dependency, SDK, runtime, or configuration
change, invalidate the receipt and rerun only the affected proof.

## Public Sources

- [Kotlin compiler options](https://kotlinlang.org/docs/compiler-reference.html)
- [Get started with Kotlin/Native](https://kotlinlang.org/docs/native-get-started.html)
- [Kotlin/Native libraries](https://kotlinlang.org/docs/native-libraries.html)
- [Test a Kotlin Multiplatform app](https://kotlinlang.org/docs/multiplatform/multiplatform-run-tests.html)
- [Kotlin Multiplatform project structure](https://kotlinlang.org/docs/multiplatform/multiplatform-discover-project.html)
- [Kotlin/Native target support](https://kotlinlang.org/docs/native-target-support.html)
- [Xcode command-line tool reference](https://developer.apple.com/documentation/xcode/xcode-command-line-tool-reference)
