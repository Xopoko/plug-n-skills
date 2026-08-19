# Agent Harness Plugin

Agent Harness combines vendor-neutral harness engineering and evaluation,
including safety contracts and evidence gates for runtime reconfiguration, with
the operational surfaces for Codex CLI, Claude Code, producer-native deferred
completion, and local operating-system scheduler proof. It does not provide a
runtime loader or prove safety from a design artifact alone.

It does not own skill/plugin authoring or portfolio maintenance; those remain
in Capability Workbench. Generic application architecture remains in
architecture-intelligence.

## Skills

The plugin exposes 20 skills: one portfolio router and 19 narrow leaves.

### Portfolio and harness

- `agent-harness`: routes harness and Codex/Claude runtime requests.
- `agent-harness-engineering`: designs typed, bounded control harnesses and
  versioned provider, tool, module, or loop reconfiguration.
- `agent-harness-evaluation`: evaluates replay, reliability, recovery,
  cancellation, concurrent runtime generations, rollback, context pressure,
  and release gates.

### Codex CLI

- `codex-cli`
- `codex-exec-automation`
- `codex-deferred-completion`
- `codex-thread-supervisor`
- `codex-plugin-mcp-manager`
- `codex-doctor-debugger`
- `codex-log-reader`
- `codex-task-corpus`
- `codex-environments`

### Claude Code

- `claude-code`
- `claude-print-automation`
- `claude-plugin-mcp-manager`
- `claude-doctor-debugger`
- `claude-agent-worktrees`
- `claude-hooks-settings`

### Scheduled automation

- `scheduled-automation-runtime`: proves launchd, systemd timer, cron, and
  Windows Task Scheduler runs without promoting manual-shell evidence.

### Human credential handoff

- `credential-handoff`: lets an operator satisfy native password, passphrase,
  OTP, device approval, or 1Password prompts while the agent receives only a
  bounded status receipt, never the credential value.

## Bundled helpers

The plugin retains the Codex and Claude CLI inspectors, Codex rollout and skill
catalog analysis, thread-handoff validation, the credential-handoff launcher,
the harness artifact validator, and the Codex deferred-completion MCP server.

```bash
python3 scripts/codex_cli_inspector.py --json
python3 scripts/claude_code_inspector.py --json
python3 scripts/codex_log_reader.py --help
python3 scripts/codex_log_reader.py corpus-check --help
python3 scripts/codex_skill_catalog_audit.py --help
python3 scripts/validate_thread_skill_handoff.py --help
python3 scripts/credential_handoff.py --help
python3 scripts/harness/validate_harness_artifact.py --help
```

Codex reads `.codex-mcp.json`; Claude Code reads `.mcp.json`. Both declarations
launch the same bounded deferred-completion server in `mcp/server.py`.

## Migration contract

`references/source-migration-ledger.json` records three whole-plugin merges,
two Capability Workbench skill moves, the Workbench responsibilities that stay
there, every migrated file and digest, and collision handling.

The only content filename collision was `references/cli-operation-contracts.md`.
Both distinct safety contracts are retained as
`codex-cli-operation-contracts.md` and
`claude-cli-operation-contracts.md`; the Claude skill links point to the latter.
Legacy READMEs and manifests are replaced by this combined publication surface.
Legacy icons are not copied.

## Validation

From this plugin directory:

```bash
python3 -m unittest discover -s tests -q
```

From the repository root:

```bash
python3 plugins/capability-workbench/scripts/plugin/validate_plugin.py plugins/agent-harness
python3 -m unittest discover -s plugins/agent-harness/tests -q
```
