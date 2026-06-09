#!/usr/bin/env python3
"""Static validation for the local Game Design Intelligence plugin."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
REQUIRED_SKILLS = [
    "game-design-intelligence",
    "gameplay-systems",
    "progression-economy-balance",
    "motivation-retention",
    "onboarding-difficulty",
    "multiplayer-live-service",
]
REQUIRED_REFERENCES = [
    "contracts.md",
    "rubrics.md",
]
FORBIDDEN_FOCUS = [
    "choose game engines",
    "write code",
    "rendering architecture",
    "asset creation workflow",
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def validate_manifest() -> None:
    data = json.loads(read(MANIFEST))
    if data.get("name") != ROOT.name:
        fail("manifest name must match plugin folder")
    if data.get("skills") != "./skills/":
        fail("manifest skills must point to ./skills/")
    interface = data.get("interface") or {}
    if not interface.get("capabilities"):
        fail("manifest interface.capabilities must not be empty")
    long_description = interface.get("longDescription", "")
    for term in ["engines", "graphics", "asset", "programming"]:
        if term not in long_description:
            fail(f"manifest longDescription must state non-goal: {term}")


def validate_skill(slug: str) -> None:
    text = read(ROOT / "skills" / slug / "SKILL.md")
    if not text.startswith("---\n"):
        fail(f"{slug} missing frontmatter")
    match = re.match(r"---\n(.*?)\n---\n", text, flags=re.S)
    if not match:
        fail(f"{slug} malformed frontmatter")
    frontmatter = match.group(1)
    if f"name: {slug}" not in frontmatter:
        fail(f"{slug} frontmatter name mismatch")
    if "description:" not in frontmatter:
        fail(f"{slug} missing description")
    lowered = text.lower()
    if "do not use" not in lowered and "hard boundaries" not in lowered:
        fail(f"{slug} missing non-goal boundary")
    if "output" not in lowered:
        fail(f"{slug} missing output expectations")


def validate_references() -> None:
    for ref in REQUIRED_REFERENCES:
        text = read(ROOT / "references" / ref)
        if len(text.strip()) < 400:
            fail(f"{ref} is too thin")
    references = "\n".join(read(ROOT / "references" / ref) for ref in REQUIRED_REFERENCES)
    for required in [
        "Core Loop",
        "Progression",
        "Economy",
        "Motivation And Retention",
        "Onboarding And Difficulty",
        "Multiplayer And Social Health",
        "Ethical Guardrails",
    ]:
        if required not in references:
            fail(f"references missing design rubric: {required}")


def validate_boundaries() -> None:
    all_text = "\n".join(
        read(ROOT / "skills" / slug / "SKILL.md") for slug in REQUIRED_SKILLS
    ).lower()
    for phrase in FORBIDDEN_FOCUS:
        if phrase in all_text and "do not" not in all_text[max(0, all_text.find(phrase) - 80):all_text.find(phrase) + 80]:
            fail(f"forbidden focus appears without nearby boundary: {phrase}")
    for boundary in ["engine", "graphics", "asset", "programming", "dark-pattern"]:
        if boundary not in all_text:
            fail(f"missing boundary keyword: {boundary}")


def main() -> None:
    validate_manifest()
    for slug in REQUIRED_SKILLS:
        validate_skill(slug)
    validate_references()
    validate_boundaries()
    print("OK: Game Design Intelligence plugin static validation passed")


if __name__ == "__main__":
    main()
