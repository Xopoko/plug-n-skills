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

    def test_fail_on_research_gates_exits_nonzero(self):
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
        self.assertEqual(result.returncode, 2)
        self.assertIn('"research_gates": true', result.stdout)

    def test_commitment_ledger_passes_when_atom_is_present(self):
        path = self.write_file("# Skill\nDo not parse generated prose for machine state.\n")
        atoms = [{"atom_id": "no-prose-parse", "text": "Do not parse generated prose", "required": True}]
        validation = audit.validate_commitment_atoms(atoms, {str(path): path.read_text(encoding="utf-8")})
        self.assertTrue(validation["passed"])
        self.assertEqual(validation["checked"], 1)

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


if __name__ == "__main__":
    unittest.main()
