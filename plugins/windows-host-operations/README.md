# Windows Host Operations Plugin

Windows Host Operations recovers the effective owner of Windows symptoms
before changing state. It covers setting and policy precedence, startup and
application-removal persistence, and device stacks. The shared completion gate
requires exact targets, a read-only baseline, the narrowest reversible action,
before-and-after evidence, and reproduction of the user-visible effect.

The plugin does not provide a privileged shell, broad cleanup, autonomous
hardening, driver-store deletion, firmware mutation, security remediation,
network repair, disk repair, or telemetry. Host values and evidence receipts
remain local and untracked.

## Skills

- `windows-host-operations`: router and shared authority boundary.
- `windows-effective-settings`: capability, configured, policy, applied,
  runtime, and observed setting state.
- `windows-startup-and-removal`: processes, services, tasks, startup entries,
  packages, locks, user data, and residue.
- `windows-device-diagnostics`: exact device identity, driver and service stack,
  endpoints, queues, roles, transports, vendor layers, and functional tests.

## Read-only Helper

`scripts/Get-WindowsHostEvidence.ps1` captures a typed, target-bounded baseline
for one leaf. It performs no mutation and reports missing privilege or missing
commands as `UNKNOWN` coverage rather than as healthy state.

```powershell
powershell.exe -NoProfile -File scripts\Get-WindowsHostEvidence.ps1 `
  -Area StartupRemoval -Target "Example App"
```

The JSON output hashes path-like command data and selected identifiers, but may
retain local display labels and registration paths such as scheduled-task
paths. Keep it private and summarize it before using it in a durable report.

## Validation

```bash
python3 -m unittest discover -s tests -q
python3 ../capability-workbench/scripts/plugin/validate_plugin.py .
```
