#!/usr/bin/env python3
"""Qualification exam for semantic compression reviewers.

A reviewer's "CLEAN" verdict is only trustworthy if the reviewer can catch
violations at all -- executing agents vary in model strength and language.
This tool PLANTS unambiguous, language-neutral violations into a real file
and GRADES the reviewer's verdict against the answer key. A reviewer that
misses blatant plants disqualifies the run, not the file.

Planted violation kinds (all language-neutral, all outside frontmatter and
fenced blocks, never on lines carrying code spans or placeholder tokens,
so the exam tests the semantic half only -- the deterministic checker
stays silent):

  drop_bullet    a mid-list bullet line is removed
  drop_sentence  a middle sentence of a multi-sentence paragraph is removed
  edit_number    a numeric literal in prose is changed
  drop_clause    the trailing comma-clause of a long bullet is removed

Usage:
  refuter_calibration.py plant <original> --exam exam.md --key key.json
      [--count 5] [--seed 7]
  refuter_calibration.py plant-diff <unified.diff> --exam exam.diff --key key.json
      [--count 5] [--seed 7]
  refuter_calibration.py grade <key.json> <verdict.json> [--threshold 0.8]

plant-diff generalizes the exam to any adversarial reviewer of changes
(code review, MR review): it mutates only ADDED lines of a unified diff
(dropping an added line or editing a number), so a reviewer that approves
the mutated diff without noticing is unqualified.

Verdict format (lenient by design, for weaker agents): JSON with a
``violations`` array whose items are either strings or objects with
optional ``line`` and ``detail``/``description`` fields. A plant counts as
caught when a reported violation names a line within +/-3 of the planted
line OR quotes a distinctive fragment of the removed/changed text.
Indiscriminate spam does not qualify: a verdict reporting more than
max(30, 10 x plants) violations fails regardless of recall.

Exit codes: plant: 0 ok / 2 usage; grade: 0 pass / 1 fail / 2 usage.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

SCHEMA_KEY = "context_density.refuter_exam_key.v1"
SCHEMA_GRADE = "context_density.refuter_exam_grade.v1"

FENCE_RE = re.compile(r"^( {0,4})(```|~~~)")
BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\S")
NUMBER_RE = re.compile(r"\b\d{1,4}\b")
PROTECTED_RE = re.compile(r"`|\$[A-Z]|\{[a-z][a-z0-9_]*\}|__[A-Z]"
                          r"|\[[A-Z][A-Z0-9 _-]{2,}\]|^[ \t]*[A-Z][A-Z_]{3,}:")
FRONTMATTER_DELIM = "---"


def fence_mask(lines: list[str]) -> list[bool]:
    masked, in_fence = [], False
    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            masked.append(True)
            continue
        masked.append(in_fence)
    return masked


def frontmatter_end(lines: list[str]) -> int:
    """Index just past the closing frontmatter delimiter, or 0."""
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        return 0
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            return i + 1
    return 0


def plantable(lines: list[str]) -> list[int]:
    """Indexes of prose lines safe to mutate for a semantics-only exam."""
    masked = fence_mask(lines)
    skip_until = frontmatter_end(lines)
    out = []
    for i, line in enumerate(lines):
        if i < skip_until or masked[i] or not line.strip():
            continue
        if line.lstrip().startswith("#") or line.lstrip().startswith("|"):
            continue
        if PROTECTED_RE.search(line):
            continue
        out.append(i)
    return out


def fragment(text: str) -> str:
    """A distinctive fragment of removed/changed text, for grading."""
    words = re.findall(r"\w{4,}", text)
    return " ".join(words[:3]).lower()


def plant(original: str, count: int, seed: int) -> tuple[str, list[dict]]:
    lines = original.split("\n")
    rng = random.Random(seed)
    candidates = plantable(lines)
    rng.shuffle(candidates)
    plants: list[dict] = []
    used: set[int] = set()

    def free(i: int) -> bool:
        return all(abs(i - u) > 2 for u in used)

    for i in candidates:
        if len(plants) >= count:
            break
        if not free(i):
            continue
        line = lines[i]
        kind = None
        detail = ""
        if BULLET_RE.match(line) and i + 1 < len(lines) and BULLET_RE.match(lines[i + 1]) \
                and i > 0 and BULLET_RE.match(lines[i - 1]):
            kind, detail = "drop_bullet", fragment(line)
            lines[i] = None  # type: ignore[call-overload]
        elif NUMBER_RE.search(line):
            match = NUMBER_RE.search(line)
            old = match.group(0)
            new = str(int(old) * 2 + 1)
            kind, detail = "edit_number", f"{old} -> {new}"
            lines[i] = line[:match.start()] + new + line[match.end():]
        elif BULLET_RE.match(line) and line.count(",") >= 2 and len(line) > 80:
            cut = line.rfind(",")
            kind, detail = "drop_clause", fragment(line[cut:])
            lines[i] = line[:cut] + "."
        else:
            sentences = re.split(r"(?<=[.!?]) +", line)
            if len(sentences) >= 3:
                kind, detail = "drop_sentence", fragment(sentences[1])
                lines[i] = " ".join(sentences[:1] + sentences[2:])
        if kind:
            used.add(i)
            plants.append({"id": f"P{len(plants) + 1}", "kind": kind,
                           "line": i + 1, "clue": detail})
    exam = "\n".join(l for l in lines if l is not None)
    return exam, plants


DIFF_ADDED_RE = re.compile(r"^\+(?!\+\+)")


def plant_diff(diff_text: str, count: int, seed: int) -> tuple[str, list[dict]]:
    lines = diff_text.split("\n")
    rng = random.Random(seed)
    candidates = [i for i, l in enumerate(lines)
                  if DIFF_ADDED_RE.match(l) and len(l.strip()) > 10]
    rng.shuffle(candidates)
    plants: list[dict] = []
    used: set[int] = set()
    for i in candidates:
        if len(plants) >= count:
            break
        if any(abs(i - u) <= 2 for u in used):
            continue
        line = lines[i]
        match = NUMBER_RE.search(line[1:])
        if match and rng.random() < 0.5:
            old = match.group(0)
            new = str(int(old) * 2 + 1)
            lines[i] = "+" + line[1:][:match.start()] + new + line[1:][match.end():]
            plants.append({"id": f"P{len(plants) + 1}", "kind": "edit_number",
                           "line": i + 1, "clue": f"{old} -> {new}"})
        else:
            plants.append({"id": f"P{len(plants) + 1}", "kind": "drop_added_line",
                           "line": i + 1, "clue": fragment(line)})
            lines[i] = None  # type: ignore[call-overload]
        used.add(i)
    exam = "\n".join(l for l in lines if l is not None)
    return exam, plants


def verdict_items(verdict: dict | list) -> list[dict]:
    items = verdict.get("violations", verdict) if isinstance(verdict, dict) else verdict
    out = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, str):
            out.append({"line": None, "text": item.lower()})
        elif isinstance(item, dict):
            text = " ".join(str(v) for v in item.values()).lower()
            line = item.get("line")
            try:
                line = int(line) if line is not None else None
            except (TypeError, ValueError):
                line = None
            out.append({"line": line, "text": text})
    return out


def grade(key: dict, verdict: dict | list, threshold: float) -> dict:
    reported = verdict_items(verdict)
    spam_limit = max(30, 10 * len(key["plants"]))
    if len(reported) > spam_limit:
        return {"schema": SCHEMA_GRADE, "score": 0.0, "caught": [],
                "missed": [p["id"] for p in key["plants"]],
                "spam_guard": True, "passed": False}
    caught, missed = [], []
    for plant_entry in key["plants"]:
        clue_words = [w for w in plant_entry["clue"].split() if len(w) >= 4]
        hit = False
        for item in reported:
            if item["line"] is not None and abs(item["line"] - plant_entry["line"]) <= 3:
                hit = True
                break
            if clue_words and all(w in item["text"] for w in clue_words[:2]):
                hit = True
                break
        (caught if hit else missed).append(plant_entry["id"])
    score = len(caught) / len(key["plants"]) if key["plants"] else 0.0
    return {"schema": SCHEMA_GRADE, "score": round(score, 2),
            "caught": caught, "missed": missed,
            "passed": score >= threshold}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    p_plant = sub.add_parser("plant")
    p_plant.add_argument("original")
    p_plant.add_argument("--exam", required=True)
    p_plant.add_argument("--key", required=True)
    p_plant.add_argument("--count", type=int, default=5)
    p_plant.add_argument("--seed", type=int, default=7)
    p_pdiff = sub.add_parser("plant-diff")
    p_pdiff.add_argument("original")
    p_pdiff.add_argument("--exam", required=True)
    p_pdiff.add_argument("--key", required=True)
    p_pdiff.add_argument("--count", type=int, default=5)
    p_pdiff.add_argument("--seed", type=int, default=7)
    p_grade = sub.add_parser("grade")
    p_grade.add_argument("key")
    p_grade.add_argument("verdict")
    p_grade.add_argument("--threshold", type=float, default=0.8)
    args = parser.parse_args(argv)

    try:
        if args.mode in ("plant", "plant-diff"):
            original = Path(args.original).read_text(encoding="utf-8")
            planter = plant if args.mode == "plant" else plant_diff
            exam, plants = planter(original, args.count, args.seed)
            if not plants:
                kind = "prose" if args.mode == "plant" else "added lines"
                print(f"ERROR: no plantable {kind} found in original", file=sys.stderr)
                return 2
            Path(args.exam).write_text(exam, encoding="utf-8")
            Path(args.key).write_text(json.dumps(
                {"schema": SCHEMA_KEY, "original": args.original,
                 "requested": args.count, "plants": plants}, indent=2),
                encoding="utf-8")
            print(f"planted {len(plants)}/{args.count} violations "
                  f"-> {args.exam} (key: {args.key})")
            if len(plants) < args.count:
                print("note: fewer plants than requested; file has limited "
                      "plantable prose", file=sys.stderr)
            return 0
        key = json.loads(Path(args.key).read_text(encoding="utf-8"))
        verdict = json.loads(Path(args.verdict).read_text(encoding="utf-8"))
        result = grade(key, verdict, args.threshold)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    except (OSError, ValueError, KeyError) as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
