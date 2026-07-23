from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_SKILL = ROOT / "skills" / "kmp-data-layer" / "SKILL.md"
DATA_REFERENCE = ROOT / "references" / "data-layer-readiness.md"
TEST_SKILL = ROOT / "skills" / "kmp-testing-quality" / "SKILL.md"
ROUTER = ROOT / "skills" / "kotlin-multiplatform" / "SKILL.md"


class AsyncStateAdapterTest(unittest.TestCase):
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
            "callbacks outside the serialized owner",
            "ordered, idempotent notification record",
            "direct caller",
            "`commontest`",
            "`kotlin.test`",
        ):
            self.assertIn(invariant, lower)

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
