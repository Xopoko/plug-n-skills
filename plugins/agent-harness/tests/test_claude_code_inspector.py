import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "claude_code_inspector.py"
spec = importlib.util.spec_from_file_location("claude_code_inspector", SCRIPT)
inspector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(inspector)


class ClaudeCodeInspectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake_script = Path(self.tmp.name) / "fake_claude.py"
        self.fake_script.write_text(
            textwrap.dedent(
                """\
                import sys

                ROOT_HELP = '''Usage: claude [options] [command] [prompt]

                Options:
                  --dangerously-skip-permissions
                  --allow-dangerously-skip-permissions
                  --output-format <format> (choices: "text", "json", "stream-json")
                  --input-format <format> (choices: "text", "stream-json")
                  --permission-mode <mode> (choices: "acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan")

                Commands:
                  agents [options]                      Manage background agents
                  mcp                                   Configure and manage MCP servers
                  plugin|plugins                        Manage Claude Code plugins
                  project                               Manage Claude Code project state
                '''

                PLUGIN_HELP = '''Usage: claude plugin|plugins [options] [command]

                Commands:
                  details [options] <name>
                  install|i [options] <plugin>
                  validate [options] <path>
                  marketplace
                '''

                MCP_HELP = '''Usage: claude mcp [options] [command]

                Commands:
                  add [options] <name> <commandOrUrl> [args...]
                  list
                  remove [options] <name>
                  serve [options]
                '''

                args = sys.argv[1:]
                if args == ["--version"]:
                    print("2.9.9 (Claude Code)")
                    raise SystemExit(0)
                if args == ["--help"]:
                    print(ROOT_HELP)
                    raise SystemExit(0)
                if len(args) == 2 and args[1] == "--help":
                    if args[0] == "plugin":
                        print(PLUGIN_HELP)
                        raise SystemExit(0)
                    if args[0] == "mcp":
                        print(MCP_HELP)
                        raise SystemExit(0)
                    print("unknown command", file=sys.stderr)
                    raise SystemExit(2)
                print("unexpected args: " + " ".join(args), file=sys.stderr)
                raise SystemExit(2)
                """
            ),
            encoding="utf-8",
        )
        self.fake_claude = Path(self.tmp.name) / ("claude.cmd" if os.name == "nt" else "claude")
        if os.name == "nt":
            self.fake_claude.write_text(
                f'@echo off\r\n"{sys.executable}" "{self.fake_script}" %*\r\nexit /b %ERRORLEVEL%\r\n',
                encoding="utf-8",
            )
        else:
            self.fake_claude.write_text(
                f'#!/usr/bin/env sh\nexec "{sys.executable}" "{self.fake_script}" "$@"\n',
                encoding="utf-8",
            )
            self.fake_claude.chmod(self.fake_claude.stat().st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = inspector.main(["--claude", str(self.fake_claude), *argv])
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_json_report_parses_root_choices_and_subcommands(self):
        output = self.run_cli(["--commands", "plugin", "mcp", "--json"])
        report = json.loads(output)
        self.assertEqual(report["version"], "2.9.9 (Claude Code)")
        self.assertIn("plugin|plugins", report["root"]["commands"])
        self.assertIn("bypassPermissions", report["safety"]["permission_modes"])
        self.assertIn("stream-json", report["root"]["output_formats"])
        plugin_report = next(item for item in report["commands"] if item["name"] == "plugin")
        self.assertIn("validate", plugin_report["summary"]["commands"])

    def test_dangerous_flags_are_reported(self):
        output = self.run_cli(["--commands", "mcp", "--json"])
        report = json.loads(output)
        self.assertIn("--dangerously-skip-permissions", report["safety"]["dangerous_flags_seen"])
        self.assertIn(
            "--allow-dangerously-skip-permissions",
            report["safety"]["dangerous_flags_seen"],
        )


if __name__ == "__main__":
    unittest.main()
