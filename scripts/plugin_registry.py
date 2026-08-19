#!/usr/bin/env python3
"""Shared local plugin identity and selection logic for repository scripts.

Repository scripts that install, validate, or report on plugins need the same
three facts: which plugins this repository owns, which retired plugin IDs still
map onto a current plugin, and how `--plugin`/`--exclude-plugin` arguments turn
into a selection. Keeping those here prevents installer and validator drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


LOCAL_PLUGIN_NAMES = [
    "agent-harness",
    "windows-host-operations",
    "capability-workbench",
    "context-density",
    "i-have-adhd",
    "git-workflows",
    "engineering-hygiene",
    "scientific-research",
    "technology-intelligence",
    "design-intelligence",
    "architecture-intelligence",
    "spec-driven-development",
    "kotlin-multiplatform",
    "tauri",
    "pixijs",
    "game-design-intelligence",
]

LEGACY_PLUGIN_RENAMES = {
    "codex-cli": "agent-harness",
    "claude-code": "agent-harness",
    "scheduled-automation": "agent-harness",
    "gitlab-review": "git-workflows",
    "stacked-delivery": "git-workflows",
    "git-worktree-safety": "git-workflows",
}

CATALOG_WEBSITE_URL = "https://github.com/Xopoko/plug-n-skills"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def canonical_name(name: str) -> str:
    return LEGACY_PLUGIN_RENAMES.get(name, name)


def canonical_names(names: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(canonical_name(name) for name in names))


@dataclass(frozen=True)
class PluginSelection:
    """Outcome of applying include/exclude arguments to available plugins.

    `selected` is empty whenever `unknown` or `overlap` is populated, or when
    every available plugin was excluded. Callers report those cases with the
    error style their command line already uses.
    """

    selected: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    overlap: list[str] = field(default_factory=list)


def resolve_selection(
    included: Sequence[str] | None,
    excluded: Sequence[str] | None,
    *,
    available: Sequence[str],
    default_names: Sequence[str] | None = None,
) -> PluginSelection:
    known = set(available)
    canonical_included = canonical_names(included or [])
    canonical_excluded = canonical_names(excluded or [])
    unknown = sorted((set(canonical_included) | set(canonical_excluded)) - known)
    if unknown:
        return PluginSelection(unknown=unknown)
    overlap = sorted(set(canonical_included) & set(canonical_excluded))
    if overlap:
        return PluginSelection(overlap=overlap)
    base = canonical_included or list(
        default_names if default_names is not None else available
    )
    excluded_set = set(canonical_excluded)
    return PluginSelection(
        selected=[name for name in base if name not in excluded_set]
    )
