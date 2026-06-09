#!/usr/bin/env python3
"""Install repository plugins into the global Codex local marketplace."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLUGIN_NAMES = [
    "build-swift-apps",
    "pixijs",
    "tauri",
    "scientific-research",
    "context-density",
    "capability-workbench",
    "codex-cli",
    "claude-code",
    "architecture-intelligence",
    "design-intelligence",
    "game-design-intelligence",
    "kotlin-multiplatform",
    "spec-driven-development",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin",
        action="append",
        choices=PLUGIN_NAMES,
        help="Install one plugin. Repeat to install several. Defaults to all.",
    )
    parser.add_argument(
        "--global-source-root",
        default=None,
        help=(
            "Destination root for editable global Codex plugin sources. Defaults to this "
            "repository's plugins/ directory. Pass ~/plugins to refresh the legacy surface."
        ),
    )
    parser.add_argument(
        "--marketplace-path",
        default=None,
        help=(
            "Codex local marketplace JSON path. Defaults to <marketplace-root>/.agents/plugins/"
            "marketplace.json."
        ),
    )
    parser.add_argument(
        "--config-path",
        default=str(Path.home() / ".codex" / "config.toml"),
        help="Codex config.toml path.",
    )
    parser.add_argument(
        "--cache-root",
        default=str(Path.home() / ".codex" / "plugins" / "cache"),
        help="Codex plugin cache root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print intended writes without changing global state.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate repository source and verify current global Codex install state.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root()
    selected = args.plugin or PLUGIN_NAMES
    source_root = root / "plugins"
    global_source_root = (
        Path(args.global_source_root).expanduser().resolve()
        if args.global_source_root
        else source_root.resolve()
    )
    marketplace_root = (
        global_source_root.parent
        if args.global_source_root
        else root.resolve()
    )
    marketplace_path = (
        Path(args.marketplace_path).expanduser().resolve()
        if args.marketplace_path
        else marketplace_root / ".agents" / "plugins" / "marketplace.json"
    )
    config_path = Path(args.config_path).expanduser().resolve()
    cache_root = Path(args.cache_root).expanduser().resolve()

    validate_helper = root / "plugins" / "capability-workbench" / "scripts" / "plugin" / "validate_plugin.py"
    install_helper = root / "plugins" / "capability-workbench" / "scripts" / "plugin" / "ensure_local_plugin_installed.py"
    require_file(validate_helper)
    require_file(install_helper)

    manifests = {}
    for name in selected:
        plugin_dir = source_root / name
        require_file(plugin_dir / ".codex-plugin" / "plugin.json")
        run([sys.executable, str(validate_helper), str(plugin_dir)])
        manifests[name] = load_json(plugin_dir / ".codex-plugin" / "plugin.json")

    if args.check_only:
        for name in selected:
            destination = global_source_root / name
            run(
                [
                    sys.executable,
                    str(install_helper),
                    str(destination),
                    "--marketplace-path",
                    str(marketplace_path),
                    "--config-path",
                    str(config_path),
                    "--cache-root",
                    str(cache_root),
                    "--check-only",
                ]
            )
        print("check-only passed")
        return

    ensure_marketplace_file(
        marketplace_path=marketplace_path,
        manifests=manifests,
        dry_run=args.dry_run,
    )
    ensure_codex_marketplace_config(
        config_path=config_path,
        marketplace_root=marketplace_root,
        dry_run=args.dry_run,
    )

    for name in selected:
        source = source_root / name
        destination = global_source_root / name
        if source.resolve() != destination.resolve():
            sync_plugin_source(source, destination, dry_run=args.dry_run)
        if args.dry_run:
            print(f"would install {name}@local from {destination}")
            continue
        run(
            [
                sys.executable,
                str(install_helper),
                str(destination),
                "--marketplace-path",
                str(marketplace_path),
                "--config-path",
                str(config_path),
                "--cache-root",
                str(cache_root),
                "--force-manual",
            ]
        )

    print("install complete" if not args.dry_run else "dry run complete")


def require_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON file must contain an object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        print(f"would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def ensure_marketplace_file(
    *,
    marketplace_path: Path,
    manifests: dict[str, dict[str, Any]],
    dry_run: bool,
) -> None:
    if marketplace_path.exists():
        marketplace = load_json(marketplace_path)
    else:
        marketplace = {
            "name": "local",
            "interface": {"displayName": "Local Plugins"},
            "plugins": [],
        }

    marketplace["name"] = "local"
    marketplace.setdefault("interface", {"displayName": "Local Plugins"})
    plugins = marketplace.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise SystemExit(f"{marketplace_path} field 'plugins' must be an array")

    by_name: dict[str, dict[str, Any]] = {}
    passthrough: list[Any] = []
    for entry in plugins:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            by_name[entry["name"]] = entry
        else:
            passthrough.append(entry)

    for name, manifest in manifests.items():
        interface = manifest.get("interface")
        category = "Productivity"
        if isinstance(interface, dict) and isinstance(interface.get("category"), str):
            category = interface["category"]
        by_name[name] = {
            "name": name,
            "source": {"source": "local", "path": f"./plugins/{name}"},
            "policy": {
                "installation": "AVAILABLE",
                "authentication": "ON_INSTALL",
            },
            "category": category,
        }

    ordered_names = [name for name in PLUGIN_NAMES if name in by_name]
    ordered_names.extend(sorted(name for name in by_name if name not in ordered_names))
    marketplace["plugins"] = passthrough + [by_name[name] for name in ordered_names]
    marketplace["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json(marketplace_path, marketplace, dry_run=dry_run)


def ensure_codex_marketplace_config(
    *,
    config_path: Path,
    marketplace_root: Path,
    dry_run: bool,
) -> None:
    source_line = f'source = "{marketplace_root}"'
    desired_block = [
        "[marketplaces.local]",
        f'last_updated = "{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}"',
        'source_type = "local"',
        source_line,
    ]
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    lines = text.splitlines()
    start = find_section(lines, "[marketplaces.local]")
    if start is None:
        next_text = append_block(text, desired_block)
    else:
        end = next_section(lines, start + 1)
        block = lines[start:end]
        block = upsert_line(block, "source_type", 'source_type = "local"')
        block = upsert_line(block, "source", source_line)
        lines[start:end] = block
        next_text = "\n".join(lines).rstrip() + "\n"

    if next_text == (text if text.endswith("\n") or not text else text + "\n"):
        return
    if dry_run:
        print(f"would update {config_path}")
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(next_text, encoding="utf-8")


def find_section(lines: list[str], section: str) -> int | None:
    for index, line in enumerate(lines):
        if line.strip() == section:
            return index
    return None


def next_section(lines: list[str], start: int) -> int:
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            return index
    return len(lines)


def upsert_line(block: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key} ="
    for index, line in enumerate(block):
        if line.strip().startswith(prefix):
            block[index] = value
            return block
    block.append(value)
    return block


def append_block(text: str, block: list[str]) -> str:
    normalized = text if text.endswith("\n") or not text else text + "\n"
    if normalized and not normalized.endswith("\n\n"):
        normalized += "\n"
    return normalized + "\n".join(block) + "\n"


def sync_plugin_source(source: Path, destination: Path, *, dry_run: bool) -> None:
    if dry_run:
        print(f"would sync {source} -> {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsync"):
        run(
            [
                "rsync",
                "-a",
                "--delete",
                "--exclude",
                ".git",
                "--exclude",
                ".DS_Store",
                "--exclude",
                "__pycache__",
                "--exclude",
                "*.pyc",
                f"{source}/",
                f"{destination}/",
            ]
        )
        return
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", ".DS_Store", "__pycache__", "*.pyc"),
    )


if __name__ == "__main__":
    main()
