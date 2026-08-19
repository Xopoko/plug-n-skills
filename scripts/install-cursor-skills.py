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
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_target import resolve_agent  # noqa: E402
import plugin_catalog  # noqa: E402
from plugin_registry import repo_root, resolve_selection  # noqa: E402


def local_plugin_names(root: Path) -> list[str]:
    return sorted(
        path.name
        for path in (root / "plugins").iterdir()
        if path.is_dir() and (path / ".codex-plugin" / "plugin.json").is_file()
    )


def first_party_plugins(root: Path) -> list[dict]:
    return plugin_catalog.validate_catalog(root)["plugins"]


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
        help=(
            "Limit to one or more local or pinned first-party plugin names "
            "(repeatable; default: every local plugin)."
        ),
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
    parser.add_argument(
        "--include-first-party",
        action="store_true",
        help="Also include catalog entries whose selection.default is true.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Never fetch; require selected standalone plugins in the verified cache.",
    )
    parser.add_argument(
        "--first-party-cache-root",
        help="Override the pinned standalone source cache root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.dry_run and args.check_only:
        print("--dry-run and --check-only cannot be combined", file=sys.stderr)
        return 2
    root = repo_root()
    names = local_plugin_names(root)
    catalog_plugins = first_party_plugins(root)
    first_party_names = [item["name"] for item in catalog_plugins]
    by_first_party = {item["name"]: item for item in catalog_plugins}
    available = names + first_party_names
    default_selection = list(names)
    if args.include_first_party:
        default_selection.extend(plugin_catalog.default_plugin_names({"plugins": catalog_plugins}))
    selected, unknown = select_plugins(
        available,
        args.plugin,
        args.exclude_plugin,
        default_available=default_selection,
    )
    if unknown:
        print(f"unknown plugin(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    dest_root = Path(args.dest).expanduser() if args.dest else resolve_agent(
        explicit="cursor"
    ).skills_dir

    # Cursor's skills namespace is flat: refuse colliding skill names upfront.
    plugin_sources: dict[str, Path] = {}
    planned_skills: dict[str, str] = {}
    collisions: list[str] = []
    for name in selected:
        if name not in by_first_party:
            plugin_sources[name] = root / "plugins" / name
            continue
        if args.dry_run:
            receipt = plugin_catalog.receipt_for(root, by_first_party[name])
            for item in receipt["skills"]["items"]:
                skill_name = item["name"]
                label = f"{name}@{by_first_party[name]['source']['commit']}:{item['path']}"
                if skill_name in planned_skills:
                    collisions.append(f"{skill_name}: {planned_skills[skill_name]} vs {label}")
                planned_skills[skill_name] = label
            continue
        try:
            plugin_sources[name] = plugin_catalog.materialize(
                root,
                name,
                offline=args.offline or args.check_only,
                cache_root=args.first_party_cache_root,
            )
        except plugin_catalog.CatalogError as exc:
            print(f"{name}: verified first-party cache unavailable: {exc}", file=sys.stderr)
            return 1
    sources: dict[str, Path] = {}
    for name, plugin_dir in plugin_sources.items():
        for skill_dir in skill_dirs(plugin_dir):
            if skill_dir.name in sources or skill_dir.name in planned_skills:
                collisions.append(
                    f"{skill_dir.name}: {sources.get(skill_dir.name, planned_skills.get(skill_dir.name))} vs {skill_dir}"
                )
            sources[skill_dir.name] = skill_dir
            planned_skills[skill_dir.name] = str(skill_dir)
    if collisions:
        print("skill name collisions; nothing installed:", file=sys.stderr)
        for line in collisions:
            print(f"- {line}", file=sys.stderr)
        return 2

    if args.dry_run:
        for name in selected:
            if name in by_first_party:
                item = by_first_party[name]
                print(
                    f"would materialize verified pin: {name}@{item['source']['commit']} "
                    f"from {item['source']['repository']}"
                )
        for skill_name in sorted(planned_skills):
            dest = dest_root / skill_name
            action = "update" if dest.is_dir() else "install"
            print(f"would {action}: {skill_name} -> {dest}")
        print(
            f"dry-run: installed=0 updated=0 unchanged=0 dest={dest_root}"
        )
        return 0

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
    *,
    default_available: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    selection = resolve_selection(
        included,
        excluded,
        available=available,
        default_names=default_available,
    )
    if selection.unknown:
        return [], selection.unknown
    if selection.overlap:
        print(
            f"plugin(s) cannot be both selected and excluded: {', '.join(selection.overlap)}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if not selection.selected:
        print("no plugins selected after applying --exclude-plugin", file=sys.stderr)
        raise SystemExit(2)
    return selection.selected, []


if __name__ == "__main__":
    raise SystemExit(main())
