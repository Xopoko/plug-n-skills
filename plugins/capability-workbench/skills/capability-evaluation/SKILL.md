---
name: capability-evaluation
description: Evaluate skill, plugin, agent-guidance, or trigger-metadata artifacts against an explicit baseline and representative behavior cases, producing evidence and an adoption decision. Excludes harness reliability and static source/safety audits.
---

# Capability Evaluation

Use this when adoption depends on evidence that a candidate capability artifact
changes agent behavior, not merely that its files are valid. Compare a skill,
plugin, guidance file, or trigger contract with no artifact or an immutable
prior version under paired conditions.

Do not use this for static safety/source review (`capability-auditor`), portfolio
boundaries (`capability-portfolio-architect`), or runner, process, transport,
cancellation, recovery, memory, and harness reliability (`agent-harness`).

## Plugin Root

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell). Set it
to the host plugin-root variable when defined; otherwise use the absolute path
of this skill folder's `../..`. The full contract and receipt schema are in
`$PLUGIN_ROOT/references/capability-evaluation.md`.

## Evaluation Spine

1. State one falsifiable artifact-behavior claim and a predeclared adoption
   rule. Keep runtime/harness reliability outside the claim.
2. Freeze the candidate identity and the baseline: either `no-artifact` or an
   immutable prior artifact. Record SHA-256 fingerprints.
3. Build representative cases before inspecting outcomes. Include foundational
   must-pass cases, realistic prompts that do not name the artifact, paraphrases,
   edge cases, and out-of-scope or anti-trigger cases when routing matters.
4. Freeze model, runner, tools, permissions, network policy, timeout, fixtures,
   configuration, and isolation. Candidate and baseline must differ only by the
   artifact. Use clean disposable workspaces for both arms.
5. Select an authorized host-specific runner or a documented manual procedure.
   This skill supplies no universal runner and grants no network, credential,
   install, tool-approval, or external-side-effect authority.
6. Grade deterministic assertions first. Use blinded human comparison or a
   calibrated model judge only for genuinely subjective properties; keep the
   rubric and judge identity auditable.
7. Repeat variable cases. Three trials is a provisional authoring minimum; use
   five or more trials or uncertainty estimates for a consequential promotion
   gate when cost permits.
8. Keep trigger, task outcome, constraint violations, subjective quality, and
   token/time/cost overhead as separate dimensions. Preserve per-case losses;
   do not hide them in one weighted score.
9. Quarantine authentication, installation, sandbox, process, transport,
   logging, runner-crash, and invalid-timeout failures. Route their diagnosis to
   Agent Harness. Count a task timeout as artifact behavior only after equivalent
   functioning harness conditions are proved.
10. Validate the plan or receipt, then decide `adopt`, `revise`, `reject`, or
    `inconclusive`. Preserve the prior artifact and a concrete rollback path.

## Receipt Gate

Create a JSON record using `capability.evaluation.v1`. Start from the bundled
template:

```bash
python3 "$PLUGIN_ROOT/scripts/evaluation/validate_capability_evaluation.py" --template
```

Validate before using the result as adoption evidence:

```bash
python3 "$PLUGIN_ROOT/scripts/evaluation/validate_capability_evaluation.py" <evaluation.json> --json
```

A `complete` receipt requires proved paired-environment parity, one result for
every declared case, matching baseline/candidate trial counts, summary counts
derived from case outcomes, explicit limitations, and rollback. A valid receipt
proves internal contract consistency, not that its evidence is truthful or that
the runtime is reliable.

## Output

Report:

- target artifact and immutable candidate/baseline identities;
- behavior claim, dimensions, cases, assertions, repetitions, and adoption rule;
- parity evidence and runner/runtime versions;
- per-case paired outcomes, quarantined trials, and negative deltas;
- deterministic and subjective review methods;
- verdict, rationale, limitations, rollback, and residual harness uncertainty.
