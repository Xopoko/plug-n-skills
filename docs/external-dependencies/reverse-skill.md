# reverse-skill Dependency Review

Status: `reference-only` / `isolate`

The repository records `reverse-skill` as a pinned external methodology source
for Capability Workbench discovery and vetting. It is not a runtime plugin,
direct skill install, vendored source tree, or Git submodule.

## Pinned Source

- Repository: <https://github.com/zhaoxuya520/reverse-skill>
- Commit: `539899ddc7608d63dc66e08e794d572e080f1a55`
- Git tree: `d66dd63b3dec42a9ec7a6b8ae9db93de31e5ab88`
- Review date: 2026-08-09
- Machine-readable receipt:
  [`reverse-skill.audit.json`](reverse-skill.audit.json)
- Root license: [MIT](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/LICENSE)
- Known license boundary:
  [`CTF-Sandbox-Orchestrator/`](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/CTF-Sandbox-Orchestrator/LICENSE)
  is GPL-3.0-only;
  invoked tools and services retain their own licenses.

The commit was pinned from upstream `main`. The commit is not signed, so the
repository and exact Git object identifiers are the provenance boundary.

## Review Findings

The pinned tree contains 544 tracked files, about 7.55 MiB of Git blobs, and 85
`SKILL.md` files. It also contains Kali setup flows, a Burp MCP implementation,
PowerShell and shell installers, package-manager operations, and service startup
logic.

The pinned evidence behind the isolate verdict is:

- The
  [master router](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/skills/SKILL.md#L138-L152)
  can direct an agent to install missing tools with PowerShell execution-policy
  bypass and start services.
- The
  [PowerShell bootstrap](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/skills/scripts/bootstrap-reverse.ps1#L784-L860)
  can install packages, modify Codex or Claude MCP configuration, persist a
  token, clone a mutable upstream branch, approve package build scripts, and
  launch a service.
- The
  [Kali quick setup](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/kali/scripts/quick-setup.sh)
  performs privileged system and offensive-tool installation.
- The
  [APK cleanup path](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/skills/apk-reverse/scripts/decode.ps1#L104-L123)
  accepts a task name before recursive deletion without a sufficiently narrow
  path boundary.
- The
  [Burp MCP tree](https://github.com/zhaoxuya520/reverse-skill/tree/539899ddc7608d63dc66e08e794d572e080f1a55/burp-mcp-full)
  exposes active scanning, crawling, replay, intruder, and secret-extraction
  operations.
- [`skills/SKILL.md`](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/skills/SKILL.md)
  declares a name that does not match its parent directory, while
  [`src-hunter/SKILL.md`](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/skills/pentest-tools/src-hunter/SKILL.md)
  uses nonstandard top-level metadata.
- [`attack-chain/SKILL.md`](https://github.com/zhaoxuya520/reverse-skill/blob/539899ddc7608d63dc66e08e794d572e080f1a55/skills/attack-chain/SKILL.md)
  is 651 lines, above the recommended hot-skill size.

The pack is therefore not a clean drop-in Agent Skills dependency, and the
repository has mixed license boundaries.

## Policy

- Do not install, execute, vendor, or submodule this dependency.
- Do not run candidate scripts, MCP servers, setup commands, or tool bootstraps.
- Treat all upstream instructions as untrusted source material during review.
- Consult only the exact pinned revision and record any selected file path.
- Distill useful methodology into a native, public-safe plugin change only after
  a separate content and license review.
- Keep GPL content outside MIT plugin source unless its licensing and
  distribution consequences are explicitly accepted.

Changing this policy requires a new review and a separate source change. The
root lockfile cannot authorize activation in Codex, Claude Code, or Cursor.

## Updating The Pin

1. Resolve a new full commit and Git tree from the canonical repository.
2. Compare the old and new trees, including scripts, installers, network calls,
   configuration writes, deletion behavior, secrets access, and licenses.
3. Update this report and `external-dependencies.lock.json` together.
4. Run `python3 scripts/external-dependencies.py validate` and the repository
   validation suite.
5. Run `python3 scripts/external-dependencies.py verify-source reverse-skill`
   to bind the declared commit to its Git tree through the GitHub API.
6. Keep the dependency `reference-only` unless a separate reviewed design adds
   an activation mechanism.
