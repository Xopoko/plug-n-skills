#!/usr/bin/env python3
"""Resolve the active coding agent and its global paths.

Supported agents: codex, claude, cursor. Resolution is deterministic and
idempotent: explicit argument, then the AGENT_TARGET env var, then in-session
env markers, then the single existing agent home. Ambiguity is an error with
an explicit escape hatch, never a guess.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping


AGENTS = ("codex", "claude", "cursor")

# In-session markers checked in order. Claude is checked before Cursor because
# Claude Code running inside the Cursor IDE inherits Cursor's markers too.
ENV_MARKERS = (
    ("claude", ("CLAUDECODE", "CLAUDE_HOME")),
    ("cursor", ("CURSOR_AGENT", "CURSOR_TRACE_ID", "CURSOR_HOME")),
    ("codex", ("CODEX_HOME",)),
)


class AgentResolutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentTarget:
    agent: str
    home_dir: Path
    skills_dir: Path
    # None when the agent has no plugin marketplace (e.g. cursor).
    marketplace_path: Path | None


def _build(agent: str, home: Path, env: Mapping[str, str]) -> AgentTarget:
    if agent == "codex":
        agent_home = Path(env.get("CODEX_HOME") or home / ".codex")
        return AgentTarget(
            agent="codex",
            home_dir=agent_home,
            skills_dir=agent_home / "skills",
            marketplace_path=home / ".agents" / "plugins" / "marketplace.json",
        )
    if agent == "claude":
        agent_home = Path(env.get("CLAUDE_HOME") or home / ".claude")
        return AgentTarget(
            agent="claude",
            home_dir=agent_home,
            skills_dir=agent_home / "skills",
            marketplace_path=agent_home / "plugins" / "marketplace.json",
        )
    if agent == "cursor":
        agent_home = Path(env.get("CURSOR_HOME") or home / ".cursor")
        return AgentTarget(
            agent="cursor",
            home_dir=agent_home,
            skills_dir=agent_home / "skills",
            marketplace_path=None,
        )
    raise AgentResolutionError(f"unknown agent {agent!r}; expected one of {AGENTS}")


def iter_agents(
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> tuple[AgentTarget, ...]:
    """All known agent targets, whether or not their homes exist."""
    env = dict(os.environ if env is None else env)
    home = Path(home if home is not None else Path.home())
    return tuple(_build(agent, home, env) for agent in AGENTS)


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
        return _build(candidate, home, env)

    for agent, markers in ENV_MARKERS:
        if any(marker in env for marker in markers):
            return _build(agent, home, env)

    present = [
        agent for agent in AGENTS if home_exists(_build(agent, home, env).home_dir)
    ]
    if len(present) == 1:
        return _build(present[0], home, env)
    if not present:
        raise AgentResolutionError(
            "no agent home found (~/.codex, ~/.claude, ~/.cursor); "
            "pass --agent codex|claude|cursor or set AGENT_TARGET"
        )
    raise AgentResolutionError(
        f"multiple agent homes exist ({', '.join(present)}); "
        "pass --agent codex|claude|cursor or set AGENT_TARGET"
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
        "marketplace_path": (
            str(target.marketplace_path) if target.marketplace_path else None
        ),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print(f"{key}={value if value is not None else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
