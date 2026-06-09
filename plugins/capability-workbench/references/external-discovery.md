# External Discovery

Use this reference for broad capability discovery before synthesis. Use `install-scope.md` separately to choose the delivery surface and whether installation is required.

## Objective

Seek the best-supported practically achievable implementation, not the best local merge. Treat public repositories, public web, marketplaces, research/docs, and community implementations as the primary corpus. Treat local skills as supplementary evidence and regression baselines. External discovery does not imply repo-local output; installation scope is validated separately.

## Required Ledger

For synthesis/augmentation, maintain `<output-dir>/external-discovery-ledger.json` and validate it:

```bash
python3 ../../scripts/synthesis/external_discovery_gate.py --template > <output-dir>/external-discovery-ledger.json
python3 ../../scripts/synthesis/external_discovery_gate.py <output-dir>/external-discovery-ledger.json --json
```

The ledger is the machine-readable source of truth for discovery breadth, source families, search waves, candidate coverage, blockers, and stop condition. Markdown reports may summarize it but must not replace it.

## Source Families

Search broadly across available inspectable sources:

- public repositories: GitHub, GitLab, source archives, example repos, templates;
- skill/plugin marketplaces: OpenAI skills, OpenClaw/ClawHub, agent plugin marketplaces;
- implementation ecosystems: libraries, CLIs, frameworks, official docs, sample apps;
- research and evaluation sources: papers, benchmarks, design docs, issue discussions, postmortems;
- community implementations: blog posts, forums, recipes, open-source examples.
- ready-made agent assets: public skills, plugins, MCP servers, prompt packs, eval harnesses, validators, and implementation repos.

Skip sources that require paid access, API keys, login, opaque install, telemetry, or credentialed inspection. Record the limitation and search for alternatives.

## Search Waves

Wave 1: direct terms.

- `"<target>" "SKILL.md"`
- `"<target>" Codex skill`
- `"<target>" Claude skill`
- `"<target>" plugin`
- `site:github.com "<target>" "SKILL.md"`

Wave 2: adjacent ecosystems and implementation patterns.

- `"<target>" architecture`
- `"<target>" implementation pattern`
- `"<target>" best practices`
- `"<target>" validator`
- `"<target>" schema`
- `"<target>" workflow`

Wave 3: failure modes and quality mechanisms.

- `"<target>" testing`
- `"<target>" evaluation`
- `"<target>" safety`
- `"<target>" reliability`
- `"<target>" benchmark`
- `"<target>" pitfalls`

Wave 4: marketplaces and community variants.

- `"<target>" OpenClaw`
- `"<target>" ClawHub`
- `"<target>" agent skill`
- `"<target>" community plugin`

Expand queries with synonyms, domain tools, file names, known packages, and failure modes discovered in earlier waves.

## Triage

For each promising source, record:

- source family, URL/path, owner, license/ref if known;
- readable files and whether source was fully inspectable;
- core mechanism candidates;
- dependencies, runtime, services, keys, telemetry, and safety risks;
- why it beats, ties, or loses to current best mechanisms.

Prefer source-pinned links or local snapshots when adopting code or precise behavior.

## Diminishing Returns

Stop only when two consecutive waves add no new high-scoring mechanism, architecture pattern, safety control, validation method, or implementation technique that changes the distillation plan.

If the stop condition is not met because time, network, source access, or safety blocks discovery, mark the synthesis as partial and state the missing source families.
