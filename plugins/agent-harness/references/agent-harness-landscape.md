# Agent Harness Landscape

Snapshot date: **2026-08-13**.

This ledger provides primary-source comparison anchors for agent-harness
engineering and evaluation. It is not a ranking and does not imply a universal
architecture. The projects target different users, domains, security models,
interfaces, and maturity levels; a mechanism useful in one system may be wrong
for another.

## Provenance Discipline

- Prefer a pinned public repository commit, paper, or first-party behavioral
  documentation over secondary descriptions.
- `Observed` means visible in the linked public source at the stated snapshot.
  It does not prove runtime behavior beyond the inspected path.
- `Inference` is a Workbench interpretation to test, not a claim made by the
  source authors.
- Source licenses govern permitted reuse. Availability of source is not a
  license to copy text or code into this repository. Review the license and
  preserve attribution before adapting an implementation.
- Public documentation for a closed product describes behavior only. Do not
  infer or claim closed internals.

## Public Implementation Snapshots

| System | Primary snapshot | Observed public surface | Workbench inference to test |
| --- | --- | --- | --- |
| OpenAI Codex | [`57f42a81131ccf5933e7ec5dc659c381eeb5d72b`](https://github.com/openai/codex/tree/57f42a81131ccf5933e7ec5dc659c381eeb5d72b) | Public workspace exposes host/core, protocol, execution, approval, and sandbox-related boundaries. | Typed host events and separated execution policy are useful comparison points for recoverable local harnesses. |
| DeepSeek Harness | [`47f943859bef60e4160492346772ded9b24f765a`](https://github.com/deepseek-ai/deepseek-harness/tree/47f943859bef60e4160492346772ded9b24f765a), including its [vendored-source ledger](https://github.com/deepseek-ai/deepseek-harness/blob/47f943859bef60e4160492346772ded9b24f765a/vendor/README.md) | MIT developer preview exposes plugin-defined model, tool, session, and loop seams. Its narrow LLM route update validates a complete candidate before one map replacement, and prepared in-flight calls retain the adapter they captured. Generic module HMR imports candidates before a swap, but does not await every asynchronous teardown and startup path. | Distill immutable generations, one admission commit, per-run binding, expected-revision checks, drain or cancel, and retained rollback. Do not generalize the narrow route swap into transactional arbitrary-module HMR or security isolation. |
| Hermes Agent | [`9d4ef04ed00055414c13fcf33925d85790221a3f`](https://github.com/NousResearch/hermes-agent/tree/9d4ef04ed00055414c13fcf33925d85790221a3f) | Public repository exposes an agent runtime, tool integrations, configuration, and user-facing execution surfaces. | Compare how extensible tool ecosystems affect registry truth, dependency checks, and portable run evidence. |
| OpenClaw | [`9c2dbf6500f16cafc6c68edbc3144b9acf06fe56`](https://github.com/openclaw/openclaw/tree/9c2dbf6500f16cafc6c68edbc3144b9acf06fe56) | Public source exposes a multi-surface assistant host with integrations, routing, and persistent runtime concerns. | Use it to study adapter boundaries, channel identity, long-lived state, and authority across noncoding actions. |
| goose | [`dafdbb7364cb8f145a71e2fd4e080136e225ad14`](https://github.com/aaif-goose/goose/tree/dafdbb7364cb8f145a71e2fd4e080136e225ad14) | Public source exposes one session-centered runtime across CLI, desktop, ACP, and server surfaces; a narrow capability-aware provider boundary; normalized extension tools; typed recipes; SQLite/WAL sessions; bounded child sessions; and a Harbor evaluation adapter. | Reuse one durable runtime across surfaces and make agent-visible context explicit. Treat its approval/configuration controls as product policy, not OS containment, and test the crash gap around external effects. |
| OpenHands | [application `4d3d9d197c0721c7f7d3b26029a4e5d09703890c`](https://github.com/OpenHands/OpenHands/tree/4d3d9d197c0721c7f7d3b26029a4e5d09703890c) and [runtime SDK `1fccbc71ba93206d5aad5d3b558fba36665cf566`](https://github.com/OpenHands/software-agent-sdk/tree/1fccbc71ba93206d5aad5d3b558fba36665cf566) | Current runtime SDK exposes a bounded local conversation, append-only EventStore, rebuildable condenser projection, interchangeable workspaces, confirmation policy, and persistent child conversations. | Event-sourced state and runtime separation are candidates for recovery experiments. Shared child workspaces and local no-sandbox mode need explicit risk tests. |
| SWE-agent | [`3ea751c087f32b16e039a2233dd6eefecef325d5c`](https://github.com/SWE-agent/SWE-agent/tree/3ea751c087f32b16e039a2233dd6eefecef325d5c) | Public source exposes a software-engineering loop, Agent-Computer Interface, history processors, per-step trajectory persistence, environment backends, and replay/evaluation workflows. | Constrained interfaces and trajectory evidence provide a focused baseline for same-model harness ablations, not a universal interface recipe. |
| aider | [`5dc9490bb35f9729ef2c95d00a19ccd30c26339c`](https://github.com/Aider-AI/aider/tree/5dc9490bb35f9729ef2c95d00a19ccd30c26339c) | Public source exposes a human-guided terminal coding workflow with repository maps, constrained edit formats, model adapters, Git commits, and undo. | Repository-aware context and draft/application stages are useful patterns, but Git rollback is not general host containment or external-effect recovery. |
| Cline | [`574b8eb45e875113ff2f541af3f5cd22ec0fbfa1`](https://github.com/cline/cline/tree/574b8eb45e875113ff2f541af3f5cd22ec0fbfa1) | Public source exposes host-owned permissions, SQLite task/session state, compacted context projections, Git checkpoints, and team/worktree surfaces. | Compare explicit permission and checkpoint UX, while keeping transcript, repository rollback, and external effects as separate recovery domains. |
| Open Interpreter | [`855ab60c0e10dac6bc89f3e248cba3746d44f034`](https://github.com/OpenInterpreter/open-interpreter/tree/855ab60c0e10dac6bc89f3e248cba3746d44f034) | Public source exposes a Rust-based local agent protocol with durable thread/turn/item records, approvals, sandbox options, child work, and optional tracing. | Study generated code, user confirmation, and host execution as separate states; do not infer that local execution is contained by default. |
| Letta Code | [`4baec4c2de3849bf3ac19881f9d05f5b495f934b`](https://github.com/letta-ai/letta-code/tree/4baec4c2de3849bf3ac19881f9d05f5b495f934b) | Public source exposes Git-backed memory/context blocks, deterministic permission handling, approvals, scheduled work, and child agents. | Compare editable durable memory with run-local context and test provenance, staleness, deletion, and the effective execution defaults. |
| LangGraph | [`658541c4960f329864a2523fc7d52427e8190bed`](https://github.com/langchain-ai/langgraph/tree/658541c4960f329864a2523fc7d52427e8190bed) | Public source exposes typed state/reducers, checkpointing per superstep, durable interrupt/resume, and hierarchical stores. | Graph transitions and checkpoints are useful orchestration primitives, but pre-interrupt side effects still need idempotency and application-level authority contracts. |
| browser-use | [`32601887cfbc9f4f1e3cad3e2b678e56aeaeaae4`](https://github.com/browser-use/browser-use/tree/32601887cfbc9f4f1e3cad3e2b678e56aeaeaae4) | Public source exposes a browser-specialized bounded loop, serializable history/replay, browser tools, domain controls, and secret-handling surfaces. | Browser traces and allowlists help specialize a harness, but live web state is not transactional and needs post-state, policy, and drift-aware evaluation. |
| Claude Code | [public distribution `5cf69b18c86d0224dc53815332bbd85574b97097`](https://github.com/anthropics/claude-code/tree/5cf69b18c86d0224dc53815332bbd85574b97097), [Agent SDK Python `71142da6e118dd113d82fc3fd549e4a2ba465973`](https://github.com/anthropics/claude-agent-sdk-python/tree/71142da6e118dd113d82fc3fd549e4a2ba465973), and [first-party documentation](https://code.claude.com/docs/en/how-claude-code-works) | Public behavioral surfaces document the loop contract, context/compaction, tools, permissions, sandbox options, subagents, and stream messages; the SDK launches a bundled native CLI. The implementation core is not an inspectable open-source target. | Evaluate documented behavior and black-box results only. Do not describe undocumented internal scheduling, storage, policy ordering, or compaction internals as fact. |

The `Observed` column is deliberately narrow. Before adopting a mechanism,
inspect the relevant file paths at the pin, capture the repository license, and
record an `E1 static` claim. Raise the grade only with local synthetic or
controlled-run evidence.

## Research And Evaluation Anchors

| Work | Primary source | Observed contribution | Boundary for harness use |
| --- | --- | --- | --- |
| Cordis composability preprint | [draft `948a07b369c62adb3b12e102458be5c18dfb69b9`](https://github.com/cordiverse/paper/tree/948a07b369c62adb3b12e102458be5c18dfb69b9) | Defines temporal and spatial composability, fiber lifecycle withdrawal, dependency-sensitive quiescence, and a proposed HMR procedure; it also names external emissions, untrusted-code sandboxing, state migration, interface versioning, and empirical validation as boundaries or open work. | Treat the formal model as a design hypothesis. The repository labels it an actively revised preprint, has no declared license, and presents self-evolving agent harnesses as future validation; do not copy its text or treat its generic atomic-reload claim as runtime evidence. |
| ReAct | [arXiv:2210.03629](https://arxiv.org/abs/2210.03629) | Presents interleaved reasoning and acting with external observations. | A prompting/interaction pattern is not a durable host loop, policy system, or side-effect contract. |
| SWE-agent | [arXiv:2405.15793](https://arxiv.org/abs/2405.15793) | Studies agent-computer interfaces for software-engineering agents. | Interface design results are domain- and benchmark-scoped; revalidate them for other tools and outcomes. |
| SWE-bench | [arXiv:2310.06770](https://arxiv.org/abs/2310.06770) | Introduces repository issue-resolution tasks with test-based evaluation. | Tests and patches are valuable coding oracles but do not cover authority, procedure safety, or noncoding effects. |
| AgentBench | [arXiv:2308.03688](https://arxiv.org/abs/2308.03688) | Evaluates language-model agents across multiple interactive environments. | Cross-domain breadth does not make a single aggregate score a universal harness measure. |
| ToolSandbox | [arXiv:2408.04682](https://arxiv.org/abs/2408.04682) | Provides stateful tool-use evaluation with trajectory and state concerns. | Map its tool and state assumptions explicitly before reusing scenarios or metrics. |
| OSWorld | [arXiv:2404.07972](https://arxiv.org/abs/2404.07972) | Introduces real-computer environment tasks for multimodal agents. | UI completion needs state and procedure oracles; visual action traces alone do not establish safe effects. |
| WebArena | [arXiv:2307.13854](https://arxiv.org/abs/2307.13854) | Provides realistic, reproducible web environments and tasks. | Controlled websites reduce evaluation risk but do not reproduce every production identity, policy, or concurrency condition. |
| tau-bench | [arXiv:2406.12045](https://arxiv.org/abs/2406.12045) | Evaluates tool-agent-user interaction in rule-governed domains. | Domain policy adherence is central, but harness release gates also need recovery, cancellation, and effect reconciliation. |
| AgentDojo | [arXiv:2406.13352](https://arxiv.org/abs/2406.13352) | Evaluates agent utility and security under prompt-injection attacks. | Security scenarios support adversarial testing; they do not replace deployment-specific threat modeling and containment. |

## Comparison Questions

Use the sources to answer bounded questions rather than to assemble a feature
checklist:

- Who owns the control loop, and which transitions are durable and typed?
- How are provider capability, tool schema, executor availability, authority,
  approval, and sandboxing kept distinct?
- What is canonical state, what is a projection or checkpoint, and how does a
  run recover after each crash boundary?
- How are intent, idempotency, external effect identity, cancellation, and
  uncertain completion represented?
- Are child agents first-class nested runs with constrained authority and
  budgets, or opaque recursive calls?
- Which mechanisms assume code, tests, a terminal, or version control, and what
  changes for mail, calendars, browsers, records, or devices?
- What complete system tuple, scenario slice, oracle, and evidence grade support
  each reliability or safety claim?

No source in this ledger establishes a universal best architecture. Synthesize
the smallest coherent contract for the target environment, preserve provenance,
and validate the composed behavior with paired ablations and domain-appropriate
oracles.
