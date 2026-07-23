# Cron Runtime Proof

Bind the exact implementation, daemon, installed source, and executing account:
user crontab, system crontab, or a cron directory.

## P0 And P1

Inspect syntax, shell, PATH, mail or log destination, working-directory
behavior, ownership, permissions, filename, file type, final newline, security
context, and daemon state. Cron implementations differ.

P1 requires implementation-specific evidence that the exact installed source
was accepted or reloaded, not merely that a file exists or `crontab -l` prints
an entry. Cronie, for example, imposes file ownership, mode, naming, type, and
newline constraints on system sources. If the implementation exposes no
acceptance or reload evidence, report P1 as unavailable rather than assuming
registration.

Keep raw crontabs and arguments in a restrictive local artifact; return only
redacted structural fields and digests.

## P3

Cron has no portable per-invocation identifier or standard demand-run
operation. For P3, combine a post-baseline daemon CMD or system-log record for
the exact source and command with a fresh nonce receipt and, when available,
short-lived parent evidence. Bound log reads by time and record count. Absence
of a daemon log is not proof that no run occurred, and weak correlation must be
reported as partial rather than upgraded to P3.

A separate temporary entry proves only the canary. Do not replace cron with a
wrapper or alternate scheduler merely to make the current entry easier to
observe. Do not infer exactly-once execution.

## Sources

- Cronie crontab format and source constraints:
  https://github.com/cronie-crond/cronie/blob/master/man/crontab.5
- Cronie daemon behavior:
  https://github.com/cronie-crond/cronie/blob/master/man/cron.8
