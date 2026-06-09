import importlib.util
import io
import json
import stat
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
        self.fake_claude = Path(self.tmp.name) / "claude"
        self.fake_claude.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env sh
                if [ "$1" = "--version" ]; then
                  echo "2.9.9 (Claude Code)"
                  exit 0
                fi
                if [ "$1" = "--help" ]; then
                  cat <<'EOF'
                Usage: claude [options] [command] [prompt]

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
                EOF
                  exit 0
                fi
                if [ "$2" = "--help" ]; then
                  case "$1" in
                    plugin)
                      cat <<'EOF'
                Usage: claude plugin|plugins [options] [command]

                Commands:
                  details [options] <name>
                  install|i [options] <plugin>
                  validate [options] <path>
                  marketplace
                EOF
                      ;;
                    mcp)
                      cat <<'EOF'
                Usage: claude mcp [options] [command]

                Commands:
                  add [options] <name> <commandOrUrl> [args...]
                  list
                  remove [options] <name>
                  serve [options]
                EOF
                      ;;
                    *)
                      echo "unknown command" >&2
                      exit 2
                      ;;
                  esac
                  exit 0
                fi
                echo "unexpected args: $*" >&2
                exit 2
                """
            ),
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
