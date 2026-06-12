# Architecture Intelligence Contracts

Use these schemas when the output should be saved, checked, or reused; keep lightweight answers short.

## `architecture_intelligence.audit.v1`

Required fields:

```json
{
  "schema": "architecture_intelligence.audit.v1",
  "target": "repo, service, package, module, or change",
  "summary": "one paragraph architecture judgment",
  "context": {
    "system_boundary": "what is in scope",
    "quality_attributes": ["maintainability", "reliability"],
    "evidence": ["source path, command, doc, trace, or user-provided fact"],
    "scenarios": [
      {
        "scenario": "change or runtime scenario",
        "stimulus": "what triggers the scenario",
        "environment": "normal, peak, incident, migration, release, onboarding, or maintenance",
        "response": "desired architectural response",
        "response_measure": "observable success measure",
        "quality_attribute": "modifiability"
      }
    ],
    "assumptions": ["bounded assumption"],
    "unknowns": ["what still needs inspection"]
  },
  "findings": [
    {
      "id": "kebab-case-id",
      "severity": "P1",
      "lens": "dependency-direction",
      "evidence": "source-backed evidence",
      "debt_type": "smell",
      "propagation_risk": "high",
      "reversibility": "moderate",
      "business_impact": "why this matters to delivery, users, operations, or cost",
      "impact": "architecture consequence",
      "recommendation": "specific change",
      "validation": "test, probe, metric, or review signal",
      "confidence": "medium"
    }
  ],
  "quality_gates": {
    "modifiability": "risk",
    "reliability": "unknown",
    "security": "pass",
    "operability": "risk",
    "testability": "risk"
  },
  "next_actions": ["action in priority order"]
}
```

Allowed severities: `P0`, `P1`, `P2`, `P3`.

Allowed lenses:

- `system-shape`
- `module-boundary`
- `dependency-direction`
- `bounded-context`
- `data-ownership`
- `ownership-topology`
- `runtime-coupling`
- `quality-attribute`
- `testability`
- `operability`
- `documentation-drift`
- `migration-risk`

Allowed confidence values: `low`, `medium`, `high`.

Allowed gate values: `pass`, `risk`, `unknown`.

Allowed debt types: `smell`, `debt`, `erosion`, `inconsistency`, `knowledge-gap`, `none`.

Allowed propagation risk values: `low`, `medium`, `high`.

Allowed reversibility values: `easy`, `moderate`, `hard`.

## `architecture_intelligence.conformance.v1`

Required fields:

```json
{
  "schema": "architecture_intelligence.conformance.v1",
  "target": "repo, service, package, module, or architecture rule set",
  "intended_model_source": "ADR, architecture doc, policy file, or explicit constraint",
  "observed_model_source": "source inspection, probe output, runtime trace, or build graph",
  "mappings": [
    {
      "source": "module, package, service, or path",
      "target": "module, package, service, or path",
      "intended_relation": "forbidden",
      "observed_relation": "present",
      "classification": "divergence",
      "evidence": "source-backed evidence"
    }
  ],
  "findings": [
    {
      "id": "kebab-case-id",
      "severity": "P1",
      "classification": "divergence",
      "evidence": "source-backed evidence",
      "impact": "architecture consequence",
      "recommendation": "specific change",
      "validation": "test, probe, metric, or review signal",
      "confidence": "high"
    }
  ],
  "drift_summary": {
    "convergences": 0,
    "divergences": 1,
    "absences": 0,
    "unknowns": 0
  },
  "next_actions": ["action in priority order"]
}
```

Allowed intended relations: `allowed`, `forbidden`, `required`.

Allowed observed relations: `present`, `absent`, `unknown`.

Allowed classifications: `convergence`, `divergence`, `absence`, `unknown`.

Use this contract only when there is both an intended architecture source and observed evidence. If the intended model is missing, report a `knowledge-gap` in `architecture_intelligence.audit.v1` or recover the observed model first.

## `architecture_intelligence.policy.v1`

Input schema accepted by `scripts/architecture_probe.py --policy`.

```json
{
  "schema": "architecture_intelligence.policy.v1",
  "forbidden_edges": [
    {
      "from": "domain",
      "to": "infrastructure",
      "reason": "domain must not depend on infrastructure"
    }
  ],
  "required_edges": [
    {
      "from": "app",
      "to": "domain",
      "reason": "application layer delegates to domain"
    }
  ],
  "required_documents": ["docs/architecture.md"]
}
```

The probe matches top-level static import edges and exact required document paths. Treat failures as conformance evidence, not as complete runtime proof.

## `architecture_intelligence.structure_metrics.v1`

Conservative static structure metrics from the offline probe.

```json
{
  "schema": "architecture_intelligence.structure_metrics.v1",
  "target": "repo, package, service, or module set",
  "observed_model_source": "architecture_probe.py static import graph",
  "components": [
    {
      "name": "domain",
      "afferent_coupling": 2,
      "efferent_coupling": 1,
      "incoming_edges": 2,
      "outgoing_edges": 1,
      "instability": 0.333,
      "stability_role": "balanced",
      "evidence": "top-level static imports"
    }
  ],
  "cycles": [
    {
      "path": ["domain", "infrastructure", "domain"],
      "length": 2,
      "evidence": "top-level static import cycle"
    }
  ],
  "summary": {
    "component_count": 3,
    "internal_edge_count": 3,
    "cycle_count": 1,
    "max_efferent_coupling": 1,
    "max_afferent_coupling": 2
  },
  "interpretation": {
    "summary": "Static structure metrics are warning signals for architecture review.",
    "limitations": "Top-level import metrics miss runtime calls, generated code, reflection, ownership, and domain intent."
  },
  "next_actions": ["inspect cycle against intended architecture"]
}
```

Allowed stability roles: `isolated`, `stable`, `balanced`, `volatile`, `unknown`.

Use these metrics to prioritize source inspection. Do not treat a high or low metric as an automatic architecture finding without a scenario, intended rule, or quality-attribute impact.

## `architecture_intelligence.decision.v1`

Required fields:

```json
{
  "schema": "architecture_intelligence.decision.v1",
  "decision_id": "kebab-case-id",
  "title": "decision title",
  "status": "proposed",
  "decision_type": "module-boundary",
  "context": {
    "problem": "decision context",
    "forces": ["constraint or quality attribute"],
    "evidence": [
      {
        "source": "path, doc, command, metric, or user-provided source",
        "claim": "what this evidence supports",
        "strength": "medium"
      }
    ],
    "assumptions": ["bounded assumption"]
  },
  "options_considered": [
    {
      "option": "option name",
      "pros": ["advantage"],
      "cons": ["tradeoff"]
    }
  ],
  "decision": "chosen decision",
  "rationale": "why this option wins",
  "rationale_quality": {
    "alternatives_complete": "pass",
    "tradeoffs_named": "pass",
    "evidence_strength": "medium",
    "knowledge_vaporization_risk": "low"
  },
  "consequences": ["accepted consequence"],
  "fitness_functions": ["validation signal or gate"],
  "owner_or_review_path": "team, role, or review path",
  "expires_or_revisit_trigger": "condition that reopens decision"
}
```

Allowed statuses: `proposed`, `accepted`, `rejected`, `superseded`, `needs-validation`.

Allowed decision types:

- `module-boundary`
- `dependency-rule`
- `data-ownership`
- `ownership-governance`
- `runtime-topology`
- `platform-choice`
- `integration-style`
- `quality-attribute`
- `migration-strategy`
- `documentation-governance`

Allowed rationale quality values:

- `alternatives_complete`: `pass`, `risk`, `unknown`
- `tradeoffs_named`: `pass`, `risk`, `unknown`
- `evidence_strength`: `low`, `medium`, `high`
- `knowledge_vaporization_risk`: `low`, `medium`, `high`

## `architecture_intelligence.fitness_plan.v1`

Required fields:

```json
{
  "schema": "architecture_intelligence.fitness_plan.v1",
  "target": "repo, service, package, or architecture decision",
  "architecture_principle": "rule or quality attribute to preserve",
  "rules": [
    {
      "id": "kebab-case-id",
      "intent": "what the rule protects",
      "scope": "files, packages, services, or runtime path",
      "quality_attribute": "modifiability",
      "tradeoff": "what this rule may make harder",
      "signal": "observable evidence",
      "mechanism": "tool, test, script, metric, or review gate",
      "pass_condition": "objective threshold",
      "cadence": "ci",
      "owner": "team, role, or review path",
      "failure_action": "what happens when the rule fails"
    }
  ],
  "rollout": {
    "mode": "warn",
    "migration_notes": ["how legacy violations are handled"]
  }
}
```

Allowed cadence values: `local`, `pre-commit`, `ci`, `release`, `scheduled`, `production`.

Allowed rollout modes: `measure`, `warn`, `enforce`.

## `architecture_intelligence.refactor_report.v1`

Use after architecture-changing refactors that should remain reviewable after the session; links the observed baseline, skill route, changed boundary, proof, and residual risks.

Required fields:

```json
{
  "schema": "architecture_intelligence.refactor_report.v1",
  "target": "repo, service, package, module, or refactor slice",
  "summary": "one paragraph result and architecture consequence",
  "route": {
    "skills_used": ["codebase-architecture-audit"],
    "skipped_skills": [
      {
        "skill": "architecture-runtime-topology",
        "reason": "no runtime paths changed"
      }
    ],
    "source_evidence": ["docs/architecture.md", "architecture_probe.py --json"]
  },
  "before": {
    "dirty_tree_state": "dirty",
    "baseline_evidence": ["git status --short", "pre-probe.json"],
    "architecture_risks": ["duplicated domain logic in UI store"],
    "pre_probe": "path, command, or explicit skip reason"
  },
  "refactor": {
    "target_boundary": "Core owns snapshot enrichment; UI coordinates display",
    "quality_attributes": ["modifiability", "testability"],
    "slices": [
      {
        "id": "extract-snapshot-enrichment",
        "intent": "move domain enrichment from UI store to core",
        "files_changed": ["Sources/Core/SnapshotUsageEnricher.swift"],
        "behavior_preserving": true,
        "validation": ["swift test"],
        "rollback": "revert slice commit"
      }
    ]
  },
  "proof": {
    "tests": ["swift test"],
    "fitness_functions": ["core boundary test"],
    "docs_updated": ["docs/ARCHITECTURE.md"],
    "post_probe": "path, command, or explicit skip reason",
    "runtime_verification": "smoke test, release gate, or explicit skip reason"
  },
  "residual_risks": [
    {
      "id": "dirty-tree-review-risk",
      "severity": "P2",
      "evidence": "pre-existing UI files were modified before the refactor",
      "mitigation": "review architecture-owned diff separately"
    }
  ],
  "next_actions": ["add CI architecture policy"]
}
```

Allowed dirty tree states: `clean`, `dirty`, `unknown`.

Allowed severities: `P0`, `P1`, `P2`, `P3`.

## `architecture_intelligence.runtime_topology.v1`

Runtime architecture evidence from source, config, deployment, and operational signals.

```json
{
  "schema": "architecture_intelligence.runtime_topology.v1",
  "target": "repo, service, system, or runtime slice",
  "observed_model_source": "architecture_probe.py repository file and signal scan",
  "surfaces": [
    {
      "type": "deployment",
      "name": "container",
      "evidence": ["Dockerfile"],
      "confidence": "medium"
    },
    {
      "type": "observability",
      "name": "opentelemetry",
      "evidence": ["app/main.py"],
      "confidence": "low"
    }
  ],
  "topology_hypotheses": [
    {
      "id": "runtime-integration-present",
      "claim": "Runtime integrations may define architecture coupling beyond source imports.",
      "evidence": "app/main.py",
      "confidence": "low",
      "validation": "Trace representative runtime calls and failure modes."
    }
  ],
  "quality_attribute_gaps": [
    {
      "attribute": "availability",
      "signal": "no timeout, retry, circuit-breaker, fallback, bulkhead, rate-limit, or health-check terms detected",
      "risk": "unknown"
    }
  ],
  "summary": {
    "deployment_artifacts": 1,
    "runtime_config_files": 0,
    "observability_signals": 1,
    "resilience_signals": 0,
    "integration_signals": 1
  },
  "limitations": ["Signals are path and term based; they do not prove runtime behavior."],
  "next_actions": ["Map deployment artifacts to runtime components and ownership."]
}
```

Allowed surface types: `deployment`, `runtime-config`, `observability`, `resilience`, `integration`, `data-store`, `runtime-adaptation`.

Allowed confidence values: `low`, `medium`, `high`.

Allowed gap risks: `low`, `medium`, `high`, `unknown`.

Never put secret values in this contract. Use paths, signal names, command outputs, topology diagrams, traces, or operational evidence.

## `architecture_intelligence.ownership_topology.v1`

Source-backed ownership evidence and coordination-risk signals.

```json
{
  "schema": "architecture_intelligence.ownership_topology.v1",
  "target": "repo, module set, monorepo package graph, service system, or runtime slice",
  "observed_model_source": "architecture_probe.py ownership document, static import, and runtime-surface scan",
  "ownership_sources": [
    {
      "path": ".github/CODEOWNERS",
      "type": "codeowners",
      "evidence": "ownership or governance document detected",
      "confidence": "medium"
    }
  ],
  "areas": [
    {
      "path": "web",
      "owners": ["@frontend"],
      "evidence": [".github/CODEOWNERS:2 /web/"],
      "coverage": "owned"
    },
    {
      "path": "legacy",
      "owners": [],
      "evidence": [],
      "coverage": "unowned"
    }
  ],
  "coordination_risks": [
    {
      "id": "cross-owned-web-to-api",
      "severity": "P2",
      "evidence": "web -> api static import edge count 3",
      "impact": "Architecture changes across this dependency may need coordination between different owner sets.",
      "recommendation": "Name the API or boundary contract and require review from both owner paths for architecture-changing work.",
      "confidence": "medium"
    }
  ],
  "summary": {
    "ownership_sources": 1,
    "owned_areas": 2,
    "unowned_areas": 1,
    "cross_owned_edges": 1,
    "ownerless_runtime_or_code_surfaces": 0
  },
  "limitations": ["Ownership files can be stale, partial, or unenforced."],
  "next_actions": ["Review cross-owned dependency edges against architecture intent."]
}
```

Allowed ownership source types: `codeowners`, `owners`, `owners-aliases`, `maintainers`, `governance`, `contributing`, `ownership-document`.

Allowed coverage values: `owned`, `unowned`, `unknown`.

Use this contract for ownership and coordination evidence. Do not infer actual team communication, workload, staffing, or branch-protection enforcement from repository files alone.
