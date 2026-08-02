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


@dataclass(frozen=True)
class CodexPluginStatePaths:
    home_dir: Path | None
    config_path: Path
    cache_root: Path
    config_explicit: bool
    cache_explicit: bool


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


def resolve_active_codex_home(
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    cwd: Path | None = None,
) -> Path:
    """Resolve the install-safe Codex home without guessing or creating it."""
    env = dict(os.environ if env is None else env)
    home = Path(home if home is not None else Path.home())
    cwd = Path(cwd if cwd is not None else Path.cwd())
    configured = env.get("CODEX_HOME")
    if configured is None or configured == "":
        candidate = home / ".codex"
        if candidate.exists() or candidate.is_symlink():
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError, ValueError) as exc:
                raise AgentResolutionError(
                    "default Codex home must resolve to an existing directory"
                ) from exc
            if not resolved.is_dir():
                raise AgentResolutionError(
                    "default Codex home must resolve to an existing directory"
                )
            return resolved
        return candidate.resolve()

    candidate = Path(configured)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise AgentResolutionError(
            "CODEX_HOME must resolve to an existing directory"
        ) from exc
    if not resolved.is_dir():
        raise AgentResolutionError("CODEX_HOME must resolve to an existing directory")
    return resolved


def resolve_codex_plugin_state_paths(
    *,
    config_path: str | Path | None,
    cache_root: str | Path | None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    cwd: Path | None = None,
) -> CodexPluginStatePaths:
    """Apply CLI override precedence to Codex plugin config/cache paths."""
    cwd = Path(cwd if cwd is not None else Path.cwd())
    config_explicit = config_path is not None
    cache_explicit = cache_root is not None
    active_home = None
    if not (config_explicit and cache_explicit):
        active_home = resolve_active_codex_home(env=env, home=home, cwd=cwd)

    def explicit_path(
        value: str | Path,
        label: str,
        *,
        canonicalize: bool,
    ) -> Path:
        if isinstance(value, str) and not value.strip():
            raise AgentResolutionError(f"{label} must not be empty")
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = cwd / candidate
        return candidate.resolve() if canonicalize else candidate

    resolved_config = (
        explicit_path(config_path, "--config-path", canonicalize=True)
        if config_explicit
        else active_home / "config.toml"
    )
    if resolved_config.exists() and not resolved_config.is_file():
        raise AgentResolutionError(
            "Codex config path must be a regular file when it already exists"
        )
    resolved_cache = (
        explicit_path(cache_root, "--cache-root", canonicalize=False)
        if cache_explicit
        else active_home / "plugins" / "cache"
    )
    if resolved_cache.is_symlink():
        raise AgentResolutionError("plugin cache root must not be a symlink")
    if resolved_cache.exists() and not resolved_cache.is_dir():
        raise AgentResolutionError(
            "plugin cache root must be a directory when it already exists"
        )
    return CodexPluginStatePaths(
        home_dir=active_home,
        config_path=resolved_config,
        cache_root=resolved_cache,
        config_explicit=config_explicit,
        cache_explicit=cache_explicit,
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
