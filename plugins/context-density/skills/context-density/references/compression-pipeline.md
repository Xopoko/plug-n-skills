# Compression Pipeline

`$PLUGIN_ROOT` is the plugin root (see the calling skill's plugin-root preamble).

<!-- cda:allow commitment_loss_risk,compression_without_relevance_check -->
Orchestrated behavior-preserving compression for batches of prompt-bearing
files (skill bodies, command templates, agent rules). One agent compressing
its own work cannot be trusted to notice what it dropped; this pipeline
splits the roles and only accepts a file when a fresh adversary finds
nothing.

## Scope and target selection

When the request names a repository or a doc tree rather than explicit
<!-- cda:allow token_only_metric,compression_without_relevance_check -->
files ("reduce tokens in this repo", "compress the docs"), select targets
before compressing anything:

1. Enumerate prompt-bearing text (*.md and agent instruction files), then
   classify by load path:
   - hot — agent instruction files (AGENTS.md, CLAUDE.md, rules files,
     <!-- cda:allow token_only_metric,compression_without_relevance_check -->
     prompt templates): compress first; they cost tokens every session.
   - reference — guides, runbooks, docs/ trees: payoff only when read.
   - evidence/legal — changelogs, ADRs, release notes, migration
     histories, LICENSE/NOTICE, generated files: EXCLUDE. These are
     records and legal text, not compressible prose.
2. Pilot one representative file per group (pilot-first rule below) and
   skip groups under the yield bar; report exclusions and skips.
3. In a repository you do not own outright, work on a fresh branch and do
   not push unless asked; state the branch and commit status explicitly.
4. Consumer validation for documentation: every relative link in a
   compressed file must still resolve, and document structure agents
   navigate by (headings, anchors) must survive.

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
5. **Cap the loop** — at most 3 repair rounds per file. A file that cannot
   converge is REVERTED to the original and reported; never force-accept,
   never loop forever. Reverting is a safe outcome, not a failure.

Deterministic half:

```bash
python3 "$PLUGIN_ROOT/skills/context-density/scripts/compression_invariants.py" <original> <compressed> --json
```

Validate the checker itself once per batch with a tamper test: corrupt one
protected token in a known-good output and confirm the checker fails.

The checker also emits non-blocking WARNINGS (lost numbers, drops in
modality/quantifier word counts) — hand them to the semantic reviewer as
attention pointers. The wordlist is English by default; pass
`--modality-words` for corpora in other languages.

## Reviewer qualification (once per batch, before verdicts count)

Executing agents differ in model strength and language; a reviewer's
"CLEAN" is only evidence if the reviewer demonstrably catches violations.
Qualify each reviewer role on a planted exam built from a real batch file:

```bash
python3 "$PLUGIN_ROOT/skills/context-density/scripts/refuter_calibration.py" plant <original> --exam exam.md --key key.json
python3 "$PLUGIN_ROOT/skills/context-density/scripts/refuter_calibration.py" grade key.json verdict.json
```

Give the reviewer exam.md as if it were a compressed candidate; grade its
JSON verdict against the key (pass = catches at least 4 of 5 blatant,
language-neutral plants; grading is lenient by line window and clue text).
A reviewer that fails the exam disqualifies the RUN — stop and report that
semantic verification is unavailable on this host, rather than shipping
<!-- cda:allow compression_without_relevance_check -->
unreviewed compression. Do not make the exam harder than the default: it
exists to catch negligent reviewers, not to demand your own strength.

## Compress contract (give verbatim to the compressing agent)

Hard rules — violation makes the output unusable:

1. The frontmatter block must be byte-identical to the original (applies
   only to files that have one).
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
telegraphically yield only 1-9% with a violation rate that is not worth
it. Prose-mass heuristics overestimate on commitment-dense writing: long
sentences full of rules compress like bullets, not like boilerplate.

Pilot before batch: run ONE representative file through the full
pipeline first. If its post-restoration yield lands under 10%, abort the
batch and report the corpus as already dense — that result is a success
of the gate, not a failure of the run.

## Refute contract (give verbatim to the reviewing agent)

Work from the diff, not from memory: you receive the original, the
compressed candidate, the unified diff between them, and the checker's
warnings. Adjudicate EVERY diff hunk — for each one answer "meaning
preserved" or report a violation; a hunk you cannot confidently clear
counts as a violation. Hunt for dropped or weakened steps, rules,
conditions, thresholds, hedges, and escalation paths; altered literal
templates or placeholders; frontmatter changes; invented instructions;
modality changes; quantifier inversions ("any X unsupported" vs
"unsupported by any X"); compound terms re-segmented by delimiter
changes; concepts whose every example was dropped; contamination from any
reference material used as an editorial guide. Dropped examples are
acceptable only if another example of the same concept survives. Return
structured `{pass, violations[]}` with line numbers — never prose.

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
    let violations = prev.violations
    for (let round = 1; round <= 3; round++) {          // capped repair loop
      await agent(repairPrompt(f, violations), {schema: REPAIR})
      const fresh = await agent(refutePrompt(f), {schema: VERDICT})  // re-refute
      if (fresh?.pass) return {...prev, ok: true, rounds: round}
      violations = fresh?.violations ?? []
    }
    await agent(`Revert ${f} to the original; it did not converge.`, {schema: REPAIR})
    return {...prev, ok: false, reverted: true, violations}
  })
```

(Before this pipeline: tamper-test the checker and run the reviewer
qualification exam; both are single agents plus the calibration script.)

Expect repairs: in a calibration run over nine rule-dense command templates,
five failed first-round refutation (dropped "do not" rules, weakened MUST
scoping, a should-to-must inversion), and a second refutation round after
repair caught five more residual losses. Files that pass first try are the
minority, not the norm.

## Weaker executors and single-agent hosts

The pipeline must degrade safely, not silently. The fallback ladder:

1. Full multi-agent host: run the pipeline as specified.
2. Limited fan-out: keep ONE qualified reviewer and feed it files
   sequentially — coverage of every file beats parallelism. Never skip
   reviews to save agents.
3. No subagents at all: run the deterministic checker and warnings, but do
   NOT claim semantic verification — mark the output "deterministic-only,
   requires external semantic review" and leave it uncommitted, or revert.
4. Reviewer fails the qualification exam: same as 3 — the run downgrades;
   files never ship on an unqualified "CLEAN".

Language robustness: planted exam violations are language-neutral
(structure and numbers, not English words); checker wordlists are
configurable; all role outputs are structured JSON, which works the same
in any conversation language. Contracts may be translated, but the
literal output templates and token names must stay verbatim. Lexical
wordlist warnings are hints, never decisions: blocking checks use only
language-independent structure, semantics belongs to the reviewer, and
when the wordlist matches nothing in a substantial corpus the checker
says so out loud (`wordlist-no-coverage`) instead of staying silently
inert.

## Cross-file duplication pass (before per-file compression)

<!-- cda:allow commitment_loss_risk,compression_without_relevance_check -->
Per-file editorial compression misses the largest win in template-style
corpora: identical boilerplate repeated across files. Before compressing,
run the audit over the whole batch and read `duplication_clusters`:

```bash
python3 "$PLUGIN_ROOT/skills/context-density/scripts/context_density_audit.py" <batch-dir> --json --top 20
```

High-mass clusters are extraction candidates (shared reference loaded
conditionally), which is a STRUCTURAL change: route it as its own
reviewed change with consumer validation, never fold it silently into
the compression batch. Never mechanically merge safety text, consent
wording, or deliberate router pointers.

## Opt-in modes (never run these by default)

- **Trigger-surface compression**: frontmatter descriptions are routing
  commitments and stay byte-identical in the normal pipeline. Compressing
  them is a separate, explicitly requested mode that additionally requires
  description-overlap measurement before and after, and trigger-metadata
  tests asserting discriminating terms per skill. Without those guards,
  do not touch descriptions.
- **Behavioral smoke validation**: for high-stakes corpora, run 2-3
  representative consumer tasks against original and compressed versions
  and compare outcomes; this is the only direct test of the economics
  rule's "task success" clause.

## Acceptance and reporting

- A file is done only when the deterministic checker passes AND the latest
  fresh, exam-qualified refuter returns clean.
- A file that hit the repair cap is reverted and listed as such.
- Report per file and total: chars/tokens before and after, violations
  found and restored, and the token cost of restorations (restored
  commitments routinely cost back 1-3% — report it, do not hide it).
- Then apply the standard economics gate from the skill: input-token
  reduction alone is not success; validate the consumer task end to end
  (render, lint, or a dogfood run) before claiming the batch done.
