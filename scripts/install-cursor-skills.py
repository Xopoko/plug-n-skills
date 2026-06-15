#!/usr/bin/env python3
"""Install repository plugin skills into the Cursor global skills directory.

Cursor consumes SKILL.md folders directly and has no plugin marketplace, so
installation means copying each plugin's skills into a flat skills directory
(default: ${CURSOR_HOME:-~/.cursor}/skills). The copy is idempotent: unchanged
skills are skipped, drifted skills are replaced to match the repository source,
and repeated runs converge to the same state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_target import resolve_agent  # noqa: E402


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def plugin_names(root: Path) -> list[str]:
    marketplace = json.loads(
        (root / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    return [entry["name"] for entry in marketplace["plugins"]]


def skill_dirs(plugin_dir: Path) -> list[Path]:
    skills_root = plugin_dir / "skills"
    if not skills_root.is_dir():
        return []
    return sorted(
        child
        for child in skills_root.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )


def tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if "__pycache__" in path.parts:
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin",
        action="append",
        default=[],
        help="Limit to one or more plugin names (repeatable; default: all).",
    )
    parser.add_argument(
        "--exclude-plugin",
        action="append",
        default=[],
        help=(
            "Exclude a plugin from the selected set. Repeat to exclude several. "
            "Useful for host-specific local installs."
        ),
    )
    parser.add_argument(
        "--dest",
        help="Destination skills directory (default: Cursor global skills dir).",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report actions without writing."
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify installed skills match the repository; exit 1 on drift.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    names = plugin_names(root)
    selected, unknown = select_plugins(names, args.plugin, args.exclude_plugin)
    if unknown:
        print(f"unknown plugin(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    dest_root = Path(args.dest).expanduser() if args.dest else resolve_agent(
        explicit="cursor"
    ).skills_dir

    # Cursor's skills namespace is flat: refuse colliding skill names upfront.
    sources: dict[str, Path] = {}
    collisions: list[str] = []
    for name in selected:
        for skill_dir in skill_dirs(root / "plugins" / name):
            if skill_dir.name in sources:
                collisions.append(
                    f"{skill_dir.name}: {sources[skill_dir.name]} vs {skill_dir}"
                )
            sources[skill_dir.name] = skill_dir
    if collisions:
        print("skill name collisions; nothing installed:", file=sys.stderr)
        for line in collisions:
            print(f"- {line}", file=sys.stderr)
        return 2

    installed = updated = unchanged = drifted = 0
    for skill_name, source in sorted(sources.items()):
        dest = dest_root / skill_name
        if dest.is_dir() and tree_fingerprint(dest) == tree_fingerprint(source):
            unchanged += 1
            continue
        if args.check_only:
            drifted += 1
            state = "missing" if not dest.is_dir() else "drifted"
            print(f"{state}: {skill_name}")
            continue
        action = "update" if dest.is_dir() else "install"
        if args.dry_run:
            print(f"would {action}: {skill_name} -> {dest}")
        else:
            if dest.is_dir():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(
                source, dest, ignore=shutil.ignore_patterns("__pycache__")
            )
            print(f"{action}d: {skill_name} -> {dest}")
        if action == "update":
            updated += 1
        else:
            installed += 1

    summary = (
        f"installed={installed} updated={updated} "
        f"unchanged={unchanged} dest={dest_root}"
    )
    if args.check_only:
        print(f"checked: drift={drifted} unchanged={unchanged} dest={dest_root}")
        return 1 if drifted else 0
    print(("dry-run: " if args.dry_run else "") + summary)
    return 0


def select_plugins(
    available: list[str],
    included: list[str],
    excluded: list[str],
) -> tuple[list[str], list[str]]:
    known = set(available)
    unknown = sorted((set(included) | set(excluded)) - known)
    if unknown:
        return [], unknown
    overlap = sorted(set(included) & set(excluded))
    if overlap:
        print(
            f"plugin(s) cannot be both selected and excluded: {', '.join(overlap)}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    base = included or available
    selected = [name for name in base if name not in set(excluded)]
    if not selected:
        print("no plugins selected after applying --exclude-plugin", file=sys.stderr)
        raise SystemExit(2)
    return selected, []


if __name__ == "__main__":
    raise SystemExit(main())
