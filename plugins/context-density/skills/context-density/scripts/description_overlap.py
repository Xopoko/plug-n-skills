#!/usr/bin/env python3
"""Measure routing competition between skill descriptions.

Skill frontmatter descriptions share one routing context at startup; pairs
with high lexical overlap compete for the same triggers. Emits JSON pairs
sorted by Jaccard similarity over content words.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "asked", "asks", "be", "by", "can",
    "do", "does", "for", "from", "his", "how", "if", "in", "into", "is", "it",
    "its", "like", "needs", "not", "of", "off", "on", "or", "other", "should",
    "that", "the", "their", "them", "this", "to", "trigger", "triggered",
    "triggers", "use", "used", "user", "users", "wants", "what", "when",
    "whenever", "which", "while", "with", "you", "your",
}
WORD_RE = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*")


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict[str, str] = {}
    current_key = ""
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key_match = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if key_match:
            current_key = key_match.group(1).lower()
            value = key_match.group(2).strip()
            fields[current_key] = "" if value in {">-", ">", "|", "|-"} else value
        elif current_key and (line.startswith(" ") or line.startswith("\t")):
            fields[current_key] = (fields[current_key] + " " + line.strip()).strip()
    return fields


def content_words(description: str) -> set[str]:
    return {w for w in WORD_RE.findall(description.lower()) if w not in STOPWORDS and len(w) > 2}


def skill_identity(skill_md: Path) -> dict[str, str]:
    parts = skill_md.parts
    plugin = ""
    if "skills" in parts:
        idx = parts.index("skills")
        if idx > 0:
            plugin = parts[idx - 1]
    return {"path": str(skill_md), "skill": skill_md.parent.name, "plugin": plugin}


def collect_skills(paths: list[str]) -> list[dict]:
    skills = []
    seen: set[str] = set()
    for raw in paths:
        root = Path(raw).expanduser()
        candidates = [root] if root.is_file() else sorted(root.rglob("SKILL.md"))
        for skill_md in candidates:
            key = str(skill_md.resolve())
            if key in seen or skill_md.name != "SKILL.md":
                continue
            seen.add(key)
            try:
                fields = parse_frontmatter(skill_md.read_text(encoding="utf-8"))
            except OSError:
                continue
            description = fields.get("description", "")
            if not description:
                continue
            identity = skill_identity(skill_md)
            identity["name"] = fields.get("name", identity["skill"])
            identity["description"] = description
            identity["words"] = content_words(description)
            skills.append(identity)
    return skills


def overlap_pairs(skills: list[dict], min_jaccard: float, top: int) -> list[dict]:
    pairs = []
    for i, a in enumerate(skills):
        for b in skills[i + 1 :]:
            if not a["words"] or not b["words"]:
                continue
            shared = a["words"] & b["words"]
            union = a["words"] | b["words"]
            jaccard = len(shared) / len(union)
            if jaccard < min_jaccard:
                continue
            pairs.append(
                {
                    "jaccard": round(jaccard, 3),
                    "shared_term_count": len(shared),
                    "a": {"name": a["name"], "plugin": a["plugin"], "path": a["path"]},
                    "b": {"name": b["name"], "plugin": b["plugin"], "path": b["path"]},
                    "same_plugin": bool(a["plugin"]) and a["plugin"] == b["plugin"],
                    "shared_terms": sorted(shared, key=lambda w: (-len(w), w))[:12],
                }
            )
    pairs.sort(key=lambda p: (-p["jaccard"], p["a"]["name"], p["b"]["name"]))
    return pairs[:top]


def main() -> int:
    parser = argparse.ArgumentParser(description="Report skill-description pairs competing for routing.")
    parser.add_argument("paths", nargs="+", help="Directories (or SKILL.md files) to scan.")
    parser.add_argument("--min-jaccard", type=float, default=0.25, help="Minimum content-word Jaccard to report.")
    parser.add_argument("--top", type=int, default=20, help="Pairs to include, sorted by similarity.")
    args = parser.parse_args()

    skills = collect_skills(args.paths)
    payload = {
        "schema": "context_density.description_overlap.v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "skills_scanned": len(skills),
        "min_jaccard": args.min_jaccard,
        "pairs": overlap_pairs(skills, args.min_jaccard, args.top),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
