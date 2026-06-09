---
name: codex-doctor-debugger
description: Use when diagnosing Codex CLI install, config, auth, runtime, feature flags, sandbox denials, debug models, prompt input, app-server, remote-control, remote websocket/unix connections, or local Codex health failures.
---

# Codex Doctor And Debugger

Use this skill when Codex CLI itself is failing or unclear: installation,
config, auth, runtime health, feature flags, sandbox denials, debug model
catalog, app-server transports, remote-control daemon, remote connection errors,
or local environment inconsistencies.

From this skill directory, the plugin root is `../..`.

## Inspect First

Start with cheap, non-mutating commands:

```bash
python3 ../../scripts/codex_cli_inspector.py --commands doctor debug sandbox features app-server remote-control --json
codex doctor --summary --ascii
```

Use machine-readable doctor output when automation needs to classify issues:

```bash
codex doctor --json
```

Do not paste raw doctor output into chat if it contains local paths, config
fragments, or environment details that are not needed. Summarize issue names,
counts, and actionable rows.

## Diagnostic Lanes

### Install, Config, Auth, Runtime

Use `codex doctor --summary --ascii` first. Expand only when the summary points
to a specific area:

```bash
codex doctor --all --ascii
codex doctor --json
```

If config parsing is suspect, run the target command with `--strict-config` to
surface unsupported fields for that CLI version.

### Feature Flags

Read before writing:

```bash
codex features list
```

Use `codex features enable <feature>` or `codex features disable <feature>` only
when the user explicitly asks to change a flag or the issue clearly requires it.
Report any config file mutation.

### Sandbox

Use sandbox commands to reproduce permission failures without launching a full
agent session:

```bash
codex sandbox -C "$PROJECT" --log-denials -- <command> <args>
codex sandbox -C "$PROJECT" --permissions-profile <name> -- <command> <args>
```

On macOS, `--log-denials` can help identify blocked paths or sockets. Keep
allowed Unix socket paths explicit:

```bash
codex sandbox -C "$PROJECT" --allow-unix-socket ./tmp/socket -- <command>
```

### Debug

Use debug commands for local model/config visibility:

```bash
codex debug models
codex debug prompt-input
codex debug app-server --help
```

Treat debug output as potentially sensitive because it can include model,
config, prompt-input, or environment-derived data.

### App Server And Remote Control

`codex app-server` and `codex remote-control` are experimental surfaces. Use
them only for app/IDE integration, remote TUI, protocol generation, or daemon
debugging.

Prefer loopback or Unix socket transports. Do not bind WebSocket listeners to
non-loopback interfaces without explicit security requirements and token setup.

Examples:

```bash
codex app-server --listen unix://
codex app-server --listen ws://127.0.0.1:0 --ws-auth capability-token --ws-token-file "$TOKEN_FILE"
codex remote-control --json start
codex remote-control --json stop
```

## Safety Boundaries

- Do not weaken sandbox, approvals, hook trust, feature flags, managed config, or app-server auth just to make a command pass.
- Do not expose bearer tokens, token file contents, shared secrets, config secrets, cookies, or auth artifacts.
- Do not start persistent daemons or listeners unless the user asked for them, and tell the user how to stop them.
- Do not delete config, sessions, caches, plugins, or logs during diagnosis without explicit approval.

## Completion Standard

Report the diagnostic lane, commands run, exact issue names or error text,
version/help facts used, any config or daemon state changed, and the smallest
next repair or verified healthy state.
