import json
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "context-density"
SCRIPT_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import context_density_audit as audit  # noqa: E402


class ContextDensityAuditResearchGateTests(unittest.TestCase):
    def write_file(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        with tmp:
            tmp.write(text)
        return Path(tmp.name)

    def test_detects_long_context_without_placement_check(self):
        path = self.write_file("# Readme\nThis workflow uses a long context window to handle every instruction reliably.\n")
        risks = audit.scan_context_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertIn("long_context_without_placement_check", {risk["kind"] for risk in risks})

    def test_detects_cache_claim_without_metrics(self):
        path = self.write_file("# Readme\nPrompt caching makes repeated prompts cheaper.\n")
        risks = audit.scan_compression_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertIn("cache_claim_without_metrics", {risk["kind"] for risk in risks})
        gate_risks = audit.research_gate_risks(risks)
        self.assertIn("cache_aware_layout", {risk["gate"] for risk in gate_risks})

    def test_detects_schema_success_without_task_validation(self):
        path = self.write_file("# Readme\nStructured output ensures reliable schema-valid responses for the model answer.\n")
        risks = audit.scan_contract_risks(path, path.read_text(encoding="utf-8"))
        self.assertIn("schema_without_task_validation", {risk["kind"] for risk in risks})
        gate_risks = audit.research_gate_risks(risks)
        self.assertIn("schema_task_validity", {risk["gate"] for risk in gate_risks})

    def test_allows_schema_with_task_validation(self):
        text = (
            "# Readme\n"
            "Structured output uses JSON Schema for model response fields.\n"
            "Task success validation and semantic source support are checked for the consumer.\n"
        )
        path = self.write_file(text)
        risks = audit.scan_contract_risks(path, path.read_text(encoding="utf-8"))
        self.assertNotIn("schema_without_task_validation", {risk["kind"] for risk in risks})

    def test_maps_long_context_risk_to_research_gate(self):
        path = self.write_file("# Readme\nThis workflow uses a long context window to handle every instruction reliably.\n")
        risks = audit.scan_context_risks(path, path.read_text(encoding="utf-8"), "router")
        gate_risks = audit.research_gate_risks(risks)
        gate = next(risk for risk in gate_risks if risk["gate"] == "long_context_placement")
        self.assertIn("task validation", " ".join(gate["required_evidence"]))

    def test_maps_compression_risk_to_research_gate(self):
        path = self.write_file("# Readme\nCompression reduces tokens and makes prompts smaller.\n")
        risks = audit.scan_compression_risks(path, path.read_text(encoding="utf-8"), "router")
        gate_risks = audit.research_gate_risks(risks)
        self.assertIn("compression_break_even", {risk["gate"] for risk in gate_risks})

    def test_detects_context_stuffing(self):
        path = self.write_file("# Readme\nAlways include all files and the entire history in the prompt.\n")
        risks = audit.scan_context_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertIn("context_stuffing", {risk["kind"] for risk in risks})
        gate_risks = audit.research_gate_risks(risks)
        self.assertIn("relevance_distractor_budget", {risk["gate"] for risk in gate_risks})

    def test_allows_packing_with_relevance_criterion(self):
        text = (
            "# Readme\n"
            "Include all files that pass the relevance filter for the current task.\n"
        )
        path = self.write_file(text)
        risks = audit.scan_context_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertNotIn("context_stuffing", {risk["kind"] for risk in risks})

    def test_detects_handoff_without_contract(self):
        path = self.write_file("# Readme\nThe planner hands off context to a subagent that continues the work.\n")
        risks = audit.scan_context_risks(path, path.read_text(encoding="utf-8"), "hot")
        self.assertIn("handoff_without_contract", {risk["kind"] for risk in risks})
        gate_risks = audit.research_gate_risks(risks)
        self.assertIn("multi_agent_handoff", {risk["gate"] for risk in gate_risks})

    def test_allows_handoff_with_typed_contract(self):
        text = (
            "# Readme\n"
            "The planner hands off context to a subagent using a typed contract with evidence refs.\n"
            "The receiver runs verification before acting on the state.\n"
        )
        path = self.write_file(text)
        risks = audit.scan_context_risks(path, path.read_text(encoding="utf-8"), "hot")
        self.assertNotIn("handoff_without_contract", {risk["kind"] for risk in risks})

    def test_detects_format_equivalence_assumption(self):
        path = self.write_file("# Readme\nWe reformatted the prompt to YAML and behavior stays the same.\n")
        risks = audit.scan_compression_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertIn("format_equivalence_assumption", {risk["kind"] for risk in risks})
        gate_risks = audit.research_gate_risks(risks)
        self.assertIn("format_sensitivity", {risk["gate"] for risk in gate_risks})

    def test_allows_format_change_with_validation(self):
        text = (
            "# Readme\n"
            "We reformatted the prompt to YAML and behavior stays the same.\n"
            "A task-level spot check on the consumer validated the rewrite.\n"
        )
        path = self.write_file(text)
        risks = audit.scan_compression_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertNotIn("format_equivalence_assumption", {risk["kind"] for risk in risks})

    def test_oversized_hot_surface_flagged_via_cli(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "SKILL.md"
            path.write_text("word " * 600, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "context_density_audit.py"),
                    str(path),
                    "--hot-token-budget",
                    "100",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        kinds = {risk["kind"] for risk in payload["context_risks"]}
        self.assertIn("oversized_hot_surface", kinds)
        oversized = next(r for r in payload["context_risks"] if r["kind"] == "oversized_hot_surface")
        self.assertEqual(oversized["severity"], "medium")
        gates = {risk["gate"] for risk in payload["research_gate_risks"]}
        self.assertIn("long_context_placement", gates)

    def test_hot_token_budget_zero_disables_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "SKILL.md"
            path.write_text("word " * 600, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "context_density_audit.py"),
                    str(path),
                    "--hot-token-budget",
                    "0",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertNotIn("oversized_hot_surface", {risk["kind"] for risk in payload["context_risks"]})

    def test_research_gate_summary_counts_by_gate(self):
        gate_risks = [
            {"gate": "cache_aware_layout", "severity": "medium", "required_evidence": ["metrics"], "source_basis": ["docs"]},
            {"gate": "cache_aware_layout", "severity": "high", "required_evidence": ["metrics"], "source_basis": ["docs"]},
        ]
        summary = audit.research_gate_summary(gate_risks)
        self.assertEqual(summary[0]["gate"], "cache_aware_layout")
        self.assertEqual(summary[0]["count"], 2)
        self.assertEqual(summary[0]["max_severity"], "high")

    def test_advisory_findings_do_not_block_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "README.md"
            path.write_text("# Readme\nPrompt caching makes repeated prompts cheaper.\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "context_density_audit.py"),
                    str(path),
                    "--fail-on-research-gates",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertIn("cache_aware_layout", {r["gate"] for r in payload["research_gate_risks"]})
        self.assertEqual(payload["research_gate_risks"][0]["evidence_class"], "advisory")

    def test_fail_on_advisory_blocks_wording_findings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "README.md"
            path.write_text("# Readme\nPrompt caching makes repeated prompts cheaper.\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "context_density_audit.py"),
                    str(path),
                    "--fail-on-research-gates",
                    "--fail-on-advisory",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn('"research_gates": true', result.stdout)

    def test_measured_findings_block_without_advisory_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "SKILL.md"
            path.write_text("word " * 600, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "context_density_audit.py"),
                    str(path),
                    "--fail-on-research-gates",
                    "--hot-token-budget",
                    "100",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 2)

    def test_commitment_ledger_passes_when_atom_is_present_in_hot_path(self):
        path = self.write_file("# Skill\nDo not parse generated prose for machine state.\n")
        atoms = [{"atom_id": "no-prose-parse", "text": "Do not parse generated prose", "required": True}]
        validation = audit.validate_commitment_atoms(
            atoms, {str(path): path.read_text(encoding="utf-8")}, {str(path): "hot"}
        )
        self.assertTrue(validation["passed"])
        self.assertEqual(validation["checked"], 1)

    def test_commitment_ledger_fails_when_atom_survives_only_in_cold_path(self):
        path = self.write_file("# Reference\nDo not parse generated prose for machine state.\n")
        atoms = [{"atom_id": "no-prose-parse", "text": "Do not parse generated prose", "required": True}]
        validation = audit.validate_commitment_atoms(
            atoms, {str(path): path.read_text(encoding="utf-8")}, {str(path): "reference"}
        )
        self.assertFalse(validation["passed"])
        failure = validation["missing_required"][0]["failure"]
        self.assertTrue(failure.startswith("outside_required_load_path:"), failure)

    def test_commitment_ledger_load_path_any_restores_corpus_wide_match(self):
        path = self.write_file("# Reference\nDo not parse generated prose for machine state.\n")
        atoms = [{"atom_id": "no-prose-parse", "text": "Do not parse generated prose", "load_path": "any"}]
        validation = audit.validate_commitment_atoms(
            atoms, {str(path): path.read_text(encoding="utf-8")}, {str(path): "reference"}
        )
        self.assertTrue(validation["passed"])

    def test_commitment_ledger_explicit_reference_load_path(self):
        path = self.write_file("# Reference\nRecovery command: rerun the audit.\n")
        atoms = [{"atom_id": "recovery", "text": "Recovery command", "load_path": "reference"}]
        validation = audit.validate_commitment_atoms(
            atoms, {str(path): path.read_text(encoding="utf-8")}, {str(path): "reference"}
        )
        self.assertTrue(validation["passed"])

    def test_compression_moving_commitment_to_reference_exits_three(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "references").mkdir()
            (root / "SKILL.md").write_text("# Skill\nCompact rules only.\n", encoding="utf-8")
            (root / "references" / "old.md").write_text(
                "# Archive\nNever push without explicit approval.\n", encoding="utf-8"
            )
            ledger = root / "atoms.json"
            ledger.write_text(
                json.dumps({"atoms": [{"atom_id": "approval", "text": "Never push without explicit approval"}]}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "context_density_audit.py"),
                    str(root),
                    "--commitment-ledger",
                    str(ledger),
                    "--fail-on-missing-commitments",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 3)
        self.assertIn("outside_required_load_path", result.stdout)

    def test_commitment_ledger_failure_exits_three(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "SKILL.md"
            ledger = Path(tmpdir) / "atoms.json"
            target.write_text("# Skill\nKeep explicit contracts.\n", encoding="utf-8")
            ledger.write_text(
                json.dumps({"atoms": [{"atom_id": "missing", "text": "Preserve this exact sentence."}]}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "context_density_audit.py"),
                    str(target),
                    "--commitment-ledger",
                    str(ledger),
                    "--fail-on-missing-commitments",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 3)
        self.assertIn('"commitments": true', result.stdout)
        self.assertIn('"atom_id": "missing"', result.stdout)

    def test_commitment_ledger_malformed_regex_fails_closed(self):
        path = self.write_file("# Skill\nKeep explicit contracts.\n")
        atoms = [{"atom_id": "bad-regex", "text": "[", "match": "regex"}]
        validation = audit.validate_commitment_atoms(atoms, {str(path): path.read_text(encoding="utf-8")})
        self.assertFalse(validation["passed"])
        self.assertEqual(validation["malformed_atoms"][0]["failure"], "invalid_regex")


DUP_BLOCK = (
    "Always preserve trigger semantics, output contracts, exact commands, safety boundaries, "
    "and validation proof before compressing any wording in a hot skill surface or router file."
)
NEAR_BLOCK_A = (
    "Measure the token cost of every hot surface before editing, record the before and after "
    "numbers, and report the delta with the validation commands used to confirm behavior."
)
NEAR_BLOCK_B = (
    "Measure the token cost of every hot surface before editing, record the before and after "
    "numbers, and publish the delta with the validation commands used to confirm behavior."
)


def write_seeded_corpus(root: Path) -> None:
    """Seeded-defect corpus: duplication across files, oversized hot file, clean control."""
    (root / "references").mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text("directive " * 400, encoding="utf-8")
    (root / "references" / "dup_a.md").write_text(
        f"# A\n\n{DUP_BLOCK}\n\n{NEAR_BLOCK_A}\n\nUnique closing paragraph for file a with enough words to pass the minimum token threshold easily today.\n",
        encoding="utf-8",
    )
    (root / "references" / "dup_b.md").write_text(
        f"# B\n\n{DUP_BLOCK}\n\n{NEAR_BLOCK_B}\n\nCompletely different trailing content here so the files only overlap in the seeded paragraphs above.\n",
        encoding="utf-8",
    )
    (root / "references" / "clean.md").write_text(
        "# Clean\n\nA single distinct explanation paragraph that shares nothing substantial with the other fixture files in this corpus.\n",
        encoding="utf-8",
    )
    legal = (
        "THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, "
        "INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE."
    )
    (root / "LICENSE").write_text(legal + "\n", encoding="utf-8")
    (root / "NOTICE").write_text(legal + "\n", encoding="utf-8")


class DuplicationTests(unittest.TestCase):
    def run_audit(self, root: Path, *extra: str) -> tuple[dict, int]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "context_density_audit.py"), str(root), *extra],
            check=False,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout), result.returncode

    def test_seeded_corpus_golden_findings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_seeded_corpus(root)
            payload, code = self.run_audit(root, "--hot-token-budget", "100")
        self.assertEqual(code, 0)
        summary = payload["duplication_summary"]
        self.assertGreaterEqual(summary["clusters"], 2)
        self.assertGreater(summary["wasted_tokens"], 0)
        matches = {c["match"] for c in payload["duplication_clusters"]}
        self.assertIn("exact", matches)
        self.assertIn("near", matches)
        spanning = [
            c
            for c in payload["duplication_clusters"]
            if len({occ["path"] for occ in c["occurrences"]}) > 1
        ]
        self.assertTrue(spanning, "expected at least one cross-file duplicate cluster")
        kinds = {r["kind"]: r["evidence_class"] for r in payload["context_risks"]}
        self.assertEqual(kinds.get("oversized_hot_surface"), "measured")
        clean_hits = [
            occ
            for c in payload["duplication_clusters"]
            for occ in c["occurrences"]
            if occ["path"].endswith("clean.md")
        ]
        self.assertEqual(clean_hits, [], "clean control file must not appear in duplicate clusters")
        legal_clusters = [
            c
            for c in payload["duplication_clusters"]
            if any(occ["path"].endswith(("LICENSE", "NOTICE")) for occ in c["occurrences"])
        ]
        self.assertTrue(legal_clusters, "expected LICENSE/NOTICE duplicate cluster")
        self.assertIn("legal_text", legal_clusters[0]["caution"])
        near_clusters = [c for c in payload["duplication_clusters"] if c["match"] == "near"]
        self.assertTrue(near_clusters)
        self.assertIn("near_match_diff_before_merge", near_clusters[0]["caution"])

    def test_duplication_budget_blocks_with_exit_four(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_seeded_corpus(root)
            payload, code = self.run_audit(root, "--max-duplication-tokens", "1")
        self.assertEqual(code, 4)
        self.assertTrue(payload["blocking"]["duplication"])

    def test_duplication_disabled_with_zero_min_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_seeded_corpus(root)
            payload, code = self.run_audit(root, "--duplication-min-tokens", "0")
        self.assertEqual(code, 0)
        self.assertEqual(payload["duplication_summary"]["clusters"], 0)


class SuppressionAndExcerptTests(unittest.TestCase):
    def write_file(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        with tmp:
            tmp.write(text)
        return Path(tmp.name)

    def test_cda_allow_suppresses_advisory_on_same_line(self):
        path = self.write_file(
            "# Readme\nPrompt caching makes repeated prompts cheaper. <!-- cda:allow cache_claim_without_metrics -->\n"
        )
        risks = audit.scan_compression_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertNotIn("cache_claim_without_metrics", {r["kind"] for r in risks})

    def test_cda_allow_on_previous_line_suppresses(self):
        path = self.write_file(
            "# Readme\n<!-- cda:allow cache_claim_without_metrics -->\nPrompt caching makes repeated prompts cheaper.\n"
        )
        risks = audit.scan_compression_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertNotIn("cache_claim_without_metrics", {r["kind"] for r in risks})

    def test_cda_allow_other_kind_does_not_suppress(self):
        path = self.write_file(
            "# Readme\nPrompt caching makes repeated prompts cheaper. <!-- cda:allow token_only_metric -->\n"
        )
        risks = audit.scan_compression_risks(path, path.read_text(encoding="utf-8"), "router")
        self.assertIn("cache_claim_without_metrics", {r["kind"] for r in risks})

    def test_no_excerpts_blanks_quoted_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "README.md"
            path.write_text("# Readme\nPrompt caching makes repeated prompts cheaper.\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / "context_density_audit.py"), str(path), "--no-excerpts"],
                check=False,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        risks = payload["compression_risks"] + payload["research_gate_risks"]
        self.assertTrue(risks)
        self.assertTrue(all(r.get("excerpt", "") == "" for r in risks))


class LoadPathMapTests(unittest.TestCase):
    def test_map_overrides_heuristic(self):
        load_map = {"hot": ["custom/*.md"], "router": [], "reference": [], "evidence": []}
        self.assertEqual(audit.classify_load_path(Path("repo/custom/rules.md"), load_map), "hot")
        self.assertEqual(audit.classify_load_path(Path("repo/other/notes.md"), load_map), "unknown")

    def test_map_precedence_hot_wins(self):
        load_map = {"hot": ["*.md"], "router": ["*.md"], "reference": [], "evidence": []}
        self.assertEqual(audit.classify_load_path(Path("anything.md"), load_map), "hot")


class GateChecklistTests(unittest.TestCase):
    def test_emit_gate_checklist_writes_fillable_form(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "README.md"
            source.write_text("# Readme\nPrompt caching makes repeated prompts cheaper.\n", encoding="utf-8")
            checklist = Path(tmpdir) / "checklist.md"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "context_density_audit.py"),
                    str(source),
                    "--emit-gate-checklist",
                    str(checklist),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            content = checklist.read_text(encoding="utf-8")
        self.assertIn("cache_aware_layout", content)
        self.assertIn("- [ ]", content)
        self.assertIn("evidence:", content)


if __name__ == "__main__":
    unittest.main()
