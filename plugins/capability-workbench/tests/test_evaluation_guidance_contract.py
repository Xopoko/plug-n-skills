from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ROOT = PLUGIN_ROOT.parents[1]
VALIDATOR_PATH = (
    PLUGIN_ROOT / "scripts/evaluation/validate_capability_evaluation.py"
)
SPEC = importlib.util.spec_from_file_location("capability_evaluation_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def persistence_plan() -> dict:
    record = copy.deepcopy(VALIDATOR.TEMPLATE)
    record["scope"]["dimensions"] = ["task-outcome", "constraints", "overhead"]
    trajectory_assertions = [
        "full-history-task-success",
        "after-boundary-1",
        "after-boundary-2",
    ]
    facets = sorted(VALIDATOR.PERSISTENCE_FACETS)
    record["cases"] = [
        {
            "id": "trajectory",
            "category": "edge",
            "critical": True,
            "prompt_sha256": "f" * 64,
            "repetitions": 5,
            "assertions": [
                {
                    "id": assertion_id,
                    "type": "deterministic",
                    "criterion": f"Check {assertion_id}.",
                }
                for assertion_id in trajectory_assertions
                + [f"facet-{facet}" for facet in facets]
            ],
        }
    ]
    record["scope"]["persistence_coverage"] = {
        "applicable": True,
        "trajectories": [
            {
                "id": "dependent-task",
                "full_history_control": {
                    "case_id": "trajectory",
                    "assertion_id": "full-history-task-success",
                },
                "dependent_boundaries": [
                    {"case_id": "trajectory", "assertion_id": "after-boundary-1"},
                    {"case_id": "trajectory", "assertion_id": "after-boundary-2"},
                ],
            }
        ],
        "facet_assertions": [
            {
                "facet": facet,
                "case_id": "trajectory",
                "assertion_id": f"facet-{facet}",
            }
            for facet in facets
        ],
    }
    return record


class EvaluationGuidanceContractTests(unittest.TestCase):
    def test_candidate_visible_content_is_blinded(self) -> None:
        skill = (PLUGIN_ROOT / "skills/capability-evaluation/SKILL.md").read_text(encoding="utf-8")
        reference = (PLUGIN_ROOT / "references/capability-evaluation.md").read_text(encoding="utf-8")

        for text in (skill, reference):
            self.assertIn("candidate-visible", text)
            self.assertIn("artifact-path", text)
            self.assertIn("Counterbalance", text)

        self.assertIn("anonymized arms", reference)
        self.assertIn("self-report", reference)

    def test_persistent_context_candidates_require_trajectory_proof(self) -> None:
        skill = (PLUGIN_ROOT / "skills/capability-evaluation/SKILL.md").read_text(encoding="utf-8")
        reference = (PLUGIN_ROOT / "references/capability-evaluation.md").read_text(encoding="utf-8")
        flat_reference = " ".join(reference.split())

        for phrase in (
            "full-history control",
            "repeated dependent",
            "complete-pipeline cost",
        ):
            self.assertIn(phrase, skill)

        for phrase in (
            "presentation brevity separately from evidence persistence",
            "repeated compactions",
            "source/recovery references",
            "successful and failed outputs",
            "complete pipeline",
            "candidate-only full-trajectory loss",
        ):
            self.assertIn(phrase, flat_reference)

        self.assertIn("scope.persistence_coverage.applicable=true", skill)
        self.assertIn("omission is accepted only for legacy v1 compatibility", flat_reference)

    def test_structured_persistence_coverage_validates(self) -> None:
        self.assertEqual(VALIDATOR.validate(persistence_plan()), [])

    def test_legacy_receipt_without_coverage_remains_valid_but_unclaimed(self) -> None:
        record = copy.deepcopy(VALIDATOR.TEMPLATE)
        del record["scope"]["persistence_coverage"]
        self.assertEqual(VALIDATOR.validate(record), [])

    def test_persistence_coverage_fails_closed(self) -> None:
        mutations = {}

        missing_facet = persistence_plan()
        missing_facet["scope"]["persistence_coverage"]["facet_assertions"].pop()
        mutations["missing facet"] = missing_facet

        one_boundary = persistence_plan()
        one_boundary["scope"]["persistence_coverage"]["trajectories"][0][
            "dependent_boundaries"
        ].pop()
        mutations["one boundary"] = one_boundary

        unknown_ref = persistence_plan()
        unknown_ref["scope"]["persistence_coverage"]["facet_assertions"][0][
            "assertion_id"
        ] = "missing"
        mutations["unknown assertion"] = unknown_ref

        human_assertion = persistence_plan()
        human_assertion["cases"][0]["assertions"][-1]["type"] = "human"
        mutations["nondeterministic assertion"] = human_assertion

        noncritical = persistence_plan()
        noncritical["cases"][0]["critical"] = False
        mutations["noncritical trajectory"] = noncritical

        for label, record in mutations.items():
            with self.subTest(label=label):
                self.assertTrue(VALIDATOR.validate(record))

    def test_tracked_capability_evaluation_receipts_validate(self) -> None:
        expected = {
            "2026-08-21-tool-output-projection.json": ("complete", "revise"),
            "2026-08-22-deterministic-projection-policy.json": (
                "blocked",
                "inconclusive",
            ),
        }
        evaluation_dir = ROOT / "docs/capability-evaluations"
        for name, (status, verdict) in expected.items():
            with self.subTest(name=name):
                record = VALIDATOR.load_strict_json(evaluation_dir / name)
                self.assertEqual(VALIDATOR.validate(record), [])
                self.assertEqual(record["status"], status)
                self.assertEqual(record["verdict"], verdict)


if __name__ == "__main__":
    unittest.main()
