# Structure Metrics Reference

Structure metrics help prioritize architecture inspection. They are warning signals, not final judgments.

## Metrics

- Afferent coupling (`Ca`): number of top-level components that depend on this component. High `Ca` can indicate a stable core or a risky central dependency.
- Efferent coupling (`Ce`): number of top-level components this component depends on. High `Ce` can indicate change amplification or broad coordination cost.
- Instability (`I`): `Ce / (Ca + Ce)`. Values near `1` are outward-dependent and volatile; values near `0` are depended on more than they depend outward.
- Dependency cycle: a directed cycle among top-level static import edges. Cycles are often erosion signals, but the intended architecture decides whether they are real findings.

## Interpretation Rules

Use metrics with source context:

1. Inspect high fan-out components for hidden orchestration, framework bleed, and broad change paths.
2. Inspect high fan-in components for stable public APIs, ownership, and backward compatibility pressure.
3. Inspect cycles against ADRs, package rules, and runtime boundaries before recommending a split.
4. Combine metric signals with scenarios, quality attributes, and recent change evidence.
5. Convert repeated metric risks into fitness functions only after the intended rule is explicit.

## Technical Debt Framing

For structural debt, name:

- principal: effort to remove or isolate the structural problem;
- interest: recurring change, review, defect, build, or coordination cost while it remains;
- repayment trigger: the scenario or delivery pressure that makes repayment worthwhile;
- exception path: when the debt is accepted temporarily and how it will be revisited.

## Limits

- Top-level import metrics miss runtime calls, dependency injection, generated code, reflection, ownership, and data coupling.
- Language import syntax is approximated by the probe; use project-native graph tools when exactness matters.
- Healthy architectures can have central stable modules. A metric becomes a finding only when tied to an architecture rule, scenario, or quality-attribute impact.
