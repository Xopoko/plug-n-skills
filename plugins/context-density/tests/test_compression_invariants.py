import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "context-density"
SCRIPT_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import compression_invariants as ci  # noqa: E402

ORIGINAL = """---
name: sample
description: demo skill
---

# Sample

You **MUST** consider `$ARGUMENTS` and run `scripts/check.sh --json` first.

```bash
python3 scripts/check.sh --json
```

Hook output template:

```
EXECUTE_COMMAND: {command}
```

Fill the [FEATURE NAME] placeholder and keep __AGENT__ markers.

```text
redundant example block
```
"""


def kinds(result):
    return sorted({v["kind"] for v in result["violations"]})


class CheckTests(unittest.TestCase):
    def test_identical_passes(self):
        result = ci.check(ORIGINAL, ORIGINAL, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertTrue(result["passed"])
        self.assertEqual(result["violations"], [])

    def test_prose_only_compression_passes(self):
        compressed = ORIGINAL.replace(
            "You **MUST** consider `$ARGUMENTS` and run `scripts/check.sh --json` first.",
            "Consider `$ARGUMENTS`; run `scripts/check.sh --json` first. MUST.")
        result = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertTrue(result["passed"], result["violations"])

    def test_frontmatter_change_fails(self):
        compressed = ORIGINAL.replace("description: demo skill",
                                      "description: demo")
        result = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("frontmatter", kinds(result))

    def test_no_frontmatter_flag_skips_that_check(self):
        compressed = ORIGINAL.replace("description: demo skill",
                                      "description: demo")
        result = ci.check(ORIGINAL, compressed, frontmatter_check=False,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertNotIn("frontmatter", kinds(result))

    def test_altered_fenced_block_fails(self):
        compressed = ORIGINAL.replace("EXECUTE_COMMAND: {command}",
                                      "EXECUTE: {command}")
        result = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))

    def test_lost_inline_span_fails_and_ignore_span_allows(self):
        compressed = ORIGINAL.replace(
            "run `scripts/check.sh --json` first", "run the checker first")
        result = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("span", kinds(result))
        allowed = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                           ignore_spans={"scripts/check.sh --json"},
                           ignore_fenced_prefixes=[])
        self.assertNotIn("span", kinds(allowed))

    def test_lost_placeholder_tokens_fail(self):
        compressed = (ORIGINAL
                      .replace("[FEATURE NAME]", "the feature name")
                      .replace("__AGENT__ markers", "agent markers"))
        result = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("bracket-placeholder", kinds(result))
        self.assertIn("dunder-token", kinds(result))

    def test_dropped_example_block_needs_explicit_allowance(self):
        compressed = ORIGINAL.replace(
            "```text\nredundant example block\n```\n", "")
        result = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))
        allowed = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                           ignore_spans=set(),
                           ignore_fenced_prefixes=["redundant example"])
        self.assertTrue(allowed["passed"], allowed["violations"])

    def test_reduction_pct_reported(self):
        compressed = ORIGINAL.replace("Hook output template:\n", "")
        result = ci.check(ORIGINAL, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertGreater(result["reduction_pct"], 0)

    def test_nested_fence_content_protected(self):
        orig = ("```outer\nsome text\n    ```\n    inner-secret-line\n"
                "    ```\nmore\n```\n")
        comp = orig.replace("    inner-secret-line\n", "")
        result = ci.check(orig, comp, frontmatter_check=False,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))

    def test_tilde_fence_protected(self):
        orig = "~~~bash\necho exact-command --flag=1\n~~~\n"
        comp = orig.replace("exact-command --flag=1", "TOTALLY-DIFFERENT")
        result = ci.check(orig, comp, frontmatter_check=False,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))

    def test_empty_fenced_block_drop_detected(self):
        orig = "before\n```\n```\nafter\n"
        comp = "before\nafter\n"
        result = ci.check(orig, comp, frontmatter_check=False,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))

    def test_unclosed_fence_protected_to_eof(self):
        orig = "```x\nline1\nline2\n"
        comp = "```x\nline1\n"
        result = ci.check(orig, comp, frontmatter_check=False,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))

    def test_pathological_fence_openers_linear_time(self):
        import time
        for pathological in ("```x\ncontent line\n" * 4000,
                             "```x\n ```\n" * 4000):
            start = time.monotonic()
            result = ci.check(pathological, pathological,
                              frontmatter_check=False,
                              ignore_spans=set(), ignore_fenced_prefixes=[])
            self.assertTrue(result["passed"])
            self.assertLess(time.monotonic() - start, 2.0)

    def test_nested_fence_with_shallower_closer_protected(self):
        orig = (" ```outer\ntext\n    ```\n    inner-secret\n    ```\n"
                "```\nafter\n")
        comp = orig.replace("    inner-secret\n", "")
        result = ci.check(orig, comp, frontmatter_check=False,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))

    def test_duplicate_block_multiplicity_enforced(self):
        block = "```bash\necho run-me\n```\n"
        orig = f"first\n{block}middle\n{block}last\n"
        comp = f"first\n{block}middle\nlast\n"
        result = ci.check(orig, comp, frontmatter_check=False,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))

    def test_unclosed_outer_with_nested_pair_protected_to_eof(self):
        orig = "```outer\ntext\n    ```\n    inner-secret\n    ```\ntail\n"
        comp = orig.replace("    inner-secret\n", "")
        result = ci.check(orig, comp, frontmatter_check=False,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertIn("fenced", kinds(result))

    def test_growth_is_not_a_violation(self):
        grown = ORIGINAL + "\nappended elaboration prose\n"
        result = ci.check(ORIGINAL, grown, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertTrue(result["passed"])
        self.assertLess(result["reduction_pct"], 0)


class WarningTests(unittest.TestCase):
    BASE = ("---\nname: w\ndescription: d\n---\n\nYou must keep all items and "
            "retry at most 3 times with a 50% backoff.\n")

    def _check(self, compressed, **kw):
        return ci.check(self.BASE, compressed, frontmatter_check=True,
                        ignore_spans=set(), ignore_fenced_prefixes=[], **kw)

    def test_identical_has_no_warnings(self):
        result = self._check(self.BASE)
        self.assertEqual(result["warnings"], [])

    def test_lost_number_warns_but_passes(self):
        compressed = self.BASE.replace(" 3 times with a 50% backoff", " a few times")
        result = self._check(compressed)
        kinds = {w["kind"] for w in result["warnings"]}
        self.assertIn("number-lost", kinds)
        self.assertTrue(result["passed"])

    def test_modality_and_quantifier_drop_warn(self):
        compressed = self.BASE.replace("You must keep all items", "Keep items")
        result = self._check(compressed)
        kinds = {w["kind"] for w in result["warnings"]}
        self.assertIn("modality-drop", kinds)
        self.assertIn("quantifier-drop", kinds)
        self.assertTrue(result["passed"])

    def test_custom_modality_wordlist(self):
        base = "---\nname: w\ndescription: d\n---\n\n\u042d\u0442\u043e \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u043e \u0434\u043b\u044f \u0432\u0441\u0435\u0445.\n"
        compressed = base.replace("\u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u043e ", "")
        result = ci.check(base, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[],
                          modality_words=("\u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u043e",))
        self.assertIn("modality-drop", {w["kind"] for w in result["warnings"]})

    def test_percent_sign_loss_warns(self):
        compressed = self.BASE.replace("a 50% backoff", "a 50 backoff")
        result = self._check(compressed)
        details = [w["detail"] for w in result["warnings"]]
        self.assertTrue(any("50%" in d for d in details), details)
        self.assertTrue(result["passed"])

    def test_numbers_inside_code_do_not_warn(self):
        base = "---\nname: w\ndescription: d\n---\n\nRun `retry --max 3`.\n"
        compressed = base  # identical; code numbers never enter prose inventory
        result = ci.check(base, compressed, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertEqual(result["warnings"], [])


class CliTests(unittest.TestCase):
    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = Path(tmp) / "orig.md"
            same = Path(tmp) / "same.md"
            broken = Path(tmp) / "broken.md"
            orig.write_text(ORIGINAL, encoding="utf-8")
            same.write_text(ORIGINAL, encoding="utf-8")
            broken.write_text(ORIGINAL.replace("EXECUTE_COMMAND:", "EXEC:"),
                              encoding="utf-8")
            self.assertEqual(ci.main([str(orig), str(same)]), 0)
            self.assertEqual(ci.main([str(orig), str(broken), "--json"]), 1)
            self.assertEqual(ci.main([str(orig), str(Path(tmp) / "missing.md")]), 2)

    def test_non_utf8_input_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = Path(tmp) / "orig.md"
            latin1 = Path(tmp) / "latin1.md"
            orig.write_text(ORIGINAL, encoding="utf-8")
            latin1.write_bytes(b"caf\xe9 `x`\n")
            self.assertEqual(ci.main([str(latin1), str(orig)]), 2)


if __name__ == "__main__":
    unittest.main()
