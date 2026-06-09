from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = load_module(ROOT / "scripts" / "architecture_probe.py", "architecture_probe")
validator = load_module(
    ROOT / "scripts" / "validate_architecture_intelligence.py",
    "validate_architecture_intelligence",
)


class ArchitectureProbeTest(unittest.TestCase):
    def test_probe_collects_basic_architecture_facts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "docs" / "adr").mkdir(parents=True)
            (root / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
            (root / "src" / "app.py").write_text("from src.domain import thing\n", encoding="utf-8")
            (root / "tests" / "test_app.py").write_text("def test_ok(): pass\n", encoding="utf-8")
            (root / "docs" / "adr" / "0001-boundary.md").write_text("# ADR\n", encoding="utf-8")

            report = probe.summarize(root, max_files=100)

        self.assertEqual(report["schema"], "architecture_intelligence.probe.v1")
        self.assertIn({"language": "python", "files": 2}, report["languages"])
        self.assertIn("package.json", report["manifests"])
        self.assertIn("docs/adr/0001-boundary.md", report["architecture_documents"])
        self.assertIn("tests/test_app.py", report["test_surfaces"])

    def test_probe_ignores_swiftpm_build_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "Sources" / "App").mkdir(parents=True)
            (root / ".build" / "checkouts" / "Dependency").mkdir(parents=True)
            (root / "Package.swift").write_text("// swift-tools-version: 6.0\n", encoding="utf-8")
            (root / "Sources" / "App" / "App.swift").write_text("import Foundation\n", encoding="utf-8")
            (root / ".build" / "checkouts" / "Dependency" / "Generated.swift").write_text(
                "import Foundation\n",
                encoding="utf-8",
            )

            report = probe.summarize(root, max_files=100)

        self.assertEqual(report["file_count"], 2)
        self.assertIn({"language": "swift", "files": 2}, report["languages"])
        self.assertEqual(report["top_level_directories"], [{"path": "Sources", "files": 1}])

    def test_probe_checks_architecture_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "domain").mkdir()
            (root / "infrastructure").mkdir()
            (root / "domain" / "model.py").write_text(
                "from infrastructure.db import save\n",
                encoding="utf-8",
            )
            (root / "infrastructure" / "db.py").write_text("def save(): pass\n", encoding="utf-8")
            policy = {
                "schema": "architecture_intelligence.policy.v1",
                "forbidden_edges": [{
                    "from": "domain",
                    "to": "infrastructure",
                    "reason": "domain must not depend on infrastructure"
                }],
                "required_documents": ["docs/architecture.md"]
            }

            report = probe.summarize(root, max_files=100, policy=policy)

        self.assertEqual(report["policy_checks"]["summary"]["fail"], 2)
        self.assertIn(
            "architecture-policy-failed",
            {risk["id"] for risk in report["risks"]},
        )

    def test_probe_collects_structure_metrics_and_cycles(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ("app", "domain", "infrastructure"):
                (root / directory).mkdir()
            (root / "app" / "main.py").write_text("from domain.service import run\n", encoding="utf-8")
            (root / "domain" / "service.py").write_text("from infrastructure.db import save\n", encoding="utf-8")
            (root / "infrastructure" / "db.py").write_text("from domain.service import run\n", encoding="utf-8")

            report = probe.summarize(root, max_files=100)

        metrics = report["structure_metrics"]
        self.assertEqual(metrics["summary"]["cycle_count"], 1)
        self.assertIn(
            {"path": ["domain", "infrastructure", "domain"], "length": 2, "evidence": "top-level static import cycle"},
            metrics["cycles"],
        )
        domain = next(item for item in metrics["components"] if item["name"] == "domain")
        self.assertEqual(domain["afferent_coupling"], 2)
        self.assertEqual(domain["efferent_coupling"], 1)
        self.assertAlmostEqual(domain["instability"], 0.333)

    def test_probe_collects_runtime_topology_signals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app").mkdir()
            (root / "config").mkdir()
            (root / "Dockerfile").write_text("FROM python:3.12\nHEALTHCHECK CMD true\n", encoding="utf-8")
            (root / "docker-compose.yml").write_text("services:\n  web:\n    image: demo\n", encoding="utf-8")
            (root / "config" / "settings.yaml").write_text("timeout_ms: 1000\nretry_policy: simple\n", encoding="utf-8")
            (root / "app" / "main.py").write_text(
                "import requests\nfrom opentelemetry import trace\nlogger.info('ready')\n",
                encoding="utf-8",
            )

            report = probe.summarize(root, max_files=100)

        runtime = report["runtime_topology"]
        self.assertEqual(runtime["schema"], "architecture_intelligence.runtime_topology.v1")
        self.assertGreaterEqual(runtime["summary"]["deployment_artifacts"], 2)
        self.assertGreaterEqual(runtime["summary"]["observability_signals"], 1)
        self.assertGreaterEqual(runtime["summary"]["resilience_signals"], 1)
        self.assertGreaterEqual(runtime["summary"]["integration_signals"], 1)
        surface_names = {surface["name"] for surface in runtime["surfaces"]}
        self.assertIn("container", surface_names)
        self.assertIn("container-compose", surface_names)

    def test_probe_collects_ownership_topology_signals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ("api", "web"):
                (root / directory).mkdir()
            (root / ".github").mkdir()
            (root / ".github" / "CODEOWNERS").write_text(
                "/api/ @backend\n/web/ @frontend\n",
                encoding="utf-8",
            )
            (root / "api" / "service.py").write_text("def load(): pass\n", encoding="utf-8")
            (root / "web" / "view.py").write_text("from api.service import load\n", encoding="utf-8")

            report = probe.summarize(root, max_files=100)

        ownership = report["ownership_topology"]
        self.assertEqual(ownership["schema"], "architecture_intelligence.ownership_topology.v1")
        self.assertEqual(ownership["summary"]["ownership_sources"], 1)
        self.assertEqual(ownership["summary"]["owned_areas"], 2)
        self.assertEqual(ownership["summary"]["cross_owned_edges"], 1)
        web_area = next(item for item in ownership["areas"] if item["path"] == "web")
        self.assertEqual(web_area["owners"], ["@frontend"])
        self.assertIn(
            "cross-owned-web-to-api",
            {risk["id"] for risk in ownership["coordination_risks"]},
        )


class ArchitectureValidatorTest(unittest.TestCase):
    def validate_payload(self, payload):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(payload, handle)
            path = Path(handle.name)
        try:
            validator.validate(path)
        finally:
            path.unlink(missing_ok=True)

    def test_validates_audit_contract(self):
        self.validate_payload({
            "schema": "architecture_intelligence.audit.v1",
            "target": "demo",
            "summary": "Boundaries are visible but not enforced.",
            "context": {
                "system_boundary": "demo repo",
                "quality_attributes": ["modifiability"],
                "evidence": ["src imports"],
                "scenarios": [{
                    "scenario": "move domain behavior",
                    "stimulus": "developer changes domain service",
                    "environment": "maintenance",
                    "response": "domain remains isolated from adapters",
                    "response_measure": "no adapter imports from domain",
                    "quality_attribute": "modifiability"
                }],
                "assumptions": [],
                "unknowns": []
            },
            "findings": [{
                "id": "dependency-direction",
                "severity": "P2",
                "lens": "dependency-direction",
                "evidence": "src imports adapter directly",
                "debt_type": "smell",
                "propagation_risk": "medium",
                "reversibility": "moderate",
                "business_impact": "feature work touches infrastructure files",
                "impact": "domain changes can leak into infrastructure",
                "recommendation": "introduce a port boundary",
                "validation": "add import-linter rule",
                "confidence": "medium"
            }],
            "quality_gates": {
                "modifiability": "risk",
                "reliability": "unknown",
                "security": "unknown",
                "operability": "unknown",
                "testability": "risk"
            },
            "next_actions": ["add architecture test"]
        })

    def test_validates_decision_contract(self):
        self.validate_payload({
            "schema": "architecture_intelligence.decision.v1",
            "decision_id": "module-boundary",
            "title": "Introduce module boundary",
            "status": "accepted",
            "decision_type": "module-boundary",
            "context": {
                "problem": "domain imports infrastructure",
                "forces": ["modifiability"],
                "evidence": [{"source": "src", "claim": "import edge exists", "strength": "medium"}],
                "assumptions": []
            },
            "options_considered": [{"option": "port", "pros": ["clear seam"], "cons": ["more files"]}],
            "decision": "add a port boundary",
            "rationale": "it reduces change amplification",
            "rationale_quality": {
                "alternatives_complete": "pass",
                "tradeoffs_named": "pass",
                "evidence_strength": "medium",
                "knowledge_vaporization_risk": "low"
            },
            "consequences": ["one adapter layer is added"],
            "fitness_functions": ["dependency rule in CI"],
            "owner_or_review_path": "architecture review",
            "expires_or_revisit_trigger": "when the domain split changes"
        })

    def test_validates_conformance_contract(self):
        self.validate_payload({
            "schema": "architecture_intelligence.conformance.v1",
            "target": "demo",
            "intended_model_source": "docs/architecture.md",
            "observed_model_source": "architecture_probe.py --policy",
            "mappings": [{
                "source": "domain",
                "target": "infrastructure",
                "intended_relation": "forbidden",
                "observed_relation": "present",
                "classification": "divergence",
                "evidence": "domain/model.py imports infrastructure.db"
            }],
            "findings": [{
                "id": "domain-imports-infrastructure",
                "severity": "P1",
                "classification": "divergence",
                "evidence": "policy check failed",
                "impact": "domain changes are coupled to persistence choices",
                "recommendation": "introduce an interface owned by domain",
                "validation": "forbidden dependency rule passes",
                "confidence": "high"
            }],
            "drift_summary": {
                "convergences": 0,
                "divergences": 1,
                "absences": 0,
                "unknowns": 0
            },
            "next_actions": ["replace direct import with a port"]
        })

    def test_validates_fitness_plan_contract(self):
        self.validate_payload({
            "schema": "architecture_intelligence.fitness_plan.v1",
            "target": "demo",
            "architecture_principle": "domain does not import adapters",
            "rules": [{
                "id": "domain-import-rule",
                "intent": "protect domain boundary",
                "scope": "src/domain",
                "quality_attribute": "modifiability",
                "tradeoff": "more explicit interfaces",
                "signal": "import graph",
                "mechanism": "import-linter",
                "pass_condition": "no adapter imports",
                "cadence": "ci",
                "owner": "architecture review",
                "failure_action": "block merge or record exception"
            }],
            "rollout": {
                "mode": "warn",
                "migration_notes": ["measure current violations first"]
            }
        })

    def test_validates_refactor_report_contract(self):
        self.validate_payload({
            "schema": "architecture_intelligence.refactor_report.v1",
            "target": "demo",
            "summary": "Core now owns snapshot enrichment and the UI only coordinates presentation.",
            "route": {
                "skills_used": [
                    "codebase-architecture-audit",
                    "architecture-refactoring-strategy",
                    "architecture-fitness-functions"
                ],
                "skipped_skills": [{
                    "skill": "architecture-ownership-topology",
                    "reason": "no ownership files or owner boundaries were present"
                }],
                "source_evidence": ["architecture_probe.py --json", "Sources/Core"]
            },
            "before": {
                "dirty_tree_state": "dirty",
                "baseline_evidence": ["git status --short", "pre-probe.json"],
                "architecture_risks": ["UI store duplicated core snapshot enrichment"],
                "pre_probe": "python3 scripts/architecture_probe.py . --json"
            },
            "refactor": {
                "target_boundary": "Core owns snapshot enrichment; UI consumes core results.",
                "quality_attributes": ["modifiability", "testability"],
                "slices": [{
                    "id": "extract-snapshot-enrichment",
                    "intent": "Move enrichment logic into core.",
                    "files_changed": ["Sources/Core/SnapshotUsageEnricher.swift"],
                    "behavior_preserving": True,
                    "validation": ["swift test"],
                    "rollback": "revert the extraction slice"
                }]
            },
            "proof": {
                "tests": ["swift test"],
                "fitness_functions": ["core boundary tests"],
                "docs_updated": ["docs/ARCHITECTURE.md"],
                "post_probe": "python3 scripts/architecture_probe.py . --json",
                "runtime_verification": "release audit passed"
            },
            "residual_risks": [{
                "id": "dirty-tree-review-risk",
                "severity": "P2",
                "evidence": "pre-existing UI changes were present",
                "mitigation": "review architecture-owned files separately"
            }],
            "next_actions": ["add CI architecture policy"]
        })

    def test_validates_structure_metrics_contract(self):
        self.validate_payload({
            "schema": "architecture_intelligence.structure_metrics.v1",
            "target": "demo",
            "observed_model_source": "architecture_probe.py static import graph",
            "components": [{
                "name": "domain",
                "afferent_coupling": 2,
                "efferent_coupling": 1,
                "incoming_edges": 2,
                "outgoing_edges": 1,
                "instability": 0.333,
                "stability_role": "balanced",
                "evidence": "top-level static imports"
            }],
            "cycles": [{
                "path": ["domain", "infrastructure", "domain"],
                "length": 2,
                "evidence": "top-level static import cycle"
            }],
            "summary": {
                "component_count": 1,
                "internal_edge_count": 3,
                "cycle_count": 1,
                "max_efferent_coupling": 1,
                "max_afferent_coupling": 2
            },
            "interpretation": {
                "summary": "Metrics are warning signals for architecture review.",
                "limitations": "Static import metrics miss runtime calls and ownership."
            },
            "next_actions": ["inspect cycle against intended architecture"]
        })

    def test_validates_runtime_topology_contract(self):
        self.validate_payload({
            "schema": "architecture_intelligence.runtime_topology.v1",
            "target": "demo",
            "observed_model_source": "architecture_probe.py repository file and signal scan",
            "surfaces": [{
                "type": "deployment",
                "name": "container",
                "evidence": ["Dockerfile"],
                "confidence": "medium"
            }, {
                "type": "observability",
                "name": "opentelemetry",
                "evidence": ["app/main.py"],
                "confidence": "low"
            }],
            "topology_hypotheses": [{
                "id": "runtime-integration-present",
                "claim": "Runtime integrations may define architecture coupling.",
                "evidence": "app/main.py",
                "confidence": "low",
                "validation": "Trace representative runtime calls."
            }],
            "quality_attribute_gaps": [{
                "attribute": "availability",
                "signal": "no circuit breaker detected",
                "risk": "unknown"
            }],
            "summary": {
                "deployment_artifacts": 1,
                "runtime_config_files": 0,
                "observability_signals": 1,
                "resilience_signals": 0,
                "integration_signals": 1
            },
            "limitations": ["Signals do not prove runtime behavior."],
            "next_actions": ["Map deployment artifacts to runtime components."]
        })

    def test_validates_ownership_topology_contract(self):
        self.validate_payload({
            "schema": "architecture_intelligence.ownership_topology.v1",
            "target": "demo",
            "observed_model_source": "architecture_probe.py ownership document, static import, and runtime-surface scan",
            "ownership_sources": [{
                "path": ".github/CODEOWNERS",
                "type": "codeowners",
                "evidence": "ownership or governance document detected",
                "confidence": "medium"
            }],
            "areas": [{
                "path": "web",
                "owners": ["@frontend"],
                "evidence": [".github/CODEOWNERS:2 /web/"],
                "coverage": "owned"
            }, {
                "path": "api",
                "owners": ["@backend"],
                "evidence": [".github/CODEOWNERS:1 /api/"],
                "coverage": "owned"
            }],
            "coordination_risks": [{
                "id": "cross-owned-web-to-api",
                "severity": "P2",
                "evidence": "web -> api static import edge count 1",
                "impact": "Architecture changes may need coordination.",
                "recommendation": "Require review from both owner paths for architecture-changing work.",
                "confidence": "medium"
            }],
            "summary": {
                "ownership_sources": 1,
                "owned_areas": 2,
                "unowned_areas": 0,
                "cross_owned_edges": 1,
                "ownerless_runtime_or_code_surfaces": 0
            },
            "limitations": ["Ownership files can be stale."],
            "next_actions": ["Review cross-owned dependency edges."]
        })

    def test_probe_collects_git_history_when_requested(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            if subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
                self.skipTest("git is not available")
            subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            (root / "src").mkdir()
            (root / "docs").mkdir()
            (root / "src" / "app.py").write_text("print('one')\n", encoding="utf-8")
            (root / "docs" / "adr.md").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=root, check=True, stdout=subprocess.DEVNULL)
            (root / "src" / "app.py").write_text("print('two')\n", encoding="utf-8")
            (root / "docs" / "adr.md").write_text("two\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "change together"], cwd=root, check=True, stdout=subprocess.DEVNULL)

            report = probe.summarize(root, max_files=100, include_git_history=True)

        self.assertTrue(report["git_history"]["available"])
        self.assertGreaterEqual(report["git_history"]["commit_count"], 2)
        self.assertIn(
            {"left": "docs", "right": "src", "count": 2},
            report["git_history"]["cochange_pairs"],
        )


if __name__ == "__main__":
    unittest.main()
