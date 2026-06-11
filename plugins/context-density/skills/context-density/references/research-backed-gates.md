# Research-Backed Gates

Use these gates when a context-density decision depends on long context, prompt compression, structured outputs, retrieval/citations, prompt caching, context relevance, prompt formatting, or agent-to-agent handoffs. They turn external evidence into portable acceptance checks for placement validation, faithfulness, task success, recovery, cache layout, and usage metrics without adding runtime dependencies.

## Gate 1: Long-Context Placement

Trigger when a workflow relies on a large context window, long prompt, long memory, or packed context.

Accept only when:

- action-critical instructions, safety boundaries, exact strings, and recovery pointers are anchored near the top or represented in compact explicit state;
- middle-buried commitments have a source pointer, router pointer, or placement check;
- task behavior is validated on the actual packed shape, not inferred from context-window size;
- the effective working length is treated as a fraction of the advertised maximum until validated: degradation is documented near 3K tokens on reasoning tasks, and most models hold claimed performance only below their advertised context size.

Reject claims that a larger context window alone makes recall reliable. Needle-in-a-haystack success is literal-match retrieval; it does not transfer to semantic tasks. When lexical overlap between query and target is removed, 11 of 13 models claiming 128K+ contexts drop below 50% of their short-context baselines at 32K.

Source basis: "Lost in the Middle" (`arxiv:2307.03172`) found U-shaped position-sensitive degradation; "Found in the Middle" (`arxiv:2406.16008`) traced it to intrinsic positional attention bias; "Same Task, More Tokens" (`arxiv:2402.14848`) found degradation far below technical maximums; RULER (`arxiv:2404.06654`) measured effective context below claimed sizes; NoLiMa (`arxiv:2502.05167`) showed NIAH success collapses without literal matching; "LLM In-Context Recall is Prompt Dependent" (`arxiv:2404.08865`) showed recall depends on the packed prompt, not specs.

## Gate 2: Compression Break-Even

Trigger when a change claims to compress, summarize, prune, trim, distill, or reduce tokens while preserving task behavior, provenance, and recovery.

Accept only when the report includes:

- input token delta and hot-path delta;
- output token or response-length effect;
- task success, semantic preservation, or validator result;
- preprocessing overhead when a compressor is used;
- latency and total-cost effect when the workflow claims speed or cost benefits;
- the task type the compression was validated on, because retention is method- and task-dependent.

Reject token-only wins that lose task behavior, provenance, exact commitments, or recovery pointers. For runtime compressors, reject adoption unless the measured workload beats the uncompressed baseline after compressor overhead. Treat extreme ratios (100x+) as task-narrow until proven otherwise. Example budget is part of the same economics: many-shot example counts measurably raise accuracy, so cutting examples is a behavior change, not free savings.

Source basis: LLMLingua (`doi:10.18653/v1/2023.emnlp-main.825`), LongLLMLingua (`doi:10.18653/v1/2024.acl-long.91`), LLMLingua-2 faithfulness work (`doi:10.18653/v1/2024.findings-acl.57`), ICAE (`arxiv:2307.06945`), 500xCompressor (`doi:10.18653/v1/2025.acl-long.1219`), semantic compression (`doi:10.18653/v1/2024.findings-acl.306`), PCToolkit (`arxiv:2403.17411`), prompt-compression surveys (`doi:10.18653/v1/2025.naacl-long.368`, `arxiv:2404.01077`), many-shot ICL (`arxiv:2404.11018`).

## Gate 3: Schema And Task Validity

Trigger when generated output feeds code, routing, scoring, extraction, classification, or side effects.

Accept only when:

- machine-consumed values come from tool arguments, strict JSON Schema, typed protocols, or closed keys;
- invalid output is rejected, repaired under the same schema, or fails loudly;
- semantic constraints and task success are checked after schema decoding;
- schema names, key names, and descriptions are reviewed as instruction-bearing text;
- for reasoning-heavy tasks, format strictness is treated as a measured cost: enforcing structured formats lowers reasoning performance versus free-form answers, and stricter constraints cause larger declines — consider reasoning first, formatting second as separate steps.

Reject "valid JSON" or "schema-valid" as the only success criterion. Constrained-decoding engines differ in efficiency, schema coverage, and output quality, so framework choice is also a measured decision.

Source basis: "Let Me Speak Freely?" (`doi:10.18653/v1/2024.emnlp-industry.91`) measured format-restriction reasoning costs; JSONSchemaBench (`arxiv:2501.10868`) benchmarked constrained-decoding engines on ~10K real schemas; Schema Reinforcement Learning (`doi:10.18653/v1/2025.acl-long.243`); structured-generation engines (`arxiv:2411.15100`, `arxiv:2312.07104`).

## Gate 4: Retrieval And Citation Promotion

Trigger when compressed state, memory, retrieval, archive search, RAG output, or citations may affect later action.

Accept only when:

- retrieved material remains `artifact_recall` until source refs, authority, confidence, conflict status, and validation are explicit;
- every promoted claim has a stable source key, URL, DOI, file path, or recovery pointer;
- cited claims are spot-checked against source records when correctness matters;
- unresolved conflicts stay visible instead of being merged into smooth prose;
- memory write/read policies state provenance and a trust boundary, because agent memory stores are a documented extraction-attack surface and long-term conversational memory degrades on temporal and causal reasoning.

Reject unattributed summaries, AI-ranked records, or generated citations as committed state. When choosing between retrieval and direct long-context packing, treat it as an economics decision: long context outperforms RAG on average with strong models but costs far more; routing between them retains performance at lower cost.

Source basis: RAG survey (`arxiv:2312.10997`); "The Power of Noise" (`arxiv:2401.14887`) on harmful related-but-irrelevant retrievals; RAG-vs-long-context routing (`arxiv:2407.16833`); MemGPT tiered memory (`arxiv:2310.08560`); LoCoMo long-term memory evaluation (`doi:10.18653/v1/2024.acl-long.747`); agent-memory extraction attacks (`doi:10.18653/v1/2025.acl-long.1227`).

## Gate 5: Cache-Aware Layout

Trigger when token economics rely on prompt caching, cached prefixes, repeated tools, static system prompts, or long common examples.

Accept only when:

- static reusable content comes before dynamic request-specific content;
- changing suffixes do not invalidate the intended reusable prefix;
- cache metrics are reported when available, such as cached tokens, cache reads/writes, hit rate, latency, or cost;
- cache savings are reported separately from task quality.

Reject cache claims without usage evidence or layout reasoning. Prompt caching can reduce cost or latency, but it does not prove output quality.

Source basis: OpenAI and Anthropic prompt-caching docs describe prefix-based reuse, static-prefix layout, and usage fields; SGLang RadixAttention (`arxiv:2312.07104`) demonstrates systematic KV-cache prefix reuse.

## Gate 6: Relevance And Distractor Budget

Trigger when a change packs additional files, history, retrievals, examples, or "just in case" material into a prompt or hot surface.

Accept only when:

- each added block has a stated relevance criterion, consumer, or decision it changes;
- semantically related but non-answering material is treated as the most harmful distractor class, not as helpful background;
- ordering aligns with the reasoning or execution order the consumer needs, since permuting order-independent premises alone drops reasoning accuracy by over 30%;
- the packed shape is validated, because distractor harm amplifies as context grows.

Reject "more context is safer" reasoning. Irrelevant context actively degrades accuracy; related-but-wrong context degrades it most; padding is a cost and a risk, not neutral filler.

Source basis: "Large Language Models Can Be Easily Distracted by Irrelevant Context" (`arxiv:2302.00093`); "How Easily do Irrelevant Inputs Skew the Responses of LLMs?" (`arxiv:2404.03302`); "The Power of Noise" (`arxiv:2401.14887`); "Premise Order Matters" (`arxiv:2402.08939`); Context Rot industry evaluation (`https://www.trychroma.com/research/context-rot`, grey literature).

## Gate 7: Format Sensitivity

Trigger when a change rewrites, reformats, re-templates, or converts prompt or context material (plain text, Markdown, JSON, YAML, tables) and claims behavior is preserved.

Accept only when:

- the change is validated with a task-level spot check, eval, or A/B on the actual consumer, not assumed from semantic equivalence;
- behavior-critical exact wording is preserved verbatim or covered by a commitment ledger;
- for few-shot or templated prompts, separator/casing/template changes are treated as behavior-relevant edits.

Reject "meaning-preserving rewrite" as proof of behavior preservation. Formatting choices alone shift accuracy by up to 76 points in few-shot settings and up to 40% on code tasks, and sensitivity persists with model scale and instruction tuning.

Source basis: FormatSpread (`arxiv:2310.11324`); "Does Prompt Formatting Have Any Impact on LLM Performance?" (`arxiv:2411.10541`); format-restriction reasoning costs (`doi:10.18653/v1/2024.emnlp-industry.91`).

## Gate 8: Multi-Agent Context Handoff

Trigger when context, findings, or task state pass between agents, subagents, sessions, or compaction boundaries.

Accept only when:

- the handoff uses a typed contract or explicit state shape (goal, constraints, decisions, evidence refs, open risks, next action), not free prose;
- transferred claims keep source refs and authority so the receiver can re-verify instead of trusting narration;
- the receiving side has a verification step before acting on handed-off state;
- information loss at the boundary is treated as a first-class failure mode, not an edge case.

Reject prose-only handoffs for action-critical state. Analysis of 1600+ multi-agent traces across 7 frameworks found failures concentrate in specification problems, inter-agent misalignment (including information withholding and context loss at handoffs), and weak verification.

Source basis: MAST multi-agent failure taxonomy (`arxiv:2503.13657`); context-engineering survey taxonomy of instructions/knowledge/tools/memory/state components (`arxiv:2507.13334`).

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

## Machine Gate IDs

`context_density_audit.py --json` emits `research_gate_risks` when deterministic
source risks map to these gates:

| Gate ID | Triggered by | Required proof |
| --- | --- | --- |
| `long_context_placement` | context-window capacity claims, long-context use without placement checks, middle-buried commitments, oversized hot surfaces | anchors, source order or middle-position check, task validation on the packed shape |
| `compression_break_even` | token-only compression claims, compression without provenance or relevance checks | input/output token delta, latency or total-cost effect, preserved commitments, task success, compressor overhead when applicable |
| `schema_task_validity` | prose parsing, schema-validity claims without semantic validation | explicit schema/tool/typed protocol, invalid-output policy, downstream task validation |
| `retrieval_citation_promotion` | retrieval, memory, archive, or citation promotion without provenance | stable source refs, authority/confidence/conflict status, spot-check or validation before promotion |
| `cache_aware_layout` | prompt-cache savings claims without layout or usage metrics | static-prefix layout, cache metrics, task-quality result separate from cache savings |
| `relevance_distractor_budget` | pack-everything wording without relevance, filtering, or selection criteria | per-block relevance criterion, distractor audit, ordering aligned to consumer reasoning, packed-shape validation |
| `format_sensitivity` | reformat/rewrite claims of preserved behavior without validation | task-level spot check or eval on the consumer, preserved verbatim atoms or commitment ledger |
| `multi_agent_handoff` | agent/session handoff or delegation without an explicit contract | typed handoff state shape, source refs on transferred claims, receiver-side verification |

Use `--fail-on-research-gates` when these gates are acceptance criteria for a
change. The audit still emits the full JSON payload, adds
`research_gate_summary`, and exits `2` for blocking gate risks at or above
`--fail-on-severity` (`medium` by default).

Use `--hot-token-budget N` (default 3000) to flag hot-path files whose measured
token count exceeds the budget; the default anchors to documented reasoning
degradation near 3K input tokens (`arxiv:2402.14848`). Files at or above twice
the budget escalate from `low` to `medium` severity.
