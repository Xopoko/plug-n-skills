from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_SKILL = ROOT / "skills" / "kmp-data-layer" / "SKILL.md"
DATA_REFERENCE = ROOT / "references" / "data-layer-readiness.md"
TEST_SKILL = ROOT / "skills" / "kmp-testing-quality" / "SKILL.md"
ROUTER = ROOT / "skills" / "kotlin-multiplatform" / "SKILL.md"


class AsyncStateAdapterTest(unittest.TestCase):
    def test_frontmatter_routes_shared_cancellation_races(self):
        text = DATA_SKILL.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1].lower()

        for route_signal in (
            "shared/coalesced work",
            "cancellation and admission races",
            "causal receipts",
        ):
            self.assertIn(route_signal, frontmatter)

    def test_data_layer_is_standalone_safe(self):
        text = DATA_SKILL.read_text(encoding="utf-8")
        compact = " ".join(text.split())
        lower = compact.lower()
        for route_signal in ("`async-state-consistency`", "available", "standalone"):
            self.assertIn(route_signal, lower)
        self.assertIn("references/data-layer-readiness.md", lower)
        self.assertTrue(DATA_REFERENCE.is_file())
        for forbidden_dependency in (
            "../architecture-intelligence",
            "plugins/architecture-intelligence",
            "references/async-state-consistency.md",
            "$architecture_plugin_root",
        ):
            self.assertNotIn(forbidden_dependency, lower)
        for invariant in (
            "unknown is not",
            "elapsed time alone does not emit",
            "global and keyed/domain generations",
            "latest-start-wins",
            "latest-success-wins",
            "reserved publication sequence",
            "committed publication authority",
            "ordinary publication must not emit `invalidated`",
            "replay candidate read plus authority validation",
            "empty dependency set",
            "post-invalidation caller",
            "cancellation is not a commit fence",
            "late failure",
            "cancellation of one waiter",
            "cancelling one waiter must not detach",
            "shared-entry cancellation request",
            "exact membership non-joinable",
            "work has not terminated",
            "replacement a distinct identity",
            "late cleanup remove only the still-matching entry",
            "join eligibility, termination, and commit authority remain separate",
            "identity-bound `started(a)`",
            "`released(a)`",
            "`decision(a)`",
            "`terminated(a)`",
            "gate release is only a schedule receipt",
            "real post-await commit or caller-outcome branch",
            "`released(a) < decision(a)`",
            "`finally` marker proves only",
            "cannot substitute for the decision receipt",
            "owner-local, non-delivering",
            "user-supplied predicates or factories",
            "backpressure outside the serialized owner",
            "neither join nor wait behind",
            "every outer and inner coordination layer",
            "public data-layer entry",
            "authoritative publication",
            "inner-layer unit proof alone is insufficient",
            "linearize shared-work admission against invalidation",
            "mutate the in-flight registry",
            "bypass generation-scoped",
            "same-generation join, queue, serialization, coalescing",
            "same-generation shared-work admission",
            "immediately before the whole atomic shared-work admission attempt",
            "combined generation-and-membership snapshot",
            "expected generation while installing membership",
            "cancellation-first and admission-first",
            "old nonterminal entry non-joinable",
            "distinct eligible entry",
            "identity-bound late cleanup cannot remove the replacement",
            "neither schedule uses cancellation as commit authority",
            "ordered, idempotent notification record",
            "direct caller",
            "`commontest`",
            "`kotlin.test`",
        ):
            self.assertIn(invariant, lower)
        reference = " ".join(DATA_REFERENCE.read_text(encoding="utf-8").split()).lower()
        for invariant in (
            "owner-local, non-delivering",
            "callbacks, predicates, factories",
            "nested mutation",
            "apply backpressure",
        ):
            self.assertIn(invariant, reference)
        receipt_row = next(
            line.lower()
            for line in DATA_REFERENCE.read_text(encoding="utf-8").splitlines()
            if line.startswith("| Causal receipt ")
        )
        for invariant in (
            "identity-bound",
            "`started(a)`",
            "`released(a)`",
            "`decision(a)`",
            "`terminated(a)`",
            "release is only schedule evidence",
            "real post-await commit or caller-outcome branch",
            "bounded decision receipt",
            "`released(a) < decision(a)`",
            "timeout or `finally` marker is not successful decision proof",
        ):
            self.assertIn(invariant, receipt_row)
        composition_row = next(
            line.lower()
            for line in DATA_REFERENCE.read_text(encoding="utf-8").splitlines()
            if line.startswith("| Coordination composition ")
        )
        for invariant in (
            "every outer and inner",
            "public data-layer entry",
            "authoritative publication",
            "before releasing a",
            "inner-layer unit proof alone is insufficient",
        ):
            self.assertIn(invariant, composition_row)
        admission_row = next(
            line.lower()
            for line in DATA_REFERENCE.read_text(encoding="utf-8").splitlines()
            if line.startswith("| Shared-work admission ")
        )
        for invariant in (
            "current owning generation",
            "joinable registry membership",
            "whole atomic admission attempt",
            "invalidation-first",
            "admission-first",
            "expected generation while atomically installing membership",
            "retry on mismatch",
            "same-generation policy pair",
        ):
            self.assertIn(invariant, admission_row)

        cancellation_row = next(
            line.lower()
            for line in DATA_REFERENCE.read_text(encoding="utf-8").splitlines()
            if line.startswith("| Shared-entry cancellation ")
        )
        for invariant in (
            "cancelling one waiter does not detach healthy shared work",
            "cancellation requested for the shared entry",
            "exact membership non-joinable",
            "join eligibility, termination, and commit authority remain separate",
            "still-matching entry identity",
            "hold shared a nonterminal",
            "one-waiter cancellation control",
            "cancellation-first and admission-first",
            "distinct eligible entry",
            "identity-bound cleanup cannot remove b",
            "admission-first preserves",
        ):
            self.assertIn(invariant, cancellation_row)

    def test_router_and_test_skill_compose_optionally(self):
        router = ROUTER.read_text(encoding="utf-8")
        testing = TEST_SKILL.read_text(encoding="utf-8")
        compact_router = " ".join(router.split()).lower()
        compact_testing = " ".join(testing.split()).lower()
        for signal in ("`async-state-consistency`", "available", "usable on their own"):
            self.assertIn(signal, compact_router)
        for signal in ("`async-state-consistency`", "available", "standalone"):
            self.assertIn(signal, compact_testing)
        for placement in (
            "`commontest`",
            "`kotlin.test`",
            "android-only",
            "native target tasks/xcode",
        ):
            self.assertIn(placement, compact_testing)

    def test_adapter_files_are_public_safe_ascii(self):
        for path in (DATA_SKILL, DATA_REFERENCE, TEST_SKILL, ROUTER):
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.isascii(), str(path))
            self.assertNotIn("/Users/", text)
            self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
