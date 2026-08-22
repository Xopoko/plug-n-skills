from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CursorDistributionContractTests(unittest.TestCase):
    def test_docs_do_not_deny_native_cursor_plugins(self) -> None:
        paths = (
            "AGENTS.md",
            "README.md",
            "docs/ARCHITECTURE.md",
            "docs/QUALITY.md",
            "plugins/capability-workbench/references/marketplace-validation.md",
            "plugins/capability-workbench/references/synthesis-contract.md",
            "plugins/capability-workbench/references/skill-runtime-model.md",
            "scripts/install-cursor-skills.py",
        )
        forbidden = (
            "Cursor needs no manifest",
            "Cursor has no plugin marketplace",
            "Cursor consumes skills directly without a plugin marketplace",
            "Cursor consumes `SKILL.md` folders directly and has no plugin marketplace",
        )

        for relative_path in paths:
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            for stale_claim in forbidden:
                self.assertNotIn(stale_claim, text, f"{relative_path}: {stale_claim}")

    def test_docs_bound_direct_export_and_native_packaging(self) -> None:
        architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
        installer = (ROOT / "scripts/install-cursor-skills.py").read_text(encoding="utf-8")

        for text in (architecture, installer):
            self.assertIn("direct Agent Skills export", " ".join(text.split()))

        self.assertIn(".cursor-plugin/plugin.json", architecture)
        self.assertIn(".cursor-plugin/marketplace.json", architecture)
        self.assertIn("native plugin manifests", installer)


if __name__ == "__main__":
    unittest.main()
