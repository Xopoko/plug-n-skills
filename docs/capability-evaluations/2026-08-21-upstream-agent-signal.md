# Upstream Agent Capability Signal, 2026-08-21

## Scope And Safety

This review distilled mechanisms from nine public repositories into the
canonical plugin source without installing, executing, vendoring, or activating
candidate code. Candidate hooks, installers, MCP servers, CLIs, workers, and
tests were not run. The only behavioral execution used synthetic prompts
against the existing loopback-only local Qwen endpoint.

The source-only target was this canonical checkout with
`install_required=false`. Runtime caches and global Codex, Claude, and Cursor
state were not refreshed.

## Immutable Source Snapshots

`external-dependencies.lock.json` is the canonical declaration surface. This
table mirrors its immutable identities and links each source to its public
static audit.

| Source | Dependency ID / audit | Commit | Tree | License boundary |
| --- | --- | --- | --- | --- |
| [mattpocock/skills](https://github.com/mattpocock/skills/tree/5b15a47f2d7150f545fbcacbfe381787fc0230dc) | [mattpocock-skills](../external-dependencies/mattpocock-skills.md) | `5b15a47f2d7150f545fbcacbfe381787fc0230dc` | `b067eb5ab717af0165a555ff7791afa3494053c4` | MIT |
| [cursor/plugins](https://github.com/cursor/plugins/tree/46125561306434d8a1d7745d540d8932ab0cd2a2) | [cursor-plugins](../external-dependencies/cursor-plugins.md) | `46125561306434d8a1d7745d540d8932ab0cd2a2` | `1d1795c88013daf2470a40892d72664ec71b5061` | `NOASSERTION` root; path-level MIT |
| [ibelick/ui-skills](https://github.com/ibelick/ui-skills/tree/33b35e7d13d4bce7e4358d2205e406c1b20263fc) | [ui-skills](../external-dependencies/ui-skills.md) | `33b35e7d13d4bce7e4358d2205e406c1b20263fc` | `8ee92fe60983596fba48851664914a5acbedea20` | MIT |
| [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd/tree/e7555fcaf612dfa1739dc86610ea926a906db614) | [i-have-adhd-eval-2026-08-21](../external-dependencies/i-have-adhd-eval-2026-08-21.md) | `e7555fcaf612dfa1739dc86610ea926a906db614` | `42ce88189368a2612da7f6f841841b404334570d` | MIT |
| [revfactory/harness](https://github.com/revfactory/harness/tree/cceac68ea1d0ad198ef4b7b906cd238375836387) | [revfactory-harness](../external-dependencies/revfactory-harness.md) | `cceac68ea1d0ad198ef4b7b906cd238375836387` | `b88c5ce9b73461bf6d92224863a9db91b6cedace` | Apache-2.0 |
| [chaitanyagiri/munder-difflin](https://github.com/chaitanyagiri/munder-difflin/tree/57a6ce65cb6d0b72bebd17a4b4ae92e60446c979) | [munder-difflin](../external-dependencies/munder-difflin.md) | `57a6ce65cb6d0b72bebd17a4b4ae92e60446c979` | `7c52501ecb2f0ddc4dad4a69601e2dfe8775b398` | MIT source; bundled LimeZu art is non-commercial |
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman/tree/2f49f0e1a352aa810e70056b7930aeb0b3d219b4) | [caveman](../external-dependencies/caveman.md) | `2f49f0e1a352aa810e70056b7930aeb0b3d219b4` | `603ece15f092a82703cb6e86d102050502775f25` | MIT plus BUSL-1.1 components and third-party notices |
| [rtk-ai/rtk](https://github.com/rtk-ai/rtk/tree/29f9bb7161775cd807565fd3041eb2b7d1be071c) | [rtk](../external-dependencies/rtk.md) | `29f9bb7161775cd807565fd3041eb2b7d1be071c` | `deedf05df34a2e415a6cdc468ec8ae5d41c96276` | Apache-2.0 |
| [Forward-Future/loopy](https://github.com/Forward-Future/loopy/tree/75966cbd572a4185064971c9fe5e9c52e8f8456d) | [loopy](../external-dependencies/loopy.md) | `75966cbd572a4185064971c9fe5e9c52e8f8456d` | `f992d05d1517c24b3598bd4b43826f92e01e34e7` | MIT |

Two final source-review passes added no plan-changing mechanism.

## High-Signal Decisions

| Mechanism | Decision | Native owner | Evidence boundary |
| --- | --- | --- | --- |
| Native Cursor `.cursor-plugin/plugin.json` and root marketplace format | Repair current documentation; defer native packaging | Repository manifests/installers plus Capability Workbench | Official pinned schema contradicts the prior local statement that Cursor has no plugin marketplace. No compatible Cursor client was present for live discovery proof. |
| Candidate-visible eval blinding, no self-report, position-bias accounting | Adopt | `capability-evaluation` | The first local run exposed evaluation terms to the model and was invalidated before scoring. |
| Tool-output reduction with exact omitted counts and raw recovery | Revise: reject model-generated projection; keep a narrow deterministic exact-duplicate helper plus raw fallback | `context-density` | The original five-trial promotion was superseded by 100-unit and held-out adversarial campaigns. The corrected fail-closed policy kept raw for 8/9 cases, preserved 45/45 immediate downstream outcomes, and reduced evidence bytes 72.085%; repeated-boundary adoption remains unproved. |
| Independent correctness, standards, and specification review passes | Defer | `forge-code-review` | The first 3-trial candidate passed, but a compact rerun produced two critical candidate failures. |
| Checkable completion criteria for skill authoring | Reject current delta | `skill-factory` | Zero wins, six critical candidate failures, and higher prompt/output tokens. |
| Evidence-first debugging loop | Reject current artifact | Potential future `engineering-hygiene` skill | One win but five critical candidate failures; no stable promotion evidence. |
| Tracer-bullet and expand/migrate/contract planning | Reject current delta | `sdd-plan-tasks` | Zero wins, one loss, and three critical candidate failures. |
| UI finding proof/falsification gate | Defer | `ui-visual-audit` | One win but three critical candidate failures. The static mechanism remains useful review material, not promoted guidance. |
| First/last-line sufficiency and ADHD response cases | Keep as future fixtures | `i-have-adhd` plus `capability-evaluation` | The local skill already has the safer invocation, persistence, and medical boundaries. |
| Loop qualification and explicit no-op/approval/stagnation outcomes | No new plugin | Agent Harness and repository guidance | Existing local contracts already cover bounded retries, stop conditions, authority, and typed results more strongly. |
| Concise narration versus durable evidence | Keep conservative native guardrails; do not promote the Caveman treatment globally | Context Density plus Capability Evaluation | A 30-unit repeated-compaction campaign found task parity but only 7.43% full-pipeline savings, below the frozen 15% gate, plus one source-ref loss. See `2026-08-22-repeated-compaction.md`. |
| Content-typed context IR and content-addressed recovery | Adopt the portable contract; defer a general runtime | Agent Harness plus Context Density | RTK-like projection failed 0/6 before and after compaction; recovery degraded because successful outputs lacked raw refs. The source contract now requires typed capsules and complete recovery, without importing the BSL runtime. |
| Munder one-writer/atomic-log/breaker patterns | Future negative fixtures only | Agent Harness | The useful invariants do not justify importing the Electron runtime, hooks, PTY control, telemetry, or approval bypass. |

Wholesale RTK injection, command interception, tracking, raw-output tee,
telemetry, Loopy cloud/OAuth workers, Cursor continual-learning hooks, candidate
auto-commit/merge flows, and all candidate credential or approval-bypass paths
were rejected.

## Local Model Method

The valid campaign used:

- the direct loopback llama.cpp `/v1/chat/completions` endpoint;
- model alias `qwen3.8-local`, model revision
  `27af057ecb382ddfea5d12837360a8980560e3ed`, GGUF SHA-256
  `322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482`;
- stable llama.cpp runtime `b10430`, loopback only, batch 1;
- temperature `0.2`, top-p `0.95`, fixed seeds, 768 output-token cap;
- `chat_template_kwargs.enable_thinking=false` (the top-level form did not
  disable thinking in the invalid exploratory run);
- the same system prompt, case, rubric, model, endpoint, timeout, permissions,
  and no-tool policy for both arms;
- arm difference limited to the immutable candidate artifact;
- deterministic regex/group/forbidden/word-limit grading, with runtime errors
  quarantined instead of counted as artifact failures.

The first exploratory corpus was quarantined after the local server terminated
during long reasoning generations. A second corpus was invalidated because the
model-visible wrapper named the evaluation treatment. Neither corpus contributed
to the results below. The valid blind run did not expose arm labels, artifact
paths, rubrics, or expected answers to the model.

## Frozen Six-Candidate Campaign

Each row used two cases and three trials per arm unless noted. `Critical fails`
counts failed candidate trials in critical cases.

| Candidate | Wins | Losses | Ties | Critical fails | Prompt delta | Completion delta | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Skill completion contract | 0 | 0 | 2 | 6 | `+558` | `+394` | Reject |
| Debugging loop | 1 | 0 | 1 | 5 | `+1,866` | `+28` | Reject |
| SDD vertical slicing | 0 | 1 | 1 | 3 | `+762` | `-37` | Reject |
| Independent review lenses | 1 | 0 | 1 | 0 | `+774` | `-15` | Revise; compact rerun failed |
| UI finding proof gate | 1 | 0 | 2 | 3 | `+1,323` | `+97` | Reject current delta |
| Tool-output projection | 2 | 0 | 0 | 0 | `+1,014` | `-303` | Extend to five trials |

The compact revision campaign was also frozen before execution:

- compact review lenses: one win, one tie, two critical candidate failures;
- compact tool projection: one win, one loss, two critical candidate failures.

Both compact revisions failed promotion and were not substituted for the tested
artifact.

## Five-Trial Confirmation

> Historical, superseded evidence: the adversarial follow-up in
> `2026-08-21-tool-output-projection-adversarial.md` invalidated this section's
> promotion conclusion. Keep these numbers for provenance, but do not use the
> linked receipt's historical promotion conclusion as current authority.

The full tool-output projection artifact was extended to five trials per arm
without changing its text, prompts, rubrics, model, or sampler.

| Case | Baseline pass | Candidate pass | Baseline output | Candidate output | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| Noisy test failures | 2/5 | 5/5 | 1,338 | 925 | Win |
| Deduplicated security search | 3/5 | 5/5 | 1,108 | 997 | Win |
| Total | 5/10 | 10/10 | 2,446 | 1,922 | 2 wins, 0 losses |

The candidate reduced completion output by 524 tokens (21.4 percent) and had no
critical candidate failure. Its extra instruction increased prompt input by
1,690 tokens, so total isolated request tokens increased from 35,201 to 36,367
(3.3 percent). This proves better contract adherence and more concise projected
output for these fixtures, not end-to-end token savings. Conditional reference
loading avoids making that instruction a startup or unrelated-task tax; a
multi-step downstream-context benchmark is still required before claiming net
efficiency.

Immutable evidence identities:

- baseline artifact SHA-256:
  `287b888baa08fc741cf1ae61200d025834c1136772cda97a99be651dbb4a4484`;
- candidate artifact SHA-256:
  `7e0fe6fedd9caa20ffb9a33db91def74f9246627e80f58f92b638596428a86dd`;
- five-trial plan SHA-256:
  `cec24b617421d8fc2270a316722b72d59749b0b97db7ccb78c82671b4fb6f98e`;
- raw JSONL SHA-256:
  `3ece166bf6f87365e25022e812fe724a75c3fffe22f364931e5c6281621fd60d`;
- runner SHA-256:
  `b688aa1b02e618407dae0606c19806e742f8f52550d8d1a38dde7853724ea0b3`.

The historical receipt is
[`2026-08-21-tool-output-projection.json`](2026-08-21-tool-output-projection.json).
Its current superseding evidence is
[`2026-08-21-tool-output-projection-adversarial.md`](2026-08-21-tool-output-projection-adversarial.md).

## Source Changes Authorized By The Evidence

1. Correct the repository's stale Cursor distribution claims. Native Cursor
   packaging remains deferred until schema validation and live client discovery
   are both proved.
2. Add observer-effect and blinding requirements to Capability Evaluation.
3. Route oversized tool-output tasks from Context Density to a conditionally
   loaded fail-closed reference. Do not ask a model to count or group records;
   use the deterministic contiguous exact-duplicate helper or keep raw.
4. Separate concise presentation from persisted evidence. Require trajectory
   tests across repeated boundaries and complete-pipeline cost before adopting
   a context-reduction mechanism. The current decision record is
   [`2026-08-22-repeated-compaction.md`](2026-08-22-repeated-compaction.md).

No new plugin, background loop, native Cursor manifest, candidate runtime,
global install, cache refresh, commit, or publication is justified by this
evidence.
