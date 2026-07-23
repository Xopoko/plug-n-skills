#!/usr/bin/env python3
"""Validate repository-level quality gates for Plug'n Skills."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


PLUGIN_NAMES = [
    "build-swift-apps",
    "pixijs",
    "tauri",
    "scientific-research",
    "context-density",
    "capability-workbench",
    "codex-cli",
    "scheduled-automation",
    "gitlab-review",
    "stacked-delivery",
    "claude-code",
    "architecture-intelligence",
    "design-intelligence",
    "game-design-intelligence",
    "kotlin-multiplatform",
    "spec-driven-development",
]

TEXT_EXTENSIONS = {
    "",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_DIR_NAMES = {
    ".git",
    ".agents",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".tox",
    ".venv",
    "venv",
}
ROOT_SCRATCH_DIRS = {
    "research",
    "skill-synthesis",
    "tmp",
    "temp",
    "output",
    "scratch",
    "reports",
}
PLUGIN_SCRATCH_DIRS = {
    "research",
    "synthesis",
    "tmp",
    "temp",
    "output",
    "scratch",
    "reports",
}
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
LOCAL_PATH_RE = re.compile("/" + "Users/" + r"[A-Za-z0-9._-]+/")
LOCAL_PROJECT_PATH_RE = re.compile(r"~/" + "Projects/")
SECRET_PATTERNS = [
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]
PRIVATE_PROJECT_TERMS = [
    "B2" + "Broker",
    "B2" + "Core",
    "Movie" + "Swipe",
    "Kino" + "Cue",
    "Ton" + "go",
    "Codex" + "Quest",
    "Philo" + "script",
    "Rybo" + "ria",
    "Sc" + "out",
    "Pre" + "ply",
    "Carp" + "Fishing",
    ".codex" + "-care",
]
PRIVATE_PROJECT_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(term) for term in PRIVATE_PROJECT_TERMS if not term.startswith("."))
    + r"|PAN-\d+)\b|"
    + re.escape(".codex" + "-care")
)
GRANDIOSE_TERMS = [
    "best-" + "of-breed",
    "world-" + "class",
    "revolution" + "ary",
    "unparallel" + "ed",
    "unmatch" + "ed",
    "ulti" + "mate",
    "strong" + "est",
    "exhaust" + "ive",
]
GRANDIOSE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in GRANDIOSE_TERMS) + r")\b",
    re.IGNORECASE,
)
PRIVATE_ORG_WORDS = [
    "comp" + "any",
    "comp" + "anies",
    "custom" + "er",
    "custom" + "ers",
]
PRIVATE_ORG_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in PRIVATE_ORG_WORDS) + r")\b",
    re.IGNORECASE,
)
LEGACY_BRAND_TERMS = [
    "Xopoko/" + "plugins",
    "github.com/Xopoko/" + "plugins",
    "xopoko-" + "plugins",
    "Xopoko/" + "power" + "packs",
    "github.com/Xopoko/" + "power" + "packs",
    "xopoko-" + "power" + "packs",
    "# Agent " + "Plugins",
    "Agent " + "Plugins collection",
    "Agent " + "Plugin Collection",
    "# Agent " + "Power" + "packs",
    "Agent " + "Power" + "packs",
    "power" + "packs",
    "Power" + "packs",
    "power" + "pack",
    "Power" + "pack",
]
LEGACY_BRAND_RE = re.compile(
    r"(?:" + "|".join(re.escape(term) for term in LEGACY_BRAND_TERMS) + r")"
)
PRIVATE_TOOL_TERMS = [
    "codex-" + "token-" + "lens",
    "Codex" + "Token" + "Lens",
]
PRIVATE_TOOL_RE = re.compile(
    r"(?:" + "|".join(re.escape(term) for term in PRIVATE_TOOL_TERMS) + r")"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> None:
    root = repo_root()
    errors: list[str] = []
    validate_helper = root / "plugins" / "capability-workbench" / "scripts" / "plugin" / "validate_plugin.py"
    if not validate_helper.is_file():
        errors.append(f"missing validator: {validate_helper}")

    for name in PLUGIN_NAMES:
        plugin_dir = root / "plugins" / name
        if not plugin_dir.is_dir():
            errors.append(f"missing plugin directory: plugins/{name}")
            continue
        manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
        manifest = load_json(manifest_path, errors)
        if manifest is not None:
            validate_manifest_metadata(name, manifest, errors)
        claude_path = plugin_dir / ".claude-plugin" / "plugin.json"
        claude_manifest = load_json(claude_path, errors)
        if claude_manifest is not None:
            if claude_manifest.get("name") != name:
                errors.append(f"plugins/{name}/.claude-plugin/plugin.json: name must match directory")
            if claude_manifest.get("license") != "MIT":
                errors.append(f"plugins/{name}/.claude-plugin/plugin.json: license must be MIT")
            if manifest is not None and claude_manifest.get("name") != manifest.get("name"):
                errors.append(f"plugins/{name}: claude/codex manifest name mismatch")
        if validate_helper.is_file():
            result = subprocess.run(
                [sys.executable, str(validate_helper), str(plugin_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode != 0:
                errors.append(
                    f"Codex plugin validation failed for {name}:\n{result.stdout}{result.stderr}"
                )

    errors.extend(validate_marketplace(root))
    errors.extend(scan_files(root))

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Repository validation passed")


def load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"missing JSON file: {path.relative_to(repo_root())}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path.relative_to(repo_root())}: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"JSON file must contain an object: {path.relative_to(repo_root())}")
        return None
    return payload


def validate_manifest_metadata(name: str, manifest: dict[str, Any], errors: list[str]) -> None:
    rel = f"plugins/{name}/.codex-plugin/plugin.json"
    if manifest.get("name") != name:
        errors.append(f"{rel}: manifest name must match directory")
    if manifest.get("license") != "MIT":
        errors.append(f"{rel}: license must be MIT")
    repository = manifest.get("repository")
    if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
        errors.append(f"{rel}: repository must be a GitHub URL")
    author = manifest.get("author")
    if isinstance(author, dict):
        author_name = author.get("name")
        if isinstance(author_name, str) and "Local" in author_name:
            errors.append(f"{rel}: author name should not include local-only branding")
    interface = manifest.get("interface")
    if isinstance(interface, dict):
        developer = interface.get("developerName")
        if isinstance(developer, str) and "Local" in developer:
            errors.append(f"{rel}: developerName should not include local-only branding")


def validate_marketplace(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / ".claude-plugin" / "marketplace.json"
    data = load_json(path, errors)
    if data is None:
        return errors
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        errors.append(".claude-plugin/marketplace.json: 'plugins' must be an array")
        return errors
    listed = []
    for entry in plugins:
        name = entry.get("name") if isinstance(entry, dict) else None
        src = entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(name, str):
            errors.append(".claude-plugin/marketplace.json: entry missing 'name'")
            continue
        listed.append(name)
        if not isinstance(src, str) or not (root / src.lstrip("./")).is_dir():
            errors.append(f".claude-plugin/marketplace.json: bad source for {name}")
        if not (root / "plugins" / name / ".claude-plugin" / "plugin.json").is_file():
            errors.append(f".claude-plugin/marketplace.json: {name} lacks a Claude manifest")
    if set(listed) != set(PLUGIN_NAMES):
        errors.append(".claude-plugin/marketplace.json: plugin set does not match PLUGIN_NAMES")
    return errors


def scan_files(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*"):
        if should_skip_scan(root, path):
            continue
        if path.name in {".DS_Store"} or path.suffix == ".pyc":
            errors.append(f"generated artifact must not be committed: {path.relative_to(root)}")
            continue
        if not path.is_file() or path.suffix not in TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root)
        if CYRILLIC_RE.search(text):
            errors.append(f"{rel}: contains Cyrillic characters")
        if LOCAL_PATH_RE.search(text) or LOCAL_PROJECT_PATH_RE.search(text):
            errors.append(f"{rel}: contains a machine-specific home path")
        if PRIVATE_PROJECT_RE.search(text):
            errors.append(f"{rel}: contains a private project or issue-key reference")
        if GRANDIOSE_RE.search(text):
            errors.append(f"{rel}: contains inflated publication wording")
        if PRIVATE_ORG_WORD_RE.search(text):
            errors.append(f"{rel}: contains private-organization wording")
        if LEGACY_BRAND_RE.search(text):
            errors.append(f"{rel}: contains legacy repository branding")
        if PRIVATE_TOOL_RE.search(text):
            errors.append(f"{rel}: contains a private local tool dependency")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{rel}: matches sensitive pattern {pattern.pattern}")
    return errors


def should_skip_scan(root: Path, path: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    if parts and (
        parts[0] in ROOT_SCRATCH_DIRS
        or any(parts[0].startswith(prefix + "-") for prefix in ROOT_SCRATCH_DIRS)
    ):
        return True
    if len(parts) >= 2 and parts[0] == "docs" and parts[1] == "superpowers":
        return True
    if len(parts) >= 3 and parts[0] == "plugins" and parts[2] in PLUGIN_SCRATCH_DIRS:
        return True
    return False


if __name__ == "__main__":
    main()
