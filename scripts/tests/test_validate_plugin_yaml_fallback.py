import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = (
    ROOT
    / "plugins"
    / "capability-workbench"
    / "scripts"
    / "plugin"
    / "validate_plugin.py"
)

spec = importlib.util.spec_from_file_location("validate_plugin", VALIDATOR_PATH)
validate_plugin = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validate_plugin)


class YamlFallbackTest(unittest.TestCase):
    def test_skill_frontmatter_validates_when_pyyaml_is_unavailable(self):
        original_yaml = validate_plugin.yaml
        validate_plugin.yaml = None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                skill_root = Path(tmp) / "portable-skill"
                skill_root.mkdir()
                (skill_root / "SKILL.md").write_text(
                    "---\n"
                    "name: portable-skill\n"
                    "description: >-\n"
                    "  Validate YAML frontmatter without\n"
                    "  requiring PyYAML.\n"
                    "---\n"
                    "\n"
                    "# Portable Skill\n",
                    encoding="utf-8",
                )

                errors = []
                validate_plugin.validate_skill_manifest(skill_root, errors)

                self.assertEqual(errors, [])
        finally:
            validate_plugin.yaml = original_yaml

    def test_agent_yaml_validates_when_pyyaml_is_unavailable(self):
        original_yaml = validate_plugin.yaml
        validate_plugin.yaml = None
        try:
            with tempfile.TemporaryDirectory() as tmp:
                plugin_root = Path(tmp) / "portable-plugin"
                skill_root = plugin_root / "skills" / "portable-skill"
                agent_root = skill_root / "agents"
                agent_root.mkdir(parents=True)
                agent_yaml = agent_root / "openai.yaml"
                agent_yaml.write_text(
                    "interface:\n"
                    "  display_name: \"Portable Skill\"\n"
                    "  short_description: \"Validate YAML without PyYAML\"\n"
                    "  default_prompt: \"Use Portable Skill for validation.\"\n",
                    encoding="utf-8",
                )

                errors = []
                validate_plugin.validate_skill_agent_manifest(
                    plugin_root=plugin_root,
                    skill_root=skill_root,
                    agent_yaml_path=agent_yaml,
                    errors=errors,
                )

                self.assertEqual(errors, [])
        finally:
            validate_plugin.yaml = original_yaml


if __name__ == "__main__":
    unittest.main()
