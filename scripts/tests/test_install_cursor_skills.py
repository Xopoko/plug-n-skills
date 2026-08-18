import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = ROOT / "scripts" / "install-cursor-skills.py"

spec = importlib.util.spec_from_file_location("install_cursor_skills", INSTALLER_PATH)
install_cursor_skills = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(install_cursor_skills)


class CursorInstallerTest(unittest.TestCase):
    def test_default_available_can_exclude_opt_in_catalog_entries(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["local", "standalone"],
            [],
            [],
            default_available=["local"],
        )

        self.assertEqual([], unknown)
        self.assertEqual(["local"], selected)

    def test_exclude_plugins_removes_default_plugins(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["a", "b", "c"],
            [],
            ["b"],
        )

        self.assertEqual(unknown, [])
        self.assertEqual(selected, ["a", "c"])

    def test_unknown_include_or_exclude_is_reported(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["a", "b"],
            ["a"],
            ["missing"],
        )

        self.assertEqual(selected, [])
        self.assertEqual(unknown, ["missing"])

    def test_plugin_cannot_be_selected_and_excluded(self):
        with self.assertRaises(SystemExit):
            install_cursor_skills.select_plugins(["a"], ["a"], ["a"])

    def test_legacy_git_plugin_names_route_to_one_consolidated_plugin(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["git-workflows", "technology-intelligence"],
            ["gitlab-review", "stacked-delivery", "git-worktree-safety"],
            [],
        )

        self.assertEqual(unknown, [])
        self.assertEqual(selected, ["git-workflows"])

    def test_legacy_git_alias_conflicts_with_canonical_exclusion(self):
        with self.assertRaises(SystemExit):
            install_cursor_skills.select_plugins(
                ["git-workflows"],
                ["gitlab-review"],
                ["git-workflows"],
            )

    def test_legacy_harness_plugin_names_route_to_one_consolidated_plugin(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["agent-harness", "capability-workbench"],
            ["codex-cli", "claude-code", "scheduled-automation"],
            [],
        )

        self.assertEqual(unknown, [])
        self.assertEqual(selected, ["agent-harness"])

    def test_legacy_harness_alias_conflicts_with_canonical_exclusion(self):
        with self.assertRaises(SystemExit):
            install_cursor_skills.select_plugins(
                ["agent-harness"],
                ["claude-code"],
                ["agent-harness"],
            )

    def test_legacy_harness_alias_excludes_canonical_default(self):
        selected, unknown = install_cursor_skills.select_plugins(
            ["agent-harness", "capability-workbench"],
            [],
            ["scheduled-automation"],
        )

        self.assertEqual(unknown, [])
        self.assertEqual(selected, ["capability-workbench"])


def write_skill(plugin_dir: Path, name: str, body: str = "# skill\n") -> Path:
    skill_dir = plugin_dir / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8")
    return skill_dir


class SourceDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_repo_root_points_at_the_checkout(self):
        self.assertEqual(ROOT, install_cursor_skills.repo_root())

    def test_local_plugin_names_requires_a_codex_manifest(self):
        for name in ("beta", "alpha"):
            manifest = self.root / "plugins" / name / ".codex-plugin" / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}", encoding="utf-8")
        (self.root / "plugins" / "no-manifest").mkdir()

        self.assertEqual(["alpha", "beta"], install_cursor_skills.local_plugin_names(self.root))

    def test_skill_dirs_requires_a_skill_file(self):
        plugin_dir = self.root / "plugin"
        write_skill(plugin_dir, "second")
        write_skill(plugin_dir, "first")
        (plugin_dir / "skills" / "empty").mkdir()

        self.assertEqual(
            ["first", "second"],
            [path.name for path in install_cursor_skills.skill_dirs(plugin_dir)],
        )

    def test_skill_dirs_is_empty_without_a_skills_directory(self):
        self.assertEqual([], install_cursor_skills.skill_dirs(self.root / "plugin"))

    def test_tree_fingerprint_ignores_bytecode_caches_and_tracks_content(self):
        source = write_skill(self.root / "plugin", "demo")
        copy = write_skill(self.root / "copy", "demo")
        baseline = install_cursor_skills.tree_fingerprint(source)

        self.assertEqual(baseline, install_cursor_skills.tree_fingerprint(copy))

        (source / "__pycache__").mkdir()
        (source / "__pycache__" / "mod.pyc").write_bytes(b"cache")
        self.assertEqual(baseline, install_cursor_skills.tree_fingerprint(source))

        (source / "SKILL.md").write_text("# changed\n", encoding="utf-8")
        self.assertNotEqual(baseline, install_cursor_skills.tree_fingerprint(source))

    def test_first_party_plugins_reads_the_pinned_catalog(self):
        with mock.patch.object(
            install_cursor_skills.plugin_catalog,
            "validate_catalog",
            return_value={"plugins": [{"name": "standalone"}]},
        ) as validate:
            self.assertEqual(
                [{"name": "standalone"}], install_cursor_skills.first_party_plugins(self.root)
            )
        validate.assert_called_once_with(self.root)


class SyntheticRepoMixin:
    """Run the installer against a synthetic checkout and destination."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.dest = self.base / "skills"
        manifest = self.repo / "plugins" / "demo" / ".codex-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        write_skill(self.repo / "plugins" / "demo", "demo-skill")
        mock.patch.object(install_cursor_skills, "repo_root", return_value=self.repo).start()
        self.catalog_plugins = []
        mock.patch.object(
            install_cursor_skills,
            "first_party_plugins",
            side_effect=lambda root: self.catalog_plugins,
        ).start()
        self.addCleanup(mock.patch.stopall)

    def run_main(self, *argv, dest=True):
        args = ["install-cursor-skills.py", *argv]
        if dest:
            args.extend(["--dest", str(self.dest)])
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", args), redirect_stdout(stdout), redirect_stderr(stderr):
            code = install_cursor_skills.main()
        return code, stdout.getvalue(), stderr.getvalue()


class InstallFlowTest(SyntheticRepoMixin, unittest.TestCase):
    def test_dry_run_and_check_only_cannot_be_combined(self):
        code, _, err = self.run_main("--dry-run", "--check-only")

        self.assertEqual(2, code)
        self.assertIn("cannot be combined", err)

    def test_unknown_plugin_selection_is_rejected(self):
        code, _, err = self.run_main("--plugin", "absent")

        self.assertEqual(2, code)
        self.assertIn("unknown plugin(s): absent", err)

    def test_dry_run_reports_planned_writes_without_touching_the_destination(self):
        code, out, _ = self.run_main("--dry-run")

        self.assertEqual(0, code)
        self.assertIn(f"would install: demo-skill -> {self.dest / 'demo-skill'}", out)
        self.assertIn("dry-run: installed=0 updated=0 unchanged=0", out)
        self.assertFalse(self.dest.exists())

    def test_dry_run_reports_updates_for_existing_destinations(self):
        (self.dest / "demo-skill").mkdir(parents=True)

        code, out, _ = self.run_main("--dry-run")

        self.assertEqual(0, code)
        self.assertIn("would update: demo-skill", out)

    def test_install_copies_skills_and_converges_on_repeated_runs(self):
        code, out, _ = self.run_main()

        self.assertEqual(0, code)
        self.assertIn(f"demo-skill -> {self.dest / 'demo-skill'}", out)
        self.assertIn("installed=1 updated=0 unchanged=0", out)
        self.assertEqual("# skill\n", (self.dest / "demo-skill" / "SKILL.md").read_text(encoding="utf-8"))

        code, out, _ = self.run_main()

        self.assertEqual(0, code)
        self.assertIn("installed=0 updated=0 unchanged=1", out)

    def test_install_replaces_drifted_skills(self):
        self.run_main()
        (self.dest / "demo-skill" / "SKILL.md").write_text("# local edit\n", encoding="utf-8")
        (self.dest / "demo-skill" / "stray.md").write_text("stray\n", encoding="utf-8")

        code, out, _ = self.run_main()

        self.assertEqual(0, code)
        self.assertIn("updated=1", out)
        self.assertEqual("# skill\n", (self.dest / "demo-skill" / "SKILL.md").read_text(encoding="utf-8"))
        self.assertFalse((self.dest / "demo-skill" / "stray.md").exists())

    def test_install_excludes_bytecode_caches(self):
        cache = self.repo / "plugins" / "demo" / "skills" / "demo-skill" / "__pycache__"
        cache.mkdir()
        (cache / "mod.pyc").write_bytes(b"cache")

        self.assertEqual(0, self.run_main()[0])
        self.assertFalse((self.dest / "demo-skill" / "__pycache__").exists())

    def test_check_only_reports_missing_then_drifted_skills(self):
        code, out, _ = self.run_main("--check-only")

        self.assertEqual(1, code)
        self.assertIn("missing: demo-skill", out)
        self.assertIn("checked: drift=1 unchanged=0", out)

        self.run_main()
        (self.dest / "demo-skill" / "SKILL.md").write_text("# local edit\n", encoding="utf-8")
        code, out, _ = self.run_main("--check-only")

        self.assertEqual(1, code)
        self.assertIn("drifted: demo-skill", out)

    def test_check_only_passes_when_the_destination_matches(self):
        self.run_main()

        code, out, _ = self.run_main("--check-only")

        self.assertEqual(0, code)
        self.assertIn("checked: drift=0 unchanged=1", out)

    def test_exclusion_leaves_nothing_to_install(self):
        with self.assertRaises(SystemExit) as raised:
            self.run_main("--exclude-plugin", "demo")

        self.assertEqual(2, raised.exception.code)

    def test_flat_namespace_collisions_block_the_install(self):
        other = self.repo / "plugins" / "other"
        (other / ".codex-plugin").mkdir(parents=True)
        (other / ".codex-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
        write_skill(other, "demo-skill", "# duplicate\n")

        code, _, err = self.run_main()

        self.assertEqual(2, code)
        self.assertIn("skill name collisions; nothing installed", err)
        self.assertIn("demo-skill:", err)
        self.assertFalse(self.dest.exists())

    def test_destination_defaults_to_the_resolved_cursor_skills_dir(self):
        with mock.patch.object(
            install_cursor_skills,
            "resolve_agent",
            return_value=SimpleNamespace(skills_dir=self.dest),
        ) as resolve:
            code, out, _ = self.run_main("--dry-run", dest=False)

        self.assertEqual(0, code)
        self.assertIn(str(self.dest), out)
        resolve.assert_called_once_with(explicit="cursor")


class FirstPartyInstallTest(SyntheticRepoMixin, unittest.TestCase):
    """Standalone pinned packs are materialized from the verified cache."""

    def setUp(self):
        super().setUp()
        self.pin = {
            "name": "standalone",
            "source": {"repository": "Xopoko/standalone", "commit": "a" * 40},
            "selection": {"default": True},
        }
        self.catalog_plugins = [self.pin]

    def test_dry_run_lists_the_pin_and_its_receipt_skills(self):
        receipt = {"skills": {"items": [{"name": "standalone-skill", "path": "skills/standalone-skill"}]}}
        with mock.patch.object(
            install_cursor_skills.plugin_catalog, "receipt_for", return_value=receipt
        ):
            code, out, _ = self.run_main("--dry-run", "--plugin", "standalone")

        self.assertEqual(0, code)
        self.assertIn(f"would materialize verified pin: standalone@{'a' * 40}", out)
        self.assertIn("would install: standalone-skill", out)

    def test_dry_run_detects_collisions_against_local_skills(self):
        receipt = {"skills": {"items": [{"name": "demo-skill", "path": "skills/demo-skill"}]}}
        with mock.patch.object(
            install_cursor_skills.plugin_catalog, "receipt_for", return_value=receipt
        ):
            code, _, err = self.run_main("--dry-run", "--plugin", "demo", "--plugin", "standalone")

        self.assertEqual(2, code)
        self.assertIn("demo-skill:", err)

    def test_include_first_party_extends_the_default_selection(self):
        materialized = self.base / "cache" / "standalone"
        write_skill(materialized, "standalone-skill", "# standalone\n")
        with mock.patch.object(
            install_cursor_skills.plugin_catalog, "materialize", return_value=materialized
        ) as materialize, mock.patch.object(
            install_cursor_skills.plugin_catalog,
            "default_plugin_names",
            return_value=["standalone"],
        ):
            code, out, _ = self.run_main("--include-first-party")

        self.assertEqual(0, code)
        self.assertIn(f"demo-skill -> {self.dest / 'demo-skill'}", out)
        self.assertIn(f"standalone-skill -> {self.dest / 'standalone-skill'}", out)
        self.assertIn("installed=2 updated=0 unchanged=0", out)
        materialize.assert_called_once_with(
            self.repo, "standalone", offline=False, cache_root=None
        )

    def test_unavailable_verified_cache_fails_the_install(self):
        with mock.patch.object(
            install_cursor_skills.plugin_catalog,
            "materialize",
            side_effect=install_cursor_skills.plugin_catalog.CatalogError("cache miss"),
        ):
            code, _, err = self.run_main("--plugin", "standalone")

        self.assertEqual(1, code)
        self.assertIn("standalone: verified first-party cache unavailable: cache miss", err)

    def test_check_only_materializes_offline(self):
        materialized = self.base / "cache" / "standalone"
        write_skill(materialized, "standalone-skill", "# standalone\n")
        with mock.patch.object(
            install_cursor_skills.plugin_catalog, "materialize", return_value=materialized
        ) as materialize:
            code, out, _ = self.run_main(
                "--check-only", "--plugin", "standalone", "--first-party-cache-root", str(self.base / "cache")
            )

        self.assertEqual(1, code)
        self.assertIn("missing: standalone-skill", out)
        materialize.assert_called_once_with(
            self.repo, "standalone", offline=True, cache_root=str(self.base / "cache")
        )


if __name__ == "__main__":
    unittest.main()
