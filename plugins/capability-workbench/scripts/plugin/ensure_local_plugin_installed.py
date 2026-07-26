#!/usr/bin/env python3
"""Ensure a local marketplace plugin has an enabled, cache-equivalent install.

Codex-specific by design: Codex is the only supported marketplace/cache/config
surface, so this script always targets Codex paths regardless of the host agent
running it. For Claude or Cursor hosts, plugin activation goes through the
host's own mechanism; report source path plus validation instead of this gate.
Runtime discovery is a separate proof and is never claimed by this helper.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    tomllib = None  # type: ignore[assignment]

_SCRIPT_PATH = Path(__file__).resolve()
for _agent_target in (
    _SCRIPT_PATH.parents[1] / "agent_target.py",
    _SCRIPT_PATH.parents[4] / "scripts" / "agent_target.py",
):
    if _agent_target.is_file():
        sys.path.insert(0, str(_agent_target.parent))
        break
from agent_target import resolve_agent  # noqa: E402

from validate_plugin import validate_plugin  # noqa: E402


MARKETPLACE_SECTION_RE = re.compile(r"^\s*\[marketplaces\.[^\]]+\]\s*$")
TABLE_HEADER_RE = re.compile(r"^\s*\[[^\]]+\]\s*$")
ENABLED_RE = re.compile(r"^\s*enabled\s*=")
SAFE_INSTALL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
CACHE_IGNORE_PATTERNS = (".git", "__pycache__", "*.pyc", ".DS_Store")
FILE_HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class InstallOutcome:
    plugin_id: str
    marketplace_name: str
    source_path: Path
    cache_path: Path
    mode: str
    config_changed: bool
    cache_changed: bool
    source_validated: bool
    install_state_verified: bool
    expected_source_path: Path | None
    expected_source_verified: bool | None


@dataclass(frozen=True)
class TreeEntry:
    kind: str
    mode: int
    size: int
    content_digest: str


def default_marketplace_path() -> Path:
    return resolve_agent(explicit="codex").marketplace_path


def default_config_path() -> Path:
    return resolve_agent(explicit="codex").home_dir / "config.toml"


def default_cache_root() -> Path:
    return resolve_agent(explicit="codex").home_dir / "plugins" / "cache"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install or verify a local Codex plugin from a marketplace entry. Uses "
            "`codex plugin add` when this CLI supports it; otherwise writes the installed-plugin "
            "config/cache state that current local Codex builds load."
        )
    )
    parser.add_argument("plugin_path", help="Path to the local plugin root")
    parser.add_argument(
        "--marketplace-path",
        default=str(default_marketplace_path()),
        help="Path to marketplace.json (defaults to the personal marketplace)",
    )
    parser.add_argument(
        "--config-path",
        default=str(default_config_path()),
        help="Path to Codex config.toml",
    )
    parser.add_argument(
        "--cache-root",
        default=str(default_cache_root()),
        help="Root of Codex plugin cache",
    )
    parser.add_argument(
        "--expected-source-path",
        help=(
            "Optional upstream source that the selected marketplace source must "
            "exactly match under the installable-tree projection"
        ),
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex CLI executable to use when plugin add is supported",
    )
    parser.add_argument(
        "--force-manual",
        action="store_true",
        help="Skip CLI install and materialize config/cache directly",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Verify marketplace source, enabled config, and filtered source/cache "
            "content equivalence without making changes"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended changes without writing config or cache",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        outcome = ensure_installed(
            plugin_path=Path(args.plugin_path),
            marketplace_path=Path(args.marketplace_path),
            config_path=Path(args.config_path),
            cache_root=Path(args.cache_root),
            codex_bin=args.codex_bin,
            expected_source_path=(
                Path(args.expected_source_path)
                if args.expected_source_path is not None
                else None
            ),
            force_manual=args.force_manual,
            check_only=args.check_only,
            dry_run=args.dry_run,
        )
    except Exception as err:  # noqa: BLE001 - CLI should return one clear error.
        print(str(err), file=sys.stderr)
        raise SystemExit(1) from err

    print(f"plugin id: {outcome.plugin_id}")
    print(f"marketplace: {outcome.marketplace_name}")
    print(f"source path: {outcome.source_path}")
    print(f"cache path: {outcome.cache_path}")
    print(f"install mode: {outcome.mode}")
    if outcome.mode == "dry-run":
        print(f"config change required: {str(outcome.config_changed).lower()}")
        print(f"cache refresh required: {str(outcome.cache_changed).lower()}")
    else:
        print(f"config changed: {str(outcome.config_changed).lower()}")
        print(f"cache changed: {str(outcome.cache_changed).lower()}")
    print(f"source validated: {str(outcome.source_validated).lower()}")
    if outcome.expected_source_path is not None:
        print(f"expected source path: {outcome.expected_source_path}")
        print(
            "expected source matches selected source: "
            f"{str(outcome.expected_source_verified).lower()}"
        )
    print(
        "install/cache state verified: "
        f"{str(outcome.install_state_verified).lower()}"
    )
    print("runtime discovery: not checked")


def ensure_installed(
    *,
    plugin_path: Path,
    marketplace_path: Path,
    config_path: Path,
    cache_root: Path,
    codex_bin: str,
    expected_source_path: Path | None = None,
    force_manual: bool = False,
    check_only: bool = False,
    dry_run: bool = False,
) -> InstallOutcome:
    if check_only and dry_run:
        raise ValueError("--check-only and --dry-run cannot be combined")

    plugin_input = plugin_path.expanduser()
    cache_input = cache_root.expanduser()
    ensure_root_is_not_symlink(plugin_input, "plugin source root")
    ensure_root_is_not_symlink(cache_input, "plugin cache root")

    plugin_root = plugin_input.resolve()
    marketplace_file = marketplace_path.expanduser().resolve()
    config_file = config_path.expanduser().resolve()
    cache_base = cache_input.resolve()

    source_before_validation = build_installable_tree_manifest(plugin_root)
    manifest = load_manifest(plugin_root)
    plugin_name = require_string(
        manifest, "name", plugin_root / ".codex-plugin" / "plugin.json"
    )
    ensure_safe_install_id_component(plugin_name, "plugin name")
    version = require_string(
        manifest, "version", plugin_root / ".codex-plugin" / "plugin.json"
    )

    validation_errors = validate_plugin(plugin_root)
    if validation_errors:
        formatted = "\n".join(f"- {error}" for error in validation_errors)
        raise ValueError(f"plugin validation failed for {plugin_root}:\n{formatted}")
    validated_source_entries = build_installable_tree_manifest(plugin_root)
    ensure_snapshot_unchanged(
        source_before_validation,
        validated_source_entries,
        "plugin source changed during validation",
    )

    marketplace = load_json_object(marketplace_file)
    marketplace_name = require_string(marketplace, "name", marketplace_file)
    ensure_safe_install_id_component(marketplace_name, "marketplace name")
    marketplace_root = infer_marketplace_root(
        marketplace_file=marketplace_file,
        marketplace_name=marketplace_name,
        config_path=config_file,
    )
    source_path = resolve_marketplace_source(
        marketplace=marketplace,
        marketplace_path=marketplace_file,
        marketplace_root=marketplace_root,
        plugin_name=plugin_name,
    )
    ensure_same_plugin_source(source_path, plugin_root, marketplace_file, plugin_name)

    plugin_id = f"{plugin_name}@{marketplace_name}"
    cache_path = cache_base / marketplace_name / plugin_name / version
    ensure_path_within_cache_root(cache_path, cache_base)
    ensure_cache_path_has_no_symlink_components(
        cache_path=cache_path,
        cache_root=cache_base,
    )
    ensure_disjoint_install_paths(plugin_root=plugin_root, cache_path=cache_path)

    expected_source_root, validated_expected_entries = verify_expected_source(
        expected_source_path=expected_source_path,
        selected_source_root=plugin_root,
        validated_selected_entries=validated_source_entries,
        plugin_name=plugin_name,
        version=version,
    )
    if expected_source_root is not None:
        ensure_disjoint_install_paths(
            plugin_root=expected_source_root,
            cache_path=cache_path,
        )

    if check_only:
        ensure_installation_receipt(
            plugin_root=plugin_root,
            cache_path=cache_path,
            validated_source_entries=validated_source_entries,
            expected_source_root=expected_source_root,
            validated_expected_entries=validated_expected_entries,
            config_file=config_file,
            plugin_id=plugin_id,
            marketplace_file=marketplace_file,
            marketplace_name=marketplace_name,
            plugin_name=plugin_name,
        )
        return InstallOutcome(
            plugin_id=plugin_id,
            marketplace_name=marketplace_name,
            source_path=source_path,
            cache_path=cache_path,
            mode="check-only",
            config_changed=False,
            cache_changed=False,
            source_validated=True,
            install_state_verified=True,
            expected_source_path=expected_source_root,
            expected_source_verified=(
                True if expected_source_root is not None else None
            ),
        )

    if not force_manual and not dry_run:
        if resolve_agent(explicit="codex").agent == "codex":
            cli_result = try_cli_install(codex_bin, plugin_id)
        else:
            cli_result = None
        if cli_result == "installed":
            ensure_installation_receipt(
                plugin_root=plugin_root,
                cache_path=cache_path,
                validated_source_entries=validated_source_entries,
                expected_source_root=expected_source_root,
                validated_expected_entries=validated_expected_entries,
                config_file=config_file,
                plugin_id=plugin_id,
                marketplace_file=marketplace_file,
                marketplace_name=marketplace_name,
                plugin_name=plugin_name,
            )
            return InstallOutcome(
                plugin_id=plugin_id,
                marketplace_name=marketplace_name,
                source_path=source_path,
                cache_path=cache_path,
                mode="codex-cli",
                config_changed=False,
                cache_changed=False,
                source_validated=True,
                install_state_verified=True,
                expected_source_path=expected_source_root,
                expected_source_verified=(
                    True if expected_source_root is not None else None
                ),
            )
        # None means CLI was skipped (non-Codex agent); treat as "fall through to manual"
        if cli_result is not None and cli_result != "unsupported":
            raise RuntimeError(cli_result)

    config_changed = ensure_config_enabled(
        config_file, plugin_id, write=True, dry_run=dry_run
    )
    cache_changed = ensure_cache_materialized(
        plugin_root=plugin_root,
        cache_path=cache_path,
        dry_run=dry_run,
    )
    if dry_run:
        install_state_verified = False
    else:
        ensure_installation_receipt(
            plugin_root=plugin_root,
            cache_path=cache_path,
            validated_source_entries=validated_source_entries,
            expected_source_root=expected_source_root,
            validated_expected_entries=validated_expected_entries,
            config_file=config_file,
            plugin_id=plugin_id,
            marketplace_file=marketplace_file,
            marketplace_name=marketplace_name,
            plugin_name=plugin_name,
        )
        install_state_verified = True
    return InstallOutcome(
        plugin_id=plugin_id,
        marketplace_name=marketplace_name,
        source_path=source_path,
        cache_path=cache_path,
        mode="dry-run" if dry_run else "manual-fallback",
        config_changed=config_changed,
        cache_changed=cache_changed,
        source_validated=True,
        install_state_verified=install_state_verified,
        expected_source_path=expected_source_root,
        expected_source_verified=True if expected_source_root is not None else None,
    )


def load_manifest(plugin_root: Path) -> dict[str, Any]:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"missing plugin manifest: {manifest_path}")
    return load_json_object(manifest_path)


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"missing JSON file: {path}") from None
    except json.JSONDecodeError as err:
        raise ValueError(f"{path} must contain valid JSON: {err}") from err
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def require_string(payload: dict[str, Any], key: str, source: Path) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source} must contain a non-empty string '{key}'")
    return value.strip()


def verify_expected_source(
    *,
    expected_source_path: Path | None,
    selected_source_root: Path,
    validated_selected_entries: dict[str, TreeEntry],
    plugin_name: str,
    version: str,
) -> tuple[Path | None, dict[str, TreeEntry] | None]:
    if expected_source_path is None:
        selected_snapshot = read_stable_tree_snapshots([selected_source_root])[0]
        ensure_snapshot_unchanged(
            validated_selected_entries,
            selected_snapshot,
            "plugin source changed after validation",
        )
        return None, None

    expected_input = expected_source_path.expanduser()
    ensure_root_is_not_symlink(expected_input, "expected plugin source root")
    expected_root = expected_input.resolve()
    expected_before_validation = build_installable_tree_manifest(expected_root)

    expected_manifest = load_manifest(expected_root)
    expected_name = require_string(
        expected_manifest,
        "name",
        expected_root / ".codex-plugin" / "plugin.json",
    )
    ensure_safe_install_id_component(expected_name, "expected plugin name")
    expected_version = require_string(
        expected_manifest,
        "version",
        expected_root / ".codex-plugin" / "plugin.json",
    )
    validation_errors = validate_plugin(expected_root)
    if validation_errors:
        formatted = "\n".join(f"- {error}" for error in validation_errors)
        raise ValueError(
            f"expected plugin source validation failed for {expected_root}:\n"
            f"{formatted}"
        )
    validated_expected_entries = build_installable_tree_manifest(expected_root)
    ensure_snapshot_unchanged(
        expected_before_validation,
        validated_expected_entries,
        "expected plugin source changed during validation",
    )
    if expected_name != plugin_name or expected_version != version:
        raise ValueError(
            "expected plugin source identity does not match the selected "
            "marketplace source"
        )

    expected_snapshot, selected_snapshot = read_stable_tree_snapshots(
        [expected_root, selected_source_root]
    )
    ensure_snapshot_unchanged(
        validated_expected_entries,
        expected_snapshot,
        "expected plugin source changed after validation",
    )
    ensure_snapshot_unchanged(
        validated_selected_entries,
        selected_snapshot,
        "plugin source changed after validation",
    )
    compare_installable_tree_manifests(
        expected_entries=expected_snapshot,
        actual_entries=selected_snapshot,
        mismatch_subject=(
            "selected marketplace source does not match expected plugin source"
        ),
        remediation=(
            "Refresh the selected marketplace source from the expected source "
            "before claiming source provenance."
        ),
    )
    return expected_root, validated_expected_entries


def ensure_safe_install_id_component(value: str, label: str) -> None:
    if SAFE_INSTALL_ID_RE.fullmatch(value) is None:
        raise ValueError(
            f"{label} must start with an ASCII letter or digit and contain only "
            "ASCII letters, digits, `_`, and `-`"
        )


def infer_marketplace_root(
    *,
    marketplace_file: Path,
    marketplace_name: str,
    config_path: Path,
) -> Path:
    configured_root = configured_marketplace_root(config_path, marketplace_name)
    if configured_root is not None:
        return configured_root
    if (
        marketplace_file.name == "marketplace.json"
        and marketplace_file.parent.name == "plugins"
        and marketplace_file.parent.parent.name == ".agents"
    ):
        return marketplace_file.parent.parent.parent.resolve()
    return marketplace_file.parent.resolve()


def configured_marketplace_root(
    config_path: Path, marketplace_name: str
) -> Path | None:
    if tomllib is None or not config_path.is_file():
        return None
    config = parse_toml(config_path)
    marketplaces = config.get("marketplaces")
    if not isinstance(marketplaces, dict):
        return None
    entry = marketplaces.get(marketplace_name)
    if not isinstance(entry, dict):
        return None
    if entry.get("source_type") != "local":
        return None
    source = entry.get("source")
    if not isinstance(source, str) or not source.strip():
        return None
    return Path(source).expanduser().resolve()


def parse_toml(path: Path) -> dict[str, Any]:
    try:
        if tomllib is not None:
            with path.open("rb") as handle:
                payload = tomllib.load(handle)
        else:
            payload = parse_minimal_toml(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except TOML_DECODE_ERROR as err:
        raise ValueError(f"{path} must contain valid TOML: {err}") from err
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a TOML object")
    return payload


if tomllib is not None:
    TOML_DECODE_ERROR = tomllib.TOMLDecodeError
else:
    TOML_DECODE_ERROR = ValueError


def parse_minimal_toml(text: str) -> dict[str, Any]:
    """Parse the simple table/string/bool subset needed for Codex plugin config."""
    payload: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            current = payload
            for part in split_toml_section(section):
                current = current.setdefault(part, {})
                if not isinstance(current, dict):
                    raise ValueError(f"invalid TOML table: [{section}]")
            continue
        if current is None or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            continue
        current[key] = parse_minimal_toml_value(raw_value)
    return payload


def split_toml_section(section: str) -> list[str]:
    parts: list[str] = []
    token = []
    in_quote = False
    escape = False
    for char in section:
        if escape:
            token.append(char)
            escape = False
            continue
        if char == "\\" and in_quote:
            escape = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if char == "." and not in_quote:
            part = "".join(token).strip()
            if part:
                parts.append(part)
            token = []
            continue
        token.append(char)
    part = "".join(token).strip()
    if part:
        parts.append(part)
    if in_quote:
        raise ValueError(f"unterminated quoted TOML section: [{section}]")
    return parts


def parse_minimal_toml_value(raw_value: str) -> Any:
    value = raw_value.split("#", 1)[0].strip()
    if value == "true":
        return True
    if value == "false":
        return False
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def resolve_marketplace_source(
    *,
    marketplace: dict[str, Any],
    marketplace_path: Path,
    marketplace_root: Path,
    plugin_name: str,
) -> Path:
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        raise ValueError(f"{marketplace_path} field 'plugins' must be an array")
    for entry in plugins:
        if not isinstance(entry, dict) or entry.get("name") != plugin_name:
            continue
        source = entry.get("source")
        if not isinstance(source, dict):
            raise ValueError(
                f"marketplace entry '{plugin_name}' source must be an object"
            )
        if source.get("source") != "local":
            raise ValueError(f"marketplace entry '{plugin_name}' must use local source")
        raw_path = source.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(
                f"marketplace entry '{plugin_name}' source.path must be non-empty"
            )
        source_path = Path(raw_path)
        if not source_path.is_absolute():
            source_path = marketplace_root / source_path
        source_input = source_path.expanduser()
        ensure_root_is_not_symlink(source_input, "marketplace plugin source root")
        return source_input.resolve()
    raise ValueError(f"{marketplace_path} has no marketplace entry for '{plugin_name}'")


def ensure_same_plugin_source(
    source_path: Path,
    plugin_root: Path,
    marketplace_path: Path,
    plugin_name: str,
) -> None:
    if not source_path.exists():
        raise FileNotFoundError(
            f"marketplace entry '{plugin_name}' in {marketplace_path} resolves to missing "
            f"source path: {source_path}"
        )
    if not plugin_root.exists():
        raise FileNotFoundError(f"plugin path does not exist: {plugin_root}")
    try:
        if source_path.samefile(plugin_root):
            return
    except OSError:
        pass
    raise ValueError(
        f"marketplace entry '{plugin_name}' resolves to {source_path}, not the plugin being "
        f"installed: {plugin_root}"
    )


def try_cli_install(codex_bin: str, plugin_id: str) -> str:
    try:
        result = subprocess.run(
            [codex_bin, "plugin", "add", plugin_id],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        return "unsupported"
    except subprocess.TimeoutExpired as err:
        raise RuntimeError(f"`{codex_bin} plugin add {plugin_id}` timed out") from err

    combined = f"{result.stdout}\n{result.stderr}".lower()
    if result.returncode == 0:
        return "installed"
    if "unrecognized subcommand" in combined or "usage: codex plugin" in combined:
        return "unsupported"
    return (
        f"`{codex_bin} plugin add {plugin_id}` failed with exit code {result.returncode}:\n"
        f"{result.stdout}{result.stderr}"
    )


def ensure_config_enabled(
    config_path: Path,
    plugin_id: str,
    *,
    write: bool = False,
    dry_run: bool = False,
) -> bool:
    text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    changed, next_text = config_with_plugin_enabled(text, plugin_id)
    if not changed:
        if config_path.is_file():
            parse_toml(config_path)
        return False
    if not write:
        raise ValueError(f'{config_path} does not enable [plugins."{plugin_id}"]')
    if dry_run:
        return True
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(next_text, encoding="utf-8")
    parse_toml(config_path)
    return True


def config_with_plugin_enabled(text: str, plugin_id: str) -> tuple[bool, str]:
    section = f'[plugins."{plugin_id}"]'
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != section:
            continue
        end = next_section_index(lines, index + 1)
        for enabled_index in range(index + 1, end):
            if ENABLED_RE.match(lines[enabled_index]):
                if lines[enabled_index].strip() == "enabled = true":
                    return False, ensure_trailing_newline(text)
                lines[enabled_index] = "enabled = true"
                return True, "\n".join(lines) + "\n"
        lines.insert(index + 1, "enabled = true")
        return True, "\n".join(lines) + "\n"

    insert_at = first_marketplace_section_index(lines)
    block = [section, "enabled = true", ""]
    if insert_at is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(block)
    else:
        if insert_at > 0 and lines[insert_at - 1].strip():
            block.insert(0, "")
        lines[insert_at:insert_at] = block
    return True, "\n".join(lines).rstrip() + "\n"


def ensure_trailing_newline(text: str) -> str:
    return text if not text or text.endswith("\n") else text + "\n"


def next_section_index(lines: list[str], start: int) -> int:
    for index in range(start, len(lines)):
        if TABLE_HEADER_RE.match(lines[index]):
            return index
    return len(lines)


def first_marketplace_section_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if MARKETPLACE_SECTION_RE.match(line):
            return index
    return None


def ensure_cache_materialized(
    *,
    plugin_root: Path,
    cache_path: Path,
    dry_run: bool,
) -> bool:
    ensure_disjoint_install_paths(plugin_root=plugin_root, cache_path=cache_path)
    build_installable_tree_manifest(plugin_root)
    if dry_run:
        return True
    if cache_path.is_symlink():
        raise ValueError("plugin cache root must not be a symlink")
    if cache_path.exists():
        shutil.rmtree(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        plugin_root,
        cache_path,
        ignore=ignored_cache_entry_names,
        symlinks=True,
    )
    try:
        build_installable_tree_manifest(cache_path)
    except Exception:
        shutil.rmtree(cache_path)
        raise
    return True


def ensure_installation_receipt(
    *,
    plugin_root: Path,
    cache_path: Path,
    validated_source_entries: dict[str, TreeEntry],
    expected_source_root: Path | None,
    validated_expected_entries: dict[str, TreeEntry] | None,
    config_file: Path,
    plugin_id: str,
    marketplace_file: Path,
    marketplace_name: str,
    plugin_name: str,
) -> None:
    control_before = capture_control_plane_snapshot(
        plugin_root=plugin_root,
        config_file=config_file,
        plugin_id=plugin_id,
        marketplace_file=marketplace_file,
        marketplace_name=marketplace_name,
        plugin_name=plugin_name,
    )
    ensure_installation_state_matches(
        plugin_root=plugin_root,
        cache_path=cache_path,
        validated_source_entries=validated_source_entries,
        expected_source_root=expected_source_root,
        validated_expected_entries=validated_expected_entries,
    )
    control_after = capture_control_plane_snapshot(
        plugin_root=plugin_root,
        config_file=config_file,
        plugin_id=plugin_id,
        marketplace_file=marketplace_file,
        marketplace_name=marketplace_name,
        plugin_name=plugin_name,
    )
    if control_before != control_after:
        raise ValueError("plugin control-plane changed during verification")


def capture_control_plane_snapshot(
    *,
    plugin_root: Path,
    config_file: Path,
    plugin_id: str,
    marketplace_file: Path,
    marketplace_name: str,
    plugin_name: str,
) -> tuple[bytes, bytes]:
    try:
        config_before = config_file.read_bytes()
    except FileNotFoundError:
        raise ValueError(
            f'{config_file} does not enable [plugins."{plugin_id}"]'
        ) from None
    marketplace_before = marketplace_file.read_bytes()

    ensure_config_enabled(config_file, plugin_id)
    marketplace = load_json_object(marketplace_file)
    current_marketplace_name = require_string(
        marketplace,
        "name",
        marketplace_file,
    )
    ensure_safe_install_id_component(
        current_marketplace_name,
        "marketplace name",
    )
    if current_marketplace_name != marketplace_name:
        raise ValueError("selected marketplace changed during verification")
    marketplace_root = infer_marketplace_root(
        marketplace_file=marketplace_file,
        marketplace_name=marketplace_name,
        config_path=config_file,
    )
    source_path = resolve_marketplace_source(
        marketplace=marketplace,
        marketplace_path=marketplace_file,
        marketplace_root=marketplace_root,
        plugin_name=plugin_name,
    )
    ensure_same_plugin_source(
        source_path,
        plugin_root,
        marketplace_file,
        plugin_name,
    )

    config_after = config_file.read_bytes()
    marketplace_after = marketplace_file.read_bytes()
    if config_before != config_after or marketplace_before != marketplace_after:
        raise ValueError("plugin control-plane changed during verification")
    return config_after, marketplace_after


def ensure_installation_state_matches(
    *,
    plugin_root: Path,
    cache_path: Path,
    validated_source_entries: dict[str, TreeEntry],
    expected_source_root: Path | None,
    validated_expected_entries: dict[str, TreeEntry] | None,
) -> None:
    ensure_disjoint_install_paths(plugin_root=plugin_root, cache_path=cache_path)

    roots = (
        [expected_source_root, plugin_root, cache_path]
        if expected_source_root is not None
        else [plugin_root, cache_path]
    )
    snapshots = read_stable_tree_snapshots(roots)
    if expected_source_root is not None:
        if validated_expected_entries is None:
            raise ValueError("expected source validation snapshot is missing")
        expected_snapshot, selected_snapshot, cache_snapshot = snapshots
        ensure_snapshot_unchanged(
            validated_expected_entries,
            expected_snapshot,
            "expected plugin source changed after validation",
        )
        compare_installable_tree_manifests(
            expected_entries=expected_snapshot,
            actual_entries=selected_snapshot,
            mismatch_subject=(
                "selected marketplace source does not match expected plugin source"
            ),
            remediation=(
                "Refresh the selected marketplace source from the expected source "
                "before claiming source provenance."
            ),
        )
    else:
        selected_snapshot, cache_snapshot = snapshots

    ensure_snapshot_unchanged(
        validated_source_entries,
        selected_snapshot,
        "plugin source changed after validation",
    )
    compare_installable_tree_manifests(
        expected_entries=selected_snapshot,
        actual_entries=cache_snapshot,
        mismatch_subject="cache content does not match plugin source",
        remediation=(
            "Refresh the selected local plugin cache before claiming "
            "install/cache equivalence."
        ),
    )


def ensure_installable_trees_match(
    *,
    expected_root: Path,
    actual_root: Path,
    mismatch_subject: str,
    remediation: str,
) -> None:
    expected_entries, actual_entries = read_stable_tree_snapshots(
        [expected_root, actual_root]
    )
    compare_installable_tree_manifests(
        expected_entries=expected_entries,
        actual_entries=actual_entries,
        mismatch_subject=mismatch_subject,
        remediation=remediation,
    )


def read_stable_tree_snapshots(
    roots: list[Path],
) -> list[dict[str, TreeEntry]]:
    first_snapshots = [build_installable_tree_manifest(root) for root in roots]
    confirmation_snapshots = [build_installable_tree_manifest(root) for root in roots]
    if first_snapshots != confirmation_snapshots:
        raise ValueError(
            "plugin trees changed during verification; retry only after all "
            "trees are stable"
        )
    return confirmation_snapshots


def ensure_snapshot_unchanged(
    expected: dict[str, TreeEntry],
    actual: dict[str, TreeEntry],
    message: str,
) -> None:
    if expected != actual:
        raise ValueError(message)


def compare_installable_tree_manifests(
    *,
    expected_entries: dict[str, TreeEntry],
    actual_entries: dict[str, TreeEntry],
    mismatch_subject: str,
    remediation: str,
) -> None:
    expected_paths = set(expected_entries)
    actual_paths = set(actual_entries)
    missing = expected_paths - actual_paths
    unexpected = actual_paths - expected_paths
    type_differences: list[str] = []
    mode_differences: list[str] = []
    content_differences: list[str] = []

    for relative_path in expected_paths & actual_paths:
        expected_entry = expected_entries[relative_path]
        actual_entry = actual_entries[relative_path]
        if expected_entry.kind != actual_entry.kind:
            type_differences.append(relative_path)
            continue
        if expected_entry.mode != actual_entry.mode:
            mode_differences.append(relative_path)
        if expected_entry.kind == "file" and (
            expected_entry.size != actual_entry.size
            or expected_entry.content_digest != actual_entry.content_digest
        ):
            content_differences.append(relative_path)

    mismatches = (
        ("missing", missing),
        ("unexpected", unexpected),
        ("type-different", type_differences),
        ("mode-different", mode_differences),
        ("content-different", content_differences),
    )
    if any(paths for _, paths in mismatches):
        detail = "; ".join(
            f"{label}={len(paths)}" for label, paths in mismatches if paths
        )
        raise ValueError(f"{mismatch_subject}: {detail}. {remediation}")

    expected_digest = digest_tree_manifest(expected_entries)
    actual_digest = digest_tree_manifest(actual_entries)
    if expected_digest != actual_digest:
        raise ValueError(f"{mismatch_subject}: internal tree digest mismatch")


def ignored_cache_entry_names(_: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in CACHE_IGNORE_PATTERNS)
    }


def build_installable_tree_manifest(root: Path) -> dict[str, TreeEntry]:
    if root.is_symlink():
        raise ValueError("plugin source and cache roots must not be symlinks")
    if not root.is_dir():
        raise ValueError(f"plugin tree is missing or not a directory: {root}")

    root_metadata = root.stat(follow_symlinks=False)
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("plugin source and cache roots must be directories")
    entries: dict[str, TreeEntry] = {
        ".": TreeEntry(
            kind="directory",
            mode=stat.S_IMODE(root_metadata.st_mode),
            size=0,
            content_digest="",
        )
    }

    def visit(directory: Path, relative_directory: Path) -> None:
        with os.scandir(directory) as iterator:
            children = sorted(iterator, key=lambda entry: canonical_utf8(entry.name))
        ignored = ignored_cache_entry_names(
            str(directory),
            [entry.name for entry in children],
        )
        for child in children:
            if child.name in ignored:
                continue
            child_path = Path(child.path)
            relative_path = relative_directory / child.name
            relative_key = relative_path.as_posix()
            canonical_utf8(relative_key)
            if child.is_symlink():
                raise ValueError(
                    "plugin source and cache trees must not contain symlinks"
                )
            metadata = child.stat(follow_symlinks=False)
            mode = stat.S_IMODE(metadata.st_mode)
            if stat.S_ISDIR(metadata.st_mode):
                entries[relative_key] = TreeEntry(
                    kind="directory",
                    mode=mode,
                    size=0,
                    content_digest="",
                )
                visit(child_path, relative_path)
                continue
            if stat.S_ISREG(metadata.st_mode):
                content_digest, size = digest_file(
                    child_path,
                    expected_metadata=metadata,
                )
                entries[relative_key] = TreeEntry(
                    kind="file",
                    mode=mode,
                    size=size,
                    content_digest=content_digest,
                )
                continue
            raise ValueError(
                "plugin source and cache trees must contain only directories "
                "and regular files"
            )

    visit(root, Path())
    return entries


def digest_file(
    path: Path,
    *,
    expected_metadata: os.stat_result,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    flags = os.O_RDONLY
    for optional_flag in ("O_BINARY", "O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK"):
        flags |= getattr(os, optional_flag, 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as err:
        raise ValueError(
            "plugin tree changed or contains an unsafe file during verification"
        ) from err
    try:
        opened_metadata = os.fstat(descriptor)
        ensure_same_open_file(expected_metadata, opened_metadata)
        while chunk := os.read(descriptor, FILE_HASH_CHUNK_SIZE):
            digest.update(chunk)
            size += len(chunk)
        final_metadata = os.fstat(descriptor)
        ensure_same_open_file(opened_metadata, final_metadata)
    finally:
        os.close(descriptor)
    return digest.hexdigest(), size


def ensure_same_open_file(
    expected: os.stat_result,
    actual: os.stat_result,
) -> None:
    stable_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if not stat.S_ISREG(actual.st_mode) or any(
        getattr(expected, field, None) != getattr(actual, field, None)
        for field in stable_fields
    ):
        raise ValueError(
            "plugin tree changed or contains an unsafe file during verification"
        )


def digest_tree_manifest(entries: dict[str, TreeEntry]) -> str:
    digest = hashlib.sha256()
    for relative_path in sorted(entries, key=canonical_utf8):
        entry = entries[relative_path]
        for value in (
            relative_path,
            entry.kind,
            str(entry.mode),
            str(entry.size),
            entry.content_digest,
        ):
            encoded = canonical_utf8(value)
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def ensure_path_within_cache_root(cache_path: Path, cache_root: Path) -> None:
    resolved_cache = cache_path.resolve(strict=False)
    resolved_root = cache_root.resolve(strict=False)
    if not path_is_within(resolved_cache, resolved_root):
        raise ValueError("plugin cache path escapes the configured cache root")


def ensure_root_is_not_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")


def ensure_cache_path_has_no_symlink_components(
    *,
    cache_path: Path,
    cache_root: Path,
) -> None:
    try:
        relative_cache_path = cache_path.relative_to(cache_root)
    except ValueError:
        raise ValueError(
            "plugin cache path escapes the configured cache root"
        ) from None
    current = cache_root
    for component in relative_cache_path.parts:
        current /= component
        if current.is_symlink():
            raise ValueError("plugin cache path components must not be symlinks")


def ensure_disjoint_install_paths(*, plugin_root: Path, cache_path: Path) -> None:
    source = plugin_root.resolve(strict=False)
    target_cache = cache_path.resolve(strict=False)
    if path_is_within(source, target_cache) or path_is_within(target_cache, source):
        raise ValueError("plugin source and target version-cache must be disjoint")


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def canonical_utf8(value: str) -> bytes:
    try:
        return value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as err:
        raise ValueError(
            "plugin tree entry names must be valid Unicode encodable as UTF-8"
        ) from err


if __name__ == "__main__":
    main()
