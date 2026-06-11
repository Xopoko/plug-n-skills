import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "plugins" / "spec-driven-development" / "skills"

# The frontmatter description is the only routing signal an agent sees at
# session start. Each skill must carry terms that (a) genuinely appear in its
# description today and (b) discriminate it from the sibling sdd skills.
REQUIRED_TERMS = {
    "sdd": ["route", "spec-driven development", "lanes"],
    "sdd-specify": ["requirements", "specifications", "acceptance"],
    "sdd-plan-tasks": ["plans", "task lists", "traceable"],
    "sdd-implement": ["execute", "evidence", "drift"],
    "sdd-audit": ["audit", "traceability", "evidence"],
    "sdd-spec-kit": ["spec kit", "constitution", "implement"],
}

MAX_DESCRIPTION_LENGTH = 1024


def extract_description(skill_md: Path) -> str:
    """Extract the frontmatter description without a yaml dependency.

    Handles both single-line ``description: ...`` and block/folded styles
    (``description: >-`` followed by indented continuation lines).
    """
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError(f"{skill_md}: missing opening frontmatter ---")
    frontmatter = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        frontmatter.append(line)
    else:
        raise AssertionError(f"{skill_md}: missing closing frontmatter ---")

    for i, line in enumerate(frontmatter):
        if not line.startswith("description:"):
            continue
        value = line[len("description:"):].strip()
        parts = [] if value in ("", ">", ">-", ">+", "|", "|-", "|+") else [value]
        for cont in frontmatter[i + 1:]:
            if not cont.strip():
                continue
            if cont[0] not in (" ", "\t"):
                break
            parts.append(cont.strip())
        return " ".join(parts)
    raise AssertionError(f"{skill_md}: frontmatter has no description key")


class SddTriggerMetadataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.descriptions = {
            name: extract_description(SKILLS_DIR / name / "SKILL.md")
            for name in REQUIRED_TERMS
        }

    def test_skill_set_matches_expectations(self):
        on_disk = {p.name for p in SKILLS_DIR.iterdir()
                   if (p / "SKILL.md").is_file()}
        self.assertEqual(
            on_disk, set(REQUIRED_TERMS),
            "sdd skill set changed; update REQUIRED_TERMS to keep "
            "trigger-metadata coverage complete",
        )

    def test_descriptions_non_empty_and_within_limit(self):
        for name, description in self.descriptions.items():
            with self.subTest(skill=name):
                self.assertTrue(description.strip(),
                                f"{name}: empty description")
                self.assertLessEqual(
                    len(description), MAX_DESCRIPTION_LENGTH,
                    f"{name}: description exceeds "
                    f"{MAX_DESCRIPTION_LENGTH} characters",
                )

    def test_required_discriminator_terms_present(self):
        for name, terms in REQUIRED_TERMS.items():
            lowered = self.descriptions[name].lower()
            for term in terms:
                with self.subTest(skill=name, term=term):
                    self.assertIn(
                        term, lowered,
                        f"{name}: description lost trigger term {term!r}",
                    )

    def test_each_skill_keeps_a_unique_discriminator(self):
        lowered = {name: d.lower() for name, d in self.descriptions.items()}
        for name, terms in REQUIRED_TERMS.items():
            present = [t for t in terms if t in lowered[name]]
            unique = [
                t for t in present
                if not any(t in lowered[other]
                           for other in lowered if other != name)
            ]
            with self.subTest(skill=name):
                self.assertTrue(
                    unique,
                    f"{name}: no required term distinguishes it from sibling "
                    f"sdd skills (present terms: {present})",
                )


if __name__ == "__main__":
    unittest.main()
