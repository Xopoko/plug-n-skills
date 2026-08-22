# i-have-adhd evaluation-source audit, 2026-08-21

## Source identity

- Repository: <https://github.com/ayghri/i-have-adhd>
- Reviewed snapshot: commit `e7555fcaf612dfa1739dc86610ea926a906db614`
- Git tree: `42ce88189368a2612da7f6f841841b404334570d`
- Review date: 2026-08-21
- Reviewer: `capability-workbench`
- Root license: MIT, with no recorded exceptions

This later snapshot was inspected statically for evaluation-isolation patterns
and realistic first/last-line sufficiency cases. It is a separate research pin
from the older snapshot that remains the provenance source for the installable
first-party `i-have-adhd` plugin.

Persistent hooks, user-home prompt injection, cross-harness runtime code, and
provider-backed evaluation runners were rejected. No upstream instruction,
hook, script, extension, installer, or test was executed.

The dependency is `reference-only`; installation, execution, vendoring, and
activation are disabled. Any future fixture must be independently authored and
validated under the first-party evaluation contract.
