#!/usr/bin/env python3
"""Inspect the local Codex CLI surface without starting an agent session."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_COMMANDS = [
    "exec",
    "review",
    "doctor",
    "mcp",
    "plugin",
    "sandbox",
    "debug",
    "features",
    "app-server",
    "remote-control",
    "resume",
    "fork",
    "archive",
    "unarchive",
]

DANGEROUS_FLAGS = [
    "--dangerously-bypass-approvals-and-sandbox",
    "--dangerously-bypass-hook-trust",
    "--yolo",
]

EXPERIMENTAL_COMMANDS = {
    "app-server",
    "remote-control",
    "cloud",
    "exec-server",
}


def clip(text: str, max_chars: int = 2000) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) > max_chars:
        return normalized[: max_chars - 3].rstrip() + "..."
    return normalized


def resolve_codex(explicit: str | None) -> str:
    candidates = [
        explicit,
        os.environ.get("CODEX_CLI"),
        shutil.which("codex"),
    ]
    for raw in candidates:
        if not raw:
            continue
        path = Path(raw).expanduser()
        if path.exists():
            return str(path)
        if os.sep not in raw and shutil.which(raw):
            return str(shutil.which(raw))
    raise SystemExit("codex executable not found; pass --codex or set CODEX_CLI")


def run_codex(codex: str, args: list[str], timeout: float) -> dict[str, Any]:
    command = [codex, *args]
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
            if not line.strip():
                break
            match = re.match(r"^  ([a-z][a-z0-9-]*)(?:\s{2,}|\s*$)", line)
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


def summarize_help(help_text: str) -> dict[str, Any]:
    options = parse_options(help_text)
    commands = parse_commands(help_text)
    dangerous = [flag for flag in DANGEROUS_FLAGS if flag in help_text]
    experimental = [
        command
        for command in commands
        if command in EXPERIMENTAL_COMMANDS or f"[experimental] {command}" in help_text.lower()
    ]
    return {
        "commands": commands,
        "options": options,
        "dangerous_flags": dangerous,
        "experimental_commands": experimental,
    }


def inspect_command(codex: str, command: str, timeout: float) -> dict[str, Any]:
    parts = command.split()
    result = run_codex(codex, [*parts, "--help"], timeout)
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    return {
        "name": command,
        "ok": result["ok"],
        "returncode": result["returncode"],
        "summary": summarize_help(stdout),
        "stderr": clip(stderr, 800) if stderr else "",
    }


def inspect(args: argparse.Namespace) -> dict[str, Any]:
    codex = resolve_codex(args.codex)
    version_result = run_codex(codex, ["--version"], args.timeout)
    root_help = run_codex(codex, ["--help"], args.timeout)
    root_stdout = str(root_help.get("stdout") or "")
    root_summary = summarize_help(root_stdout)
    command_names = args.commands or [
        command for command in DEFAULT_COMMANDS if command in root_summary["commands"] or command in DEFAULT_COMMANDS
    ]
    command_reports = [inspect_command(codex, command, args.timeout) for command in command_names]
    report: dict[str, Any] = {
        "schema": "codex_cli.inspect.v1",
        "codex_path": codex,
        "version": clip(str(version_result.get("stdout") or version_result.get("stderr") or "")),
        "version_ok": version_result["ok"],
        "root_help_ok": root_help["ok"],
        "root": root_summary,
        "commands": command_reports,
        "safety": {
            "dangerous_flags_seen": sorted(
                {
                    flag
                    for flag in root_summary["dangerous_flags"]
                    for _ in [flag]
                }
                | {
                    flag
                    for item in command_reports
                    for flag in item["summary"]["dangerous_flags"]
                }
            ),
            "default_guidance": [
                "Prefer --sandbox workspace-write --ask-for-approval on-request for ordinary interactive work.",
                "Prefer --sandbox read-only --ask-for-approval never for read-only CI checks.",
                "Use dangerous bypass flags only inside an explicit external sandbox.",
            ],
        },
    }
    if args.include_doctor:
        report["doctor"] = run_codex(codex, ["doctor", "--json"], args.timeout)
    return report


def print_text(report: dict[str, Any]) -> None:
    print(f"codex: {report['codex_path']}")
    print(f"version: {report['version'] or '-'}")
    commands = ", ".join(report["root"].get("commands") or [])
    print(f"commands: {commands or '-'}")
    dangerous = ", ".join(report["safety"].get("dangerous_flags_seen") or [])
    print(f"dangerous_flags_seen: {dangerous or '-'}")
    for item in report["commands"]:
        status = "ok" if item.get("ok") else f"failed:{item.get('returncode')}"
        options = ", ".join(item["summary"].get("options")[:10])
        print(f"{item['name']}: {status} options={options}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", help="Path to codex executable. Defaults to CODEX_CLI or PATH.")
    parser.add_argument("--commands", nargs="*", help="Subcommands to inspect with --help.")
    parser.add_argument("--include-doctor", action="store_true", help="Also run codex doctor --json.")
    parser.add_argument("--timeout", type=float, default=8.0, help="Timeout per codex invocation.")
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
