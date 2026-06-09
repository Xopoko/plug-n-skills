---
name: product-framing
description: "Frame product and UX decisions before interface work: strategy, user needs, Jobs-to-be-Done, outcome mapping, opportunity-solution trees, HEART/GSM, problem statements, assumptions, discovery plans."
---

# Product Framing

Use before interface recommendations when problem, user outcome, segment, or evidence is unclear. Goal: prevent designing the wrong screen for the wrong reason, not create workshop artifacts.

## Core Model

Frame:

1. User/context: actor, situation, constraints.
2. Need/job: progress sought.
3. Outcome: observable user or business state to improve.
4. Opportunity: pain, motivation, barrier, or unmet need.
5. Solution bet: candidate interface or behavior change.
6. Evidence: research, analytics, support, observation, or source.
7. Metric/counter-metric: value signal and guardrail.

Evidence strength: user behavior, usability sessions, analytics, support logs, and production traces outrank stakeholder preference; primary standards/platform guidance outrank blog summaries; heuristics are risk signals, not proof.

Frameworks:

- Double Diamond: discover evidence, define problem/success, develop bets, deliver smallest testable intervention.
- Opportunity Solution Tree: outcome -> opportunities -> solution bets -> evidence/criteria.
- HEART/GSM: happiness, engagement, adoption, retention, task success; goal -> signal -> metric; counter-metric.

## Questions To Resolve

Ask only if missing context would materially change the recommendation:

- Which user segment is this for?
- What task or outcome matters most?
- Is the main risk desirability, usability, feasibility, viability, or trust?
- What evidence already exists?
- What existing product or workflow should this preserve?

## Output

Produce:

1. **Problem frame**: one compact problem statement.
2. **Primary user outcome**: observable and specific.
3. **Assumptions**: ranked by risk.
4. **Opportunity map**: 3-7 opportunities, not features.
5. **Solution principles**: constraints for interface work.
6. **Metric plan**: goal, signal, metric, counter-metric.
7. **Smallest next step**: design, research, prototype, or measurement action.

For durable product decisions, use `design_intelligence.decision.v1` from `references/contracts.md`.

## Quality Bar

Good framing makes weak UI asks sharper. If it still sounds like "make it cleaner" or "improve UX," continue framing.

Avoid:

- generic personas without behavior evidence;
- invented metrics;
- feature lists disguised as opportunities;
- business-only goals with no user outcome;
- user-only goals with no product constraint;
- engagement metrics without counter-metrics.
