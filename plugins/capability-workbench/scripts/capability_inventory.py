#!/usr/bin/env python3
"""Inventory local agent (Codex and Claude) skills, plugins, and marketplace entries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_SKILL_ROOTS = [
    "${CODEX_HOME:-$HOME/.codex}/skills",
    "$HOME/.codex/skills/.system",
    "${CLAUDE_HOME:-$HOME/.claude}/skills",
    "$HOME/.claude/skills/.system",
    "${CURSOR_HOME:-$HOME/.cursor}/skills",
]
DEFAULT_PLUGIN_ROOTS = [
    "$HOME/plugins",
    "$HOME/.codex/plugins/cache/local",
    "$HOME/.codex/plugins/cache/openai-curated",
    "$HOME/.codex/plugins/cache/openai-curated-remote",
    "${CLAUDE_HOME:-$HOME/.claude}/plugins",
]
DEFAULT_MARKETPLACES = [
    "$HOME/.agents/plugins/marketplace.json",
    "${CLAUDE_HOME:-$HOME/.claude}/plugins/marketplace.json",
]
PLUGIN_MANIFEST_NAMES = (".codex-plugin", ".claude-plugin")


def expand_template(raw: str) -> Path:
    for var, default in (
        ("CODEX_HOME", ".codex"),
        ("CLAUDE_HOME", ".claude"),
        ("CURSOR_HOME", ".cursor"),
    ):
        template = "${%s:-$HOME/%s}" % (var, default)
        if raw.startswith(template):
            base = os.environ.get(var) or str(Path.home() / default)
            raw = raw.replace(template, base, 1)
            break
    return Path(os.path.expandvars(os.path.expanduser(raw)))


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def read_frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    result: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip("'\"")
    return result


def maybe_match(row: dict[str, Any], query: str | None) -> bool:
    if not query:
        return True
    haystack = " ".join(str(v) for v in row.values()).lower()
    return query.lower() in haystack


def inventory_skills(roots: list[Path], query: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for skill_md in sorted(root.rglob("SKILL.md")):
            if skill_md in seen:
                continue
            seen.add(skill_md)
            meta = read_frontmatter(skill_md)
            row = {
                "name": meta.get("name") or skill_md.parent.name,
                "description": meta.get("description", ""),
                "path": str(skill_md.parent),
                "root": str(root),
                "source": "local-skill-root",
            }
            if maybe_match(row, query):
                rows.append(row)
    return rows


def inventory_plugins(roots: list[Path], query: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    seen_plugins: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        manifests = [
            manifest
            for manifest_dir in PLUGIN_MANIFEST_NAMES
            for manifest in root.rglob(f"{manifest_dir}/plugin.json")
        ]
        for manifest in sorted(manifests):
            if manifest in seen or manifest.parent.parent in seen_plugins:
                continue
            seen.add(manifest)
            seen_plugins.add(manifest.parent.parent)
            data = read_json(manifest) or {}
            interface = data.get("interface") if isinstance(data.get("interface"), dict) else {}
            row = {
                "name": data.get("name") or manifest.parent.parent.name,
                "version": data.get("version", ""),
                "description": data.get("description", ""),
                "display_name": interface.get("displayName", ""),
                "path": str(manifest.parent.parent),
                "root": str(root),
                "source": "local-plugin-root",
                "skills": data.get("skills", ""),
            }
            if maybe_match(row, query):
                rows.append(row)
    return rows


def inventory_marketplaces(paths: list[Path], query: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        data = read_json(path)
        if not data:
            continue
        plugins = data.get("plugins")
        if not isinstance(plugins, list):
            continue
        for entry in plugins:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
            policy = entry.get("policy") if isinstance(entry.get("policy"), dict) else {}
            row = {
                "marketplace": data.get("name", ""),
                "marketplace_path": str(path),
                "name": entry.get("name", ""),
                "category": entry.get("category", ""),
                "source_kind": source.get("source", ""),
                "source_path": source.get("path", ""),
                "installation": policy.get("installation", ""),
                "authentication": policy.get("authentication", ""),
                "source": "marketplace-entry",
            }
            if maybe_match(row, query):
                rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory local agent skill and plugin capability surfaces (Codex and Claude).")
    parser.add_argument("--query", help="Substring filter across names, descriptions, and paths.")
    parser.add_argument("--skill-root", action="append", default=[], help="Additional skill root to scan.")
    parser.add_argument("--plugin-root", action="append", default=[], help="Additional plugin root to scan.")
    parser.add_argument("--marketplace", action="append", default=[], help="Additional marketplace.json path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON. Default is a compact text summary.")
    args = parser.parse_args()

    skill_roots = [expand_template(p) for p in DEFAULT_SKILL_ROOTS + args.skill_root]
    plugin_roots = [expand_template(p) for p in DEFAULT_PLUGIN_ROOTS + args.plugin_root]
    marketplace_paths = [expand_template(p) for p in DEFAULT_MARKETPLACES + args.marketplace]

    payload = {
        "schema": "capability.inventory.v1",
        "query": args.query,
        "skill_roots": [str(p) for p in skill_roots],
        "plugin_roots": [str(p) for p in plugin_roots],
        "marketplace_paths": [str(p) for p in marketplace_paths],
        "skills": inventory_skills(skill_roots, args.query),
        "plugins": inventory_plugins(plugin_roots, args.query),
        "marketplace_entries": inventory_marketplaces(marketplace_paths, args.query),
    }
    payload["counts"] = {
        "skills": len(payload["skills"]),
        "plugins": len(payload["plugins"]),
        "marketplace_entries": len(payload["marketplace_entries"]),
    }

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(json.dumps(payload["counts"], ensure_ascii=False))
    for section in ("skills", "plugins", "marketplace_entries"):
        print(f"\n{section}:")
        for row in payload[section][:25]:
            print(f"- {row.get('name')}  {row.get('path') or row.get('source_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
