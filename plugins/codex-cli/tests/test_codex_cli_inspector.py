import importlib.util
import io
import json
import os
import stat
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "codex_cli_inspector.py"
spec = importlib.util.spec_from_file_location("codex_cli_inspector", SCRIPT)
inspector = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(inspector)


class CodexCliInspectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fake_codex = Path(self.tmp.name) / "codex"
        self.fake_codex.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env sh
                if [ "$1" = "--version" ]; then
                  echo "codex-cli 9.9.9"
                  exit 0
                fi
                if [ "$1" = "--help" ]; then
                  cat <<'EOF'
                Codex CLI

                Usage: codex [OPTIONS] [PROMPT]

                Commands:
                  exec            Run Codex non-interactively
                  review          Run a code review non-interactively
                  doctor          Diagnose local Codex installation
                  app-server      [experimental] Run the app server
                  help            Print this message

                Options:
                  -C, --cd <DIR>
                  -s, --sandbox <SANDBOX_MODE>
                      --dangerously-bypass-approvals-and-sandbox
                EOF
                  exit 0
                fi
                if [ "$2" = "--help" ]; then
                  case "$1" in
                    exec)
                      cat <<'EOF'
                Run Codex non-interactively

                Usage: codex exec [OPTIONS] [PROMPT]

                Options:
                      --json
                      --output-schema <FILE>
                  -o, --output-last-message <FILE>
                EOF
                      ;;
                    doctor)
                      cat <<'EOF'
                Diagnose local Codex installation

                Options:
                      --json
                      --summary
                      --ascii
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
        mode = self.fake_codex.stat().st_mode
        self.fake_codex.chmod(mode | stat.S_IXUSR)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = inspector.main(["--codex", str(self.fake_codex), *argv])
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_json_report_parses_root_and_subcommands(self):
        output = self.run_cli(["--commands", "exec", "doctor", "--json"])
        report = json.loads(output)
        self.assertEqual(report["version"], "codex-cli 9.9.9")
        self.assertIn("exec", report["root"]["commands"])
        self.assertIn("app-server", report["root"]["experimental_commands"])
        exec_report = next(item for item in report["commands"] if item["name"] == "exec")
        self.assertIn("--output-schema", exec_report["summary"]["options"])

    def test_dangerous_flags_are_reported(self):
        output = self.run_cli(["--commands", "doctor", "--json"])
        report = json.loads(output)
        self.assertIn(
            "--dangerously-bypass-approvals-and-sandbox",
            report["safety"]["dangerous_flags_seen"],
        )


if __name__ == "__main__":
    unittest.main()
