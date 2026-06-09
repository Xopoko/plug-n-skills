#!/usr/bin/env python3
"""Detect SDD-related surfaces in a repository."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "DerivedData",
    "build",
    "dist",
}


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def exists(root: Path, value: str) -> bool:
    return (root / value).exists()


def find_files(root: Path, names: set[str], limit: int = 200) -> list[str]:
    found: list[str] = []
    for current, dirs, files in walk(root):
        dirs[:] = [item for item in dirs if item not in IGNORE_DIRS]
        for filename in files:
            if filename in names:
                found.append(rel(Path(current) / filename, root))
                if len(found) >= limit:
                    return found
    return found


def walk(root: Path):
    import os

    return os.walk(root)


def feature_dirs(root: Path, base: str, required_any: set[str]) -> list[dict[str, Any]]:
    base_path = root / base
    if not base_path.is_dir():
        return []
    result: list[dict[str, Any]] = []
    for child in sorted(base_path.iterdir()):
        if not child.is_dir():
            continue
        files = sorted(item.name for item in child.iterdir() if item.is_file())
        if required_any and not any(name in files for name in required_any):
            continue
        result.append(
            {
                "path": rel(child, root),
                "files": files,
            }
        )
    return result


def detect(root: Path) -> dict[str, Any]:
    root = root.resolve()
    spec_kit_features = feature_dirs(root, "specs", {"spec.md", "plan.md", "tasks.md"})
    kiro_features = feature_dirs(root, ".kiro/specs", {"requirements.md", "bugfix.md", "design.md", "tasks.md"})
    spec_flow_features = feature_dirs(root, ".spec-flow/active", {"requirements.md", "proposal.md", "design.md", "tasks.md"})
    openspec_specs = feature_dirs(root, "openspec/specs", {"spec.md"})
    openspec_changes = feature_dirs(root, "openspec/changes", {"proposal.md", "tasks.md", "design.md"})

    root_trio = {
        "requirements": exists(root, "requirements.md"),
        "design": exists(root, "design.md"),
        "tasks": exists(root, "tasks.md"),
    }

    surfaces = {
        "git": exists(root, ".git"),
        "spec_kit": {
            "present": exists(root, ".specify") or bool(spec_kit_features),
            "constitution": exists(root, ".specify/memory/constitution.md"),
            "feature_json": exists(root, ".specify/feature.json"),
            "extensions": exists(root, ".specify/extensions.yml"),
            "features": spec_kit_features,
        },
        "kiro": {
            "present": exists(root, ".kiro") or bool(kiro_features),
            "steering": exists(root, ".kiro/steering"),
            "features": kiro_features,
        },
        "spec_flow": {
            "present": exists(root, ".spec-flow") or bool(spec_flow_features),
            "steering": exists(root, ".spec-flow/steering"),
            "features": spec_flow_features,
        },
        "openspec": {
            "present": exists(root, "openspec") or bool(openspec_specs) or bool(openspec_changes),
            "project": exists(root, "openspec/project.md"),
            "specs": openspec_specs,
            "changes": openspec_changes,
        },
        "root_trio": {
            "present": any(root_trio.values()),
            **root_trio,
        },
        "scattered_artifacts": find_files(
            root,
            {"spec.md", "requirements.md", "bugfix.md", "plan.md", "design.md", "tasks.md", "quickstart.md"},
        ),
    }

    recommendations: list[str] = []
    if surfaces["spec_kit"]["present"]:
        recommendations.append("spec-kit")
    if surfaces["kiro"]["present"]:
        recommendations.append("kiro-lite")
    if surfaces["openspec"]["present"]:
        recommendations.append("change-proposal")
    if surfaces["spec_flow"]["present"] or all(root_trio.values()):
        recommendations.append("kiro-lite")
    if not recommendations:
        recommendations.append("tiny-direct or sdd-specify, depending on risk and scope")

    return {
        "schema": "sdd.surface_audit.v1",
        "root": root.as_posix(),
        "surfaces": surfaces,
        "recommended_lanes": recommendations,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect SDD surfaces in a repository.")
    parser.add_argument("path", nargs="?", default=".", help="Repository or workspace path")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = detect(Path(args.path))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"SDD surface audit: {payload['root']}")
    print("Recommended lanes: " + ", ".join(payload["recommended_lanes"]))
    for name, data in payload["surfaces"].items():
        if isinstance(data, dict) and data.get("present"):
            print(f"- {name}: present")


if __name__ == "__main__":
    main()
