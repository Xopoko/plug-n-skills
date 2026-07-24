from __future__ import annotations

import importlib.util
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SERVER = PLUGIN_ROOT / "mcp" / "server.py"
RESERVE_TOOL = "reserve_completion_receipt"
AWAIT_TOOL = "await_completion_receipt"
RECEIPT_SCHEMA = "example.release-watch-result.v1"
EXPECTED_SHA = "a" * 40
TERMINAL_OUTCOMES = {"ready": 0, "failed": 2, "timeout": 3, "error": 2}
RESERVE_ARGUMENTS: dict[str, Any] = {
    "label": f"release-watch group/mobile-app!42 @{EXPECTED_SHA}",
    "schema": RECEIPT_SCHEMA,
    "terminalOutcomes": TERMINAL_OUTCOMES,
    "resultPathPointer": "/request/artifacts/result",
    "assertions": [
        {"pointer": "/request/mr", "value": 42},
        {"pointer": "/request/project", "value": "group/mobile-app"},
        {"pointer": "/request/requiredJobs", "value": ["integration"]},
        {
            "pointer": "/lastReport/gitlab/mr/sha",
            "value": EXPECTED_SHA,
            "outcomes": ["ready", "failed"],
        },
    ],
    "producerTimeoutSeconds": 60,
    "launchGraceSeconds": 30,
    "completionGraceSeconds": 60,
}


class McpHarness:
    def __init__(self) -> None:
        self.closed = False
        self.process = subprocess.Popen(
            [sys.executable, str(SERVER)],
            cwd=tempfile.gettempdir(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.invalid_stdout: queue.Queue[str] = queue.Queue()
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()
        self.next_id = 1
        response = self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        if "result" not in response:
            raise AssertionError(f"MCP initialize failed: {response}")

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self.invalid_stdout.put(line.rstrip("\n"))
                continue
            if not isinstance(payload, dict):
                self.invalid_stdout.put(line.rstrip("\n"))
                continue
            self.messages.put(payload)

    def assert_clean_stdout(self) -> None:
        invalid: list[str] = []
        while True:
            try:
                invalid.append(self.invalid_stdout.get_nowait())
            except queue.Empty:
                break
        if invalid:
            raise AssertionError(f"MCP emitted malformed stdout: {invalid!r}")

    def send(self, payload: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def new_id(self) -> int:
        request_id = self.next_id
        self.next_id += 1
        return request_id

    def wait_for_id(self, request_id: int, timeout: float = 10) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        deferred: list[dict[str, Any]] = []
        try:
            while True:
                self.assert_clean_stdout()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    stderr = ""
                    if (
                        self.process.poll() is not None
                        and self.process.stderr is not None
                    ):
                        stderr = self.process.stderr.read()
                    raise AssertionError(
                        f"timed out waiting for MCP id={request_id}; stderr={stderr!r}"
                    )
                try:
                    message = self.messages.get(timeout=min(remaining, 0.1))
                except queue.Empty:
                    continue
                if message.get("id") == request_id:
                    self.assert_clean_stdout()
                    return message
                deferred.append(message)
        finally:
            for message in deferred:
                self.messages.put(message)

    def assert_no_message(self, timeout: float = 0.2) -> None:
        self.assert_clean_stdout()
        try:
            message = self.messages.get(timeout=timeout)
        except queue.Empty:
            message = None
        if message is not None:
            raise AssertionError(f"unexpected MCP message: {message}")
        self.assert_clean_stdout()

    def request(
        self, method: str, params: dict[str, Any] | None = None, timeout: float = 10
    ) -> dict[str, Any]:
        request_id = self.new_id()
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        self.send(payload)
        return self.wait_for_id(request_id, timeout)

    def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        params_meta: dict[str, Any] | None = None,
        timeout: float = 10,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"name": name, "arguments": arguments}
        if params_meta is not None:
            params["_meta"] = params_meta
        return self.request("tools/call", params, timeout=timeout)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        if self.process.poll() is None:
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=2)
        self.reader.join(timeout=1)
        self.assert_clean_stdout()
        stderr = self.process.stderr.read() if self.process.stderr is not None else ""
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None:
                stream.close()
        if self.process.returncode != 0:
            raise AssertionError(
                f"MCP exited with {self.process.returncode}; stderr={stderr!r}"
            )


def structured(response: dict[str, Any]) -> dict[str, Any]:
    if "error" in response:
        raise AssertionError(f"unexpected MCP error: {response}")
    result = response.get("result")
    if not isinstance(result, dict):
        raise AssertionError(f"missing MCP result: {response}")
    value = result.get("structuredContent")
    if not isinstance(value, dict):
        raise AssertionError(f"missing structured content: {response}")
    content = result.get("content")
    if not isinstance(content, list) or len(content) != 1:
        raise AssertionError(f"missing text fallback: {response}")
    text = content[0].get("text") if isinstance(content[0], dict) else None
    if not isinstance(text, str) or json.loads(text) != value:
        raise AssertionError(f"text fallback differs from structured content: {response}")
    return value


def valid_last_report(state: str) -> dict[str, Any]:
    return {
        "schema": "example.release-status.v1",
        "state": state,
        "terminal": state in {"ready", "failed"},
        "gitlab": {"mr": {"iid": 42, "sha": EXPECTED_SHA}},
    }


def valid_receipt(
    result_path: str,
    *,
    outcome: str = "ready",
    error: str | None = None,
) -> dict[str, Any]:
    terminal = outcome != "running"
    last_report = valid_last_report(outcome) if outcome in {"ready", "failed"} else None
    return {
        "schema": RECEIPT_SCHEMA,
        "outcome": outcome,
        "exitCode": TERMINAL_OUTCOMES.get(outcome),
        "startedAt": "2026-07-14T10:00:00Z",
        "completedAt": "2026-07-14T10:00:05Z" if terminal else None,
        "elapsedSeconds": 5.0 if terminal else 0.0,
        "transitionCount": 1 if last_report is not None else 0,
        "request": {
            "mr": 42,
            "project": "group/mobile-app",
            "requiredJobs": ["integration"],
            "artifacts": {"result": result_path},
        },
        "lastReport": last_report,
        "error": error if outcome == "error" else None,
    }


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        encoded = (json.dumps(payload, sort_keys=True) + "\n").encode()
        view = memoryview(encoded)
        while view:
            view = view[os.write(descriptor, view) :]
    finally:
        os.close(descriptor)
    os.replace(temporary, path)


class DeferredCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = McpHarness()
        self.runtime_directories: set[Path] = set()

    def tearDown(self) -> None:
        try:
            self.server.close()
        finally:
            for directory in self.runtime_directories:
                shutil.rmtree(directory, ignore_errors=True)

    def reserve(self, **overrides: Any) -> dict[str, Any]:
        arguments = {**RESERVE_ARGUMENTS, **overrides}
        response = self.server.call_tool(
            RESERVE_TOOL,
            {**arguments, "_meta": {"hostExtension": "ignored"}},
            params_meta={"progressToken": "reserve-1", "extension": True},
        )
        reservation = structured(response)
        self.runtime_directories.add(Path(reservation["resultPath"]).parent)
        return reservation

    def await_handle(self, handle: str, timeout: float = 10) -> dict[str, Any]:
        response = self.server.call_tool(
            AWAIT_TOOL,
            {"handle": handle, "_meta": {"hostExtension": "ignored"}},
            params_meta={"progressToken": 2, "extension": {"ignored": True}},
            timeout=timeout,
        )
        return structured(response)

    def test_reservation_returns_only_a_private_producer_path(self) -> None:
        reservation = self.reserve()
        self.assertEqual(reservation["status"], "reserved")
        self.assertEqual(reservation["label"], RESERVE_ARGUMENTS["label"])
        self.assertEqual(reservation["schema"], RECEIPT_SCHEMA)
        self.assertEqual(reservation["producerTimeoutSeconds"], 60.0)
        self.assertEqual(reservation["launchGraceSeconds"], 30.0)
        self.assertEqual(reservation["completionGraceSeconds"], 60.0)
        result_path = Path(reservation["resultPath"])
        self.assertTrue(result_path.is_absolute())
        self.assertEqual(result_path.parent.stat().st_mode & 0o777, 0o700)
        self.assertFalse(result_path.exists())
        self.assertNotIn("command", reservation)
        self.assertNotIn("arguments", reservation)

    def test_protocol_negotiation_returns_the_supported_version(self) -> None:
        response = self.server.request(
            "initialize",
            {
                "protocolVersion": "2099-01-01",
                "capabilities": {},
                "clientInfo": {"name": "future-test", "version": "1"},
            },
        )
        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")

    def test_notifications_are_silent_and_explicit_null_id_is_answered(self) -> None:
        self.server.send(
            {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": RESERVE_TOOL,
                    "arguments": {**RESERVE_ARGUMENTS, "command": "must-not-run"},
                },
            }
        )
        self.server.assert_no_message()
        self.server.send({"jsonrpc": "2.0", "id": None, "method": "ping"})
        response = self.server.wait_for_id(None)
        self.assertEqual(response, {"jsonrpc": "2.0", "id": None, "result": {}})

    def test_malformed_and_oversized_frames_do_not_stop_the_server(self) -> None:
        assert self.server.process.stdin is not None
        deeply_nested = "[" * 10_000 + "0" + "]" * 10_000 + "\n"
        oversized = "x" * (262_144 + 100) + "\n"
        self.server.process.stdin.write(deeply_nested)
        self.server.process.stdin.write(oversized)
        self.server.process.stdin.write('{"jsonrpc":"2.0","id":NaN,"method":"ping"}\n')
        self.server.process.stdin.write(
            '{"jsonrpc":"2.0","id":1,"id":2,"method":"ping"}\n'
        )
        self.server.process.stdin.flush()
        errors = [self.server.wait_for_id(None) for _ in range(4)]
        self.assertEqual(
            [response["error"]["code"] for response in errors],
            [-32700, -32700, -32700, -32700],
        )
        response = self.server.request("ping")
        self.assertEqual(response["result"], {})

    def test_concurrent_reservations_share_one_private_runtime_safely(self) -> None:
        request_ids: list[int] = []
        for index in range(16):
            request_id = self.server.new_id()
            request_ids.append(request_id)
            self.server.send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": RESERVE_TOOL,
                        "arguments": {
                            **RESERVE_ARGUMENTS,
                            "label": f"concurrent reservation {index}",
                        },
                    },
                }
            )

        reservations = [
            structured(self.server.wait_for_id(request_id))
            for request_id in request_ids
        ]
        directories = {Path(item["resultPath"]).parent for item in reservations}
        handles = {item["handle"] for item in reservations}
        self.runtime_directories.update(directories)
        self.assertEqual(len(directories), 1)
        self.assertEqual(len(handles), len(reservations))
        self.assertEqual(next(iter(directories)).stat().st_mode & 0o777, 0o700)

    def test_running_to_terminal_completes_in_one_wait_and_is_idempotent(self) -> None:
        reservation = self.reserve()
        result_path = Path(reservation["resultPath"])

        def producer() -> None:
            atomic_write(
                result_path, valid_receipt(str(result_path), outcome="running")
            )
            time.sleep(0.15)
            atomic_write(result_path, valid_receipt(str(result_path), outcome="ready"))

        writer = threading.Thread(target=producer)
        writer.start()
        terminal = self.await_handle(str(reservation["handle"]))
        writer.join(timeout=2)

        self.assertEqual(
            (terminal["status"], terminal["outcome"], terminal["exitCode"]),
            ("terminal", "ready", 0),
        )
        self.assertEqual(terminal["label"], RESERVE_ARGUMENTS["label"])
        self.assertFalse(terminal["receiptRetained"])
        self.assertFalse(result_path.exists())
        repeated = self.await_handle(str(reservation["handle"]))
        self.assertEqual(repeated, terminal)

    def test_all_terminal_outcomes_use_a_fixed_output_projection(self) -> None:
        sentinel = "receipt-secret-must-not-escape"
        for outcome, exit_code in (
            ("failed", 2),
            ("timeout", 3),
            ("error", 2),
        ):
            with self.subTest(outcome=outcome):
                reservation = self.reserve()
                path = Path(reservation["resultPath"])
                atomic_write(
                    path,
                    valid_receipt(
                        str(path),
                        outcome=outcome,
                        error=sentinel if outcome == "error" else None,
                    ),
                )
                terminal = self.await_handle(str(reservation["handle"]))
                self.assertEqual(
                    (terminal["outcome"], terminal["exitCode"]),
                    (outcome, exit_code),
                )
                self.assertEqual(
                    set(terminal),
                    {
                        "status",
                        "handle",
                        "label",
                        "schema",
                        "outcome",
                        "exitCode",
                        "completedAt",
                        "elapsedSeconds",
                        "transitionCount",
                        "receiptRetained",
                    },
                )
                self.assertNotIn(sentinel, json.dumps(terminal))

    def test_wall_clock_adjustment_does_not_reject_monotonic_completion(self) -> None:
        reservation = self.reserve()
        path = Path(reservation["resultPath"])
        payload = valid_receipt(str(path))
        payload["completedAt"] = "2026-07-14T09:59:59Z"
        payload["elapsedSeconds"] = 5.0
        atomic_write(path, payload)
        terminal = self.await_handle(str(reservation["handle"]))
        self.assertEqual(terminal["outcome"], "ready")
        self.assertEqual(terminal["elapsedSeconds"], 5.0)

    def test_json_numbers_compare_by_value_but_booleans_remain_distinct(self) -> None:
        reservation = self.reserve(
            assertions=[{"pointer": "/request/mr", "value": 42.0}]
        )
        path = Path(reservation["resultPath"])
        atomic_write(path, valid_receipt(str(path)))
        terminal = self.await_handle(str(reservation["handle"]))
        self.assertEqual(terminal["outcome"], "ready")

        reservation = self.reserve(
            assertions=[{"pointer": "/request/flag", "value": True}]
        )
        path = Path(reservation["resultPath"])
        payload = valid_receipt(str(path))
        payload["request"]["flag"] = 1
        atomic_write(path, payload)
        rejected = self.server.call_tool(
            AWAIT_TOOL, {"handle": reservation["handle"]}
        )
        self.assertEqual(rejected["error"]["code"], -32602)

    def test_terminal_cache_does_not_exhaust_pending_reservation_quota(self) -> None:
        last: dict[str, Any] | None = None
        for index in range(70):
            reservation = self.reserve(label=f"sequential completion {index}")
            path = Path(reservation["resultPath"])
            atomic_write(path, valid_receipt(str(path)))
            last = self.await_handle(str(reservation["handle"]))
        assert last is not None
        self.assertEqual(last["outcome"], "ready")

    def test_graceful_shutdown_removes_nonterminal_receipt_contents(self) -> None:
        reservation = self.reserve()
        path = Path(reservation["resultPath"])
        payload = valid_receipt(str(path), outcome="running")
        payload["sensitiveDiagnostic"] = "must-not-remain-on-disk"
        atomic_write(path, payload)
        self.server.close()
        self.assertFalse(path.exists())
        self.assertFalse(path.parent.exists())
        with self.assertRaises(FileNotFoundError):
            atomic_write(path, valid_receipt(str(path)))

    def test_sigterm_runs_the_same_runtime_cleanup(self) -> None:
        reservation = self.reserve()
        path = Path(reservation["resultPath"])
        atomic_write(path, valid_receipt(str(path), outcome="running"))
        self.server.process.terminate()
        self.server.process.wait(timeout=3)
        self.assertEqual(self.server.process.returncode, 0)
        self.assertFalse(path.exists())
        self.assertFalse(path.parent.exists())

    def test_post_read_permission_race_is_rejected(self) -> None:
        module_name = f"deferred_completion_server_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, SERVER)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        reservation = module.STORE.reserve(dict(RESERVE_ARGUMENTS))
        path = Path(reservation.result_path)
        self.runtime_directories.add(path.parent)
        atomic_write(path, valid_receipt(str(path)))
        original_read = module.os.read
        changed = False

        def raced_read(descriptor: int, count: int) -> bytes:
            nonlocal changed
            chunk = original_read(descriptor, count)
            if not changed:
                changed = True
                path.chmod(0o644)
            return chunk

        module.os.read = raced_read
        try:
            with self.assertRaises(module.ToolInputError):
                module.read_receipt(reservation)
        finally:
            module.os.read = original_read
            module.STORE.close()
            module.RUNTIME.close()
            sys.modules.pop(module_name, None)

    def test_atomic_replace_during_read_retries_the_new_inode(self) -> None:
        module_name = f"deferred_completion_server_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, SERVER)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        reservation = module.STORE.reserve(dict(RESERVE_ARGUMENTS))
        path = Path(reservation.result_path)
        self.runtime_directories.add(path.parent)
        atomic_write(path, valid_receipt(str(path), outcome="running"))
        replacement = path.with_name(f".{path.name}.terminal")
        atomic_write(replacement, valid_receipt(str(path), outcome="ready"))
        original_read = module.os.read
        replaced = False

        def raced_read(descriptor: int, count: int) -> bytes:
            nonlocal replaced
            chunk = original_read(descriptor, count)
            if not replaced:
                replaced = True
                os.replace(replacement, path)
            return chunk

        module.os.read = raced_read
        try:
            self.assertIsNone(module.read_receipt(reservation))
            module.os.read = original_read
            receipt = module.read_receipt(reservation)
            assert receipt is not None
            self.assertEqual(receipt["outcome"], "ready")
        finally:
            module.os.read = original_read
            replacement.unlink(missing_ok=True)
            module.STORE.close()
            module.RUNTIME.close()
            sys.modules.pop(module_name, None)

    def test_late_running_receipt_cannot_extend_launch_deadline(self) -> None:
        module_name = f"deferred_completion_server_{uuid.uuid4().hex}"
        spec = importlib.util.spec_from_file_location(module_name, SERVER)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        reservation = module.STORE.reserve(dict(RESERVE_ARGUMENTS))
        path = Path(reservation.result_path)
        self.runtime_directories.add(path.parent)
        atomic_write(path, valid_receipt(str(path), outcome="running"))
        reservation.launch_deadline_monotonic = time.monotonic() - 1
        try:
            result = module.await_receipt(reservation, threading.Event())
            self.assertEqual(result["status"], "wait_timeout")
            self.assertEqual(result["stage"], "launch")
            self.assertIsNone(reservation.producer_deadline_monotonic)
        finally:
            module.STORE.close()
            module.RUNTIME.close()
            sys.modules.pop(module_name, None)

    def test_cancel_stops_only_the_wait_and_preserves_the_reservation(self) -> None:
        reservation = self.reserve()
        handle = str(reservation["handle"])
        request_id = self.server.new_id()
        self.server.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": AWAIT_TOOL,
                    "arguments": {"handle": handle},
                    "_meta": {"progressToken": "cancel-me"},
                },
            }
        )
        time.sleep(0.1)
        self.server.send(
            {
                "jsonrpc": "2.0",
                "method": "notifications/cancelled",
                "params": {"requestId": request_id, "reason": "test"},
            }
        )
        cancelled = self.server.wait_for_id(request_id, timeout=3)
        self.assertEqual(cancelled["error"]["code"], -32800)

        path = Path(reservation["resultPath"])
        atomic_write(path, valid_receipt(str(path)))
        terminal = self.await_handle(handle)
        self.assertEqual(terminal["outcome"], "ready")

    def test_tools_reject_execution_and_arbitrary_filesystem_inputs(self) -> None:
        response = self.server.request("tools/list")
        tools = response["result"]["tools"]
        properties = {
            item["name"]: set(item["inputSchema"]["properties"]) for item in tools
        }
        forbidden = {
            "command",
            "argv",
            "pid",
            "session",
            "cwd",
            "workspacePath",
            "env",
            "receiptPath",
            "resultPath",
            "predicate",
            "signal",
        }
        for names in properties.values():
            self.assertTrue(names.isdisjoint(forbidden))

        rejected = self.server.call_tool(
            RESERVE_TOOL, {**RESERVE_ARGUMENTS, "command": "echo unsafe"}
        )
        self.assertEqual(rejected["error"]["code"], -32602)
        reservation = self.reserve()
        rejected_wait = self.server.call_tool(
            AWAIT_TOOL,
            {"handle": reservation["handle"], "workspacePath": "/tmp"},
        )
        self.assertEqual(rejected_wait["error"]["code"], -32602)

        server_source = SERVER.read_text(encoding="utf-8")
        for forbidden_call in (
            "import subprocess",
            "os.system(",
            "os.exec",
            "os.spawn",
            "os.kill(",
            "os.killpg(",
        ):
            self.assertNotIn(forbidden_call, server_source)

    def test_schema_path_and_identity_are_enforced_without_echo(self) -> None:
        mutations = (
            lambda payload: payload.update(schema="different.schema.v1"),
            lambda payload: payload["request"]["artifacts"].update(
                result="/tmp/not-reserved"
            ),
            lambda payload: payload["lastReport"]["gitlab"]["mr"].update(sha="b" * 40),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                reservation = self.reserve()
                path = Path(reservation["resultPath"])
                payload = valid_receipt(str(path))
                mutate(payload)
                payload["sentinel-secret-field"] = "sentinel-secret-value"
                atomic_write(path, payload)
                rejected = self.server.call_tool(
                    AWAIT_TOOL, {"handle": reservation["handle"]}
                )
                self.assertEqual(rejected["error"]["code"], -32602)
                self.assertNotIn("sentinel-secret", json.dumps(rejected))

    def test_duplicate_json_fields_are_rejected(self) -> None:
        reservation = self.reserve()
        path = Path(reservation["resultPath"])
        raw = json.dumps(valid_receipt(str(path)))
        raw = raw.replace('"schema":', '"schema":"duplicate","schema":', 1)
        path.write_text(raw, encoding="utf-8")
        path.chmod(0o600)
        rejected = self.server.call_tool(AWAIT_TOOL, {"handle": reservation["handle"]})
        self.assertEqual(rejected["error"]["code"], -32602)

    def test_non_json_numbers_are_rejected(self) -> None:
        reservation = self.reserve()
        path = Path(reservation["resultPath"])
        raw = json.dumps(valid_receipt(str(path))).replace(
            '"elapsedSeconds": 5.0', '"elapsedSeconds": NaN'
        )
        path.write_text(raw, encoding="utf-8")
        path.chmod(0o600)
        rejected = self.server.call_tool(AWAIT_TOOL, {"handle": reservation["handle"]})
        self.assertEqual(rejected["error"]["code"], -32602)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "safe file tests require POSIX")
    def test_symlink_hardlink_fifo_and_broad_modes_are_rejected(self) -> None:
        def make_symlink(path: Path) -> None:
            target = path.with_name(f"outside-{uuid.uuid4().hex}.json")
            target.write_text("{}", encoding="utf-8")
            path.symlink_to(target)

        def make_hardlink(path: Path) -> None:
            source = path.with_name(f"source-{uuid.uuid4().hex}.json")
            source.write_text("{}", encoding="utf-8")
            source.chmod(0o600)
            os.link(source, path)

        def make_fifo(path: Path) -> None:
            os.mkfifo(path, 0o600)

        def make_world_readable(path: Path) -> None:
            path.write_text("{}", encoding="utf-8")
            path.chmod(0o644)

        for label, creator in (
            ("symlink", make_symlink),
            ("hardlink", make_hardlink),
            ("fifo", make_fifo),
            ("world-readable", make_world_readable),
        ):
            with self.subTest(case=label):
                reservation = self.reserve()
                creator(Path(reservation["resultPath"]))
                started = time.monotonic()
                rejected = self.server.call_tool(
                    AWAIT_TOOL, {"handle": reservation["handle"]}, timeout=3
                )
                self.assertLess(time.monotonic() - started, 1.5)
                self.assertEqual(rejected["error"]["code"], -32602)

    def test_input_bounds_fail_before_a_reservation_is_created(self) -> None:
        invalid_values = (
            {"schema": "contains spaces"},
            {"terminalOutcomes": {"running": 0}},
            {"resultPathPointer": "not-a-pointer"},
            {"producerTimeoutSeconds": 59},
            {
                "producerTimeoutSeconds": 20_880,
                "launchGraceSeconds": 600,
                "completionGraceSeconds": 1800,
            },
            {
                "assertions": [
                    {
                        "pointer": "/request/mr",
                        "value": 42,
                        "outcomes": ["ready", "ready"],
                    }
                ]
            },
        )
        for override in invalid_values:
            with self.subTest(override=override):
                response = self.server.call_tool(
                    RESERVE_TOOL, {**RESERVE_ARGUMENTS, **override}
                )
                self.assertEqual(response["error"]["code"], -32602)


if __name__ == "__main__":
    unittest.main()
