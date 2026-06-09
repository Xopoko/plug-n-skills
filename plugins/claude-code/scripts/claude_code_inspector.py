#!/usr/bin/env python3
"""Inspect the local Claude Code CLI surface without starting a session."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_COMMANDS = [
    "plugin",
    "plugin marketplace",
    "plugin install",
    "plugin validate",
    "mcp",
    "mcp add",
    "agents",
    "project",
    "doctor",
    "auto-mode",
    "ultrareview",
    "install",
    "auth",
]

DANGEROUS_FLAGS = [
    "--dangerously-skip-permissions",
    "--allow-dangerously-skip-permissions",
]

MUTATING_COMMANDS = {
    "auth",
    "install",
    "update",
    "upgrade",
    "setup-token",
    "project purge",
    "plugin install",
    "plugin uninstall",
    "plugin update",
    "plugin marketplace add",
    "plugin marketplace remove",
    "plugin marketplace update",
    "mcp add",
    "mcp remove",
    "mcp reset-project-choices",
    "ultrareview",
}


def clip(text: str, max_chars: int = 2000) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) > max_chars:
        return normalized[: max_chars - 3].rstrip() + "..."
    return normalized


def resolve_claude(explicit: str | None) -> str:
    candidates = [
        explicit,
        os.environ.get("CLAUDE_CLI"),
        shutil.which("claude"),
    ]
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.exists():
            return str(path)
        if os.sep not in raw and shutil.which(raw):
            return str(shutil.which(raw))
    raise SystemExit("claude executable not found; pass --claude or set CLAUDE_CLI")


def run_claude(claude: str, args: list[str], timeout: float) -> dict[str, Any]:
    command = [claude, *args]
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
            "stdout": clip(exc.stdout or ""),
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


def parse_commands(help_text: str) -> list[str]:
    commands: list[str] = []
    in_commands = False
    for line in help_text.splitlines():
        if line.strip() == "Commands:":
            in_commands = True
            continue
        if in_commands:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped == "Options:":
                break
            if stripped.endswith(":"):
                continue
            match = re.match(r"^  ([A-Za-z][A-Za-z0-9-]*(?:\|[A-Za-z0-9-]+)?)(?:\s|$)", line)
            if match:
                commands.append(match.group(1))
    return commands


def parse_options(help_text: str) -> list[str]:
    options: set[str] = set()
    for line in help_text.splitlines():
        for match in re.finditer(r"(?<![\w-])--[A-Za-z0-9][A-Za-z0-9-]*", line):
            options.add(match.group(0))
        short = re.match(r"\s*(-[A-Za-z]),", line)
        if short:
            options.add(short.group(1))
    return sorted(options)


def parse_choices(help_text: str, option: str) -> list[str]:
    lines = help_text.splitlines()
    block = ""
    for index, line in enumerate(lines):
        stripped = line.strip()
        if re.match(rf"^{re.escape(option)}(?:\s|$)", stripped) is None:
            continue
        parts = [line]
        for follow in lines[index + 1 : index + 10]:
            if follow.startswith("  --") and option not in follow:
                break
            parts.append(follow)
        block = "\n".join(parts)
        if "choices:" in block:
            break
    pattern = re.compile(r"\(choices:\s*([^)]+)\)")
    match = pattern.search(block)
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def summarize_help(help_text: str) -> dict[str, Any]:
    options = parse_options(help_text)
    commands = parse_commands(help_text)
    dangerous = [flag for flag in DANGEROUS_FLAGS if flag in help_text]
    permission_modes = parse_choices(help_text, "--permission-mode")
    output_formats = parse_choices(help_text, "--output-format")
    input_formats = parse_choices(help_text, "--input-format")
    return {
        "commands": commands,
        "options": options,
        "dangerous_flags": dangerous,
        "permission_modes": permission_modes,
        "output_formats": output_formats,
        "input_formats": input_formats,
    }


def inspect_command(claude: str, command: str, timeout: float) -> dict[str, Any]:
    parts = command.split()
    result = run_claude(claude, [*parts, "--help"], timeout)
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    return {
        "name": command,
        "ok": result["ok"],
        "returncode": result["returncode"],
        "summary": summarize_help(stdout),
        "mutating": command in MUTATING_COMMANDS,
        "stderr": clip(stderr, 800) if stderr else "",
    }


def inspect(args: argparse.Namespace) -> dict[str, Any]:
    claude = resolve_claude(args.claude)
    version_result = run_claude(claude, ["--version"], args.timeout)
    root_help = run_claude(claude, ["--help"], args.timeout)
    root_stdout = str(root_help.get("stdout") or "")
    root_summary = summarize_help(root_stdout)
    command_names = args.commands or DEFAULT_COMMANDS
    command_reports = [inspect_command(claude, command, args.timeout) for command in command_names]
    return {
        "schema": "claude_code.inspect.v1",
        "claude_path": claude,
        "version": clip(str(version_result.get("stdout") or version_result.get("stderr") or "")),
        "version_ok": version_result["ok"],
        "root_help_ok": root_help["ok"],
        "root": root_summary,
        "commands": command_reports,
        "safety": {
            "dangerous_flags_seen": sorted(
                set(root_summary["dangerous_flags"])
                | {
                    flag
                    for item in command_reports
                    for flag in item["summary"]["dangerous_flags"]
                }
            ),
            "permission_modes": root_summary["permission_modes"],
            "default_guidance": [
                "Prefer permission-mode default or plan for exploratory work.",
                "Use --safe-mode for broken configuration and --bare for minimal explicit-context runs.",
                "Use dangerous skip-permissions flags only inside an explicit external sandbox.",
            ],
        },
    }


def print_text(report: dict[str, Any]) -> None:
    print(f"claude: {report['claude_path']}")
    print(f"version: {report['version'] or '-'}")
    print(f"commands: {', '.join(report['root'].get('commands') or []) or '-'}")
    print(f"permission_modes: {', '.join(report['safety'].get('permission_modes') or []) or '-'}")
    dangerous = ", ".join(report["safety"].get("dangerous_flags_seen") or [])
    print(f"dangerous_flags_seen: {dangerous or '-'}")
    for item in report["commands"]:
        status = "ok" if item.get("ok") else f"failed:{item.get('returncode')}"
        marker = " mutating" if item.get("mutating") else ""
        options = ", ".join(item["summary"].get("options")[:10])
        print(f"{item['name']}: {status}{marker} options={options}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", help="Path to claude executable. Defaults to CLAUDE_CLI or PATH.")
    parser.add_argument("--commands", nargs="*", help="Subcommands to inspect with --help.")
    parser.add_argument("--timeout", type=float, default=8.0, help="Timeout per claude invocation.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = inspect(args)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text(report)
    return 0 if report["version_ok"] and report["root_help_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
