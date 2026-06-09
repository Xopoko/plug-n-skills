#!/usr/bin/env python3
"""Prepare an imagegen prompt for a marketplace plugin icon."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
PALETTES = (
    {
        "name": "deep-teal",
        "background": "deep ink to saturated teal",
        "brandColor": "#0B1220",
        "foreground": "warm off-white, bright aqua, and soft amber",
    },
    {
        "name": "blue-ember",
        "background": "charcoal navy to vivid cobalt",
        "brandColor": "#111827",
        "foreground": "crisp white, light sky blue, and muted coral",
    },
    {
        "name": "violet-mint",
        "background": "deep indigo to saturated violet",
        "brandColor": "#1E1B4B",
        "foreground": "clean white, lavender, and fresh mint",
    },
    {
        "name": "forest-gold",
        "background": "dark evergreen to rich green",
        "brandColor": "#06281F",
        "foreground": "warm ivory, spring green, and clear gold",
    },
    {
        "name": "paper-blue",
        "background": "soft white to pale blue",
        "brandColor": "#F8FAFC",
        "foreground": "dark ink, strong blue, and deep green",
    },
    {
        "name": "warm-paper",
        "background": "warm ivory to soft peach",
        "brandColor": "#FFF7ED",
        "foreground": "deep graphite, burnt orange, and dark cyan",
    },
)

MOTIF_HINTS = (
    (("cli", "terminal", "shell", "command", "codex", "claude"), "a bold terminal prompt mark, abstracted into one large chevron and one block cursor"),
    (("security", "audit", "safe", "guard", "threat"), "a modern protective shield mark reduced to two large interlocking planes"),
    (("design", "ui", "ux", "visual", "interface"), "a precise compass or drafting mark simplified into large intersecting shapes"),
    (("research", "science", "docs", "papers", "search"), "a clean lens or discovery mark with one strong circular form"),
    (("data", "context", "density", "metric", "analytics"), "three large ascending signal bars merged into a distinctive abstract mark"),
    (("build", "swift", "kotlin", "tauri", "web", "app"), "three broad layered slabs suggesting construction and assembly"),
    (("game", "play", "studio", "motion"), "a dynamic orbit mark with one central shape and one sweeping arc"),
    (("capability", "workbench", "skill", "plugin", "factory"), "a strong bridge or workbench mark made from two supports and one arch"),
)


def normalize_plugin_name(plugin_name: str) -> str:
    normalized = plugin_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("Plugin name must contain at least one ASCII letter or digit.")
    return normalized


def choose_palette(plugin_name: str, brand_color: str | None) -> dict[str, str]:
    if brand_color is not None:
        if HEX_COLOR_RE.fullmatch(brand_color) is None:
            raise ValueError("--brand-color must use #RRGGBB.")
        return {
            "name": "custom",
            "background": f"a tasteful background built around {brand_color.upper()}",
            "brandColor": brand_color.upper(),
            "foreground": "high-contrast foreground colors that meet WCAG non-text contrast",
        }

    digest = hashlib.sha256(plugin_name.encode("utf-8")).digest()
    return PALETTES[digest[0] % len(PALETTES)]


def choose_motif(plugin_name: str, motif: str | None) -> str:
    if motif:
        return motif
    for keywords, hint in MOTIF_HINTS:
        if any(keyword in plugin_name for keyword in keywords):
            return hint
    return "one memorable abstract geometric mark that communicates the plugin capability without literal detail"


def build_prompt(plugin_name: str, description: str, palette: dict[str, str], motif: str) -> str:
    display = plugin_name.replace("-", " ")
    subject_line = f"{display} agent plugin" if not description else description
    return f"""Use case: logo-brand
Asset type: 1024x1024 marketplace plugin icon
Primary request: Create a premium minimal bitmap icon for the {subject_line}.
Subject: {motif}.
Style/medium: polished modern app icon, vector-friendly but rendered as a high-quality bitmap, flat geometric foreground with subtle dimensional polish.
Composition/framing: centered, one dominant readable silhouette, generous safe area, no small details, readable at 32x32.
Scene/backdrop: full-bleed rounded-square app-icon background, {palette['background']}.
Color palette: foreground uses {palette['foreground']}; background may use a smooth restrained gradient.
Materials/textures: clean solid shapes, crisp edges, no busy texture, no photo material, no UI screenshot.
Text (verbatim): none.
Constraints: no visible letters, no words, no numbers, no tiny badges, no tiny decorative dots, no thin-line illustration, no product UI, no watermark, no private names.
Avoid: generic stock logo, overly literal object collage, mascot, complex scene, skeuomorphic clutter, low contrast, text inside the icon.
"""


def build_contract(plugin_name: str, description: str, brand_color: str | None, motif: str | None) -> dict[str, Any]:
    normalized = normalize_plugin_name(plugin_name)
    palette = choose_palette(normalized, brand_color)
    chosen_motif = choose_motif(normalized, motif)
    return {
        "schema": "capability_workbench.plugin_icon_prompt.v1",
        "plugin_name": normalized,
        "brandColor": palette["brandColor"],
        "recommended_asset_path": "assets/icon.png",
        "imagegen_mode": "built-in",
        "prompt": build_prompt(normalized, description, palette, chosen_motif),
        "checks": [
            "save the selected image into the plugin workspace as assets/icon.png",
            "inspect the image at 1024, 64, and 32 px",
            "reject visible text, letters, tiny details, screenshots, photos, watermarks, or low contrast",
            "wire interface.composerIcon, interface.logo, and interface.brandColor after the file exists",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare an imagegen prompt for a plugin icon.")
    parser.add_argument("plugin_name")
    parser.add_argument("--description", default="", help="Short plugin purpose to guide the icon.")
    parser.add_argument("--brand-color", help="Optional #RRGGBB background color anchor.")
    parser.add_argument("--motif", help="Optional motif hint. Defaults to name-based inference.")
    parser.add_argument("--json", action="store_true", help="Emit the full prompt contract as JSON.")
    parser.add_argument("--out", type=Path, help="Optional path to write the JSON prompt contract.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = build_contract(args.plugin_name, args.description, args.brand_color, args.motif)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(contract, indent=2))
    else:
        print(contract["prompt"])
        print(f"brandColor: {contract['brandColor']}")
        print(f"recommended asset path: {contract['recommended_asset_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
