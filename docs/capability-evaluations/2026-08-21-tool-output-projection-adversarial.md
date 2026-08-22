# Adversarial Tool-Output Projection Evaluation, 2026-08-21

## Current Decision

Reject model-generated tool-output projection as a general compression path.
Retain raw evidence for risky or non-reducing surfaces. Keep only the bundled
deterministic contiguous exact-line reducer as a narrow, opt-in source
capability behind a fail-closed caller gate. Its immediate downstream result is
`revise`, not a global or repeated-compaction adoption: it must keep raw when
classification or recovery is unsafe, and current trajectory coverage is still
inconclusive.

This report supersedes the promotion conclusion in
`2026-08-21-tool-output-projection.json`. That earlier two-case receipt remains
historical evidence, but its original promotion conclusion is not current: it
did not test later decisions, unknown future questions, malformed recovery,
alternative branches, provenance, Git status, authority/effect boundaries, or
cumulative pipeline cost.

No upstream RTK, Caveman, or other candidate runtime was installed or executed.
The only executable source added by this evaluation was the native deterministic
helper written and tested in this repository.

The current structured policy record is
[`2026-08-22-deterministic-projection-policy.json`](2026-08-22-deterministic-projection-policy.json).
It is valid but intentionally `blocked` / `inconclusive`: the immediate tests
below do not substitute for the required two-boundary persistence campaign.

## Environment And Identity

- model: `qwen3.8-local`;
- endpoint: loopback-only `127.0.0.1:18080/v1/chat/completions`;
- model revision: `Qwen3.8-27B-UD-Q4_K_M@27af057ecb382ddfea5d12837360a8980560e3ed`;
- GGUF SHA-256: `322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482`;
- runtime: llama.cpp `b10430`, batch 1, thinking disabled;
- sampler: temperature `0.2`, top-p `0.95`, five fixed seeds;
- final held-out runner SHA-256:
  `796041f9e0c2e6c4ae3df59e1b3d952b10543e94383c6f8f633e6ba6c0c70197`;
- final held-out plan SHA-256:
  `9f0d7ac79386ab5ea7be55ef9c1cf2fc4dc9924aa1df1f2d3cbddabd51d11f86`;
- old-reference candidate SHA-256:
  `3a9fb5074fd2de8d4c396b51dc7b6ca39d1b594123278dee74beb832494a4b8a`;
- repaired-routing candidate SHA-256:
  `0276569fdf516d20a2076b4578931586982ed43a6b6b460afc56e340d4a8ee9a`;
- current reference SHA-256:
  `3f34336d29e59bac5d0c0e5c951800bd771f263fbd96245309cf960c428f5dbe`;
- deterministic projector SHA-256:
  `cd1f5304e56c024a763428e142f2a79c0e247fbb62b15b7f9f24e4927fd68688`;
- fail-closed policy runner SHA-256:
  `2e27ac04d469fe82c1fb18b4f12491de41aefdba08b21c61661b0628d92be39c`;
- deterministic-policy raw JSONL SHA-256:
  `9c27f69b50f5daea2ec5e4f4d4482a993fc703613fbe354c692aea20766940fd`;
- deterministic-policy summary SHA-256:
  `480449a1218792d89f6766873421dc3aff5cc48383cdd9b61807a63babecd3cf`.

The projection call never saw the frozen downstream questions. Raw and
candidate downstream arms used the same model, question, seed, sampler, and
rubric. Runs were counterbalanced. Runtime failures were quarantined rather
than scored as candidate failures. A 45/45 raw-control gate was required before
the held-out result was accepted.

## Threat Corpus

The final held-out corpus contained nine critical cases with five trials each:

1. two Git rename states plus a modified deployment file;
2. approval scope versus planned, executed, and not-executed effects;
3. causal order and failed rollback supersession;
4. malformed and truncated structured output;
5. independent debugging branches and negative evidence;
6. a rare singleton inside two large exact-duplicate runs;
7. unique records with an unknown future question;
8. an unavailable raw resolver;
9. source/build/deployment provenance disagreement.

The broader preceding campaign covered 20 cases and 100 trial units. Its
automatic regex grader reported 18 projection losses. Independent review found
that this headline was mostly wrong: no decisive hidden fact or alternative
branch was absent in those 18 units, but one projection lost its recovery
pointer, one downstream response was truncated, duplicate arithmetic was often
wrong, and dangling/wrong-digest recovery was never actually exercised. This
is why the final held-out campaign used a clean 45/45 raw control plus manual
adjudication instead of trusting the regex headline.

## Final Held-Out Before And After

| Measure | Old model projection | Repaired model routing |
| --- | ---: | ---: |
| Trial units | 45 | 45 |
| Raw-control passes | 45 | 45 |
| Valid `keep_raw` decisions | 0 | 44 |
| Automated downstream passes | 24 | 45 |
| Manually confirmed downstream decision losses | 2 | 0 |
| Manually confirmed latent factual corruptions | 10 | 1 |
| Decision or context losses | 12 (26.7%) | 1 (2.2%) |
| Safe abstentions | 18 | 0 |
| Invalid recovery strings | 18 | 0 |
| Downstream false certainty | 0 | 0 |

The repair reduced observed decision/context losses by 11/12, or 91.7%, and
removed both observed downstream decision losses. It did so mostly by refusing
lossy work: 44/45 trials retained raw evidence. The only model-generated
projection confidently reported 300 source records where the fixture contained
400 duplicate retry records plus two other records. Its narrow downstream
question did not expose that corruption. Therefore repaired model routing alone
still has verdict `revise`, not `adopt`.

Manual review of the old arm found two Git task losses, ten confident duplicate
count corruptions hidden by narrow downstream questions, eighteen safe but
unusable recovery attempts, five unknown-future routing failures without an
observed frozen-question loss, and one grader false positive. No old-arm answer
authorized a dangerous action or invented a common root cause; safe abstention
prevented false certainty but did not complete the task.

## Why LLM Preprocessing Was Rejected

In the 100-unit broad campaign, a projected downstream prompt was 68.97%
smaller than raw, but the projection call itself dominated the pipeline:

| Pipeline | Total tokens | Elapsed |
| --- | ---: | ---: |
| Raw downstream | 104,535 | 165.527 s |
| Projection plus projected downstream and all recovery | 481,982 | 844.159 s |

The complete model-projection pipeline used 4.611 times the tokens and 5.100
times the elapsed time of raw. Projection preprocessing alone consumed 445,127
tokens. The apparent downstream saving was also cache-sensitive: an optimistic
uncached-prompt-plus-completion proxy reduced the downstream saving to 13.36%.
Shorter downstream context is not evidence of end-to-end efficiency when a
second model call creates it.

## Deterministic Policy Result

The final policy removes the model from counting and grouping. The caller runs
`exact_duplicate_projection.py` on pre-redacted UTF-8 line-record output. The
helper run-length-encodes only contiguous exact duplicates, preserves every
unique record and run position, computes counts and digests in code, and emits
`keep_raw` when there is no smaller result.

Across all nine held-out cases:

| Measure | Raw control | Deterministic policy |
| --- | ---: | ---: |
| Qwen downstream passes | 45/45 | 45/45 |
| Evidence bytes | 23,679 | 6,610 |
| Prompt tokens | 45,265 | 14,660 |
| Prompt plus completion tokens | 46,252 | 15,647 |
| Elapsed | 39.889 s | 38.873 s |

The fail-closed caller kept raw for eight cases and projected only the safe
exact-duplicate-heavy case. In particular, it overrode the helper's smaller
projection for the dangling-resolver fixture. It reduced evidence bytes by
72.085%, prompt tokens by 67.613%, and total downstream tokens by 66.170%; wall
time fell only 2.547%, so this is not a meaningful latency win. It retained
45/45 parity with zero quarantines. Deterministic preprocessing for all nine
inputs took 0.245 ms and required no model call.

Forty candidate trials were byte-identical `keep_raw` routes and therefore
reused frozen raw-control receipts only after verifying case key, seed, input
hash, quarantine state, and rubric pass. The five materially changed projection
trials were executed again against the final reference and helper hashes. Input
identities were captured before execution and rechecked before the receipt was
written, preventing a mid-run edit from rebinding old rows to new source.

A separate count-sensitive fixture reduced 17,731 bytes to 676 bytes (96.187%)
while raw and projected Qwen arms both passed 5/5. Prompt tokens fell from
32,615 to 2,070 and total tokens from 32,841 to 2,260. This rerun used the same
final projector hash; its runner, raw JSONL, and summary hashes are respectively
`beb2a428ba87ab3ec5f013bdf678668483bcd3919d2dfa5617d58b301fac7bca`,
`3070339c981b82ac25da0d8974c6a209ec44b9cb3552079b300c423dd19034c9`,
and `f63b1f956f4af968146805ba71137476fe6b803392376b4c013e1fd58dfc2f57`.
It directly exercises the count fields that stochastic projections corrupted.

## Source Outcome

- `references/tool-output-projection.md` now makes projection conditional,
  routes risky evidence to raw, defines typed recovery integrity, requires
  pre-model redaction, and forbids end-to-end savings claims from a shorter
  downstream prompt alone.
- `scripts/exact_duplicate_projection.py` implements the only retained reducer;
  it is not a general compaction policy or a repeated-boundary adoption.
- focused tests cover exact arithmetic, unique-record/order preservation,
  never-larger fallback, non-UTF-8 fallback, and raw identity validation.
- the Context Density router and command table expose the reference and helper
  only on demand.

## Limits And Residual Risk

- The behavioral evidence uses one local model, quantization, and synthetic
  corpus. It does not prove behavior for every model or real repository.
- The helper supports only trusted UTF-8 line-record boundaries and contiguous
  exact duplicates. It is not a generic log parser, semantic summarizer, secret
  scrubber, persistence layer, or recovery resolver.
- Exact-byte, formatting-sensitive, malformed, authority, provenance, and other
  risky surfaces still default to raw. The caller owns that classification.
- The deterministic policy reused the already frozen 45/45 raw-control records;
  it verified key set, seed, input hash, quarantine state, and rubric pass before
  comparison.
- The corrected deterministic campaign measures immediate downstream behavior,
  not multiple dependent compactions. The current policy therefore remains
  `revise` until a validated structured trajectory receipt covers state,
  provenance, successful and failed recovery, repeated work, false certainty,
  authority, and full-pipeline cost.
- No global Codex, Claude, or Cursor install was refreshed. No production tool
  hook or automatic dispatcher was activated.
