# Decision Evidence Contract

Use this reference for load-bearing evidence, experiments, benchmarks, and
machine- or model-assisted rationale. It complements the compact decision rules
in `evidence-methodology.md`.

## Three Clocks

Never collapse these timestamps:

- `published_at`: when the source became public;
- `measurement_window.start` and `.end`: when the underlying sample, telemetry,
  benchmark, or observation was collected;
- `retrieved_at`: when this snapshot inspected the source.

A recent retrieval proves access, not current evidence. A recent publication
can report old measurements. An undated live page can still be useful first-
party documentation, but it does not satisfy a bounded publication window.
Use `evidence-window` to report that distinction explicitly.

## Claim Receipt

For a decision-changing claim, preserve enough context to reproduce its
interpretation:

- stable source and observation IDs, direct locator, edition or revision;
- publication, measurement, retrieval, and observation dates;
- evidence mode: documentation, release, survey, telemetry, benchmark,
  experiment, security analysis, or expert opinion;
- claim type: descriptive, association, or causal;
- population, sample, recruitment, candidate selection, and geography when
  applicable;
- scope, limitations, plausible confounders, and candidate affiliation;
- whether extraction or rationale was machine-assisted, the model/version and
  prompt or input hash, and human verification status;
- invalidation triggers such as candidate version, framework, model, hardware,
  precision, workload, security advisory, or support-policy change.

Do not upgrade association language to causation. A source is independent only
relative to the candidate being assessed; foundation, registry, and steward
material can be affiliated even when its global role is `independent-signal`.

## Radar, Survey, And Generated Rationale

A radar ring is an opinionated, sampled ecosystem signal, not a plugin
disposition. Record sample size, familiarity filter, recruitment, geography,
candidate selection, scoring formula, and subjective share before using it.
Foundation lifecycle stage, registry presence, downloads, and stars have the
same boundary: context, not fit proof.

Model-generated rationale is `proposed` until a person verifies every
load-bearing argument against cited evidence and project context. Helpful extra
arguments may be retained as hypotheses; unsupported arguments cannot justify
a positive disposition.

## Experiment Receipt

Turn a verification gap into a bounded experiment with:

- `decision_id`, hypothesis, scope, environment, candidate and version;
- prerequisites, controlled variables, workload or scenario;
- metrics, thresholds, stop condition, and expected decision consequence;
- artifact and configuration hashes;
- result: `pass`, `fail`, or `inconclusive`;
- limitations, anomalies, and reviewer.

The experiment must be reversible and must not promote prototype code to
production automatically. A result without a predeclared threshold or stop
condition is an anecdote, not a decision receipt.

## Benchmark Receipt

A comparative performance claim requires candidate versions, topology,
hardware, configuration, dataset, workload, scale points, ground truth where
relevant, fixed seeds, repetitions, aggregation, variability, and excluded
capabilities. Report confidence intervals or another stability measure for a
subset-derived ranking. Do not generalize a single-node or single-workload
result beyond its declared scope.

Framework or model changes normally require remeasurement. Hardware or
precision changes require at least paired review. A remaining time-to-live does
not override a material invalidation trigger.

## Contradictions And Revalidation

Store conflicting claims independently with polarity, provenance,
`known_since`, and justification. Resolve them through a separate review note;
do not rewrite the source claim. Staleness triggers revalidation, not deletion
or automatic downgrade. Record one of:

- `stale_unchecked`;
- `revalidated_stable`, with paired snapshot IDs and support delta;
- `changed_materially`, with the affected assessment or experiment.

A large source diff need not change a conclusion, and a small diff can reverse
one. Review semantic support, not byte volume alone.

## Research Basis: 2026-02-11 Through 2026-08-11

The following primary or official sources informed this contract. Their
mechanisms were distilled; no external code or instructions were installed or
executed.

- OECD, [Building capacity in technology horizon scanning](https://doi.org/10.1787/b4f0d383-en),
  2026-04-14: separates corpus coverage and selection from AI-assisted
  extraction, and cautions about bias, prompt sensitivity, hallucination, and
  loss of critical review.
- CNCF, [The CNCF Technology Radar Report: Workflow Orchestration, App Delivery and Security & Policy Management](https://www.cncf.io/reports/q1-2026-the-cncf-technology-radar-report/),
  2026-03-23: discloses its 422-person familiarity-filtered survey and says
  radar position need not match project maturity.
- OpenSSF and Linux Foundation,
  [2026 CRA Awareness and Readiness Report](https://openssf.org/wp-content/uploads/2026/06/2026_CRA_Awareness_Readiness_Report.pdf),
  June 2026: demonstrates why survey field dates and older telemetry windows
  must stay separate from publication date and why association is not causation.
- ICSA 2026,
  [Architecture Decision Records: Adoption, Impact, and Developer Engagement](https://conf.researchr.org/details/icsa-2026/icsa-2026-papers/34/Architecture-Decision-Records-Adoption-Impact-and-Developer-Engagement-in-Open-Sou),
  2026-06-26: finds mostly small correlations and many ADRs created directly as
  accepted, so record count and status do not prove deliberation quality.
- ACM TOSEM,
  [Using LLMs in Generating Design Rationale for Software Architecture Decisions](https://doi.org/10.1145/3785010),
  2026-07-16: reports limited precision for generated rationale and practitioner
  reluctance to trust unvalidated output.
- Antognolli and Petrillo,
  [Proof of Concept as a First-Class Architectural Decision Instrument](https://arxiv.org/abs/2604.05835),
  2026-04-07: motivates hypothesis-, metric-, and stop-condition-bound PoCs;
  evidence is an early preprint and practitioner synthesis.
- Frontiers in Computer Science,
  [A unified benchmarking framework for vector databases](https://doi.org/10.3389/fcomp.2026.1819991),
  2026-07-14: uses fixed seeds, controlled resets, ground truth, repetitions,
  aggregation, and variability while limiting claims to its tested topology.
- MLSys 2026, [DriftBench](https://proceedings.mlsys.org/paper_files/paper/2026/hash/ea0b5818ae9255ee1fb1e3b4442d2ffe-Abstract-Conference.html),
  2026: shows that some serving-stack changes produce idiosyncratic
  behavioral drift and therefore require remeasurement.
- Provenance-bound evidence from Kuissi et al.,
  [Still Fresh? Evaluating Temporal Drift in Retrieval Benchmarks](https://arxiv.org/abs/2603.04532),
  2026-03-04: a large documentation diff did not necessarily invalidate support
  or rankings, motivating explicit semantic revalidation states.
- Gusev and Zaytsev,
  [Benchmarking on Tasks That Matter](https://arxiv.org/abs/2606.27997),
  2026-06-26: subset rankings require random baselines and uncertainty estimates;
  gains can be small and domain-dependent.

Preprints remain provisional. Recheck the current version and its limitations
before a high-stakes decision.
