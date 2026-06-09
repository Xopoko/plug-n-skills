# Ownership Topology Reference

Ownership topology connects code structure, ownership evidence, and coordination risk. It is an architecture lens, not a social diagnosis.

## Core Lens

- Technical dependencies can imply coordination requirements.
- Conway-style alignment is useful as a hypothesis, but source files cannot prove actual communication.
- Code ownership and ownership gaps affect maintenance knowledge and review accountability.
- Architecture decisions and governance need explicit owner, review, exception, and validation paths.

## Evidence Classes

Use these evidence classes:

- `observed`: ownership files, dependency edges, runtime/deployment paths, ADR owner fields, branch protection evidence.
- `inferred`: cross-owned edge may need coordination, unowned area may have knowledge risk.
- `assumed`: user-provided team facts not visible in the repository.
- `unknown`: actual communication, enforcement state, team capacity, or off-repository ownership.

## Risk Signals

High-value signals:

- cross-owned static or runtime dependency edges;
- unowned architecture-significant modules, deployment areas, APIs, or data owners;
- shared modules with no owner or exception policy;
- ADRs that change boundaries without owner or review path;
- CODEOWNERS rules that do not cover high fan-out modules;
- ownership rules that conflict with intended architecture boundaries.

## Recommendations

Prefer the smallest governance mechanism that makes ownership observable:

- add or adjust CODEOWNERS for architecture-significant paths;
- document a module owner or review path in ADRs;
- require both owner paths for architecture-changing cross-owned dependency work;
- add an architecture fitness function for confirmed owner-boundary rules;
- record exceptions with expiry and revisit triggers.

## Limits

Ownership topology is a prioritization lens. It cannot prove branch protection, actual review quality, team health, or communication frequency without project-specific evidence.
