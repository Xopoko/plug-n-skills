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
  "context_risks": [{"path": "file", "line": 1, "kind": "low_value_hot_context|middle_buried_commitment|context_window_assumption|context_stuffing|handoff_without_contract|oversized_hot_surface", "severity": "low|medium|high", "message": "..."}],
  "compression_risks": [{"path": "file", "line": 1, "kind": "commitment_loss_risk|token_only_metric|compression_without_relevance_check|retrieval_commitment_risk|format_equivalence_assumption", "severity": "medium|high", "message": "..."}],
  "contract_risks": [{"path": "file", "line": 1, "kind": "prose_parsing|schema_without_task_validation", "severity": "low|medium|high", "message": "...", "suggested_contract": "..."}],
  "research_gate_risks": [{"path": "file", "line": 1, "gate": "long_context_placement|compression_break_even|schema_task_validity|retrieval_citation_promotion|cache_aware_layout|relevance_distractor_budget|format_sensitivity|multi_agent_handoff", "triggered_by": "risk_kind", "severity": "medium", "required_evidence": ["..."], "source_basis": ["..."]}],
  "research_gate_summary": [{"gate": "cache_aware_layout", "count": 1, "max_severity": "medium", "required_evidence": ["..."], "source_basis": ["..."]}],
  "commitment_validation": {"schema": "context_density.commitment_validation.v1", "checked": 0, "passed": true, "missing_required": [], "malformed_atoms": [], "results": []},
  "blocking": {"research_gates": false, "fail_on_severity": "medium", "commitments": false},
  "risk_counts": {"context": 0, "compression": 0, "contract": 0, "research_gates": 0}
}
```

For CI-style enforcement, run `context_density_audit.py --fail-on-research-gates`.
It still prints JSON and exits `2` when a research gate risk at or above
`--fail-on-severity` is present. Do not parse the human Markdown report for
machine decisions; use the JSON output.

`--hot-token-budget N` (default 3000, 0 disables) emits `oversized_hot_surface`
for hot-path files above the budget: `low` severity below twice the budget,
`medium` at or above it. The default anchors to documented reasoning
degradation near 3K input tokens.

## Commitment Ledger

Use `--commitment-ledger atoms.json --fail-on-missing-commitments` when a
compression or refactor must preserve exact atoms. The ledger may be JSON with
an `atoms` array or JSONL rows:

```json
{
  "schema": "context_density.commitment_ledger.v1",
  "atoms": [
    {"atom_id": "no-prose-parse", "text": "Do not parse generated prose", "required": true, "match": "literal", "source_ref": "SKILL.md"}
  ]
}
```

Fields: `text` is required; `match` is `literal` or `regex`; `paths` optionally
limits files; `required` defaults to true. The command exits `3` when required
atoms are missing or malformed and `--fail-on-missing-commitments` is set.
