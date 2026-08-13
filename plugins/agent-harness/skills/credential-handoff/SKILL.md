---
name: credential-handoff
description: >-
  Credential prompts and 1Password CLI: route task-scoped secrets from a human
  or vault into a target process without exposing values to model context,
  chat, logs, arguments, or files. Excludes account administration.
---

# Credential Handoff

Bundled commands use `$PLUGIN_ROOT` (`$env:PLUGIN_ROOT` in PowerShell; same
path suffix) for the plugin root. Set it once from the host's plugin-root
variable when defined; otherwise use this skill folder's `../..`.

Use this skill when work is blocked on a password, passphrase, OTP, API token,
login, device unlock/trust action, Windows Hello approval, or a 1Password item.
The agent may coordinate the handoff, but the secret value must not enter model
context or an agent-observed tool result.

Read `$PLUGIN_ROOT/references/credential-handoff-contract.md` before choosing a
1Password mode, a browser/device handoff, or a non-native input adapter.

## Required Route

1. Prove a credential is actually required with a non-prompting probe when the
   target supports one. Do not create an unexpected blocking prompt during
   discovery.
2. Choose the narrowest route:
   - native hidden prompt in a separate user-visible terminal;
   - `op run` or a 1Password Shell Plugin that injects only into the target
     subprocess;
   - direct user action in a browser, password-manager, system-authentication,
     or device-unlock surface that the agent must not automate.
3. Tell the user the target, purpose, expected input type and prompt count. Do
   not ask them to paste the value into chat or an ordinary text-input tool.
4. Observe only an allowlisted receipt such as `running`, `succeeded`,
   `failed`, or `cancelled`, plus a non-secret exit code. Never capture the
   detached terminal transcript, keystrokes, clipboard, resolved environment,
   or secret-bearing stdout/stderr.
5. Verify the resulting authenticated state with a secret-free check. Clean up
   request/status artifacts after the detached process has finished.

## Windows Visible-Terminal Helper

The helper launches the target in a new console and returns only a status-file
path and process ID. Every command and argument must already be secret-free.
Use one untracked, host-local state directory per task. The helper rejects a
second launch while an atomic lifecycle lock exists. It rejects shells,
interpreters, and generic launchers; pass an absolute native executable path
and its SHA-256 pin. For `op run`, pin both `op.exe` and the executable after
`--`.

```powershell
$target = (Resolve-Path -LiteralPath "C:\path\to\target.exe").Path
$targetSha256 = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()

python "$PLUGIN_ROOT/scripts/credential_handoff.py" launch `
  --state-dir "$HANDOFF_STATE_DIR" `
  --title "Credential required" `
  --purpose "Authenticate the requested target" `
  --expected-input "account password in the native prompt" `
  --cwd "$PWD" `
  --executable-sha256 "$targetSha256" `
  --acknowledge-nonsecret-command `
  -- "$target" <non-secret-args>

python "$PLUGIN_ROOT/scripts/credential_handoff.py" status <status-path>
python "$PLUGIN_ROOT/scripts/credential_handoff.py" cleanup <status-path>
```

Poll only at bounded, user-relevant intervals. A waiting prompt is not a
failure. Do not relaunch unless the prior request reached a terminal state or
the user cancelled it.

## 1Password Route

- Verify `op --version`; let the user complete the 1Password desktop or system
  authentication prompt.
- Prefer a task-scoped `op://vault/item/field` reference supplied or selected
  for this task, then run the consumer under `op run`. Keep default output
  masking enabled. Pass references through repeated `--env-reference
  NAME=op://...` options before `--`; the helper supplies them only to the
  detached process and does not use a shell.
- When the helper launches `op run`, also pass `--op-target-sha256` for the
  absolute consumer executable after `--`.
- Prefer a supported `op plugin run` integration when it can authenticate the
  exact target CLI without exposing a value.
- Never emit `op read` output to an agent tool, use `--no-masking`, reveal a
  secret field, enumerate unrelated vault contents, or place a resolved secret
  in a command argument, chat message, clipboard, tracked file, or status file.

## Stop Conditions

Stop and request direct user completion when the target cannot accept a native
prompt, 1Password injection, or another non-observed handoff. Also stop on
target-identity ambiguity, unexpected prompt scope, host-key/certificate
mismatch, repeated authentication failure, or any indication that a secret
would be logged or returned to the agent.

Completion means the target operation is verified, the receipt contains no
secret material, and the agent reports the mechanism and result without
claiming it read or knew the credential.
