# Agent Harness Evaluation

Use this reference to evaluate a complete harnessed system, compare a mechanism
against a baseline, or gate a release. Evaluation is outcome-neutral: use the
same discipline for code changes, research artifacts, business workflows,
browser tasks, messages, records, schedules, and device operations.

Work sampled-first. Start with the cheapest representative scenario slice and
direct oracle that can falsify the claim. Persist plans, manifests, schemas,
and run receipts only for a repeated campaign, release gate, or durable
independent review with a named consumer and acceptance action. Report a
bounded incident or sampled ablation inline when no durable consumer exists.
Keep `created`, `adopted`, `executed`, and `accepted` as separate states.

## Version The Complete System Tuple

A result belongs to the whole system, not to a model or harness name alone.
For a warranted persistent evaluation, record an immutable manifest or digest
for:

```text
S = (
  harness source and configuration,
  active runtime generation and candidate-generation manifest,
  runtime origin and catalog/tool admission inputs,
  model identity and model parameters,
  provider endpoint, API revision, and capability adapter,
  system prompts, context builder, retrieval, and memory state,
  tool registry schemas and executor/adapter revisions,
  policy, approval, sandbox, credentials scope, and authority,
  runtime, dependencies, OS/container, network, and external-service versions,
  scenario corpus, initial-state fixture, and oracle revisions,
  deadlines, token/cost/step/action/concurrency budgets,
  seeds, sampling controls, scheduling policy, and evaluation runner
)
```

A standalone prompt diagnostic belongs to a different tuple unless its runtime
origin, generation, and admission inputs match the evaluated task. It cannot
substitute for the task's recorded catalog or for independently captured tool
schemas.

Record unavailable or mutable components as such. If one component changes,
the tuple changes. Comparisons may still be useful, but do not call them the
same system or attribute the delta solely to the model.

## Paired Ablations

To test one harness mechanism, run baseline and variant against paired scenario
instances with all feasible tuple components held constant.

1. State a falsifiable hypothesis and the exact mechanism toggled.
2. Reset to the same verified initial state before each attempt.
3. Use matched scenario IDs, budgets, model/provider settings, and oracle
   revisions.
4. Randomize or counterbalance baseline/variant order to reduce temporal and
   service-load bias.
5. Repeat enough paired trials to expose nondeterminism; preserve every run,
   including infrastructure and invalid outcomes.
6. Report paired deltas, confidence or uncertainty, scenario-level results,
   resource changes, and shifts between failure classes.
7. Test material interactions separately. A multi-change bundle does not
   identify which mechanism caused the delta.

Declare exclusions before looking at outcomes when possible. Never discard a
run because it makes the preferred variant look worse. A causal claim is scoped
to the manipulated mechanism and tested tuple only.

## Post-State And Procedure Oracles

Use independent, deterministic checks where practical. A final model answer is
an artifact to judge, not proof that the task succeeded.

| Oracle | Question | Examples |
| --- | --- | --- |
| post-state | Is the intended world state true? | Tests pass in the changed checkout; target record has the expected revision; calendar contains one event with exact attendees. |
| artifact | Does the produced object meet its contract? | Schema-valid patch, report with required evidence, draft with correct recipients, parseable export. |
| procedure | Were required and forbidden actions respected? | Approval preceded send; no forbidden path or network target was accessed; limits and recipient scope held. |
| reconciliation | Are external effects and duplicates accounted for? | Service effect ID exists once; partial writes are identified; compensation state is known. |

Define success as an explicit expression over these oracles. Safety-critical
procedure failure should remain blocking even when the desired post-state was
reached. When only a human can judge quality, use a blinded rubric, retain
adjudication and disagreement, and keep subjective quality separate from
mechanical correctness.

## `pass@k` Versus `pass^k`

These metrics answer different questions.

- `pass@k` asks whether at least one of `k` attempts succeeds. With `n`
  sampled candidates and `c` successes, the common unbiased estimator is
  `1 - C(n-c, k) / C(n, k)` when `n >= k`. It measures opportunity to select or
  retry, not single-run reliability.
- `pass^k` asks whether all `k` required attempts succeed. Estimate it directly
  from prespecified groups of `k` runs. Computing `p^k` from a marginal pass
  rate assumes independent, identically distributed attempts and must be
  labeled as a model, not an observation.

Always report `k`, sampling and selection policy, retry visibility, number of
scenarios, attempts per scenario, and oracle. Shared outages, cached state,
provider routing, adaptive retries, and scenario difficulty make attempts
dependent. A system can improve `pass@k` while remaining unsuitable for a
workflow that requires every operation to succeed.

## Scenario Matrix

Cover behavior by risk and mechanism, not only by an average benchmark score.

| Dimension | Required slices |
| --- | --- |
| outcome domain | code, structured data, document/research, browser/UI, communication, external record or device |
| authority | reason-only, observe, propose, scoped execute, elevated execute |
| side effect | none, ephemeral, durable reversible, external compensatable, irreversible/destructive |
| horizon | single turn, short loop, long run, resumed run, scheduled or delayed continuation |
| interaction | no tool, one tool, multiple tools, parallel tools, child run, human approval |
| input trust | control-plane, operator, authenticated external, untrusted content, mixed or unknown |
| state | clean, stale, conflicting, partially complete, duplicate, already satisfied |
| dependency | healthy, slow, rate-limited, unavailable, malformed, partially successful |
| concurrency | isolated, competing run, callback race, shared quota, shared external target |
| runtime generation | fixed, invalid candidate, old/new concurrent, draining, rolled back, rollback failed |
| termination | success, partial, denial, block, cancel, timeout, budget exhaustion, invalid input |

Tag each scenario with expected applicable mechanisms and worst plausible
effect. Aggregate only after reporting the safety-critical and rare slices that
an average would hide.

## Fault Injection

Inject failures at durable boundaries, with public-safe fixtures and reversible
targets:

- provider timeout, rate limit, stream truncation, duplicate response, invalid
  tool call, and usage correction;
- executor unavailable, slow response, malformed result, duplicate callback,
  partial external success, and stale precondition;
- crash before intent, after intent, after effect but before result, during
  checkpoint, and before terminal commit;
- delayed, expired, mutated, denied, and duplicate approval;
- sandbox denial, credential expiry, network partition, disk-full, and log
  append failure;
- cancellation during model stream, executor action, child run, reconciliation,
  and terminal transition;
- corrupt checkpoint, stale projection, unavailable memory, poisoned retrieval,
  and secret-like content in logs;
- child-run timeout, orphan, over-budget request, malformed result, and late
  completion;
- wall-clock jump, exhausted budget, output explosion, and concurrent target
  mutation.

When runtime reconfiguration is claimed, add all of these fault classes to the
scheduled suite rather than merely declaring them in prose:

- candidate schema, dependency, interface, or capability validation failure;
- provider capability loss and partial tool or module initialization;
- old and new runs executing concurrently while admission changes;
- late provider, executor, child-run, watcher, or health callback from the old
  generation;
- post-activation health failure, a stale G2 rollback racing after G3 activates,
  rollback timeout, and rollback failure;
- an external effect emitted by the candidate before its health gate fails;
- namespace, resource, filesystem, network, or credential leakage across the
  declared isolation boundary.

For every such scenario, bind its exact class to one or more declared fault
injection IDs and bind the outcome to declared oracle IDs, including at least
one deterministic or human oracle for that scenario. A class label without an
executable injection and resolving non-LLM oracle is coverage metadata, not
evidence.

The oracles must reconstruct which generation admitted each run, intent,
callback, effect, and terminal event. Test that a rejected candidate never
changes admission, an active run never changes generation implicitly, no mixed
component set is published, the old generation is retained until leases drain,
stale rollback cannot overwrite a newer generation, and rollback evidence does
not claim that external effects were reversed. In v2 results, verify the design
and evaluation references as well as binding semantics: pin keeps admitted and
terminal generation IDs equal; explicit migration changes them only with a
migration receipt.

Verify both the terminal outcome and the invariant: no unauthorized effect,
bounded retries, reconciled or explicitly unknown effects, reconstructable
history, and no false success.

## Failure Taxonomy

Assign one primary cause and any contributing factors. Keep cause separate from
terminal outcome, user-visible symptom, and retry decision.

| Class | Boundary |
| --- | --- |
| `input_invalid` | Request, scenario, or initial state cannot satisfy its declared contract. |
| `planning_or_context` | Required information was omitted, corrupted, or used incorrectly before a command. |
| `model_protocol` | Provider/model response cannot be interpreted under the negotiated protocol. |
| `schema_or_registry` | Capability ID, version, arguments, or result violates the registered contract. |
| `capability_missing` | Declared operation has no available compatible executor or dependency. |
| `policy_or_authority` | Intent exceeds policy, trust handling, or delegated authority. |
| `approval` | Approval is absent, denied, expired, or does not bind the final intent. |
| `sandbox_or_isolation` | Runtime containment prevents or fails to contain execution. |
| `executor_or_adapter` | Concrete operation fails before a confirmed effect. |
| `effect_partial_or_unknown` | External state may have changed but completion or compensation is unresolved. |
| `state_or_concurrency` | Preconditions are stale, conflicting, duplicated, or raced. |
| `recovery_or_idempotency` | Resume, replay, reconciliation, or duplicate control violates the contract. |
| `runtime_reconfiguration` | Candidate validation, activation, generation binding, quiescence, health, isolation, or rollback violates its lifecycle contract. |
| `cancellation_or_bounds` | Stop propagation or a declared resource/deadline limit fails. |
| `oracle_or_evaluator` | Judgement is invalid, nondeterministic, contaminated, or unavailable. |
| `infrastructure` | Host, storage, network, or service failure sits outside the mechanism under test. |

Do not relabel an infrastructure failure as success. Report it in the denominator
policy and rerun only under a prespecified rule.

## Trace, Telemetry, And Evaluation

| Surface | Purpose | Required discipline |
| --- | --- | --- |
| trace | Reconstruct one run's causal transitions and effects. | Typed events, stable IDs, sequence, spans, redaction, and integrity. |
| telemetry | Operate a population of runs over time. | Aggregation, sampling policy, privacy controls, retention, and alert definitions. |
| evaluation | Judge a versioned system against scenarios and oracles. | Frozen tuple, denominators, oracle versions, comparison design, and immutable results. |

Evaluation may consume traces, and telemetry may identify scenarios, but neither
is interchangeable with the other. Sampled telemetry cannot prove a specific
run's history. A detailed trace cannot establish population reliability.
Changing an evaluator must create a new judgement linked to the old result, not
rewrite the run. Keep secrets and unnecessary model internals out of all three
surfaces.

In retrospective trace analysis, duplicate status polls are leads to inspect,
not independent work or failures. Deduplicate mirrored records across
compaction boundaries by stable event identity or a documented fingerprint.
Cumulative token counters copied into several snapshots are not unique tokens
and are not billed-token evidence; use provider billing or usage receipts for a
billing claim. Audits are event-triggered only: use a named event, incident, or
explicit review request, never an always-on observer.

## Release Gates

Define numeric thresholds and zero-tolerance conditions before the release run.
At minimum gate:

- correctness: required post-state and artifact oracle thresholds by scenario
  slice;
- procedure safety: zero unauthorized, unapproved, out-of-scope, or falsely
  reported effects in the critical suite;
- recovery: bounded restart, reconciliation, duplicate suppression, and
  uncertain-effect handling at every injected crash point;
- cancellation and bounds: deadlines and all budgets stop new work and reach a
  documented safe terminal state;
- observability: every run has a reconstructable terminal event, system tuple,
  intent/result chain, and redaction result;
- compatibility: supported provider, executor, schema, projection, and stored
  event migrations pass;
- runtime reconfiguration, when claimed: zero generation misbindings, partial
  activations, missing generation evidence, unauthorized capability changes,
  stale rollback overwrites, false rollback successes, external-effect
  misreports, and isolation leaks; bounded drain, health, teardown, and rollback
  complete with receipts;
- regression: paired results do not cross declared quality, safety, latency, or
  cost limits;
- provenance: source revisions, fixtures, evaluator, exclusions, and evidence
  grade are complete and public-safe.

A release gate is a decision rule, not a marketing score. Preserve failed gate
evidence, name the owner and expiry of any exception, and require a new tuple
and evaluation after a material fix.
