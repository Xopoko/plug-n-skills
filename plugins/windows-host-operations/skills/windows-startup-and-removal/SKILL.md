---
name: windows-startup-and-removal
description: Diagnose and reconcile exact Windows apps across processes, services, tasks, startup entries, packages, locks, data, update helpers, and residue. Prefer disable-before-delete, explicit data choices, rollback, and per-surface absence proof.
---

# Windows Startup And Removal

Use this skill when an application starts unexpectedly, returns after being
disabled, resists uninstall, leaves helpers or data, or may be held by another
process. Read `$PLUGIN_ROOT/references/windows-control-contract.md` first.

## Inventory Before Action

1. Bind exact product name, package/product id, publisher, install source,
   user/machine scope, architecture, and expected keep/remove outcome. Similar
   display names are not identity proof.
2. Capture a private read-only inventory across the relevant surfaces:

   - running process and normal application shutdown route;
   - service state plus startup mode;
   - scheduled task registration, trigger, action owner, and last result;
   - Run/RunOnce and policy keys, startup folders, Active Setup, Winlogon,
     BootExecute, and policy scripts when applicable;
   - packaged application, classic uninstall registration, update helper, and
     launcher-owned installation;
   - user data, shared data, caches, logs, shell integration, and file locks.

3. Use the bundled read-only helper for the common surfaces:

```powershell
powershell.exe -NoProfile -File `
  "$env:PLUGIN_ROOT\scripts\Get-WindowsHostEvidence.ps1" `
  -Area StartupRemoval -Target "Exact Product Name"
```

It intentionally hashes path-like command data and selected identifiers, while
retaining matching display labels such as service, task, and package names.
Keep the receipt private and local. It does not prove complete absence from
every advanced surface; the coverage array names what was and was not probed.

## Controlled Change

4. Choose the narrowest outcome. Disable startup before deleting an entry when
   disablement is sufficient and rollback matters. Use the product's supported
   uninstaller with exact identity and scope before manual residue removal.
5. Make preservation versus purge of user-created data an explicit choice.
   Shared data and account/cloud state require separate ownership evidence.
6. Ask the application or service to stop normally. Do not close arbitrary
   handles, kill unrelated processes, or delete locked files forcefully.
7. For PowerShell mutators, require `SupportsShouldProcess`; propagate
   `-WhatIf` and `-Confirm` into nested helpers. For native uninstallers, expose
   the exact command, silent flags, return-code contract, logs, rollback, and
   pending restart before execution.
8. After one bounded attempt, verify each surface separately and report
   remaining entries, locks, data, tasks, services, helpers, and pending
   logoff/reboot. Absence from one package manager is not global absence.

## Safety Boundaries

- Never query `Win32_Product`; use package-manager and uninstall-registry
  inventory because `Win32_Product` may initiate installer repair checks.
- Do not remove wildcard matches, all products from a publisher, shared
  runtimes, drivers, shell components, or user data from an ambiguous target.
- Do not treat a successful uninstaller exit code as proof of absence or a
  failed code as permission for manual deletion.
- Optional Sysinternals Autoruns can broaden read-only coverage, but keep
  VirusTotal submission disabled unless the user explicitly authorizes network
  disclosure and its terms.
