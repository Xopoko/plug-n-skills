#!/usr/bin/env python3
"""Resolve the active coding agent and its global paths."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


AGENTS = ("codex", "claude")


class AgentResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentTarget:
    agent: str
    home_dir: Path
    skills_dir: Path
    marketplace_path: Path


def _build(agent: str, home: Path) -> AgentTarget:
    if agent == "codex":
        codex_home = home / ".codex"
        return AgentTarget(
            agent="codex",
            home_dir=codex_home,
            skills_dir=codex_home / "skills",
            marketplace_path=home / ".agents" / "plugins" / "marketplace.json",
        )
    claude_home = home / ".claude"
    return AgentTarget(
        agent="claude",
        home_dir=claude_home,
        skills_dir=claude_home / "skills",
        marketplace_path=claude_home / "plugins" / "marketplace.json",
    )


def resolve_agent(
    *,
    explicit: str | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    home_exists: Callable[[Path], bool] | None = None,
) -> AgentTarget:
    env = dict(os.environ if env is None else env)
    home = Path(home if home is not None else Path.home())
    home_exists = home_exists or (lambda p: p.exists())

    candidate = explicit or env.get("AGENT_TARGET")
    if candidate:
        candidate = candidate.strip().lower()
        if candidate not in AGENTS:
            raise AgentResolutionError(
                f"unknown agent {candidate!r}; expected one of {AGENTS}"
            )
        return _build(candidate, home)

    if "CLAUDE_HOME" in env or "CLAUDECODE" in env:
        return _build("claude", home)
    if "CODEX_HOME" in env:
        return _build("codex", home)

    codex_present = home_exists(home / ".codex")
    claude_present = home_exists(home / ".claude")
    if codex_present and not claude_present:
        return _build("codex", home)
    if claude_present and not codex_present:
        return _build("claude", home)

    if codex_present and claude_present:
        raise AgentResolutionError(
            "both ~/.codex and ~/.claude exist; pass --agent codex|claude "
            "or set AGENT_TARGET"
        )
    raise AgentResolutionError(
        "neither ~/.codex nor ~/.claude exists; pass --agent codex|claude "
        "or set AGENT_TARGET"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", choices=AGENTS, help="Force the target agent.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args(argv)
    try:
        target = resolve_agent(explicit=args.agent)
    except AgentResolutionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    payload = {
        "agent": target.agent,
        "home_dir": str(target.home_dir),
        "skills_dir": str(target.skills_dir),
        "marketplace_path": str(target.marketplace_path),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
