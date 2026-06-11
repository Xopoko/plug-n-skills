---
name: architecture-conformance
description: "Use when intended architecture must be compared with implementation: dependency policies, ADRs, ownership rules, drift, erosion, recovered models, and conformance classifications."
---

# Architecture Conformance

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory. Works under any host agent, including Codex, Claude, and Cursor.

Use when the question is whether implementation still matches intended architecture.

Triggers: compare code to ADR/docs/policy, detect drift or erosion, turn intent into checks, classify edges as convergence/divergence/absence/unknown, recover observed architecture before updating docs.

## Inputs

- Intended model: ADRs, diagrams, README architecture sections, package rules, service boundaries, CODEOWNERS/OWNERS, ownership docs, explicit constraints.
- Observed model: source tree, imports, manifests, build graph, tests, runtime config, deployment/IaC, recent changes.
- Policy scope: modules, services, packages, data stores, topics, runtime paths.
- Exception path: waivers, migration windows, legacy constraints, owners.

If intent is thin, label it incomplete. Do not convert recovered source shape into design intent.

## Probe

```bash
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json --policy <policy.json>
```

`architecture_intelligence.policy.v1` supports forbidden edges, required edges, and required documents. See `references/contracts.md`.

The probe is conservative: top-level static imports and exact document paths only. Reflection, generated code, runtime calls, full CODEOWNERS semantics, actual team communication, and deployment edges need separate evidence.

## Classification

- `convergence`: intended and observed relation agree.
- `divergence`: observed source violates intent.
- `absence`: required relation/document is missing.
- `unknown`: evidence or policy is insufficient.

For each mapping record source, target, intended relation, observed relation, classification, and evidence path/command/doc/trace.

## Workflow

1. State intended architecture as explicit rules.
2. Build observed model from source/runtime evidence.
3. Compare each rule and classify result.
4. Separate violations from documented exceptions and migration debt.
5. Prioritize by impact, propagation risk, reversibility, confidence.
6. Propose smallest fix plus a fitness function or policy check.

## Output

Compact: conformance summary, key convergences/divergences, missing intent evidence, priority fixes, validation checks.

Durable: `architecture_intelligence.conformance.v1`.

Do not report a violation without an intended rule and observed evidence. Do not enforce a new rule without intent, owner, exception path, and rollout mode.
