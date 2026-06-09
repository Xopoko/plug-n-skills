import sys
import tempfile
import unittest
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

    def test_detects_schema_success_without_task_validation(self):
        path = self.write_file("# Readme\nStructured output ensures reliable schema-valid responses for the model answer.\n")
        risks = audit.scan_contract_risks(path, path.read_text(encoding="utf-8"))
        self.assertIn("schema_without_task_validation", {risk["kind"] for risk in risks})

    def test_allows_schema_with_task_validation(self):
        text = (
            "# Readme\n"
            "Structured output uses JSON Schema for model response fields.\n"
            "Task success validation and semantic source support are checked for the consumer.\n"
        )
        path = self.write_file(text)
        risks = audit.scan_contract_risks(path, path.read_text(encoding="utf-8"))
        self.assertNotIn("schema_without_task_validation", {risk["kind"] for risk in risks})


if __name__ == "__main__":
    unittest.main()
