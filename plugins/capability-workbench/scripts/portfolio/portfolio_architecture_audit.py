#!/usr/bin/env python3
"""Audit skill/plugin portfolio architecture signals.

The script is intentionally conservative. It does not decide that a skill must
be deleted, split, or merged; it emits candidates that need human/agent review.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from itertools import combinations
from pathlib import Path
from typing import Any


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+-]{2,}")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.S)
STOPWORDS = {
    "about",
    "across",
    "action",
    "actions",
    "after",
    "and",
    "any",
    "are",
    "before",
    "body",
    "boundary",
    "boundaries",
    "check",
    "checks",
    "command",
    "commands",
    "context",
    "current",
    "data",
    "decision",
    "decisions",
    "detail",
    "details",
    "docs",
    "during",
    "edit",
    "editing",
    "file",
    "files",
    "for",
    "from",
    "has",
    "into",
    "issue",
    "issues",
    "local",
    "make",
    "must",
    "need",
    "needs",
    "into",
    "not",
    "output",
    "outputs",
    "path",
    "paths",
    "preserve",
    "report",
    "reports",
    "review",
    "reviews",
    "run",
    "runs",
    "script",
    "scripts",
    "source",
    "sources",
    "step",
    "steps",
    "target",
    "targets",
    "the",
    "this",
    "tool",
    "tools",
    "use",
    "used",
    "user",
    "users",
    "validate",
    "validation",
    "validator",
    "validators",
    "when",
    "with",
    "work",
    "workflow",
    "workflows",
    "skill",
    "skills",
    "plugin",
    "plugins",
    "agent",
    "agents",
}

INTENT_TAGS = {
    "portfolio-architecture": {
        "architecture",
        "boundary",
        "boundaries",
        "capability",
        "cohesion",
        "coupling",
        "delete",
        "merge",
        "modularity",
        "move",
        "overlap",
        "portfolio",
        "refactor",
        "router",
        "split",
    },
    "context-contracts": {
        "compression",
        "contract",
        "contracts",
        "density",
        "json",
        "llm",
        "prompt",
        "schema",
        "structured",
        "token",
        "tokens",
    },
    "release-packaging": {
        "archive",
        "build",
        "ci",
        "distribution",
        "notarize",
        "package",
        "publish",
        "release",
        "signing",
        "store",
        "testflight",
        "upload",
    },
    "project-scaffolding": {
        "bootstrap",
        "create",
        "init",
        "project",
        "scaffold",
        "template",
    },
    "quality-validation": {
        "audit",
        "debug",
        "diagnose",
        "fitness",
        "quality",
        "repair",
        "test",
        "testing",
    },
    "research-evidence": {
        "claim",
        "claims",
        "corpus",
        "deduplication",
        "doi",
        "evidence",
        "literature",
        "paper",
        "research",
        "scholarly",
    },
    "interface-design": {
        "accessibility",
        "design",
        "interaction",
        "interface",
        "usability",
        "visual",
    },
}


def load_encoder(name: str):
    try:
        import tiktoken  # type: ignore

        return tiktoken.get_encoding(name), "exact"
    except Exception:
        return None, "approx"


def count_tokens(text: str, encoder) -> int:
    if encoder is not None:
        return len(encoder.encode(text))
    return int(math.ceil(len(text) / 4))


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    data: dict[str, str] = {}
    current_key = ""
    current_value: list[str] = []
    for line in raw.splitlines():
        if re.match(r"^[A-Za-z0-9_-]+:", line):
            if current_key:
                data[current_key] = " ".join(current_value).strip().strip('"')
            current_key, value = line.split(":", 1)
            current_value = [value.strip()]
        elif current_key:
            current_value.append(line.strip())
    if current_key:
        data[current_key] = " ".join(current_value).strip().strip('"')
    return data, text[match.end() :]


def words(text: str) -> set[str]:
    return {
        token.lower()
        for token in WORD_RE.findall(text)
        if token.lower() not in STOPWORDS and len(token) > 2
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def heading_count(body: str) -> int:
    return sum(1 for line in body.splitlines() if line.startswith("#"))


def code_fence_count(body: str) -> int:
    return body.count("```") // 2


def responsibility_text(name: str, description: str, body: str) -> str:
    """Use retrieval-facing text, not the whole skill body, for boundary overlap."""
    headings = [line.lstrip("#").strip() for line in body.splitlines() if line.startswith("#")]
    first_lines = "\n".join(line for line in body.splitlines()[:35] if not line.startswith("```"))
    return "\n".join([name, description, *headings, first_lines])


def responsibility_tag_text(name: str, description: str, body: str) -> str:
    headings = [line.lstrip("#").strip() for line in body.splitlines() if line.startswith("#")]
    return "\n".join([name, description, *headings])


def responsibility_tags(terms: set[str]) -> list[str]:
    tags = []
    for tag, markers in INTENT_TAGS.items():
        if len(terms & markers) >= 2:
            tags.append(tag)
    return tags


def name_families(rows: list[dict[str, Any]], plugin_name: str) -> dict[str, int]:
    families: dict[str, int] = {}
    for row in rows:
        parts = [part for part in row["name"].split("-") if part and part != plugin_name]
        if not parts:
            continue
        family = parts[0]
        if family in {"ios", "macos", "xcode", "appstore", "swiftpm", "tuist", "kmp", "pixijs"} and len(parts) > 1:
            family = "-".join(parts[:2]) if family in {"appstore", "pixijs"} else family
        families[family] = families.get(family, 0) + 1
    return dict(sorted(families.items(), key=lambda item: item[1], reverse=True))


def skill_rows(plugin_dir: Path, encoder) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for skill_md in sorted((plugin_dir / "skills").glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(text)
        skill_dir = skill_md.parent
        reference_files = sorted((skill_dir / "references").glob("*.md"))
        script_files = sorted((skill_dir / "scripts").glob("*")) if (skill_dir / "scripts").is_dir() else []
        description = frontmatter.get("description", "")
        signature_terms = words(
            responsibility_text(
                frontmatter.get("name", skill_dir.name),
                description,
                body,
            )
        )
        tag_terms = words(
            responsibility_tag_text(
                frontmatter.get("name", skill_dir.name),
                description,
                body,
            )
        )
        rows.append(
            {
                "plugin": plugin_dir.name,
                "name": frontmatter.get("name", skill_dir.name),
                "path": str(skill_md),
                "description_chars": len(description),
                "tokens": count_tokens(text, encoder),
                "lines": text.count("\n") + (1 if text else 0),
                "headings": heading_count(body),
                "code_fences": code_fence_count(body),
                "references": len([p for p in reference_files if p.is_file()]),
                "scripts": len([p for p in script_files if p.is_file()]),
                "terms": sorted(words(description + "\n" + body)),
                "signature_terms": sorted(signature_terms),
                "intent_tags": responsibility_tags(tag_terms),
                "has_reference_link": "references/" in body or "references/" in description,
                "has_script_link": "scripts/" in body or "scripts/" in description,
            }
        )
    return rows


def pair_overlaps(rows: list[dict[str, Any]], threshold: float) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for left, right in combinations(rows, 2):
        score = jaccard(set(left["terms"]), set(right["terms"]))
        if score >= threshold:
            shared = sorted(set(left["terms"]) & set(right["terms"]))[:20]
            pairs.append(
                {
                    "left": left["name"],
                    "right": right["name"],
                    "score": round(score, 3),
                    "shared_terms": shared,
                }
            )
    pairs.sort(key=lambda item: item["score"], reverse=True)
    return pairs


def recommendations(
    plugin_dir: Path,
    rows: list[dict[str, Any]],
    overlaps: list[dict[str, Any]],
    *,
    large_skill_tokens: int,
    very_large_skill_tokens: int,
    max_description_chars: int,
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    skill_count = len(rows)
    plugin_name = plugin_dir.name
    has_router = any(row["name"] == plugin_name for row in rows)
    families = name_families(rows, plugin_name)

    if skill_count >= 10 and not has_router:
        recs.append(
            {
                "action": "router-review",
                "subject": plugin_name,
                "reason": "Large plugin has many skills but no plugin-named router skill.",
            }
        )
    if skill_count >= 25 and len(families) >= 6:
        recs.append(
            {
                "action": "plugin-split-review",
                "subject": plugin_name,
                "reason": f"{skill_count} skills across {len(families)} name families",
                "families": families,
            }
        )

    for row in rows:
        if row["description_chars"] > max_description_chars:
            recs.append(
                {
                    "action": "metadata-review",
                    "subject": row["name"],
                    "reason": f"description has {row['description_chars']} chars",
                }
            )
        if row["tokens"] >= very_large_skill_tokens and row["headings"] >= 8:
            recs.append(
                {
                    "action": "split-review",
                    "subject": row["name"],
                    "reason": f"{row['tokens']} tokens and {row['headings']} headings",
                }
            )
        elif row["tokens"] >= large_skill_tokens and not row["has_reference_link"]:
            recs.append(
                {
                    "action": "reference-extract",
                    "subject": row["name"],
                    "reason": f"{row['tokens']} hot-path tokens with no reference link",
                }
            )
        if row["code_fences"] >= 5 and row["scripts"] == 0 and not row["has_script_link"]:
            recs.append(
                {
                    "action": "script-extract",
                    "subject": row["name"],
                    "reason": f"{row['code_fences']} code fences and no local scripts",
                }
            )

    for pair in overlaps[:20]:
        recs.append(
            {
                "action": "merge-review",
                "subject": f"{pair['left']} + {pair['right']}",
                "reason": f"term overlap score {pair['score']}",
            }
        )

    if not recs and rows:
        recs.append(
            {
                "action": "keep",
                "subject": plugin_name,
                "reason": "No structural review threshold triggered.",
            }
        )
    return recs


def cross_plugin_overlaps(
    rows: list[dict[str, Any]],
    *,
    threshold: float,
    min_shared_terms: int,
    limit: int,
) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for left, right in combinations(rows, 2):
        if left["plugin"] == right["plugin"]:
            continue
        left_terms = set(left["signature_terms"])
        right_terms = set(right["signature_terms"])
        shared = sorted(left_terms & right_terms)
        shared_tags = sorted(set(left.get("intent_tags", [])) & set(right.get("intent_tags", [])))
        score = jaccard(left_terms, right_terms)
        if score < threshold and not shared_tags:
            continue
        if len(shared) < min_shared_terms and not shared_tags:
            continue
        pairs.append(
            {
                "left_plugin": left["plugin"],
                "left_skill": left["name"],
                "left_path": left["path"],
                "right_plugin": right["plugin"],
                "right_skill": right["name"],
                "right_path": right["path"],
                "score": round(score, 3),
                "shared_terms": shared[:24],
                "shared_intent_tags": shared_tags,
            }
        )
    pairs.sort(key=lambda item: (len(item["shared_intent_tags"]), item["score"], len(item["shared_terms"])), reverse=True)
    return pairs[:limit]


def portfolio_recommendations(cross_overlaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    for pair in cross_overlaps:
        action = "cross-plugin-overlap-review"
        if pair["left_skill"] == pair["right_skill"]:
            action = "cross-plugin-merge-review"
        recs.append(
            {
                "action": action,
                "subject": f"{pair['left_plugin']}:{pair['left_skill']} + {pair['right_plugin']}:{pair['right_skill']}",
                "reason": f"responsibility signature overlap score {pair['score']}",
                "shared_terms": pair["shared_terms"],
                "shared_intent_tags": pair["shared_intent_tags"],
            }
        )
    if not recs:
        recs.append(
            {
                "action": "keep",
                "subject": "portfolio",
                "reason": "No cross-plugin responsibility overlap threshold triggered.",
            }
        )
    return recs


def audit_plugin(plugin_dir: Path, args: argparse.Namespace, encoder, mode: str) -> dict[str, Any]:
    rows = skill_rows(plugin_dir, encoder)
    overlaps = pair_overlaps(rows, args.overlap_threshold)
    total_tokens = sum(row["tokens"] for row in rows)
    plugin_references = [p for p in (plugin_dir / "references").rglob("*") if p.is_file()]
    plugin_scripts = [p for p in (plugin_dir / "scripts").rglob("*") if p.is_file()]
    skill_references = sum(row["references"] for row in rows)
    skill_scripts = sum(row["scripts"] for row in rows)
    total_references = len(plugin_references) + skill_references
    total_scripts = len(plugin_scripts) + skill_scripts
    recs = recommendations(
        plugin_dir,
        rows,
        overlaps,
        large_skill_tokens=args.large_skill_tokens,
        very_large_skill_tokens=args.very_large_skill_tokens,
        max_description_chars=args.max_description_chars,
    )
    skill_summaries = [
        {key: row[key] for key in ("name", "path", "tokens", "lines", "description_chars", "headings", "code_fences", "references", "scripts", "has_reference_link", "has_script_link")}
        for row in sorted(rows, key=lambda item: item["tokens"], reverse=True)
    ]
    return {
        "plugin": plugin_dir.name,
        "path": str(plugin_dir),
        "token_mode": mode,
        "skills": len(rows),
        "total_skill_tokens": total_tokens,
        "avg_skill_tokens": round(total_tokens / len(rows), 1) if rows else 0,
        "references": total_references,
        "scripts": total_scripts,
        "plugin_references": len(plugin_references),
        "plugin_scripts": len(plugin_scripts),
        "overlaps": overlaps[: args.top_overlaps],
        "recommendations": recs,
        "skill_summaries": skill_summaries[: args.top_skills],
    }


def collect_plugin_dirs(paths: list[str]) -> tuple[list[Path], list[str]]:
    plugin_dirs: list[Path] = []
    skipped: list[str] = []
    seen: set[Path] = set()
    for raw in paths:
        path = Path(raw)
        candidates = [path]
        if path.is_dir() and not (path / "skills").is_dir():
            children = sorted(child for child in path.iterdir() if child.is_dir())
            candidates = children if children else [path]
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            if not candidate.is_dir() or not (candidate / "skills").is_dir():
                skipped.append(str(candidate))
                continue
            seen.add(resolved)
            plugin_dirs.append(candidate)
    return plugin_dirs, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit skill/plugin portfolio architecture signals.")
    parser.add_argument("paths", nargs="+", help="Plugin directories to audit.")
    parser.add_argument("--encoding", default="o200k_base")
    parser.add_argument("--overlap-threshold", type=float, default=0.42)
    parser.add_argument("--cross-overlap-threshold", type=float, default=0.12)
    parser.add_argument("--min-cross-shared-terms", type=int, default=8)
    parser.add_argument("--large-skill-tokens", type=int, default=1200)
    parser.add_argument("--very-large-skill-tokens", type=int, default=2400)
    parser.add_argument("--max-description-chars", type=int, default=500)
    parser.add_argument("--top-skills", type=int, default=20)
    parser.add_argument("--top-overlaps", type=int, default=20)
    parser.add_argument("--top-cross-overlaps", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="Emit JSON only.")
    args = parser.parse_args()

    encoder, mode = load_encoder(args.encoding)
    plugin_dirs, skipped_paths = collect_plugin_dirs(args.paths)
    audits = [audit_plugin(plugin_dir, args, encoder, mode) for plugin_dir in plugin_dirs]
    all_rows = [row for audit in audits for row in skill_rows(Path(audit["path"]), encoder)]
    cross_overlaps = cross_plugin_overlaps(
        all_rows,
        threshold=args.cross_overlap_threshold,
        min_shared_terms=args.min_cross_shared_terms,
        limit=args.top_cross_overlaps,
    )
    result = {
        "schema": "codex.capability_portfolio_architecture_audit.v1",
        "portfolio": {
            "plugin_count": len(audits),
            "skill_count": sum(audit["skills"] for audit in audits),
            "skipped_paths": skipped_paths,
            "cross_plugin_overlaps": cross_overlaps,
            "recommendations": portfolio_recommendations(cross_overlaps),
        },
        "plugins": audits,
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(f"portfolio: {result['portfolio']['plugin_count']} plugins, {result['portfolio']['skill_count']} skills")
    for rec in result["portfolio"]["recommendations"]:
        print(f"- {rec['action']}: {rec['subject']} ({rec['reason']})")
    for audit in audits:
        print(f"{audit['plugin']}: {audit['skills']} skills, {audit['total_skill_tokens']} skill tokens")
        for rec in audit["recommendations"]:
            print(f"- {rec['action']}: {rec['subject']} ({rec['reason']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
