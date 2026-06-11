# Quality Gates

Use this file before turning papers into decisions, recommendations, product rules, or durable memory.

## Evidence Levels

- Metadata only: title/abstract/provider record only. Good for discovery, weak for claims.
- Abstract-backed: abstract supports a narrow claim. State that the full paper was not reviewed.
- Full-text-backed: open full text or PDF was inspected. Stronger but still quote sparingly.
- Multi-source synthesis: claim is supported by multiple independent records or a review/meta-analysis.
- Disconfirmed/mixed: evidence conflicts or does not generalize.

## Required Checks

- Query diversity: include synonyms and neighboring terms when the topic is broad.
- Deduplication: DOI, PMID, PMCID, arXiv id, normalized title, open-copy URL, and content hash when available.
- Date awareness: identify recent papers separately from foundational papers when recency matters.
- Source bias: note when only preprints, only biomedical indexes, or only publisher metadata were searched.
- Source routing: inspect `source-status` before querying and name any sources in cooldown, auth failure, or wrapper failure.
- Open-copy policy: only download files that provider metadata exposes as open or user explicitly supplied as public.
- Screening trace: for systematic, scoping, or literature-review outputs, keep inclusion/exclusion decisions in JSONL and produce `screening_summary.json`. A summary with zero decisions fails — unscreened is not screened.
- Claim support: every non-trivial conclusion points to record keys, DOI/PMID/PMCID/arXiv id, or stable URLs. The gate fails on zero claims, missing claim text, and claims citing records you excluded during screening (pass `--decisions`); pass `--plan` so the plan's own `quality_gates` thresholds are enforced.
- Gate scope honesty: a passing gate proves traceability (every claim resolves to records you kept), not truth. Spot-check load-bearing claims against source text before promoting them.
- Negative evidence: record disconfirming or limiting sources when they affect the answer.
- AI assistance disclosure: name where AI was used in search, screening, extraction, synthesis, or drafting; state input data, output format, human checks, and limitations.

## Stop Conditions

Stop and report limitations instead of expanding blindly when:

- source APIs are blocked/rate-limited and available fallbacks cover the core question;
- duplicates dominate and new search terms are not changing the corpus;
- records are metadata-only and the requested output needs full-text claims;
- a source requires credentials or paid access;
- the task needs a domain expert judgment that the evidence cannot support.

## Final Answer Shape

Keep the answer compact but auditable:

```text
Answer:
...

Evidence:
- record key / DOI / URL: why it matters

Coverage:
- sources queried, records accepted, duplicates, blocked sources

Limitations:
- ...

Artifacts:
- ...
- screening_summary.json path when applicable
```
