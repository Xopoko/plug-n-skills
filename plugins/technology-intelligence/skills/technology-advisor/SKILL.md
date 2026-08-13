---
name: technology-advisor
description: >-
  Map software capabilities to candidate technologies and
  CLI/SDK/WASM/MCP/API/skill interfaces for adoption or migration using dated
  evidence. Keeps runtime separate; excludes routine coding and tool execution
  or installation.
---

# Technology Advisor

Use this skill for a genuine choice. Do not reopen an accepted stack during
ordinary implementation unless the user asks or a hard compatibility or
security constraint invalidates it.

Resolve `$PLUGIN_ROOT` from the host when available; otherwise use the absolute
path of this skill folder's `../..`.

## Workflow

1. Name the needed outcome as a capability, then bind the decision profile:
   lifecycle stage, use case, team and platform,
   delivery horizon, scale and reliability, security and compliance, budget and
   operating capacity, lock-in tolerance, and hard requirements. Ask only for a
   missing constraint that could change the shortlist.
2. Validate the local snapshot before relying on it:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/technology_intelligence.py" validate
   ```

3. Query only the relevant slice. Prefer `--capability` when the need is known
   but the product is not. Use `--technology` or `--interface` for a named
   candidate or access surface. Add `--runtime-inventory <json>` when the
   caller already has a read-only live inventory; never infer availability from
   the catalog.

   ```bash
   python3 "$PLUGIN_ROOT/scripts/technology_intelligence.py" query \
     --capability <capability> --stage <stage> --use-case <use-case> --format json
   ```

   For a time-bounded decision, inspect publication coverage separately from
   retrieval freshness:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/technology_intelligence.py" evidence-window \
     --since <YYYY-MM-DD> --as-of <YYYY-MM-DD> --json
   ```

4. Keep four entities explicit: a capability is the needed outcome, a
   technology is a candidate product or pattern, an interface is its durable
   access contract, and runtime inventory is short-lived evidence of what can
   be used here now. Treat retrieved assessments as dated decision cards, not
   universal truth.
   Apply hard gates first, compare visible dimensions, preserve conflicting
   evidence, and name missing evidence. Popularity alone cannot promote a
   candidate.
5. If relevant evidence or an assessment is stale, report that boundary. Use
   live first-party research when authorized, or hand evidence maintenance to
   `technology-evidence-maintainer`; do not trigger network refresh implicitly.
6. Recommend a small shortlist with one preferred fit only when the constraints
   distinguish it. Otherwise return a bounded experiment or the next cheapest
   discriminator with a hypothesis, metrics, threshold, stop condition,
   environment, versions, artifact hashes, result states, and limitations.

## Output Contract

Report:

- decision profile and hard gates;
- normalized capability and candidate interfaces;
- preferred candidate or bounded shortlist;
- why each candidate fits this context and where it does not;
- dated observations with direct source URLs;
- confidence, verification gaps, and staleness;
- alternatives and a reversible validation experiment;
- runtime availability separately when a caller supplied it.

Load `$PLUGIN_ROOT/references/evidence-methodology.md` for assessment rules and
`$PLUGIN_ROOT/references/decision-evidence-contract.md` for time-bounded claims,
experiments, benchmarks, or model-assisted rationale. Load
`$PLUGIN_ROOT/references/runtime-boundary.md` when CLI, MCP, API, SDK, install,
authentication, permissions, or invocation is part of the question.
