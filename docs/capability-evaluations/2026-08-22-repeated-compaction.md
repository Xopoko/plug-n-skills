# Repeated-Compaction Context Evaluation, 2026-08-22

## Decision

Keep concise user-facing narration as a presentation choice, not as a memory
or reasoning optimization. Do not promote the frozen Caveman treatment as a
global context-efficiency default: it matched the natural baseline on task
success, but its full compacted pipeline saved only 7.43% cache-aware tokens
against the predeclared 15% gate and lost one set of source references.

Reject RTK-like semantic projection as a default. Its state loss happened
before compaction, and incomplete recovery then degraded across repeated
compactions and caused completed work to be repeated.

Apply these conservative native guardrails instead; this is not an efficiency
promotion for a new compaction or projection mechanism:

- concise presentation must not reduce reasoning/output allowance, tool
  evidence, durable typed state, or recovery coverage;
- compaction handoffs need a typed capsule with exact errors, completed-work
  receipts, rejected branches and reasons, authority, risks, source refs,
  recovery refs, and next action;
- projected successful and failed tool outputs both require content-addressed
  raw recovery; and
- any lossy context mechanism needs full-history and repeated-compaction
  behavioral proof plus complete-pipeline cost accounting before adoption.

## Scope And Method

The controlled campaign used two recursive task families, three predeclared
seeds (`1709`, `1901`, and `2027`), five arms, and three dependent compaction
boundaries (`C1 -> C2 -> C3`). It produced 30 controlled units and 234 valid
local-model calls with zero quarantines, truncations, or repairs.

The arms were:

- `natural_raw`: natural notes plus complete raw evidence;
- `caveman_raw`: the frozen Caveman response-style prompt plus complete raw
  evidence;
- `silent_raw`: no note-generation call plus complete raw evidence;
- `natural_rtk`: natural notes plus a deterministic source-derived RTK-like
  lossy projection; and
- `caveman_rtk`: the Caveman response style plus that projection.

The same persisted transcript policy was tested once with full history and
once after recursive Qwen compaction. The compactor emitted strict typed state
covering facts, constraints, completed work, rejected branches, risks, exact
details, source refs, recovery refs, and next action. Deterministic grading
separated projection loss, loss at each compaction boundary, and the interaction
where full history passed but the compacted trajectory failed.

The endpoint was the existing loopback-only `qwen3.8-local` llama.cpp route,
with thinking disabled, temperature `0.2`, top-p `0.95`, and fixed seeds. No
upstream candidate code, hook, proxy, wrapper, or provider optimizer was run.
The RTK-like arm was a frozen source-derived fixture, not RTK execution.

## Results

| Arm | Full-history task | After C1-C3 | Gold visible before C1 | C3 gold recall | Compact repeated work |
| --- | ---: | ---: | ---: | ---: | ---: |
| `natural_raw` | 6/6 | 5/6 | 100.00% | 100.00% | 0/6 |
| `caveman_raw` | 6/6 | 5/6 | 100.00% | 98.15% | 0/6 |
| `silent_raw` | 6/6 | 5/6 | 100.00% | 100.00% | 0/6 |
| `natural_rtk` | 0/6 | 0/6 | 25.93% | 29.01% | 6/6 |
| `caveman_rtk` | 0/6 | 0/6 | 25.93% | 26.54% | 6/6 |

Caveman-style notes were 36.54% shorter than natural notes and exposed 87.53%
of durable IDs versus 67.41% for natural notes. The task outcome was identical:
6/6 with full history and 5/6 after compaction, with no Caveman-only task loss.
At C3 it retained every required fact, constraint, completed action, rejected
branch, risk, exact detail, and next action. It retained 92.86% of required
source refs versus 100% for natural notes because one unit omitted three refs.

The compacted Caveman pipeline used 44,711 cache-aware tokens versus 48,300 for
natural notes, a 7.43% reduction. Its visible transcript was only 1.36% shorter.
This did not meet the predeclared 15% full-pipeline efficiency gate.

The no-narration arm also matched natural task success, but it removes note
generation entirely and therefore measures an upper bound, not a deployable
policy. It does not prove that durable work notes are unnecessary.

The RTK-like projection exposed only 25.93% of required state and failed all
six tasks even before compaction. Recovery raised effective recall to 100% at
C1 but only 70.37% at C3 because later successful projections lacked raw
recovery refs. All six compacted units requested valid recovery, none recovered
the task, and all repeated a completed action.

## Causal Reading

The one compacted failure shared by all raw-evidence arms was not caused by
Caveman narration or missing evidence. The compactor introduced an unsupported
extra constraint, `K03`, despite retaining the required atoms. That same false
atom appeared under natural, Caveman, and silent narration. The policy must
therefore test false-atom introduction as well as recall.

The RTK-like failure had the opposite cause: unique state was absent before
compaction. Later compaction could not reconstruct it, and failure-first
recovery was insufficient because successful outputs also carried
decision-critical provenance and completion evidence.

## Source Outcome

- Context Density now separates presentation brevity from persisted evidence,
  defines a durable compaction capsule, requires recovery for successful and
  failed projections, and adds a repeated-compaction adoption gate.
- Capability Evaluation now requires trajectory-level tests and complete
  pipeline accounting for artifacts that affect verbosity, persistence,
  projection, compaction, or recovery.
- The deterministic exact-duplicate projector remains the only retained
  reduction helper. Its projected output is explicitly non-standalone, marks
  `raw_recovery_required=true`, and remains `revise` for repeated-boundary use.

No candidate runtime, global install, cache refresh, agent configuration,
commit, or publication is authorized by this report.

## Evidence Identity

- combined summary SHA-256:
  `a3f1e7dfef057f7e2ab79fac8a53a7b5d49e913f78fec4f8333c1e338dc4ac02`;
- human-readable result SHA-256:
  `97ac480b342eed3f116b88ea83c9bc931f290bfee1b344f98c3dd50b2e62a4fa`;
- analyzer SHA-256:
  `4e383e859dd2dd2231c7c57bf9a861b6a4b5f629ac87207f2705a7147f055bbb`;
- benchmark runner SHA-256:
  `c3811f21001a1554ba484105887408ca2b72c9c5aa789ab77eebf3297d2de3b3`;
- Caveman commit/tree:
  `2f49f0e1a352aa810e70056b7930aeb0b3d219b4` /
  `603ece15f092a82703cb6e86d102050502775f25`;
- RTK commit/tree:
  `29f9bb7161775cd807565fd3041eb2b7d1be071c` /
  `deedf05df34a2e415a6cdc468ec8ae5d41c96276`.

The full model-visible inputs, outputs, usage, schemas, and component-run
identities remain in the ignored evaluation workspace. This tracked report is
the portable decision record, not a replacement for the raw receipts.

## Limits

- Two task families and three seeds are a strong local discriminator, not a
  universal benchmark.
- The compactions were controlled Qwen simulations, not native Codex
  compaction.
- The evidence covers one model, quantization, runtime, and synthetic corpus.
- The frozen Caveman treatment covered response style only; SDK compaction,
  provider wrapping, proxying, and hidden-reasoning changes were excluded.
- The RTK-like fixture intentionally represented lossy failure-first projection;
  it does not claim that every possible RTK command or configuration behaves
  identically.
