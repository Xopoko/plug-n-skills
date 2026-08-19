---
name: windows-device-diagnostics
description: Diagnose exact Windows peripherals across present/remembered identity, driver stack, endpoint/queue/role, transport, vendor software, and live function. Excludes wildcard or class-wide disable, driver-store deletion, and firmware update.
---

# Windows Device Diagnostics

Use this skill for microphones, audio, printers, Bluetooth, cameras, USB,
controllers, input devices, endpoints, queues, driver failures, or vendor-app
state. Read `$PLUGIN_ROOT/references/windows-control-contract.md` first.

## Bind Identity Before Action

1. Reproduce one live symptom and name the intended device/function. A friendly
   name alone is not identity.
2. Capture, where applicable:

   - exact PnP instance and container;
   - present versus remembered/non-present state;
   - class, interface, hardware/compatible ids, and transport;
   - driver package/provider/version/date and owning service/stack;
   - audio endpoint, default and communications role, printer queue/port, or
     other function-layer identity;
   - vendor application/firmware layer and the user-visible failing operation.

3. Start with the bundled read-only helper:

```powershell
powershell.exe -NoProfile -File `
  "$env:PLUGIN_ROOT\scripts\Get-WindowsHostEvidence.ps1" `
  -Area Device -Target "Exact Friendly Name"
```

Device instance ids and port values are hashed by default. Use the native
commands locally when exact identifiers are required for an authorized narrow
action; do not paste serial-bearing inventories into durable reports.

4. Use `Get-PnpDevice`, `Get-PnpDeviceProperty`, `pnputil.exe`, queue/endpoint
   commands, vendor diagnostics, and SetupAPI logs selectively. Record denied
   or unavailable layers as `UNKNOWN`, not healthy.
5. Distinguish a known non-present device from a current failure. `Status=OK`
   proves neither endpoint selection nor actual microphone, audio, print,
   camera, Bluetooth, or input behavior.

## Narrow Recovery And Proof

6. Prefer refresh or restart of the exact owning component over class-wide or
   bus-wide change. State the exact instance, expected disconnect window,
   rollback, required privilege, and functional verifier before action.
7. Re-enumerate identity, driver, endpoint/queue/role, transport, and vendor
   state. Then repeat the same live operation after the required ticks or
   refresh. Configuration evidence and functional evidence are separate.

## Hard Stops

- No wildcard, class-wide, bus-wide, or force disable/remove in the core path.
- No routine driver-store deletion, arbitrary old-driver cleanup, firmware
  update, BIOS write, filter-driver surgery, or broad USB/Bluetooth reset.
- Do not replace a driver merely because a newer version exists. Bind the
  observed failure and a supported rollback or recovery path first.
- Do not switch default/communications roles, remove queues, forget pairings,
  or modify vendor preferences unless the current task authorizes that exact
  target and the previous state is captured.
