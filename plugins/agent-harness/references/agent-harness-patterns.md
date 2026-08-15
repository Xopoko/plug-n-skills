# Agent Harness Patterns

Use these patterns when implementing or reviewing an agent host. They define
separable responsibilities and recovery invariants rather than a universal
architecture. Select only the mechanisms justified by the target domain and
validate the composed system.

## Deterministic Host Loop

Keep control flow in the harness. A model proposes; the host validates,
authorizes, executes, records, and decides whether the run continues.

```text
persist run.started
while run is active:
    recover projection from canonical events
    check cancellation, deadline, and budgets
    if the externally verified requested outcome already holds and no named risk threatens it:
        append one succeeded terminal event and stop
    assemble and record the exact bounded model context
    call the negotiated provider capability and record its response
    parse proposals into typed commands; reject invalid proposals
    for each accepted command:
        classify trust, authority, and worst plausible side effect
        evaluate policy, approval, and sandbox gates independently
        persist durable intent with a stable idempotency key
        execute or reconcile the intent
        persist the typed result and observed effect identifiers
    evaluate state, artifact, and procedure oracles
    either append the next transition or one terminal event
```

Use a single durable writer per run, or compare-and-swap on the next sequence,
so concurrent callbacks cannot invent two histories. Make scheduling,
selection, limit checks, and terminal-state transitions deterministic for the
same event history. Record provider nondeterminism instead of pretending it is
host determinism.

## Model And Provider Capability Boundary

Put provider-specific request formats, streaming records, tool-call encodings,
reasoning controls, token accounting, and error classes behind a versioned
adapter. Negotiate supported capabilities at run start and record the result.

- Represent absence explicitly; do not emulate an unsupported capability
  without naming and evaluating the emulation.
- Normalize only semantics the host can preserve. Retain vendor extensions in
  namespaced fields when they matter to replay or evaluation.
- Keep model identity, provider endpoint, API revision, parameters, and adapter
  revision in the system tuple.
- Test truncated streams, duplicate tool calls, out-of-order callbacks, and
  usage corrections at this boundary.

## Registry And Schema Versus Executor

A registry answers what the model may request. An executor answers what the
host can actually do now.

- Registry entries contain a stable capability ID, schema version, description,
  input/output schemas, and declared side-effect class.
- Executor bindings contain availability, credentials reference, concrete
  target scope, policy hooks, timeout, idempotency behavior, and result schema.
- Resolve a registry entry to exactly one authorized executor revision before
  persisting intent.
- Refuse schema-valid commands when the binding, authority, dependency, or
  target precondition is absent.

This separation supports dry-run registries, remote executors, domain-specific
approval, and honest capability reporting without granting execution through
prompt text.

## Runtime Generations And Reconfiguration

Treat a live configuration change as a versioned admission and lifecycle
protocol, not as file replacement or an unload callback. A coherent runtime
generation contains the configuration digest, provider adapters, tool registry
and executor bindings, policy, context builder, loop revision, state store, and
every interface or dependency version needed by an admitted run.

```text
candidate = build immutable generation outside the active path
validate schemas, dependencies, capabilities, isolation, and migrations
if active_generation != candidate.expected_active: reject stale candidate
stage candidate, bound readiness, and retain the last-known-good generation
atomically publish candidate for new admissions and close old admission
bind each new run and callback to that generation
monitor a bounded post-activation health window
on failure CAS only failed generation + activation attempt to retained target
if a newer generation is active, reject the rollback as stale
pin or explicitly migrate bindings; independently drain/cancel retirement
await teardown and release the old generation only after its leases reach zero
```

- Negotiate capabilities per generation. Capability loss is a new compatibility
  decision, never a silent degradation for already admitted runs. Validate that
  the candidate provider adapters still supply every required provider-boundary
  capability before activation.
- Prefer pinning an in-flight run to the generation it captured. A migration is
  a typed state transition with compatibility checks, a durable receipt, and
  its own failure and rollback behavior; pointer reassignment is not migration.
- Separate binding from retirement. Pinning says which generation an admitted
  run uses; drain, cancel, or drain-then-cancel says how the old generation
  reaches quiescence after admission closes. Bound the retirement, require
  cancellation acknowledgement or fencing at timeout, and await teardown.
- Fence every late provider, tool, child-run, watcher, and health callback by
  both run ID and generation ID. A current callback cannot complete an old
  intent, and an old callback cannot mutate the current generation.
- Serialize refresh requests or coalesce them behind one runner. This prevents
  competing rebuilds but does not by itself make a multi-component activation
  atomic.
- Await asynchronous startup, health, quiescence, and teardown. Starting cleanup
  in reverse order does not prove that cleanup completed in that order.
- Keep the prior generation reachable until the health window is closed,
  rollback is terminal, leases are zero, and teardown is complete. A candidate
  that fails before commit leaves the expected active generation unchanged. A
  candidate that fails after commit rolls back only through CAS bound to its
  failed generation and activation attempt; a stale rollback cannot overwrite
  a later activation. A failed rollback is a distinct terminal lifecycle result.
- Separate lifecycle ownership from security isolation. Dependency scopes,
  namespaces, and reversible callbacks do not contain untrusted code; enforce
  process, runtime, container, filesystem, network, and credential boundaries
  outside the module system where the threat model requires them.
- Runtime rollback changes host routing and components. Durable or external
  effects produced before it remain subject to intent, idempotency,
  reconciliation, and compensation contracts.
- Make run evidence executable, not decorative: a reconfiguration scenario
  resolves to fault-injection and oracle IDs, while its v2 result resolves to
  the design, evaluation plan, activation receipt, generation-bound trace, and
  effect evidence. Pin keeps one generation ID through terminal; migration
  requires different IDs and a durable receipt.

This protocol supports a narrow route-level hot swap without claiming that
arbitrary module code, local mutable state, or external effects can be replaced
transactionally. Prefer a controlled restart when the candidate cannot satisfy
the compatibility, state-transfer, isolation, or quiescence contract.

## Canonical Append-Only Log, Projections, And Checkpoints

Treat the append-only typed event log as the canonical run history.

- Build status pages, queues, context state, usage totals, and summaries as
  projections that can be recreated from events.
- A checkpoint declares its schema, source run, `through_sequence`, source
  digest, and projection digest. Ignore or rebuild it when any value mismatches.
- Record migrations as new versioned projections; do not rewrite old events to
  fit a new reader.
- Store large or secret payloads behind retained, access-controlled references
  while keeping a redacted event and integrity digest.
- Make compaction preserve the evidence needed for terminal results, effect
  reconciliation, audit, and configured deletion obligations.
- Create persistent plans, schemas, manifests, and receipts only for a named
  downstream consumer. Record `created`, `adopted`, `executed`, and `accepted`
  as distinct lifecycle states; do not infer consumption from file creation.
- Generate a validation receipt last and exclude the receipt plus its derived
  files from the hash universe it attests.

## Context, Working State, And Memory

Keep three surfaces distinct:

| Surface | Lifetime | Rule |
| --- | --- | --- |
| model context | One turn | Record the exact bounded input or a privacy-safe digest and construction manifest. |
| working projection | One run | Rebuild from canonical events; summaries are derived and may be stale. |
| durable memory | Across runs | Admit, retrieve, update, expire, and delete through explicit policy with provenance. |

Retrieved memory is untrusted input until validated for the current run. A
model request to remember something is a proposal, not a memory write. Record
source, subject, confidence, retention, access scope, supersession, and deletion
state. Do not use a conversation summary as the sole record of side effects or
operator authority.

## Policy, Approval, And Sandbox

Model these as independent gates:

- policy decides whether a typed intent is allowed under rules and run scope;
- approval records an authorized actor's decision about a specific intent;
- sandbox limits what the executing process can reach even after authorization;
- executor checks domain preconditions and enforces the concrete operation.

Bind an approval to command digest, target, arguments, authority, expiry, and
maximum side effect. Material mutation invalidates approval. Sandbox denial is
an execution result, not retroactive policy denial. Policy allowance must not
disable sandboxing, and sandbox access must not imply policy allowance.

## Durable Intent, Result, And Idempotency

Persist intent before starting a side effect. Give every accepted command a
stable `command_id` and domain-appropriate idempotency key. Bind every result to
that identity and record external effect IDs, observed post-state, and whether
completion is certain.

Exactly-once execution is rarely available across a crash boundary. Prefer an
outbox or transactional handoff where possible; otherwise combine at-least-once
delivery with executor idempotency, status reconciliation, duplicate detection,
and compensation. A retry with a new key is a new effect, not recovery.

If a crash occurs after the effect but before the result is durable, recover by
querying the domain with the original idempotency key or effect identifier. If
the domain cannot answer, terminate or pause with `effect_unknown`; never label
the retry safe from lack of evidence.

## Recovery, Cancellation, And Bounds

Define recovery for every durable boundary: before intent, after intent, during
execution, after effect, after result, during projection, and during terminal
commit.

- Resume from canonical events and reconcile unresolved intents before asking
  the model for another action.
- Make retry limits depend on structured error class and new evidence. Do not
  repeat identical failures indefinitely.
- Check run deadline, provider deadline, tool timeout, steps, actions, tokens,
  cost, output size, concurrency, and child-run budgets at durable boundaries.
- Treat cancellation as a state machine: requested, accepted, executor stop or
  quarantine, reconciled effects, then terminal `cancelled`.
- Prevent new intents after cancellation is accepted. Track workers that cannot
  be stopped so their late effects cannot be mistaken for another run.
- Preserve enough diagnostic evidence to distinguish host crash, dependency
  outage, timeout, denial, and uncertain effect.
- Give a long-running job one producer-owned completion path. Prefer a native
  terminal receipt or deferred completion, and expose only coarse, meaningful
  milestones. An unchanged status must not re-enter the model.
- Audits are event-triggered only: use a material event, named incident,
  release gate, or explicit retrospective request. Do not run an always-on
  observer that searches for possible work.

## Child Agents As Nested Runs

Represent delegation as a child run, not an invisible recursive model call.

- Persist `parent_run_id`, delegation event, objective, input references,
  allowed tools, authority ceiling, budgets, deadline, and expected result
  schema.
- Give the child its own log, projections, intents, terminal event, and complete
  system tuple.
- Return a typed child result to the parent; do not splice child free-form output
  directly into parent authority.
- Make cancellation propagation, orphan handling, retries, and budget charging
  explicit.
- A child may receive less authority than its parent, never more without a new
  independent authorization path.

For independent scouting, use 2-3 sibling scouts only when parallel evidence
or independent review justifies the coordination cost. Fork no history or only
a minimal bounded capsule, prohibit descendants, assign distinct ownership,
and merge at exactly one parent-owned point. Prefer one run when those
conditions do not hold.

Process isolation can improve containment, but a child agent is not inherently
a new trust domain. Shared credentials, storage, network, executors, or policy
still couple the runs.

## Noncoding Adapters

Avoid assuming that every result is a file diff followed by tests. Domain
adapters should expose the domain's real identity, concurrency, and verification
semantics.

For mail, calendars, CRM, documents, browsers, data systems, and devices:

- split search/read, draft/preview, and execute/send/publish capabilities;
- use stable domain IDs instead of display names or screen positions;
- capture versions, ETags, revision IDs, or preconditions to detect stale state;
- preview the exact target, payload, recipients, schedule, amount, or device
  command before a high-impact effect;
- record service acknowledgements and then verify post-state through an
  independent read when feasible;
- define duplicate detection, compensation, rate limits, privacy redaction,
  and domain-specific oracles;
- test partial success such as one recipient accepted, one record updated, or a
  browser action completed before navigation failed.

## Dangerous Non-Equivalences

Treat each pair below as explicitly non-equivalent:

- tool advertised != tool installed != executor reachable != action authorized;
- valid JSON != valid schema != valid command != safe effect;
- model requested completion != executor completed effect != oracle-confirmed
  success;
- authentication != trust != authorization;
- operator approval != policy allowance != sandbox access;
- read-only side effects != no confidentiality, load, or timing risk;
- a compensating action != transaction rollback;
- request cancellation != executor stopped != effects reconciled;
- retryability != idempotency != exactly-once execution;
- append acknowledgement != durable event persistence;
- checkpoint != canonical history; projection != current truth without a source
  sequence;
- context summary != durable memory != run evidence;
- child process != isolated trust domain;
- effect disposer registered != disposer completed != external effect reversed;
- candidate imported != candidate healthy != generation atomically activated;
- runtime rollback != state migration != external-effect compensation;
- trace completeness != telemetry representativeness != evaluation validity;
- passing one benchmark != production reliability != universal capability.
