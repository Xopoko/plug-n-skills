#!/usr/bin/env python3
"""Validate plugin icon assets and schema-v2 prompt contracts without dependencies."""

from __future__ import annotations

import argparse
import binascii
import json
import re
import struct
import zlib
from pathlib import Path, PurePosixPath
from typing import Any

from prepare_plugin_icon_prompt import ICON_CATALOG, SCHEMA, SIZE_GATES


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_object(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"missing {label}: {path}")
        return None
    try:
        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError(f"duplicate key {key!r}")
                value[key] = item
            return value

        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite number {token}")
            ),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{label} must be readable JSON: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label} must contain a JSON object")
        return None
    return value


def resolve_icon_path(plugin_root: Path, raw_path: str, errors: list[str]) -> Path | None:
    candidate = PurePosixPath(raw_path.replace("\\", "/"))
    if not raw_path.startswith("./") or candidate.is_absolute() or ".." in candidate.parts:
        errors.append("manifest icon path must start with `./` and stay inside the plugin")
        return None
    resolved = (plugin_root / candidate.as_posix()).resolve()
    if not resolved.is_relative_to(plugin_root.resolve()):
        errors.append("manifest icon path must stay inside the plugin")
        return None
    if not resolved.is_file():
        errors.append(f"manifest icon path is missing: {raw_path}")
        return None
    return resolved


def parse_png(path: Path, errors: list[str]) -> tuple[dict[str, int], bytes] | None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        errors.append(f"unable to read icon PNG: {exc}")
        return None
    if not data.startswith(PNG_SIGNATURE):
        errors.append("icon must be a PNG file with a valid signature")
        return None

    offset = len(PNG_SIGNATURE)
    ihdr: bytes | None = None
    idat: list[bytes] = []
    saw_iend = False
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            errors.append("PNG contains a truncated chunk")
            return None
        payload = data[offset + 8 : offset + 8 + length]
        declared_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        actual_crc = binascii.crc32(chunk_type + payload) & 0xFFFFFFFF
        if declared_crc != actual_crc:
            errors.append(f"PNG chunk {chunk_type.decode('ascii', 'replace')} has an invalid CRC")
            return None
        if chunk_type == b"IHDR":
            ihdr = payload
        elif chunk_type == b"IDAT":
            idat.append(payload)
        elif chunk_type == b"tRNS":
            errors.append("icon must be fully opaque RGB; PNG transparency is not allowed")
        elif chunk_type == b"IEND":
            saw_iend = True
            break
        offset = end

    if ihdr is None or len(ihdr) != 13 or not idat or not saw_iend:
        errors.append("PNG must contain valid IHDR, IDAT, and IEND chunks")
        return None
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
    metadata = {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "interlace": interlace,
    }
    if (width, height) != (1024, 1024):
        errors.append(f"icon must be exactly 1024x1024; found {width}x{height}")
    if bit_depth != 8 or color_type != 2:
        errors.append("icon mode policy requires an 8-bit opaque RGB PNG (PNG color type 2)")
    if compression != 0 or filtering != 0 or interlace != 0:
        errors.append("icon PNG must use standard compression/filtering and be non-interlaced")
    if errors:
        return metadata, b""

    try:
        scanlines = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        errors.append(f"PNG IDAT data cannot be decompressed: {exc}")
        return metadata, b""
    row_bytes = width * 3
    expected = height * (row_bytes + 1)
    if len(scanlines) != expected:
        errors.append(f"PNG scanline payload has {len(scanlines)} bytes; expected {expected}")
        return metadata, b""

    pixels = bytearray(width * height * 3)
    previous = bytearray(row_bytes)
    source = 0
    destination = 0
    for _ in range(height):
        filter_type = scanlines[source]
        source += 1
        row = bytearray(scanlines[source : source + row_bytes])
        source += row_bytes
        if filter_type not in {0, 1, 2, 3, 4}:
            errors.append(f"PNG uses unsupported row filter {filter_type}")
            return metadata, b""
        for index in range(row_bytes):
            left = row[index - 3] if index >= 3 else 0
            up = previous[index]
            upper_left = previous[index - 3] if index >= 3 else 0
            if filter_type == 1:
                row[index] = (row[index] + left) & 0xFF
            elif filter_type == 2:
                row[index] = (row[index] + up) & 0xFF
            elif filter_type == 3:
                row[index] = (row[index] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                row[index] = (row[index] + paeth(left, up, upper_left)) & 0xFF
        pixels[destination : destination + row_bytes] = row
        destination += row_bytes
        previous = row
    return metadata, bytes(pixels)


def paeth(left: int, up: int, upper_left: int) -> int:
    estimate = left + up - upper_left
    left_distance = abs(estimate - left)
    up_distance = abs(estimate - up)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def thumbnail_stats(pixels: bytes, width: int, height: int, size: int) -> dict[str, Any]:
    colors: set[tuple[int, int, int]] = set()
    luminances: list[float] = []
    for target_y in range(size):
        y = min(height - 1, int((target_y + 0.5) * height / size))
        for target_x in range(size):
            x = min(width - 1, int((target_x + 0.5) * width / size))
            index = (y * width + x) * 3
            red, green, blue = pixels[index : index + 3]
            colors.add((red // 16, green // 16, blue // 16))
            luminances.append(0.2126 * red + 0.7152 * green + 0.0722 * blue)
    span = max(luminances) - min(luminances)
    return {
        "size": size,
        "quantized_colors": len(colors),
        "luminance_span": round(span, 2),
        "passes_non_flat_gate": len(colors) >= 2 and span >= 20.0,
    }


def require_strings(value: Any, field: str, errors: list[str], *, allow_empty: bool = False) -> None:
    if not isinstance(value, list) or (not value and not allow_empty) or not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"icon prompt field `{field}` must be {'an' if allow_empty else 'a non-empty'} array of non-empty strings")


def validate_prompt(prompt: dict[str, Any], plugin_name: str, brand_color: str, errors: list[str]) -> None:
    allowed_keys = {
        "schema",
        "plugin_name",
        "catalog",
        "semantic_hero",
        "support_cue",
        "avoid",
        "collision_avoid",
        "brand_source",
        "brandColor",
        "recommended_asset_path",
        "imagegen_mode",
        "size_gates",
        "prompt",
        "checks",
    }
    unknown = sorted(set(prompt) - allowed_keys)
    missing = sorted(allowed_keys - set(prompt))
    if unknown:
        errors.append(f"icon prompt has unknown fields: {', '.join(unknown)}")
    if missing:
        errors.append(f"icon prompt is missing fields: {', '.join(missing)}")
    if prompt.get("schema") != SCHEMA:
        errors.append(f"icon prompt schema must be `{SCHEMA}`")
    if prompt.get("plugin_name") != plugin_name:
        errors.append("icon prompt `plugin_name` must match the manifest name")
    if prompt.get("brandColor") != brand_color:
        errors.append("icon prompt `brandColor` must match manifest `interface.brandColor`")

    catalog = prompt.get("catalog")
    if not isinstance(catalog, dict) or catalog.get("source") not in {"first-party-catalog", "deterministic-fallback", "user-override"} or not isinstance(catalog.get("key"), str):
        errors.append("icon prompt `catalog` must declare source and key")
    elif plugin_name in ICON_CATALOG and catalog.get("source") == "deterministic-fallback":
        errors.append("known first-party plugin must use its catalog spec or an explicit user override")

    hero = prompt.get("semantic_hero")
    if not isinstance(hero, dict) or not all(isinstance(hero.get(key), str) and hero[key].strip() for key in ("object", "meaning", "silhouette")):
        errors.append("icon prompt `semantic_hero` must declare object, meaning, and silhouette")
    support = prompt.get("support_cue")
    if support is not None and (
        not isinstance(support, dict)
        or not all(isinstance(support.get(key), str) and support[key].strip() for key in ("object", "meaning"))
    ):
        errors.append("icon prompt `support_cue` must be null or one object with object and meaning")
    require_strings(prompt.get("avoid"), "avoid", errors)
    require_strings(prompt.get("collision_avoid"), "collision_avoid", errors)

    brand = prompt.get("brand_source")
    brand_keys = ("type", "source", "trademark_status", "license", "authorization")
    if not isinstance(brand, dict) or not all(isinstance(brand.get(key), str) and brand[key].strip() for key in brand_keys):
        errors.append("icon prompt `brand_source` must declare type, source, trademark_status, license, and authorization")
    elif brand.get("type") not in {"original-domain-metaphor", "brand-adjacent", "authorized-brand"}:
        errors.append("icon prompt `brand_source.type` is unsupported")
    elif brand.get("type") == "authorized-brand" and (
        brand.get("source") == "none"
        or brand.get("license") == "original-generated-artwork"
        or brand.get("authorization") == "not-required-no-brand-mark"
    ):
        errors.append("authorized-brand prompt requires explicit source, license, and authorization evidence")
    if prompt.get("size_gates") != SIZE_GATES:
        errors.append("icon prompt `size_gates` must be [16, 24, 32, 64]")
    if prompt.get("recommended_asset_path") != "assets/icon.png":
        errors.append("icon prompt `recommended_asset_path` must be `assets/icon.png`")
    if prompt.get("imagegen_mode") != "built-in":
        errors.append("icon prompt `imagegen_mode` must be `built-in`")
    if not isinstance(prompt.get("prompt"), str) or not prompt["prompt"].strip():
        errors.append("icon prompt `prompt` must be a non-empty string")
    require_strings(prompt.get("checks"), "checks", errors)


def validate_plugin_icons(plugin_root: Path, *, require_icon: bool = False, require_prompt: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest = load_object(plugin_root / ".codex-plugin" / "plugin.json", "Codex manifest", errors)
    if manifest is None:
        return {"valid": False, "errors": errors, "warnings": warnings, "checks": {}}
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("manifest `interface` must be an object")
        return {"valid": False, "errors": errors, "warnings": warnings, "checks": {}}

    composer = interface.get("composerIcon")
    logo = interface.get("logo")
    if composer is None and logo is None:
        if require_icon:
            errors.append("manifest must declare both `interface.composerIcon` and `interface.logo`")
        else:
            warnings.append("manifest has no plugin icon paths")
        icon_path = None
    elif not isinstance(composer, str) or not isinstance(logo, str) or composer != logo:
        errors.append("manifest `interface.composerIcon` and `interface.logo` must be identical non-empty paths")
        icon_path = None
    else:
        icon_path = resolve_icon_path(plugin_root, composer, errors)

    brand_color = interface.get("brandColor")
    if icon_path is not None and (not isinstance(brand_color, str) or HEX_COLOR_RE.fullmatch(brand_color) is None):
        errors.append("manifest with an icon must declare `interface.brandColor` as #RRGGBB")

    checks: dict[str, Any] = {}
    if icon_path is not None:
        png_error_count = len(errors)
        parsed = parse_png(icon_path, errors)
        if parsed is not None:
            metadata, pixels = parsed
            checks["png"] = metadata
            if pixels and len(errors) == png_error_count:
                thumbnails = [thumbnail_stats(pixels, metadata["width"], metadata["height"], size) for size in SIZE_GATES]
                checks["thumbnails"] = thumbnails
                for result in thumbnails:
                    if not result["passes_non_flat_gate"]:
                        errors.append(f"icon fails the {result['size']}px non-flat readability gate")

    prompt_path = plugin_root / "assets" / "icon-prompt.json"
    if prompt_path.is_file():
        prompt = load_object(prompt_path, "icon prompt contract", errors)
        if prompt is not None and isinstance(manifest.get("name"), str) and isinstance(brand_color, str):
            if prompt.get("schema") == SCHEMA or require_prompt:
                validate_prompt(prompt, manifest["name"], brand_color, errors)
            else:
                warnings.append(
                    "legacy icon prompt receipt retained; schema-v2 semantic/provenance checks skipped"
                )
        checks["prompt_path"] = "assets/icon-prompt.json"
    elif require_prompt:
        errors.append("missing required icon prompt contract: assets/icon-prompt.json")
    else:
        warnings.append("icon prompt contract not present; schema/provenance checks skipped")

    checks["manual_review_required"] = [
        "literal semantic hero recognition at 16, 24, 32, and 64 px",
        "silhouette cohesion and portfolio collision review",
        "brand-source trademark, license, and authorization accuracy",
    ]
    return {"valid": not errors, "errors": errors, "warnings": warnings, "checks": checks}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate plugin icon asset, manifest wiring, prompt schema, and thumbnail statistics.")
    parser.add_argument("plugin_root", type=Path)
    parser.add_argument("--allow-missing-icon", action="store_true", help="Do not require manifest icon paths.")
    parser.add_argument("--require-prompt", action="store_true", help="Require assets/icon-prompt.json schema v2 provenance.")
    parser.add_argument("--json", action="store_true", help="Emit a structured report.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_plugin_icons(
        args.plugin_root.expanduser().resolve(),
        require_icon=not args.allow_missing_icon,
        require_prompt=args.require_prompt,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["valid"]:
        print(f"Plugin icon validation passed: {args.plugin_root}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
    else:
        print("Plugin icon validation failed:")
        for error in result["errors"]:
            print(f"- {error}")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
