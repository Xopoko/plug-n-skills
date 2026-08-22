# Capability Evaluation Contract

`$PLUGIN_ROOT` is the Capability Workbench plugin root.

Use this reference to design and review provider-neutral behavioral comparisons
for capability artifacts. The contract measures the delta caused by a skill,
plugin, agent-guidance file, or trigger-metadata change. It does not certify the
runner or agent harness.

## Evaluation Boundary

Artifact evidence may cover:

- discovery and trigger precision/recall;
- behavior after activation;
- task outcome and deterministic correctness;
- constraint or policy violations caused by the artifact;
- subjective output quality;
- context, token, elapsed-time, and cost overhead.

Authentication, installation, sandbox, process, transport, logging, runner
crashes, broken timeout enforcement, cancellation, recovery, state, and memory
reliability are Agent Harness concerns. Quarantine affected trials instead of
scoring them as artifact failures. A task-level timeout may count only after the
same functioning runtime conditions are proved for both arms.

Separate harness failure from artifact-caused persistence loss. When the paired
harness is functioning and the candidate artifact changes which evidence,
state, provenance, or recovery pointers survive, that delta is capability
behavior and must be scored rather than quarantined.

## Treatment And Parity

Freeze the treatment before execution:

- candidate artifact identity and SHA-256;
- `no-artifact` baseline or immutable prior artifact identity and SHA-256; an
  artifact baseline must have a different fingerprint from the candidate;
- prompt/fixture, verifier, configuration, environment, tools, permissions,
  model, runner, network policy, timeout, and isolation identities;
- clean disposable workspace per arm;
- assertions, rubrics, case set, repetitions, and adoption rule.

Candidate and baseline must differ only by the capability artifact. A missing
baseline, mutable artifact, unproved parity, candidate-only configuration, or
forced trigger nudge makes the comparison inconclusive. A nudge can be a
separate diagnostic arm, never a substitute for the natural treatment.

Protect the comparison from observer effects. Keep arm names, evaluation terms,
rubrics, expected answers, and artifact-path hints out of candidate-visible
prompts and workspaces; do not ask the candidate to report which treatment it
received.
Counterbalance sequential request order (AB/BA) when practical, or record the
unmeasured position effect as a limitation and use an A/A position probe when
order could materially affect the result. For subjective comparison, show
anonymized arms to one blinded judge in the same pass; do not let candidate
self-report substitute for external grading.

## Case Design

Use cases that resemble real work and do not name the target skill unless exact
invocation is the behavior under test. Cover the relevant categories:

- `foundational`: critical must-pass workflows;
- `representative`: ordinary realistic use;
- `paraphrase`: varied wording and context;
- `edge`: difficult, sparse, or conflicting evidence;
- `anti-trigger`: adjacent or out-of-scope work where activation is undesirable.

Freeze held-out trigger cases before tuning. Prefer deterministic end-state or
contract assertions. Exact prose and exact tool order are valid only when they
are contractual. Subjective rubrics require blinded humans or a calibrated,
named model judge and remain secondary to deterministic evidence.

## Persistent-context mechanisms

Use this additional gate when a candidate changes response verbosity, working
notes, persisted state, tool-output projection, transcript compaction, handoff,
or recovery:

- set `scope.persistence_coverage.applicable=true`; omission is accepted only
  for legacy v1 compatibility and proves no persistent-context coverage;
- test presentation brevity separately from evidence persistence;
- require a passing full-history control plus multiple dependent post-boundary
  checkpoints or repeated compactions on the same trajectory;
- make state exactness/precision, atom recall by category, source/recovery
  references, repeated work, false certainty, and authority critical
  deterministic assertions;
- do not promote lossy filtering without content-addressed raw recovery for
  successful and failed outputs; and
- measure the complete pipeline, including preprocessing, note generation,
  compaction, cache effects, downstream calls, and recovery.

Predeclare a task-appropriate efficiency threshold. A shorter visible answer,
projected prompt, or compacted state is not a win without task parity and the
required state, provenance, safety, and recovery checks. Reject a global
default on any candidate-only full-trajectory loss or critical persistence
regression.

The structured coverage block binds the claim to declared cases and assertions:

```json
{
  "applicable": true,
  "trajectories": [
    {
      "id": "dependent-task",
      "full_history_control": {
        "case_id": "trajectory",
        "assertion_id": "full-history-task-success"
      },
      "dependent_boundaries": [
        {"case_id": "trajectory", "assertion_id": "after-boundary-1"},
        {"case_id": "trajectory", "assertion_id": "after-boundary-2"}
      ]
    }
  ],
  "facet_assertions": [
    {
      "facet": "state_exactness",
      "case_id": "trajectory",
      "assertion_id": "state-exactness"
    }
  ]
}
```

Every applicable record must cover these facets exactly once with separate
deterministic assertion references: `presentation_brevity`, `state_exactness`,
`atom_recall_by_category`, `source_references`,
`successful_output_recovery`, `failed_output_recovery`, `repeated_work`,
`false_certainty`, `authority`, and `complete_pipeline_cost`. It must declare a
full-history control and at least two distinct dependent-boundary assertions.
Trajectory references and all facets except presentation/cost must use critical
cases. The scope dimensions must include `task-outcome`, `constraints`, and
`overhead`.

This structural gate proves that the receipt names resolvable, separate checks;
it cannot prove that the runner really shared state across boundaries or that
the evidence files are truthful. Preserve runner-level receipts for that.

## Repetition And Decisions

Agent behavior varies. Three trials per arm is a useful provisional minimum;
five or more, or confidence intervals, are preferable for a consequential
promotion gate. Record per-case outcomes and losses. Do not collapse trigger,
outcome, safety, subjective quality, and overhead into one opaque score.

Predeclare the adoption rule. Every critical candidate case must have zero
failed trials, and the gate requires at least one candidate win. Equivalent
quality with a time/cost reduction must therefore be represented as a declared
overhead case whose frozen assertions produce that win; an all-tie receipt
cannot adopt. `inconclusive` is required when parity, baseline, or sufficient
valid evidence is missing. Preserve the previous artifact for rollback.

## Receipt Schema

The validator accepts one strict JSON object with schema
`capability.evaluation.v1`. Duplicate keys, `NaN`, and infinity are invalid.

Top-level fields:

| Field | Contract |
| --- | --- |
| `schema` | Exactly `capability.evaluation.v1`. |
| `status` | `planned`, `complete`, or `blocked`. |
| `target` | Artifact kind/name plus immutable candidate and baseline identities. |
| `scope` | Falsifiable claim, dimensions, fixed artifact/harness boundary, and optional structured persistence coverage. |
| `environment` | Runner/model versions, hashes, policy, timeout, isolation, and parity proof. |
| `cases` | Unique case IDs, category, critical flag, prompt hash, repetitions, assertions. |
| `adoption_rule` | Critical-case rule plus explicit regression/win thresholds. |
| `subjective_review` | `none`, `blind-human`, `calibrated-model-judge`, or `hybrid`; rubric provenance when used. |
| `results` | Empty while planned/blocked; paired per-case counts when complete. |
| `summary` | Counts derived from declared cases and completed result outcomes. |
| `verdict` | `planned`, `adopt`, `revise`, `reject`, or `inconclusive`. |
| `rationale` | Bounded explanation of the decision. |
| `limitations` | Non-empty limitations for complete or blocked evidence. |
| `rollback` | Concrete rollback path. |

Allowed dimensions are `trigger`, `task-outcome`, `constraints`, `subjective`,
and `overhead`. Assertion types are `deterministic`, `human`, and
`model-judge`. New generic records should explicitly use
`"persistence_coverage": {"applicable": false}` when the additional gate is
not relevant.

Each completed case result contains baseline and candidate counts:

```json
{
  "attempted": 3,
  "passed": 2,
  "failed": 1,
  "quarantined": 0,
  "evidence": ["relative/path/to/receipt.json"]
}
```

The four counts must be non-negative integers; `passed + failed + quarantined`
must equal `attempted`, and paired arms must attempt the declared repetitions.
The validator derives `win`, `loss`, `tie`, or `inconclusive` from the paired
pass/quarantine counts and rejects a contradictory declared outcome. The
top-level summary must exactly match these derived outcomes and quarantined
trial totals. Any failed candidate trial in a critical case is a critical
regression and blocks adoption.

Generate a complete template with:

```bash
python3 "$PLUGIN_ROOT/scripts/evaluation/validate_capability_evaluation.py" --template
```

## Evidence Basis

Reviewed 2026-08-13. These sources inform the contract but are not runtime
dependencies, and no external code is vendored or executed:

- [Anthropic skill-creator at `f17010c`](https://github.com/anthropics/skills/blob/f17010c9bb483898c1d9c9f42dde2b3a98889434/skills/skill-creator/SKILL.md): paired candidate/baseline runs, assertions, held-out trigger cases, repetition, and blind review.
- [OpenAI agent evals](https://developers.openai.com/api/docs/guides/agent-evals) and [graders](https://developers.openai.com/api/docs/guides/graders): real workflow cases, layered graders, trace evidence, and calibrated judges.
- [Open Agent Skills specification at `69ef37e`](https://github.com/agentskills/agentskills/blob/69ef37e9424c0a7ea9dd2293b559e43ec8176379/docs/specification.mdx): discovery metadata, progressive loading, compatibility, and the boundary between structural validation and behavior.
- [Google ADK evaluation guide at `a7584a1`](https://github.com/google/adk-docs/blob/a7584a1dc9c123c838d1ae13dbedbaf02b86441c/docs/evaluate/index.md): outcome/trajectory separation and selectable assertion strictness.
- [Microsoft agent evaluation checklist](https://learn.microsoft.com/en-us/agents/agent-evaluation/evaluation-checklist): versioned baselines, lifecycle reruns, realistic cases, repetitions, and hybrid grading.
- [SkillsBench at `9a1f4dd`](https://github.com/benchflow-ai/skillsbench/blob/9a1f4dd5f7659f75707435da3ce854b6e48321d1/README.md): isolated workspaces, deterministic verifiers, repeated trials, uncertainty, negative deltas, and infrastructure-error handling.
- [AWS sample agent-skill eval at `13b2277`](https://github.com/aws-samples/sample-agent-skill-eval/blob/13b2277b300d2beafa09bbbe425ca0cc41f34c8d/README.md) and [Skilljack Evals at `5d76a69`](https://github.com/olaservo/skilljack-evals/blob/5d76a69b29b67a10a837a661b669406c82b3462f/README.md): artifact/environment fingerprints, disposable workspaces, natural prompts, separate invocation/outcome metrics, and fail-closed baseline parity.

## Interpretation

The validator checks schema, pairing, counts, boundary declarations, and verdict
consistency. It cannot prove artifact hashes were computed honestly, cases are
representative, judges are unbiased, evidence files exist, or the runner is
reliable. Report those as provenance, design, audit, or Agent Harness findings.

Never execute candidate-provided graders, hooks, scripts, or configuration just
because they are named by a receipt. Never grant provider credentials,
permission bypass, global installation, network access, or external side effects
without separate explicit authorization.
