#!/usr/bin/env python3
"""Render the README plugin dashboard header from source plugin assets."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plugin_catalog  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SIZE = (2400, 1500)
BACKGROUND = ROOT / "assets" / "plugin-dashboard-background.png"
OUTPUT = ROOT / "assets" / "plugin-dashboard-header.webp"
FONT = ROOT / "assets" / "fonts" / "inter" / "InterVariable.ttf"
WEBP_QUALITY = 94

PLUGIN_LAYOUT_ROWS = [
    # Agent operating system: runtime, capability lifecycle, context, delivery, hygiene.
    [
        "agent-harness",
        "windows-host-operations",
        "capability-workbench",
        "context-density",
        "i-have-adhd",
        "git-workflows",
    ],
    # Evidence and engineering method, from discovery through maintenance.
    [
        "engineering-hygiene",
        "scientific-research",
        "technology-intelligence",
        "design-intelligence",
        "architecture-intelligence",
        "spec-driven-development",
    ],
    # Product platforms and domains.
    [
        "build-swift-apps",
        "kotlin-multiplatform",
        "tauri",
        "pixijs",
        "game-design-intelligence",
        "career",
    ],
]

PLUGIN_SUMMARIES = {
    "architecture-intelligence": "Architecture decisions, drift, and topology.",
    "agent-harness": "Codex, Claude, harnesses, and automation.",
    "build-swift-apps": "Build, debug, profile, and ship Apple apps.",
    "career": "Career evidence, search, interviews, and offers.",
    "capability-workbench": "Engineer, evaluate, and govern agent capabilities.",
    "context-density": "Measure, compress, and verify agent context.",
    "i-have-adhd": "Action-first focus with visible progress.",
    "design-intelligence": "Product framing, UX, access, and systems.",
    "engineering-hygiene": "Code, logic, UI, and toolchain maintenance.",
    "game-design-intelligence": "Loops, progression, economies, and retention.",
    "git-workflows": "Review, stack, recover, and deliver across forges.",
    "kotlin-multiplatform": "KMP migration, Gradle, Compose, and publishing.",
    "pixijs": "PixiJS scenes, rendering, events, and performance.",
    "scientific-research": "Scholarly discovery with auditable evidence.",
    "spec-driven-development": "Specifications through traceable delivery.",
    "technology-intelligence": "Current evidence for technology decisions.",
    "tauri": "Secure Tauri IPC, testing, packaging, and release.",
    "windows-host-operations": "Windows settings, startup, apps, and devices.",
}

FONT_WEIGHTS = {
    "regular": 400,
    "medium": 500,
    "semibold": 600,
}


@dataclass(frozen=True)
class PluginCard:
    name: str
    display_name: str
    summary: str
    icon: Path
    brand_color: tuple[int, int, int]


def load_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Load the bundled Inter variable font with repeatable weight selection."""
    if not FONT.is_file():
        raise FileNotFoundError(f"Missing dashboard font: {FONT.relative_to(ROOT)}")
    font = ImageFont.truetype(
        str(FONT),
        size,
        layout_engine=ImageFont.Layout.BASIC,
    )
    optical_size = max(14, min(32, round(size * 0.44)))
    try:
        font.set_variation_by_axes([optical_size, FONT_WEIGHTS[weight]])
    except (AttributeError, OSError):
        # Older Pillow builds can still render the font at its regular defaults.
        # Failing back to another host font would make the committed image drift.
        if weight != "regular":
            raise RuntimeError(
                "The dashboard renderer requires Pillow variable-font support"
            )
    return font


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
    mask_draw.rounded_rectangle((0, 0, size, size), radius=24, fill=255)
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
    catalog = plugin_catalog.validate_catalog(ROOT)
    for item in catalog["plugins"]:
        receipt = plugin_catalog.receipt_for(ROOT, item)
        icon = ROOT.joinpath(*Path(receipt["icons"]["catalogAsset"]).parts)
        plugins[item["name"]] = PluginCard(
            name=item["name"],
            display_name=item["displayName"],
            summary=PLUGIN_SUMMARIES.get(item["name"], item["description"]),
            icon=icon,
            brand_color=hex_color(receipt["icons"]["brandColor"]),
        )
    return plugins


def ordered_rows(plugins: dict[str, PluginCard]) -> list[list[PluginCard]]:
    seen = {name for row in PLUGIN_LAYOUT_ROWS for name in row}
    missing = sorted(set(plugins) - seen)
    rows = [[plugins[name] for name in row if name in plugins] for row in PLUGIN_LAYOUT_ROWS]
    rows = [row for row in rows if row]
    for name in missing:
        available = [row for row in rows if len(row) < 6]
        if not available:
            raise ValueError(
                "Dashboard supports at most 18 plugin cards in three rows; "
                "update the canvas or card layout before adding more."
            )
        min(available, key=len).append(plugins[name])
    return rows


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
    radius = 34
    shadow = Image.new("RGBA", (width + 72, height + 82), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (36, 24, width + 36, height + 24),
        radius=radius,
        fill=(0, 4, 20, 132),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))
    canvas.alpha_composite(shadow, (x - 36, y - 24))

    panel = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle(
        (0, 0, width - 1, height - 1),
        radius=radius,
        fill=(5, 15, 43, 216),
        outline=(205, 232, 255, 60),
        width=2,
    )
    draw.rounded_rectangle(
        (4, 4, width - 5, height - 5),
        radius=radius - 4,
        outline=(255, 255, 255, 18),
        width=1,
    )

    icon_size = 84
    icon_x = (width - icon_size) // 2
    icon_y = 32

    glow = Image.new("RGBA", (184, 184), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((38, 38, 146, 146), fill=(*card.brand_color, 82))
    glow = glow.filter(ImageFilter.GaussianBlur(34))
    panel.alpha_composite(glow, ((width - 184) // 2, icon_y - 50))

    icon = rounded_icon(card.icon, icon_size)
    icon_shadow = Image.new("RGBA", (icon_size + 36, icon_size + 40), (0, 0, 0, 0))
    icon_shadow_alpha = Image.new("L", icon_shadow.size, 0)
    icon_shadow_alpha.paste(icon.getchannel("A"), (18, 13))
    icon_shadow_alpha = icon_shadow_alpha.filter(ImageFilter.GaussianBlur(12))
    icon_shadow.putalpha(icon_shadow_alpha.point(lambda value: value * 90 // 255))
    panel.alpha_composite(icon_shadow, (icon_x - 18, icon_y - 5))
    panel.alpha_composite(icon, (icon_x, icon_y))

    title_font = fonts["title"]
    body_font = fonts["body"]
    title_lines = wrap_lines(draw, card.display_name, title_font, width - 48, 2)
    if any(line.endswith("...") for line in title_lines):
        raise ValueError(f"Dashboard title does not fit: {card.display_name}")
    title_y = 145 + (2 - len(title_lines)) * 17
    draw_centered_lines(
        draw,
        title_lines,
        width // 2,
        title_y,
        title_font,
        (245, 249, 255, 255),
        34,
    )

    summary_lines = wrap_lines(draw, card.summary, body_font, width - 52, 2)
    if any(line.endswith("...") for line in summary_lines):
        raise ValueError(f"Dashboard summary does not fit: {card.name}")
    draw_centered_lines(
        draw,
        summary_lines,
        width // 2,
        227,
        body_font,
        (202, 218, 239, 248),
        28,
    )

    canvas.alpha_composite(panel, (x, y))


def render(background_path: Path, output_path: Path, quality: int = WEBP_QUALITY) -> None:
    if not background_path.is_file():
        raise FileNotFoundError(f"Missing background: {background_path.relative_to(ROOT)}")

    background = cover_image(Image.open(background_path), SIZE)
    background = ImageEnhance.Color(background).enhance(0.92)
    background = ImageEnhance.Contrast(background).enhance(1.08)
    canvas = background.convert("RGBA")

    wash = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    wash_draw = ImageDraw.Draw(wash)
    wash_draw.rectangle((0, 0, SIZE[0], SIZE[1]), fill=(1, 7, 26, 24))
    wash_draw.rectangle((0, 0, SIZE[0], 250), fill=(1, 8, 31, 84))
    canvas.alpha_composite(wash)

    fonts = {
        "hero": load_font("semibold", 82),
        "subtitle": load_font("regular", 31),
        "eyebrow": load_font("medium", 23),
        "title": load_font("medium", 30),
        "body": load_font("regular", 23),
    }

    draw = ImageDraw.Draw(canvas)
    title = "Plug'n Skills"
    subtitle = "Ready-to-install skills and plugins for Codex, Claude Code, and coding agents."
    draw.text((104, 62), title, font=fonts["hero"], fill=(248, 252, 255, 255))
    draw.text((108, 166), subtitle, font=fonts["subtitle"], fill=(204, 222, 246, 242))

    plugins = load_plugins()
    badge_text = f"{len(plugins)} plugin packs"
    badge_width = text_width(draw, badge_text, fonts["eyebrow"]) + 58
    badge_x = SIZE[0] - 104 - badge_width
    draw.rounded_rectangle(
        (badge_x, 86, badge_x + badge_width, 144),
        radius=29,
        fill=(4, 15, 47, 164),
        outline=(214, 239, 255, 86),
        width=2,
    )
    draw.text(
        (badge_x + 29, 101),
        badge_text,
        font=fonts["eyebrow"],
        fill=(232, 243, 255, 248),
    )

    rows = ordered_rows(plugins)
    card_w = 344
    card_h = 326
    row_gap = 30
    col_gap = 24
    grid_y = 276
    for row_index, row in enumerate(rows):
        row_width = len(row) * card_w + (len(row) - 1) * col_gap
        x = (SIZE[0] - row_width) // 2
        y = grid_y + row_index * (card_h + row_gap)
        for card in row:
            draw_card(canvas, card, x, y, card_w, card_h, fonts)
            x += card_w + col_gap

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output = canvas.convert("RGB")
    suffix = output_path.suffix.lower()
    if suffix == ".webp":
        if quality < 1 or quality > 100:
            raise ValueError("WebP quality must be between 1 and 100")
        output.save(output_path, format="WEBP", quality=quality, method=6)
    elif suffix == ".png":
        output.save(output_path, format="PNG", optimize=True)
    else:
        raise ValueError("Dashboard output must use .webp or .png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--background", type=Path, default=BACKGROUND)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--quality", type=int, default=WEBP_QUALITY)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    render(args.background, args.output, args.quality)
    print(f"Rendered {args.output}")


if __name__ == "__main__":
    main()
