# Scheduled Automation Plugin

Scheduled Automation proves local jobs in the runtime owned by the real
operating-system scheduler instead of treating a successful manual shell run as
scheduler evidence.

## Skill

- `scheduled-automation-runtime`: launchd, systemd timer, cron, and Windows Task
  Scheduler registration, runtime-context diagnosis, native-trigger proof,
  safe canaries, correlated receipts, missed-run and overlap analysis, and
  rollback-aware repair.

The hot skill routes to one platform reference and loads the heavier run-proof
contract only when P3/P4, a canary, a receipt, or repair is actually needed.

## Validation

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/scheduled-automation
python3 scripts/validate-repository.py
```
