# Evidence And Decision Methodology

Use this reference when interpreting or changing an assessment.

## Separate Facts From Decisions

An observation is a dated, attributable statement from a source. An assessment
is a contextual judgment that cites observations. Never encode a recommendation
as an observation or silently turn a survey rank, star count, download count,
foundation stage, or security score into a recommendation.

Publication date, measurement window, retrieval date, and observation date are
different facts. A newly retrieved old source is not fresh evidence for a
bounded research window, and a recent report can contain stale telemetry.

The evidence hierarchy is:

1. candidate first-party documentation, repository, release, support, security,
   compatibility, and license facts;
2. independent primary ecosystem, foundation, survey, telemetry, or security
   signals;
3. explicitly scoped expert opinion and radar material.

A positive assessment (`recommend`, `consider`, or `pilot`) requires at least
one first-party observation and either an independent signal or a concrete
`verification_gap`. A gap is not evidence; it makes the limitation visible and
normally lowers confidence or narrows the proposed experiment.

## Decision Profile

Bind at least lifecycle stage and use case. Add constraints that can change the
answer:

- team experience and ownership capacity;
- platform, language, data shape, and integration boundaries;
- delivery horizon and reversibility;
- scale, latency, availability, durability, and operability;
- data sensitivity, security, compliance, and supply-chain exposure;
- budget, licensing, vendor dependence, and exit cost;
- deployment environment, offline needs, and runtime availability.

`experiment`, `startup`, `scale-up`, and `enterprise-critical` are different
profiles, not maturity ranks. A low-operations choice can be correct for an
experiment and wrong for a regulated system; a mature orchestration platform
can be correct at scale and needless for a small service.

## Assessment Rules

Apply hard gates before tradeoffs. Compare dimensions directly rather than
producing a universal composite score:

- functional and platform fit;
- maturity and compatibility;
- maintenance and governance;
- security and dependency exposure;
- ecosystem and team fit;
- operational load and failure modes;
- cost, licensing, lock-in, and migration cost;
- evidence freshness and uncertainty.

Preserve negative evidence and conflicting signals. Do not treat absent known
vulnerabilities as proof of safety, a foundation listing as endorsement, survey
interest as production adoption, or registry presence as runtime trust.

Staleness triggers revalidation rather than automatic deletion or downgrade.
Material version, framework, model, hardware, precision, workload, support, or
security changes can require remeasurement before the nominal expiry date.
Treat model-generated rationale as proposed until its load-bearing arguments
are verified against cited evidence and project context.

## Output Quality

A useful recommendation includes a dated profile, hard gates, direct evidence,
confidence, gaps, rejected alternatives, and a reversible next experiment. If
the evidence does not distinguish candidates, say so and propose the cheapest
discriminator instead of inventing certainty.

Load `decision-evidence-contract.md` for measurement windows, candidate-relative
independence, experiment and benchmark receipts, generated-rationale review,
contradiction handling, and the February-August 2026 research basis.
