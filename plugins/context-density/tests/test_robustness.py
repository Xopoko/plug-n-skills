"""Determinism, convergence, feedback-loop, and hostile-input guarantees.

These tests exist so 'it works' is a measured property, not an impression:
same tree -> same output; fix -> strictly better re-audit; audit outputs never
feed back into audit inputs; malformed or weird inputs fail cleanly or are
tolerated, never tracebacks.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "context-density"
SCRIPT_DIR = SKILL_DIR / "scripts"
AUDIT = SCRIPT_DIR / "context_density_audit.py"
OVERLAP = SCRIPT_DIR / "description_overlap.py"
REPORT = SCRIPT_DIR / "agent_context_report.py"

from test_context_density_audit import write_seeded_corpus  # noqa: E402


def run_audit(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(AUDIT), *args], capture_output=True, text=True, check=False
    )


def payload_of(result: subprocess.CompletedProcess) -> dict:
    payload = json.loads(result.stdout)
    payload.pop("generated_at_utc", None)
    return payload


class DeterminismTests(unittest.TestCase):
    def test_audit_output_is_identical_across_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_seeded_corpus(root)
            first = payload_of(run_audit(str(root)))
            second = payload_of(run_audit(str(root)))
        self.assertEqual(first, second)

    def test_overlap_output_is_identical_across_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for name in ("alpha", "beta"):
                d = root / name
                d.mkdir()
                (d / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: audit token cost and prompt compression for {name}\n---\n",
                    encoding="utf-8",
                )
            runs = []
            for _ in range(2):
                result = subprocess.run(
                    [sys.executable, str(OVERLAP), str(root)], capture_output=True, text=True, check=True
                )
                payload = json.loads(result.stdout)
                payload.pop("generated_at_utc", None)
                runs.append(payload)
        self.assertEqual(runs[0], runs[1])

    def test_remeasuring_unchanged_tree_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_seeded_corpus(root)
            wasted = [
                payload_of(run_audit(str(root)))["duplication_summary"]["wasted_tokens"]
                for _ in range(3)
            ]
        self.assertEqual(len(set(wasted)), 1)


class ConvergenceTests(unittest.TestCase):
    def test_fix_then_reaudit_strictly_improves_and_adds_nothing(self):
        from test_context_density_audit import DUP_BLOCK, NEAR_BLOCK_B

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_seeded_corpus(root)
            before = payload_of(run_audit(str(root)))
            w_before = before["duplication_summary"]["wasted_tokens"]
            kinds_before = {
                r["kind"]
                for r in before["context_risks"] + before["compression_risks"] + before["contract_risks"]
            }
            self.assertGreater(w_before, 0)

            dup_b = root / "references" / "dup_b.md"
            text = dup_b.read_text(encoding="utf-8")
            text = text.replace(DUP_BLOCK, "See dup_a.md for the shared preservation rule.")
            text = text.replace(NEAR_BLOCK_B, "Token measurement workflow lives in dup_a.md.")
            dup_b.write_text(text, encoding="utf-8")

            after = payload_of(run_audit(str(root)))
            w_after = after["duplication_summary"]["wasted_tokens"]
            kinds_after = {
                r["kind"]
                for r in after["context_risks"] + after["compression_risks"] + after["contract_risks"]
            }
        self.assertLess(w_after, w_before)
        self.assertTrue(
            kinds_after.issubset(kinds_before),
            f"fix introduced new finding kinds: {kinds_after - kinds_before}",
        )


class FeedbackLoopTests(unittest.TestCase):
    def test_emitted_checklist_is_excluded_from_future_audits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "README.md").write_text(
                "# Readme\nPrompt caching makes repeated prompts cheaper.\n", encoding="utf-8"
            )
            baseline = payload_of(run_audit(str(root)))
            checklist = root / "gate-evidence.md"
            run_audit(str(root), "--emit-gate-checklist", str(checklist))
            self.assertTrue(checklist.exists())
            rerun = payload_of(run_audit(str(root)))
        self.assertEqual(baseline["risk_counts"], rerun["risk_counts"])
        all_paths = {
            r["path"]
            for r in rerun["context_risks"] + rerun["compression_risks"] + rerun["contract_risks"]
        }
        self.assertNotIn(str(checklist), all_paths)


class HostileInputTests(unittest.TestCase):
    def test_weird_inputs_do_not_crash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "empty.md").write_text("", encoding="utf-8")
            (root / "frontmatter_only.md").write_text("---\nname: x\n---\n", encoding="utf-8")
            (root / "unclosed_fence.md").write_text("# T\n\n```bash\nnever closed\n", encoding="utf-8")
            (root / "crlf.md").write_bytes(b"# T\r\n\r\nline one\r\nline two\r\n")
            (root / "unicode.md").write_text("# T\n\nemoji \U0001f9e0 ümläut 中文 text\n", encoding="utf-8")
            (root / "binaryish.md").write_bytes(b"\x00\x80\xff\xfe garbage \x00 bytes")
            (root / "long_line.md").write_text("# T\n\n" + "x" * 60000 + "\n", encoding="utf-8")
            result = run_audit(str(root))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn("token_summary", payload)

    def test_approx_mode_without_tiktoken_still_measures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_seeded_corpus(root)
            result = run_audit(str(root), "--encoding", "no-such-encoding")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["mode"], "approx")
        self.assertGreater(payload["duplication_summary"]["wasted_tokens"], 0)

    def test_malformed_load_path_map_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.md").write_text("# A\n", encoding="utf-8")
            bad = root / "map.json"
            bad.write_text("{not json", encoding="utf-8")
            result = run_audit(str(root / "a.md"), "--load-path-map", str(bad))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("load_path_map_invalid_json", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_ledger_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "a.md").write_text("# A\n", encoding="utf-8")
            bad = root / "atoms.json"
            bad.write_text("[{broken", encoding="utf-8")
            result = run_audit(str(root / "a.md"), "--commitment-ledger", str(bad))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commitment_ledger_invalid_json", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_bom_prefixed_skill_md_is_parsed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            d = root / "bom-skill"
            d.mkdir()
            (d / "SKILL.md").write_bytes(
                "﻿---\nname: bom-skill\ndescription: parses despite byte order mark\n---\n".encode("utf-8")
            )
            result = subprocess.run(
                [sys.executable, str(OVERLAP), str(root)], capture_output=True, text=True, check=True
            )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["skills_scanned"], 1)

    def test_reporter_tolerates_garbage_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir) / ".codex"
            home.mkdir()
            (home / "config.toml").write_text("[[[ not toml ===\x00", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(REPORT), "mcp", "--agent", "codex", "--agent-home", str(home), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()
