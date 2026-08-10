# launchd Runtime Proof

Bind an exact service target such as `system/<label>`, `user/<uid>/<label>`, or
`gui/<uid>/<label>`. A plist path alone does not identify the loaded domain.

## P0 And P1

Read-only inspection commonly includes:

```bash
plutil -lint <job.plist>
launchctl print <domain>/<label>
launchctl print-disabled <domain>
```

Capture raw output in a restrictive local artifact because definitions and
status can expose arguments or environment values. Return only redacted
structural fields and a digest.

Inspect `Program`, `ProgramArguments`, `WorkingDirectory`,
`EnvironmentVariables`, `UserName`, `GroupName`, `StandardOutPath`,
`StandardErrorPath`, and the configured launch conditions. Prefer an absolute
interpreter and script path. `UserName` and `GroupName` apply to privileged
system services; agents inherit user or session context.

The plist `Disabled` key alone is not current state. `launchctl print` is
human-oriented diagnostic output, not a stable parsing API; preserve a bounded
raw excerpt and do not build a durable parser around its layout.

## P2 And P3

`launchctl kickstart <domain>/<label>` proves at most P2. Avoid restart or kill
options unless terminating an existing instance is explicitly authorized.

P3 requires evidence that the job's configured non-demand condition fired:
calendar or interval, login or load, path or queue state, socket, keep-alive, or
another declared launch condition. Correlate a fresh receipt with
version-matched raw trigger-reason/state evidence and bounded redirected output.
launchd has no stable structured per-invocation identifier; when trigger origin
cannot be distinguished from a demand start, report P3 as partial or unproven.

A separate `StartCalendarInterval` canary proves only the canary. launchd has no
disposable one-shot calendar primitive. Give its payload an expiry and
single-consumption guard to bound repeated effects, then remove the exact
service and verify cleanup. An orphaned registration remains unresolved.

`StartInterval` firings can be missed during sleep or while the job runs;
calendar firings may coalesce after wake. Rapid respawn can be throttled. Do not
infer exactly-once execution.

## Sources

- Apple launchd jobs:
  https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html
- Apple launchd sources:
  https://github.com/apple-oss-distributions/launchd

Prefer the installed host's `man launchctl` and `man launchd.plist` when
archived documentation differs.
