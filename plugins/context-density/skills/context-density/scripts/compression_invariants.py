#!/usr/bin/env python3
"""Deterministic invariant check for behavior-preserving compression.

Compares a compressed text artifact against its original and fails when
machine-checkable commitments were lost. Derives the invariants from the
original automatically, with no hand-authored ledger required:

  frontmatter   first ``---`` block must be byte-identical (markdown files)
  fenced        every fenced code block (``` or ~~~, indent <= 4) must
                appear verbatim; unclosed fences extend to end of file
  spans         every inline ``code span`` must survive
  tokens        placeholder inventories must not shrink:
                $VARS, {curly_tokens}, __DUNDER__, [BRACKETED PLACEHOLDERS],
                ALLCAPS: output markers

Besides blocking violations, the check emits non-blocking WARNINGS that
direct the semantic review's attention (never the exit code): numeric
literals lost from prose, and count drops of modality/quantifier words.
The default wordlist is English; pass ``--modality-words`` with a
comma-separated list for other languages.

Notes: a compressed file larger than the original is reported with a
negative reduction but does not fail (size is not an invariant);
``--ignore-span`` suppresses only the span finding, not token-inventory
findings derived from the same text.

This is the deterministic half of the compression pipeline
(references/compression-pipeline.md); semantic rule preservation needs the
adversarial review half on top.

Usage:
  compression_invariants.py ORIGINAL COMPRESSED [--json] [--no-frontmatter]
      [--ignore-span LITERAL]... [--ignore-fenced-prefix LINE_PREFIX]...

Exit codes: 0 = all invariants hold, 1 = violations, 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "context_density.compression_invariants.v1"

FRONTMATTER_RE = re.compile(r"^(---\n.*?\n---\n)", re.S)
FENCE_LINE_RE = re.compile(r"^( {0,4})(```|~~~)(.*)$")
SPAN_RE = re.compile(r"`([^`\n]+)`")
TOKEN_PATTERNS = (
    ("dollar-var", re.compile(r"\$[A-Z][A-Z0-9_]+")),
    ("curly-token", re.compile(r"\{[a-z][a-z0-9_]*\}")),
    ("dunder-token", re.compile(r"__[A-Z][A-Z0-9_]+__")),
    ("bracket-placeholder", re.compile(r"\[[A-Z][A-Z0-9 _-]{2,}\]")),
    ("output-marker", re.compile(r"^[ \t]*[A-Z][A-Z_]{3,}:", re.M)),
)

NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?%?")
MODALITY_WORDS = ("must", "never", "always", "only", "unless", "should",
                  "may", "cannot", "do not")
QUANTIFIER_WORDS = ("any", "all", "every", "each", "none")
MAX_WARNINGS_PER_KIND = 10


def prose_only(text: str) -> str:
    """Text with fenced blocks and inline code spans removed."""
    out = text
    for block in fenced_blocks(text):
        out = out.replace(block, "", 1)
    return SPAN_RE.sub("", out)


def word_count(text: str, word: str) -> int:
    return len(re.findall(r"(?<!\w)" + re.escape(word) + r"(?!\w)",
                          text, re.IGNORECASE))


WORDLIST_COVERAGE_MIN_PROSE = 400


def collect_warnings(original: str, compressed: str,
                     modality_words: tuple[str, ...]) -> list[dict]:
    warnings: list[dict] = []
    orig_prose, comp_prose = prose_only(original), prose_only(compressed)

    lost_numbers = sorted(set(NUMBER_RE.findall(orig_prose))
                          - set(NUMBER_RE.findall(comp_prose)))
    for number in lost_numbers[:MAX_WARNINGS_PER_KIND]:
        warnings.append({"kind": "number-lost",
                         "detail": f"numeric literal lost from prose: {number}"})

    wordlist_hits = 0
    for group, words in (("modality", modality_words),
                         ("quantifier", QUANTIFIER_WORDS)):
        for word in words:
            before, after = word_count(orig_prose, word), word_count(comp_prose, word)
            wordlist_hits += before
            if after < before:
                warnings.append({"kind": f"{group}-drop",
                                 "detail": f"'{word}' count {before} -> {after}"})

    # Loud degradation: zero hits on substantial prose means the wordlist
    # does not cover the corpus language and these detectors are inert.
    if wordlist_hits == 0 and len(orig_prose.strip()) >= WORDLIST_COVERAGE_MIN_PROSE:
        warnings.append({
            "kind": "wordlist-no-coverage",
            "detail": "modality/quantifier wordlists matched nothing in the "
                      "original; the corpus language is likely not covered - "
                      "these hints are INACTIVE for this file. Pass "
                      "--modality-words for the corpus language; semantic "
                      "review remains the language-independent guard."})
    return warnings


def frontmatter(text: str) -> str:
    match = FRONTMATTER_RE.match(text)
    return match.group(1) if match else ""


def fenced_blocks(text: str) -> list[str]:
    """Linear line-based fence scanner.

    Pairs an opener with the next bare fence of the same marker at the same
    or shallower indent; a deeper-indented nested fence stays inside its
    outer block instead of closing it. An unclosed opener extends to end of
    file, which keeps its content protected. Scan ranges never overlap, so
    the pass is linear even on pathological inputs.
    """
    lines = text.split("\n")
    blocks: list[str] = []
    index, total = 0, len(lines)
    while index < total:
        opener = FENCE_LINE_RE.match(lines[index])
        if not opener:
            index += 1
            continue
        indent, marker = opener.group(1), opener.group(2)
        close = None
        for j in range(index + 1, total):
            candidate = FENCE_LINE_RE.match(lines[j])
            if candidate and candidate.group(2) == marker \
                    and not candidate.group(3).strip() \
                    and len(candidate.group(1)) <= len(indent):
                close = j
                break
        if close is None:
            close = total - 1
        blocks.append("\n".join(lines[index:close + 1]))
        index = close + 1
    return blocks


def code_spans(text: str) -> set[str]:
    without_fences = text
    for block in fenced_blocks(text):
        without_fences = without_fences.replace(block, "", 1)
    return set(SPAN_RE.findall(without_fences))


def check(original: str, compressed: str, *, frontmatter_check: bool,
          ignore_spans: set[str], ignore_fenced_prefixes: list[str],
          modality_words: tuple[str, ...] = MODALITY_WORDS) -> dict:
    violations: list[dict] = []

    if frontmatter_check:
        orig_fm = frontmatter(original)
        if orig_fm and frontmatter(compressed) != orig_fm:
            violations.append({"kind": "frontmatter",
                               "detail": "frontmatter block is not byte-identical"})

    needed: dict[str, int] = {}
    for block in fenced_blocks(original):
        needed[block] = needed.get(block, 0) + 1
    for block, count in needed.items():
        found = compressed.count(block)
        if found >= count:
            continue
        first_line = block.splitlines()[1][:80] if len(block.splitlines()) > 1 else ""
        if any(first_line.startswith(p) for p in ignore_fenced_prefixes):
            continue
        violations.append({"kind": "fenced",
                           "detail": f"fenced block not verbatim "
                                     f"(needs {count}, found {found}): {first_line!r}"})

    missing_spans = code_spans(original) - code_spans(compressed) - ignore_spans
    for span in sorted(missing_spans):
        violations.append({"kind": "span", "detail": f"inline code span lost: `{span}`"})

    for kind, pattern in TOKEN_PATTERNS:
        lost = set(pattern.findall(original)) - set(pattern.findall(compressed))
        for token in sorted(lost):
            violations.append({"kind": kind, "detail": f"token lost: {token.strip()}"})

    return {
        "schema": SCHEMA,
        "original_chars": len(original),
        "compressed_chars": len(compressed),
        "reduction_pct": round((1 - len(compressed) / len(original)) * 100, 1)
        if original else 0.0,
        "violations": violations,
        "warnings": collect_warnings(original, compressed, modality_words),
        "passed": not violations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic invariant check for compressed text artifacts.")
    parser.add_argument("original")
    parser.add_argument("compressed")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--no-frontmatter", action="store_true",
                        help="skip the frontmatter byte-identity check")
    parser.add_argument("--ignore-span", action="append", default=[],
                        metavar="LITERAL",
                        help="inline code span allowed to disappear (repeatable)")
    parser.add_argument("--ignore-fenced-prefix", action="append", default=[],
                        metavar="LINE_PREFIX",
                        help="fenced blocks whose first content line starts with "
                             "this prefix may be dropped (repeatable)")
    parser.add_argument("--modality-words", default=None, metavar="W1,W2,...",
                        help="comma-separated modality wordlist for warnings "
                             "(default: English; set for other languages)")
    args = parser.parse_args(argv)

    try:
        original = Path(args.original).read_text(encoding="utf-8")
        compressed = Path(args.compressed).read_text(encoding="utf-8")
    except (OSError, ValueError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2

    modality = (tuple(w.strip() for w in args.modality_words.split(",") if w.strip())
                if args.modality_words else MODALITY_WORDS)
    result = check(original, compressed,
                   frontmatter_check=not args.no_frontmatter,
                   ignore_spans=set(args.ignore_span),
                   ignore_fenced_prefixes=args.ignore_fenced_prefix,
                   modality_words=modality)
    result["original"] = args.original
    result["compressed"] = args.compressed

    if args.as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{args.original}: chars {result['original_chars']} -> "
              f"{result['compressed_chars']} ({result['reduction_pct']}%)")
        if result["violations"]:
            print("VIOLATIONS:")
            for violation in result["violations"]:
                print(f"  - [{violation['kind']}] {violation['detail']}")
        else:
            print("INVARIANTS: PASS")
        if result["warnings"]:
            print("WARNINGS (review attention, non-blocking):")
            for warning in result["warnings"]:
                print(f"  - [{warning['kind']}] {warning['detail']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
