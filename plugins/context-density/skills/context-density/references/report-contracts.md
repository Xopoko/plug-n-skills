# Report Contracts

Use concise Markdown for humans and JSON from scripts for machines.

## Context Density Audit

```markdown
Context density audit:
- Consumer/load path:
- Token measurement: command, mode, before/after, delta, top hotspots.
- Commitment preservation: critical atoms retained, exact strings preserved, evidence refs, recovery pointers.
- Relevance/placement: hot anchors, router references, middle-buried commitments handled, residual recall risk.
- Research-backed gates: long-context placement, compression break-even, schema/task validity, retrieval citation promotion, cache-prefix economics, or not applicable.
- Compression economics: input/output token effect, total cost, task validation, or unavailable reason.
- Recall/state boundary: artifact refs kept separate from committed state.
- Existing context refactor: merged/replaced/compacted/deferred.
- Duplication handled: removed/linked/left as explicit tradeoff.
- Preserved invariants: triggers, safety, commands, contracts, validation.
- Contract discipline: schema/tool/typed protocol changes or risk statement.
- Validation: token count, contract scan, tests, skill/plugin validators.
- Adopted/rejected changes:
- Remaining tradeoffs:
```

## Prompt Contract Audit

```markdown
Prompt contract audit:
- Output consumer:
- Contract choice: generated prose / strict JSON / tool call / fixed key / mixed.
- Source of truth:
- Brittle parsing risk:
- Prompt shape: outcome, success criteria, constraints, output, stop rules.
- Schema discipline: required fields, enums, unknown-field policy, typed decoder.
- Validation loop: decode, semantic checks, retry/repair/fallback.
- Change made:
- Remaining tradeoff:
- Verification:
```

## Script JSON Schemas

`context_density_audit.py --json` emits:

```json
{
  "schema": "context_density.audit.v1",
  "generated_at_utc": "ISO-8601",
  "mode": "exact|approx",
  "token_summary": {"files": 0, "tokens": 0, "chars": 0, "lines": 0},
  "token_hotspots": [{"path": "file", "tokens": 0, "load_path": "hot|router|reference|evidence|unknown"}],
  "context_risks": [{"path": "file", "line": 1, "kind": "low_value_hot_context|middle_buried_commitment|context_window_assumption", "severity": "low|medium|high", "message": "..."}],
  "compression_risks": [{"path": "file", "line": 1, "kind": "commitment_loss_risk|token_only_metric|compression_without_relevance_check|retrieval_commitment_risk", "severity": "medium|high", "message": "..."}],
  "contract_risks": [{"path": "file", "line": 1, "kind": "prose_parsing|schema_without_task_validation", "severity": "low|medium|high", "message": "...", "suggested_contract": "..."}]
}
```

Do not parse the human Markdown report for machine decisions; use the JSON output.
