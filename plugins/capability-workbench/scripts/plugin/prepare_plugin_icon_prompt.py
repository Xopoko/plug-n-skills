#!/usr/bin/env python3
"""Prepare a catalog-first schema-v2 imagegen contract for a plugin icon."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "capability_workbench.plugin_icon_prompt.v2"
HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
SIZE_GATES = [16, 24, 32, 64]

PALETTES = (
    ("deep-teal", "deep ink to saturated teal", "#0B1220", "warm ivory with aqua and amber accents"),
    ("blue-ember", "charcoal navy to vivid cobalt", "#111827", "crisp white with sky and coral accents"),
    ("violet-mint", "deep indigo to saturated violet", "#1E1B4B", "clean white with lavender and mint accents"),
    ("forest-gold", "dark evergreen to rich green", "#06281F", "warm ivory with spring green and gold accents"),
    ("paper-blue", "soft white to pale blue", "#F8FAFC", "dark ink with strong blue and deep green accents"),
    ("warm-paper", "warm ivory to soft peach", "#FFF7ED", "deep graphite with burnt orange and dark cyan accents"),
)


def brand_source(
    source_type: str = "original-domain-metaphor",
    source: str = "none",
    trademark_status: str = "no proprietary mark requested",
) -> dict[str, str]:
    return {
        "type": source_type,
        "source": source,
        "trademark_status": trademark_status,
        "license": "original-generated-artwork",
        "authorization": "not-required-no-brand-mark",
    }


def spec(
    hero: str,
    meaning: str,
    silhouette: str,
    support: str | None,
    support_meaning: str | None,
    avoid: list[str],
    collisions: list[str],
    brand: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "hero": {"object": hero, "meaning": meaning, "silhouette": silhouette},
        "support": (
            {"object": support, "meaning": support_meaning}
            if support is not None
            else None
        ),
        "avoid": avoid,
        "collisions": collisions,
        "brand": brand or brand_source(),
    }


# Exact first-party names are intentional: portfolio semantics are reviewed as a
# catalog, not inferred from fragments of a product name.
ICON_CATALOG: dict[str, dict[str, Any]] = {
    "agent-harness": spec(
        "a sturdy rigging harness buckle", "coordinated agent execution", "one broad buckle loop with a locked center bar",
        "one three-way route notch", "multiple controlled execution paths",
        ["robot head", "terminal glyph", "glowing abstract orbit"], ["safety harness product logo", "generic automation nodes"],
    ),
    "architecture-intelligence": spec(
        "a load-bearing building arch", "software architecture and structural integrity", "one heavy arch with two grounded supports",
        "one drafting-compass notch", "deliberate architectural analysis",
        ["city skyline", "stack of boxes", "generic letter A"], ["navigation compass", "construction-firm logo"],
    ),
    "build-swift-apps": spec(
        "an original swift-in-flight bird silhouette", "building Apple-platform applications", "one broad forward-moving bird with a distinct wing and tail",
        "one orange code-editor window", "hands-on Swift implementation",
        ["Apple logo", "exact Apple Swift logo geometry", "Xcode hammer", "Xcode icon", "device collage"], ["social-media bird", "email bird"],
        brand_source("brand-adjacent", "Apple platforms and Swift", "names describe compatibility; use original bird artwork and no exact Apple, Swift, or Xcode mark geometry"),
    ),
    "capability-workbench": spec(
        "a workshop pegboard with large round holes", "building and repairing agent capabilities", "one broad perforated tool wall",
        "one crossed hammer-and-wrench pair", "hands-on capability construction",
        ["table", "bridge", "arch", "gear", "magic wand", "tool collection beyond the pair"], ["developer toolbox", "engineering hygiene brush"],
    ),
    "career": spec(
        "a modern work briefcase", "career and job-search work", "one broad front-facing briefcase with a clearly open handle",
        "one open laptop behind it", "digital career operations",
        ["compass", "paper airplane", "road", "map pin", "corporate ladder", "resume collage"], ["business suite", "travel luggage"],
    ),
    "context-density": spec(
        "a wide funnel compressing document cards", "dense context without lost commitments", "one funnel containing three broad layers",
        "one intact output card", "preserved result after compression",
        ["bar chart", "database cylinder", "tiny tokens"], ["analytics funnel", "capability inventory"],
    ),
    "design-intelligence": spec(
        "a drafting compass", "intentional interface and product design", "one open compass forming a stable triangular silhouette",
        "one grid corner", "systematic visual construction",
        ["paint palette", "sparkles", "generic cursor arrow"], ["navigation compass", "architecture arch"],
    ),
    "engineering-hygiene": spec(
        "a broad cleaning brush", "removing code and workflow residue", "one angled brush with a single clean bristle block",
        "one code tile being swept clean", "literal codebase cleanup",
        ["shield", "check mark", "crescent", "lock", "spray bottle", "bucket"], ["paint brush", "capability workbench tools"],
    ),
    "game-design-intelligence": spec(
        "a generic game controller", "gameplay systems and player experience", "one compact controller with two large grips",
        "one restrained blueprint grid engraved in its center", "intentional systems design",
        ["brand-specific controller", "play triangle", "pixel mascot", "circular arrows", "refresh symbol", "orbit"], ["media playback", "esports team logo"],
        brand_source("brand-adjacent", "generic game hardware", "no console vendor shape, button layout, or mark requested"),
    ),
    "git-workflows": spec(
        "a railway switch lever", "controlled branching and recovery", "one heavy lever joining two route rails",
        "one checked stop plate", "review gate before delivery",
        ["GitHub Octocat", "GitLab fox", "Git logo", "generic node graph"], ["railway app", "automation route nodes"],
        brand_source("brand-adjacent", "Git workflows", "Git names the domain; no Git or forge trademark requested"),
    ),
    "kotlin-multiplatform": spec(
        "a shared-code tile", "one implementation spanning device platforms", "one central tile with an oversized code-brace pair",
        "one phone and one desktop window joined behind it", "mobile and desktop platform reach",
        ["Kotlin letter K", "Kotlin diagonal-square mark", "Kotlin Multiplatform logo", "mascot", "platform vendor logos"], ["responsive design", "generic mobile development"],
        brand_source("brand-adjacent", "Kotlin Multiplatform", "name describes compatibility; no JetBrains or Kotlin mark requested"),
    ),
    "pixijs": spec(
        "the official unmodified PixiJS P mark", "PixiJS 2D web rendering", "one white rounded P on the official square pink field",
        None, None,
        ["recolored mark", "redrawn mark", "diamond", "crystal", "fairy mascot", "browser screenshot"], ["generic lettermark", "cryptocurrency mark"],
        {
            "type": "authorized-brand",
            "source": "https://pixijs.com/branding",
            "trademark_status": "the official branding page expressly recommends the supplied mark for plugin authors; use it unmodified",
            "license": "official PixiJS brand asset terms",
            "authorization": "https://pixijs.com/branding",
        },
    ),
    "scientific-research": spec(
        "a laboratory microscope", "scholarly evidence investigation", "one side-profile microscope with a broad base",
        "one paper sheet", "traceable published evidence",
        ["atom symbol", "flask collection", "AI sparkle"], ["medical diagnostics", "generic web search"],
    ),
    "spec-driven-development": spec(
        "a specification document transforming into a code window", "implementation governed by an explicit specification", "two large panels connected by one broad forward chevron",
        "one code-bracket pair in the destination panel", "the specification becomes implementation",
        ["chart", "graph", "rising line", "magic wand", "approval shield", "document-only checkmark"], ["generic task approval", "file conversion"],
    ),
    "tauri": spec(
        "a native desktop application window", "cross-platform desktop application delivery", "one broad window split into web and native halves",
        "one oversized plug joining both halves", "web-to-native boundary",
        ["Tauri rings and dots", "Tauri logo", "bull or cow mascot", "shield", "lock", "webview screenshot"], ["browser integration", "generic desktop app"],
        brand_source("brand-adjacent", "Tauri", "name describes compatibility; no Tauri mark or mascot requested"),
    ),
    "technology-intelligence": spec(
        "a surveyor compass over a component tile", "evidence-backed technology selection", "one directional compass fused to one square component base",
        "one comparison fork", "contextual choice between options",
        ["vendor logo collage", "ranking podium", "radar chart"], ["career compass", "design drafting compass"],
    ),
}

FALLBACK_HEROES = (
    ("toolbox", "a single open toolbox", "building and operating a capability", "one box silhouette with one raised lid"),
    ("ledger", "a bound field ledger", "traceable knowledge and decisions", "one thick book with one visible tab"),
    ("switchboard", "a compact switchboard", "routing controlled operations", "one panel with two large switches"),
    ("lens", "a handheld inspection lens", "focused analysis and verification", "one large lens joined to one thick handle"),
    ("bridge", "a stone bridge", "connecting systems or stages", "one broad arch with two short piers"),
    ("press", "a workshop press", "transforming inputs into a reliable artifact", "one upright press with a broad platen"),
)


def normalize_plugin_name(plugin_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", plugin_name.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("Plugin name must contain at least one ASCII letter or digit.")
    return normalized


def choose_palette(plugin_name: str, custom: str | None) -> dict[str, str]:
    if custom is not None:
        if HEX_COLOR_RE.fullmatch(custom) is None:
            raise ValueError("--brand-color must use #RRGGBB.")
        return {"name": "custom", "background": f"a full-bleed field anchored on {custom.upper()}", "brandColor": custom.upper(), "foreground": "high-contrast warm white with at most two restrained accents"}
    digest = hashlib.sha256(plugin_name.encode("utf-8")).digest()
    name, background, color, foreground = PALETTES[digest[0] % len(PALETTES)]
    return {"name": name, "background": background, "brandColor": color, "foreground": foreground}


def choose_spec(plugin_name: str) -> tuple[str, str, dict[str, Any]]:
    if plugin_name in ICON_CATALOG:
        return "first-party-catalog", plugin_name, ICON_CATALOG[plugin_name]
    index = hashlib.sha256(plugin_name.encode("utf-8")).digest()[1] % len(FALLBACK_HEROES)
    key, hero, meaning, silhouette = FALLBACK_HEROES[index]
    fallback = spec(
        hero, meaning, silhouette, None, None,
        ["generic abstract geometry", "initials derived from the plugin name", "object collage"],
        ["stock app icon", f"another portfolio icon using a {key}"],
    )
    return "deterministic-fallback", key, fallback


def build_prompt(plugin_name: str, description: str, palette: dict[str, str], semantic: dict[str, Any], avoid: list[str], collisions: list[str], brand: dict[str, str]) -> str:
    purpose = description.strip() or f"the {plugin_name.replace('-', ' ')} plugin"
    hero = semantic["hero"]
    support = semantic["support"]
    support_text = (
        f"Use exactly one subordinate support cue: {support['object']}, meaning {support['meaning']}."
        if support is not None else
        "Use no support cue; the hero must carry the meaning alone."
    )
    return f"""Use case: logo-brand
Asset type: 1024x1024 marketplace plugin icon
Purpose: {purpose}.
Literal semantic hero: {hero['object']}. It communicates {hero['meaning']}.
Silhouette: {hero['silhouette']}. {support_text}
Composition: one centered dominant silhouette, full-bleed opaque background, meaningful content inside the central 72 percent, no more than one support cue.
Small-size requirement: the same hero must remain recognizable at 64, 32, 24, and 16 pixels; keep critical negative space open at 24 pixels.
Style: polished modern bitmap icon, bold filled shapes, crisp edges, restrained dimensional polish, consistent portfolio weight.
Background: {palette['background']}.
Foreground palette: {palette['foreground']}; meaningful adjacent colors meet at least 3:1 contrast.
Brand-source rule: {brand['type']} referencing {brand['source']}; {brand['trademark_status']}. Do not introduce an unlicensed mark or distinctive trade dress.
Avoid: {'; '.join(avoid)}.
Collision avoid: {'; '.join(collisions)}.
Text: none. No letters, words, numbers, watermark, screenshot, photo, UI replica, tiny badge, thin-line detail, mascot, or private identifier.
Do not replace the literal hero with a generic abstract symbol derived only from the plugin name.
"""


def build_contract(args: argparse.Namespace) -> dict[str, Any]:
    plugin_name = normalize_plugin_name(args.plugin_name)
    catalog_source, catalog_key, selected = choose_spec(plugin_name)
    semantic = {"hero": dict(selected["hero"]), "support": dict(selected["support"]) if selected["support"] else None}
    if args.hero:
        semantic["hero"]["object"] = args.hero.strip()
        catalog_source = "user-override"
    if args.hero_meaning:
        semantic["hero"]["meaning"] = args.hero_meaning.strip()
        catalog_source = "user-override"
    if args.hero_silhouette:
        semantic["hero"]["silhouette"] = args.hero_silhouette.strip()
        catalog_source = "user-override"
    if args.support_cue:
        semantic["support"] = {"object": args.support_cue.strip(), "meaning": (args.support_meaning or "clarifies the hero action").strip()}
        catalog_source = "user-override"
    elif args.support_meaning:
        raise ValueError("--support-meaning requires --support-cue.")

    avoid = list(dict.fromkeys([*selected["avoid"], *args.avoid]))
    collisions = list(dict.fromkeys([*selected["collisions"], *args.collision_avoid]))
    brand = dict(selected["brand"])
    for key, value in (
        ("type", args.brand_source_type), ("source", args.brand_source_ref),
        ("trademark_status", args.trademark_status), ("license", args.brand_license),
        ("authorization", args.brand_authorization),
    ):
        if value:
            brand[key] = value.strip()
    if brand["type"] == "authorized-brand" and (
        brand["source"] == "none"
        or brand["license"] == "original-generated-artwork"
        or brand["authorization"] == "not-required-no-brand-mark"
    ):
        raise ValueError(
            "authorized-brand requires explicit --brand-source-ref, --brand-license, "
            "and --brand-authorization evidence."
        )

    palette = choose_palette(plugin_name, args.brand_color)
    return {
        "schema": SCHEMA,
        "plugin_name": plugin_name,
        "catalog": {"source": catalog_source, "key": catalog_key},
        "semantic_hero": semantic["hero"],
        "support_cue": semantic["support"],
        "avoid": avoid,
        "collision_avoid": collisions,
        "brand_source": brand,
        "brandColor": palette["brandColor"],
        "recommended_asset_path": "assets/icon.png",
        "imagegen_mode": "built-in",
        "size_gates": SIZE_GATES,
        "prompt": build_prompt(plugin_name, args.description, palette, semantic, avoid, collisions, brand),
        "checks": [
            "save the selected image as a 1024x1024 opaque RGB PNG at assets/icon.png",
            "inspect semantic recognition and the monochrome silhouette at 16, 24, 32, and 64 px",
            "reject a competing second cue, closed critical gap, portfolio collision, text, screenshot, photo, watermark, or low contrast",
            "verify brand-source, trademark, license, and authorization provenance manually",
            "wire identical interface.composerIcon and interface.logo paths plus interface.brandColor",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a semantic schema-v2 imagegen contract for a plugin icon.")
    parser.add_argument("plugin_name")
    parser.add_argument("--description", default="", help="Short plugin purpose.")
    parser.add_argument("--brand-color", help="Optional #RRGGBB background anchor.")
    parser.add_argument("--hero", help="Override the catalog with one literal hero object.")
    parser.add_argument("--hero-meaning", help="Meaning carried by the hero.")
    parser.add_argument("--hero-silhouette", help="Thumbnail-scale silhouette description.")
    parser.add_argument("--support-cue", help="Optional single subordinate support cue.")
    parser.add_argument("--support-meaning", help="Meaning of the support cue.")
    parser.add_argument("--avoid", action="append", default=[], help="Additional visual to avoid; repeatable.")
    parser.add_argument("--collision-avoid", action="append", default=[], help="Additional portfolio collision to avoid; repeatable.")
    parser.add_argument("--brand-source-type", choices=("original-domain-metaphor", "brand-adjacent", "authorized-brand"))
    parser.add_argument("--brand-source-ref", help="Brand/product referenced, or none.")
    parser.add_argument("--trademark-status", help="Trademark-use rationale.")
    parser.add_argument("--brand-license", help="Asset/license basis.")
    parser.add_argument("--brand-authorization", help="Authorization evidence or status.")
    parser.add_argument("--json", action="store_true", help="Emit the full JSON contract.")
    parser.add_argument("--out", type=Path, help="Write the JSON contract to this path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        contract = build_contract(args)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(contract, indent=2))
    else:
        print(contract["prompt"])
        print(f"brandColor: {contract['brandColor']}")
        print(f"catalog: {contract['catalog']['source']}:{contract['catalog']['key']}")
        print(f"recommended asset path: {contract['recommended_asset_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
