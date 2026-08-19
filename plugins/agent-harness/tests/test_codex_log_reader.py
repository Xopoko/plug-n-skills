import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "codex_log_reader.py"
spec = importlib.util.spec_from_file_location("codex_log_reader", SCRIPT)
reader = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(reader)


THREAD_ID = "019e9b79-3fe7-7f82-ae6f-ca518861bd13"
MODERN_ROOT_ID = "019f0000-0000-7000-8000-000000000001"
MODERN_PARENT_ID = "019f0000-0000-7000-8000-000000000002"
MODERN_CHILD_ID = "019f0000-0000-7000-8000-000000000003"
AUDIT_ID = "019f0000-0000-7000-8000-000000000004"
LOW_CONFIDENCE_CHILD_ID = "019f0000-0000-7000-8000-000000000005"
DEEP_CHILD_ID = "019f0000-0000-7000-8000-000000000006"
TRUNCATED_DEEP_ID = "019f0000-0000-7000-8000-000000000007"
CORPUS_ROOT_A_ID = "019f0000-0000-7000-8000-000000000008"
CORPUS_ROOT_B_ID = "019f0000-0000-7000-8000-000000000009"
CORPUS_FORK_ID = "019f0000-0000-7000-8000-00000000000a"
CORPUS_SUBAGENT_ID = "019f0000-0000-7000-8000-00000000000b"


class CodexLogReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name)
        self.home = home
        log_dir = home / "sessions" / "2026" / "06" / "06"
        log_dir.mkdir(parents=True)
        self.rollout = log_dir / f"rollout-2026-06-06T07-47-55-{THREAD_ID}.jsonl"
        legacy_rows = [
            {
                "timestamp": "2026-06-06T07:47:55Z",
                "type": "session_meta",
                "payload": {"id": THREAD_ID, "cwd": "/tmp/project", "model_provider": "openai"},
            },
            {
                "timestamp": "2026-06-06T07:48:00Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "Fix ISSUE-123 in parser"},
            },
            {
                "timestamp": "2026-06-06T07:48:01Z",
                "type": "response_item",
                "payload": {"type": "message", "role": "assistant", "content": "I will inspect it."},
            },
            {
                "timestamp": "2026-06-06T07:48:02Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps(
                        {
                            "cmd": "TOKEN=redact-me-value rg ISSUE-123 .",
                            "workdir": "/tmp/project",
                        }
                    ),
                },
            },
            {
                "timestamp": "2026-06-06T07:48:03Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "output": "api_key=should_not_leak",
                },
            },
        ]
        self.write_rollout(self.rollout, legacy_rows, trailing='{"timestamp": "broken"\n')

        self.modern_child = log_dir / f"rollout-2026-06-06T08-00-00-{MODERN_CHILD_ID}.jsonl"
        self.modern_child_rows = self.modern_child_fixture()
        self.modern_child_line_bytes = self.write_rollout(self.modern_child, self.modern_child_rows)

        self.modern_root = log_dir / f"rollout-2026-06-06T08-10-00-{MODERN_ROOT_ID}.jsonl"
        self.write_rollout(
            self.modern_root,
            [
                {
                    "timestamp": "2026-06-06T08:10:00Z",
                    "type": "session_meta",
                    "payload": {
                        "session_id": MODERN_ROOT_ID,
                        "id": MODERN_ROOT_ID,
                        "cwd": "C:/workspace",
                        "source": "cli",
                    },
                },
                {
                    "timestamp": "2026-06-06T08:10:01Z",
                    "type": "event_msg",
                    "payload": {"type": "task_started", "turn_id": "root-turn"},
                },
            ],
        )

    @staticmethod
    def write_rollout(path, rows, trailing=""):
        encoded_lines = [
            (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            for row in rows
        ]
        with path.open("wb") as handle:
            for line in encoded_lines:
                handle.write(line)
            if trailing:
                handle.write(trailing.encode("utf-8"))
        return [len(line) for line in encoded_lines]

    @staticmethod
    def modern_child_fixture():
        mirrored_user = "Inspect the modern rollout."
        mirrored_assistant = "The mirrored answer is ready."
        repeated_assistant = "A repeated status update."
        return [
            # A modern child starts with its own metadata. The copied root
            # session metadata follows at the head of inherited history.
            {
                "timestamp": "2026-06-06T08:00:00Z",
                "type": "session_meta",
                "payload": {
                    "session_id": MODERN_CHILD_ID,
                    "id": MODERN_CHILD_ID,
                    "parent_thread_id": MODERN_PARENT_ID,
                    "cwd": "C:/workspace",
                    "source": {
                        "subagent": {
                            "thread_spawn": {
                                "parent_thread_id": MODERN_PARENT_ID,
                                "depth": 2,
                                "agent_path": "/root/reviewer",
                            }
                        }
                    },
                },
            },
            {
                "timestamp": "2026-06-06T08:00:00.001Z",
                "type": "session_meta",
                "payload": {
                    "session_id": MODERN_ROOT_ID,
                    "id": MODERN_ROOT_ID,
                    "cwd": "C:/workspace",
                    "source": "cli",
                },
            },
            {
                "timestamp": "2026-06-06T08:00:00.002Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_started",
                    "turn_id": "019e0000-0000-7000-8000-000000000001",
                },
            },
            {
                "timestamp": "2026-06-06T08:00:00.003Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Inherited request."}],
                },
            },
            {
                "timestamp": "2026-06-06T08:00:00.004Z",
                "type": "event_msg",
                "payload": {"type": "user_message", "message": "Inherited request."},
            },
            {
                "timestamp": "2026-06-06T08:00:00.005Z",
                "type": "event_msg",
                "payload": {"type": "agent_message", "message": "Inherited answer."},
            },
            {
                "timestamp": "2026-06-06T08:00:00.006Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Inherited answer."}],
                },
            },
            {
                "timestamp": "2026-06-06T08:00:00.007Z",
                "type": "event_msg",
                "payload": {
                    "type": "task_complete",
                    "turn_id": "019e0000-0000-7000-8000-000000000001",
                },
            },
            # The second task_started record is the first active child record.
            {
                "timestamp": "2026-06-06T08:00:01Z",
                "type": "event_msg",
                "payload": {"type": "task_started", "turn_id": MODERN_CHILD_ID},
            },
            {
                "timestamp": "2026-06-06T08:00:02Z",
                "type": "turn_context",
                "payload": {"cwd": "C:/workspace", "model": "test-model"},
            },
            {
                "timestamp": "2026-06-06T08:00:03Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": mirrored_user}],
                },
            },
            {
                "timestamp": "2026-06-06T08:00:03.001Z",
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "message": mirrored_user,
                    "trace_marker": "raw-only-marker",
                },
            },
            {
                "timestamp": "2026-06-06T08:00:04Z",
                "type": "event_msg",
                "payload": {"type": "agent_message", "message": mirrored_assistant},
            },
            {
                "timestamp": "2026-06-06T08:00:04.001Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": mirrored_assistant}],
                },
            },
            {
                "timestamp": "2026-06-06T08:00:05Z",
                "type": "event_msg",
                "payload": {"type": "agent_message", "message": repeated_assistant},
            },
            {
                "timestamp": "2026-06-06T08:00:05.001Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": repeated_assistant}],
                },
            },
            {
                "timestamp": "2026-06-06T08:00:06Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "call_id": "call-shell",
                    "name": "shell_command",
                    "arguments": json.dumps(
                        {"command": "rg modern .", "workdir": "C:/workspace"}
                    ),
                },
            },
            {
                "timestamp": "2026-06-06T08:00:07Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "call_id": "call-exec",
                    "name": "exec",
                    "input": (
                        'const result = await tools.shell_command({command:"git status --short",'
                        'workdir:"C:/workspace"}); text(result)'
                    ),
                },
            },
            {
                "timestamp": "2026-06-06T08:00:08Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "call_id": "call-image",
                    "name": "view_image",
                    "input": json.dumps({"path": "C:/workspace/image.png", "detail": "high"}),
                },
            },
            # Same text after tool activity is a distinct semantic message and
            # must survive mirror-pair deduplication.
            {
                "timestamp": "2026-06-06T08:00:09Z",
                "type": "event_msg",
                "payload": {"type": "agent_message", "message": repeated_assistant},
            },
            {
                "timestamp": "2026-06-06T08:00:09.001Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": repeated_assistant}],
                },
            },
            {
                "timestamp": "2026-06-06T08:00:10Z",
                "type": "event_msg",
                "payload": {"type": "task_complete", "turn_id": MODERN_CHILD_ID},
            },
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv):
        out = io.StringIO()
        full_argv = [argv[0], "--codex-home", str(self.home), *argv[1:]]
        with redirect_stdout(out):
            code = reader.main(full_argv)
        self.assertEqual(code, 0)
        return out.getvalue()

    def run_cli_at_home(self, home, argv, expected=0):
        out = io.StringIO()
        if argv[0] == "corpus-check":
            full_argv = argv
        else:
            full_argv = [argv[0], "--codex-home", str(home), *argv[1:]]
        with redirect_stdout(out):
            code = reader.main(full_argv)
        self.assertEqual(expected, code)
        return out.getvalue()

    def make_corpus_home(self, cwd_by_id=None):
        home = Path(self.tmp.name) / "corpus-home"
        log_dir = home / "sessions" / "2026" / "06" / "07"
        log_dir.mkdir(parents=True)
        cwd_by_id = cwd_by_id or {}

        def add(task_id, second, *, source="vscode", parent=None, mtime=0):
            path = log_dir / f"rollout-2026-06-07T09-00-{second:02d}-{task_id}.jsonl"
            payload = {
                "id": task_id,
                "session_id": task_id,
                "cwd": cwd_by_id.get(task_id, "C:/private/example-project"),
                "source": source,
            }
            if parent:
                payload["parent_thread_id"] = parent
            self.write_rollout(
                path,
                [
                    {
                        "timestamp": f"2026-06-07T09:00:{second:02d}Z",
                        "type": "session_meta",
                        "payload": payload,
                    },
                    {
                        "timestamp": f"2026-06-07T09:01:{second:02d}Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "user_message",
                            "message": "Private prompt must not be copied.",
                        },
                    },
                ],
            )
            os.utime(path, (mtime, mtime))
            return path

        root_a = add(CORPUS_ROOT_A_ID, 8, mtime=1_800_000_100)
        root_b = add(CORPUS_ROOT_B_ID, 9, mtime=1_800_000_200)
        fork = add(
            CORPUS_FORK_ID,
            10,
            source="operator@example.test",
            parent=CORPUS_ROOT_A_ID,
            mtime=1_800_000_300,
        )
        subagent = add(
            CORPUS_SUBAGENT_ID,
            11,
            source={
                "subagent": {
                    "thread_spawn": {
                        "parent_thread_id": CORPUS_ROOT_A_ID,
                        "depth": 1,
                    }
                }
            },
            parent=CORPUS_ROOT_A_ID,
            mtime=1_800_000_400,
        )
        return home, {"root_a": root_a, "root_b": root_b, "fork": fork, "subagent": subagent}

    def test_find_ranks_by_thread_id_and_query(self):
        output = self.run_cli(["find", "--thread-id", THREAD_ID, "--query", "ISSUE-123"])
        self.assertIn(THREAD_ID, output)
        self.assertIn("message", output)
        self.assertIn(str(self.rollout), output)

    def test_exact_find_bypasses_scan_and_recency_limits(self):
        output = self.run_cli(
            [
                "find",
                "--thread-id",
                THREAD_ID,
                "--scan-limit",
                "0",
                "--since-days",
                "0",
            ]
        )
        self.assertIn(THREAD_ID, output)
        self.assertIn(str(self.rollout), output)

    def test_brief_redacts_secret_values_and_reports_malformed(self):
        output = self.run_cli(["brief", THREAD_ID])
        self.assertIn("malformed_lines: 1", output)
        self.assertIn("TOKEN=[REDACTED]", output)
        self.assertNotIn("redact-me-value", output)
        self.assertNotIn("should_not_leak", output)

    def test_search_uses_safe_fields_by_default(self):
        output = self.run_cli(["search", "ISSUE-123", THREAD_ID])
        self.assertIn("ISSUE-123", output)
        self.assertIn("user_message", output)
        self.assertNotIn("api_key=should_not_leak", output)

    def test_commands_can_filter_exec_command(self):
        output = self.run_cli(["commands", THREAD_ID, "--tool", "exec_command"])
        self.assertIn("exec_command", output)
        self.assertIn("TOKEN=[REDACTED]", output)
        self.assertNotIn("redact-me-value", output)

    def test_brief_json_reports_modern_lineage_and_inherited_prefix(self):
        digest = json.loads(self.run_cli(["brief", MODERN_CHILD_ID, "--json"]))

        self.assertEqual(digest["rollout_id"], MODERN_CHILD_ID)
        self.assertEqual(digest["id"], MODERN_CHILD_ID)
        self.assertEqual(digest["root_id"], MODERN_ROOT_ID)
        self.assertEqual(digest["parent_id"], MODERN_PARENT_ID)
        self.assertEqual(digest["ancestor_ids"], [MODERN_PARENT_ID, MODERN_ROOT_ID])
        self.assertEqual(digest["active_start_line"], 9)
        self.assertEqual(digest["pre_active_lines"], 8)
        self.assertEqual(digest["inherited_prefix_lines"], 7)
        self.assertEqual(
            digest["inherited_prefix_bytes"],
            sum(self.modern_child_line_bytes[1:8]),
        )
        self.assertGreater(digest["inherited_prefix_ratio"], 0)
        self.assertLess(digest["inherited_prefix_ratio"], 1)

    def test_brief_json_identifies_a_modern_root_without_inherited_history(self):
        digest = json.loads(self.run_cli(["brief", MODERN_ROOT_ID, "--json"]))

        self.assertEqual(digest["rollout_id"], MODERN_ROOT_ID)
        self.assertEqual(digest["id"], MODERN_ROOT_ID)
        self.assertEqual(digest["root_id"], MODERN_ROOT_ID)
        self.assertIsNone(digest["parent_id"])
        self.assertEqual(digest["inherited_prefix_lines"], 0)
        self.assertEqual(digest["inherited_prefix_bytes"], 0)
        self.assertEqual(digest["inherited_prefix_ratio"], 0)

    def test_deep_lineage_follows_explicit_parent_chain_to_root(self):
        parent = "019e0000-0000-7000-8000-000000000101"
        grandparent = "019e0000-0000-7000-8000-000000000102"
        root = "019e0000-0000-7000-8000-000000000103"
        path = self.rollout.parent / (
            f"rollout-2026-06-06T08-12-00-{DEEP_CHILD_ID}.jsonl"
        )
        self.write_rollout(
            path,
            [
                {
                    "timestamp": "2026-06-06T08:12:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": DEEP_CHILD_ID,
                        "parent_thread_id": parent,
                        "source": {
                            "subagent": {"thread_spawn": {"depth": 3}}
                        },
                    },
                },
                {
                    "timestamp": "2026-06-06T08:11:00Z",
                    "type": "session_meta",
                    "payload": {"id": parent, "parent_thread_id": grandparent},
                },
                {
                    "timestamp": "2026-06-06T08:10:00Z",
                    "type": "session_meta",
                    "payload": {"id": grandparent, "parent_thread_id": root},
                },
                {
                    "timestamp": "2026-06-06T08:00:00Z",
                    "type": "session_meta",
                    "payload": {"id": root, "source": "cli"},
                },
                {
                    "timestamp": "2026-06-06T08:00:01Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_started",
                        "turn_id": "019e0000-0000-7000-8000-000000000001",
                    },
                },
                {
                    "timestamp": "2026-06-06T08:12:01Z",
                    "type": "event_msg",
                    "payload": {"type": "task_started", "turn_id": DEEP_CHILD_ID},
                },
            ],
        )

        digest = json.loads(self.run_cli(["brief", DEEP_CHILD_ID, "--json"]))
        self.assertEqual(digest["parent_id"], parent)
        self.assertEqual(digest["ancestor_ids"], [parent, grandparent, root])
        self.assertEqual(digest["root_id"], root)
        self.assertEqual(digest["active_start_line"], 6)

        truncated_parent = "019e0000-0000-7000-8000-000000000201"
        truncated_path = self.rollout.parent / (
            f"rollout-2026-06-06T08-13-00-{TRUNCATED_DEEP_ID}.jsonl"
        )
        self.write_rollout(
            truncated_path,
            [
                {
                    "timestamp": "2026-06-06T08:13:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": TRUNCATED_DEEP_ID,
                        "parent_thread_id": truncated_parent,
                        "source": {
                            "subagent": {"thread_spawn": {"depth": 2}}
                        },
                    },
                },
                {
                    "timestamp": "2026-06-06T08:12:00Z",
                    "type": "session_meta",
                    "payload": {"id": truncated_parent},
                },
                {
                    "timestamp": "2026-06-06T08:13:01Z",
                    "type": "event_msg",
                    "payload": {
                        "type": "task_started",
                        "turn_id": TRUNCATED_DEEP_ID,
                    },
                },
            ],
        )
        truncated = json.loads(
            self.run_cli(["brief", TRUNCATED_DEEP_ID, "--json"])
        )
        self.assertEqual(truncated["parent_id"], truncated_parent)
        self.assertIsNone(truncated["root_id"])

    def test_brief_json_preserves_legacy_id_alias(self):
        digest = json.loads(self.run_cli(["brief", THREAD_ID, "--json"]))

        self.assertEqual(digest["rollout_id"], THREAD_ID)
        self.assertEqual(digest["id"], digest["rollout_id"])
        self.assertEqual(digest["root_id"], THREAD_ID)
        self.assertIsNone(digest["parent_id"])

    def test_messages_deduplicate_only_adjacent_mirror_pairs(self):
        rows = json.loads(self.run_cli(["messages", MODERN_CHILD_ID, "--json"]))
        messages = [row["message"] for row in rows]

        self.assertEqual(messages.count("Inherited request."), 0)
        self.assertEqual(messages.count("Inherited answer."), 0)
        self.assertEqual(messages.count("Inspect the modern rollout."), 1)
        self.assertEqual(messages.count("The mirrored answer is ready."), 1)
        self.assertEqual(messages.count("A repeated status update."), 2)

        timeline = json.loads(self.run_cli(["timeline", MODERN_CHILD_ID, "--json"]))
        timeline_messages = [
            row["summary"]
            for row in timeline
            if row["kind"] in {"user", "assistant"}
        ]
        self.assertEqual(timeline_messages.count("Inspect the modern rollout."), 1)
        self.assertEqual(timeline_messages.count("The mirrored answer is ready."), 1)
        self.assertEqual(timeline_messages.count("A repeated status update."), 2)

        digest = json.loads(self.run_cli(["brief", MODERN_CHILD_ID, "--json"]))
        self.assertEqual(digest["last_user"].count("Inspect the modern rollout."), 1)
        self.assertEqual(digest["last_assistant"].count("The mirrored answer is ready."), 1)
        self.assertEqual(digest["last_assistant"].count("A repeated status update."), 2)

        inherited_rows = json.loads(
            self.run_cli(
                ["messages", MODERN_CHILD_ID, "--include-inherited", "--json"]
            )
        )
        inherited_messages = [row["message"] for row in inherited_rows]
        self.assertEqual(inherited_messages.count("Inherited request."), 1)
        self.assertEqual(inherited_messages.count("Inherited answer."), 1)

    def test_commands_include_modern_shell_exec_and_custom_tool_records(self):
        rows = json.loads(self.run_cli(["commands", MODERN_CHILD_ID, "--json"]))
        by_tool = {row["tool"]: row["summary"] for row in rows}

        # `exec` input is JavaScript, not a structured nested-call ledger. Keep
        # the outer call honest instead of inventing a second shell_command.
        self.assertEqual(
            [row["tool"] for row in rows],
            ["shell_command", "exec", "view_image"],
        )
        self.assertIn("shell_command", by_tool)
        self.assertIn("rg modern .", by_tool["shell_command"])
        self.assertIn("exec", by_tool)
        self.assertIn("tools.shell_command", by_tool["exec"])
        self.assertIn("git status --short", by_tool["exec"])
        self.assertNotIn("nested_tools", next(row for row in rows if row["tool"] == "exec"))
        self.assertIn("view_image", by_tool)
        self.assertIn("image.png", by_tool["view_image"])

    def test_active_scope_applies_to_search_and_brief(self):
        default_search = self.run_cli(["search", "Inherited request", MODERN_CHILD_ID])
        inherited_search = self.run_cli(
            [
                "search",
                "Inherited request",
                MODERN_CHILD_ID,
                "--include-inherited",
            ]
        )
        self.assertEqual(default_search, "")
        self.assertIn("Inherited request", inherited_search)

        active = json.loads(self.run_cli(["brief", MODERN_CHILD_ID, "--json"]))
        full = json.loads(
            self.run_cli(["brief", MODERN_CHILD_ID, "--include-inherited", "--json"])
        )
        self.assertEqual(active["scope"], "active")
        self.assertEqual(active["scope_start_line"], 9)
        self.assertEqual(full["scope"], "all")
        self.assertEqual(full["scope_start_line"], 1)
        self.assertNotIn("Inherited request.", active["last_user"])

        self.assertEqual(
            self.run_cli(["search", "raw-only-marker", MODERN_CHILD_ID]),
            "",
        )
        raw_search = self.run_cli(
            ["search", "raw-only-marker", MODERN_CHILD_ID, "--raw-line"]
        )
        self.assertIn("raw-only-marker", raw_search)

    def test_low_confidence_boundary_does_not_hide_history(self):
        path = self.rollout.parent / (
            f"rollout-2026-06-06T08-15-00-{LOW_CONFIDENCE_CHILD_ID}.jsonl"
        )
        self.write_rollout(
            path,
            [
                {
                    "timestamp": "2026-06-06T08:15:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": LOW_CONFIDENCE_CHILD_ID,
                        "parent_thread_id": MODERN_PARENT_ID,
                        "source": {
                            "subagent": {"thread_spawn": {"depth": 2}}
                        },
                    },
                },
                {
                    "timestamp": "2026-06-06T08:15:00.001Z",
                    "type": "event_msg",
                    "payload": {"type": "task_started", "turn_id": "legacy-parent"},
                },
                {
                    "timestamp": "2026-06-06T08:15:00.002Z",
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Visible inherited."},
                },
                {
                    "timestamp": "2026-06-06T08:15:10Z",
                    "type": "event_msg",
                    "payload": {"type": "task_started", "turn_id": "legacy-child"},
                },
                {
                    "timestamp": "2026-06-06T08:15:10.001Z",
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Visible active."},
                },
            ],
        )

        brief = json.loads(
            self.run_cli(["brief", LOW_CONFIDENCE_CHILD_ID, "--json"])
        )
        messages = self.run_cli(["messages", LOW_CONFIDENCE_CHILD_ID])
        self.assertEqual(brief["boundary_basis"], "timestamp-gap")
        self.assertEqual(brief["active_scope_confidence"], "low")
        self.assertEqual(brief["scope"], "boundary-undetermined")
        self.assertIsNone(brief["scope_start_line"])
        self.assertEqual(messages, "")
        all_messages = self.run_cli(
            ["messages", LOW_CONFIDENCE_CHILD_ID, "--include-inherited"]
        )
        self.assertIn("Visible inherited.", all_messages)
        self.assertIn("Visible active.", all_messages)

    def test_audit_reports_measured_failures_repeats_and_opaque_exec(self):
        path = self.rollout.parent / f"rollout-2026-06-06T08-20-00-{AUDIT_ID}.jsonl"
        rows = [
            {
                "timestamp": "2026-06-06T08:20:00Z",
                "type": "session_meta",
                "payload": {"id": AUDIT_ID, "cwd": "C:/workspace"},
            },
            {
                "timestamp": "2026-06-06T08:20:01Z",
                "type": "event_msg",
                "payload": {"type": "task_started", "turn_id": "audit-turn"},
            },
            {
                "timestamp": "2026-06-06T08:20:02Z",
                "type": "response_item",
                "payload": {"type": "agent_message", "message": "Unicode arrow: →"},
            },
            {
                "timestamp": "2026-06-06T08:20:03Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "call_id": "call-1",
                    "name": "shell_command",
                    "arguments": json.dumps({"command": "git status --short"}),
                },
            },
            {
                "timestamp": "2026-06-06T08:20:04Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-1",
                    "output": json.dumps({"exit_code": 0}),
                },
            },
            {
                "timestamp": "2026-06-06T08:20:05Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "call_id": "call-2",
                    "name": "shell_command",
                    "arguments": json.dumps({"command": "git status --short"}),
                },
            },
            {
                "timestamp": "2026-06-06T08:20:06Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-2",
                    "output": json.dumps({"exit_code": 1}),
                },
            },
            {
                "timestamp": "2026-06-06T08:20:07Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call",
                    "call_id": "call-exec",
                    "name": "exec",
                    "input": "const token='sk-abcdefghijklmnop'; tools.fake()",
                },
            },
            {
                "timestamp": "2026-06-06T08:20:08Z",
                "type": "compacted",
                "payload": {"summary": "bounded marker"},
            },
            {
                "timestamp": "2026-06-06T08:20:09Z",
                "type": "unknown_future_record",
                "payload": {
                    "type": "future",
                    "password": "public-safe-demo-value",
                    "output": json.dumps(
                        {"password": "nested-public-safe-demo-value"}
                    ),
                },
            },
        ]
        self.write_rollout(path, rows, trailing='{"timestamp":"broken"\n')

        report = json.loads(self.run_cli(["audit", AUDIT_ID, "--json"]))
        self.assertEqual(report["logical_messages"]["by_role"]["assistant"], 1)
        self.assertEqual(report["outer_tool_calls"]["total"], 3)
        self.assertEqual(report["outer_tool_calls"]["by_tool"]["shell_command"], 2)
        self.assertEqual(report["outer_tool_calls"]["opaque_exec_calls"], 1)
        self.assertEqual(report["call_output_pairs"]["paired"], 2)
        self.assertEqual(len(report["explicit_failures"]), 1)
        self.assertEqual(report["explicit_failures"][0]["tool"], "shell_command")
        self.assertEqual(len(report["repeat_candidates"]), 1)
        self.assertEqual(report["repeat_candidates"][0]["count"], 2)
        self.assertEqual(report["potential_duplicate_calls"], 1)
        self.assertEqual(report["compactions"], {"count": 1, "lines": [9]})
        self.assertEqual(report["malformed_lines"], 1)
        self.assertNotIn("nested_tools", report)
        self.assertNotIn("abcdefghijklmnop", json.dumps(report))

        messages = self.run_cli(["messages", AUDIT_ID])
        self.assertIn("Unicode arrow: →", messages)
        commands = self.run_cli(["commands", AUDIT_ID, "--tool", "exec"])
        self.assertIn("[REDACTED]", commands)
        self.assertNotIn("abcdefghijklmnop", commands)
        raw_search = self.run_cli(
            ["search", "unknown_future_record", AUDIT_ID, "--raw-line"]
        )
        self.assertIn("[REDACTED]", raw_search)
        self.assertNotIn("public-safe-demo-value", raw_search)
        self.assertNotIn("nested-public-safe-demo-value", raw_search)

    def test_redaction_covers_structured_and_quoted_secret_shapes(self):
        canary = "public-safe-demo-value"
        private_key = (
            "-----BEGIN "
            + "PRIVATE KEY-----\n"
            + canary
            + "\n-----END "
            + "PRIVATE KEY-----"
        )
        samples = [
            {"nested": {"password": canary}},
            json.dumps({"api_key": canary}),
            f'PASSWORD="{canary} with spaces"',
            f"MY_TOKEN={canary}",
            f"GENERIC_SETTING={canary}",
            f'$env:GENERIC_SETTING="{canary} with spaces"',
            f"Authorization: Basic {canary}",
            f"Cookie: session={canary}; theme=dark",
            f"https://demo-user:{canary}@example.test/path",
            private_key,
        ]
        for sample in samples:
            with self.subTest(sample=type(sample).__name__):
                redacted = reader.redact(sample)
                self.assertNotIn(canary, redacted)
                self.assertIn("[REDACTED", redacted)

        control_text = (
            "\x1b]52;c;clipboard\x07safe\u202etext\x1b[31m"
            "\u009b31m\u009d52;c;clipboard\x07"
        )
        control_safe = reader.redact(control_text)
        for control in ("\x1b", "\x07", "\u202e", "\u009b", "\u009d"):
            self.assertNotIn(control, control_safe)
        self.assertIn("[CONTROL]", control_safe)

    def test_failure_detection_requires_result_envelope_evidence(self):
        domain_payload = {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "output": json.dumps(
                    {
                        "result": {"status": "failed"},
                        "note": "documentation says Exit code: 1",
                    }
                ),
            },
        }
        explicit_exit = {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "output": "Script failed\nExit code: 2\n",
            },
        }
        quoted_documentation = {
            "type": "response_item",
            "payload": {
                "type": "function_call_output",
                "output": json.dumps("documentation\nExit code: 7\n"),
            },
        }
        self.assertEqual(reader._explicit_failure_reason(domain_payload), "")
        self.assertEqual(
            reader._explicit_failure_reason(quoted_documentation), ""
        )
        self.assertEqual(
            reader._explicit_failure_reason(explicit_exit),
            "output.exit_code=2",
        )

    def test_doctor_does_not_apply_posix_mode_warning_on_windows(self):
        with mock.patch.object(
            reader, "supports_posix_mode_checks", return_value=False
        ):
            report = json.loads(self.run_cli(["doctor", THREAD_ID, "--json"]))
        self.assertEqual(report[0]["mode"], "")
        self.assertNotIn("world-readable", report[0]["issues"])

    def test_target_path_must_be_a_rollout_jsonl_file(self):
        other = self.home / "notes.txt"
        other.write_text("not a rollout", encoding="utf-8")
        with self.assertRaisesRegex(
            SystemExit, "target path must be a rollout"
        ):
            reader.main(
                ["messages", "--codex-home", str(self.home), str(other)]
            )

    def test_find_reasons_do_not_echo_query_literals(self):
        rows = json.loads(
            self.run_cli(["find", "--query", "ISSUE-123", "--json"])
        )
        reasons = rows[0]["reasons"]
        self.assertTrue(any(reason.startswith("message:") for reason in reasons))
        self.assertFalse(any("ISSUE-123" in reason for reason in reasons))

    def test_corpus_is_metadata_only_and_excludes_current_and_subagents(self):
        home, _paths = self.make_corpus_home()
        output_dir = Path(self.tmp.name) / "corpus-output"
        with mock.patch.dict(os.environ, {"CODEX_THREAD_ID": CORPUS_ROOT_B_ID}):
            summary = json.loads(
                self.run_cli_at_home(
                    home,
                    [
                        "corpus",
                        "--count",
                        "2",
                        "--output-dir",
                        str(output_dir),
                        "--cutoff",
                        "2030-01-01T00:00:00Z",
                        "--json",
                    ],
                )
            )
        self.assertTrue(summary["complete"])
        self.assertEqual(2, summary["selected_count"])
        manifest = json.loads(
            (output_dir / "corpus-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1, manifest["exclusions"]["internal_subagent"])
        self.assertEqual(1, manifest["exclusions"]["explicit_or_current"])
        task_rows = [
            json.loads(line)
            for line in (output_dir / "task-index.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual([CORPUS_FORK_ID, CORPUS_ROOT_A_ID], [row["task_id"] for row in task_rows])
        self.assertEqual(["fork", "root"], [row["task_kind"] for row in task_rows])
        self.assertEqual(["other", "vscode"], [row["source_kind"] for row in task_rows])
        serialized = json.dumps(task_rows)
        self.assertNotIn("Private prompt", serialized)
        self.assertNotIn("operator@example.test", serialized)
        self.assertNotIn("example-project", serialized)
        self.assertNotIn("cwd", serialized.lower())
        self.assertTrue(all(not Path(row["rollout_ref"]).is_absolute() for row in task_rows))

        check = json.loads(
            self.run_cli_at_home(
                home,
                ["corpus-check", str(output_dir), "--json"],
            )
        )
        self.assertTrue(check["valid"])
        self.assertEqual(2, check["pending"])

        invalid_threshold = json.loads(
            self.run_cli_at_home(
                home,
                [
                    "corpus-check",
                    str(output_dir),
                    "--min-independent",
                    "0",
                    "--json",
                ],
                expected=1,
            )
        )
        self.assertIn(
            "argument:min-independent-must-be-positive",
            invalid_threshold["errors"],
        )

        with self.assertRaisesRegex(SystemExit, "output already exists"):
            reader.main(
                [
                    "corpus",
                    "--codex-home",
                    str(home),
                    "--count",
                    "2",
                    "--output-dir",
                    str(output_dir),
                    "--cutoff",
                    "2030-01-01T00:00:00Z",
                ]
            )

    def test_corpus_cwd_filter_uses_path_boundaries(self):
        home, _paths = self.make_corpus_home(
            {
                CORPUS_ROOT_A_ID: "C:/private/example-project-old",
                CORPUS_ROOT_B_ID: "C:/private/example-project/child",
                CORPUS_FORK_ID: "C:/private/example-project",
            }
        )
        output_dir = Path(self.tmp.name) / "cwd-filter-output"
        summary = json.loads(
            self.run_cli_at_home(
                home,
                [
                    "corpus",
                    "--count",
                    "2",
                    "--output-dir",
                    str(output_dir),
                    "--cwd",
                    "c:\\private\\example-project\\",
                    "--cutoff",
                    "2030-01-01T00:00:00Z",
                    "--json",
                ],
            )
        )
        self.assertTrue(summary["complete"])
        task_rows = [
            json.loads(line)
            for line in (output_dir / "task-index.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        self.assertEqual(
            [CORPUS_FORK_ID, CORPUS_ROOT_B_ID],
            [row["task_id"] for row in task_rows],
        )
        manifest = json.loads(
            (output_dir / "corpus-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1, manifest["exclusions"]["cwd_mismatch"])
        self.assertTrue(manifest["created_at"].endswith("Z"))

        self.assertTrue(
            reader._path_is_within_scope(
                "C:/private/example-project/child", "C:/private/example-project"
            )
        )
        self.assertFalse(
            reader._path_is_within_scope(
                "C:/private/example-project-old", "C:/private/example-project"
            )
        )
        self.assertFalse(
            reader._path_is_within_scope(
                "C:/private", "C:/private/example-project"
            )
        )

    def test_corpus_requires_exact_count_unless_partial_is_explicit(self):
        home, _paths = self.make_corpus_home()
        output_dir = Path(self.tmp.name) / "partial-output"
        with self.assertRaisesRegex(SystemExit, "eligible task count is smaller"):
            reader.main(
                [
                    "corpus",
                    "--codex-home",
                    str(home),
                    "--count",
                    "10",
                    "--output-dir",
                    str(output_dir),
                    "--cutoff",
                    "2030-01-01T00:00:00Z",
                ]
            )
        summary = json.loads(
            self.run_cli_at_home(
                home,
                [
                    "corpus",
                    "--count",
                    "10",
                    "--output-dir",
                    str(output_dir),
                    "--cutoff",
                    "2030-01-01T00:00:00Z",
                    "--allow-partial",
                    "--json",
                ],
            )
        )
        self.assertFalse(summary["complete"])
        self.assertEqual(3, summary["selected_count"])

    def test_corpus_final_check_enforces_independence_and_privacy(self):
        home, _paths = self.make_corpus_home()
        output_dir = Path(self.tmp.name) / "final-output"
        self.run_cli_at_home(
            home,
            [
                "corpus",
                "--count",
                "3",
                "--output-dir",
                str(output_dir),
                "--cutoff",
                "2030-01-01T00:00:00Z",
            ],
        )
        coding_path = output_dir / "coding-ledger.jsonl"
        coding_rows = [json.loads(line) for line in coding_path.read_text(encoding="utf-8").splitlines()]
        for row in coding_rows:
            row["review_status"] = "complete"
            row["eof_receipt"] = {"complete": True, "method": "local-active-scope"}
            row["outcome"] = "bounded synthetic outcome"
            row["classification"] = "missing_capability"
            row["evidence_strength"] = "strong"
            row["privacy_sensitivity"] = "low"
        coding_path.write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in coding_rows),
            encoding="utf-8",
        )
        task_ids = [row["task_id"] for row in coding_rows]
        cluster = {
            "schema": reader.CORPUS_CLUSTER_SCHEMA,
            "cluster_id": "synthetic-repeated-gap",
            "task_ids": task_ids,
            "independent_task_ids": task_ids,
            "independent_count": 3,
            "decision": "candidate",
            "classification": "missing_capability",
            "inference": "A public-safe synthetic gap repeats.",
            "counterevidence": ["Existing owners were checked."],
            "existing_owner_assessment": "No owner in the synthetic fixture.",
            "cheapest_discriminator": "Run one held-out synthetic case.",
        }
        (output_dir / "cluster-ledger.jsonl").write_text(
            json.dumps(cluster, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        handoff_path = output_dir / "workbench-handoff.json"
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff["status"] = "ready_for_review"
        handoff_candidate = {
            "cluster_id": cluster["cluster_id"],
            "affected_artifact_at_task_time": "none in synthetic fixture",
            "current_artifact_state": "no owner in synthetic fixture",
            "proposed_owner": "agent-harness",
            "proposed_artifact_type": "skill",
            "hypothesis": "A focused route reduces repeated recovery work.",
            "cheapest_discriminator": "Replay one held-out synthetic case.",
            "evidence_pointers": [f"task-index:{task_ids[0]}"],
            "validation_scenarios": ["held-out positive route"],
            "regression_scenarios": ["near-miss existing-owner route"],
            "safety_notes": ["metadata only; no source edits authorized"],
            "uncertainty": "Synthetic evidence does not prove field frequency.",
            "residual_tradeoff": "The route adds catalog context cost.",
        }
        handoff["candidate_gaps"] = [handoff_candidate]
        handoff_path.write_text(json.dumps(handoff), encoding="utf-8")

        valid = json.loads(
            self.run_cli_at_home(
                home,
                ["corpus-check", str(output_dir), "--final", "--json"],
            )
        )
        self.assertTrue(valid["valid"])
        self.assertEqual(3, valid["completed"])

        del handoff_candidate["hypothesis"]
        handoff_path.write_text(json.dumps(handoff), encoding="utf-8")
        incomplete_handoff = json.loads(
            self.run_cli_at_home(
                home,
                ["corpus-check", str(output_dir), "--final", "--json"],
                expected=1,
            )
        )
        self.assertIn(
            "handoff:synthetic-repeated-gap:missing-hypothesis",
            incomplete_handoff["errors"],
        )
        handoff_candidate["hypothesis"] = (
            "A focused route reduces repeated recovery work."
        )
        handoff_path.write_text(json.dumps(handoff), encoding="utf-8")

        coding_rows[2]["review_status"] = "skipped"
        coding_rows[2]["skip_reason"] = "synthetic exclusion"
        coding_path.write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in coding_rows),
            encoding="utf-8",
        )
        skipped_independent = json.loads(
            self.run_cli_at_home(
                home,
                ["corpus-check", str(output_dir), "--final", "--json"],
                expected=1,
            )
        )
        self.assertIn(
            "cluster:synthetic-repeated-gap:independent-task-not-complete",
            skipped_independent["errors"],
        )
        self.assertIn(
            "cluster:synthetic-repeated-gap:below-independent-threshold",
            skipped_independent["errors"],
        )
        coding_rows[2]["review_status"] = "complete"
        coding_rows[2].pop("skip_reason")

        coding_rows[1]["independence_group"] = coding_rows[0]["independence_group"]
        coding_path.write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in coding_rows),
            encoding="utf-8",
        )
        duplicate_group = json.loads(
            self.run_cli_at_home(
                home,
                ["corpus-check", str(output_dir), "--final", "--json"],
                expected=1,
            )
        )
        self.assertIn(
            "cluster:synthetic-repeated-gap:duplicate-independence-group",
            duplicate_group["errors"],
        )

        coding_rows[1]["independence_group"] = coding_rows[1]["task_id"]
        coding_rows[0]["observations"] = ["Contact user@example.test for the raw transcript."]
        coding_path.write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in coding_rows),
            encoding="utf-8",
        )
        invalid = json.loads(
            self.run_cli_at_home(
                home,
                ["corpus-check", str(output_dir), "--final", "--json"],
                expected=1,
            )
        )
        self.assertFalse(invalid["valid"])
        self.assertTrue(any(item.startswith("email-indicator") for item in invalid["errors"]))


if __name__ == "__main__":
    unittest.main()
