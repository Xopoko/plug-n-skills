# Windows Task Scheduler Runtime Proof

Bind the full task path and principal. Treat the task name alone as ambiguous.

## P0 And P1

Read-only inspection commonly includes:

```powershell
Get-ScheduledTask -TaskPath <path> -TaskName <name>
Get-ScheduledTaskInfo -TaskPath <path> -TaskName <name>
Export-ScheduledTask -TaskPath <path> -TaskName <name>
```

Keep exported XML and action arguments in a restrictive local artifact. Inspect
only redacted structural fields in model context: executable, arguments digest,
working directory, triggers, principal SID or account, logon type, run level,
conditions, missed-run behavior, and multiple-instance policy.

Set the working directory explicitly; the default differs from an interactive
shell. The action has no general stdout or stderr sink, so the payload or a
controlled wrapper must produce bounded private output and a receipt.

Record principal, logon type, SID, session, integrity, and resource access.
Interactive-token tasks require an interactive session. Other logon types have
different credential, network, and encrypted-file behavior.

## P2 And P3

`Start-ScheduledTask` and `schtasks /Run` are asynchronous demand requests.
They prove P2 only after a new manager-started action and terminal result are
observed. They also create ordinary start, action, result, and instance
evidence, so those surfaces cannot prove P3.

P3 requires a version-verified Operational event or trigger reason specific to
the configured non-demand trigger, joined by exact task path and activity or
instance identifier to the same nonce-bearing receipt and terminal event.
`LastRunTime`, `LastTaskResult`, running state, and a generic instance identifier
are corroboration only.

Bound event inspection server-side to the exact task, time window, and one
version-verified scheduled-trigger event identifier. For example, after setting
an exact full task path, a bounded window in milliseconds, and a verified event
identifier:

```powershell
function ConvertTo-XPathLiteral {
  param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$Value
  )

  if (-not $Value.Contains("'")) { return "'" + $Value + "'" }
  if (-not $Value.Contains('"')) { return '"' + $Value + '"' }

  throw "The Event Log XPath subset cannot encode a TaskName containing both quote delimiters."
}

$TriggerId = [int]$VerifiedScheduledTriggerId
$WindowMs = [long]$WindowMilliseconds
if ($TriggerId -lt 1 -or $TriggerId -gt 65535) {
  throw "VerifiedScheduledTriggerId must be an integer from 1 through 65535."
}
if ($WindowMs -lt 1 -or $WindowMs -gt 86400000) {
  throw "WindowMilliseconds must be an integer from 1 through 86400000."
}

$TaskLiteral = ConvertTo-XPathLiteral -Value $ExactTaskPath
$XPath = @"
*[System[
  EventID=$TriggerId and
  TimeCreated[timediff(@SystemTime) <= $WindowMs]
]]
and
*[EventData[Data[@Name='TaskName']=$TaskLiteral]]
"@

$Filter = [xml]'<QueryList><Query Id="0" Path="Microsoft-Windows-TaskScheduler/Operational"><Select Path="Microsoft-Windows-TaskScheduler/Operational"></Select></Query></QueryList>'
$Filter.SelectSingleNode('//Select').InnerText = $XPath
Get-WinEvent -FilterXml $Filter.OuterXml -MaxEvents 20
```

Use the trigger event's activity or instance identifier for a second
server-side exact-chain query. Preserve only redacted excerpts. Verify event
identifiers, `TaskName` field placement, and correlation fields on the deployed
Windows version; Microsoft troubleshooting guidance commonly uses event 107
for a scheduler-triggered task, but do not hard-code that assumption across
versions without checking. Do not interpolate a task path directly into XPath:
construct a supported XPath literal, insert the complete expression through an
XML API, and fail closed when the path cannot be encoded.

A separate one-time trigger can be used as a canary when authorized, but it
proves only its own P3. Set and report the multiple-instance policy explicitly:
parallel, queue, ignore-new, and stop-existing have different behavior.

## Sources

- Task Scheduler overview:
  https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page
- ScheduledTasks PowerShell module:
  https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/
- Task Scheduler troubleshooting:
  https://learn.microsoft.com/en-us/troubleshoot/windows-server/system-management-components/troubleshoot-scheduled-tasks-not-running
