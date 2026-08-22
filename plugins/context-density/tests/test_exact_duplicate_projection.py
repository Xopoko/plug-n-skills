from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "context-density"
SCRIPT_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import exact_duplicate_projection as projection  # noqa: E402


class ExactDuplicateProjectionTests(unittest.TestCase):
    def test_contiguous_runs_preserve_unique_records_and_order(self) -> None:
        raw = (
            ("WARN retry\n" * 240)
            + "ERROR CHECKSUM_MISMATCH blob-771\n"
            + ("WARN retry\n" * 160)
            + "process exit code 1\n"
        ).encode()
        result = projection.project_bytes(raw, "raw://test/retries")

        self.assertEqual(result["mode"], "project")
        self.assertEqual(result["input_records"], 402)
        self.assertEqual(result["emitted_records"], 4)
        self.assertEqual(result["omitted_exact_duplicates"], 398)
        self.assertIs(result["raw_recovery_required"], True)
        self.assertLess(result["projected_bytes"], result["input_bytes"])
        text = result["projection"]
        self.assertLess(text.index("count=240"), text.index("CHECKSUM_MISMATCH"))
        self.assertLess(text.index("CHECKSUM_MISMATCH"), text.index("count=160"))
        self.assertLess(text.index("count=160"), text.index("process exit code 1"))
        self.assertEqual(text.count("WARN retry"), 2)
        self.assertEqual(text.count("ERROR CHECKSUM_MISMATCH blob-771"), 1)

    def test_run_receipts_have_exact_arithmetic_and_record_digests(self) -> None:
        alpha = b"record=alpha payload=0123456789abcdef\n"
        beta = b"record=beta payload=0123456789abcdef\n"
        gamma = b"record=gamma payload=0123456789abcdef\n"
        raw = (alpha * 30) + (beta * 20) + (gamma * 10)
        result = projection.project_bytes(raw, "raw://test/arithmetic")

        self.assertEqual(sum(run["count"] for run in result["runs"]), 60)
        self.assertEqual(sum(run["omitted"] for run in result["runs"]), 57)
        self.assertEqual(result["omitted_exact_duplicates"], 57)
        self.assertTrue(all(len(run["record_sha256"]) == 64 for run in result["runs"]))

    def test_noncontiguous_equal_records_remain_separate_runs(self) -> None:
        repeated = "record=A payload=0123456789abcdef0123456789abcdef\n"
        separator = "record=B payload=unique-separator\n"
        raw = ((repeated * 100) + separator + (repeated * 100)).encode()
        result = projection.project_bytes(raw, "raw://test/order")

        self.assertEqual([run["count"] for run in result["runs"]], [100, 1, 100])
        self.assertEqual(result["projection"].count("exact-duplicate-run"), 2)

    def test_small_or_unique_input_keeps_raw(self) -> None:
        for raw, reason in (
            (b"A\nB\nC\n", "no_contiguous_exact_duplicates"),
            (b"A\nA\n", "projection_not_smaller"),
        ):
            with self.subTest(reason=reason):
                result = projection.project_bytes(raw, "raw://test/small")
                self.assertEqual(result["mode"], "keep_raw")
                self.assertEqual(result["reason"], reason)
                self.assertIsNone(result["projection"])

    def test_non_utf8_input_keeps_raw_without_echoing_bytes(self) -> None:
        result = projection.project_bytes(b"ok\n\xff\n", "raw://test/binary")
        self.assertEqual(result["mode"], "keep_raw")
        self.assertEqual(result["reason"], "non_utf8_input")
        self.assertIsNone(result["projection"])

    def test_invalid_raw_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "raw://"):
            projection.project_bytes(b"A\nA\nA\n", "not-a-raw-id")


if __name__ == "__main__":
    unittest.main()
