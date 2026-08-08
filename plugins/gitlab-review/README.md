# GitLab Review Plugin

GitLab Review addresses existing merge request feedback as one bounded,
race-safe transaction. It keeps discussion ownership, code changes, replies,
source-project-bound publication, and CI evidence tied to the same current
head.

## Skill

- `gitlab-review-response`: complete discussion inventory, current-diff
  classification, focused repair, idempotent same-thread replies,
  reviewer-owned resolution, source-project-bound exact-SHA publication, and
  exact-head handoff proof.

The hot skill carries the state machine and routes detailed schemas and formulas
to the references. `gitlab_review_guard.py` validates already-fetched complete
JSON or NDJSON snapshots, exact-head pipeline evidence, and one-thread mutation
plans without calling GitLab or Git. `gitlab_push_binding_guard.py` runs only
local Git inspection and may create one new private transaction envelope; it
does not contact GitLab, acquire credentials, execute hooks, fetch, push, or
mutate the source repository. Neither helper posts replies, resolves
discussions, approves, or merges.

## Validation

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/gitlab-review
python3 -m unittest discover -s plugins/gitlab-review/tests -p 'test_*.py'
python3 scripts/validate-repository.py
```
