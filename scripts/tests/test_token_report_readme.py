import importlib.util
import sys
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
