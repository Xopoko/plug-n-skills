# Runtime Topology Reference

Runtime topology is the architecture that exists when the system is deployed, called, observed, and operated.

## Evidence Surfaces

- Deployment: Docker, Compose, Kubernetes, Helm, Terraform, serverless, PaaS manifests, CI/CD, release config.
- Runtime config: environment, feature flags, service discovery, scheduler/job config, connection settings.
- Integrations: HTTP, gRPC, GraphQL, queues, topics, caches, databases, webhooks, external APIs, batch jobs.
- Resilience: timeout, retry, circuit breaker, fallback, bulkhead, rate limit, health checks, idempotency, backpressure.
- Observability: logs, metrics, traces, dashboards, alerts, SLOs, health checks, incident evidence.

## Review Rules

1. Build an observed runtime model from repository evidence first.
2. Separate source evidence from production evidence.
3. Tie runtime findings to a quality-attribute scenario.
4. Check whether deployment/IaC and source boundaries express the same architecture.
5. Treat absent resilience or observability signals as an investigation gap unless a critical runtime path is known.
6. Validate recommendations with traces, tests, synthetic monitoring, chaos or failure tests, SLOs, or deployment review.

## Resilience Tactics

Use tactics only when a scenario needs them:

- timeout: prevent indefinite wait on dependency calls;
- retry: recover from transient faults without amplifying load;
- circuit breaker: stop repeated calls to a failing dependency;
- fallback: preserve degraded behavior when a dependency fails;
- bulkhead: isolate resource pools or failure domains;
- rate limit: protect systems from overload;
- health check: expose readiness, liveness, and dependency state.

Every tactic needs an owner, threshold, failure action, and observability signal.

## Deployment Conformance

Review deployment artifacts as architecture evidence:

- Do deployment units match intended components or bounded contexts?
- Are runtime dependencies visible and owned?
- Are configuration differences between environments intentional?
- Are IaC changes reviewed with the same seriousness as source architecture changes?
- Can the team detect drift between intended topology and deployed topology?

## Limits

- Repository files do not prove production state.
- Signal names do not prove correct behavior.
- Generated config, cloud state, service mesh rules, and incident history may be outside the repository.
- Never include secret values in runtime topology artifacts.
