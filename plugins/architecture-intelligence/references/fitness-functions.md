# Architecture Fitness Functions

Fitness functions turn architecture intent into observable signals. They can be tests, static analysis rules, CI checks, review gates, dashboards, or production monitors.

## Selection Heuristic

Use the cheapest reliable mechanism:

1. Existing project test or linter.
2. Existing package graph or build tool.
3. Small repository script.
4. Ecosystem architecture tool.
5. Manual review gate with a clear checklist.

Do not add a dependency just because an architecture tool exists. Add it only when the protected boundary is important enough and the tool can run deterministically in the project.

The plugin probe can serve as the first small repository script for top-level dependency conformance:

```bash
python3 scripts/architecture_probe.py <repo-path> --json --policy <policy.json>
```

Use it to establish baseline drift before adopting a stronger ecosystem tool.

## Ecosystem Examples

| Ecosystem | Possible mechanisms |
| --- | --- |
| Java/Kotlin | ArchUnit, jQAssistant, Gradle dependency rules |
| .NET | NetArchTest, NDepend |
| TypeScript/JavaScript | dependency-cruiser, eslint boundaries, Nx graph, Turborepo graph |
| Python | import-linter, pytest architecture checks, package import probes |
| Go | `go list`, package import tests, staticcheck |
| Rust | `cargo metadata`, workspace crate policy, clippy |
| Swift | SwiftPM target graph, XCTest boundary checks |

## Rollout Modes

- `measure`: collect current violations and trend only.
- `warn`: surface violations without blocking delivery.
- `enforce`: fail the command, PR, release, or deploy.

Legacy systems usually need `measure -> warn -> enforce`.

## Good Rule Examples

- Domain packages cannot import HTTP controllers.
- Feature packages can import shared interfaces but not other feature internals.
- Database writes for a bounded context only happen through that context's repository or service boundary.
- Public packages expose imports only through documented entry points.
- A module extraction PR must include parity tests for the moved behavior.
- A high-risk package cannot add new co-change hotspots above the agreed threshold without an ADR exception.
- An architecture-changing PR must link a scenario, quality attribute, and validation signal.
- A documented forbidden dependency edge must stay absent unless an ADR exception exists.
- Architecture-significant paths must have CODEOWNERS/OWNERS coverage or an explicit shared-ownership exception.
- A cross-owned dependency change must request both owner paths or link a documented waiver.

## Bad Rule Examples

- "Use clean architecture everywhere."
- "No file may exceed 200 lines" as an architecture rule.
- "All services must be microservices."
- "All code must use this pattern" without a quality attribute, owner, or validation signal.

## Evidence Types

- Ownership evidence: CODEOWNERS/OWNERS, governance docs, owner-review rules, and exception paths.
- Static dependency evidence: imports, package graph, target graph.
- Structure metric evidence: fan-in, fan-out, instability, dependency cycles, and graph hotspots.
- Historical evidence: co-change hotspots, churn, repeated files touched together.
- Runtime evidence: traces, metrics, SLOs, logs, incident reports.
- Deployment evidence: Docker, Kubernetes, Terraform, serverless, CI/CD, health checks, service mesh, platform manifests.
- Decision evidence: ADR status, rationale, alternatives, accepted consequences.
- Test evidence: architecture tests, contract tests, migration parity tests.

Historical and metric evidence can point to a concern but should not be the only reason for an architecture verdict.
