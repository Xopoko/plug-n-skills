# Contracts

Design Intelligence can produce prose for humans, but machine-readable facts should use the JSON shape below.

## `design_intelligence.review.v1`

Required top-level fields:

```json
{
  "schema": "design_intelligence.review.v1",
  "surface": "product, flow, screen, feature, or system being reviewed",
  "context": {
    "user": "primary user or segment",
    "task": "task or decision context",
    "evidence": ["screenshots, docs, source files, URLs, observations"],
    "assumptions": ["bounded assumptions"]
  },
  "summary": "one-paragraph design judgment",
  "findings": [
    {
      "id": "stable-kebab-id",
      "severity": "P1",
      "lens": "interaction",
      "evidence": "observable evidence",
      "principle": "heuristic, standard, or source-backed principle",
      "impact": "user/product consequence",
      "recommendation": "specific change",
      "confidence": "medium",
      "requires_validation": true
    }
  ],
  "quality_gates": {
    "accessibility_floor": "pass|risk|unknown",
    "task_success": "pass|risk|unknown",
    "ethical_ux": "pass|risk|unknown",
    "system_fit": "pass|risk|unknown"
  },
  "next_actions": ["ordered next steps"]
}
```

Allowed `lens` values:

- `product-fit`
- `interface-architecture`
- `interaction`
- `accessibility`
- `cognitive-load`
- `visual-communication`
- `ethics-trust`
- `system-governance`

Allowed `severity` values: `P0`, `P1`, `P2`, `P3`.

Allowed `confidence` values: `low`, `medium`, `high`.

Use `requires_validation: true` when a finding depends on live assistive technology behavior, user behavior, analytics, performance, device constraints, or domain facts not directly checked.

Optional surface-specific fields:

```json
{
  "surface_type": "form",
  "pattern_obligations": [
    {
      "obligation": "error repair path",
      "status": "risk",
      "evidence": "validation errors are shown but do not explain how to fix them"
    }
  ],
  "validation_limits": ["keyboard focus order was not inspected live"]
}
```

Allowed `surface_type` values:

- `flow`
- `form`
- `data-view`
- `search-browse`
- `navigation`
- `onboarding`
- `permission-consent`
- `notification-status`
- `empty-error-recovery`
- `settings-admin`
- `content-screen`
- `transaction`
- `design-system-pattern`

Allowed pattern-obligation `status` values: `met`, `risk`, `unknown`, `not-applicable`.

## `design_intelligence.decision.v1`

Use this for durable product, IA, interaction, visual, accessibility, or design-system decisions.

Required top-level fields:

```json
{
  "schema": "design_intelligence.decision.v1",
  "decision_id": "stable-kebab-id",
  "title": "short decision title",
  "decision_type": "product-framing",
  "surface": "product, flow, screen, pattern, or system",
  "status": "proposed",
  "context": {
    "user": "primary user or segment",
    "task": "job, task, or decision context",
    "evidence": [
      {
        "source": "stable URL, local file, screenshot id, research note, analytics source, or observation",
        "source_type": "standard",
        "claim": "specific evidence claim used by the decision",
        "strength": "high"
      }
    ],
    "assumptions": ["bounded assumptions"]
  },
  "decision": "what should be true in the product or system",
  "rationale": "why this decision is better than plausible alternatives",
  "alternatives_rejected": [
    {
      "alternative": "rejected option",
      "reason": "why it lost"
    }
  ],
  "accessibility_requirements": ["keyboard, focus, semantics, contrast, motion, cognitive support, or none with reason"],
  "behavioral_requirements": ["states, feedback, recovery, content, or governance obligations"],
  "validation_plan": [
    {
      "method": "usability-test",
      "signal": "observable signal",
      "pass_condition": "what would count as success"
    }
  ],
  "counter_metrics": ["signals that must not get worse"],
  "owner_or_review_path": "person, team, design-system process, or unresolved owner",
  "expires_or_revisit_trigger": "date, release, metric threshold, or evidence gap"
}
```

Allowed `decision_type` values:

- `product-framing`
- `interface-architecture`
- `interaction`
- `accessibility`
- `visual-communication`
- `design-system-governance`
- `ethics-trust`

Allowed `status` values: `proposed`, `accepted`, `rejected`, `superseded`, `needs-validation`.

Allowed evidence `source_type` values: `observed-product`, `user-research`, `analytics`, `support`, `standard`, `platform-guidance`, `design-system`, `scholarly`, `benchmark`, `heuristic`, `stakeholder`.

Allowed evidence `strength` values: `low`, `medium`, `high`.

Use at least one evidence item. If evidence is only heuristic or stakeholder input, keep `status` as `proposed` or `needs-validation`.

Optional surface-specific fields:

```json
{
  "surface_type": "data-view",
  "pattern_obligations": [
    {
      "obligation": "comparison criteria",
      "status": "met",
      "evidence": "primary columns map to the user's decision criteria"
    }
  ],
  "validation_limits": ["table density was not tested with localized labels"]
}
```

Use these fields when the decision governs a common UI pattern and the pattern obligations should remain reusable outside a specific implementation technology.
