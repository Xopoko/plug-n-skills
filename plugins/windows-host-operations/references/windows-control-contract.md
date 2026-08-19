# Windows Host Control Contract

Use this reference with the Windows Host Operations router and leaves. It keeps
diagnosis, authority, mutation, and proof separate across Windows subsystems.

## State Model

Capture only fields relevant to the selected leaf, but preserve their meaning:

| Field | Meaning | Common mistake |
| --- | --- | --- |
| `desired` | User-authorized intended effect | Treating it as current state |
| `capability` | Hardware, edition, build, product, or driver support | Treating a visible setting as support proof |
| `configured` | Stored local value and scope | Treating it as resultant state |
| `policy_source` | Local policy, domain policy, MDM, consent, or higher owner | Calling an override a failed write |
| `applied` | Result after precedence and refresh | Inferring it from one registry value |
| `runtime` | Service, process, task, device, endpoint, or queue state | Ignoring startup mode, role, or stale cache |
| `observed_effect` | Reproduced user-visible behavior | Trusting command success instead |

Allowed classifications are `unsupported`, `misconfigured`,
`blocked_by_authority`, `stale_runtime`, `active_failure`, and `unknown`.
Missing privilege, missing commands, unsupported providers, timeouts, or parsing
failures produce `UNKNOWN` coverage plus a reason. They never become an empty
healthy result.

## Authority Gate

Diagnosis is read-only by default. Before any mutation, bind:

- exact target and owning surface;
- requested outcome and current authority;
- user versus machine scope;
- privilege and protected sign-in boundary;
- one proposed action and one attempt limit;
- old value or state and rollback eligibility;
- blast radius and expected disconnect/restart behavior;
- verifier for both resulting state and observed function.

PowerShell state-changing functions must declare `SupportsShouldProcess` and
call `$PSCmdlet.ShouldProcess()` on the exact target. Nested helpers propagate
`-WhatIf` and `-Confirm`; a wrapper that supports them while a child ignores them
is not compliant. Native tools without dry-run semantics require a displayed
exact command and a separate authorization checkpoint before execution.

## Operation Receipt

Keep host-specific receipts private. A compact receipt shape is:

```json
{
  "schema": "windows_host_operations.receipt.v1",
  "area": "StartupRemoval",
  "target_binding": {
    "kind": "package",
    "identity": "private local value",
    "scope": "user",
    "confidence": "high"
  },
  "baseline": {
    "coverage": [],
    "state": {}
  },
  "classification": "misconfigured",
  "authorization": {
    "requested": true,
    "requires_admin": false,
    "approved_action": "private local value"
  },
  "attempt": {
    "count": 1,
    "native_return_code": 0,
    "changed_properties": [],
    "rollback_eligible": true
  },
  "pending": {
    "refresh_required": false,
    "logoff_required": false,
    "reboot_required": false
  },
  "verification": {
    "state_rechecked": true,
    "functional_test": "private local value",
    "observed_effect": "passed"
  }
}
```

Native return code, changed properties, and functional effect are independent.
An installer can return success while requiring reboot. A service configuration
can change while its runtime remains stale. A device can report OK while its
endpoint role or live function remains wrong.

## Surface Coverage

### Effective settings

Consider capability/support, local value, user/machine scope, consent/privacy,
service state and start mode, local/domain/MDM policy, active power scheme,
active power requests, vendor/driver state, runtime cache, and firmware. Probe
only surfaces that can plausibly own the named setting.

### Startup and removal

Consider processes, services, scheduled tasks, Run/RunOnce and policy keys,
startup folders, packaged apps, classic uninstall registrations, Active Setup,
Winlogon/BootExecute, policy scripts, update helpers, launcher ownership, file
locks, user data, shared data, and pending restart. The bundled helper covers a
safe common subset and declares the remaining surfaces as unprobed.

### Devices

Consider present/remembered identity, instance/container/class/interface,
hardware ids, driver package/provider/version, owning service and filters,
endpoint/queue/port/role, transport, vendor software, and the live operation.
Exact identifiers may contain hardware serials; keep them private.

## Forbidden Core Actions

- generic privileged PowerShell, shell, registry, service, driver, or device MCP;
- `ExecutionPolicy Bypass`, encoded commands, `Invoke-Expression`, or hidden
  elevation;
- wildcard/bulk package removal, service change, task deletion, or device action;
- `Win32_Product` inventory;
- arbitrary handle close or forced locked-file deletion;
- driver-store deletion, firmware update, BIOS write, broad class/bus reset;
- automatic hardening, security remediation, account changes, network reset,
  disk repair, or data purge;
- telemetry, hosted trace upload, VirusTotal submission, or other egress by
  default.

## Completion Gate

Completion requires all applicable items:

1. exact target and scope are proven;
2. baseline coverage and unknowns are explicit;
3. the effective owner or remaining blocker is identified;
4. any mutation stayed within current authority and one bounded attempt;
5. old state, native code, changed properties, rollback, and pending completion
   are recorded;
6. affected surfaces were re-enumerated;
7. the same user-visible operation was reproduced successfully, or a precise
   external/authority blocker remains.

Stop at this gate. Do not add cleanup, monitoring, optimization, or unrelated
host administration.
