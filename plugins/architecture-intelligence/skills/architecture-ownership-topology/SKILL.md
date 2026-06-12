---
name: architecture-ownership-topology
description: "Use when architecture crosses ownership or review boundaries: CODEOWNERS/OWNERS, module coverage, cross-owned dependencies, socio-technical coordination, and governance paths."
---

# Architecture Ownership Topology

Bundled commands use `$PLUGIN_ROOT` for the plugin root. Set it once: use the host's plugin-root variable when defined (Claude Code: `PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"`), otherwise the absolute path of this plugin's root directory.

Use when the question involves ownership, team boundaries, review paths, CODEOWNERS, OWNERS files, shared modules, Conway-style alignment, or coordination risk across modules/services.

## Inputs

- Ownership sources: `.github/CODEOWNERS`, `CODEOWNERS`, `OWNERS`, `OWNERS_ALIASES`, `MAINTAINERS`, `GOVERNANCE.md`, `CONTRIBUTING.md`.
- Architecture sources: package/module layout, ADRs, architecture docs, service boundaries, public APIs, dependency rules.
- Coupling evidence: static imports, build/package graph, runtime integrations, deployment/IaC, data ownership, co-change history.
- Governance evidence: branch protection, review rules, release ownership, exception paths, waivers.
- User-provided organization facts, only when explicitly provided.

Do not infer actual communication, staffing, workload, or review enforcement from repository files alone.

## Probe

```bash
python3 "$PLUGIN_ROOT/scripts/architecture_probe.py" <repo-path> --json
```

Use `ownership_topology` for ownership sources, top-level coverage, ownerless areas, and cross-owned static dependency edges.
The parser is conservative: no GitHub API, org membership lookup, branch-protection proof, or full CODEOWNERS semantics.

## Lenses

- Coverage: significant modules, runtime surfaces, and docs have owner or review path.
- Coordination risk: dependency/runtime/data/co-change edges cross different owner sets.
- Conway alignment: code and ownership boundaries appear aligned, misaligned, or unknown.
- Governance: architecture-changing work has decision owner, review path, exception path, revisit trigger.
- Knowledge risk: critical areas are ownerless, shared without policy, or tribal.

## Workflow

1. Identify ownership documents and scope.
2. Map owned, unowned, ambiguous architecture areas.
3. Join ownership with dependency, runtime, and docs evidence.
4. Separate observed facts from coordination hypotheses.
5. Prioritize by quality impact, propagation risk, reversibility.
6. Recommend the smallest mechanism: CODEOWNERS rule, ADR owner, review gate, exception policy, or fitness function.

## Output

Compact: topology summary, ownerless significant areas, cross-owned risks, governance gaps, review-path recommendations, limitations, next validation.

Durable: `architecture_intelligence.ownership_topology.v1`.

Do not diagnose team dysfunction. Do not treat ownership files as complete organization truth. Do not enforce review gates without migration path, exception policy, and owner confirmation.
