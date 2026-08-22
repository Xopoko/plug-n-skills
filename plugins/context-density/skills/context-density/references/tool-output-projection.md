# Tool-Output Projection Safety Contract

Tool-output projection is a conditional optimization. Use it only when the raw
output is too large and the downstream decision is already known. The bundled
`scripts/exact_duplicate_projection.py` implements only contiguous exact-line
deduplication; it does not decide whether a risky evidence surface is safe to
reduce and it does not implement a raw-output resolver.

## Presentation versus persistence

Concise user-facing narration is a presentation policy only. It may remove
repetition and conversational scaffolding, but it must not lower model
reasoning or output allowances, suppress tool calls or evidence, or replace
durable typed task state. The visible response and the persistent task record
are separate outputs.

Silence is not a persistence strategy. Before a compaction, handoff, or session
boundary, promote every behavior-critical claim that exists only in ephemeral
narration into typed state, a source reference, or a verified raw-recovery
reference.

## Route before reducing

A deterministic caller or harness, not an LLM, owns byte/token measurement and
the final keep-raw decision. Retain the raw output or a lossless structured form
when any of these conditions applies:

- the raw input is short or a proposed projection is not strictly smaller;
- exact bytes, formatting, record position, or causal order may matter;
- the input is malformed, truncated, or internally contradictory;
- the evidence is a Git porcelain/diff surface, an approval or authority
  boundary, an executed-versus-planned effect, or a deployment/provenance
  claim;
- future questions are unknown, or reducing the output would drop any unique
  record or decision-critical atom;
- the raw artifact or its verified resolver will not remain available.

When a model is asked only to advise a routing caller, the portable typed
decision is exactly two lines:

```text
mode=keep_raw
raw_id=<raw-id>
```

The caller must then supply the actual raw evidence; the marker itself is not
evidence. Reject a missing or mismatched raw identity.

## Projection invariants

For output that is safe to project:

- failures and safety-relevant anomalies may be indexed first, but preserve the
  original causal sequence separately;
- group only exact duplicate records automatically; never cap or drop unique
  records, changed paths, statuses, or alternative branches;
- make duplicate arithmetic exact: retained count plus omitted count must equal
  the source count;
- preserve exit status, exact error text, file and line, and both old and new
  paths for a rename;
- preserve every decision-critical claim as claim-level atoms: kind and value,
  source or provenance, observed time and order, supersession or conflict,
  uncertainty, authority, effect state (`planned`, `executed`, or
  `not-executed`), approval scope, negative evidence, and viable alternative
  branches;
- label any derived conclusion separately from observed evidence; do not invent
  a root cause, authorization, remediation command, or success state;
- retain a typed recovery pointer to the immutable raw output.

For a pre-redacted, line-record surface that satisfies those gates, prefer the
deterministic helper over asking a model to count or group records:

```bash
python3 "$PLUGIN_ROOT/skills/context-density/scripts/exact_duplicate_projection.py" output.txt --raw-id raw://run/id --model-safe-input
```

The helper run-length-encodes only contiguous exact duplicates, keeps every
unique record and run position, computes count arithmetic and digests in code,
and returns `mode=keep_raw` when its projection is not smaller.

## Durable compaction capsule

Before replacing transcript history with compressed state, persist a strict
machine-readable capsule with, at minimum:

- schema version and observation cutoff;
- goal, constraints, authority, and approval scope;
- verified facts and unresolved conflicts;
- completed actions with receipts and effect state;
- rejected branches with reasons and negative evidence;
- exact errors, risks, and decision-critical details;
- separate source references and raw-recovery references; and
- the next action and its preconditions.

Keep recalled artifacts separate from committed state. Validate the capsule at
the receiver after every boundary; on a missing field, incompatible schema,
unresolved conflict, or invalid recovery reference, keep raw context or fail
closed.

## Recovery integrity

A recovery pointer carries a raw identity, content digest, artifact kind, and
availability or expiry state. Validate the resolver before discarding raw
context. Permit at most one bounded recovery request for a downstream decision.
Fail closed on a dangling pointer, wrong artifact kind, digest mismatch, or
truncated recovery; do not guess, recursively follow another pointer, or turn
missing evidence into certainty.

Recovery coverage applies to successful and failed outputs. A failures-first
index is not complete recovery: successful observations can explain later
state, prove completed work, preserve provenance, or prevent repeated work.
Every projected output therefore needs a content-addressed raw-recovery path.
`mode=project` is only an overlay while that raw evidence remains resolvable;
the helper marks this with `raw_recovery_required=true`.

## Repeated-compaction adoption gate

Semantic selection, truncation, capping, or any projection that drops a unique
record is an opt-in experiment, never a global default. Compare an immutable
baseline and candidate both with full history and after multiple dependent
compaction or handoff boundaries. Predeclare tasks, seeds or repetitions, the
efficiency threshold, and rejection rules.

Measure task success, atom recall by category, source-reference recall,
false-atom introduction, repeated completed work, recovery requests and
success, false certainty, authority violations, and cache-aware tokens, latency,
and preprocessing across the complete pipeline. Reject a global default on any
candidate-only full-trajectory loss, repeated work, authority violation, false
certainty, dangling recovery, or material state/provenance regression. A
shorter visible response or downstream prompt alone is not an efficiency win.

## Privacy and efficacy

Redact secrets before model visibility at the harness boundary. Redacting a
projection after a model has seen raw output is not a privacy boundary. Persist
raw output only when the task independently authorizes that evidence surface.

Measure cumulative provider tokens, latency, recovery calls, decision quality,
and false certainty across the complete pipeline. A shorter downstream prompt
or response alone is not an end-to-end efficiency win.
