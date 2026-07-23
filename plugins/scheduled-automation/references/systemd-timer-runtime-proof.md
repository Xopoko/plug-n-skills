# systemd Timer Runtime Proof

First distinguish the PID 1 system manager from `systemctl --user`. User
services also depend on login-manager lifetime and lingering configuration.

## P0 And P1

Read-only patterns:

```bash
systemd-analyze <manager-flags> verify <service-file> <timer-file>
systemctl <manager-flags> show <service> <timer> \
  -p LoadState -p FragmentPath -p DropInPaths -p UnitFileState \
  -p ActiveState -p SubState -p NeedDaemonReload
systemctl <manager-flags> is-enabled <timer>
systemctl <manager-flags> list-timers --all
```

Check both service and timer. Resolve base fragments, drop-ins, overrides, and
`NeedDaemonReload`; a valid file on disk does not prove the manager loaded that
version. Inspect `ExecStart`, `WorkingDirectory`, environment sources, `User`,
`Group`, output sinks, timer trigger, persistence, and accuracy.

Keep raw unit content and environment values in restrictive local artifacts.
Environment variables are not secret storage; use the platform credential
mechanisms for secrets.

## P2 And P3

Starting the paired service proves P2 after a fresh service activation and
terminal result are observed. Starting the timer only arms it.

For timer P3, inspect timer properties such as `LastTriggerUSec`,
`NextElapseUSecRealtime`, `NextElapseUSecMonotonic`, `Triggers`, and current
active state. Correlate the timer's post-baseline event with the service's fresh
`InvocationID`, bounded journal records, and matching receipt.

Use an absolute record bound:

```bash
systemctl <manager-flags> show <service> \
  -p InvocationID -p Result -p ExecMainCode -p ExecMainStatus \
  -p ExecMainStartTimestamp -p ExecMainExitTimestamp
journalctl <manager-flags> --unit <timer> \
  --boot 0 --since "$SCHEDULE_BASELINE_TIME" --lines 200 --no-pager
journalctl <manager-flags> "_SYSTEMD_INVOCATION_ID=$SCHEDULE_INVOCATION_ID" \
  --boot 0 --lines 200 --no-pager
```

Prefer invocation-ID filtering once the fresh identifier is known. Preserve
only redacted excerpts in model context. Accept terminal agreement only after
the service's fresh `InvocationID`, `Result`, `ExecMainCode`, and
`ExecMainStatus` are captured together.

A dedicated service and timer or transient timer can be a separate canary when
authorized. Capture evidence before collection removes transient state.

A timer does not restart an already-active target. `Persistent=true` can catch
up with one activation after downtime but does not replay every missed
occurrence. Do not infer exactly-once execution.

## Sources

- systemd timers:
  https://www.freedesktop.org/software/systemd/man/latest/systemd.timer.html
- execution environment:
  https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html
- manager properties:
  https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.systemd1.html
- journal:
  https://www.freedesktop.org/software/systemd/man/latest/journalctl.html
