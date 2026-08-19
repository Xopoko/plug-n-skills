#!/usr/bin/env python3
"""Shared read-only helpers for agent CLI inspectors.

Inspectors in this folder probe a coding-agent CLI by running `--version` and
`--help` and parsing the output. They all need the same primitives: locate the
executable from an explicit path, an environment variable, or `PATH`; run it
with a timeout and never raise; clip noisy text; and read commands and options
out of help text. Tool-specific vocabulary stays in the inspector.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


OPTION_RE = re.compile(r"(?<![\w-])--[A-Za-z0-9][A-Za-z0-9-]*")
SHORT_OPTION_RE = re.compile(r"\s*(-[A-Za-z]),")


def clip(text: str, max_chars: int = 2000) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) > max_chars:
        return normalized[: max_chars - 3].rstrip() + "..."
    return normalized


def _as_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def resolve_executable(explicit: str | None, *, program: str, env_var: str, flag: str) -> str:
    for raw in (explicit, os.environ.get(env_var), shutil.which(program)):
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.exists():
            return str(path)
        if os.sep not in raw and shutil.which(raw):
            return str(shutil.which(raw))
    raise SystemExit(f"{program} executable not found; pass {flag} or set {env_var}")


def run_cli(executable: str, args: list[str], timeout: float) -> dict[str, Any]:
    command = [executable, *args]
    try:
        completed = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "ok": False,
            "returncode": None,
            "stdout": clip(_as_text(exc.stdout)),
            "stderr": "timeout",
        }
    except OSError as exc:
        return {
            "command": command,
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "command": command,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_commands(
    help_text: str,
    entry_re: re.Pattern[str],
    *,
    stop_on_blank: bool = True,
) -> list[str]:
    """Read subcommand names out of the `Commands:` section of help text.

    `stop_on_blank` ends the section at the first blank line, which suits help
    output with a single flat command list. Otherwise blank lines and nested
    headings are skipped and the section ends at `Options:`.
    """

    commands: list[str] = []
    in_commands = False
    for line in help_text.splitlines():
        stripped = line.strip()
        if stripped == "Commands:":
            in_commands = True
            continue
        if not in_commands:
            continue
        if not stripped:
            if stop_on_blank:
                break
            continue
        if not stop_on_blank:
            if stripped == "Options:":
                break
            if stripped.endswith(":"):
                continue
        match = entry_re.match(line)
        if match:
            commands.append(match.group(1))
    return commands


def parse_options(help_text: str) -> list[str]:
    options: set[str] = set()
    for line in help_text.splitlines():
        options.update(match.group(0) for match in OPTION_RE.finditer(line))
        short = SHORT_OPTION_RE.match(line)
        if short:
            options.add(short.group(1))
    return sorted(options)
