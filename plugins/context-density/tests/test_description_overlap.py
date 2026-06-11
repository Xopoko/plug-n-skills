import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "context-density"
SCRIPT_DIR = SKILL_DIR / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import description_overlap as overlap  # noqa: E402


def write_skill(root: Path, name: str, description: str) -> None:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: >-\n  {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


class DescriptionOverlapTests(unittest.TestCase):
    def test_reports_competing_descriptions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_skill(root, "alpha", "Audit token cost, prompt compression, and context placement for skill packages.")
            write_skill(root, "beta", "Audit token cost, prompt compression, and context placement for plugin manifests.")
            write_skill(root, "gamma", "Generate watercolor paintings from photographs using diffusion checkpoints.")
            skills = overlap.collect_skills([str(root)])
            pairs = overlap.overlap_pairs(skills, min_jaccard=0.25, top=10)
        self.assertEqual(len(skills), 3)
        self.assertEqual(len(pairs), 1)
        names = {pairs[0]["a"]["name"], pairs[0]["b"]["name"]}
        self.assertEqual(names, {"alpha", "beta"})
        self.assertGreaterEqual(pairs[0]["jaccard"], 0.5)
        self.assertIn("compression", pairs[0]["shared_terms"])

    def test_multiline_folded_description_parsed(self):
        text = "---\nname: x\ndescription: >-\n  first line of text\n  second line continues\n---\nbody\n"
        fields = overlap.parse_frontmatter(text)
        self.assertEqual(fields["description"], "first line of text second line continues")

    def test_stopwords_and_boilerplate_excluded(self):
        words = overlap.content_words("Use this skill when the user asks to trigger it for analysis.")
        self.assertNotIn("use", words)
        self.assertNotIn("when", words)
        self.assertIn("analysis", words)


if __name__ == "__main__":
    unittest.main()
