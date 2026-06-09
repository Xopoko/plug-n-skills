import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_target import resolve_agent, AgentTarget, AgentResolutionError


class ResolveAgentTest(unittest.TestCase):
    def test_explicit_flag_wins(self):
        t = resolve_agent(explicit="claude", env={}, home=Path("/home/u"),
                           home_exists=lambda p: True)
        self.assertIsInstance(t, AgentTarget)
        self.assertEqual(t.agent, "claude")
        self.assertEqual(t.skills_dir, Path("/home/u/.claude/skills"))

    def test_env_agent_target(self):
        t = resolve_agent(explicit=None, env={"AGENT_TARGET": "codex"},
                          home=Path("/home/u"), home_exists=lambda p: True)
        self.assertEqual(t.agent, "codex")
        self.assertEqual(t.skills_dir, Path("/home/u/.codex/skills"))
        self.assertEqual(t.marketplace_path,
                         Path("/home/u/.agents/plugins/marketplace.json"))

    def test_claude_env_markers(self):
        t = resolve_agent(explicit=None, env={"CLAUDECODE": "1"},
                          home=Path("/home/u"), home_exists=lambda p: False)
        self.assertEqual(t.agent, "claude")

    def test_codex_home_env(self):
        t = resolve_agent(explicit=None, env={"CODEX_HOME": "/x/.codex"},
                          home=Path("/home/u"), home_exists=lambda p: False)
        self.assertEqual(t.agent, "codex")

    def test_falls_back_to_only_existing_home(self):
        only_claude = lambda p: p.name == ".claude"
        t = resolve_agent(explicit=None, env={}, home=Path("/home/u"),
                          home_exists=only_claude)
        self.assertEqual(t.agent, "claude")

    def test_ambiguous_both_present_raises(self):
        with self.assertRaises(AgentResolutionError) as ctx:
            resolve_agent(explicit=None, env={}, home=Path("/home/u"),
                          home_exists=lambda p: True)
        self.assertIn("both", str(ctx.exception))

    def test_neither_present_raises(self):
        with self.assertRaises(AgentResolutionError) as ctx:
            resolve_agent(explicit=None, env={}, home=Path("/home/u"),
                          home_exists=lambda p: False)
        self.assertIn("neither", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
