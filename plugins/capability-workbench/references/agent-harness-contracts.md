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

Important nested contracts:

- Design `outcome` declares `description`, `workload`, execution `mode`, trust
  boundaries, and side effects. `control_loop.bounds` includes positive
  `max_steps` and `wall_time_seconds`; states, guarded transitions, effects,
  invariants, and terminal outcomes are explicit. Terminal outcomes include
  `succeeded`, `failed`, and `cancelled`.
- `provider_boundary` declares required capabilities plus explicit unsupported
  and degraded behavior. `delegation` always records an `enabled` decision and
  rationale; enabled delegation also sets positive child and depth bounds.
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
- A run result uses one terminal outcome from this reference, preserves terminal
  timing/reason/integrity, a trace pointer, structured failures, oracle and
  post-state evidence, policy/effect records, unresolved effects, evidence
  grade, and redactions. It records non-negative tokens, latency, and cost and
  identifies the design, evaluation-plan, and scenario versions used to judge
  it. `succeeded` is invalid if an oracle failed, a blocking failure exists, or
  an effect remains unresolved.

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
`checkpoint.*`, `child_run.*`, and `recovery.*`.

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
