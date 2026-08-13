#!/usr/bin/env python3
"""Validate and install repository plugins through the Codex local marketplace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from agent_target import AgentResolutionError, resolve_codex_plugin_state_paths
import plugin_catalog


LOCAL_PLUGIN_NAMES = [
    "agent-harness",
    "capability-workbench",
    "context-density",
    "i-have-adhd",
    "git-workflows",
    "engineering-hygiene",
    "scientific-research",
    "technology-intelligence",
    "design-intelligence",
    "architecture-intelligence",
    "spec-driven-development",
    "kotlin-multiplatform",
    "tauri",
    "pixijs",
    "game-design-intelligence",
]


def catalog_payload(root: Path | None = None) -> dict[str, Any]:
    return plugin_catalog.validate_catalog(
        root or Path(__file__).resolve().parents[1]
    )


def all_plugin_names(root: Path | None = None) -> list[str]:
    payload = catalog_payload(root)
    return [*LOCAL_PLUGIN_NAMES, *(item["name"] for item in payload["plugins"])]


# Kept as a public compatibility surface for tests and callers that import the
# installer. The immutable catalog is validated before these names are exposed.
PLUGIN_NAMES = all_plugin_names()

LEGACY_PLUGIN_RENAMES = {
    "codex-cli": "agent-harness",
    "claude-code": "agent-harness",
    "scheduled-automation": "agent-harness",
    "gitlab-review": "git-workflows",
    "stacked-delivery": "git-workflows",
    "git-worktree-safety": "git-workflows",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin",
        action="append",
        choices=[*PLUGIN_NAMES, *LEGACY_PLUGIN_RENAMES],
        help=(
            "Install one local or pinned first-party plugin. Repeat to install "
            "several. Defaults to every local plugin."
        ),
    )
    parser.add_argument(
        "--exclude-plugin",
        action="append",
        choices=[*PLUGIN_NAMES, *LEGACY_PLUGIN_RENAMES],
        default=[],
        help=(
            "Exclude a plugin from the selected set. Repeat to exclude several. "
            "Useful for host-specific local installs."
        ),
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
        default=None,
        help=(
            "Codex config.toml path. Defaults to the active CODEX_HOME, "
            "or ~/.codex when unset."
        ),
    )
    parser.add_argument(
        "--cache-root",
        default=None,
        help=(
            "Codex plugin cache root. Defaults to the active CODEX_HOME, "
            "or ~/.codex when unset."
        ),
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
    parser.add_argument(
        "--include-first-party",
        action="store_true",
        help="Also include pinned first-party entries whose selection.default is true.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Never fetch; require selected standalone plugins in the verified cache.",
    )
    parser.add_argument(
        "--first-party-cache-root",
        default=None,
        help="Override the pinned standalone source cache root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run and args.check_only:
        raise SystemExit("--dry-run and --check-only cannot be combined")
    root = repo_root()
    payload = catalog_payload(root)
    first_party = {item["name"]: item for item in payload["plugins"]}
    default_names = list(LOCAL_PLUGIN_NAMES)
    if args.include_first_party:
        default_names.extend(plugin_catalog.default_plugin_names(payload))
    selected = select_plugins(
        args.plugin,
        args.exclude_plugin,
        available=all_plugin_names(root),
        default_names=default_names,
    )
    source_root = root / "plugins"
    global_source_root = (
        Path(args.global_source_root).expanduser().resolve()
        if args.global_source_root
        else source_root.resolve()
    )
    marketplace_root = (
        global_source_root.parent if args.global_source_root else root.resolve()
    )
    marketplace_path = (
        Path(args.marketplace_path).expanduser().resolve()
        if args.marketplace_path
        else marketplace_root / ".agents" / "plugins" / "marketplace.json"
    )
    try:
        state_paths = resolve_codex_plugin_state_paths(
            config_path=args.config_path,
            cache_root=args.cache_root,
        )
    except AgentResolutionError as exc:
        raise SystemExit(str(exc)) from exc
    config_path = state_paths.config_path
    cache_root = state_paths.cache_root

    validate_helper = (
        root
        / "plugins"
        / "capability-workbench"
        / "scripts"
        / "plugin"
        / "validate_plugin.py"
    )
    install_helper = (
        root
        / "plugins"
        / "capability-workbench"
        / "scripts"
        / "plugin"
        / "ensure_local_plugin_installed.py"
    )
    require_file(validate_helper)
    require_file(install_helper)

    manifests = {}
    repository_sources: dict[str, Path] = {}
    install_sources: dict[str, Path] = {}
    for name in selected:
        if name in first_party:
            plugin = first_party[name]
            planned_source = plugin_catalog.materialized_path(
                root, plugin, args.first_party_cache_root
            )
            if args.dry_run:
                repository_sources[name] = planned_source
                install_sources[name] = planned_source
                manifests[name] = {
                    "interface": {"category": "Productivity"},
                }
                print(
                    f"would materialize verified pin: {name}@{plugin['source']['commit']} "
                    f"from {plugin['source']['repository']}"
                )
                continue
            try:
                plugin_dir = plugin_catalog.materialize(
                    root,
                    name,
                    offline=args.offline or args.check_only,
                    cache_root=args.first_party_cache_root,
                    validator=validate_helper,
                )
            except plugin_catalog.CatalogError as exc:
                raise SystemExit(f"{name}: verified first-party cache unavailable: {exc}") from exc
            repository_sources[name] = plugin_dir
            install_sources[name] = plugin_dir
            manifests[name] = load_json(plugin_dir / ".codex-plugin" / "plugin.json")
            continue

        plugin_dir = source_root / name
        require_file(plugin_dir / ".codex-plugin" / "plugin.json")
        run([sys.executable, str(validate_helper), str(plugin_dir)])
        repository_sources[name] = plugin_dir
        destination = global_source_root / name
        install_sources[name] = destination
        manifests[name] = load_json(plugin_dir / ".codex-plugin" / "plugin.json")

    if args.check_only:
        for name in selected:
            repository_source = repository_sources[name]
            destination = install_sources[name]
            command = [
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
            if repository_source.resolve() != destination.resolve():
                command.extend(
                    [
                        "--expected-source-path",
                        str(repository_source),
                    ]
                )
            run(command)
        print("check-only passed")
        return

    retired_plugins = ensure_marketplace_file(
        marketplace_path=marketplace_path,
        canonical_source_root=source_root,
        manifests=manifests,
        dry_run=args.dry_run,
        source_paths=install_sources,
        marketplace_root=marketplace_root,
    )
    ensure_codex_marketplace_config(
        config_path=config_path,
        marketplace_root=marketplace_root,
        dry_run=args.dry_run,
    )

    for name in selected:
        source = repository_sources[name]
        destination = install_sources[name]
        if name not in first_party and source.resolve() != destination.resolve():
            sync_plugin_source(source, destination, dry_run=args.dry_run)
        if args.dry_run:
            print(f"would install {name}@local from {destination}")
            continue
        command = [
            sys.executable,
            str(install_helper),
            str(destination),
            "--marketplace-path",
            str(marketplace_path),
        ]
        if args.marketplace_path is not None or args.offline:
            command.extend(
                [
                    "--config-path",
                    str(config_path),
                    "--cache-root",
                    str(cache_root),
                    "--force-manual",
                ]
            )
        elif args.config_path is not None:
            command.extend(["--config-path", str(config_path)])
        if args.marketplace_path is None and args.cache_root is not None:
            command.extend(["--cache-root", str(cache_root)])
        if source.resolve() != destination.resolve():
            command.extend(
                [
                    "--expected-source-path",
                    str(source),
                ]
            )
        run(command)

    legacy_targets = set(LEGACY_PLUGIN_RENAMES.values())
    for target_plugin in selected:
        if target_plugin in legacy_targets:
            report_legacy_plugin_residuals(
                target_plugin=target_plugin,
                config_path=config_path,
                cache_root=cache_root,
                global_source_root=global_source_root,
            )
    if retired_plugins:
        report_plugin_residuals(
            plugin_names=retired_plugins,
            heading=(
                "retired plugin residuals detected; no residual was deleted "
                "automatically:"
            ),
            remediation=(
                "Use the host's explicit uninstall/disable lifecycle for each "
                "retired ID."
            ),
            config_path=config_path,
            cache_root=cache_root,
            global_source_root=global_source_root,
        )

    print("install complete" if not args.dry_run else "dry run complete")


def select_plugins(
    included: list[str] | None,
    excluded: list[str],
    *,
    available: list[str] | None = None,
    default_names: list[str] | None = None,
) -> list[str]:
    known = set(available or PLUGIN_NAMES)
    canonical_included = list(
        dict.fromkeys(
            LEGACY_PLUGIN_RENAMES.get(name, name) for name in (included or [])
        )
    )
    canonical_excluded = list(
        dict.fromkeys(LEGACY_PLUGIN_RENAMES.get(name, name) for name in excluded)
    )
    unknown = sorted((set(canonical_included) | set(canonical_excluded)) - known)
    if unknown:
        raise SystemExit("unknown plugin(s): " + ", ".join(unknown))
    include_set = canonical_included if included else list(
        default_names if default_names is not None else LOCAL_PLUGIN_NAMES
    )
    excluded_set = set(canonical_excluded)
    overlap = sorted(set(canonical_included) & excluded_set)
    if overlap:
        raise SystemExit(
            "plugin(s) cannot be both selected and excluded: " + ", ".join(overlap)
        )
    selected = [name for name in include_set if name not in excluded_set]
    if not selected:
        raise SystemExit("no plugins selected after applying --exclude-plugin")
    return selected


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
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(command, check=True, env=environment)


def ensure_marketplace_file(
    *,
    marketplace_path: Path,
    canonical_source_root: Path,
    manifests: dict[str, dict[str, Any]],
    dry_run: bool,
    source_paths: dict[str, Path] | None = None,
    marketplace_root: Path | None = None,
) -> list[str]:
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

    retired_plugins = sorted(
        name
        for name, entry in by_name.items()
        if name not in manifests
        and name not in LEGACY_PLUGIN_RENAMES
        and is_missing_repo_owned_entry(
            name=name,
            entry=entry,
            canonical_source_root=canonical_source_root,
        )
    )
    for retired_name in retired_plugins:
        del by_name[retired_name]
    if retired_plugins:
        action = "would retire" if dry_run else "retired"
        print(f"{action} marketplace entries: " + ", ".join(retired_plugins))

    for target_plugin in manifests:
        removed_legacy = sorted(
            legacy_name
            for legacy_name, canonical_name in LEGACY_PLUGIN_RENAMES.items()
            if canonical_name == target_plugin and legacy_name in by_name
        )
        for legacy_name in removed_legacy:
            del by_name[legacy_name]
        if removed_legacy:
            action = "would migrate" if dry_run else "migrated"
            print(
                f"{action} legacy marketplace entries: "
                + ", ".join(removed_legacy)
                + f" -> {target_plugin}"
            )

    for name, manifest in manifests.items():
        interface = manifest.get("interface")
        category = "Productivity"
        if isinstance(interface, dict) and isinstance(interface.get("category"), str):
            category = interface["category"]
        source_path = (
            source_paths[name]
            if source_paths is not None and name in source_paths
            else canonical_source_root / name
        )
        root_for_paths = marketplace_root or canonical_source_root.parent
        try:
            rendered_path = source_path.resolve().relative_to(root_for_paths.resolve()).as_posix()
            rendered_path = f"./{rendered_path}"
        except ValueError:
            rendered_path = source_path.resolve().as_posix()
        by_name[name] = {
            "name": name,
            "source": {"source": "local", "path": rendered_path},
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
    return retired_plugins


def is_missing_repo_owned_entry(
    *,
    name: str,
    entry: dict[str, Any],
    canonical_source_root: Path,
) -> bool:
    source = entry.get("source")
    return (
        source == {"source": "local", "path": f"./plugins/{name}"}
        and not (canonical_source_root / name).exists()
    )


def ensure_codex_marketplace_config(
    *,
    config_path: Path,
    marketplace_root: Path,
    dry_run: bool,
) -> None:
    source_line = f"source = {toml_basic_string(str(marketplace_root))}"
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


def toml_basic_string(value: str) -> str:
    escaped: list[str] = []
    for char in value:
        if char == "\\":
            escaped.append("\\\\")
        elif char == '"':
            escaped.append('\\"')
        elif char == "\b":
            escaped.append("\\b")
        elif char == "\t":
            escaped.append("\\t")
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\f":
            escaped.append("\\f")
        elif char == "\r":
            escaped.append("\\r")
        elif ord(char) < 0x20:
            escaped.append(f"\\u{ord(char):04x}")
        else:
            escaped.append(char)
    return f'"{"".join(escaped)}"'


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


def report_legacy_plugin_residuals(
    *,
    target_plugin: str = "git-workflows",
    config_path: Path,
    cache_root: Path,
    global_source_root: Path,
) -> bool:
    """Report legacy plugin state for one canonical replacement without mutation."""
    legacy_names = sorted(
        legacy_name
        for legacy_name, canonical_name in LEGACY_PLUGIN_RENAMES.items()
        if canonical_name == target_plugin
    )
    return report_plugin_residuals(
        plugin_names=legacy_names,
        heading=(
            f"legacy {target_plugin} plugin residuals detected; no residual was deleted "
            "automatically:"
        ),
        remediation=(
            f"Verify {target_plugin} first, then use the host's explicit "
            "uninstall/disable lifecycle for each legacy ID."
        ),
        config_path=config_path,
        cache_root=cache_root,
        global_source_root=global_source_root,
    )


def report_plugin_residuals(
    *,
    plugin_names: list[str] | tuple[str, ...] | set[str] | dict[str, str],
    heading: str,
    remediation: str,
    config_path: Path,
    cache_root: Path,
    global_source_root: Path,
) -> bool:
    """Report plugin config/cache/source residuals without mutating them."""
    config_text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    config_lines = config_text.splitlines()
    enabled_ids: list[str] = []
    cache_paths: list[Path] = []
    source_paths: list[Path] = []

    for plugin_name in plugin_names:
        plugin_id = f"{plugin_name}@local"
        section = find_section(config_lines, f'[plugins."{plugin_id}"]')
        if section is not None:
            end = next_section(config_lines, section + 1)
            if any(
                line.strip() == "enabled = true"
                for line in config_lines[section + 1 : end]
            ):
                enabled_ids.append(plugin_id)

        cache_path = cache_root / "local" / plugin_name
        if cache_path.exists():
            cache_paths.append(cache_path)
        source_path = global_source_root / plugin_name
        if source_path.exists():
            source_paths.append(source_path)

    if not (enabled_ids or cache_paths or source_paths):
        return False

    print(heading)
    if enabled_ids:
        print("- enabled config IDs: " + ", ".join(enabled_ids))
    if cache_paths:
        print("- cache paths: " + ", ".join(str(path) for path in cache_paths))
    if source_paths:
        print("- source paths: " + ", ".join(str(path) for path in source_paths))
    print(remediation)
    return True


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
