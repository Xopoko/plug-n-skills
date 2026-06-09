#!/usr/bin/env python3
"""Offline probe for Tauri 2 project structure.

Reads local project files and prints JSON. It performs no installs, network
calls, or command execution.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]


def read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - diagnostic tool
        return None, str(exc)


def read_toml(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if tomllib is None:
        return None, "tomllib unavailable"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:  # noqa: BLE001 - diagnostic tool
        return None, str(exc)


def detect_package_manager(root: Path) -> str | None:
    markers = [
        ("pnpm-lock.yaml", "pnpm"),
        ("bun.lockb", "bun"),
        ("bun.lock", "bun"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
        ("deno.lock", "deno"),
    ]
    for marker, manager in markers:
        if (root / marker).exists():
            return manager
    if (root / "package.json").exists():
        return "npm"
    return None


def tauri_command(manager: str | None, subcommand: str) -> str:
    if manager == "pnpm":
        return f"pnpm tauri {subcommand}"
    if manager == "yarn":
        return f"yarn tauri {subcommand}"
    if manager == "bun":
        return f"bun tauri {subcommand}"
    if manager == "deno":
        return f"deno task tauri {subcommand}"
    if manager == "npm":
        return f"npm run tauri {subcommand}"
    return f"cargo tauri {subcommand}"


def parse_package(root: Path) -> dict[str, Any]:
    package_path = root / "package.json"
    if not package_path.exists():
        return {"exists": False}
    data, error = read_json(package_path)
    if error:
        return {"exists": True, "parse_error": error}
    deps: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        value = data.get(key, {}) if data else {}
        if isinstance(value, dict):
            deps.update({str(k): str(v) for k, v in value.items()})
    return {
        "exists": True,
        "scripts": data.get("scripts", {}) if data else {},
        "tauri_packages": {
            k: v for k, v in deps.items() if k.startswith("@tauri-apps/")
        },
    }


def parse_tauri_config(src_tauri: Path) -> dict[str, Any]:
    candidates = [
        src_tauri / "tauri.conf.json",
        src_tauri / "tauri.conf.json5",
        src_tauri / "Tauri.toml",
        src_tauri / "tauri.conf.toml",
    ]
    for path in candidates:
        if not path.exists():
            continue
        suffixes = "".join(path.suffixes)
        if suffixes.endswith(".json"):
            data, error = read_json(path)
        elif suffixes.endswith(".toml"):
            data, error = read_toml(path)
        else:
            data, error = None, "json5 parsing not supported by offline probe"
        result: dict[str, Any] = {"path": str(path), "parse_error": error}
        if data:
            build = data.get("build", {})
            app = data.get("app", {})
            result.update(
                {
                    "productName": data.get("productName"),
                    "version": data.get("version"),
                    "identifier": data.get("identifier"),
                    "build": {
                        "devUrl": build.get("devUrl") if isinstance(build, dict) else None,
                        "frontendDist": build.get("frontendDist")
                        if isinstance(build, dict)
                        else None,
                        "beforeDevCommand": build.get("beforeDevCommand")
                        if isinstance(build, dict)
                        else None,
                        "beforeBuildCommand": build.get("beforeBuildCommand")
                        if isinstance(build, dict)
                        else None,
                    },
                    "declared_capabilities": (
                        app.get("security", {}).get("capabilities")
                        if isinstance(app, dict)
                        and isinstance(app.get("security", {}), dict)
                        else None
                    ),
                }
            )
        return result
    return {"path": None, "parse_error": "no tauri config found"}


def parse_cargo(src_tauri: Path) -> dict[str, Any]:
    cargo_path = src_tauri / "Cargo.toml"
    if not cargo_path.exists():
        return {"exists": False}
    text = cargo_path.read_text(encoding="utf-8", errors="replace")
    tauri_deps = sorted(set(re.findall(r"(?m)^\s*(tauri[\w-]*)\s*=", text)))
    return {
        "exists": True,
        "path": str(cargo_path),
        "tauri_dependencies": tauri_deps,
    }


def parse_capability(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        data, error = read_json(path)
    elif path.suffix == ".toml":
        data, error = read_toml(path)
    else:
        return {"path": str(path), "parse_error": "unsupported extension"}
    item: dict[str, Any] = {"path": str(path), "parse_error": error}
    if isinstance(data, dict):
        permissions = data.get("permissions", [])
        item.update(
            {
                "identifier": data.get("identifier"),
                "windows": data.get("windows"),
                "platforms": data.get("platforms"),
                "permission_count": len(permissions) if isinstance(permissions, list) else None,
            }
        )
    return item


def parse_capabilities(src_tauri: Path) -> list[dict[str, Any]]:
    cap_dir = src_tauri / "capabilities"
    if not cap_dir.exists():
        return []
    files = sorted(
        p for p in cap_dir.iterdir() if p.is_file() and p.suffix in {".json", ".toml"}
    )
    return [parse_capability(path) for path in files]


def probe(root: Path) -> dict[str, Any]:
    root = root.resolve()
    src_tauri = root / "src-tauri"
    manager = detect_package_manager(root)
    package = parse_package(root)
    config = parse_tauri_config(src_tauri) if src_tauri.exists() else {"path": None}
    capabilities = parse_capabilities(src_tauri) if src_tauri.exists() else []
    warnings: list[str] = []
    if not src_tauri.exists():
        warnings.append("missing src-tauri directory")
    if config.get("path") is None:
        warnings.append("missing tauri config")
    if src_tauri.exists() and not capabilities:
        warnings.append("no capability files found")
    if config.get("parse_error"):
        warnings.append(f"config parse issue: {config['parse_error']}")
    if capabilities and config.get("declared_capabilities") is None:
        warnings.append("capabilities found; app.security.capabilities not explicit")
    return {
        "root": str(root),
        "src_tauri_exists": src_tauri.exists(),
        "package_manager": manager,
        "package": package,
        "cargo": parse_cargo(src_tauri) if src_tauri.exists() else {"exists": False},
        "tauri_config": config,
        "capabilities": capabilities,
        "suggested_commands": {
            "dev": tauri_command(manager, "dev"),
            "build": tauri_command(manager, "build"),
            "cargo_check": "cargo check --manifest-path src-tauri/Cargo.toml",
            "cargo_test": "cargo test --manifest-path src-tauri/Cargo.toml",
        },
        "warnings": warnings,
    }


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        (root / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {"tauri": "tauri"},
                    "devDependencies": {"@tauri-apps/cli": "^2.0.0"},
                    "dependencies": {"@tauri-apps/api": "^2.0.0"},
                }
            ),
            encoding="utf-8",
        )
        src_tauri = root / "src-tauri"
        (src_tauri / "capabilities").mkdir(parents=True)
        (src_tauri / "Cargo.toml").write_text(
            "[dependencies]\ntauri = \"2\"\ntauri-plugin-opener = \"2\"\n",
            encoding="utf-8",
        )
        (src_tauri / "tauri.conf.json").write_text(
            json.dumps(
                {
                    "productName": "Probe",
                    "version": "0.1.0",
                    "identifier": "com.example.probe",
                    "build": {"devUrl": "http://localhost:5173", "frontendDist": "../dist"},
                    "app": {"security": {"capabilities": ["main"]}},
                }
            ),
            encoding="utf-8",
        )
        (src_tauri / "capabilities" / "main.json").write_text(
            json.dumps(
                {
                    "identifier": "main",
                    "windows": ["main"],
                    "permissions": ["core:default"],
                }
            ),
            encoding="utf-8",
        )
        result = probe(root)
        assert result["package_manager"] == "pnpm"
        assert result["tauri_config"]["identifier"] == "com.example.probe"
        assert result["capabilities"][0]["identifier"] == "main"
        assert result["suggested_commands"]["dev"] == "pnpm tauri dev"
    print("self-test ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Project root")
    parser.add_argument("--self-test", action="store_true", help="Run built-in self-test")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    print(json.dumps(probe(Path(args.root)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
