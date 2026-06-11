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

    def test_cursor_env_markers(self):
        t = resolve_agent(explicit=None, env={"CURSOR_TRACE_ID": "abc"},
                          home=Path("/home/u"), home_exists=lambda p: False)
        self.assertEqual(t.agent, "cursor")
        self.assertEqual(t.skills_dir, Path("/home/u/.cursor/skills"))

    def test_cursor_has_no_marketplace(self):
        t = resolve_agent(explicit="cursor", env={}, home=Path("/home/u"),
                          home_exists=lambda p: True)
        self.assertIsNone(t.marketplace_path)

    def test_claude_wins_inside_cursor_ide(self):
        # Claude Code running in a Cursor terminal sees both marker sets.
        t = resolve_agent(explicit=None,
                          env={"CLAUDECODE": "1", "CURSOR_TRACE_ID": "abc"},
                          home=Path("/home/u"), home_exists=lambda p: False)
        self.assertEqual(t.agent, "claude")

    def test_codex_home_env(self):
        t = resolve_agent(explicit=None, env={"CODEX_HOME": "/x/.codex"},
                          home=Path("/home/u"), home_exists=lambda p: False)
        self.assertEqual(t.agent, "codex")
        self.assertEqual(t.home_dir, Path("/x/.codex"))

    def test_falls_back_to_only_existing_home(self):
        for agent in ("codex", "claude", "cursor"):
            only = lambda p, marker=f".{agent}": p.name == marker
            t = resolve_agent(explicit=None, env={}, home=Path("/home/u"),
                              home_exists=only)
            self.assertEqual(t.agent, agent)

    def test_ambiguous_multiple_present_raises(self):
        with self.assertRaises(AgentResolutionError) as ctx:
            resolve_agent(explicit=None, env={}, home=Path("/home/u"),
                          home_exists=lambda p: True)
        self.assertIn("multiple", str(ctx.exception))
        self.assertIn("AGENT_TARGET", str(ctx.exception))

    def test_none_present_raises(self):
        with self.assertRaises(AgentResolutionError) as ctx:
            resolve_agent(explicit=None, env={}, home=Path("/home/u"),
                          home_exists=lambda p: False)
        self.assertIn("no agent home", str(ctx.exception))

    def test_resolution_is_idempotent(self):
        kwargs = dict(explicit=None, env={"AGENT_TARGET": "cursor"},
                      home=Path("/home/u"), home_exists=lambda p: True)
        self.assertEqual(resolve_agent(**kwargs), resolve_agent(**kwargs))


if __name__ == "__main__":
    unittest.main()
