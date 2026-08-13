from __future__ import annotations

import json
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
SKILL = PLUGIN_ROOT / "skills" / "i-have-adhd" / "SKILL.md"
CODEX_MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = REPOSITORY_ROOT / ".claude-plugin" / "marketplace.json"
ROOT_README = REPOSITORY_ROOT / "README.md"
PLUGINS_README = REPOSITORY_ROOT / "plugins" / "README.md"
OPENAI_METADATA = (
    PLUGIN_ROOT / "skills" / "i-have-adhd" / "agents" / "openai.yaml"
)


class IHaveAdhdSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL.read_text(encoding="utf-8").lower()
        cls.codex = json.loads(CODEX_MANIFEST.read_text(encoding="utf-8"))
        cls.claude = json.loads(CLAUDE_MANIFEST.read_text(encoding="utf-8"))
        cls.marketplace = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        cls.root_readme = ROOT_README.read_text(encoding="utf-8").lower()
        cls.plugins_readme = PLUGINS_README.read_text(encoding="utf-8").lower()
        cls.openai = OPENAI_METADATA.read_text(encoding="utf-8").lower()
        cls.normalized_skill = " ".join(cls.skill.split())

    def test_invocation_is_explicit_and_per_request(self) -> None:
        self.assertIn("current explicitly opted-in request", self.normalized_skill)
        self.assertIn("invokes the skill again", self.normalized_skill)
        self.assertIn("do not claim", self.normalized_skill)
        self.assertIn("persist state across turns", self.normalized_skill)
        self.assertIn("allow_implicit_invocation: false", self.openai)

    def test_no_portable_persistence_claim_remains(self) -> None:
        marketplace_entry = next(
            plugin
            for plugin in self.marketplace["plugins"]
            if plugin["name"] == "i-have-adhd"
        )
        exposed = "\n".join(
            (
                self.skill,
                self.codex["description"].lower(),
                self.codex["interface"]["shortDescription"].lower(),
                self.codex["interface"]["longDescription"].lower(),
                self.claude["description"].lower(),
                marketplace_entry["description"].lower(),
                self.root_readme,
                self.plugins_readme,
                self.openai,
            )
        )
        for forbidden in (
            "conversation-scoped",
            "rest of the current conversation",
            "until the user says stop",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, exposed)

    def test_response_contract_stays_bounded(self) -> None:
        for requirement in (
            "two to five numbered steps",
            "progress: x/y",
            "concrete estimate",
            "exactly one `next action:",
            "ask one blocking question at a time",
        ):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, self.skill)


if __name__ == "__main__":
    unittest.main()
