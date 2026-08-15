from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def normalized(relative: str) -> str:
    return " ".join(read(relative).lower().split())


class ProportionalHarnessContractTests(unittest.TestCase):
    def test_artifacts_are_conditional_and_consumer_driven(self) -> None:
        engineering = normalized("skills/agent-harness-engineering/SKILL.md")
        evaluation = normalized("skills/agent-harness-evaluation/SKILL.md")
        contracts = normalized("references/agent-harness-contracts.md")

        self.assertRegex(
            engineering,
            r"new harness.*material control-plane\s+revision.*durable release or handoff",
        )
        self.assertIn("a bounded diagnosis, fix", contracts)
        self.assertIn("inline checklist and direct tests", contracts)
        self.assertIn("repeated campaign, release gate, or durable", evaluation)
        self.assertIn("bounded incident or sampled ablation inline", evaluation)
        self.assertIn("named downstream consumer", contracts)
        self.assertRegex(contracts, r"`created`.*`adopted`.*`executed`.*`accepted`")

        for relative in (
            "skills/agent-harness/agents/openai.yaml",
            "skills/agent-harness-engineering/agents/openai.yaml",
            "skills/agent-harness-evaluation/agents/openai.yaml",
        ):
            with self.subTest(metadata=relative):
                self.assertIn("consumer", read(relative).lower())

    def test_user_outcome_latches_terminal_success(self) -> None:
        router = normalized("skills/agent-harness/SKILL.md")
        contracts = normalized("references/agent-harness-contracts.md")
        combined = router + contracts

        self.assertIn("requested user outcome separate from harness tax", combined)
        self.assertIn("externally verifiable requested outcome", combined)
        self.assertIn("named unresolved risk threatens", combined)
        self.assertIn("requires renewed scope", combined)
        self.assertIn("always-on observer", combined)

    def test_trigger_metadata_does_not_hide_activation_inside_other_work(self) -> None:
        surfaces = [
            *sorted((ROOT / "skills").glob("*/SKILL.md")),
            *sorted((ROOT / "skills").glob("*/agents/openai.yaml")),
        ]
        self.assertTrue(surfaces)
        for surface in surfaces:
            with self.subTest(surface=surface.relative_to(ROOT).as_posix()):
                self.assertNotIn("even if buried", surface.read_text(encoding="utf-8"))

    def test_evaluation_is_sampled_first_with_direct_inline_fallback(self) -> None:
        skill = normalized("skills/agent-harness-evaluation/SKILL.md")
        reference = normalized("references/agent-harness-evaluation.md")

        self.assertIn("work sampled-first", skill)
        self.assertIn("cheapest representative scenario slice", reference)
        self.assertIn("direct oracle", reference)
        self.assertIn("bounded incident or sampled ablation inline", skill)

    def test_async_delegation_and_audit_costs_are_bounded(self) -> None:
        contracts = normalized("references/agent-harness-contracts.md")
        patterns = normalized("references/agent-harness-patterns.md")
        evaluation = normalized("references/agent-harness-evaluation.md")

        self.assertRegex(contracts, r"validation receipt.*after every artifact")
        self.assertRegex(contracts, r"receipt.*excluded from the hash\s+universe")
        self.assertIn("producer-owned completion path", patterns)
        self.assertIn("deferred completion", patterns)
        self.assertIn("unchanged status must not re-enter the model", patterns)
        self.assertIn("2-3 sibling scouts", patterns)
        self.assertIn("prohibit descendants", patterns)
        self.assertIn("exactly one parent-owned point", patterns)
        self.assertIn("duplicate status polls are leads", evaluation)
        self.assertIn("deduplicate mirrored records", evaluation)
        self.assertIn("not unique tokens", evaluation)
        self.assertIn("not billed-token evidence", evaluation)
        self.assertIn("audits are event-triggered only", patterns)

    def test_supervisor_and_updater_adjacent_routes_stay_narrow(self) -> None:
        supervisor = normalized("skills/codex-thread-supervisor/SKILL.md")
        doctor = normalized("skills/codex-doctor-debugger/SKILL.md")
        router = normalized("skills/codex-cli/SKILL.md")
        fixture = json.loads(read("tests/fixtures/router-trigger-cases.json"))

        self.assertIn("only when the user explicitly asks to monitor or supervise", supervisor)
        self.assertIn("multiple targets or a compaction alone do not require", supervisor)
        self.assertNotIn("## mine durable capabilities", supervisor)
        self.assertNotIn("capability mining", supervisor)
        self.assertNotIn("capability changes produced", supervisor)

        for surface in (doctor, router):
            self.assertIn("if codex starts normally", surface)
            self.assertIn("update-channel eligibility", surface)
            self.assertIn("scheduled-automation-runtime", surface)
        self.assertIn("updater that owns channel selection", doctor)
        self.assertIn("do not route", router)

        routed = {case["id"]: case for case in fixture["should_route"]}
        self.assertEqual(
            "scheduled-automation-runtime",
            routed["codex-custom-updater-proof"]["expected_leaf"],
        )


if __name__ == "__main__":
    unittest.main()
