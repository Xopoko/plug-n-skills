# Mechanism Sources And Adoption Ledger

This plugin was distilled from repeated cross-task Windows operations and an
external-broad mechanism review. The links below are provenance for contracts,
not runtime dependencies. Candidate code was not imported or executed.

## Adopted Primary Mechanisms

| Mechanism | Source | Distilled surface |
| --- | --- | --- |
| Exact-target `ShouldProcess`, `WhatIf`, and `Confirm` | [PowerShell ShouldProcess](https://learn.microsoft.com/en-us/powershell/scripting/learn/deep-dives/everything-about-shouldprocess?view=powershell-7.6) | Shared mutation gate |
| Broad autostart surface inventory | [Sysinternals Autoruns](https://learn.microsoft.com/en-us/sysinternals/downloads/autoruns), [Win32_StartupCommand](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-startupcommand) | Startup/removal coverage map |
| Exact package identity and scope | [WinGet uninstall](https://learn.microsoft.com/en-us/windows/package-manager/winget/uninstall), [Ansible win_package](https://docs.ansible.com/projects/ansible/latest/collections/ansible/windows/win_package_module.html) | Package target and return-code receipt |
| PnP identity and stack-first diagnosis | [Get-PnpDevice](https://learn.microsoft.com/en-us/powershell/module/pnpdevice/get-pnpdevice?view=windowsserver2025-ps), [PnPUtil](https://learn.microsoft.com/en-us/windows-hardware/drivers/devtest/pnputil-command-syntax), [SetupAPI logs](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/setupapi-text-logs) | Device identity, driver, log, and exact-target gates |
| Resultant policy and runtime separation | [gpresult](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/gpresult), [powercfg](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options), [Win32_Service](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-service) | Effective-setting state model |
| Get/Test/Set and typed diff | [PowerShell DSC service example](https://learn.microsoft.com/en-us/powershell/dsc/reference/resources/microsoft/windows/windowspowershell/examples/manage-a-windows-service?view=dsc-3.0) | Desired/current/diff structure |
| Explicit pending reboot | [DSC rebootRequested](https://learn.microsoft.com/en-us/powershell/dsc/reference/schemas/resource/properties/rebootrequested?view=dsc-3.0) | Refresh/logoff/reboot pending fields |

Public PowerShell skill packs, configuration frameworks, machine-health tools,
Windows execution benchmarks, and rollback-oriented controllers were also
screened for portable mechanisms. They informed cross-edition checks, UNKNOWN
coverage, first-run dry behavior, functional postconditions, and rollback
eligibility. They are not dependencies and their broad execution surfaces were
not adopted.

## Rejected Or Deferred

- Broad Windows MCP servers and generic privileged shells: rejected because
  raw registry, service, driver, account, network, and filesystem mutation is a
  larger authority surface than this diagnostic contract needs.
- Agent Harness or scheduler ownership: rejected because Windows is the
  controlled host, not the agent runtime or launch boundary.
- One monolithic private skill: rejected because the three public workflows
  have independent repeated evidence and benefit from separate triggers.
- Automatic cleanup, hardening, driver/firmware update, security, network, or
  disk repair: rejected from the core because blast radius and evidence needs
  differ materially.
- DSC, Ansible, WinRM, VM benchmarks, local-model harnesses, paid APIs, and
  hosted telemetry: reference mechanisms only; stock Windows tools are enough
  for the plugin's default runtime.
- Sysinternals VirusTotal integration: deferred and off by default because it
  adds network disclosure and separate terms.

## Evidence Limits

Primary documentation supports command and state semantics; it does not prove
that this plugin improves agent outcomes. Static validation proves source shape,
not safe execution on every Windows version. Behavioral evaluation should use
public-safe synthetic cases for policy precedence, service state/start mode,
package identity/scope, startup coverage, present-versus-known devices, locks,
pending reboot, rollback, and functional verification.
