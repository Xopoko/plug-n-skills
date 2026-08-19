---
name: windows-effective-settings
description: Diagnose Windows settings that do not stick or take effect across capability, support, scope, policy, service, consent, power, vendor, firmware, cache, runtime, and observed behavior. Excludes generic registry tweaking and firmware writes.
---

# Windows Effective Settings

Use this skill when a Windows preference appears set but the observed behavior
disagrees, or when the first question is whether the host actually supports the
requested behavior. Read
`$PLUGIN_ROOT/references/windows-control-contract.md` for the shared receipt.

## Recover The Effective Owner

1. Name one setting and one expected effect. Bind user versus machine scope and
   the exact Windows build, edition, hardware capability, and product support.
2. Capture the configured value without changing it. Record the native surface,
   data type, scope, and source rather than a screenshot alone.
3. Check higher authorities only when relevant: local or domain policy, MDM,
   consent/privacy controls, service state and start mode, active power scheme
   and power requests, vendor application, driver, runtime cache, and firmware.
4. Separate these fields:

   - `desired`: the requested behavior;
   - `configured`: the local preference;
   - `policy_source`: the authority that may override it;
   - `applied`: resultant state after precedence;
   - `runtime`: the state of the owning service/process/device;
   - `observed_effect`: the reproduced user-visible behavior.

5. Classify `unsupported`, `misconfigured`, `blocked_by_authority`,
   `stale_runtime`, `active_failure`, or `unknown`. Do not collapse support and
   configuration into one answer.
6. If a change is authorized, prefer the highest-level supported surface and
   one reversible value. Record the old value, rollback command, required
   refresh, and whether logoff/reboot is pending.
7. Re-query every owning layer and reproduce the effect. If the value changed
   but the effect did not, the task remains incomplete.

Useful read-only probes, selected narrowly:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture
Get-CimInstance Win32_Service -Filter "Name='ExactService'" | Select-Object Name,State,StartMode,StartName,ExitCode
powercfg.exe /getactivescheme
powercfg.exe /requests
gpresult.exe /Scope Computer /R
```

`gpresult`, policy reports, and vendor diagnostics can contain private host or
tenant data; keep raw output local. Run them only when policy ownership is a
live hypothesis. The bundled helper can capture host, matching service, power,
and coverage state with `-Area EffectiveSetting`.

## Boundaries

- A running service is not proof of the intended `StartMode`, and a start mode
  is not proof of a running service.
- An active power scheme is not proof that no request is preventing sleep.
- Registry presence is not proof of resultant policy or runtime application.
- Firmware and BIOS are diagnostic/routing boundaries only. Prove that they own
  the limit, then stop unless a separate, explicitly authorized firmware
  workflow exists.
- Do not invent registry keys, disable policy, bypass consent, or write an
  undocumented value to make a UI appear consistent.
