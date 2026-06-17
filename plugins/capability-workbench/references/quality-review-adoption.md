# Quality Review Adoption

Use this reference when Capability Workbench is creating, refactoring, auditing,
or packaging a local Codex skill or plugin and needs structured quality-review
evidence.

## Adopted Mechanisms

- Intent-first router: convert a natural quality request into a compact local command sequence.
- Canonical result: keep local validator and audit JSON as the source for structure, token cost, duplication, research-gate, and blocking findings.
- Fix-first triage: review blocking errors, measured risk entries, token hotspots, and duplication clusters before lower-value cleanup.
- Budget visibility: inspect startup metadata, hot instruction, deferred support, and explicit-only surfaces when a host policy provides that split.
- Improvement loop: capture before/after JSON in ignored output, then compare changed validation results, token summaries, and blocking findings.
- Measurement path: collect observed usage only when the user wants real usage calibration and cost/network boundaries are explicit.

## Boundaries

- Quality review is a Workbench evidence contract, not a hard dependency on any external evaluator.
- Workbench validators still gate manifest validity, install scope, marketplace visibility, safety, and source publication.
- Static budget findings are triage signals until supported by observed usage or task outcomes.
- Review summaries are rewrite inputs; preserve trigger semantics, safety boundaries, install scope, provenance, and validation proof separately.
- Do not run live benchmark scenarios, network calls, or credentialed measurement without explicit user intent.

## Commands

```bash
python3 "$PLUGIN_ROOT/scripts/plugin/validate_plugin.py" <plugin-dir>
python3 "$PLUGIN_ROOT/scripts/skill/quick_validate.py" <skill-dir>
python3 "$PLUGIN_ROOT/scripts/context/token_count.py" <path> --json --top 20
python3 "$PLUGIN_ROOT/scripts/context/context_density_audit.py" <path> --json --top 20
python3 "$PLUGIN_ROOT/scripts/portfolio/portfolio_architecture_audit.py" <plugin-dir> --json
```

## Adoption Ledger Fields

When adopting quality-review findings into Workbench changes, record:

- evaluator script path, version when available, and command arguments;
- target path and target kind;
- top recommendations adopted, adapted, rejected, deferred, or reference-only;
- final surface: skill text, reference, manifest, validator, benchmark config, or report field;
- validation command that proves the adopted change;
- residual risk when a static estimate lacks observed usage.
