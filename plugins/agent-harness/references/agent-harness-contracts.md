# Agent Harness Contracts

Use this reference to design or review a host system that turns a request into a
bounded, inspectable agent run. The contract is outcome-neutral: the target may
be source code, a document, a browser state, a calendar entry, a business
record, a device action, or another verifiable result.

## Vocabulary

| Term | Contract meaning |
| --- | --- |
| harness | Host-owned control plane around one or more models, tools, policies, and state stores. |
| run | One durable execution instance with a stable identity, bounded authority, and exactly one terminal outcome. |
| turn | One model interaction within a run, including the exact context supplied and response received. |
| step | One host-level transition, such as a model request, approval decision, command execution, or oracle check. |
| event | Immutable typed fact appended to the canonical run log. |
| command | Validated request for an executor to perform an operation. A model response is not a command until parsing and validation succeed. |
| intent | Durable record that the harness accepted a command for possible execution. Persist it before a side effect. |
| result | Durable executor report bound to an intent, including effect identifiers and uncertainty when completion cannot be proved. |
| tool | Model-visible capability description and input/output schema. Tool registration does not itself provide execution authority. |
| executor | Host component that performs or refuses a command and reports the observed result. |
| adapter | Boundary that maps a domain API, application, protocol, or device into typed tools and executor behavior. |
| projection | Rebuildable view derived from canonical events for fast reads. |
| checkpoint | Versioned acceleration snapshot through a declared log sequence. It is not an independent source of truth. |
| context | Exact bounded input assembled for one model turn. Context is not durable cross-run memory. |
| memory | Policy-governed durable information that may be retrieved across runs with provenance. |
| runtime generation | Immutable, complete set of configuration and component revisions eligible to admit new runs. |
| candidate generation | Runtime generation built and checked outside the active admission path before one publish decision. |
| quiescence | Declared condition under which a generation accepts no new work and its in-flight work is drained, cancelled, or migrated. |
| scenario | Versioned initial state, request, constraints, perturbations, and oracle contract used for evaluation. |
| oracle | Procedure that judges post-state, artifacts, or required and forbidden behavior. |
| evidence claim | Assertion paired with its scope, evidence grade, source pointers, and known limits. |

## Required Artifacts

Every implementation or material revision should produce three separately
versioned artifacts. A diagram or README may explain them, but does not replace
their machine-readable fields.

### Design artifact

Suggested schema: `agent_harness.design.v1`.

Record at least:

- harness revision and dependency lock or digests;
- run, turn, step, event, intent, result, and terminal-state schemas;
- model/provider capability negotiation and fallback rules;
- tool registry schemas and concrete executor bindings;
- trust, authority, policy, approval, sandbox, and side-effect rules;
- canonical log, projections, checkpoints, memory, and secret-storage
  boundaries;
- deadlines, token/cost/step limits, concurrency limits, and child-run budgets;
- retry, idempotency, recovery, cancellation, and uncertain-effect behavior;
- adapter-specific preconditions, postconditions, and compensating actions;
- compatibility policy, migrations, observability, and rollback route.

If runtime reconfiguration is in scope, also record an immutable candidate
generation, component and interface revisions, capability set, expected-active
compare-and-swap, one admission commit point, per-run generation binding,
in-flight and late-result policy, quiescence, isolation or quarantine, retained
rollback generation, health gate, and lifecycle evidence. If it is not recorded
and validated, the design does not claim provider, tool, module, or loop hot
swap.

### Evaluation-plan artifact

Suggested schema: `agent_harness.evaluation_plan.v1`.

Record at least:

- the complete versioned system tuple, not only the model name;
- scenario corpus and initial-state reset procedure;
- state, artifact, and procedure oracles;
- baseline, paired ablations, repetitions, seeds, and ordering policy;
- fault-injection schedule and failure taxonomy;
- metrics with exact denominators, uncertainty, and excluded runs;
- release thresholds, blocking failures, and accepted residual risk;
- links to immutable run results and evaluator versions.

### Run-result artifact

Suggested schema: `agent_harness.run_result.v1`.

Record at least:

- `run_id`, optional `parent_run_id`, scenario ID, and system-tuple digest;
- input and initial-environment digests, subject to privacy policy;
- start, end, duration, terminal outcome, and structured reason code;
- limits, actual usage, retries, approvals, and policy decisions;
- accepted intents, executor results, effect identifiers, and unresolved effects;
- produced artifacts and observed post-state evidence;
- oracle results, failure classification, and evidence grade;
- canonical event-log pointer, terminal event ID, and integrity digest;
- redactions, known gaps, evaluator identity, and creation timestamp.

Do not overwrite a completed result to improve an outcome. Append a superseding
evaluation or create a new run and preserve the relationship.

## Validator-Facing Shapes

The bundled gate validates JSON objects with these exact schema discriminators:

| Schema | Required top-level fields |
| --- | --- |
| `agent_harness.design.v1` | `outcome`, `success_criteria`, `non_goals`, `provider_boundary`, `control_loop`, `tools`, `state`, `context`, `policy`, `recovery`, `cancellation`, `observability`, `delegation`, `evaluation_handoff`, `risks` |
| `agent_harness.evaluation_plan.v1` | `system_tuple`, `task_suite`, `variants`, `baselines`, `oracles`, `repeated_trials`, `fault_injection`, `analysis`, `residual_risks`, `metrics`, `scenarios`, `release_gates`, `provenance` |
| `agent_harness.run_result.v1` | `run_id`, `scenario_id`, `system_tuple`, `status`, `metrics`, `trace_ref`, `terminal`, `failures`, `evidence`, `usage`, `artifact_versions` |
| `agent_harness.run_result.v2` | All v1 fields plus required `runtime_generation`; use for every result supporting a runtime-reconfiguration claim |

Important nested contracts:

- Design `outcome` declares `description`, `workload`, execution `mode`, trust
  boundaries, and side effects. `control_loop.bounds` includes positive
  `max_steps` and `wall_time_seconds`; states, guarded transitions, effects,
  invariants, and terminal outcomes are explicit. Terminal outcomes include
  `succeeded`, `failed`, and `cancelled`.
- `provider_boundary` declares required capabilities plus explicit unsupported
  and degraded behavior. `delegation` always records an `enabled` decision and
  rationale; enabled delegation also sets positive child and depth bounds.
- Design `runtime_reconfiguration` is optional for backward compatibility. Its
  absence means the artifact makes no runtime-reconfiguration claim. When
  present it strictly declares `supported` and a rationale. A supported design
  also defines `candidate_generation`, `activation`, `run_binding`, `isolation`,
  `rollback`, and `evidence`; an unsupported design must not include activation
  claims. Unknown fields inside this optional block are invalid rather than
  silently ignored.
- A supported candidate generation identifies its config revision and digest,
  provenance, and unique components with stable IDs, kinds, revisions,
  interface versions, capability sets, compatibility policy, and state-transfer
  behavior. It covers at least provider adapter, tool registry, executor, policy,
  context builder, control loop, and state store; the union of provider-adapter
  capabilities must satisfy `provider_boundary.required_capabilities`.
  Activation binds compare-and-swap to the expected active generation,
  identifies each activation attempt, bounds readiness, uses one admission
  commit point, and monitors a bounded post-activation health window. A
  pre-commit failure preserves the expected active generation. A post-commit
  failure rolls back only by comparing the current active generation and
  activation attempt with the failed candidate; a stale health result cannot
  overwrite a newer generation.
- Run binding separately selects `pin` or explicit migration and a retirement
  mode. Retirement closes old admission as part of the activation commit,
  declares quiescence, drain or cancellation, timeout behavior, cancellation
  acknowledgement, and teardown completion. Rollback retains the prior
  generation until health is closed, rollback is terminal, leases are zero, and
  teardown is complete. It describes failed-generation runs and external-effect
  reconciliation separately because runtime rollback is not a transaction over
  the outside world.

The supported block uses these closed key sets:

| Object | Required keys |
| --- | --- |
| `runtime_reconfiguration` | `supported`, `rationale`, `candidate_generation`, `activation`, `run_binding`, `isolation`, `rollback`, `evidence` |
| `candidate_generation` | `id_schema`, `config_revision`, `config_digest`, `compatibility_policy`, `state_migration`, `provenance`, `components` |
| each component | `id`, `kind`, `revision`, `interface_version`, `capabilities`; kind is one of `provider_adapter`, `tool_registry`, `executor`, `policy`, `context_builder`, `control_loop`, `state_store`, `memory_store`, `sandbox`, `module`, `scheduler`, `session` |
| `activation` | `candidate_validation`, `attempt_id_schema`, `expected_active_generation`, `compare_and_swap: true`, `readiness_gate`, positive `readiness_timeout_seconds`, `commit_point`, `health_gate`, positive `health_window_seconds`, `pre_commit_failure_behavior: preserve_expected_active_generation`, `post_commit_failure_behavior: rollback_via_compare_and_swap` |
| `run_binding` | `admission`, `binding_policy: pin|explicit_migrate`, `late_result_fencing`, `lease_release`, and `retirement`; `migration_contract` is required for `explicit_migrate` |
| `retirement` | `admission_closed_at_commit: true`, `mode: drain|cancel|drain_then_cancel|migrate`, `quiescence_condition`, positive `timeout_seconds`, `timeout_behavior`, `cancel_acknowledgement`, `teardown_completion` |
| `isolation` | `boundary_type: same_process|process|vm|container|wasm`, `trust_model: reviewed_trusted|untrusted`, `authority_surfaces`, `failure_containment`, `quarantine`, `enforcement_evidence`; untrusted code cannot use `same_process` |
| `rollback` | `retain_prior_generation: true`, `expected_failed_generation`, `target_generation`, `activation_attempt_binding`, `compare_and_swap: true`, positive `timeout_seconds`, `trigger`, `receipt`, `failed_generation_runs`, `external_effects`, and `release_condition` |
| `rollback.release_condition` | all of `health_window_closed`, `rollback_terminal`, `leases_zero`, `teardown_complete` set to `true` |
| `evidence` | `event_schema`, `generation_binding`, `activation_receipt`, `rollback_receipt` |

An explicit restart-only design uses only `supported: false` and `rationale`.
It is valid, while attaching activation fields to that decision is not.
- Every tool declares model-visible input/output schemas, effect class,
  authority ceiling, timeout, approval mode, and idempotency mode. External or
  irreversible tools cannot use `approval: never` and must define
  reconciliation.
- Design `state` names the state schema, canonical log, checkpoint, replay,
  resume, and reconciliation policy.
  `context` supplies trust-labelled sources, a positive token budget, and a
  compaction policy. Recovery, cancellation, redaction, evaluation claims, and
  residual risks stay explicit.
- Enabled delegation includes bounded child count and depth plus a child
  authority, tool-scope, result, and cancellation contract.
- Each evaluation `system_tuple` component is `{ "id": "...", "version":
  "..." }` for harness, provider, model, prompts, tools, policy, context,
  environment, and evaluator. The task suite and each oracle are versioned.
- The task suite defines reset, seed, and ordering procedures. The plan declares
  fault injection, uncertainty analysis, exclusion policy, and residual risks
  before interpreting results. Scenario IDs and release-gate metrics must
  resolve to declared definitions.
- An evaluation plan includes a deterministic or human oracle; an LLM-only
  judge is invalid. It covers policy denial, context pressure, recovery, and
  cancellation scenarios at minimum. One trial is accepted with a warning but
  cannot establish repeated reliability.
- Evaluation `runtime_reconfiguration` is also optional. When it sets
  `claimed: true`, the scheduled suite covers invalid candidates, capability
  loss, partial initialization, concurrent generations, late results,
  post-activation failure, stale rollback, rollback, an external effect before a
  failed health gate, and isolation leakage. Blocking zero gates cover missing
  or incorrect generation evidence, partial activation, unauthorized capability
  change, stale rollback overwrite, false rollback success, false external-effect
  reporting, and isolation leakage.
  Each scheduled reconfiguration scenario names non-empty `fault_injection_ids`
  and `oracle_ids`. Every linked injection declares the exact scenario class it
  exercises, every reference resolves to a declared injection or oracle, and at
  least one linked oracle is deterministic or human; scenario tags or an
  unrelated deterministic oracle are not fault-injection evidence.

The evaluation block uses `claimed`, `rationale`, and, when claimed,
`design_ref` plus `result_schema: agent_harness.run_result.v2`. A claimed plan
schedules all of these exact classes:
`reconfiguration_invalid_candidate`, `reconfiguration_capability_loss`,
`reconfiguration_partial_initialization`,
`reconfiguration_concurrent_generations`, `reconfiguration_late_result`,
`reconfiguration_post_activation_failure`, `reconfiguration_stale_rollback`,
`reconfiguration_rollback`, `reconfiguration_external_effect_after_commit`, and
`reconfiguration_isolation_leak`. It declares blocking zero gates for
`generation_misbinding_count`, `generation_evidence_gap_count`,
`partial_activation_count`, `unauthorized_capability_change_count`,
`stale_rollback_overwrite_count`, `false_rollback_success_count`,
`external_effect_misreport_count`, and `isolation_leak_count`.
- A run result uses one terminal outcome from this reference, preserves terminal
  timing/reason/integrity, a trace pointer, structured failures, oracle and
  post-state evidence, policy/effect records, unresolved effects, evidence
  grade, and redactions. It records non-negative tokens, latency, and cost and
  identifies the design, evaluation-plan, and scenario versions used to judge
  it. `succeeded` is invalid if an oracle failed, a blocking failure exists, or
  an effect remains unresolved.
- Every v2 run result records `runtime_generation` with
  `design_ref`, `evaluation_plan_ref`, `binding_policy`,
  `admitted_generation_id`, `terminal_generation_id`, `activation_attempt_id`,
  `activation_receipt_ref`, `trace_generation_binding_ref`, and
  `effect_generation_binding_ref`. A `pin` result has identical admitted and
  terminal generation IDs and cannot claim migration. An `explicit_migrate`
  result has distinct IDs and adds `migration_receipt_ref`. V1 remains valid for
  backward compatibility but cannot support a runtime-reconfiguration release
  claim.

Run the gate from either harness skill:

```bash
python3 "$PLUGIN_ROOT/scripts/harness/validate_harness_artifact.py" <artifact-path> --json
```

The gate checks completeness and selected unsafe combinations. It does not
execute a harness, inspect containment, validate source claims, or prove an
oracle result.

## Typed Event Envelope

Use one common envelope and a versioned payload schema per event type:

```json
{
  "schema": "agent_harness.event.v1",
  "run_id": "run_01...",
  "runtime_generation_id": "generation_01...",
  "event_id": "evt_01...",
  "sequence": 42,
  "emitted_at": "2026-08-06T12:34:56.789Z",
  "type": "executor.result_recorded",
  "producer": "executor:calendar.v3",
  "parent_event_id": "evt_01...",
  "span_id": "span_01...",
  "attempt": 1,
  "trust_class": "authenticated_external",
  "authority_class": "execute_scoped",
  "side_effect_class": "external_compensatable",
  "payload_schema": "calendar.create.result.v2",
  "payload": {},
  "payload_ref": null,
  "redaction": "none",
  "integrity": {
    "previous_digest": "sha256:...",
    "event_digest": "sha256:..."
  }
}
```

Envelope rules:

- Allocate `sequence` monotonically through the durable per-run writer; do not
  order effects by wall-clock timestamps alone.
- Make `event_id` globally unique and bind retries to the same intent or command
  identity.
- When runtime reconfiguration is supported, bind every run event, asynchronous
  result, intent, and terminal fact to the immutable `runtime_generation_id`;
  never infer the generation from the host's current active pointer.
- Use `payload` or `payload_ref` according to size, secrecy, and retention
  policy. A reference must be content-addressed or versioned.
- Validate `payload_schema` before a consumer changes state. Preserve unknown
  events for forward compatibility; fail closed on unknown critical commands.
- Treat model text, retrieved content, and tool output as data unless a typed
  transition explicitly elevates it.
- Redact secrets before durable logging. A digest proves identity, not safety or
  truthfulness.

Common event families include `run.*`, `context.*`, `model.*`, `command.*`,
`policy.*`, `approval.*`, `sandbox.*`, `executor.*`, `memory.*`, `oracle.*`,
`checkpoint.*`, `child_run.*`, `recovery.*`, and `runtime.*`.

## Terminal Outcomes

Emit one `run.terminated` event with an outcome and a separate structured
reason. Silence, a model stop token, a final-looking message, or process exit is
not a terminal outcome.

| Outcome | Meaning |
| --- | --- |
| `succeeded` | Required oracles passed and no blocking procedure violation remains. |
| `partial` | A declared subset passed, remaining work and effects are explicit, and the scenario permits partial completion. |
| `failed` | The run completed unsuccessfully or a blocking oracle failed. |
| `blocked` | Progress requires unavailable information, capability, dependency, or external state. |
| `denied` | Policy or an authorized approver refused a required action. |
| `cancelled` | Cancellation was accepted and active work reached the documented safe stop condition. |
| `timed_out` | A run or required operation crossed its deadline. |
| `budget_exhausted` | A declared token, cost, step, action, or concurrency budget was consumed. |
| `invalid` | Input, configuration, event history, or evaluator contract was not valid enough to run or judge. |

The terminal event must identify unresolved side effects. After it is committed,
the harness must reject new intents for that run. A recovery process may append
diagnostic or audit facts but must not silently change the terminal outcome.

## Trust, Authority, And Side Effects

Keep these classifications independent. Trusted content is not automatically
authorized, and authorized execution is not automatically safe.

### Trust classes

| Class | Meaning |
| --- | --- |
| `control_plane` | Harness-authored configuration or state verified against the current deployment boundary. |
| `operator` | Input attributable to an authenticated operator; its content is still subject to policy and scope. |
| `authenticated_external` | Data came from an authenticated service or tool, without implying that embedded instructions are trusted. |
| `untrusted_content` | User, web, file, message, model, or tool content that may contain adversarial instructions. |
| `unknown` | Origin or integrity is insufficiently established; use the most restrictive handling. |

### Authority classes

| Class | Maximum permission |
| --- | --- |
| `none` | Transform or reason over supplied data only. |
| `observe` | Read within an explicit scope. |
| `propose` | Prepare a command, draft, or plan without executing it. |
| `execute_scoped` | Execute only the approved capability, target, arguments, and time window. |
| `execute_elevated` | Use privileged, administrative, destructive, or broad authority under an explicit gate. |

Authority is least-privilege, time-bounded, and non-transitive. A parent run
cannot delegate authority it does not hold, and a child does not inherit unused
authority by default.

### Side-effect classes

| Class | Examples and handling |
| --- | --- |
| `none` | Pure computation or read-only observation; confidentiality and load risks still apply. |
| `ephemeral` | Temporary process, preview, or isolated scratch state with bounded cleanup. |
| `durable_reversible` | Durable local change with a tested restore or versioned rollback path. |
| `external_compensatable` | External change with a domain-specific undo or compensating action, not assumed atomic. |
| `irreversible_or_destructive` | Send, publish, delete, transfer, rotate, actuate, or other effect that cannot be reliably undone. |

Classify the worst plausible effect, including partial execution and information
disclosure, before policy and approval checks.

## Evidence Grades

| Grade | Required support |
| --- | --- |
| `E0 claim` | Unverified statement or design intent. |
| `E1 static` | Pinned code, schema, configuration, or primary documentation was inspected. |
| `E2 synthetic` | Deterministic checks or public-safe fixtures exercised the claimed path. |
| `E3 controlled-run` | The versioned system ran in a controlled environment with trace and pre/post-state evidence. |
| `E4 replicated` | Independent or repeated controlled runs reproduced the result across the declared scenario slice. |
| `E5 operational` | Privacy-reviewed operational evidence supports the claim under a declared deployment window and population. |

Higher grades do not broaden scope. An `E5` observation for one deployment does
not prove portability, and an `E1` architecture observation does not prove
runtime behavior. Every claim should retain its scenario, system tuple, date,
source, and uncertainty.
