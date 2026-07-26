#!/usr/bin/env python3
"""Inventory local agent (Codex and Claude) skills, plugins, and marketplace entries."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


DEFAULT_SKILL_ROOTS = [
    "${CODEX_HOME:-$HOME/.codex}/skills",
    "${CODEX_HOME:-$HOME/.codex}/skills/.system",
    "${CLAUDE_HOME:-$HOME/.claude}/skills",
    "${CLAUDE_HOME:-$HOME/.claude}/skills/.system",
    "${CURSOR_HOME:-$HOME/.cursor}/skills",
]
DEFAULT_CODEX_CACHE_ROOTS = [
    "${CODEX_HOME:-$HOME/.codex}/plugins/cache",
]
DEFAULT_PLUGIN_ROOTS = [
    "$HOME/plugins",
    *DEFAULT_CODEX_CACHE_ROOTS,
    "${CLAUDE_HOME:-$HOME/.claude}/plugins",
]
DEFAULT_MARKETPLACES = [
    "$HOME/.agents/plugins/marketplace.json",
    "${CLAUDE_HOME:-$HOME/.claude}/plugins/marketplace.json",
]
PLUGIN_MANIFEST_NAMES = (".codex-plugin", ".claude-plugin")
MAX_CACHE_VERSION_LENGTH = 255
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


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


def semver_sort_key(raw: str) -> tuple[Any, ...] | None:
    """Return SemVer precedence plus a deterministic cachebuster tie-break."""
    if len(raw) > MAX_CACHE_VERSION_LENGTH:
        return None
    match = SEMVER_RE.fullmatch(raw)
    if match is None:
        return None

    prerelease = match.group(4)
    if prerelease is not None:
        prerelease_parts = prerelease.split(".")
        if any(
            part.isdigit() and len(part) > 1 and part.startswith("0")
            for part in prerelease_parts
        ):
            return None
        prerelease_key = tuple(
            (0, int(part)) if part.isdigit() else (1, part)
            for part in prerelease_parts
        )
    else:
        prerelease_key = ()

    build = match.group(5)
    build_key = (
        tuple(
            (0, int(part), part) if part.isdigit() else (1, part)
            for part in build.split(".")
        )
        if build
        else ()
    )

    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        prerelease is None,
        prerelease_key,
        build_key,
    )


def path_is_within_without_symlinks(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    current = root
    if current.is_symlink():
        return False
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return False
    return True


def readable_directories(root: Path) -> list[Path]:
    try:
        entries = list(root.iterdir())
    except OSError:
        return []
    directories: list[Path] = []
    for path in entries:
        try:
            if path.is_symlink() or not path.is_dir():
                continue
        except OSError:
            continue
        directories.append(path)
    return directories


def direct_plugin_manifests(plugin_root: Path) -> list[Path]:
    manifests: list[Path] = []
    for manifest_dir in PLUGIN_MANIFEST_NAMES:
        manifest_parent = plugin_root / manifest_dir
        manifest = manifest_parent / "plugin.json"
        try:
            if (
                manifest_parent.is_symlink()
                or manifest.is_symlink()
                or not manifest.is_file()
                or not path_is_within_without_symlinks(
                    manifest,
                    plugin_root,
                )
            ):
                continue
        except OSError:
            continue
        manifests.append(manifest)
    return manifests


def preferred_cache_manifest(plugin_root: Path) -> Path | None:
    for manifest in direct_plugin_manifests(plugin_root):
        data = read_json(manifest)
        if (
            data is not None
            and all(
                isinstance(data.get(field), str)
                and bool(data[field].strip())
                for field in ("name", "version", "description")
            )
            and semver_sort_key(data["version"]) is not None
        ):
            return manifest
    return None


def resolved_path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(
            root.resolve(strict=False)
        )
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def cache_plugin_candidates(plugin_dir: Path) -> list[tuple[tuple[Any, ...], Path]]:
    candidates: dict[Path, tuple[Any, ...]] = {}
    for candidate in readable_directories(plugin_dir):
        manifest = preferred_cache_manifest(candidate)
        if manifest is None:
            continue
        data = read_json(manifest)
        if data is None:
            continue
        directory_key = semver_sort_key(candidate.name)
        manifest_key = semver_sort_key(str(data.get("version", "")))
        key = directory_key or manifest_key
        if key is not None:
            candidates[candidate] = key
    return [(key, path) for path, key in candidates.items()]


def latest_cache_version_roots(root: Path) -> list[Path]:
    """Select one current candidate per source/plugin without deleting siblings."""
    selected: list[Path] = []
    if not root.is_dir() or root.is_symlink():
        return selected
    for source_dir in sorted(readable_directories(root)):
        for plugin_dir in sorted(readable_directories(source_dir)):
            if preferred_cache_manifest(plugin_dir) is not None:
                selected.append(plugin_dir)
                continue
            candidates = cache_plugin_candidates(plugin_dir)
            if candidates:
                highest_key = max(key for key, _ in candidates)
                highest = [
                    path
                    for key, path in candidates
                    if key == highest_key
                ]
                if len(highest) == 1:
                    selected.append(highest[0])
    return selected


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


def inventory_plugins(
    roots: list[Path],
    query: str | None,
    *,
    versioned_cache_roots: set[Path] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    seen_plugins: set[Path] = set()
    cache_roots = versioned_cache_roots or set()
    for root in roots:
        if not root.exists():
            continue
        if any(
            root != cache_root
            and resolved_path_is_within(root, cache_root)
            for cache_root in cache_roots
        ):
            continue
        if root in cache_roots:
            manifests = [
                manifest
                for scan_root in latest_cache_version_roots(root)
                for manifest in [preferred_cache_manifest(scan_root)]
                if manifest is not None
            ]
        else:
            manifests = [
                manifest
                for manifest_dir in PLUGIN_MANIFEST_NAMES
                for manifest in root.rglob(
                    f"{manifest_dir}/plugin.json"
                )
            ]
        for manifest in sorted(manifests):
            if manifest in seen or manifest.parent.parent in seen_plugins:
                continue
            seen.add(manifest)
            seen_plugins.add(manifest.parent.parent)
            data = read_json(manifest)
            if data is None:
                continue
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
    codex_cache_roots = {
        expand_template(path)
        for path in DEFAULT_CODEX_CACHE_ROOTS
    }
    marketplace_paths = [expand_template(p) for p in DEFAULT_MARKETPLACES + args.marketplace]

    payload = {
        "schema": "capability.inventory.v1",
        "query": args.query,
        "skill_roots": [str(p) for p in skill_roots],
        "plugin_roots": [str(p) for p in plugin_roots],
        "marketplace_paths": [str(p) for p in marketplace_paths],
        "skills": inventory_skills(skill_roots, args.query),
        "plugins": inventory_plugins(
            plugin_roots,
            args.query,
            versioned_cache_roots=codex_cache_roots,
        ),
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
