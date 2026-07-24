#!/usr/bin/env python3
"""MCP server for one-shot waits on producer-owned native completion receipts."""

from __future__ import annotations

import errno
import json
import math
import os
import re
import select
import signal
import stat
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "lib"))

from native_completion_contract import (  # noqa: E402
    MAX_RECEIPT_BYTES,
    NativeCompletionContractError,
    parse_json_pointer,
    parse_receipt_bytes,
    validate_bounded_json_value,
)


SERVER_NAME = "Codex Deferred Completion"
SERVER_VERSION = json.loads(
    (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
)["version"]
SUPPORTED_PROTOCOL_VERSION = "2025-06-18"
RESERVE_TOOL = "reserve_completion_receipt"
AWAIT_TOOL = "await_completion_receipt"
MAX_PENDING_RESERVATIONS = 64
MAX_TERMINAL_CACHE = 64
MAX_ACTIVE_WAITS = 8
MAX_WORKER_THREADS = 16
MAX_FRAME_BYTES = 262_144
MAX_TOTAL_WAIT_SECONDS = 21_600
RESERVATION_RETENTION_SECONDS = 3600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_PARSE_ERROR = -32700
JSONRPC_REQUEST_CANCELLED = -32800
SAFE_OPEN_SUPPORTED = (
    hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and os.open in getattr(os, "supports_dir_fd", set())
    and os.stat in getattr(os, "supports_dir_fd", set())
    and os.stat in getattr(os, "supports_follow_symlinks", set())
    and os.unlink in getattr(os, "supports_dir_fd", set())
    and os.listdir in getattr(os, "supports_fd", set())
)
SCHEMA_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
OUTCOME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class ToolInputError(ValueError):
    """Invalid MCP tool input or unsafe receipt state."""


class WaitCancelled(RuntimeError):
    """The MCP client cancelled only the receipt wait."""


class ShutdownRequested(RuntimeError):
    """The MCP host requested graceful server shutdown."""


class RuntimeDirectory:
    def __init__(self) -> None:
        self.path: Path | None = None
        self.descriptor: int | None = None
        self.identity: tuple[int, int] | None = None
        self._lock = threading.Lock()

    def ensure(self) -> None:
        with self._lock:
            if self.descriptor is not None:
                self._assert_identity_unlocked()
                return
            if not SAFE_OPEN_SUPPORTED:
                raise ToolInputError(
                    "deferred completion requires POSIX safe-open support on this host"
                )
            path = Path(tempfile.mkdtemp(prefix="codex-deferred-completion-"))
            os.chmod(path, 0o700)
            flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
            descriptor = os.open(path, flags)
            details = os.fstat(descriptor)
            if not stat.S_ISDIR(details.st_mode):
                os.close(descriptor)
                raise ToolInputError(
                    "unable to create a safe completion runtime directory"
                )
            if hasattr(os, "getuid") and details.st_uid != os.getuid():
                os.close(descriptor)
                raise ToolInputError("completion runtime directory has the wrong owner")
            if details.st_mode & 0o077:
                os.close(descriptor)
                raise ToolInputError(
                    "completion runtime directory permissions are too broad"
                )
            self.path = path
            self.descriptor = descriptor
            self.identity = (details.st_dev, details.st_ino)

    def _assert_identity_unlocked(self) -> None:
        if self.path is None or self.descriptor is None or self.identity is None:
            raise ToolInputError("completion runtime directory is unavailable")
        opened = os.fstat(self.descriptor)
        try:
            current = os.stat(self.path, follow_symlinks=False)
        except OSError as exc:
            raise ToolInputError(
                "completion runtime directory disappeared during the wait"
            ) from exc
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or (opened.st_dev, opened.st_ino) != self.identity
            or (current.st_dev, current.st_ino) != self.identity
        ):
            raise ToolInputError("completion runtime directory changed identity")
        if hasattr(os, "getuid") and (
            opened.st_uid != os.getuid() or current.st_uid != os.getuid()
        ):
            raise ToolInputError("completion runtime directory has the wrong owner")
        if opened.st_mode & 0o077 or current.st_mode & 0o077:
            raise ToolInputError(
                "completion runtime directory permissions are too broad"
            )

    def assert_identity(self) -> None:
        with self._lock:
            self._assert_identity_unlocked()

    def result_path(self, filename: str) -> str:
        self.ensure()
        with self._lock:
            self._assert_identity_unlocked()
            assert self.path is not None
            return str(self.path / filename)

    def remove_file(self, filename: str) -> bool:
        with self._lock:
            self._assert_identity_unlocked()
            assert self.descriptor is not None
            try:
                os.unlink(filename, dir_fd=self.descriptor)
            except FileNotFoundError:
                return True
            except OSError:
                return False
            return True

    def close(self) -> None:
        with self._lock:
            if self.descriptor is None:
                return
            path = self.path
            self._assert_identity_unlocked()
            closing_path = path.with_name(f".{path.name}.closing-{uuid.uuid4().hex}")
            try:
                os.rename(path, closing_path)
            except OSError:
                closing_path = path
            try:
                names = os.listdir(self.descriptor)
            except OSError:
                names = []
            for name in names:
                try:
                    os.unlink(name, dir_fd=self.descriptor)
                except OSError:
                    pass
            try:
                os.rmdir(closing_path)
            except OSError:
                pass
            try:
                os.close(self.descriptor)
            except OSError:
                pass
            self.descriptor = None
            self.identity = None
            self.path = None


@dataclass
class Reservation:
    handle: str
    result_filename: str
    result_path: str
    expectation: dict[str, Any]
    created_monotonic: float
    launch_deadline_monotonic: float
    expires_monotonic: float
    expires_at: str
    producer_deadline_monotonic: float | None = None
    active: bool = False
    terminal_result: dict[str, Any] | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


class ReservationStore:
    def __init__(self) -> None:
        self._reservations: dict[str, Reservation] = {}
        self._lock = threading.Lock()
        self._active_waits = 0

    def _cleanup_locked(self, now: float) -> None:
        stale_handles = {
            reservation.handle
            for reservation in self._reservations.values()
            if not reservation.active and reservation.expires_monotonic <= now
        }
        terminal = sorted(
            (
                reservation
                for reservation in self._reservations.values()
                if not reservation.active
                and reservation.terminal_result is not None
                and reservation.handle not in stale_handles
            ),
            key=lambda reservation: reservation.created_monotonic,
        )
        stale_handles.update(
            reservation.handle for reservation in terminal[:-MAX_TERMINAL_CACHE]
        )
        stale = [
            reservation
            for reservation in self._reservations.values()
            if reservation.handle in stale_handles
        ]
        for reservation in stale:
            self._reservations.pop(reservation.handle, None)
            RUNTIME.remove_file(reservation.result_filename)

    def reserve(self, arguments: dict[str, Any]) -> Reservation:
        expectation = normalize_expectation(arguments)
        RUNTIME.ensure()
        now = time.monotonic()
        handle = str(uuid.uuid4())
        result_filename = f"native-completion-{handle}.json"
        result_path = RUNTIME.result_path(result_filename)
        expectation["resultPath"] = result_path
        total_wait = (
            expectation["launchGraceSeconds"]
            + expectation["producerTimeoutSeconds"]
            + expectation["completionGraceSeconds"]
        )
        expires_at = (
            (
                datetime.now(timezone.utc)
                + timedelta(seconds=total_wait + RESERVATION_RETENTION_SECONDS)
            )
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        reservation = Reservation(
            handle=handle,
            result_filename=result_filename,
            result_path=result_path,
            expectation=expectation,
            created_monotonic=now,
            launch_deadline_monotonic=now + expectation["launchGraceSeconds"],
            expires_monotonic=now + total_wait + RESERVATION_RETENTION_SECONDS,
            expires_at=expires_at,
        )
        with self._lock:
            self._cleanup_locked(now)
            pending = sum(
                reservation.terminal_result is None
                for reservation in self._reservations.values()
            )
            if pending >= MAX_PENDING_RESERVATIONS:
                raise ToolInputError("completion reservation quota is exhausted")
            self._reservations[handle] = reservation
        return reservation

    def acquire_wait(self, handle: Any) -> Reservation:
        normalized = validate_handle(handle)
        now = time.monotonic()
        with self._lock:
            self._cleanup_locked(now)
            reservation = self._reservations.get(normalized)
            if reservation is None:
                raise ToolInputError("completion handle is unknown or expired")
            with reservation.lock:
                if reservation.terminal_result is not None:
                    return reservation
                if reservation.active:
                    raise ToolInputError("a wait is already active for this handle")
                if self._active_waits >= MAX_ACTIVE_WAITS:
                    raise ToolInputError("active completion wait quota is exhausted")
                reservation.active = True
                self._active_waits += 1
            return reservation

    def finish_wait(
        self, reservation: Reservation, terminal_result: dict[str, Any] | None
    ) -> None:
        with self._lock:
            with reservation.lock:
                if terminal_result is not None:
                    try:
                        removed = RUNTIME.remove_file(reservation.result_filename)
                    except ToolInputError:
                        removed = False
                    terminal_result["receiptRetained"] = not removed
                    reservation.terminal_result = terminal_result
                if reservation.active:
                    reservation.active = False
                    self._active_waits -= 1
            self._cleanup_locked(time.monotonic())

    def close(self) -> None:
        with self._lock:
            reservations = list(self._reservations.values())
            self._reservations.clear()
            self._active_waits = 0
        for reservation in reservations:
            try:
                RUNTIME.remove_file(reservation.result_filename)
            except ToolInputError:
                pass


RUNTIME = RuntimeDirectory()
STORE = ReservationStore()
OUTPUT_LOCK = threading.Lock()
CANCELLATIONS: dict[str, threading.Event] = {}
CANCELLATIONS_LOCK = threading.Lock()
WORKER_THREADS: set[threading.Thread] = set()
WORKER_THREADS_LOCK = threading.Lock()
WORKER_SLOTS = threading.BoundedSemaphore(MAX_WORKER_THREADS)


def request_key(request_id: Any) -> str:
    return json.dumps(request_id, sort_keys=True, separators=(",", ":"))


def valid_request_id(request_id: Any) -> bool:
    if request_id is None:
        return True
    if isinstance(request_id, bool):
        return False
    if isinstance(request_id, str):
        return len(request_id) <= 200
    if isinstance(request_id, int):
        return True
    return isinstance(request_id, float) and math.isfinite(request_id)


def send(message: dict[str, Any]) -> None:
    encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
    with OUTPUT_LOCK:
        sys.stdout.write(encoded + "\n")
        sys.stdout.flush()


def send_result(request_id: Any, result: dict[str, Any]) -> None:
    send({"jsonrpc": "2.0", "id": request_id, "result": result})


def send_error(request_id: Any, code: int, message: str) -> None:
    send(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message[:500]},
        }
    )


def tool_result(structured: dict[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(
        structured, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return {
        "content": [{"type": "text", "text": serialized}],
        "structuredContent": structured,
    }


def require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolInputError(f"{name} must be an object")
    return value


def strip_reserved_meta(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.pop("_meta", None)
    return normalized


def reject_unknown_fields(payload: dict[str, Any], allowed: set[str]) -> None:
    if set(payload) - allowed:
        raise ToolInputError("tool arguments contain unsupported fields")


def validate_handle(value: Any) -> str:
    if not isinstance(value, str):
        raise ToolInputError("handle must be a lowercase UUIDv4 string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ToolInputError("handle must be a lowercase UUIDv4 string") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ToolInputError("handle must be a lowercase UUIDv4 string")
    return value


def validate_bounded_string(value: Any, label: str, *, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ToolInputError(f"{label} must be a bounded non-empty string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ToolInputError(f"{label} must not contain control characters")
    return value


def validate_number(value: Any, label: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolInputError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not (minimum <= number <= maximum):
        raise ToolInputError(f"{label} is outside the supported range")
    return number


def normalize_terminal_outcomes(value: Any) -> dict[str, int]:
    payload = strip_reserved_meta(require_object(value, "terminalOutcomes"))
    if not payload or len(payload) > 16:
        raise ToolInputError("terminalOutcomes must contain 1 to 16 outcomes")
    normalized: dict[str, int] = {}
    for outcome, exit_code in payload.items():
        if not OUTCOME_PATTERN.fullmatch(outcome) or outcome == "running":
            raise ToolInputError("terminalOutcomes contains an invalid outcome")
        if (
            isinstance(exit_code, bool)
            or not isinstance(exit_code, int)
            or not (0 <= exit_code <= 255)
        ):
            raise ToolInputError(
                "terminalOutcomes exit codes must be integers 0 to 255"
            )
        normalized[outcome] = exit_code
    return normalized


def normalize_assertions(
    value: Any, terminal_outcomes: dict[str, int]
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 32:
        raise ToolInputError("assertions must be a bounded array")
    normalized: list[dict[str, Any]] = []
    known_outcomes = {"running", *terminal_outcomes}
    for item in value:
        payload = strip_reserved_meta(require_object(item, "assertion"))
        reject_unknown_fields(payload, {"pointer", "value", "outcomes"})
        if "pointer" not in payload or "value" not in payload:
            raise ToolInputError("each assertion requires pointer and value")
        pointer = parse_json_pointer(payload["pointer"])
        assertion_outcomes = payload.get("outcomes")
        if assertion_outcomes is not None:
            if (
                not isinstance(assertion_outcomes, list)
                or not assertion_outcomes
                or len(assertion_outcomes) > len(known_outcomes)
                or any(
                    not isinstance(outcome, str) or outcome not in known_outcomes
                    for outcome in assertion_outcomes
                )
                or len(set(assertion_outcomes)) != len(assertion_outcomes)
            ):
                raise ToolInputError(
                    "assertion outcomes must be unique reserved outcomes"
                )
            outcomes: frozenset[str] | None = frozenset(assertion_outcomes)
        else:
            outcomes = None
        normalized.append(
            {
                "pointer": pointer,
                "value": validate_bounded_json_value(payload["value"]),
                "outcomes": outcomes,
            }
        )
    return normalized


def normalize_expectation(arguments: dict[str, Any]) -> dict[str, Any]:
    payload = strip_reserved_meta(arguments)
    allowed = {
        "label",
        "schema",
        "terminalOutcomes",
        "resultPathPointer",
        "assertions",
        "producerTimeoutSeconds",
        "launchGraceSeconds",
        "completionGraceSeconds",
    }
    reject_unknown_fields(payload, allowed)
    required = {"schema", "terminalOutcomes", "resultPathPointer"}
    if not required.issubset(payload):
        raise ToolInputError(
            "schema, terminalOutcomes, and resultPathPointer are required"
        )

    label = validate_bounded_string(
        payload.get("label", "native completion"), "label", maximum=200
    )
    schema = validate_bounded_string(payload["schema"], "schema", maximum=200)
    if not SCHEMA_PATTERN.fullmatch(schema):
        raise ToolInputError("schema contains unsupported characters")
    terminal_outcomes = normalize_terminal_outcomes(payload["terminalOutcomes"])
    result_path_pointer = parse_json_pointer(payload["resultPathPointer"])
    producer_timeout = validate_number(
        payload.get("producerTimeoutSeconds", 7200),
        "producerTimeoutSeconds",
        minimum=60,
        maximum=20_880,
    )
    launch_grace = validate_number(
        payload.get("launchGraceSeconds", 120),
        "launchGraceSeconds",
        minimum=30,
        maximum=600,
    )
    completion_grace = validate_number(
        payload.get("completionGraceSeconds", 300),
        "completionGraceSeconds",
        minimum=60,
        maximum=1800,
    )
    if producer_timeout + launch_grace + completion_grace > MAX_TOTAL_WAIT_SECONDS:
        raise ToolInputError("combined completion deadline exceeds the server limit")
    return {
        "label": label,
        "schema": schema,
        "terminalOutcomes": terminal_outcomes,
        "resultPathPointer": result_path_pointer,
        "assertions": normalize_assertions(
            payload.get("assertions"), terminal_outcomes
        ),
        "producerTimeoutSeconds": producer_timeout,
        "launchGraceSeconds": launch_grace,
        "completionGraceSeconds": completion_grace,
    }


def validate_receipt_stat(
    details: os.stat_result, *, allow_unlinked: bool = False
) -> None:
    if not stat.S_ISREG(details.st_mode):
        raise ToolInputError("completion receipt must be a regular file")
    if hasattr(os, "getuid") and details.st_uid != os.getuid():
        raise ToolInputError("completion receipt has the wrong owner")
    if details.st_nlink != 1 and not (allow_unlinked and details.st_nlink == 0):
        raise ToolInputError("completion receipt must not be hard-linked")
    if stat.S_IMODE(details.st_mode) != 0o600:
        raise ToolInputError("completion receipt permissions must be 0600")
    if details.st_size > MAX_RECEIPT_BYTES:
        raise ToolInputError("completion receipt exceeds the fixed size limit")


def receipt_stat_identity(details: os.stat_result) -> tuple[int, ...]:
    return (
        details.st_dev,
        details.st_ino,
        details.st_size,
        details.st_mtime_ns,
        details.st_ctime_ns,
        details.st_mode,
        details.st_nlink,
        details.st_uid,
    )


def read_receipt(reservation: Reservation) -> dict[str, Any] | None:
    RUNTIME.assert_identity()
    assert RUNTIME.descriptor is not None
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(
            reservation.result_filename, flags, dir_fd=RUNTIME.descriptor
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ToolInputError("completion receipt must not be a symlink") from exc
        raise ToolInputError("unable to open the completion receipt safely") from exc
    try:
        before = os.fstat(descriptor)
        validate_receipt_stat(before)
        chunks: list[bytes] = []
        remaining = MAX_RECEIPT_BYTES + 1
        while remaining > 0:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > MAX_RECEIPT_BYTES:
            raise ToolInputError("completion receipt exceeds the fixed size limit")
        after = os.fstat(descriptor)
        validate_receipt_stat(after, allow_unlinked=True)
        identity_before = receipt_stat_identity(before)
        identity_after = receipt_stat_identity(after)
        RUNTIME.assert_identity()
        assert RUNTIME.descriptor is not None
        try:
            entry = os.stat(
                reservation.result_filename,
                dir_fd=RUNTIME.descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ToolInputError("unable to revalidate the completion receipt") from exc
        if (entry.st_dev, entry.st_ino) != (after.st_dev, after.st_ino):
            return None
        validate_receipt_stat(after)
        validate_receipt_stat(entry)
        if identity_before != identity_after or len(raw) != after.st_size:
            raise ToolInputError("completion receipt changed while it was read")
        if receipt_stat_identity(entry) != identity_after:
            raise ToolInputError("completion receipt changed after it was read")
    finally:
        os.close(descriptor)
    try:
        return parse_receipt_bytes(raw, reservation.expectation)
    except NativeCompletionContractError as exc:
        raise ToolInputError(str(exc)) from exc


class DirectoryWatcher:
    def __init__(self, descriptor: int) -> None:
        self._kqueue: Any = None
        if hasattr(select, "kqueue") and hasattr(select, "kevent"):
            try:
                kqueue = select.kqueue()
                flags = select.KQ_EV_ADD | select.KQ_EV_CLEAR
                fflags = (
                    select.KQ_NOTE_WRITE
                    | select.KQ_NOTE_EXTEND
                    | select.KQ_NOTE_ATTRIB
                    | select.KQ_NOTE_RENAME
                    | select.KQ_NOTE_DELETE
                )
                event = select.kevent(
                    descriptor,
                    filter=select.KQ_FILTER_VNODE,
                    flags=flags,
                    fflags=fflags,
                )
                kqueue.control([event], 0, 0)
                self._kqueue = kqueue
            except (OSError, ValueError):
                if self._kqueue is not None:
                    self._kqueue.close()
                self._kqueue = None

    def wait(self, timeout: float, cancellation: threading.Event) -> None:
        remaining = max(0.0, timeout)
        while remaining > 0:
            if cancellation.is_set():
                raise WaitCancelled()
            slice_seconds = min(0.5, remaining)
            started = time.monotonic()
            if self._kqueue is not None:
                try:
                    events = self._kqueue.control(None, 1, slice_seconds)
                except OSError:
                    events = []
                if events:
                    return
            elif cancellation.wait(slice_seconds):
                raise WaitCancelled()
            remaining -= max(time.monotonic() - started, 0.001)

    def close(self) -> None:
        if self._kqueue is not None:
            self._kqueue.close()
            self._kqueue = None


def project_terminal(
    reservation: Reservation, receipt: dict[str, Any]
) -> dict[str, Any]:
    return {
        "status": "terminal",
        "handle": reservation.handle,
        "label": reservation.expectation["label"],
        "schema": reservation.expectation["schema"],
        "outcome": receipt["outcome"],
        "exitCode": receipt["exitCode"],
        "completedAt": receipt["completedAt"],
        "elapsedSeconds": receipt["elapsedSeconds"],
        "transitionCount": receipt["transitionCount"],
    }


def wait_timeout_result(
    reservation: Reservation, started: float, stage: str
) -> dict[str, Any]:
    return {
        "status": "wait_timeout",
        "handle": reservation.handle,
        "label": reservation.expectation["label"],
        "schema": reservation.expectation["schema"],
        "stage": stage,
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "resultPath": reservation.result_path,
    }


def await_receipt(
    reservation: Reservation, cancellation: threading.Event
) -> dict[str, Any]:
    if reservation.terminal_result is not None:
        return reservation.terminal_result
    RUNTIME.ensure()
    assert RUNTIME.descriptor is not None
    watcher = DirectoryWatcher(RUNTIME.descriptor)
    started = time.monotonic()
    try:
        while True:
            if cancellation.is_set():
                raise WaitCancelled()
            now = time.monotonic()
            if (
                reservation.producer_deadline_monotonic is None
                and now >= reservation.launch_deadline_monotonic
            ):
                return wait_timeout_result(reservation, started, "launch")
            receipt = read_receipt(reservation)
            now = time.monotonic()
            if (
                reservation.producer_deadline_monotonic is None
                and now >= reservation.launch_deadline_monotonic
            ):
                return wait_timeout_result(reservation, started, "launch")
            if receipt is not None:
                if receipt["outcome"] != "running":
                    return project_terminal(reservation, receipt)
                if reservation.producer_deadline_monotonic is None:
                    reservation.producer_deadline_monotonic = now + (
                        reservation.expectation["producerTimeoutSeconds"]
                        + reservation.expectation["completionGraceSeconds"]
                    )

            if reservation.producer_deadline_monotonic is None:
                deadline = reservation.launch_deadline_monotonic
                stage = "launch"
            else:
                deadline = reservation.producer_deadline_monotonic
                stage = "producer"
            remaining = deadline - now
            if remaining <= 0:
                if stage == "producer":
                    receipt = read_receipt(reservation)
                    if receipt is not None and receipt["outcome"] != "running":
                        return project_terminal(reservation, receipt)
                return wait_timeout_result(reservation, started, stage)
            watcher.wait(min(remaining, 1.0), cancellation)
    finally:
        watcher.close()


def reserve_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    reservation = STORE.reserve(arguments)
    structured = {
        "status": "reserved",
        "handle": reservation.handle,
        "label": reservation.expectation["label"],
        "schema": reservation.expectation["schema"],
        "resultPath": reservation.result_path,
        "producerTimeoutSeconds": reservation.expectation["producerTimeoutSeconds"],
        "launchGraceSeconds": reservation.expectation["launchGraceSeconds"],
        "completionGraceSeconds": reservation.expectation["completionGraceSeconds"],
        "expiresAt": reservation.expires_at,
    }
    return tool_result(structured)


def await_tool(
    arguments: dict[str, Any], cancellation: threading.Event
) -> dict[str, Any]:
    payload = strip_reserved_meta(arguments)
    reject_unknown_fields(payload, {"handle"})
    if "handle" not in payload:
        raise ToolInputError("handle is required")
    reservation = STORE.acquire_wait(payload["handle"])
    if reservation.terminal_result is not None:
        result = reservation.terminal_result
        return tool_result(result)
    terminal_result: dict[str, Any] | None = None
    try:
        result = await_receipt(reservation, cancellation)
        if result["status"] == "terminal":
            terminal_result = result
    finally:
        STORE.finish_wait(reservation, terminal_result)
    return tool_result(result)


def reserve_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "label": {"type": "string", "minLength": 1, "maxLength": 200},
            "schema": {
                "type": "string",
                "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$",
            },
            "terminalOutcomes": {
                "type": "object",
                "minProperties": 1,
                "maxProperties": 16,
                "additionalProperties": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 255,
                },
            },
            "resultPathPointer": {
                "type": "string",
                "pattern": "^/",
                "maxLength": 300,
            },
            "assertions": {
                "type": "array",
                "maxItems": 32,
                "items": {
                    "type": "object",
                    "properties": {
                        "pointer": {
                            "type": "string",
                            "pattern": "^/",
                            "maxLength": 300,
                        },
                        "value": {},
                        "outcomes": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 17,
                            "uniqueItems": True,
                            "items": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 64,
                            },
                        },
                    },
                    "required": ["pointer", "value"],
                    "additionalProperties": False,
                },
                "default": [],
            },
            "producerTimeoutSeconds": {
                "type": "number",
                "minimum": 60,
                "maximum": 20_880,
                "default": 7200,
            },
            "launchGraceSeconds": {
                "type": "number",
                "minimum": 30,
                "maximum": 600,
                "default": 120,
            },
            "completionGraceSeconds": {
                "type": "number",
                "minimum": 60,
                "maximum": 1800,
                "default": 300,
            },
        },
        "required": ["schema", "terminalOutcomes", "resultPathPointer"],
        "additionalProperties": False,
    }


def tools_list() -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": RESERVE_TOOL,
                "title": "Reserve Native Completion Receipt",
                "description": (
                    "Reserve a private result path for one directly launched native producer. "
                    "The producer must atomically publish a bounded JSON completion envelope. "
                    "This tool never launches a command."
                ),
                "inputSchema": reserve_input_schema(),
                "annotations": {
                    "readOnlyHint": False,
                    "destructiveHint": False,
                    "idempotentHint": False,
                    "openWorldHint": False,
                },
            },
            {
                "name": AWAIT_TOOL,
                "title": "Await Native Completion Receipt",
                "description": (
                    "Wait once for a schema-, path-, and identity-validated terminal receipt. "
                    "This tool never executes, signals, or kills the producer."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "handle": {
                            "type": "string",
                            "pattern": "^[0-9a-f-]{36}$",
                        }
                    },
                    "required": ["handle"],
                    "additionalProperties": False,
                },
                "annotations": {
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            },
        ]
    }


def process_tool_call(
    request_id: Any, params: Any, cancellation: threading.Event
) -> None:
    try:
        request = strip_reserved_meta(require_object(params, "tools/call params"))
        reject_unknown_fields(request, {"name", "arguments"})
        name = request.get("name")
        arguments = require_object(request.get("arguments", {}), "arguments")
        if name == RESERVE_TOOL:
            result = reserve_tool(arguments)
        elif name == AWAIT_TOOL:
            result = await_tool(arguments, cancellation)
        else:
            raise ToolInputError("unknown deferred-completion tool")
        send_result(request_id, result)
    except WaitCancelled:
        send_error(request_id, JSONRPC_REQUEST_CANCELLED, "completion wait cancelled")
    except (ToolInputError, NativeCompletionContractError) as exc:
        send_error(request_id, JSONRPC_INVALID_PARAMS, str(exc))
    except Exception:
        send_error(
            request_id, JSONRPC_INTERNAL_ERROR, "internal completion server error"
        )
    finally:
        key = request_key(request_id)
        with CANCELLATIONS_LOCK:
            if CANCELLATIONS.get(key) is cancellation:
                CANCELLATIONS.pop(key, None)
        current = threading.current_thread()
        with WORKER_THREADS_LOCK:
            WORKER_THREADS.discard(current)
        WORKER_SLOTS.release()


def handle_message(message: dict[str, Any]) -> None:
    has_request_id = "id" in message
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params")

    if message.get("jsonrpc") != "2.0":
        if has_request_id:
            send_error(None, JSONRPC_INVALID_REQUEST, "invalid JSON-RPC version")
        return
    if has_request_id and not valid_request_id(request_id):
        send_error(None, JSONRPC_INVALID_REQUEST, "invalid JSON-RPC request id")
        return

    if method == "notifications/cancelled":
        if not isinstance(params, dict) or "requestId" not in params:
            return
        cancelled_id = params["requestId"]
        if not valid_request_id(cancelled_id):
            return
        key = request_key(cancelled_id)
        with CANCELLATIONS_LOCK:
            event = CANCELLATIONS.get(key)
        if event is not None:
            event.set()
        return
    if not has_request_id:
        return
    if method == "initialize":
        send_result(
            request_id,
            {
                "protocolVersion": SUPPORTED_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Reserve a native receipt, start the producer directly through native "
                    "Codex exec with its result flag, then await the handle once. This server "
                    "never launches commands."
                ),
            },
        )
        return
    if method == "ping":
        send_result(request_id, {})
        return
    if method == "tools/list":
        send_result(request_id, tools_list())
        return
    if method == "tools/call":
        if not WORKER_SLOTS.acquire(blocking=False):
            send_error(
                request_id,
                JSONRPC_INTERNAL_ERROR,
                "completion server worker capacity is exhausted",
            )
            return
        cancellation = threading.Event()
        key = request_key(request_id)
        with CANCELLATIONS_LOCK:
            duplicate_request_id = key in CANCELLATIONS
            if not duplicate_request_id:
                CANCELLATIONS[key] = cancellation
        if duplicate_request_id:
            WORKER_SLOTS.release()
            send_error(request_id, JSONRPC_INVALID_PARAMS, "request id is already active")
            return
        thread = threading.Thread(
            target=process_tool_call,
            args=(request_id, params, cancellation),
            daemon=True,
        )
        with WORKER_THREADS_LOCK:
            WORKER_THREADS.add(thread)
        try:
            thread.start()
        except Exception:
            with WORKER_THREADS_LOCK:
                WORKER_THREADS.discard(thread)
            with CANCELLATIONS_LOCK:
                if CANCELLATIONS.get(key) is cancellation:
                    CANCELLATIONS.pop(key, None)
            WORKER_SLOTS.release()
            send_error(request_id, JSONRPC_INTERNAL_ERROR, "unable to start tool worker")
        return
    if has_request_id:
        send_error(request_id, JSONRPC_METHOD_NOT_FOUND, "method not found")


def reject_input_constant(value: str) -> None:
    raise ValueError(f"non-JSON constant {value}")


def reject_input_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON-RPC object field")
        result[key] = value
    return result


def request_shutdown(_signum: int, _frame: Any) -> None:
    raise ShutdownRequested()


def bounded_input_frames() -> Iterator[bytes | None]:
    stream = sys.stdin.buffer
    while True:
        raw = stream.readline(MAX_FRAME_BYTES + 1)
        if not raw:
            return
        if len(raw) > MAX_FRAME_BYTES:
            while raw and not raw.endswith(b"\n"):
                raw = stream.readline(MAX_FRAME_BYTES + 1)
            yield None
            continue
        yield raw


def main() -> int:
    handled_signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGHUP"):
        handled_signals.append(signal.SIGHUP)
    for handled_signal in handled_signals:
        signal.signal(handled_signal, request_shutdown)
    try:
        for raw in bounded_input_frames():
            if raw is None:
                send_error(None, JSONRPC_PARSE_ERROR, "JSON-RPC frame exceeds size limit")
                continue
            if not raw.strip():
                continue
            try:
                message = json.loads(
                    raw,
                    object_pairs_hook=reject_input_duplicate_pairs,
                    parse_constant=reject_input_constant,
                )
            except (ValueError, RecursionError, UnicodeDecodeError):
                send_error(None, JSONRPC_PARSE_ERROR, "invalid JSON-RPC JSON frame")
                continue
            if not isinstance(message, dict):
                send_error(None, JSONRPC_INVALID_REQUEST, "JSON-RPC message must be an object")
                continue
            handle_message(message)
    except ShutdownRequested:
        pass
    finally:
        for handled_signal in handled_signals:
            signal.signal(handled_signal, signal.SIG_IGN)
        with CANCELLATIONS_LOCK:
            events = list(CANCELLATIONS.values())
        for event in events:
            event.set()
        with WORKER_THREADS_LOCK:
            workers = list(WORKER_THREADS)
        join_deadline = time.monotonic() + 2
        for worker in workers:
            worker.join(timeout=max(0.0, join_deadline - time.monotonic()))
        STORE.close()
        RUNTIME.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
