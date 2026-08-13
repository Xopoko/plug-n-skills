from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "credential_handoff.py"
SPEC = importlib.util.spec_from_file_location("credential_handoff", SCRIPT)
assert SPEC and SPEC.loader
credential_handoff = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = credential_handoff
SPEC.loader.exec_module(credential_handoff)


class CredentialHandoffTests(unittest.TestCase):
    def test_safe_native_and_onepassword_commands_are_allowed(self) -> None:
        for command in (
            ["ssh", "example-host"],
            ["op", "run", "--", "example-cli", "login"],
            ["op", "account", "list"],
        ):
            with self.subTest(command=command):
                credential_handoff.validate_nonsecret_command(command)

    def test_common_secret_bearing_shapes_are_rejected(self) -> None:
        commands = (
            ["tool", "--password", "example"],
            ["tool", "--api-key=example"],
            ["env", "ACCESS_TOKEN=resolved-value", "tool"],
            ["tool", "https://user:password@example.invalid"],
            ["curl", "-H", "Authorization: Bearer example"],
            ["op", "read", "op://vault/item/password"],
            ["op", "run", "--no-masking", "--", "tool"],
            ["tool", "abcdefghijklmnopqrstuvwxyz0123456789TOKENVALUE"],
        )
        for command in commands:
            with self.subTest(command=command):
                with self.assertRaises(credential_handoff.UserFacingError):
                    credential_handoff.validate_nonsecret_command(command)

    def test_env_references_require_names_and_unresolved_op_uris(self) -> None:
        self.assertEqual(
            {"EXAMPLE_TOKEN": "op://vault/item/field"},
            credential_handoff.parse_env_references(
                ["EXAMPLE_TOKEN=op://vault/item/field"]
            ),
        )
        for value in (
            "bad-name=op://vault/item/field",
            "EXAMPLE_TOKEN=resolved-value",
            "EXAMPLE_TOKEN",
        ):
            with self.subTest(value=value):
                with self.assertRaises(credential_handoff.UserFacingError):
                    credential_handoff.parse_env_references([value])

    def test_status_receipt_has_only_allowlisted_nonsecret_fields(self) -> None:
        payload = credential_handoff.status_payload(
            "a" * 32,
            "succeeded",
            "2026-01-01T00:00:00Z",
            exit_code=0,
        )
        self.assertEqual(credential_handoff.STATUS_SCHEMA, payload["schema"])
        self.assertEqual("succeeded", payload["state"])
        self.assertNotIn("command", payload)
        self.assertNotIn("arguments", payload)
        self.assertNotIn("purpose", payload)
        self.assertNotIn("expected_input", payload)
        self.assertNotIn("environment", payload)

    def test_status_reader_rejects_unexpected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "status.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": credential_handoff.STATUS_SCHEMA,
                        "request_id": "a" * 32,
                        "state": "running",
                        "exit_code": None,
                        "created_at_utc": "2026-01-01T00:00:00Z",
                        "updated_at_utc": "2026-01-01T00:00:01Z",
                        "secret": "must-not-pass",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(credential_handoff.UserFacingError):
                credential_handoff.show_status(path)

    def test_cleanup_removes_only_completed_owned_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            request_dir = Path(directory) / ("credential-handoff-" + "a" * 32)
            request_dir.mkdir()
            status_path = request_dir / "status.json"
            status_path.write_text(
                json.dumps(
                    credential_handoff.status_payload(
                        "a" * 32,
                        "succeeded",
                        "2026-01-01T00:00:00Z",
                        exit_code=0,
                    )
                ),
                encoding="utf-8",
            )
            (request_dir / "request.json").write_text("{}", encoding="utf-8")
            credential_handoff.cleanup(status_path)
            self.assertFalse(request_dir.exists())

    def test_cleanup_rejects_running_or_unowned_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            request_dir = Path(directory) / ("credential-handoff-" + "b" * 32)
            request_dir.mkdir()
            status_path = request_dir / "status.json"
            status_path.write_text(
                json.dumps(
                    credential_handoff.status_payload(
                        "b" * 32, "running", "2026-01-01T00:00:00Z"
                    )
                ),
                encoding="utf-8",
            )
            with self.assertRaises(credential_handoff.UserFacingError):
                credential_handoff.cleanup(status_path)
            self.assertTrue(request_dir.exists())

    def test_status_reader_rejects_secret_smuggling_in_allowlisted_fields(self) -> None:
        payload = credential_handoff.status_payload(
            "c" * 32,
            "failed",
            "2026-01-01T00:00:00Z",
            exit_code=1,
        )
        for field, value in (
            ("request_id", "secret-value"),
            ("state", "secret-value"),
            ("error_code", "secret-value"),
            ("updated_at_utc", "secret-value"),
        ):
            candidate = dict(payload)
            candidate[field] = value
            with self.subTest(field=field):
                with self.assertRaises(credential_handoff.UserFacingError):
                    credential_handoff.validate_status_receipt(candidate)

    def test_child_environment_drops_inherited_credentials(self) -> None:
        original = dict(credential_handoff.os.environ)
        try:
            credential_handoff.os.environ.clear()
            credential_handoff.os.environ.update(
                {
                    "PATH": "example-path",
                    "EXAMPLE_PASSWORD": "must-not-pass",
                    "SERVICE_TOKEN": "must-not-pass",
                    "AWS_ACCESS_KEY_ID": "must-not-pass",
                    "SSH_AUTH_SOCK": "must-not-pass",
                }
            )
            environment = credential_handoff.build_child_environment(
                {"TASK_TOKEN": "op://vault/item/field"}
            )
        finally:
            credential_handoff.os.environ.clear()
            credential_handoff.os.environ.update(original)
        self.assertEqual("example-path", environment["PATH"])
        self.assertEqual("op://vault/item/field", environment["TASK_TOKEN"])
        self.assertNotIn("EXAMPLE_PASSWORD", environment)
        self.assertNotIn("SERVICE_TOKEN", environment)
        self.assertNotIn("AWS_ACCESS_KEY_ID", environment)
        self.assertNotIn("SSH_AUTH_SOCK", environment)

    def test_shell_wrappers_and_direct_op_retrieval_are_rejected(self) -> None:
        for command in (
            ["pwsh", "-Command", "example-cli"],
            ["cmd.exe", "/c", "example-cli"],
            ["python.exe", "-c", "print('example')"],
            ["env.exe", "EXAMPLE=1", "example-cli"],
            ["op", "item", "get", "example"],
            ["op", "inject", "-i", "example.tpl"],
            ["op", "run"],
        ):
            with self.subTest(command=command):
                with self.assertRaises(credential_handoff.UserFacingError):
                    credential_handoff.validate_nonsecret_command(command)

    def test_pinned_commands_require_absolute_native_files_and_matching_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native = root / "ssh.exe"
            native.write_bytes(b"synthetic-native-target")
            digest = credential_handoff.sha256_file(native)

            prepared = credential_handoff.prepare_pinned_command(
                [str(native.resolve()), "example-host"],
                executable_sha256=digest,
                op_target_sha256=None,
            )
            self.assertEqual(str(native.resolve()), prepared[0])

            with self.assertRaises(credential_handoff.UserFacingError):
                credential_handoff.prepare_pinned_command(
                    ["ssh.exe", "example-host"],
                    executable_sha256=digest,
                    op_target_sha256=None,
                )
            with self.assertRaises(credential_handoff.UserFacingError):
                credential_handoff.prepare_pinned_command(
                    [str(native.resolve()), "example-host"],
                    executable_sha256="0" * 64,
                    op_target_sha256=None,
                )

    def test_op_run_pins_both_op_and_its_exact_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            op = root / "op.exe"
            target = root / "example-cli.exe"
            op.write_bytes(b"synthetic-op")
            target.write_bytes(b"synthetic-target")
            op_hash = credential_handoff.sha256_file(op)
            target_hash = credential_handoff.sha256_file(target)

            prepared = credential_handoff.prepare_pinned_command(
                [str(op.resolve()), "run", "--", str(target.resolve()), "login"],
                executable_sha256=op_hash,
                op_target_sha256=target_hash,
            )
            self.assertEqual(str(op.resolve()), prepared[0])
            self.assertEqual(str(target.resolve()), prepared[3])
            with self.assertRaises(credential_handoff.UserFacingError):
                credential_handoff.prepare_pinned_command(
                    [str(op.resolve()), "run", "--", str(target.resolve())],
                    executable_sha256=op_hash,
                    op_target_sha256=None,
                )

    def test_atomic_lock_rejects_a_second_launch_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_id = "d" * 32
            lock_dir = credential_handoff.acquire_state_lock(root, request_id)
            with self.assertRaises(credential_handoff.UserFacingError):
                credential_handoff.acquire_state_lock(root, "e" * 32)
            credential_handoff.bind_lock_to_worker(lock_dir, request_id)
            owner = credential_handoff.read_lock_owner(lock_dir)
            self.assertEqual(request_id, owner["request_id"])
            self.assertGreater(owner["worker_pid"], 0)
            credential_handoff.release_state_lock(lock_dir, request_id)
            self.assertFalse(lock_dir.exists())

    def test_cleanup_rejects_forged_terminal_status_while_worker_lock_is_active(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_id = "f" * 32
            request_dir = root / ("credential-handoff-" + request_id)
            request_dir.mkdir()
            status_path = request_dir / "status.json"
            status_path.write_text(
                json.dumps(
                    credential_handoff.status_payload(
                        request_id,
                        "succeeded",
                        "2026-01-01T00:00:00Z",
                        exit_code=0,
                    )
                ),
                encoding="utf-8",
            )
            (request_dir / "request.json").write_text("{}", encoding="utf-8")
            lock_dir = credential_handoff.acquire_state_lock(root, request_id)
            with self.assertRaises(credential_handoff.UserFacingError):
                credential_handoff.cleanup(status_path)
            credential_handoff.release_state_lock(lock_dir, request_id)
            credential_handoff.cleanup(status_path)

    def test_trigger_fixture_covers_positive_and_negative_boundaries(self) -> None:
        payload = json.loads(
            (ROOT / "tests" / "fixtures" / "credential-handoff-trigger-cases.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("agent_harness.credential_handoff_trigger_cases.v1", payload["schema"])
        self.assertEqual("credential-handoff", payload["skill"])
        self.assertGreaterEqual(len(payload["should_trigger"]), 6)
        self.assertGreaterEqual(len(payload["should_not_trigger"]), 4)


if __name__ == "__main__":
    unittest.main()
