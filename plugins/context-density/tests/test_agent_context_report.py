import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "plugins" / "context-density" / "skills" / "context-density" / "scripts" / "agent_context_report.py"
sys.path.insert(0, str(SCRIPT.parent))

import agent_context_report as report  # noqa: E402


class ScrubTests(unittest.TestCase):
    def test_scrub_url_drops_userinfo_query_values_and_fragment(self):
        out = report.scrub_url("https://alice:hunter2@mcp.example.com:8443/sse?api_key=abc123&mode=fast#frag")
        self.assertEqual(out, "https://mcp.example.com:8443/sse?api_key=<redacted>&mode=<redacted>")

    def test_scrub_url_keeps_plain_urls_identifiable(self):
        self.assertEqual(report.scrub_url("https://mcp.example.com/sse"), "https://mcp.example.com/sse")

    def test_display_command_redacts_sensitive_strings(self):
        out = report.display_command("npx server --api-key=XYZ", Path("/tmp"))
        self.assertEqual(out, "<redacted-command>")


class CodexContextReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.codex_home = self.base / ".codex"
        self.project = self.base / "project"
        self.codex_home.mkdir()
        self.project.mkdir()

        (self.project / "AGENTS.md").write_text("# Agent Guide\nUse repo rules.\n", encoding="utf-8")
        (self.codex_home / "config.toml").write_text(
            "\n".join(
                [
                    "[mcp_servers.demo]",
                    'command = "/usr/bin/demo"',
                    'args = ["serve"]',
                    'disabled_tools = ["dangerous_tool"]',
                    "",
                    "[mcp_servers.demo.env]",
                    'SECRET_TOKEN = "should-not-leak"',
                ]
            ),
            encoding="utf-8",
        )

        skill = self.codex_home / "skills" / ".system" / "sample"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\n"
            "name: sample\n"
            "description: Use for sample token diagnostics.\n"
            "---\n\n"
            "# Sample\n\nRun deterministic checks.\n",
            encoding="utf-8",
        )

        plugin = self.codex_home / "plugins" / "cache" / "local" / "demo-plugin" / "0.1.0"
        (plugin / ".codex-plugin").mkdir(parents=True)
        (plugin / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"name": "demo-plugin", "description": "Demo plugin."}),
            encoding="utf-8",
        )
        plugin_skill = plugin / "skills" / "plugin-skill"
        plugin_skill.mkdir(parents=True)
        (plugin_skill / "SKILL.md").write_text(
            "---\n"
            "name: plugin-skill\n"
            "description: Use for plugin skill diagnostics.\n"
            "---\n\n"
            "# Plugin Skill\n\nInspect plugin cache context.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def run_report(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                *args,
                "--agent",
                "codex",
                "--agent-home",
                str(self.codex_home),
                "--project",
                str(self.project),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def test_brief_json_has_cli_compatible_fields(self):
        result = self.run_report("brief", "--json")
        payload = json.loads(result.stdout)
        self.assertIn("startupTokens", payload)
        self.assertIn("onDemandTokens", payload)
        self.assertIn("categories", payload)
        self.assertGreater(payload["rowCount"], 0)

    def test_skills_include_standalone_and_plugin_cache_skills(self):
        result = self.run_report("skills", "--json")
        payload = json.loads(result.stdout)
        names = {row["name"] for row in payload}
        self.assertIn("sample", names)
        self.assertIn("demo-plugin:plugin-skill", names)

    def test_skill_lookup_matches_plugin_skill(self):
        result = self.run_report("skill", "demo-plugin:plugin-skill", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["name"], "demo-plugin:plugin-skill")
        self.assertGreater(payload["bodyTokens"], 0)

    def test_mcp_tools_reports_disabled_tool_without_leaking_env(self):
        result = self.run_report("mcp", "--tools", "demo", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["name"], "demo")
        self.assertEqual(payload["disabledToolCount"], 1)
        self.assertNotIn("should-not-leak", result.stdout)

    def test_sources_ndjson_and_export_markdown_work(self):
        sources = self.run_report("sources", "--limit", "2", "--ndjson")
        rows = [json.loads(line) for line in sources.stdout.splitlines() if line.strip()]
        self.assertEqual(len(rows), 2)
        self.assertIn("type", rows[0])

        export = self.run_report("export", "markdown")
        self.assertIn("| Type | Source | Tokens |", export.stdout)


if __name__ == "__main__":
    unittest.main()
