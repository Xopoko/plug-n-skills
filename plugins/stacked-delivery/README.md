# Stacked Delivery Plugin

Stacked Delivery keeps dependent code changes bound to the exact stack they
were prepared and proved against. It separates dependency readiness from
review or merge readiness and fails closed when a lower layer changes.

## Skill

- `stacked-change-delivery`: freeze a bottom-to-top stack snapshot, validate
  exact parent heads and ownership, invalidate stale descendants, require
  node-local proof, select a safe landing prefix, and produce a
  content-addressed handoff receipt. It also validates additive prepared
  history-mutation handoffs with exact old/new mappings, equivalence,
  attribution, backup, lease, proof, authority, scope, and action-order gates.

The bundled guard consumes already-collected JSON. It is read-only and
standard-library only: it never invokes Git, contacts a forge, mutates a ref,
rebases, pushes, retargets, approves, or merges.

For a future rewrite prepared for another task:

```bash
python3 plugins/stacked-delivery/skills/stacked-change-delivery/scripts/stacked_delivery_guard.py \
  validate-prepared-mutation --input PREPARED_JSON
```

## Validation

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/stacked-delivery
python3 -m unittest discover -s plugins/stacked-delivery/tests -p 'test_*.py'
python3 scripts/validate-repository.py
```
