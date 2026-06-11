# Prompt Contracts

Design LLM workflows as explicit contracts. Do not parse accidental model prose.

## Contract Ladder

Choose the most reliable practical interface:

1. Tool/function-call arguments for actions, side effects, database writes, file operations, or agent steps.
2. Strict JSON Schema / structured output plus task validation for extraction, classification, routing, scoring, and machine decisions.
3. Typed protocol grammar when JSON/tool calls are unavailable.
4. Fixed key or enum when the model selects authored product copy or a closed taxonomy.
5. Generated prose only for user-visible writing, drafts, summaries, and explanations.

If prose and machine data are both needed, use a mixed contract with separate fields.

## Schema Defaults

- Required fields by default.
- Reject unknown fields unless extensibility is intentional.
- Use enums for closed sets and booleans for binary decisions.
- Bound arrays and numeric ranges when relevant.
- Use explicit date/time formats.
- Keep `reason`, `rationale`, or `summary` fields human-facing; code must not parse them for the real decision.
- Gate side effects behind validated typed fields, not assistant narration.

Schema validity is not task validity. After decoding a structured response, also check semantic constraints, source support, and task success for the consumer. Treat schema names, key names, enum labels, and descriptions as instruction-bearing text that can influence the model.

Format strictness is a measured cost, not a free guarantee: enforcing structured formats degrades reasoning performance versus free-form answers, and stricter constraints degrade it more. For reasoning-heavy tasks, prefer a two-step contract — reason in free form, then format the conclusion under the schema — or validate that single-step constrained output preserves task quality. Constrained-decoding engines also differ in coverage and output quality, so the engine choice is part of the contract (see `research-backed-gates.md`, Gate 3 and Gate 7).

## Risk Signals

Investigate code or prompts that:

- regex, split, search, or replace generated assistant text;
- parse Markdown headings or section order;
- infer status, IDs, categories, scores, dates, or actions from explanations;
- accept invalid JSON and guess missing values;
- silently accept unknown fields;
- retry without passing validation errors;
- use generated user-visible text as machine state.

Parsing is acceptable for explicit deterministic protocols: JSON, XML, CSV, YAML, tool arguments, source files, logs, CLI output, database rows, APIs, or documented grammar tokens.

## Validation Loop

1. Decode structured output or tool arguments.
2. Validate schema and unknown-field policy.
3. Check semantic constraints and cross-field consistency.
4. Reject unsafe actions before side effects.
5. Retry with validation error and bounded count, repair under the same schema, fallback, or fail loudly.
6. Cover malformed output with tests or fixtures.

## Review Standard

Before accepting a model-output implementation, answer:

1. Who consumes the output?
2. Is each consumed value explicit?
3. Is there a schema or declared grammar?
4. Are invalid outputs rejected before use?
5. Are retries bounded and error-driven?
6. Is user-visible prose separate from machine decisions?
7. Could a wording change break the code?

If wording drift can break behavior, redesign the contract.

## Compression Contract Check

When an LLM compresses memory, instructions, reports, tool outputs, or handoff state, require a mixed contract:

- machine state in strict JSON/schema or a declared typed protocol;
- human summary only as explanatory prose;
- separate `artifact_refs` from `committed_state`;
- `source_refs` or `recovery_refs` for every claim that may affect later action;
- closed enums for authority, confidence, risk, and status;
- metrics fields for `input_tokens_before`, `input_tokens_after`, `output_tokens_delta`, `total_cost_delta`, and `validation_status` when the workflow claims efficiency;
- explicit low-confidence fallback: keep raw text, ask for lookup, or fail closed.

Do not accept compressed text that drops provenance, merges conflicting instructions, or turns exact evidence into unattributed conclusions.
