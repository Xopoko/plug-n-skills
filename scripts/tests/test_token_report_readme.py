import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
            (plugin / "references").mkdir()
            (skill / "references").mkdir()
            (skill / "scripts").mkdir()
            (plugin / ".codex-plugin" / "plugin.json").write_text(
                '{"description": "Example plugin"}',
                encoding="utf-8",
            )
            (skill / "SKILL.md").write_bytes(
                b"---\r\nname: demo\r\ndescription: Demo skill\r\n---\r\n\r\nBody\r\n"
            )
            (plugin / "references" / "plugin.md").write_text(
                "plugin reference", encoding="utf-8"
            )
            (skill / "references" / "skill.md").write_text(
                "skill reference", encoding="utf-8"
            )
            (skill / "scripts" / "guard.py").write_text(
                "print('ok')", encoding="utf-8"
            )

            encoder = FakeEncoder()
            plugins, skills = token_report.collect_reports(root, encoder)

        self.assertEqual(skills[0].path, "skills/demo/SKILL.md")
        self.assertIn("file: skills/demo/SKILL.md\n", encoder.texts[0])
        self.assertNotIn("\\", encoder.texts[0])
        self.assertEqual(encoder.texts[1], "\nBody\n")
        self.assertIsNone(skills[0].published_url_routing_tokens)
        self.assertEqual(plugins[0].reference_count, 2)
        self.assertEqual(plugins[0].script_count, 1)

    def test_first_party_routing_is_recomputed_from_source_relative_path(self):
        class FakeEncoder:
            def __init__(self):
                self.texts = []

            def encode(self, text):
                self.texts.append(text)
                return text.split()

        plugin = {
            "name": "standalone",
            "description": "Standalone plugin",
            "source": {
                "repository": "owner/repo",
                "commit": "a" * 40,
            },
        }
        receipt = {
            "skills": {
                "count": 1,
                "items": [
                    {
                        "name": "demo",
                        "path": "skills/demo/SKILL.md",
                        "description": "Demo skill",
                        "startupTokens": 99,
                        "bodyTokens": 4,
                    }
                ],
            },
            "counts": {"references": 2, "scripts": 3},
            "tokens": {"startup": 99, "body": 4},
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / token_report.plugin_catalog.LOCKFILE_NAME).write_text(
                "{}", encoding="utf-8"
            )
            encoder = FakeEncoder()
            with (
                mock.patch.object(
                    token_report.plugin_catalog,
                    "validate_catalog",
                    return_value={"plugins": [plugin]},
                ),
                mock.patch.object(
                    token_report.plugin_catalog,
                    "receipt_for",
                    return_value=receipt,
                ),
                mock.patch.object(
                    token_report,
                    "plugin_order",
                    return_value=["standalone"],
                ),
            ):
                plugins, skills = token_report.collect_reports(root, encoder)

        self.assertEqual(skills[0].path, "skills/demo/SKILL.md")
        self.assertIn("file: skills/demo/SKILL.md\n", encoder.texts[0])
        self.assertNotIn("github.com", encoder.texts[0])
        self.assertNotEqual(skills[0].source_routing_tokens, 99)
        self.assertEqual(skills[0].published_url_routing_tokens, 99)
        self.assertEqual(
            plugins[0].source_routing_tokens,
            skills[0].source_routing_tokens,
        )
        self.assertEqual(plugins[0].published_url_routing_tokens, 99)

    def test_render_separates_source_receipt_and_runtime_claims(self):
        plugin = token_report.PluginReport(
            name="standalone",
            description="Standalone plugin",
            skill_count=1,
            reference_count=2,
            script_count=3,
            source_routing_tokens=7,
            published_url_routing_tokens=99,
            body_tokens=4,
        )
        skill = token_report.SkillReport(
            plugin="standalone",
            skill="demo",
            path="skills/demo/SKILL.md",
            description="Demo skill",
            source_routing_tokens=7,
            published_url_routing_tokens=99,
            body_tokens=4,
        )

        rendered = token_report.render_markdown([plugin], [skill])
        payload = json.loads(token_report.render_json([plugin], [skill]))

        self.assertIn("static source measurements, not evidence", rendered)
        self.assertNotIn("always-visible", rendered)
        self.assertIn("| Script/support files |", rendered)
        self.assertIn("| Source-relative routing estimate | 1 skills | 7 |", rendered)
        self.assertIn(
            "| Published first-party URL locator snapshot | 1 skills | 99 |",
            rendered,
        )
        self.assertIn(
            "| Plugin | Skills | Refs | Script/support files | Source routing | Published URL routing | Body source |",
            rendered,
        )
        self.assertNotIn("startup_tokens", payload["plugins"][0])
        self.assertEqual(payload["plugins"][0]["source_routing_tokens"], 7)
        self.assertEqual(
            payload["plugins"][0]["published_url_routing_tokens"],
            99,
        )

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
