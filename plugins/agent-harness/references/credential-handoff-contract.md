# Credential Handoff Contract

Use this reference with `skills/credential-handoff/SKILL.md` when an agent-run
workflow needs a human-entered credential, 1Password, a system authentication
dialog, browser login, or physical device unlock/trust action.

## Security Boundary

The goal is not to make the agent a secret holder. The goal is to authorize one
task-scoped use while keeping the value outside model-visible context and
agent-observed results.

Allowed agent-visible data:

- target identity and purpose;
- an opaque account selector or secret reference only when the user approved it
  as non-sensitive; otherwise the user selects the account or item locally;
- request ID, process ID, allowlisted state, exit code, timestamps, and a
  sanitized error class;
- secret-free verification output.

Forbidden agent-visible data:

- passwords, passphrases, PINs, OTP values, recovery codes, API keys, tokens,
  private keys, seed phrases, cookies, or resolved secret fields;
- terminal keystrokes or transcripts from the credential window;
- secret-bearing stdout/stderr, process arguments, command history, clipboard,
  prompt/chat text, environment dumps, screenshots, recordings, or temp files.

This boundary reduces exposure; it does not prove that the local operating
system, the target program, or other same-user processes are uncompromised.

## Mechanism Selection

| Situation | Preferred mechanism | Agent observes |
| --- | --- | --- |
| CLI already has a hidden prompt | Run the real CLI in a detached visible terminal | Status and exit code only |
| CLI accepts environment credentials | `op run -- <command>` with task-scoped secret references | Status and masked non-secret result |
| Supported 1Password Shell Plugin | `op plugin run -- <command>` | Approval plus status |
| Browser login | User or officially supported password-manager autofill controls the credential fields | Login state, not field values |
| Windows Hello, biometric, password-manager unlock, device passcode/trust | User acts directly in that protected surface | Completion or cancellation only |
| Target accepts only a plaintext argument or agent-captured input | No safe adapter | Stop and hand the step to the user |

Do not treat an ordinary chat form, generic agent input request, or captured
terminal stdin as a protected secret channel unless the host explicitly proves
that the value is excluded from model context and logs.

## Visible-Terminal Protocol

Before launch:

1. Resolve and verify the exact executable, working directory, remote/service
   identity, and non-secret arguments. The helper requires an absolute native
   `.exe`/`.com` path plus a SHA-256 pin and rechecks the pin in the worker. For
   `op run`, pin both `op.exe` and the executable after `--`.
2. Use a non-interactive probe when available. For SSH, disable password and
   keyboard-interactive fallback during discovery; verify or pin the host key
   before asking for a password.
3. Explain why input is needed, which native program will prompt, how many
   prompts are expected, and what success will enable.
4. Ensure the launch request contains no secret. The helper rejects common
   secret-bearing flags, direct top-level 1Password retrieval, shells,
   interpreters, generic launchers, URL credentials, and `--no-masking`.
   These checks do not prove an arbitrary target binary is safe: review the
   pinned executable, its configuration, working directory, and arguments.
5. Use one untracked, host-local state directory per task. An atomically created
   lifecycle lock blocks a second launch and remains owned by the worker until
   the target exits.

During the handoff:

- The target inherits the new console's stdin/stdout/stderr. The agent does not
  redirect or read them.
- The helper removes inherited environment variables whose names commonly
  identify credentials before adding explicitly approved unresolved `op://`
  references.
- The user types only into the target's native prompt or protected system UI.
- Coordination uses the lifecycle lock plus an atomic JSON status receipt. A
  waiting state is normal; poll slowly and do not create duplicate prompts.
- Do not take screenshots of the credential surface or use UI automation to
  type into password-manager, biometric, system-authentication, or device
  passcode dialogs.

After completion:

1. Verify with a new secret-free operation rather than assuming exit code alone
   proves the intended authenticated state.
2. Delete the exact per-request directory only after it reaches a terminal
   state and no process still needs it.
3. Report the target, mechanism, and verification. Say that the credential was
   applied without being returned to the agent; do not claim stronger host-wide
   secrecy than the evidence proves.

## 1Password Modes

### Desktop app integration

On Windows, install the CLI, turn on Windows Hello in the desktop app, then
enable **Settings > Developer > Integrate with 1Password CLI**. A subsequent
`op` command triggers user authentication. The agent must not automate the
password-manager or Windows Hello dialog.

### `op run`

Use secret references rather than resolved values. `op run` resolves them and
starts a subprocess whose environment contains the values only for that
process lifetime. Default masking conceals resolved secrets if the subprocess
prints them; never add `--no-masking`.

Environment injection is not isolation from other processes running as the
same OS user. Prefer the smallest target subprocess and least-privilege vault or
service-account scope. Do not print, inspect, serialize, or return its effective
environment.

### Shell Plugins

Use a supported Shell Plugin when it owns authentication for the target CLI.
Let the user select/approve credentials in 1Password, keep the default scope as
narrow as practical, and observe only the target command's non-secret result.

### `op read` and direct retrieval

Do not call `op read`, reveal secret fields, or resolve an SDK secret into an
agent-observed variable merely because the user permits 1Password access. If a
consumer requires stdin, use a reviewed target-specific adapter entirely
inside the detached process, with no intermediate output or persisted value.
If that cannot be proved, stop and hand the step to the user.

## Status Receipt

`scripts/credential_handoff.py` emits
`agent_harness.credential_handoff_status.v1` with only:

- `request_id`;
- `state`: `launched`, `running`, `succeeded`, `failed`, or `cancelled`;
- `exit_code` after completion;
- `created_at_utc` and `updated_at_utc`;
- optional allowlisted `error_code`.

Purpose, command, arguments, prompt text, terminal output, environment, and
secret values never appear in the status receipt. The separate request file is
non-secret by contract and should be removed after verification.
Cleanup refuses a forged terminal receipt while that request's worker still
owns the lifecycle lock. A stale lock after a worker crash is fail-closed and
requires explicit process/state inspection before manual recovery.

## Failure Handling

- No prompt: verify the target is interactive, the new console stayed alive,
  and, for 1Password, the CLI is installed, the desktop app is unlocked, and
  app integration is enabled.
- Stale lifecycle lock: inspect the recorded worker PID and relevant process
  state. Do not delete the lock merely to force a retry while ownership is
  uncertain.
- Rejected authentication: preserve the same target and let the user retry only
  when the native program supports it; do not ask for the value in chat.
- Ambiguous item/account: ask the user to select the correct item or provide a
  secret reference. Do not broaden to unrelated vault enumeration.
- Unexpected prompt, certificate, host key, consent, or destination: cancel and
  re-establish target identity before any entry.
- Command needs a plaintext argument: find an environment, stdin, OS credential
  store, Shell Plugin, or native-prompt route; otherwise stop.

## Primary Sources

- 1Password CLI setup and desktop integration:
  https://www.1password.dev/cli/get-started
- 1Password desktop-app authentication and activity log:
  https://www.1password.dev/cli/app-integration
- `op run`, subprocess scoping, and masking:
  https://www.1password.dev/cli/reference/commands/run
- Environment-variable exposure caveat:
  https://www.1password.dev/cli/secrets-environment-variables
- 1Password security guidance for AI access:
  https://www.1password.dev/get-started/secure-ai-access
