#!/usr/bin/env python3
"""Wire an existing plugin icon asset into a Codex plugin manifest."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_relative_asset(plugin_root: Path, raw_path: str) -> str:
    candidate = PurePosixPath(raw_path.replace("\\", "/"))
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("--icon-path must be a non-empty relative path inside the plugin.")
    normalized = candidate.as_posix()
    resolved = (plugin_root / normalized).resolve()
    if not resolved.is_relative_to(plugin_root.resolve()):
        raise ValueError("--icon-path must stay inside the plugin.")
    if not resolved.is_file():
        raise FileNotFoundError(f"Icon asset does not exist: {resolved}")
    return "./" + normalized.lstrip("./")


def wire_icon(plugin_root: Path, icon_path: str, brand_color: str) -> Path:
    if HEX_COLOR_RE.fullmatch(brand_color) is None:
        raise ValueError("--brand-color must use #RRGGBB.")
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")

    normalized_icon_path = validate_relative_asset(plugin_root, icon_path)
    payload = load_json(manifest_path)
    interface = payload.setdefault("interface", {})
    if not isinstance(interface, dict):
        raise ValueError("plugin.json field `interface` must be an object.")
    interface["brandColor"] = brand_color.upper()
    interface["composerIcon"] = normalized_icon_path
    interface["logo"] = normalized_icon_path
    write_json(manifest_path, payload)
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wire an existing icon into a Codex plugin manifest.")
    parser.add_argument("plugin_root", type=Path)
    parser.add_argument("--icon-path", default="assets/icon.png", help="Relative icon path inside the plugin.")
    parser.add_argument("--brand-color", required=True, help="#RRGGBB icon background/base color.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = wire_icon(
        args.plugin_root.expanduser().resolve(),
        args.icon_path,
        args.brand_color,
    )
    print(f"Wired plugin icon in {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
