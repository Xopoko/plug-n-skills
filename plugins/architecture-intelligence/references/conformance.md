# Architecture Conformance Reference

Architecture conformance compares an intended model to observed implementation evidence.

## Models

- Intended model: ADRs, architecture docs, dependency policies, package rules, service contracts, ownership docs, or explicit user constraints.
- Observed model: source imports, build graph, manifests, runtime traces, deployment config, tests, repository structure, and recent changes.
- Recovered model: an observed model inferred from source when intent is missing. Use it as evidence, not as design authority.

## Reflexion-Style Mapping

Map intended relations to observed relations:

| Intended relation | Observed relation | Classification |
| --- | --- | --- |
| `forbidden` | `absent` | `convergence` |
| `forbidden` | `present` | `divergence` |
| `required` | `present` | `convergence` |
| `required` | `absent` | `absence` |
| `allowed` | `present` or `absent` | `convergence` |
| any | `unknown` | `unknown` |

Use `unknown` when generated code, reflection, runtime-only links, service calls, or ownership data are not visible in the current evidence.

## Policy Checks

`scripts/architecture_probe.py --policy <policy.json>` supports:

- `forbidden_edges`: top-level source import edge must not be present;
- `required_edges`: top-level source import edge must be present;
- `required_documents`: exact path must exist.

The policy surface is intentionally small. It is suitable for early drift detection and CI guardrails, not full architecture recovery.

## Drift Review

For each divergence or absence:

1. Confirm the intended rule still applies.
2. Check for documented exceptions or migration windows.
3. Identify the smallest repair or policy update.
4. Add or update a fitness function in warn mode when legacy violations exist.
5. Record owner, revisit trigger, and validation path.

## Socio-Technical Lens

When ownership or team topology is available, compare technical dependencies to coordination paths. A module dependency across teams is not automatically wrong, but it creates coordination demand. Treat mismatches as hypotheses unless communication, ownership, review, or build-success evidence is present.

## Limits

- Static import edges miss runtime calls, dependency injection, generated code, reflection, and external service calls.
- Required edges can encode a design assumption that is no longer true; verify intent before enforcing.
- Conformance checks detect drift from intent. They do not prove the intent is good.
