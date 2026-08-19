---
name: windows-host-operations
description: "Windows host operations: route effective settings and policy precedence, startup/removal persistence, and device-stack diagnosis. Requires exact targets, reversible actions, and functional proof; excludes broad repair and non-Windows hosts."
---

# Windows Host Operations

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same path
suffix) for the plugin root. Set it once to this plugin's root directory.

Use this router when a Windows symptom may be owned by policy, service, power,
startup, package, process, device, driver, endpoint, queue, transport, vendor
software, or firmware. On a non-Windows host, route to that operating system's
owner instead of translating commands speculatively.

Read `$PLUGIN_ROOT/references/windows-control-contract.md` for the typed state,
authority, receipt, and completion contract.

## Route

- Setting does not stick, a service or power preference is ineffective, a
  privacy/consent or policy layer may override it, or support/capability is in
  question: use `windows-effective-settings`.
- App launches, returns, will not uninstall, leaves helpers/data, or may persist
  through services, tasks, Run keys, startup folders, packages, or locks: use
  `windows-startup-and-removal`.
- Peripheral, audio, microphone, printer, Bluetooth, camera, USB, controller,
  input, endpoint, queue, driver, or vendor-app symptom: use
  `windows-device-diagnostics`.

Use `scheduled-automation-runtime` when the requested claim is what a native
scheduler actually launched. Use `computer-use` for pure UI navigation,
`technology-advisor` for product selection, `credential-handoff` for protected
prompts, and the Human Decision Surface for consequential non-secret choices.
This plugin may call those owners; it does not absorb their contracts.

## Shared Control Spine

1. Bind the target host, Windows build, PowerShell edition/version/bitness,
   elevation state, and exact process, package, setting, or device.
2. Capture a read-only baseline. A denied or unsupported probe is `UNKNOWN`
   with `needs_admin` or `unsupported`; it is never evidence of healthy state.
3. Enumerate every relevant authority or persistence surface for the selected
   leaf. Separate `desired`, `configured`, `policy_source`, `applied`,
   `runtime`, and `observed_effect` when those layers exist.
4. Classify the symptom as unsupported capability, misconfiguration, higher
   authority, stale runtime state, active failure, or still unknown.
5. If the task authorizes a change, propose the narrowest reversible action
   with exact target, scope, privilege, rollback, blast radius, and expected
   verifier. Preserve `-WhatIf` and `-Confirm` through nested PowerShell helpers.
6. Execute at most one bounded attempt, capture native return code and changed
   properties, then record `refresh_required`, `logoff_required`, and
   `reboot_required` independently.
7. Re-enumerate every affected surface and reproduce the actual user-visible
   behavior. A command exit code or changed registry value alone is incomplete.

Start with the bundled read-only probe when it covers the selected leaf:

```powershell
powershell.exe -NoProfile -File `
  "$env:PLUGIN_ROOT\scripts\Get-WindowsHostEvidence.ps1" `
  -Area StartupRemoval -Target "Exact Product Name"
```

Keep raw host evidence private. Durable output should contain typed summaries,
not machine names, private paths, device serials, installed-product inventories,
vendor preferences, or authorization state.

## Hard Stops

- No `ExecutionPolicy Bypass`, encoded command, `Invoke-Expression`, generic
  privileged shell/MCP import, broad wildcard mutation, or class/bus-wide action.
- No automatic hardening, security, network, disk, account, driver-store, or
  firmware repair in the core workflow.
- Never use `Win32_Product` as an inventory probe; it can trigger installer
  consistency checks.
- Do not close arbitrary handles, delete locked files forcefully, purge user
  data by implication, or treat missing privilege as successful absence.
- Stop after verified outcome or a precise owner/authority blocker. Do not add
  monitoring, cleanup, or optimization that the user did not request.
