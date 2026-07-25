# Evidence Coverage Contract

Use this contract before making an aggregate claim such as "fully reviewed",
"all items validated", or "complete across the portfolio".

The gate proves coverage only relative to a caller-declared universe, cutoff,
and evidence matrix. It does not discover the real-world universe, authenticate
evidence, judge review quality, or prove reviewer independence.

## Contract

Input schema: `capability.evidence_coverage.v1`.

```json
{
  "schema": "capability.evidence_coverage.v1",
  "subject": "change-review",
  "cutoff": "snapshot-42",
  "universe": {
    "status": "complete",
    "items": ["alpha", "beta"],
    "dimensions": ["metadata", "source-review"],
    "evidence_refs": ["inventory@snapshot-42"]
  },
  "checks": [
    {
      "item": "alpha",
      "dimension": "metadata",
      "outcome": "pass",
      "evidence_refs": ["alpha-metadata@snapshot-42"]
    }
  ],
  "claims": [
    {
      "id": "full-review",
      "kind": "full_matrix",
      "items": ["alpha", "beta"],
      "dimensions": ["metadata", "source-review"]
    }
  ]
}
```

The required coverage for a claim is the exact Cartesian product:

```text
claim items x claim dimensions
```

Counts, percentages, duplicate checks, or evidence on unrelated pairs never
compensate for a missing pair.

## Claim Kinds

- `full_matrix`: items and dimensions must exactly equal the declared universe,
  and the universe status must be `complete`. Every pair must pass.
- `bounded_matrix`: items and dimensions are non-empty subsets. It supports
  only the named bounded claim, even when the selected items happen to include
  every currently declared item.

Use separate ledgers when item classes require different mandatory dimensions.
Version 1 intentionally has no threshold, wildcard, or `not_applicable` escape
hatch.

## Outcomes

- `pass`: satisfies one item-dimension pair and requires at least one evidence
  reference.
- `fail`: records a checked but failing pair.
- `blocked`: records a checked pair that cannot yet produce a verdict.
- an absent pair is `missing`.

Every check has evidence references. The gate verifies their presence only.
Bind those references to the declared cutoff or revision in the producing
workflow.

## Exit And Result Contract

```bash
python3 "$PLUGIN_ROOT/scripts/audit/evidence_coverage_gate.py" \
  evidence-coverage.json --json
```

- exit `0`: input is structurally valid and every declared claim is satisfied;
- exit `1`: input is valid, but at least one claim is unsatisfied;
- exit `2`: malformed, ambiguous, oversized, or structurally invalid input.

`--template` is a separate generation mode: invoke it without a ledger. It
exits `0` after printing an intentionally incomplete template and makes no
validation claim. Supplying both a ledger and `--template` exits `2`.

Output schema: `capability.evidence_coverage_gate.result.v1`.

Read `subject`, `cutoff`, `ledger_fingerprint`, `declared_universe_status`,
`input_valid`, `all_claims_satisfied`, `highest_satisfied_claim`, per-claim
missing/non-passing pairs, and the summary directly. Do not infer success from
the process producing JSON. The SHA-256 fingerprint binds the canonical
contract, including evidence references, without echoing those references.

## Fail-Closed Rules

- Empty universes, dimensions, and claim lists do not pass vacuously.
- IDs, dimensions, claims, and item-dimension checks are unique.
- Unknown fields, duplicate JSON keys, unknown IDs, and duplicate checks fail
  structurally.
- `full_matrix` requires exact item and dimension set equality.
- A partial declared universe cannot support `full_matrix`.
- `bounded_matrix` never upgrades itself to `full_matrix`.
- The output is canonical and omits timestamps, input paths, and evidence text.
- The aggregate claim matrix is bounded to 4,096 pairs across all claims.

If the universe itself is not independently established, report the result as
bounded or partial even when every pair in the supplied ledger passes.

## Bounded Partial Example

Use this shape when only a named subset is ready:

```json
{
  "schema": "capability.evidence_coverage.v1",
  "subject": "change-review",
  "cutoff": "snapshot-42",
  "universe": {
    "status": "partial",
    "items": ["alpha", "beta"],
    "dimensions": ["metadata", "source-review"],
    "evidence_refs": ["inventory@snapshot-42"]
  },
  "checks": [
    {
      "item": "alpha",
      "dimension": "metadata",
      "outcome": "pass",
      "evidence_refs": ["alpha-metadata@snapshot-42"]
    }
  ],
  "claims": [
    {
      "id": "alpha-metadata-only",
      "kind": "bounded_matrix",
      "items": ["alpha"],
      "dimensions": ["metadata"]
    }
  ]
}
```
