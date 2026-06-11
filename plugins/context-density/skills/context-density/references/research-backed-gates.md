# Research-Backed Gates

Acceptance checks for context-density decisions involving long context, compression, structured outputs, retrieval/citations, caching, relevance, formatting, or agent handoffs. Each gate states when it triggers, what evidence accepts the change (task validation, preserved commitments, total cost), and what to reject.

Findings come in two evidence classes. `measured` findings (token budgets, duplication mass, line length, commitment atoms) cannot be silenced by rewording and may block CI. `advisory` findings come from wording patterns, can be silenced by vocabulary changes, and exist to direct attention — never to gate a merge unless `--fail-on-advisory` is explicit.

Evidence vintage: corpus assembled 2026-06. Quoted effect sizes (76 points, 11 of 13 models, >30%) are snapshots of specific models and benchmarks; the directions have replicated across independent sources, the numbers will drift. Re-verify a number before citing it onward as current.

## Gate 1: Long-Context Placement

Trigger: a workflow relies on a large context window, long prompt, long memory, or packed context.

Accept iff: action-critical instructions, safety boundaries, exact strings, and recovery pointers are anchored near the top or in compact explicit state; middle-buried commitments have a source or placement pointer; behavior is validated on the actual packed shape; effective working length is treated as a fraction of the advertised maximum until validated.

Reject: "bigger window = reliable recall." NIAH-style needle retrieval is literal matching — without lexical overlap, 11 of 13 models claiming 128K+ drop below 50% of short-context baselines at 32K; reasoning degrades near 3K tokens.

Sources: Lost in the Middle `arxiv:2307.03172`; attention-bias mechanism `arxiv:2406.16008`; degradation below maximums `arxiv:2402.14848`; effective context size `arxiv:2404.06654`; non-literal recall collapse `arxiv:2502.05167`; prompt-dependent recall `arxiv:2404.08865`.

## Gate 2: Compression Break-Even

Trigger: a change claims to compress, summarize, prune, trim, distill, or reduce tokens while preserving behavior.

Accept iff the report includes: input and hot-path token delta; output token or response-length effect; task success or validator result; compressor preprocessing overhead when one is used; latency/total-cost effect when speed or cost is claimed; the task type the compression was validated on (retention is method- and task-dependent).

Reject: token-only wins that lose behavior, provenance, exact commitments, or recovery; runtime compressors that do not beat the uncompressed baseline after overhead; extreme ratios (100x+) generalized beyond their validated task; cutting in-context examples as "free" savings (many-shot counts measurably raise accuracy).

Sources: LLMLingua `doi:10.18653/v1/2023.emnlp-main.825`; LongLLMLingua `doi:10.18653/v1/2024.acl-long.91`; LLMLingua-2 `doi:10.18653/v1/2024.findings-acl.57`; ICAE `arxiv:2307.06945`; 500xCompressor `doi:10.18653/v1/2025.acl-long.1219`; semantic compression `doi:10.18653/v1/2024.findings-acl.306`; PCToolkit `arxiv:2403.17411`; surveys `doi:10.18653/v1/2025.naacl-long.368`, `arxiv:2404.01077`; many-shot ICL `arxiv:2404.11018`.

## Gate 3: Schema And Task Validity

Trigger: generated output feeds code, routing, scoring, extraction, classification, or side effects.

Accept iff: machine-consumed values come from tool arguments, strict JSON Schema, typed protocols, or closed keys; invalid output is rejected, repaired under the same schema, or fails loudly; semantic constraints and task success are checked after schema decoding; schema/key names and descriptions are reviewed as instruction-bearing text; for reasoning-heavy tasks, format strictness is treated as a measured cost (consider reason-first, format-second).

Reject: "valid JSON" as the only success criterion. Format restrictions lower reasoning performance and stricter constraints lower it more; constrained-decoding engines differ in efficiency, coverage, and quality, so engine choice is also a measured decision.

Sources: format-restriction costs `doi:10.18653/v1/2024.emnlp-industry.91`; JSONSchemaBench `arxiv:2501.10868`; Schema RL `doi:10.18653/v1/2025.acl-long.243`; engines `arxiv:2411.15100`, `arxiv:2312.07104`.

## Gate 4: Retrieval And Citation Promotion

Trigger: compressed state, memory, retrieval, archive search, RAG output, or citations may affect later action.

Accept iff: retrieved material stays `artifact_recall` until source refs, authority, confidence, conflict status, and validation are explicit; every promoted claim has a stable source key, URL, DOI, path, or recovery pointer; cited claims are spot-checked when correctness matters; unresolved conflicts stay visible; memory read/write policies state provenance and a trust boundary (agent memory is a documented extraction-attack surface; long-term conversational memory degrades on temporal/causal reasoning).

Reject: unattributed summaries, AI-ranked records, or generated citations as committed state. Treat retrieval-vs-long-context as economics: long context outperforms RAG on average with strong models but costs far more; routing retains performance at lower cost.

Sources: RAG survey `arxiv:2312.10997`; harmful related-but-irrelevant retrievals `arxiv:2401.14887`; RAG-vs-LC routing `arxiv:2407.16833`; MemGPT `arxiv:2310.08560`; LoCoMo `doi:10.18653/v1/2024.acl-long.747`; memory extraction `doi:10.18653/v1/2025.acl-long.1227`.

## Gate 5: Cache-Aware Layout

Trigger: token economics rely on prompt caching, cached prefixes, repeated tools, static system prompts, or long common examples.

Accept iff: static reusable content precedes dynamic request-specific content; changing suffixes do not invalidate the intended prefix; cache metrics (cached tokens, reads/writes, hit rate, latency, cost) are reported when available; cache savings are reported separately from task quality.

Reject: cache claims without usage evidence or layout reasoning. Caching reduces cost/latency; it proves nothing about output quality.

Sources: OpenAI and Anthropic prompt-caching docs; RadixAttention prefix reuse `arxiv:2312.07104`.

## Gate 6: Relevance And Distractor Budget

Trigger: a change packs additional files, history, retrievals, examples, or "just in case" material into a prompt or hot surface.

Accept iff: each added block has a stated relevance criterion, consumer, or decision it changes; semantically related but non-answering material is treated as the most harmful distractor class; ordering aligns with the consumer's reasoning or execution order (permuting order-independent premises alone drops reasoning accuracy by over 30%); the packed shape is validated (distractor harm amplifies with length).

Reject: "more context is safer." Irrelevant context actively degrades accuracy; related-but-wrong degrades it most; padding is a cost and a risk.

Sources: distraction `arxiv:2302.00093`, `arxiv:2404.03302`; retrieval noise `arxiv:2401.14887`; premise order `arxiv:2402.08939`; Context Rot (grey) `https://www.trychroma.com/research/context-rot`.

## Gate 7: Format Sensitivity

Trigger: a change rewrites, reformats, re-templates, or converts prompt/context material and claims behavior is preserved.

Accept iff: the change is validated with a task-level spot check, eval, or A/B on the actual consumer; behavior-critical wording is preserved verbatim or covered by a commitment ledger; separator/casing/template changes in few-shot or templated prompts are treated as behavior-relevant edits.

Reject: "meaning-preserving" as proof of behavior preservation. Formatting choices alone shift accuracy by up to 76 points few-shot and 40% on code tasks, persisting with scale and instruction tuning.

Sources: FormatSpread `arxiv:2310.11324`; template impact `arxiv:2411.10541`; format-restriction costs `doi:10.18653/v1/2024.emnlp-industry.91`.

## Gate 8: Multi-Agent Context Handoff

Trigger: context, findings, or task state pass between agents, subagents, sessions, or compaction boundaries.

Accept iff: the handoff uses a typed contract or explicit state shape (goal, constraints, decisions, evidence refs, open risks, next action); transferred claims keep source refs and authority; the receiver verifies before acting; boundary information loss is treated as a first-class failure mode.

Reject: prose-only handoffs for action-critical state. Across 1600+ multi-agent traces, failures concentrate in specification problems, inter-agent misalignment (including context loss at handoffs), and weak verification.

Sources: MAST failure taxonomy `arxiv:2503.13657`; context-engineering taxonomy `arxiv:2507.13334`.

## Machine Gate IDs

`context_density_audit.py --json` emits `research_gate_risks` mapping deterministic findings to gates. Every gate risk carries `evidence_class`.

| Gate ID | Triggered by | Required proof |
| --- | --- | --- |
| `long_context_placement` | capacity claims, long-context use without placement checks, middle-buried commitments, oversized hot surfaces (measured) | anchors, placement check, task validation on packed shape |
| `compression_break_even` | token-only compression claims, compression without provenance/relevance checks | input/output delta, latency or total cost, preserved commitments, task success, compressor overhead |
| `schema_task_validity` | prose parsing, schema-validity claims without semantic validation | schema/tool/typed protocol, invalid-output policy, task validation |
| `retrieval_citation_promotion` | retrieval/memory/citation promotion without provenance | stable source refs, authority/confidence/conflict status, spot-check before promotion |
| `cache_aware_layout` | cache savings claims without layout or usage metrics | static-prefix layout, cache metrics, quality reported separately |
| `relevance_distractor_budget` | pack-everything wording without relevance criteria | per-block relevance criterion, distractor audit, consumer-order alignment, packed-shape validation |
| `format_sensitivity` | reformat claims of preserved behavior without validation | task-level spot check or eval, verbatim atoms or commitment ledger |
| `multi_agent_handoff` | handoff/delegation without an explicit contract | typed state shape, source refs on claims, receiver-side verification |

Flags:

- `--fail-on-research-gates` exits `2` for measured gate risks at or above `--fail-on-severity` (`medium` default). Advisory findings block only with `--fail-on-advisory`.
- `--hot-token-budget N` (default 3000, 0 off) flags hot files above budget; `low` below 2x budget, `medium` at or above. The default is a heuristic motivated by degradation documented near 3K input tokens (`arxiv:2402.14848`) — that study measured total task input, not single files, so tune the budget to your packed shape.
- `--max-duplication-tokens N` exits `4` when wasted duplicate tokens exceed the budget.
- `--emit-gate-checklist FILE` writes a fillable evidence form for triggered gates — use it as the change-report skeleton.

## Source Map

Platform docs:

- OpenAI Structured Outputs: `https://developers.openai.com/api/docs/guides/structured-outputs`
- OpenAI Prompt Caching: `https://developers.openai.com/api/docs/guides/prompt-caching`
- Anthropic Prompt Caching: `https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching`

Peer-reviewed and preprint sources:

- Lost in the Middle: `https://arxiv.org/abs/2307.03172` (`doi:10.1162/tacl_a_00638`)
- Found in the Middle (attention bias): `https://arxiv.org/abs/2406.16008`
- Same Task, More Tokens: `https://arxiv.org/abs/2402.14848`
- RULER: `https://arxiv.org/abs/2404.06654`
- NoLiMa: `https://arxiv.org/abs/2502.05167`
- LLM In-Context Recall is Prompt Dependent: `https://arxiv.org/abs/2404.08865`
- LLMLingua: `doi:10.18653/v1/2023.emnlp-main.825`
- LongLLMLingua: `https://aclanthology.org/2024.acl-long.91/`
- LLMLingua-2: `doi:10.18653/v1/2024.findings-acl.57`
- ICAE: `https://arxiv.org/abs/2307.06945`
- 500xCompressor: `doi:10.18653/v1/2025.acl-long.1219`
- Semantic Compression: `doi:10.18653/v1/2024.findings-acl.306`
- PCToolkit: `https://arxiv.org/abs/2403.17411`
- Prompt Compression Survey: `doi:10.18653/v1/2025.naacl-long.368`
- Efficient Prompting Survey: `https://arxiv.org/abs/2404.01077`
- Many-Shot In-Context Learning: `https://arxiv.org/abs/2404.11018`
- Let Me Speak Freely?: `doi:10.18653/v1/2024.emnlp-industry.91`
- JSONSchemaBench: `https://arxiv.org/abs/2501.10868`
- Schema Reinforcement Learning: `doi:10.18653/v1/2025.acl-long.243`
- XGrammar: `https://arxiv.org/abs/2411.15100`
- SGLang: `https://arxiv.org/abs/2312.07104`
- Easily Distracted by Irrelevant Context: `https://arxiv.org/abs/2302.00093`
- Irrelevant Inputs Skew Responses: `https://arxiv.org/abs/2404.03302`
- The Power of Noise: `https://arxiv.org/abs/2401.14887`
- Premise Order Matters: `https://arxiv.org/abs/2402.08939`
- RAG Survey: `https://arxiv.org/abs/2312.10997`
- RAG or Long-Context (Self-Route): `https://arxiv.org/abs/2407.16833`
- MemGPT: `https://arxiv.org/abs/2310.08560`
- LoCoMo: `doi:10.18653/v1/2024.acl-long.747`
- Agent Memory Extraction (MEXTRA): `doi:10.18653/v1/2025.acl-long.1227`
- MAST Multi-Agent Failure Taxonomy: `https://arxiv.org/abs/2503.13657`
- Context Engineering Survey: `https://arxiv.org/abs/2507.13334`
- Context Rot (grey literature): `https://www.trychroma.com/research/context-rot`
