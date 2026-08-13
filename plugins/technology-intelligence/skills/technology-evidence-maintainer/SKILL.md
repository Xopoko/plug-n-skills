---
name: technology-evidence-maintainer
description: >-
  Validate, inspect, diff, or explicitly refresh Technology Intelligence
  evidence, provenance, staleness, rights, and coverage. Excludes stack
  selection, runtime discovery, installation, and automatic recommendation
  changes.
---

# Technology Evidence Maintainer

Maintain provenance and reviewability. Refreshing a source is not authority to
change an assessment.

Resolve `$PLUGIN_ROOT` from the host when available; otherwise use the absolute
path of this skill folder's `../..`.

## Workflow

1. Read `$PLUGIN_ROOT/references/refresh-policy.md` and
   `$PLUGIN_ROOT/references/source-and-licensing-ledger.md` before any network
   capture or redistribution decision.
2. Establish the baseline with offline checks:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/technology_intelligence.py" validate
   python3 "$PLUGIN_ROOT/scripts/technology_intelligence.py" stale --as-of <YYYY-MM-DD>
   python3 "$PLUGIN_ROOT/scripts/technology_intelligence.py" evidence-window \
     --since <YYYY-MM-DD> --as-of <YYYY-MM-DD>
   ```

3. For a source update, name one allowlisted `source-id`, state the expected
   change, cheapest discriminator, output directory, and stop condition. Do not
   crawl a domain or execute candidate code.
4. Only when network capture is explicitly authorized, write outside the plugin
   tree and require the acknowledgement flag:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/technology_intelligence.py" refresh \
     --source-id <source-id> --acknowledge-network \
     --output-dir <ignored-or-temporary-directory>
   ```

   The command captures one bounded artifact and a hash-bound receipt. It does
   not normalize observations or edit assessments.
5. Review publication and measurement dates, methodology, licensing, candidate
   affiliation, changed claims, source scope, contradictions, and bias. Then
   make a separate source edit to observations. Make any assessment change as a
   second, explicit review step with rationale, alternatives, expiry, and
   evidence coverage.
6. Treat capability and interface mappings as separate reviewed relations.
   Every interface needs first-party observation support, and neither a
   documented interface nor a package identifier may be converted into an
   installed or healthy runtime claim.
7. Diff the complete old and proposed data directories, validate again, and run
   plugin-local tests. Never publish a partially updated snapshot manifest.

## Completion

Report source IDs, captured receipts, observation changes, assessment changes
or explicit absence of them, licensing decision, stale residuals, validation
commands, and whether any runtime or installed state was touched.
