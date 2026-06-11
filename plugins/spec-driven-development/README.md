# Spec-Driven Development

SDD router and validator. It uses Spec Kit, Kiro, OpenSpec, Agent OS, or generic artifacts as project shapes without copying those ecosystems into every task.

Core surfaces:

- `sdd`: route the request and choose the workflow lane.
- `sdd-spec-kit`: use GitHub Spec Kit projects and commands.
- `sdd-specify`: write or refine behavior-first requirements/specs.
- `sdd-plan-tasks`: turn approved specs into technical design and traceable tasks.
- `sdd-implement`: implement from tasks with fresh verification evidence.
- `sdd-audit`: check SDD surface, traceability, and completion readiness.

Utility scripts:

- `scripts/sdd_surface_audit.py`
- `scripts/sdd_traceability_check.py`

Core additions:

- progressive rigor by risk and evidence profile
- requirement quality ledgers for sources, assumptions, ambiguity, and acceptance
- machine-checkable requirement -> scenario -> design -> task -> test/evidence -> code traceability
- evidence-led completion gates that reject LLM self-judgment as proof
- risk-based escalation from tests and smoke checks to model checking or formal evidence when appropriate
