# Workflow Contracts

Use machine-readable contracts for routing, corpus state, claims, and final quality gates.

## Plan Contract

Schema: `scientific_research.plan.v1`

Required fields:

- `topic`: non-empty string.
- `questions`: array of non-empty strings.
- `sources`: array of source ids.
- `limits.per_source`: positive integer.
- `limits.total_records`: positive integer.
- `policy.open_copy_only`: boolean.
- `policy.no_paywall_bypass`: boolean.
- `outputs.layout`: expected corpus layout.

Generate and validate with:

```bash
python3 skills/scientific-research/scripts/scholarly_research.py plan --topic "..." --question "..." --out plan.json
python3 skills/scientific-research/scripts/scholarly_research.py validate-plan plan.json
```

## Record Contract

Schema: `scientific_research.record.v1`

Core fields:

- `key`
- `source`
- `source_id`
- `title`
- `creators`
- `year`
- `container`
- `doi`
- `pmid`
- `pmcid`
- `arxiv_id`
- `landing_url`
- `open_copy_url`
- `summary`
- `query`
- `dedupe_keys`
- `raw_metadata`

Store records as JSONL plus a CSV projection. Keep raw metadata because provider-specific fields often matter later.

## Query Log Contract

Schema: `scientific_research.query_log.v1`

Each row should include:

- `queried_at_utc`
- `source`
- `query`
- `status`: `ok`, `auth_required`, `cooldown`, `blocked`, `error`, or `skipped`
- `records_returned`
- `accepted_after_dedupe`
- `error`
- `endpoint`

## Source Status Contract

Schema: `scientific_research.source_status.v1`

`source-status.json` records local routing state for a corpus directory. It is not a global truth source; it only prevents repeated bad calls during related runs.

Each source entry should include:

- `status`: `available`, `ok`, `auth_required`, `cooldown`, `blocked`, `error`, or `skipped`.
- `cooldown_until_utc`: when the local cooldown expires, if any.
- `last_http_status`: provider HTTP status when known.
- `last_error`: bounded provider or wrapper error text.
- `last_endpoint`: endpoint attempted when safe to record.
- `fallbacks`: source ids to try next.

Inspect or write the status sidecar:

```bash
python3 skills/scientific-research/scripts/scholarly_research.py source-status \
  --out-dir research-corpus \
  --out research-corpus/03_runs/source-status.json
```

## Claim Ledger Contract

Schema: `scientific_research.claim.v1`

Each JSONL row must include:

```json
{
  "claim_id": "claim-001",
  "claim": "Short claim text.",
  "evidence_keys": ["doi-10-0000-example"],
  "source_refs": ["https://doi.org/10.0000/example"],
  "confidence": "medium",
  "limitations": "Why this claim may not generalize."
}
```

Allowed confidence values: `low`, `medium`, `high`.

## Screening Decision Contract

Use this for systematic reviews, scoping reviews, and evidence synthesis where inclusion/exclusion choices matter.

Each `screening-decisions.jsonl` row should include:

```json
{
  "record_key": "doi-10-0000-example",
  "stage": "title-abstract",
  "decision": "include",
  "reason": "Meets topic and study-type criteria.",
  "reviewer": "codex-assisted"
}
```

Allowed decisions: `include`, `exclude`, `maybe`, `duplicate`.

Generate a PRISMA-style summary:

```bash
python3 skills/scientific-research/scripts/scholarly_research.py screening-summary \
  --records research-corpus/01_index/records.jsonl \
  --decisions screening-decisions.jsonl \
  --out research-corpus/05_reports/screening_summary.json
```

## Quality Gate Contract

Schema: `scientific_research.quality_gate.v1`

A passing synthesis needs:

- at least the requested minimum record count;
- at least the requested minimum source count unless the task is source-specific;
- no unsupported claims;
- every claim linked to `evidence_keys` or `source_refs`;
- limitations present for each claim;
- blocked sources named, not hidden.
- screening decisions summarized when the requested output is a systematic/scoping/literature review.

Run:

```bash
python3 skills/scientific-research/scripts/scholarly_research.py quality-gate \
  --records research-corpus/01_index/records.jsonl \
  --claims claims.jsonl \
  --out quality_gate.json
```

## Heavy Run Boundary

Use a dry-run manifest before corpus-scale work:

- target records >= 100;
- PDF downloads > 20;
- multiple hours expected;
- permanent downstream behavior change;
- external automation or scheduled refresh.

Large runs should produce a command plan and require explicit approval before execution.
