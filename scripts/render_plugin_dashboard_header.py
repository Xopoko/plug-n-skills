#!/usr/bin/env python3
"""Render the README plugin dashboard header from source plugin assets."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SIZE = (1672, 941)
BACKGROUND = ROOT / "assets" / "plugin-dashboard-background.png"
OUTPUT = ROOT / "assets" / "plugin-dashboard-header.png"

PLUGIN_LAYOUT_ROWS = [
    [
        "build-swift-apps",
        "codex-cli",
        "claude-code",
        "tauri",
        "kotlin-multiplatform",
    ],
    [
        "pixijs",
        "design-intelligence",
        "architecture-intelligence",
        "spec-driven-development",
    ],
    [
        "capability-workbench",
        "context-density",
        "scientific-research",
        "game-design-intelligence",
    ],
]

PLUGIN_SUMMARIES = {
    "architecture-intelligence": "Boundaries, ownership, topology, drift, and ADRs from source.",
    "build-swift-apps": "Apple app build, debug, test, profile, and release workflows.",
    "capability-workbench": "Discovery, synthesis, vetting, packaging, install, and repair.",
    "claude-code": "Claude sessions, hooks, plugins, MCP, automation, and diagnostics.",
    "codex-cli": "Codex automation, diagnostics, logs, plugins, and MCP operations.",
    "context-density": "Token measurement, compression, provenance, and prompt contracts.",
    "design-intelligence": "Product framing, UI architecture, accessibility, and design systems.",
    "game-design-intelligence": "Loops, progression, economies, onboarding, difficulty, and retention.",
    "kotlin-multiplatform": "KMP migration, Gradle, Compose UI, tests, and publishing.",
    "pixijs": "PixiJS v8 scenes, assets, rendering, events, and performance.",
    "scientific-research": "Scholarly discovery, deduplication, evidence ledgers, and quality gates.",
    "spec-driven-development": "Specs, plans, tasks, traceable implementation, and proof.",
    "tauri": "Secure Tauri 2 setup, IPC, testing, packaging, and release.",
}

FONT_CANDIDATES = {
    "regular": [
        "SF-Pro-Text-Regular.otf",
        "SFNS.ttf",
        "HelveticaNeue.ttc",
        "Arial.ttf",
        "DejaVuSans.ttf",
    ],
    "semibold": [
        "SF-Pro-Text-Semibold.otf",
        "SF-Pro-Display-Semibold.otf",
        "SFNS.ttf",
        "Arial Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ],
    "bold": [
        "SF-Pro-Display-Bold.otf",
        "SF-Pro-Text-Bold.otf",
        "SFNS.ttf",
        "Arial Bold.ttf",
        "DejaVuSans-Bold.ttf",
    ],
}


@dataclass(frozen=True)
class PluginCard:
    name: str
    display_name: str
    summary: str
    icon: Path
    brand_color: tuple[int, int, int]


def load_font(weight: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES[weight]:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def hex_color(value: object, fallback: str = "#37C9FF") -> tuple[int, int, int]:
    if not isinstance(value, str):
        value = fallback
    cleaned = value.strip().lstrip("#")
    if len(cleaned) != 6:
        cleaned = fallback.lstrip("#")
    try:
        return tuple(int(cleaned[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return tuple(int(fallback.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return right - left


def wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and " ".join(lines).split() != words:
        lines[-1] = ellipsize(draw, lines[-1], font, max_width)
    return lines


def ellipsize(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    marker = "..."
    while text and text_width(draw, text + marker, font) > max_width:
        text = text[:-1].rstrip()
    return (text + marker) if text else marker


def cover_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def rounded_icon(path: Path, size: int) -> Image.Image:
    icon = Image.open(path).convert("RGBA")
    icon = ImageOps.fit(icon, (size, size), method=Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size, size), radius=20, fill=255)
    icon.putalpha(mask)
    return icon


def load_plugins() -> dict[str, PluginCard]:
    plugins: dict[str, PluginCard] = {}
    for manifest_path in sorted((ROOT / "plugins").glob("*/.codex-plugin/plugin.json")):
        name = manifest_path.parts[-3]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        interface = manifest.get("interface", {})
        if not isinstance(interface, dict):
            interface = {}
        icon = ROOT / "plugins" / name / "assets" / "icon.png"
        if not icon.is_file():
            raise FileNotFoundError(f"Missing plugin icon: {icon.relative_to(ROOT)}")
        display_name = interface.get("displayName") or manifest.get("displayName") or name
        if not isinstance(display_name, str):
            display_name = name
        short = interface.get("shortDescription") or manifest.get("description") or ""
        if not isinstance(short, str):
            short = ""
        plugins[name] = PluginCard(
            name=name,
            display_name=display_name,
            summary=PLUGIN_SUMMARIES.get(name, short),
            icon=icon,
            brand_color=hex_color(interface.get("brandColor") or manifest.get("brandColor")),
        )
    return plugins


def ordered_rows(plugins: dict[str, PluginCard]) -> list[list[PluginCard]]:
    seen = {name for row in PLUGIN_LAYOUT_ROWS for name in row}
    missing = sorted(set(plugins) - seen)
    rows = [[plugins[name] for name in row if name in plugins] for row in PLUGIN_LAYOUT_ROWS]
    for index in range(0, len(missing), 5):
        rows.append([plugins[name] for name in missing[index : index + 5]])
    return [row for row in rows if row]


def draw_centered_lines(
    draw: ImageDraw.ImageDraw,
    lines: Iterable[str],
    center_x: int,
    start_y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
    line_height: int,
) -> int:
    y = start_y
    for line in lines:
        width = text_width(draw, line, font)
        draw.text((center_x - width / 2, y), line, font=font, fill=fill)
        y += line_height
    return y


def draw_card(
    canvas: Image.Image,
    card: PluginCard,
    x: int,
    y: int,
    width: int,
    height: int,
    fonts: dict[str, ImageFont.ImageFont],
) -> None:
    radius = 28
    shadow = Image.new("RGBA", (width + 40, height + 46), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (20, 16, width + 20, height + 16),
        radius=radius,
        fill=(2, 10, 30, 94),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(shadow, (x - 20, y - 16))

    panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=(246, 250, 255, 222),
        outline=(255, 255, 255, 172),
        width=2,
    )

    icon_size = 62
    icon_x = (width - icon_size) // 2
    icon_y = 24
    draw.rounded_rectangle(
        (icon_x - 5, icon_y - 5, icon_x + icon_size + 5, icon_y + icon_size + 5),
        radius=24,
        fill=(255, 255, 255, 190),
        outline=(255, 255, 255, 230),
        width=2,
    )
    panel.alpha_composite(rounded_icon(card.icon, icon_size), (icon_x, icon_y))

    title_font = fonts["title"]
    body_font = fonts["body"]
    title_lines = wrap_lines(draw, card.display_name, title_font, width - 34, 2)
    title_y = 96
    end_y = draw_centered_lines(
        draw,
        title_lines,
        width // 2,
        title_y,
        title_font,
        (7, 20, 48, 255),
        23,
    )

    summary_lines = wrap_lines(draw, card.summary, body_font, width - 38, 2)
    draw_centered_lines(
        draw,
        summary_lines,
        width // 2,
        end_y + 8,
        body_font,
        (39, 52, 82, 244),
        19,
    )

    accent = (*card.brand_color, 238)
    draw.rounded_rectangle((24, height - 18, width - 24, height - 12), radius=4, fill=accent)

    canvas.alpha_composite(panel, (x, y))


def render(background_path: Path, output_path: Path) -> None:
    if not background_path.is_file():
        raise FileNotFoundError(f"Missing background: {background_path.relative_to(ROOT)}")

    background = cover_image(Image.open(background_path), SIZE)
    background = ImageEnhance.Color(background).enhance(1.04)
    background = ImageEnhance.Contrast(background).enhance(1.02)
    canvas = background.convert("RGBA")

    wash = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    wash_draw = ImageDraw.Draw(wash)
    wash_draw.rectangle((0, 0, SIZE[0], 190), fill=(3, 12, 40, 74))
    wash_draw.rectangle((0, 760, SIZE[0], SIZE[1]), fill=(255, 255, 255, 24))
    canvas.alpha_composite(wash)

    fonts = {
        "hero": load_font("bold", 58),
        "subtitle": load_font("regular", 24),
        "eyebrow": load_font("semibold", 18),
        "title": load_font("semibold", 20),
        "body": load_font("regular", 15),
    }

    draw = ImageDraw.Draw(canvas)
    title = "Plug'n Skills"
    subtitle = "Ready-to-install skills and plugins for Codex, Claude Code, and coding agents."
    draw.text((72, 48), title, font=fonts["hero"], fill=(248, 252, 255, 255))
    draw.text((73, 115), subtitle, font=fonts["subtitle"], fill=(218, 236, 255, 238))

    badge_text = "13 plugin packs"
    badge_width = text_width(draw, badge_text, fonts["eyebrow"]) + 42
    badge_x = SIZE[0] - 72 - badge_width
    draw.rounded_rectangle(
        (badge_x, 62, badge_x + badge_width, 104),
        radius=21,
        fill=(5, 18, 48, 116),
        outline=(255, 255, 255, 112),
        width=1,
    )
    draw.text((badge_x + 21, 73), badge_text, font=fonts["eyebrow"], fill=(238, 249, 255, 244))

    plugins = load_plugins()
    rows = ordered_rows(plugins)
    card_w = 295
    card_h = 212
    row_gap = 24
    col_gap = 20
    grid_y = 205
    for row_index, row in enumerate(rows):
        row_width = len(row) * card_w + (len(row) - 1) * col_gap
        x = (SIZE[0] - row_width) // 2
        y = grid_y + row_index * (card_h + row_gap)
        for card in row:
            draw_card(canvas, card, x, y, card_w, card_h, fonts)
            x += card_w + col_gap

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path, format="PNG", optimize=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background", type=Path, default=BACKGROUND)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render(args.background, args.output)
    print(f"Rendered {args.output}")


if __name__ == "__main__":
    main()
