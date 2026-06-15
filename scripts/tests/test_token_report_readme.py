import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "token-report.py"
spec = importlib.util.spec_from_file_location("token_report", SCRIPT)
token_report = importlib.util.module_from_spec(spec)
sys.modules["token_report"] = token_report
spec.loader.exec_module(token_report)

README = """# Title

Intro prose.

## Token Efficiency

old table row

### Plugin Token Rollup

old rollup

## Repository Design

untouched tail
"""

RENDERED = """## Token Efficiency

new table row

### Plugin Token Rollup

new rollup
"""


class SpliceTests(unittest.TestCase):
    def test_normalizes_line_endings(self):
        self.assertEqual(
            token_report.normalize_newlines("a\r\nb\rc\n"),
            "a\nb\nc\n",
        )

    def test_collect_reports_is_platform_stable(self):
        class FakeEncoder:
            def __init__(self):
                self.texts = []

            def encode(self, text):
                self.texts.append(text)
                return text.split()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin = root / "plugins" / "example"
            skill = plugin / "skills" / "demo"
            (plugin / ".codex-plugin").mkdir(parents=True)
            skill.mkdir(parents=True)
            (plugin / ".codex-plugin" / "plugin.json").write_text(
                '{"description": "Example plugin"}',
                encoding="utf-8",
            )
            (skill / "SKILL.md").write_bytes(
                b"---\r\nname: demo\r\ndescription: Demo skill\r\n---\r\n\r\nBody\r\n"
            )

            encoder = FakeEncoder()
            _plugins, skills = token_report.collect_reports(root, encoder)

        self.assertEqual(skills[0].path, "plugins/example/skills/demo/SKILL.md")
        self.assertIn("file: plugins/example/skills/demo/SKILL.md\n", encoder.texts[0])
        self.assertNotIn("\\", encoder.texts[0])
        self.assertEqual(encoder.texts[1], "\nBody\n")

    def test_count_tokens_preserves_caller_text(self):
        class FakeEncoder:
            def encode(self, text):
                self.last_text = text
                return text.split()

        encoder = FakeEncoder()
        token_report.count_tokens(
            encoder,
            "file: plugins/example/skills/demo/SKILL.md\n",
        )
        self.assertNotIn("\\", encoder.last_text)

    def test_replaces_only_the_managed_region(self):
        out = token_report.splice_readme(README, RENDERED)
        self.assertIn("new table row", out)
        self.assertIn("new rollup", out)
        self.assertNotIn("old table row", out)
        self.assertNotIn("old rollup", out)
        self.assertIn("# Title\n\nIntro prose.", out)
        self.assertIn("## Repository Design\n\nuntouched tail", out)

    def test_idempotent(self):
        once = token_report.splice_readme(README, RENDERED)
        twice = token_report.splice_readme(once, RENDERED)
        self.assertEqual(once, twice)

    def test_missing_start_marker_raises(self):
        with self.assertRaises(ValueError):
            token_report.splice_readme("# No section here\n", RENDERED)

    def test_missing_following_section_raises(self):
        broken = "## Token Efficiency\n\nstuff with no next heading\n"
        with self.assertRaises(ValueError):
            token_report.splice_readme(broken, RENDERED)


if __name__ == "__main__":
    unittest.main()
