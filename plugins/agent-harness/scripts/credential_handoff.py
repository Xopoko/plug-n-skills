#!/usr/bin/env python3
"""Launch a secret-free command in a user-visible Windows console.

The agent-facing process receives only an allowlisted status receipt. The
detached console inherits the target's stdin/stdout/stderr so a human can use
the native credential prompt without returning keystrokes or transcript text
to the caller.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


REQUEST_SCHEMA = "agent_harness.credential_handoff_request.v1"
STATUS_SCHEMA = "agent_harness.credential_handoff_status.v1"
LOCK_SCHEMA = "agent_harness.credential_handoff_lock.v1"
LOCK_DIR_NAME = ".credential-handoff.lock"
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
ALL_STATES = {"launched", "running", *TERMINAL_STATES}
ERROR_CODES = {
    "console_launch_failed",
    "invalid_request",
    "target_launch_failed",
    "target_not_found",
    "working_directory_missing",
}
SENSITIVE_OPTIONS = {
    "--access-token",
    "--api-key",
    "--apikey",
    "--authorization",
    "--client-secret",
    "--pass",
    "--passphrase",
    "--passwd",
    "--password",
    "--refresh-token",
    "--secret",
    "--token",
}
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)^(?:[A-Z0-9_]*(?:PASSWORD|PASSWD|PASSPHRASE|TOKEN|SECRET|API_KEY|PRIVATE_KEY)[A-Z0-9_]*)=(.*)$"
)
URL_CREDENTIALS = re.compile(r"(?i)^[a-z][a-z0-9+.-]*://[^/@:\s]+:[^/@\s]+@")
TOKEN_LIKE_VALUE = re.compile(r"^[A-Za-z0-9_+/=-]{40,}$")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
REQUEST_DIR = re.compile(r"^credential-handoff-[0-9a-f]{32}$")
REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
COMMAND_LAUNCHERS = {
    "bash",
    "bun",
    "cscript",
    "cmd",
    "command",
    "dash",
    "deno",
    "dotnet",
    "env",
    "fish",
    "java",
    "javaw",
    "mshta",
    "node",
    "perl",
    "powershell",
    "pwsh",
    "python",
    "python3",
    "regsvr32",
    "ruby",
    "rundll32",
    "sh",
    "wscript",
    "wsl",
    "zsh",
}
EXECUTABLE_HASH = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_NATIVE_SUFFIXES = {".com", ".exe"}
SENSITIVE_ENV_NAME = re.compile(
    r"(?i)(?:PASSWORD|PASSWD|PASSPHRASE|TOKEN|SECRET|API_KEY|ACCESS_KEY|PRIVATE_KEY|SIGNING_KEY|AUTHORIZATION|AUTH_SOCK|AGENT_INFO|COOKIE|CREDENTIAL)"
)


class UserFacingError(ValueError):
    """A safe error message intended for the agent-facing caller."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise UserFacingError("handoff state is missing or invalid") from error
    if not isinstance(payload, dict):
        raise UserFacingError("handoff state must be a JSON object")
    return payload


def normalize_command(raw: Sequence[str]) -> list[str]:
    command = list(raw)
    if command and command[0] == "--":
        command.pop(0)
    if not command:
        raise UserFacingError("a target command is required after --")
    return command


def executable_is_launcher(executable: Path) -> bool:
    stem = executable.stem.lower()
    return stem in COMMAND_LAUNCHERS or bool(
        re.fullmatch(r"python(?:\d+(?:\.\d+)*)?", stem)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise UserFacingError("could not verify the pinned target executable") from error
    return digest.hexdigest()


def canonical_pinned_executable(
    raw_path: str,
    expected_sha256: str | None,
    *,
    label: str,
) -> Path:
    if expected_sha256 is None or not EXECUTABLE_HASH.fullmatch(expected_sha256.lower()):
        raise UserFacingError(f"{label} requires a lowercase SHA-256 pin")
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        raise UserFacingError(f"{label} must be an absolute executable path")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise UserFacingError(f"{label} executable is missing") from error
    if not resolved.is_file() or resolved.suffix.lower() not in WINDOWS_NATIVE_SUFFIXES:
        raise UserFacingError(f"{label} must be a native .exe or .com file")
    if executable_is_launcher(resolved):
        raise UserFacingError(
            f"{label} cannot be a shell, interpreter, or generic command launcher"
        )
    actual_sha256 = sha256_file(resolved)
    if not hmac.compare_digest(actual_sha256, expected_sha256.lower()):
        raise UserFacingError(f"{label} executable hash does not match its pin")
    return resolved


def prepare_pinned_command(
    command: Sequence[str],
    *,
    executable_sha256: str | None,
    op_target_sha256: str | None,
) -> list[str]:
    prepared = list(command)
    validate_nonsecret_command(prepared)
    executable = canonical_pinned_executable(
        prepared[0], executable_sha256, label="target"
    )
    prepared[0] = str(executable)

    is_op = executable.stem.lower() == "op"
    op_words = [value.lower() for value in prepared[1:]] if is_op else []
    is_op_run = bool(op_words) and (
        op_words[0] == "run" or op_words[:2] == ["plugin", "run"]
    )
    if is_op_run:
        separator = prepared.index("--")
        target_index = separator + 1
        prepared[target_index] = str(
            canonical_pinned_executable(
                prepared[target_index],
                op_target_sha256,
                label="op target",
            )
        )
    elif op_target_sha256 is not None:
        raise UserFacingError("--op-target-sha256 is valid only for op run")
    return prepared


def validate_nonsecret_command(command: Sequence[str]) -> None:
    """Reject common shapes that would persist or reveal a secret value."""

    if not command:
        raise UserFacingError("target command is empty")

    joined = " ".join(command).lower()
    executable = Path(command[0]).stem.lower()
    if executable_is_launcher(Path(command[0])):
        raise UserFacingError(
            "shells, interpreters, and generic command launchers are not allowed"
        )
    if executable == "op":
        op_words = [value.lower() for value in command[1:]]
        is_version = op_words == ["--version"] or op_words == ["version"]
        is_account_list = op_words[:2] == ["account", "list"]
        is_run = bool(op_words) and op_words[0] == "run"
        is_plugin_run = op_words[:2] == ["plugin", "run"]
        if not (is_version or is_account_list or is_run or is_plugin_run):
            raise UserFacingError(
                "direct 1Password retrieval or administration is not allowed; use op run"
            )
        if (is_run or is_plugin_run) and (
            "--" not in command or command.index("--") == len(command) - 1
        ):
            raise UserFacingError("op run requires an exact target command after --")
    if re.search(r"(?:^|\s)op(?:\.exe)?\s+read(?:\s|$)", joined):
        raise UserFacingError("embedded 'op read' is not allowed")

    for argument in command:
        if any(ord(character) < 32 for character in argument):
            raise UserFacingError("target arguments must not contain control characters")
        lowered = argument.lower()
        if lowered == "--no-masking":
            raise UserFacingError("1Password output masking must remain enabled")
        if lowered in SENSITIVE_OPTIONS or any(
            lowered.startswith(f"{option}=") for option in SENSITIVE_OPTIONS
        ):
            raise UserFacingError(
                f"secret-bearing command option is not allowed: {lowered.split('=', 1)[0]}"
            )
        assignment = SENSITIVE_ASSIGNMENT.match(argument)
        if assignment and not assignment.group(1).lower().startswith("op://"):
            raise UserFacingError("resolved secret assignments are not allowed")
        if URL_CREDENTIALS.match(argument):
            raise UserFacingError("credentials embedded in a URL are not allowed")
        if TOKEN_LIKE_VALUE.fullmatch(argument) and not argument.lower().startswith("op://"):
            raise UserFacingError("token-like command arguments are not allowed")
        if "authorization:" in lowered or "bearer " in lowered:
            raise UserFacingError("authorization headers or bearer tokens are not allowed")
        if "-----begin private key-----" in lowered:
            raise UserFacingError("private key material is not allowed")


def status_payload(
    request_id: str,
    state: str,
    created_at_utc: str,
    *,
    exit_code: int | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    if not REQUEST_ID.fullmatch(request_id):
        raise ValueError("request_id must be 32 lowercase hexadecimal characters")
    if state not in ALL_STATES:
        raise ValueError(f"unsupported state: {state}")
    if error_code is not None and error_code not in ERROR_CODES:
        raise ValueError(f"unsupported error code: {error_code}")
    payload: dict[str, Any] = {
        "schema": STATUS_SCHEMA,
        "request_id": request_id,
        "state": state,
        "exit_code": exit_code,
        "created_at_utc": created_at_utc,
        "updated_at_utc": utc_now(),
    }
    if error_code is not None:
        payload["error_code"] = error_code
    return payload


def validate_status_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema",
        "request_id",
        "state",
        "exit_code",
        "created_at_utc",
        "updated_at_utc",
        "error_code",
    }
    required = allowed - {"error_code"}
    if set(payload) - allowed or not required.issubset(payload):
        raise UserFacingError("handoff status has an invalid field set")
    if payload.get("schema") != STATUS_SCHEMA:
        raise UserFacingError("unsupported handoff status schema")
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise UserFacingError("handoff status has an invalid request ID")
    state = payload.get("state")
    if state not in ALL_STATES:
        raise UserFacingError("handoff status has an invalid state")
    exit_code = payload.get("exit_code")
    if exit_code is not None and (not isinstance(exit_code, int) or isinstance(exit_code, bool)):
        raise UserFacingError("handoff status has an invalid exit code")
    if state not in TERMINAL_STATES and exit_code is not None:
        raise UserFacingError("non-terminal handoff status cannot have an exit code")
    error_code = payload.get("error_code")
    if error_code is not None and error_code not in ERROR_CODES:
        raise UserFacingError("handoff status has an invalid error code")
    for field in ("created_at_utc", "updated_at_utc"):
        value = payload.get(field)
        if not isinstance(value, str):
            raise UserFacingError(f"handoff status has an invalid {field}")
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise UserFacingError(f"handoff status has an invalid {field}") from error
    return payload


def read_owned_status(status_path: Path) -> tuple[Path, dict[str, Any]]:
    resolved = status_path.expanduser().resolve()
    request_dir = resolved.parent
    if resolved.name != "status.json" or not REQUEST_DIR.fullmatch(request_dir.name):
        raise UserFacingError("status path is not an owned handoff directory")
    payload = validate_status_receipt(read_json(resolved))
    expected_request_id = request_dir.name.removeprefix("credential-handoff-")
    if payload["request_id"] != expected_request_id:
        raise UserFacingError("handoff status does not match its request directory")
    return resolved, payload


def build_child_environment(env_references: dict[str, str]) -> dict[str, str]:
    """Drop unrelated inherited credentials, then add unresolved op references."""

    environment = {
        name: value
        for name, value in os.environ.items()
        if not SENSITIVE_ENV_NAME.search(name)
    }
    environment.update(env_references)
    return environment


def validate_lock_owner(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"schema", "request_id", "worker_pid"}:
        raise UserFacingError("credential handoff lock has an invalid field set")
    if payload.get("schema") != LOCK_SCHEMA:
        raise UserFacingError("credential handoff lock has an invalid schema")
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise UserFacingError("credential handoff lock has an invalid request ID")
    worker_pid = payload.get("worker_pid")
    if worker_pid is not None and (
        not isinstance(worker_pid, int) or isinstance(worker_pid, bool) or worker_pid <= 0
    ):
        raise UserFacingError("credential handoff lock has an invalid worker PID")
    return payload


def acquire_state_lock(state_root: Path, request_id: str) -> Path:
    lock_dir = state_root / LOCK_DIR_NAME
    try:
        lock_dir.mkdir(mode=0o700)
    except FileExistsError as error:
        raise UserFacingError("an active or unrecovered credential handoff exists") from error
    try:
        atomic_write_json(
            lock_dir / "owner.json",
            {"schema": LOCK_SCHEMA, "request_id": request_id, "worker_pid": None},
        )
    except Exception:
        try:
            lock_dir.rmdir()
        except OSError:
            pass
        raise
    return lock_dir


def read_lock_owner(lock_dir: Path) -> dict[str, Any]:
    if lock_dir.name != LOCK_DIR_NAME or not lock_dir.is_dir():
        raise UserFacingError("credential handoff lock is missing or invalid")
    return validate_lock_owner(read_json(lock_dir / "owner.json"))


def bind_lock_to_worker(lock_dir: Path, request_id: str) -> None:
    owner = read_lock_owner(lock_dir)
    if owner["request_id"] != request_id:
        raise UserFacingError("credential handoff lock belongs to another request")
    atomic_write_json(
        lock_dir / "owner.json",
        {"schema": LOCK_SCHEMA, "request_id": request_id, "worker_pid": os.getpid()},
    )


def release_state_lock(lock_dir: Path, request_id: str) -> None:
    owner = read_lock_owner(lock_dir)
    if owner["request_id"] != request_id:
        raise UserFacingError("credential handoff lock belongs to another request")
    entries = {path.name for path in lock_dir.iterdir()}
    if entries != {"owner.json"}:
        raise UserFacingError("credential handoff lock contains unexpected files")
    (lock_dir / "owner.json").unlink()
    lock_dir.rmdir()


def set_console_title(title: str) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleTitleW(title)
    except (AttributeError, OSError):
        pass


def bind_console_streams() -> None:
    """Bind Python streams to the worker's new console, never the caller pipes."""

    if os.name != "nt":
        return
    sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)


def parse_env_references(values: Sequence[str]) -> dict[str, str]:
    references: dict[str, str] = {}
    for value in values:
        name, separator, reference = value.partition("=")
        if not separator or not ENV_NAME.fullmatch(name):
            raise UserFacingError("--env-reference must use NAME=op://vault/item/field")
        if not reference.lower().startswith("op://"):
            raise UserFacingError("--env-reference values must be 1Password references")
        if any(ord(character) < 32 for character in reference):
            raise UserFacingError("secret references must not contain control characters")
        references[name] = reference
    return references


def run_worker(request_path: Path) -> int:
    bind_console_streams()
    request_path = request_path.expanduser().resolve()
    if (
        request_path.name != "request.json"
        or not REQUEST_DIR.fullmatch(request_path.parent.name)
    ):
        raise UserFacingError("request path is not an owned handoff directory")
    request = read_json(request_path)
    if request.get("schema") != REQUEST_SCHEMA:
        raise UserFacingError("unsupported handoff request schema")

    request_id = str(request["request_id"])
    expected_request_id = request_path.parent.name.removeprefix("credential-handoff-")
    if request_id != expected_request_id:
        raise UserFacingError("handoff request does not match its directory")
    created_at = str(request["created_at_utc"])
    status_path = request_path.parent / "status.json"
    lock_dir = request_path.parent.parent / LOCK_DIR_NAME
    bind_lock_to_worker(lock_dir, request_id)
    command = prepare_pinned_command(
        [str(value) for value in request["command"]],
        executable_sha256=str(request["executable_sha256"]),
        op_target_sha256=(
            str(request["op_target_sha256"])
            if request.get("op_target_sha256") is not None
            else None
        ),
    )
    env_references = {
        str(name): str(reference)
        for name, reference in dict(request.get("env_references", {})).items()
    }
    parse_env_references(
        [f"{name}={reference}" for name, reference in env_references.items()]
    )
    working_directory = request.get("cwd")
    if working_directory is not None and not Path(str(working_directory)).is_dir():
        atomic_write_json(
            status_path,
            status_payload(
                request_id,
                "failed",
                created_at,
                error_code="working_directory_missing",
            ),
        )
        release_state_lock(lock_dir, request_id)
        return 2

    set_console_title(str(request["title"]))
    atomic_write_json(status_path, status_payload(request_id, "running", created_at))

    print("Agent credential handoff")
    print(f"Purpose: {request['purpose']}")
    print(f"Expected input: {request['expected_input']}")
    print(f"Native program: {Path(command[0]).name}")
    print("Enter secrets only into the native prompt in this window.")
    print("This window is not captured by the agent-facing status channel.\n")

    exit_code: int
    state: str
    error_code: str | None = None
    try:
        child_environment = build_child_environment(env_references)
        completed = subprocess.run(
            command,
            cwd=str(working_directory) if working_directory is not None else None,
            env=child_environment,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            check=False,
        )
        exit_code = completed.returncode
        state = "succeeded" if exit_code == 0 else "failed"
    except KeyboardInterrupt:
        exit_code = 130
        state = "cancelled"
    except FileNotFoundError:
        exit_code = 127
        state = "failed"
        error_code = "target_not_found"
    except OSError:
        exit_code = 126
        state = "failed"
        error_code = "target_launch_failed"

    atomic_write_json(
        status_path,
        status_payload(
            request_id,
            state,
            created_at,
            exit_code=exit_code,
            error_code=error_code,
        ),
    )
    release_state_lock(lock_dir, request_id)
    print(f"\nHandoff result: {state} (exit code {exit_code})")
    if bool(request.get("hold_open", True)):
        try:
            input("Press Enter to close this window...")
        except EOFError:
            pass
    return exit_code


def launch(args: argparse.Namespace) -> int:
    if os.name != "nt":
        raise UserFacingError(
            "detached visible-console launch is currently supported only on Windows"
        )
    if not args.acknowledge_nonsecret_command:
        raise UserFacingError("--acknowledge-nonsecret-command is required")

    command = normalize_command(args.command)
    command = prepare_pinned_command(
        command,
        executable_sha256=args.executable_sha256,
        op_target_sha256=args.op_target_sha256,
    )
    env_references = parse_env_references(args.env_reference)
    state_root = Path(args.state_dir).expanduser().resolve()
    state_root.mkdir(parents=True, exist_ok=True)
    request_id = uuid.uuid4().hex
    lock_dir = acquire_state_lock(state_root, request_id)
    request_dir = state_root / f"credential-handoff-{request_id}"
    try:
        request_dir.mkdir(mode=0o700)
    except OSError:
        release_state_lock(lock_dir, request_id)
        raise
    request_path = request_dir / "request.json"
    status_path = request_dir / "status.json"
    created_at = utc_now()
    cwd = str(Path(args.cwd).expanduser().resolve()) if args.cwd else None
    request = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "created_at_utc": created_at,
        "title": args.title,
        "purpose": args.purpose,
        "expected_input": args.expected_input,
        "cwd": cwd,
        "hold_open": not args.no_hold_open,
        "env_references": env_references,
        "executable_sha256": args.executable_sha256.lower(),
        "op_target_sha256": (
            args.op_target_sha256.lower()
            if args.op_target_sha256 is not None
            else None
        ),
        "command": command,
    }
    atomic_write_json(request_path, request)
    atomic_write_json(status_path, status_payload(request_id, "launched", created_at))

    worker_command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_worker",
        "--request",
        str(request_path),
    ]
    creation_flags = subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        process = subprocess.Popen(
            worker_command,
            close_fds=True,
            creationflags=creation_flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        atomic_write_json(
            status_path,
            status_payload(
                request_id,
                "failed",
                created_at,
                error_code="console_launch_failed",
            ),
        )
        release_state_lock(lock_dir, request_id)
        raise UserFacingError("could not launch the visible credential console") from error

    print(
        json.dumps(
            {
                "schema": "agent_harness.credential_handoff_launch.v1",
                "request_id": request_id,
                "status_path": str(status_path),
                "process_id": process.pid,
                "captured_streams": False,
            },
            indent=2,
        )
    )
    return 0


def show_status(status_path: Path) -> int:
    _, payload = read_owned_status(status_path)
    print(json.dumps(payload, indent=2))
    return 0


def cleanup(status_path: Path) -> int:
    resolved, payload = read_owned_status(status_path)
    if payload.get("state") not in TERMINAL_STATES:
        raise UserFacingError("handoff cleanup requires a terminal status")
    request_dir = resolved.parent
    lock_dir = request_dir.parent / LOCK_DIR_NAME
    if lock_dir.exists():
        owner = read_lock_owner(lock_dir)
        if owner["request_id"] == payload["request_id"]:
            raise UserFacingError("handoff cleanup refused while its worker owns the lock")
    entries = {path.name for path in request_dir.iterdir()}
    if not entries.issubset({"request.json", "status.json"}):
        raise UserFacingError("handoff directory contains unexpected files")
    for name in ("request.json", "status.json"):
        candidate = request_dir / name
        if candidate.exists():
            candidate.unlink()
    request_dir.rmdir()
    print(
        json.dumps(
            {
                "schema": "agent_harness.credential_handoff_cleanup.v1",
                "request_id": payload.get("request_id"),
                "removed": True,
            },
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    launch_parser = subparsers.add_parser(
        "launch", help="launch a non-secret command in a visible Windows console"
    )
    launch_parser.add_argument("--state-dir", required=True)
    launch_parser.add_argument("--title", default="Agent credential handoff")
    launch_parser.add_argument("--purpose", required=True)
    launch_parser.add_argument("--expected-input", required=True)
    launch_parser.add_argument("--cwd")
    launch_parser.add_argument(
        "--executable-sha256",
        required=True,
        help="pin the absolute target executable to this SHA-256 digest",
    )
    launch_parser.add_argument(
        "--op-target-sha256",
        help="pin the absolute subprocess after op run -- to this SHA-256 digest",
    )
    launch_parser.add_argument("--no-hold-open", action="store_true")
    launch_parser.add_argument(
        "--env-reference",
        action="append",
        default=[],
        metavar="NAME=op://vault/item/field",
        help="pass a 1Password reference to op run without shell interpolation",
    )
    launch_parser.add_argument(
        "--acknowledge-nonsecret-command",
        action="store_true",
        help="assert that the command and arguments contain no resolved secret",
    )
    launch_parser.add_argument("command", nargs=argparse.REMAINDER)

    status_parser = subparsers.add_parser("status", help="print an allowlisted status")
    status_parser.add_argument("status_path")

    cleanup_parser = subparsers.add_parser(
        "cleanup", help="remove one completed owned request directory"
    )
    cleanup_parser.add_argument("status_path")

    worker_parser = subparsers.add_parser("_worker", help=argparse.SUPPRESS)
    worker_parser.add_argument("--request", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "launch":
            return launch(args)
        if args.mode == "status":
            return show_status(Path(args.status_path))
        if args.mode == "cleanup":
            return cleanup(Path(args.status_path))
        if args.mode == "_worker":
            return run_worker(Path(args.request).expanduser().resolve())
    except UserFacingError as error:
        print(str(error), file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled mode: {args.mode}")


if __name__ == "__main__":
    raise SystemExit(main())
