# Design Notes

This plugin distills reusable scholarly research mechanisms without copying
domain-specific pipelines, project-specific context, or local operational
ledgers.

Adopted mechanisms:

- Bounded source routing: blocked or cooled-down sources remain visible, but
  fallbacks continue the run.
- Dry-run before heavy execution: long corpus work starts with a
  machine-readable manifest and command plan.
- Open-copy-only downloads: no paywall bypass, no private exports, no leaked
  access.
- Corpus layout: `01_index`, `02_sources`, `03_runs`, `04_knowledge_base`,
  `05_reports`, `runtime_distillation`.
- Strict dedupe: DOI, PMID, PMCID, arXiv id, normalized title, open-copy URL,
  and content hash.
- Query logs: source, query, status, counts, endpoint, and errors are records,
  not prose.
- Source status sidecar: cooldowns, auth failures, and wrapper failures survive
  across related corpus runs.
- Runtime distillation gate: source-backed records and claim ledgers must pass a
  quality gate before integration.

Rejected or not generalized:

- Domain-specific relevance scoring and vocabulary.
- Full PDF extraction stacks and Java-dependent tooling.
- Project-specific lifecycle selectors and source-specific operational ledgers.
- Any mechanism that parses generated Markdown headings for machine decisions.

Reusable input patterns used during synthesis:

- generic research-pipeline planning;
- source routing with cooldown and fallback state;
- heavy-research workflow handoff;
- publication-expansion workflows using OpenAlex, Crossref, Europe PMC, strict
  dedupe, and open-copy handling.

The resulting plugin is deliberately lighter: it gives Codex a reusable
scholarly research workflow and helper scripts, while leaving multi-hour corpus
execution as an explicit, approved escalation. The live search helper uses
Python standard-library HTTP so errors can retain response bodies and
rate-limit headers.

## Tested Guarantees And Limits

Guarantees locked by `tests/test_scholarly_research.py`:

- Merge, never destroy: repeated searches into one out-dir merge into the
  existing index; prior records survive dedupe and the `total_records` cap;
  the previous index is backed up before any change; over-cap drops are
  logged, never silent.
- Idempotent re-runs: an unchanged search leaves the index byte-identical,
  reports `index_changed: false`, and writes no new backup.
- Idempotent normalization: `normalize_record(normalize_record(x))` equals
  `normalize_record(x)`, so merged indexes do not drift across runs.
- Fail loudly on corruption: a damaged line in records/claims/decisions/plan
  JSON exits with a named `invalid_json`/`invalid_jsonl` error including the
  line number, and leaves the damaged file untouched for repair.
- Gates cannot pass vacuously: zero claims or zero screening decisions fail.

Known limits:

- No file locking: two concurrent searches into the same out-dir can race;
  run searches into one corpus sequentially.
- A passing quality gate proves traceability, not truth.
- Query sanitization is OpenAlex-specific; other sources receive queries
  verbatim.
