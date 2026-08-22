from __future__ import annotations

import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class ToolOutputProjectionContractTests(unittest.TestCase):
    def _reference(self) -> str:
        return (
            PLUGIN_ROOT / "skills/context-density/references/tool-output-projection.md"
        ).read_text(encoding="utf-8")

    def _flat_reference(self) -> str:
        return " ".join(self._reference().split())

    def test_skill_routes_to_projection_reference(self) -> None:
        skill = (PLUGIN_ROOT / "skills/context-density/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("references/tool-output-projection.md", skill)

    def test_projection_routes_risky_evidence_to_raw(self) -> None:
        reference = self._flat_reference()
        for phrase in (
            "A deterministic caller or harness, not an LLM",
            "Git porcelain/diff surface",
            "executed-versus-planned effect",
            "future questions are unknown",
            "mode=keep_raw",
            "raw_id=<raw-id>",
            "the marker itself is not evidence",
            "Reject a missing or mismatched raw identity",
        ):
            self.assertIn(phrase, reference)

    def test_projection_preserves_claim_level_atoms(self) -> None:
        reference = self._flat_reference()
        for phrase in (
            "group only exact duplicate records",
            "never cap or drop unique records",
            "retained count plus omitted count",
            "both old and new paths",
            "claim-level atoms",
            "negative evidence",
            "alternative branches",
            "original causal sequence",
        ):
            self.assertIn(phrase, reference)

    def test_recovery_privacy_and_cost_fail_closed(self) -> None:
        reference = self._flat_reference()
        for phrase in (
            "content digest",
            "Validate the resolver before discarding raw context",
            "at most one bounded recovery request",
            "Fail closed on a dangling pointer",
            "Redact secrets before model visibility",
            "not a privacy boundary",
            "cumulative provider tokens",
            "not an end-to-end efficiency win",
        ):
            self.assertIn(phrase, reference)

    def test_reference_does_not_overclaim_llm_determinism(self) -> None:
        reference = self._reference()
        self.assertNotIn("# Deterministic Tool-Output Projection", reference)
        self.assertIn("implements only contiguous exact-line", reference)
        self.assertIn("does not implement a raw-output resolver", reference)

    def test_presentation_brevity_does_not_replace_persistence(self) -> None:
        skill = (PLUGIN_ROOT / "skills/context-density/SKILL.md").read_text(encoding="utf-8")
        reference = self._flat_reference()

        for phrase in (
            "presentation policy only",
            "model reasoning or output allowances",
            "durable typed task state",
            "Silence is not a persistence strategy",
            "visible response and the persistent task record",
        ):
            self.assertIn(phrase, f"{skill} {reference}")

    def test_capsule_and_recovery_cover_success_and_failure(self) -> None:
        reference = self._flat_reference()
        for phrase in (
            "completed actions with receipts and effect state",
            "rejected branches with reasons and negative evidence",
            "separate source references and raw-recovery references",
            "successful and failed outputs",
            "successful observations can explain later state",
            "raw_recovery_required=true",
        ):
            self.assertIn(phrase, reference)

    def test_repeated_compaction_is_an_adoption_gate(self) -> None:
        reference = self._flat_reference()
        for phrase in (
            "Repeated-compaction adoption gate",
            "full history and after multiple dependent compaction",
            "source-reference recall",
            "false-atom introduction",
            "repeated completed work",
            "candidate-only full-trajectory loss",
            "complete pipeline",
        ):
            self.assertIn(phrase, reference)


if __name__ == "__main__":
    unittest.main()
