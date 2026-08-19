import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "context-density"
SCRIPT_DIR = SKILL_DIR / "scripts"

with mock.patch.object(sys, "path", [str(SCRIPT_DIR), *sys.path]):
    import token_count  # noqa: E402


class LoadEncoderTests(unittest.TestCase):
    def test_missing_tiktoken_falls_back_to_approximation(self):
        with mock.patch.dict(sys.modules, {"tiktoken": None}):
            encoder, mode = token_count.load_encoder("o200k_base")
        self.assertIsNone(encoder)
        self.assertEqual("approx", mode)

    def test_available_encoder_reports_exact_mode(self):
        fake = mock.Mock()
        fake.get_encoding.return_value = "encoder"
        with mock.patch.dict(sys.modules, {"tiktoken": fake}):
            encoder, mode = token_count.load_encoder("o200k_base")
        self.assertEqual("encoder", encoder)
        self.assertEqual("exact", mode)
        fake.get_encoding.assert_called_once_with("o200k_base")


class CountTextTests(unittest.TestCase):
    def test_approximation_rounds_up_to_four_characters_per_token(self):
        self.assertEqual(0, token_count.count_text("", None))
        self.assertEqual(1, token_count.count_text("abc", None))
        self.assertEqual(2, token_count.count_text("abcde", None))

    def test_encoder_result_length_is_used_when_available(self):
        encoder = mock.Mock()
        encoder.encode.return_value = [1, 2, 3, 4, 5]
        self.assertEqual(5, token_count.count_text("hello", encoder))
        encoder.encode.assert_called_once_with("hello")


class IterFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_directory_walk_keeps_text_and_extensionless_files(self):
        (self.root / "docs").mkdir()
        (self.root / "docs" / "guide.md").write_text("guide\n", encoding="utf-8")
        (self.root / "docs" / "notes.bin").write_bytes(b"\x00\x01")
        (self.root / "Makefile").write_text("all:\n", encoding="utf-8")

        found = token_count.iter_files([str(self.root)])

        self.assertEqual(
            sorted([self.root / "Makefile", self.root / "docs" / "guide.md"]),
            found,
        )

    def test_skip_dirs_are_not_traversed(self):
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "dep.js").write_text("x\n", encoding="utf-8")
        (self.root / "kept.py").write_text("x = 1\n", encoding="utf-8")

        self.assertEqual([self.root / "kept.py"], token_count.iter_files([str(self.root)]))

    def test_explicit_file_paths_bypass_directory_walk_and_are_deduplicated(self):
        target = self.root / "a.md"
        target.write_text("a\n", encoding="utf-8")

        found = token_count.iter_files([str(target), str(target)])

        self.assertEqual([target], found)

    def test_missing_path_is_reported_and_skipped(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            found = token_count.iter_files([str(self.root / "absent.md")])

        self.assertEqual([], found)
        self.assertIn("skipped missing path", stderr.getvalue())


class ReadTextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_utf8_content_is_returned(self):
        path = self.root / "a.md"
        path.write_text("hello\n", encoding="utf-8")
        self.assertEqual("hello\n", token_count.read_text(path))

    def test_invalid_utf8_is_replaced_instead_of_skipped(self):
        path = self.root / "a.md"
        path.write_bytes(b"ok\xff\n")
        text = token_count.read_text(path)
        self.assertIsNotNone(text)
        self.assertIn("ok", text)

    def test_unreadable_file_is_reported_and_skipped(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            text = token_count.read_text(self.root)
        self.assertIsNone(text)
        self.assertIn("skipped unreadable file", stderr.getvalue())


class CountPathsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = mock.patch.object(token_count, "load_encoder", return_value=(None, "approx"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rows_are_sorted_by_descending_tokens_with_aggregated_total(self):
        (self.root / "small.md").write_text("ab\n", encoding="utf-8")
        (self.root / "large.md").write_text("x" * 40 + "\n", encoding="utf-8")

        total, rows = token_count.count_paths([str(self.root)], "o200k_base")

        self.assertEqual(["large.md", "small.md"], [Path(row["path"]).name for row in rows])
        self.assertEqual(2, total["files"])
        self.assertEqual("approx", total["mode"])
        self.assertIsNone(total["encoding"])
        self.assertEqual(sum(row["tokens"] for row in rows), total["tokens"])
        self.assertEqual(44, total["chars"])
        self.assertEqual(4, total["lines"])

    def test_stdin_is_measured_when_no_paths_resolve(self):
        with mock.patch.object(sys, "stdin", io.StringIO("piped text\n")):
            total, rows = token_count.count_paths([], "o200k_base")

        self.assertEqual(["<stdin>"], [row["path"] for row in rows])
        self.assertEqual(1, total["files"])
        self.assertEqual(11, total["chars"])

    def test_exact_mode_records_the_requested_encoding(self):
        (self.root / "a.md").write_text("hello\n", encoding="utf-8")
        encoder = mock.Mock()
        encoder.encode.return_value = [1, 2]
        with mock.patch.object(token_count, "load_encoder", return_value=(encoder, "exact")):
            total, rows = token_count.count_paths([str(self.root)], "cl100k_base")

        self.assertEqual("cl100k_base", total["encoding"])
        self.assertEqual(2, rows[0]["tokens"])


class MainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "a.md").write_text("alpha\n", encoding="utf-8")
        (self.root / "b.md").write_text("beta beta beta beta\n", encoding="utf-8")
        patcher = mock.patch.object(token_count, "load_encoder", return_value=(None, "approx"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, *argv):
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["token_count.py", *argv]), redirect_stdout(stdout):
            code = token_count.main()
        return code, stdout.getvalue()

    def test_json_output_carries_total_and_files(self):
        code, output = self.run_main(str(self.root), "--json")

        payload = json.loads(output)
        self.assertEqual(0, code)
        self.assertEqual(2, payload["total"]["files"])
        self.assertEqual(2, len(payload["files"]))

    def test_top_limits_reported_files_without_changing_the_total(self):
        code, output = self.run_main(str(self.root), "--json", "--top", "1")

        payload = json.loads(output)
        self.assertEqual(0, code)
        self.assertEqual(2, payload["total"]["files"])
        self.assertEqual(1, len(payload["files"]))

    def test_text_output_flags_approximate_counts_and_lists_files(self):
        code, output = self.run_main(str(self.root))

        self.assertEqual(0, code)
        self.assertIn("(approx; install tiktoken for exact counts)", output)
        self.assertIn("a.md", output)
        self.assertIn("b.md", output)


if __name__ == "__main__":
    unittest.main()
