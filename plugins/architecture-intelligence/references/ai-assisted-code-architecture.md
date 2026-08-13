# AI-Assisted Code Architecture

## Scope

The object of this workflow is the architecture of application and library code: modules, layers, dependency direction, public APIs, domain and data ownership, extension points, runtime coupling, and quality attributes. Codex, Claude Code, and similar coding agents are analysis, design, implementation, and review tools. Their own runtime architecture is out of scope.

Use this reference with `codebase-architecture-audit`, `architecture-conformance`, `architecture-decisions`, `architecture-refactoring-strategy`, and `architecture-fitness-functions`.

## Research Snapshot

This review was completed on 2026-08-11. The inclusive publication and material-revision window is 2026-05-11 through 2026-08-11.

One direct empirical study in the window evaluates source-grounded conformance of generated patches to repository-specific architectural conventions. Its architectural labels rely on an LLM judge without reported agreement with independent human architects. No longitudinal controlled study of agent-induced architecture drift, conformance against explicit ADR or policy intent, or agent-versus-human effects on coupling, cohesion, cycles, or API-boundary quality was identified.

The practical conclusion is bounded: coding agents can broaden architecture recovery, option generation, implementation, and review, but their architecture claims remain hypotheses until source evidence and deterministic project checks confirm them.

## Evidence-Derived Rules

1. Functional correctness is necessary but does not prove architectural conformance.
2. Recover explicit intent and observed source conventions separately. Source shape is evidence, not design authority.
3. Explore outward from changed code through callers, callees, interfaces, shared state, sibling implementations, subclasses, importers, and downstream consumers.
4. Evaluate architecture-significant patches with repository- and issue-specific rubric axes, not generic style preferences.
5. Ask agents for design options and counterarguments; keep the architecture decision with the accountable reviewer and record it when the ADR threshold is crossed.
6. Separate requested behavior from incidental refactoring. Tangled refactors widen blast radius and can reduce compilability without improving correctness.
7. Implement and prove one smallest architecture slice at a time.
8. Separate review from mutation: produce a finding set first, then run a controlled fix pass and repeat functional plus architecture checks.
9. Treat repository guidance as a discovery source, not a substitute for source, diff, tests, dependency evidence, or runtime proof.

## Architecture-First Workflow

### 1. Classify The Change

Classify the task as bug fix, feature addition, behavior-preserving refactor, migration, or architecture change. Name the code-level architecture risk: module boundary, layering, dependency direction, public API, data ownership, extension point, cross-cutting convention, runtime coupling, or propagation width.

### 2. Recover Intent And Observed Architecture

- Explicit intent: user constraints, ADRs, architecture docs, policy files, package rules, API contracts, ownership rules, and accepted quality scenarios.
- Observed architecture: source tree, imports, manifests, build graph, entry points, implementations, tests, runtime configuration, and recent changes.
- Unknowns: inaccessible, excluded, generated, dynamic, or uninspected surfaces.

Run `architecture_probe.py` when its static signals are useful. An agent-generated diagram or summary is a hypothesis; bind every important edge and responsibility to a path, symbol, command, or runtime trace.

### 3. Map Ripple Effects

Start from the requested and changed symbols, then inspect:

- defining component and responsibility;
- callers and callees;
- interfaces, base classes, subclasses, and sibling implementations;
- imports, public entry points, and downstream consumers;
- shared state, schemas, storage, events, and runtime integrations;
- tests, architecture policies, and ownership paths.

Record both the directly changed surface and the cross-module blast radius. Context retrieval can miss critical files, so explicitly list gaps and lower confidence instead of implying whole-repository coverage.

### 4. Build A Source-Grounded Rubric

Use only axes that matter to this issue and repository:

| Axis | Questions |
| --- | --- |
| Components and responsibilities | Does behavior live in the component that owns it? |
| Dependency direction and layering | Did the patch add a reverse edge, bypass, cycle, or framework leak? |
| Public API and extension points | Does the change use the intended seam and preserve consumers? |
| Domain and data ownership | Did write authority, invariants, or transaction boundaries move? |
| Cross-cutting conventions | Are errors, configuration, observability, security, or persistence handled through the established boundary? |
| Runtime coupling | Did calls, queues, jobs, caches, deployment, or failure modes change? |
| Change propagation | Is the touched width necessary, or did incidental refactoring amplify it? |

For each selected axis record priority, source evidence, confidence, ideal anchor, poor anchor, and a plausible-but-wrong implementation path. Use `architecture_intelligence.conformance.v1` only when explicit intent exists; otherwise report alignment or deviation from observed conventions as an audit finding.

### 5. Compare Design Options

Use one or more independent passes to generate options, tradeoffs, and counterexamples. Agents are useful as a sounding board, but recent evidence reports context gaps and inconsistent recommendations. The final choice must name the protected quality attribute, accepted tradeoff, reversibility, validation, owner or review path, and revisit trigger. Use `architecture_intelligence.decision.v1` when the choice crosses the ADR threshold.

### 6. Execute One Slice

Choose the smallest behavior-preserving code-boundary change that reduces the named risk. Add characterization or contract tests before moving behavior. Keep behavior changes, schema/API migrations, and incidental cleanup in separate slices.

After each slice:

1. compile, type-check, lint, and run focused tests as applicable;
2. run the relevant dependency, cycle, conformance, ownership, runtime, or architecture fitness check;
3. inspect the actual diff, public surface, and blast radius;
4. stop on unexplained failure, unexpected file, new dependency direction, public-contract drift, or unplanned scope expansion;
5. proceed only after the slice is proven.

### 7. Review Before Fixing

Run an independent architecture review against source, intent, rubric, and diff. The reviewer should produce findings before proposing mutations. Ask what would falsify the claimed improvement and whether tests can pass while a boundary, consumer, runtime path, or ADR is broken. Apply accepted fixes in a separate pass and rerun the affected proof.

### 8. Close The Architecture Loop

Finish with full validation, before/after probe comparison when static evidence was used, runtime smoke or an explicit skip reason, ADR disposition, residual structural gaps, and rollback. Save durable work as `architecture_intelligence.refactor_report.v1`.

## Optional `architecture_assessment` Appendix

Add this object to a refactor report when an AI-assisted change needs durable architecture review evidence:

```json
{
  "architecture_assessment": {
    "change_type": "behavior-preserving-refactor",
    "intended_model_sources": ["ADR or policy path"],
    "recovered_conventions": ["observed source-backed convention"],
    "affected_components": ["component and responsibility"],
    "boundary_edges_before": ["source -> target relation"],
    "boundary_edges_after": ["source -> target relation"],
    "public_api_changes": ["none or named change"],
    "dependency_direction": "preserved, improved, regressed, or unknown",
    "cross_module_blast_radius": ["caller, importer, consumer, schema, or runtime path"],
    "rubric_axes": [
      {
        "axis": "dependency-direction",
        "priority": "high",
        "ideal_anchor": "domain remains independent of adapters",
        "poor_anchor": "domain imports an adapter implementation",
        "evidence": ["path, symbol, command, or trace"],
        "confidence": "high"
      }
    ],
    "plausible_wrong_paths": ["locally correct change that bypasses the public boundary"],
    "structural_gaps": ["unverified runtime edge"],
    "functional_proof": ["test command and result"],
    "architecture_fitness_proof": ["dependency or policy check and result"],
    "adr_disposition": "created, updated, superseded, unnecessary, or unresolved"
  }
}
```

This is an optional evidence appendix, not a new schema. The existing refactor-report validator permits additional fields but does not validate this appendix independently.

## Stress Scenarios

| ID | Code-architecture scenario | Required response |
| --- | --- | --- |
| AICA-01 | An agent patch passes tests but bypasses a public module API | Trace import and consumer edges, reject the bypass, add a boundary check |
| AICA-02 | Domain behavior moves into UI or infrastructure | Compare responsibilities and dependency direction before and after |
| AICA-03 | A new dependency closes a package cycle | Identify the rule, choose a seam, and prove the cycle is removed |
| AICA-04 | An agent proposes splitting a module | Compare at least two boundaries against cohesion, coupling, ownership, and migration cost |
| AICA-05 | A base class or extension point changes | Inspect subclasses, sibling implementations, importers, and downstream consumers |
| AICA-06 | A multi-file refactor mixes requested behavior and cleanup | Separate slices and remove unnecessary tangled refactoring |
| AICA-07 | Source conventions and an ADR disagree | Treat the ADR as intent, report divergence, and use the exception or update path |
| AICA-08 | Architecture recovery omits a dynamic or generated edge | Record the gap, lower confidence, and obtain runtime or build evidence |
| AICA-09 | An independent review finds a structural gap | Freeze the finding set, fix separately, and rerun functional and architecture proof |
| AICA-10 | A slice expands beyond its named quality scenario | Stop, re-scope, or create a separately justified architecture decision |

## Direct Evidence

| Date | Source | Signal | Limitation |
| --- | --- | --- | --- |
| 2026-06-12, revised 2026-07-06 | [Beyond Correctness](https://arxiv.org/abs/2606.14948) | Source-grounded rubrics assess components, layering, dependency direction, extension mechanisms, conventions, boundaries, and cross-module effects | Architecture labels use the study's LLM judge; no reported independent human-architect agreement |
| 2026-07 | [LLMs as Assistants in Software Architecture Design](https://doi.org/10.1109/MS.2026.3663353) | LLMs generate relevant design options and counterpoints but can lack context and be inconsistent | Human architects retain final design judgment; article scope is design assistance, not autonomous refactoring |
| 2026-05-21 | [Refactoring Runaway](https://arxiv.org/abs/2605.22526) | Study of 3,691 agent patches links tangled refactoring to reduced compilability; a refactoring-aware pass improved compilability from 19.34% to 38.33% | Issue-resolution benchmark; compilability and functional correctness do not fully measure architecture quality |

## Strong Adjacent Evidence

| Date | Source | Transferable rule | Limitation |
| --- | --- | --- | --- |
| 2026-08-10 | [SWE-Bench ProMax](https://arxiv.org/abs/2608.09802) | Large behavior-preserving multi-file refactors need explicit, coordinated proof | Does not score module, layer, or API conformance directly |
| 2026-08-10 | [OpenCodeReview](https://arxiv.org/abs/2608.09290) | Cross-file dependency recovery plus independently scoped falsification improves review precision | Evaluates review comments, not final application architecture |
| 2026-08-10 | [SWE-RPG](https://arxiv.org/abs/2608.09072) | Requirements and implementation planning need repository-grounded evidence | Does not score structural conformance |
| 2026-08-03 | [SWE-Touch](https://arxiv.org/abs/2608.02499) | Reinspect source and rerun targeted tests after relevant concurrent edits | Tests collaborative workspace response, not architecture outcomes |
| 2026-07-27 | [Agent Retrieval Bench](https://arxiv.org/abs/2607.24882) | Retrieval can miss affected files and propagation paths | No final architecture outcome measure |
| 2026-07-08 | [DeepSWE](https://arxiv.org/abs/2607.07946) | Prefer solution-independent functional verifiers over inherited tests alone | Architecture is not an explicit outcome variable |

## Official Workflow Evidence

| Date | Source | Bounded use |
| --- | --- | --- |
| 2026-05-27 | [Self-improving tax agents with Codex](https://openai.com/index/building-self-improving-tax-agents-with-codex/) | Separate task, plan, results, targeted evaluation, regression evaluation, review, and candidate change; architecture and shipping judgment remain accountable decisions |
| 2026-05-21 | [Claude Code 2.1.147](https://github.com/anthropics/claude-code/releases/tag/v2.1.147) | Separate correctness-focused review findings from cleanup or mutation |
| 2026-05-27 | [Claude Code 2.1.152](https://github.com/anthropics/claude-code/releases/tag/v2.1.152) | Use accepted review findings as input to a distinct fix phase |
| 2026-07-19 | [Claude Code 2.1.215](https://github.com/anthropics/claude-code/releases/tag/v2.1.215) | Name review and verification gates explicitly instead of assuming they ran |
| 2026-07-22 | [Claude Code 2.1.218](https://github.com/anthropics/claude-code/releases/tag/v2.1.218) | An independently scoped review can reduce dependence on implementation narrative |
| 2026-06-12 | [GitHub code-review controls](https://github.blog/changelog/2026-06-12-copilot-code-review-new-configurations-and-controls/) | Record excluded or inaccessible source surfaces and lower confidence |
| 2026-06-18 | [GitHub code review and AGENTS.md](https://github.blog/changelog/2026-06-18-copilot-code-review-agents-md-support-and-ui-improvements/) | Discover repository-local instructions before review, while keeping source as proof |

Vendor sandboxing, concurrency, subagent limits, session transport, plugin catalogs, worktree implementation, messaging, and provider policy were deliberately excluded: they describe agent runtime behavior, not code architecture.

## AI-Assistance Disclosure

Codex performed search, metadata collection, title and abstract screening, primary-page checks, comparison, and synthesis. Deterministic ledgers recorded source status, screening decisions, claims, and quality-gate results. No independent human replication or full-paper peer review was performed for this snapshot.
