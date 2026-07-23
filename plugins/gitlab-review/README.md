# GitLab Review Plugin

GitLab Review addresses existing merge request feedback as one bounded,
race-safe transaction. It keeps discussion ownership, code changes, replies,
and CI evidence tied to the same current head.

## Skill

- `gitlab-review-response`: complete discussion inventory, current-diff
  classification, focused repair, idempotent same-thread replies,
  reviewer-owned resolution, and exact-head handoff proof.

The hot skill carries the state machine and routes detailed schemas and formulas
to the references. The bundled fail-closed guard validates already-fetched,
complete JSON or NDJSON snapshots, exact-head pipeline evidence, and one-thread
mutation plans. It is read-only: it never calls GitLab, invokes git, posts
replies, resolves discussions, approves, or merges.

## Validation

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/gitlab-review
python3 -m unittest discover -s plugins/gitlab-review/tests -p 'test_*.py'
python3 scripts/validate-repository.py
```
