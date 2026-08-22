# mattpocock/skills external source audit

## Source identity

- Repository: <https://github.com/mattpocock/skills>
- Reviewed snapshot: commit `5b15a47f2d7150f545fbcacbfe381787fc0230dc`
- Git tree: `b067eb5ab717af0165a555ff7791afa3494053c4`
- Review date: 2026-08-21
- Reviewer: `capability-workbench`
- Root license: MIT, with no recorded exceptions

The static review covered agent-skill instructions and workflow material for
checkable completion, evidence-first debugging, tracer-task planning, and
independent review lenses. No upstream instruction, script, installer, test,
hook, or agent workflow was executed.

The mechanisms were converted into bounded evaluation candidates rather than
copied. Most candidate deltas failed the frozen local behavioral gates; the
results remain evidence for rejection or revision, not authority to activate
the upstream bundle.

Recursive agent fan-out, automatic commit, pull-request, and merge behavior,
secret-handling flows, and broad global-link deletion were rejected. The pin is
`reference-only`: installation, execution, vendoring, and activation remain
disabled, and a later upstream revision requires a new review.
