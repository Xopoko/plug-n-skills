# Compression Pipeline

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

<!-- cda:allow commitment_loss_risk,compression_without_relevance_check -->
Orchestrated behavior-preserving compression for batches of prompt-bearing
files (skill bodies, command templates, agent rules). One agent compressing
its own work cannot be trusted to notice what it dropped; this pipeline
splits the roles and only accepts a file when a fresh adversary finds
nothing.

## Shape

Per file, as an independent pipeline (no barrier between files):

<!-- cda:allow compression_without_relevance_check -->
1. **Compress** — one agent rewrites the file in place under the hard
   contract below, then self-checks with the deterministic checker until it
   prints PASS.
2. **Verify** — two parallel checks: the deterministic checker (machine
   invariants) and an adversarial semantic refuter (rules, steps,
   conditions, modality).
3. **Repair** — only on violations: a repair agent restores the flagged
   <!-- cda:allow commitment_loss_risk,compression_without_relevance_check -->
   content from the original, keeping the rest of the compression, and
   re-runs the checker to PASS.
4. **Re-refute** — a repair invalidates every earlier semantic verdict. A
   FRESH refuter (not the one that found the violations) must return clean;
   loop repair/re-refute until it does.

Deterministic half:

```bash
python3 "$PLUGIN_ROOT/skills/context-density/scripts/compression_invariants.py" <original> <compressed> --json
```

Validate the checker itself once per batch with a tamper test: corrupt one
protected token in a known-good output and confirm the checker fails.

## Compress contract (give verbatim to the compressing agent)

Hard rules — violation makes the output unusable:

1. The frontmatter block must be byte-identical to the original.
2. Preserve verbatim: every fenced block containing commands or literal
   output templates; all file paths; all placeholder tokens of any form
   ($VARS, {curly}, __DUNDER__, [BRACKETED]); machine-consumed output
   markers (ALLCAPS: lines).
3. Preserve the semantics of every numbered step and every
   MUST/NEVER/"do not" rule — shorten wording, never drop a rule, reorder
   steps, weaken a constraint, or change modality (should/must).
4. Keep one rule per bullet. Never collapse a rule list into a multi-clause
   <!-- cda:allow compression_without_relevance_check -->
   sentence — structure survives compression nearly free, and collapsed
   rules are the first thing reviewers reject.
5. Multi-example lists: keep the single most informative example per
   concept; a concept whose every example was dropped is a violation.
6. Never change list delimiters. Joining comma-separated items with "/"
   re-segments compound terms that already contain that character
   (Kotlin/Native, expect/actual, TLS/certificate pinning) and silently
   rewrites trigger and scope lists.
7. Do not add new instructions, opinions, or commentary.

<!-- cda:allow commitment_loss_risk,compression_without_relevance_check -->
Compress: boilerplate prose, rationale text, redundant restatements,
verbose transitions, surplus examples, self-evident header explanations.
Set a target (25-35% on prose-heavy files) but instruct the agent to stop
where the hard rules force it to stop and report the real number —
rule-dense files honestly yield 16-29%, and corpora already authored
telegraphically yield only 2-9% with a violation rate that usually is not
worth it. Run the audit's break-even gate first and skip files whose
compressible prose mass cannot pay for the pipeline.

## Refute contract (give verbatim to the reviewing agent)

Mission: REFUTE the claim that the compressed file preserves full
semantics. Hunt for dropped or weakened steps, rules, conditions,
thresholds, hedges, and escalation paths; altered literal templates or
placeholders; frontmatter changes; invented instructions; modality
changes; quantifier inversions ("any X unsupported" vs "unsupported by
any X"); compound terms re-segmented by delimiter changes; concepts
whose every example was dropped; contamination from any reference
material used as an editorial guide. Dropped examples are
acceptable only if another example of the same concept survives. Be
strict: uncertainty counts as a violation. Return structured
`{pass, violations[]}` — never prose.

## Workflow skeleton

```js
const results = await pipeline(FILES,
  f => agent(compressPrompt(f), {schema: STATS}),
  async (prev, f) => {
    const [inv, sem] = await parallel([
      () => agent(`Run the invariant checker on ${f}; pass=true only on PASS.`, {schema: VERDICT}),
      () => agent(refutePrompt(f), {schema: VERDICT}),
    ])
    return {...prev, ok: inv?.pass && sem?.pass,
            violations: [...(inv?.violations ?? []), ...(sem?.violations ?? [])]}
  },
  async (prev, f) => {
    if (prev.ok) return prev
    await agent(repairPrompt(f, prev.violations), {schema: REPAIR})
    const fresh = await agent(refutePrompt(f), {schema: VERDICT})  // re-refute
    return {...prev, ok: fresh?.pass, violations: fresh?.violations ?? []}
  })
```

Expect repairs: in a calibration run over nine rule-dense command templates,
five failed first-round refutation (dropped "do not" rules, weakened MUST
scoping, a should-to-must inversion), and a second refutation round after
repair caught five more residual losses. Files that pass first try are the
minority, not the norm.

## Acceptance and reporting

- A file is done only when the deterministic checker passes AND the latest
  fresh refuter returns clean.
- Report per file and total: chars/tokens before and after, violations
  found and restored, and the token cost of restorations (restored
  commitments routinely cost back 1-3% — report it, do not hide it).
- Then apply the standard economics gate from the skill: input-token
  reduction alone is not success; validate the consumer task end to end
  (render, lint, or a dogfood run) before claiming the batch done.
