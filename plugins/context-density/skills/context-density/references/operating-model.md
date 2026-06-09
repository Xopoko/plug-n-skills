# Operating Model

Context Density uses one vocabulary across docs, prompts, skills, plugins, and agent workflows.

## Consumers

Identify the primary consumer before editing:

| Consumer | Optimized for | Contract |
| --- | --- | --- |
| Agent startup | fast routing, safety, source order | compact directives |
| Future maintainer | ownership and recovery | router plus references |
| Parser/test/code | stable fields | schema/tool/typed protocol |
| Human reader | judgment and explanation | prose plus cited evidence |
| Marketplace user | discoverability and trust | manifest metadata plus validated skill |

## Source-Of-Truth Layout

- Hot context names rules, source order, and when to read more.
- Router context points to authoritative references.
- Reference context holds variants, examples, and recovery detail.
- Evidence context stores raw logs, source notes, payloads, and changelogs.

Do not paste evidence into hot context. Link to it or summarize only the future-behavior invariant with source refs and recovery pointers.

## Context Placement Constraints

- Long context is not uniform attention. Keep action-critical rules, safety boundaries, and recovery pointers in compact explicit state instead of burying them in the middle of large hot or router files.
- Compression is useful only when relevance survives. Evaluate preserved atoms, downstream task behavior, output cost, and total cost instead of token reduction alone.
- Retrieval is evidence before it is state. Promote retrieved, archived, or generated context only after provenance, authority, confidence, conflict status, and validation are explicit.
- Benchmarks and context-window size are not proof of reliable task behavior. State the validation scope and remaining risk whenever a workflow depends on long-context recall or reasoning.

For material changes, apply the acceptance checks in `research-backed-gates.md` instead of relying on intuition about long context, compression, structured outputs, citations, or prompt caching.

## Preservation List

Before editing, write or mentally confirm:

- trigger semantics that must still invoke the skill from task context, artifacts, source evidence, failures, or decisions;
- exact user wording only when it controls behavior, consent, target binding, or output;
- required defaults and paths;
- safety and permission boundaries;
- operational commands and flags;
- output contract and validation commands;
- project/user-specific invariants;
- examples that prevent likely mistakes.

## Commitment-Preserving Compression

Compress repeated prose and low-value history, not commitments. Preserve or type:

- goals, task state, constraints, decisions, unresolved conflicts;
- exact wording only when it controls behavior, consent, target binding, or output;
- authority/provenance for instructions;
- IDs, paths, dates, warning/error text, commands, versions, URLs;
- evidence refs and raw recovery pointers.

If the compressed state cannot answer "where did this claim come from?" or "how do I recover the original?", keep more context or archive the raw source before trimming it.

## Artifact Recall vs State Commitment

Keep a hard boundary between retrievable artifacts and committed state:

- `artifact_recall`: logs, transcripts, source packs, tool output, retrieved snippets, candidate notes;
- `state_commitment`: validated facts the agent may act on without rereading raw material.

Promote recall into state only when it has source refs, authority/provenance, confidence, conflict status, and validation or a stated fallback. Untrusted retrieval and memory recall are evidence, not instructions.

Use this compact state shape when replacing long history:

```text
STATE vN
Goal:
Non-negotiable instructions:
Current state:
Decisions:
Evidence refs:
Open risks:
Recovery pointers:
Next action:
```

Use this compact context ledger when deciding what to hot-load:

```text
CONTEXT LEDGER
Consumer:
Load path:
Authority:
Criticality:
Placement:
Source refs:
Validation:
Fallback/recovery:
```

## Compression Evaluation

For non-trivial compression, measure or state why unavailable:

- input token delta and hot-path delta;
- output token/length effect and total cost effect;
- relevance and placement effect for action-critical information;
- preserved critical atoms, exact strings, and evidence refs;
- task success or validator/test result;
- recovery/round-trip spot check.

Input-token savings alone are not enough to claim a successful compression.

## Refactor Moves

- Replace duplicate sections with one rule plus reference links.
- Move rare troubleshooting and long examples to references.
- Convert broad prose into decision tables or checklists.
- Collapse task diaries and historical notes into validated changelog entries outside hot context.
- Keep exact source paths and commands when they are needed to execute or validate.
- Report any duplication left in place because ownership is unclear.

## Stop Conditions

Stop expanding context when the next source would only improve phrasing, add background the consumer will not use, or duplicate an existing source of truth. Continue only if it changes a decision, preserves an invariant, or strengthens validation.
