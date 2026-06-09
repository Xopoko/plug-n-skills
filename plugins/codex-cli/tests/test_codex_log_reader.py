import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "codex_log_reader.py"
spec = importlib.util.spec_from_file_location("codex_log_reader", SCRIPT)
reader = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(reader)


THREAD_ID = "019e9b79-3fe7-7f82-ae6f-ca518861bd13"


class CodexLogReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name)
        self.home = home
        log_dir = home / "sessions" / "2026" / "06" / "06"
        log_dir.mkdir(parents=True)
        self.rollout = log_dir / f"rollout-2026-06-06T07-47-55-{THREAD_ID}.jsonl"
        rows = [
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
        with self.rollout.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")
            handle.write('{"timestamp": "broken"\n')

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv):
        out = io.StringIO()
        full_argv = [argv[0], "--codex-home", str(self.home), *argv[1:]]
        with redirect_stdout(out):
            code = reader.main(full_argv)
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_find_ranks_by_thread_id_and_query(self):
        output = self.run_cli(["find", "--thread-id", THREAD_ID, "--query", "ISSUE-123"])
        self.assertIn(THREAD_ID, output)
        self.assertIn("message", output)
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


if __name__ == "__main__":
    unittest.main()
