# Research-Backed Gates

Use these gates when a context-density decision depends on long context, prompt compression, structured outputs, retrieval/citations, or prompt caching. They turn external evidence into portable acceptance checks for placement validation, faithfulness, task success, recovery, cache layout, and usage metrics without adding runtime dependencies.

## Gate 1: Long-Context Placement

Trigger when a workflow relies on a large context window, long prompt, long memory, or packed context.

Accept only when:

- action-critical instructions, safety boundaries, exact strings, and recovery pointers are anchored near the top or represented in compact explicit state;
- middle-buried commitments have a source pointer, router pointer, or placement check;
- task behavior is validated on the actual packed shape, not inferred from context-window size.

Reject claims that a larger context window alone makes recall reliable. Treat long context as capacity, not proof of retrieval quality.

Source basis: "Lost in the Middle: How Language Models Use Long Contexts" (`arxiv:2307.03172`) found position-sensitive degradation in multi-document QA and key-value retrieval.

## Gate 2: Compression Break-Even

Trigger when a change claims to compress, summarize, prune, trim, distill, or reduce tokens while preserving task behavior, provenance, and recovery.

Accept only when the report includes:

- input token delta and hot-path delta;
- output token or response-length effect;
- task success, semantic preservation, or validator result;
- preprocessing overhead when a compressor is used;
- latency and total-cost effect when the workflow claims speed or cost benefits.

Reject token-only wins that lose task behavior, provenance, exact commitments, or recovery pointers. For runtime compressors, reject adoption unless the measured workload beats the uncompressed baseline after compressor overhead.

Source basis: LongLLMLingua and PCToolkit report task-specific compression gains and evaluation across multiple tasks, while later prompt-compression studies show gains depend on model, workload, compression ratio, and hardware.

## Gate 3: Schema And Task Validity

Trigger when generated output feeds code, routing, scoring, extraction, classification, or side effects.

Accept only when:

- machine-consumed values come from tool arguments, strict JSON Schema, typed protocols, or closed keys;
- invalid output is rejected, repaired under the same schema, or fails loudly;
- semantic constraints and task success are checked after schema decoding;
- schema names, key names, and descriptions are reviewed as instruction-bearing text.

Reject "valid JSON" or "schema-valid" as the only success criterion. Format constraints can change task behavior, so schema validity and task validity are separate checks.

Source basis: OpenAI Structured Outputs documents schema adherence over JSON mode; constrained-generation and JSON Schema benchmark work shows formal constraints and schema wording affect reliability and behavior.

## Gate 4: Retrieval And Citation Promotion

Trigger when compressed state, memory, retrieval, archive search, RAG output, or citations may affect later action.

Accept only when:

- retrieved material remains `artifact_recall` until source refs, authority, confidence, conflict status, and validation are explicit;
- every promoted claim has a stable source key, URL, DOI, file path, or recovery pointer;
- cited claims are spot-checked against source records when correctness matters;
- unresolved conflicts stay visible instead of being merged into smooth prose.

Reject unattributed summaries, AI-ranked records, or generated citations as committed state.

Source basis: citation-verification work in RAG shows that citation text needs verification rather than blind promotion.

## Gate 5: Cache-Aware Layout

Trigger when token economics rely on prompt caching, cached prefixes, repeated tools, static system prompts, or long common examples.

Accept only when:

- static reusable content comes before dynamic request-specific content;
- changing suffixes do not invalidate the intended reusable prefix;
- cache metrics are reported when available, such as cached tokens, cache reads/writes, hit rate, latency, or cost;
- cache savings are reported separately from task quality.

Reject cache claims without usage evidence or layout reasoning. Prompt caching can reduce cost or latency, but it does not prove output quality.

Source basis: OpenAI and Anthropic prompt-caching docs both describe prefix-based reuse, static-prefix layout, and usage fields for cache performance.

## Source Map

- OpenAI Structured Outputs: `https://developers.openai.com/api/docs/guides/structured-outputs`
- OpenAI Prompt Caching: `https://developers.openai.com/api/docs/guides/prompt-caching`
- Anthropic Prompt Caching: `https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching`
- Lost in the Middle: `https://arxiv.org/abs/2307.03172`
- LongLLMLingua: `https://aclanthology.org/2024.acl-long.91/`
- PCToolkit: `https://arxiv.org/abs/2403.17411`
- Guiding LLMs The Right Way: `https://arxiv.org/abs/2403.06988`
