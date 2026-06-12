import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "context-density"
SCRIPT_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import refuter_calibration as rc  # noqa: E402

ORIGINAL = """---
name: sample
description: demo
---

# Sample

This workflow has several stages. Each stage produces an artifact. The
artifact is validated before the next stage starts.

Rules for processing items in the queue:

- First check the queue depth and reject when it exceeds limits
- Then take the oldest item from the queue, mark it as claimed, and log the claim
- Retry failed items at most 4 times before moving them aside
- Finally archive completed items after the retention window passes

Run `process.sh --batch` once per cycle.

```bash
process.sh --batch
```
"""


class PlantTests(unittest.TestCase):
    def test_plants_are_deterministic_and_keyed(self):
        exam1, plants1 = rc.plant(ORIGINAL, count=3, seed=7)
        exam2, plants2 = rc.plant(ORIGINAL, count=3, seed=7)
        self.assertEqual(exam1, exam2)
        self.assertEqual(plants1, plants2)
        self.assertGreaterEqual(len(plants1), 2)
        for p in plants1:
            self.assertIn(p["kind"], {"drop_bullet", "drop_sentence",
                                      "edit_number", "drop_clause"})

    def test_plants_avoid_fences_and_protected_lines(self):
        exam, _ = rc.plant(ORIGINAL, count=5, seed=7)
        self.assertIn("```bash\nprocess.sh --batch\n```", exam)
        self.assertIn("`process.sh --batch`", exam)

    def test_exam_differs_from_original(self):
        exam, plants = rc.plant(ORIGINAL, count=3, seed=7)
        self.assertNotEqual(exam, ORIGINAL)
        self.assertLess(abs(len(exam) - len(ORIGINAL)), len(ORIGINAL))
        self.assertTrue(plants)

    def test_plants_invisible_to_deterministic_checker(self):
        import compression_invariants as ci
        exam, _ = rc.plant(ORIGINAL, count=5, seed=7)
        result = ci.check(ORIGINAL, exam, frontmatter_check=True,
                          ignore_spans=set(), ignore_fenced_prefixes=[])
        self.assertTrue(result["passed"], result["violations"])

    def test_plants_avoid_frontmatter(self):
        for seed in range(8):
            _, plants = rc.plant(ORIGINAL, count=5, seed=seed)
            for p in plants:
                self.assertGreater(p["line"], 4,
                                   f"seed {seed} planted in frontmatter: {p}")

    def test_plants_avoid_digit_bearing_curly_tokens(self):
        orig = ORIGINAL.replace(
            "- Then take the oldest item from the queue, mark it as claimed, and log the claim",
            "- Then take the {step1} item from the queue, mark it as claimed, and log the claim")
        for seed in range(8):
            exam, _ = rc.plant(orig, count=5, seed=seed)
            self.assertIn("{step1}", exam, f"seed {seed} mutated token line")


DIFF = """--- a/src/service.py
+++ b/src/service.py
@@ -10,6 +10,9 @@ def handler(request):
 context line stays
+    retries = settings.get("retries", 4)
+    if not request.user.is_active and request.attempts > 2:
+        raise PermissionError("inactive user exceeded attempts")
+    audit_log.record(request.user, action="login", source="handler")
 another context line
-removed_old_line()
"""


class PlantDiffTests(unittest.TestCase):
    def test_mutates_only_added_lines(self):
        exam, plants = rc.plant_diff(DIFF, count=3, seed=7)
        self.assertTrue(plants)
        self.assertIn("context line stays", exam)
        self.assertIn("-removed_old_line()", exam)
        self.assertIn("+++ b/src/service.py", exam)  # header untouched
        self.assertNotEqual(exam, DIFF)

    def test_deterministic(self):
        a = rc.plant_diff(DIFF, count=3, seed=7)
        b = rc.plant_diff(DIFF, count=3, seed=7)
        self.assertEqual(a, b)

    def test_grade_roundtrip(self):
        _, plants = rc.plant_diff(DIFF, count=3, seed=7)
        key = {"schema": rc.SCHEMA_KEY, "plants": plants}
        good = {"violations": [{"line": p["line"]} for p in plants]}
        self.assertTrue(rc.grade(key, good, threshold=0.8)["passed"])
        self.assertFalse(rc.grade(key, {"violations": []}, threshold=0.8)["passed"])

    def test_no_added_lines_yields_no_plants(self):
        ctx_only = "--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n context\n-old\n"
        _, plants = rc.plant_diff(ctx_only, count=3, seed=7)
        self.assertEqual(plants, [])


class GradeTests(unittest.TestCase):
    def setUp(self):
        self.exam, self.plants = rc.plant(ORIGINAL, count=3, seed=7)
        self.key = {"schema": rc.SCHEMA_KEY, "plants": self.plants}

    def test_perfect_verdict_by_line_passes(self):
        verdict = {"violations": [{"line": p["line"], "detail": "x"}
                                  for p in self.plants]}
        result = rc.grade(self.key, verdict, threshold=0.8)
        self.assertTrue(result["passed"])
        self.assertEqual(result["missed"], [])

    def test_clue_text_match_counts_without_line(self):
        verdict = {"violations": [f"dropped content about {p['clue']}"
                                  for p in self.plants]}
        result = rc.grade(self.key, verdict, threshold=0.8)
        self.assertTrue(result["passed"])

    def test_empty_verdict_fails(self):
        result = rc.grade(self.key, {"violations": []}, threshold=0.8)
        self.assertFalse(result["passed"])
        self.assertEqual(result["caught"], [])

    def test_near_line_match_is_lenient(self):
        verdict = {"violations": [{"line": p["line"] + 2, "detail": "near"}
                                  for p in self.plants]}
        result = rc.grade(self.key, verdict, threshold=0.8)
        self.assertTrue(result["passed"])

    def test_spam_verdict_fails_despite_full_recall(self):
        verdict = {"violations": [{"line": n, "detail": ""}
                                  for n in range(1, 301)]}
        result = rc.grade(self.key, verdict, threshold=0.8)
        self.assertFalse(result["passed"])
        self.assertTrue(result.get("spam_guard"))

    def test_verbose_honest_verdict_is_not_spam(self):
        extra = [{"line": 999, "detail": f"observation {i}"} for i in range(10)]
        verdict = {"violations": [{"line": p["line"]} for p in self.plants] + extra}
        result = rc.grade(self.key, verdict, threshold=0.8)
        self.assertTrue(result["passed"])

    def test_malformed_verdict_items_are_tolerated(self):
        verdict = {"violations": [123, None, {"weird": True},
                                  {"line": self.plants[0]["line"]}]}
        result = rc.grade(self.key, verdict, threshold=0.1)
        self.assertGreaterEqual(len(result["caught"]), 1)


class CliTests(unittest.TestCase):
    def test_plant_and_grade_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = Path(tmp) / "orig.md"
            exam = Path(tmp) / "exam.md"
            key = Path(tmp) / "key.json"
            orig.write_text(ORIGINAL, encoding="utf-8")
            self.assertEqual(rc.main(["plant", str(orig), "--exam", str(exam),
                                      "--key", str(key), "--count", "3"]), 0)
            plants = json.loads(key.read_text())["plants"]
            good = Path(tmp) / "good.json"
            good.write_text(json.dumps(
                {"violations": [{"line": p["line"]} for p in plants]}))
            self.assertEqual(rc.main(["grade", str(key), str(good)]), 0)
            bad = Path(tmp) / "bad.json"
            bad.write_text(json.dumps({"violations": []}))
            self.assertEqual(rc.main(["grade", str(key), str(bad)]), 1)
            self.assertEqual(rc.main(["grade", str(key),
                                      str(Path(tmp) / "missing.json")]), 2)

    def test_unplantable_file_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = Path(tmp) / "code-only.md"
            orig.write_text("```bash\nls\n```\n", encoding="utf-8")
            rcode = rc.main(["plant", str(orig),
                             "--exam", str(Path(tmp) / "e.md"),
                             "--key", str(Path(tmp) / "k.json")])
            self.assertEqual(rcode, 2)


if __name__ == "__main__":
    unittest.main()
