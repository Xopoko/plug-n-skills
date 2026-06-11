#!/usr/bin/env python3
"""Ensure a local marketplace plugin is visible to Codex as an installed plugin.

Codex-specific by design: Codex is the only supported marketplace/cache/config
surface, so this script always targets Codex paths regardless of the host agent
running it. For Claude or Cursor hosts, plugin activation goes through the
host's own mechanism; report source path plus validation instead of this gate.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
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

from validate_plugin import validate_plugin


MARKETPLACE_SECTION_RE = re.compile(r"^\s*\[marketplaces\.[^\]]+\]\s*$")
TABLE_HEADER_RE = re.compile(r"^\s*\[[^\]]+\]\s*$")
ENABLED_RE = re.compile(r"^\s*enabled\s*=")


@dataclass(frozen=True)
class InstallOutcome:
    plugin_id: str
    marketplace_name: str
    source_path: Path
    cache_path: Path
    mode: str
    config_changed: bool
    cache_changed: bool


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
        help="Verify marketplace source, config, and cache without making changes",
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
    print(f"config changed: {str(outcome.config_changed).lower()}")
    print(f"cache changed: {str(outcome.cache_changed).lower()}")
    print("visibility check passed")


def ensure_installed(
    *,
    plugin_path: Path,
    marketplace_path: Path,
    config_path: Path,
    cache_root: Path,
    codex_bin: str,
    force_manual: bool = False,
    check_only: bool = False,
    dry_run: bool = False,
) -> InstallOutcome:
    plugin_root = plugin_path.expanduser().resolve()
    marketplace_file = marketplace_path.expanduser().resolve()
    config_file = config_path.expanduser().resolve()
    cache_base = cache_root.expanduser().resolve()

    manifest = load_manifest(plugin_root)
    plugin_name = require_string(manifest, "name", plugin_root / ".codex-plugin" / "plugin.json")
    version = require_string(manifest, "version", plugin_root / ".codex-plugin" / "plugin.json")

    validation_errors = validate_plugin(plugin_root)
    if validation_errors:
        formatted = "\n".join(f"- {error}" for error in validation_errors)
        raise ValueError(f"plugin validation failed for {plugin_root}:\n{formatted}")

    marketplace = load_json_object(marketplace_file)
    marketplace_name = require_string(marketplace, "name", marketplace_file)
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

    if check_only:
        ensure_config_enabled(config_file, plugin_id)
        ensure_cache_present(cache_path, plugin_name)
        return InstallOutcome(
            plugin_id=plugin_id,
            marketplace_name=marketplace_name,
            source_path=source_path,
            cache_path=cache_path,
            mode="check-only",
            config_changed=False,
            cache_changed=False,
        )

    if not force_manual:
        if resolve_agent(explicit="codex").agent == "codex":
            cli_result = try_cli_install(codex_bin, plugin_id)
        else:
            cli_result = None
        if cli_result == "installed":
            return InstallOutcome(
                plugin_id=plugin_id,
                marketplace_name=marketplace_name,
                source_path=source_path,
                cache_path=cache_path,
                mode="codex-cli",
                config_changed=False,
                cache_changed=False,
            )
        # None means CLI was skipped (non-Codex agent); treat as "fall through to manual"
        if cli_result is not None and cli_result != "unsupported":
            raise RuntimeError(cli_result)

    config_changed = ensure_config_enabled(config_file, plugin_id, write=True, dry_run=dry_run)
    cache_changed = ensure_cache_materialized(
        plugin_root=plugin_root,
        cache_path=cache_path,
        dry_run=dry_run,
    )
    if not dry_run:
        ensure_config_enabled(config_file, plugin_id)
        ensure_cache_present(cache_path, plugin_name)
    return InstallOutcome(
        plugin_id=plugin_id,
        marketplace_name=marketplace_name,
        source_path=source_path,
        cache_path=cache_path,
        mode="manual-fallback",
        config_changed=config_changed,
        cache_changed=cache_changed,
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


def configured_marketplace_root(config_path: Path, marketplace_name: str) -> Path | None:
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
            raise ValueError(f"marketplace entry '{plugin_name}' source must be an object")
        if source.get("source") != "local":
            raise ValueError(f"marketplace entry '{plugin_name}' must use local source")
        raw_path = source.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"marketplace entry '{plugin_name}' source.path must be non-empty")
        source_path = Path(raw_path)
        if not source_path.is_absolute():
            source_path = marketplace_root / source_path
        return source_path.expanduser().resolve()
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
        raise ValueError(f"{config_path} does not enable [plugins.\"{plugin_id}\"]")
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


def ensure_cache_materialized(*, plugin_root: Path, cache_path: Path, dry_run: bool) -> bool:
    if dry_run:
        return True
    if cache_path.exists():
        shutil.rmtree(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    prune_stale_cache_versions(cache_path)
    shutil.copytree(
        plugin_root,
        cache_path,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".DS_Store"),
    )
    return True


def prune_stale_cache_versions(cache_path: Path) -> None:
    plugin_cache_dir = cache_path.parent
    if not plugin_cache_dir.exists():
        return
    for entry in plugin_cache_dir.iterdir():
        if entry == cache_path:
            continue
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def ensure_cache_present(cache_path: Path, plugin_name: str) -> None:
    manifest_path = cache_path / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise ValueError(f"cache manifest is missing: {manifest_path}")
    manifest = load_json_object(manifest_path)
    cached_name = manifest.get("name")
    if cached_name != plugin_name:
        raise ValueError(
            f"cache manifest {manifest_path} has name {cached_name!r}, expected {plugin_name!r}"
        )


if __name__ == "__main__":
    main()
