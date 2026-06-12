---
name: architecture-runtime-topology
description: "Use when code work touches runtime shape: services, app/CLI/background flows, deployment/IaC, observability, resilience, external integrations, ownership, and runtime coupling."
---

# Architecture Runtime Topology

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use when the question is how the system runs, communicates, fails, scales, or is operated.

## Inputs

- Deployment: Docker, Compose, Kubernetes, Helm, Terraform, serverless, Procfile, platform manifests, CI/CD, release config.
- Runtime config: env/config directories, service discovery, feature flags, schedulers/jobs.
- Integrations: HTTP, gRPC, GraphQL, queues, topics, cache, database, external APIs, webhooks, batch.
- Observability: logs, metrics, traces, dashboards, alerts, SLOs, health checks, incidents.
- Resilience: timeout, retry, circuit breaker, fallback, bulkhead, rate limit, idempotency, backpressure, degradation.
- Ownership: service owners, CODEOWNERS/OWNERS, runbooks, escalation paths, review gates.

Record paths and signal names only; never repeat secret values.

## Probe

```bash
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json
```

Use `runtime_topology` as evidence inventory. It detects deployment artifacts and runtime signal names, not production truth.

## Lenses

- Topology: what deploys, what calls what, and which runtime edges matter.
- Failure behavior: slow/down/partial/overloaded/inconsistent dependency response.
- Observability: critical paths have actionable logs, metrics, traces, health checks, owners.
- Deployment conformance: source boundaries and IaC/deployment boundaries agree or drift.
- Operability: teams can diagnose, roll back, and safely change runtime dependencies.
- Ownership: runtime-critical surfaces have source-backed owner or review path.
- Quality attributes: availability, reliability, latency, scalability, security, cost, operability.

## Output

Compact: runtime summary, highest-impact coupling/resilience risks, evidence inspected, unknowns needing traces/config/owner input, next validation.

Durable: `architecture_intelligence.runtime_topology.v1`.

Do not infer production state from repo files alone. Do not treat an import as proof a tactic is correctly used. Recommend distributed-system patterns only when topology and quality-attribute scenarios justify them.
