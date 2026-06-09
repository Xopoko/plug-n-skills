# Architecture Scorecards

Use these scorecards to keep architecture review concrete.

## Audit Score

Score each lens from 0 to 3.

| Lens | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| Boundary clarity | No clear module/service ownership | Informal boundaries only | Mostly clear with leakage | Explicit APIs and ownership |
| Dependency direction | Cycles or arbitrary imports | Direction implied but unenforced | Direction mostly followed | Direction enforced by tests/tools |
| Domain fit | Technical layers hide domain | Mixed domain language | Bounded areas visible | Contexts and data ownership are explicit |
| Change locality | Small changes touch many areas | Common change amplification | Most changes stay local | Change paths are narrow and predictable |
| Structure metrics | Metrics absent or ignored | Fan-in/fan-out known only manually | Cycles and hotspots are measured | Metrics are tied to scenarios and gates |
| Ownership topology | Owners and review paths are tribal | Some paths have owners but coverage is uneven | Architecture-significant areas have visible owners | Cross-owned edges and ownerless surfaces are gated or documented |
| Runtime topology | Deployment/runtime unknown | Deployment paths known but not mapped | Runtime dependencies and signals visible | Runtime topology is owned, tested, and observed |
| Runtime resilience | Failure modes unknown | Some timeouts/retries | Critical paths covered | Resilience behavior tested/observed |
| Testability | Architecture resists testing | Tests exist but miss boundaries | Important seams testable | Boundary/contract/architecture tests exist |
| Observability | No usable signals | Logs only | Metrics/traces for critical paths | Signals tied to SLOs and decisions |
| Decision record | Decisions tribal | Some stale docs | ADRs exist for major choices | ADRs have owners, status, and revisit triggers |
| Scenario coverage | No scenarios | Generic quality claims | Key scenarios named | Scenarios have measurable responses |
| Debt propagation | Unknown spread | Local smell only | Spread understood | Propagation risk measured and gated |
| Conformance | No intended model | Intent exists but is not checked | Key rules checked manually | Rules are measured and regression-gated |

Interpretation:

- 0-12: architecture facts are missing or risky; start with discovery and guardrails.
- 13-25: architecture can work but has visible drift; prioritize top P1/P2 risks.
- 26-36: mostly healthy; add focused fitness functions.
- 37-39: strong; preserve with lightweight governance.

## Risk Priority

Rank findings by:

1. User, data, security, or release impact.
2. Change amplification and team blockage.
3. Debt propagation, principal, and interest.
4. Cycles, high fan-out, and co-change hotspots.
5. Cross-owned dependencies and ownerless architecture-significant areas.
6. Runtime coupling, deployment drift, and operability gaps.
7. Irreversibility and migration cost.
8. Evidence strength.
9. Validation cost.

## Architecture Finding Test

A valid finding should answer:

- What source evidence proves the issue?
- Which scenario makes the issue observable?
- Which quality attribute is hurt?
- What concrete change reduces the risk?
- How will we know the change worked?
- What gets worse or more expensive?

If any answer is missing, mark confidence lower or convert the finding into an investigation task.

## Scenario Review

For important findings, capture:

| Field | Question |
| --- | --- |
| Stimulus | What change, load, failure, threat, or team action triggers the concern? |
| Environment | Does it happen during normal operation, peak load, incident, release, migration, or maintenance? |
| Response | What should the architecture do? |
| Response measure | What concrete signal proves success or failure? |
| Tradeoff | Which quality attribute improves, and which one becomes harder? |

## Conformance Review

For intended-vs-observed checks, capture:

| Field | Question |
| --- | --- |
| Intended source | Which ADR, doc, policy, or explicit constraint defines the rule? |
| Observed source | Which source path, import edge, probe output, build graph, or trace shows reality? |
| Classification | Is this convergence, divergence, absence, or unknown? |
| Exception path | Is the difference documented, time-bounded, and owned? |
| Validation | Which check prevents regression after repair? |
