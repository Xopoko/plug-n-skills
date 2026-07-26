from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (
    ROOT
    / "skills"
    / "kmp-data-layer"
    / "references"
    / "legacy-storage-migration.md"
)


class LegacyMirrorRepairGuidanceTest(unittest.TestCase):
    def test_overlapping_repairs_keep_late_cancelled_writes_from_winning(self):
        text = (
            " ".join(REFERENCE.read_text(encoding="utf-8").split())
            .lower()
            .replace("`", "")
        )

        for invariant in (
            "treat every mirror repair as a competing publisher",
            "cancellation is not a commit fence",
            "canonical revision and a distinct repair identity",
            "do not release its writer ownership while its mirror write can still occur",
            "accepted receipt only after both conditions hold: every older capable write is terminal or storage-visible conditional authority has fenced it; and the final mirror durably reflects the newest admitted canonical revision",
            "storage-visible conditional authority has fenced it",
            "serialize the actual writes through one non-detached owner",
            "write the newest canonical value after older capable writes finish",
            "readback taken while an older write can still run is only tentative",
            "classify mirror freshness as best-effort",
            "cancelled mirror repair overtaken by a newer repair",
            "gate repair a immediately before its mirror write",
            "repair b for a newer canonical revision before releasing a",
            "b cannot return an accepted receipt until both conditions hold: a is terminal or a storage-visible fence rejects its stale write; and the final mirror durably reflects b's newest canonical revision",
            "a cancellation request, b write receipt, or readback while a can still write is insufficient",
        ):
            self.assertIn(invariant, text)

    def test_guidance_is_public_safe_ascii(self):
        text = REFERENCE.read_text(encoding="utf-8")
        self.assertTrue(text.isascii())
        self.assertNotIn("/Users/", text)
        self.assertNotIn("\\Users\\", text)


if __name__ == "__main__":
    unittest.main()
