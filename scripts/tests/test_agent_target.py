import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_target import (
    AgentResolutionError,
    AgentTarget,
    resolve_active_codex_home,
    resolve_agent,
    resolve_codex_plugin_state_paths,
)


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

    def test_codex_home_unset_and_empty_fall_back_without_requiring_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            expected = (home / ".codex").resolve()

            self.assertEqual(
                expected,
                resolve_active_codex_home(env={}, home=home, cwd=root),
            )
            self.assertEqual(
                expected,
                resolve_active_codex_home(
                    env={"CODEX_HOME": ""},
                    home=home,
                    cwd=root,
                ),
            )

    def test_codex_home_fallback_rejects_file_and_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            fallback = home / ".codex"
            fallback.write_text("not-a-directory\n", encoding="utf-8")

            with self.assertRaisesRegex(
                AgentResolutionError,
                "default Codex home must resolve to an existing directory",
            ):
                resolve_active_codex_home(env={}, home=home, cwd=root)

            fallback.unlink()
            try:
                fallback.symlink_to(root / "missing-target", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with self.assertRaisesRegex(
                AgentResolutionError,
                "default Codex home must resolve to an existing directory",
            ):
                resolve_active_codex_home(env={}, home=home, cwd=root)

    def test_codex_home_existing_absolute_and_relative_paths_are_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "profiles" / "work"
            codex_home.mkdir(parents=True)

            self.assertEqual(
                codex_home.resolve(),
                resolve_active_codex_home(
                    env={"CODEX_HOME": str(codex_home)},
                    home=root,
                    cwd=root,
                ),
            )
            self.assertEqual(
                codex_home.resolve(),
                resolve_active_codex_home(
                    env={"CODEX_HOME": "profiles/work"},
                    home=root,
                    cwd=root,
                ),
            )

    def test_codex_home_canonicalizes_directory_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            try:
                link.symlink_to(target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            self.assertEqual(
                target.resolve(),
                resolve_active_codex_home(
                    env={"CODEX_HOME": str(link)},
                    home=root,
                    cwd=root,
                ),
            )

    def test_codex_home_rejects_missing_paths_and_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_path = root / "not-a-directory"
            file_path.write_text("fixture\n", encoding="utf-8")

            for configured in (root / "missing", file_path):
                with self.subTest(configured=configured):
                    with self.assertRaisesRegex(
                        AgentResolutionError,
                        "existing directory",
                    ):
                        resolve_active_codex_home(
                            env={"CODEX_HOME": str(configured)},
                            home=root,
                            cwd=root,
                        )

    def test_explicit_plugin_state_paths_bypass_invalid_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = resolve_codex_plugin_state_paths(
                config_path="state/config.toml",
                cache_root="state/cache",
                env={"CODEX_HOME": str(root / "missing")},
                home=root,
                cwd=root,
            )

            self.assertIsNone(paths.home_dir)
            self.assertTrue(paths.config_explicit)
            self.assertTrue(paths.cache_explicit)
            self.assertEqual(
                (root / "state" / "config.toml").resolve(),
                paths.config_path,
            )
            self.assertEqual(root / "state" / "cache", paths.cache_root)

    def test_one_plugin_state_override_still_validates_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(AgentResolutionError, "existing directory"):
                resolve_codex_plugin_state_paths(
                    config_path=root / "config.toml",
                    cache_root=None,
                    env={"CODEX_HOME": str(root / "missing")},
                    home=root,
                    cwd=root,
                )

    def test_explicit_cache_root_symlink_is_rejected_before_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_target = root / "cache-target"
            cache_target.mkdir()
            cache_link = root / "cache-link"
            try:
                cache_link.symlink_to(cache_target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            with self.assertRaisesRegex(
                AgentResolutionError,
                "cache root must not be a symlink",
            ):
                resolve_codex_plugin_state_paths(
                    config_path=root / "config.toml",
                    cache_root=cache_link,
                    env={"CODEX_HOME": str(root / "missing")},
                    home=root,
                    cwd=root,
                )

    def test_existing_config_path_must_be_a_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_directory = root / "config.toml"
            config_directory.mkdir()

            with self.assertRaisesRegex(
                AgentResolutionError,
                "config path must be a regular file",
            ):
                resolve_codex_plugin_state_paths(
                    config_path=config_directory,
                    cache_root=root / "cache",
                    env={"CODEX_HOME": str(root / "missing")},
                    home=root,
                    cwd=root,
                )

    def test_plugin_state_defaults_share_one_canonical_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / "work-profile"
            codex_home.mkdir()

            paths = resolve_codex_plugin_state_paths(
                config_path=None,
                cache_root=None,
                env={"CODEX_HOME": str(codex_home)},
                home=root,
                cwd=root,
            )

            self.assertEqual(codex_home.resolve(), paths.home_dir)
            self.assertEqual(
                codex_home.resolve() / "config.toml",
                paths.config_path,
            )
            self.assertEqual(
                codex_home.resolve() / "plugins" / "cache",
                paths.cache_root,
            )

    def test_agent_target_copies_remain_identical(self):
        root_copy = Path(__file__).resolve().parents[1] / "agent_target.py"
        plugin_copy = (
            Path(__file__).resolve().parents[2]
            / "plugins"
            / "capability-workbench"
            / "scripts"
            / "agent_target.py"
        )

        self.assertEqual(root_copy.read_bytes(), plugin_copy.read_bytes())


if __name__ == "__main__":
    unittest.main()
