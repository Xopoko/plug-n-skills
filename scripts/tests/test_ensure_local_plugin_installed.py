import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
HELPER_PATH = (
    ROOT
    / "plugins"
    / "capability-workbench"
    / "scripts"
    / "plugin"
    / "ensure_local_plugin_installed.py"
)

sys.path.insert(0, str(HELPER_PATH.parent))
spec = importlib.util.spec_from_file_location(
    "ensure_local_plugin_installed",
    HELPER_PATH,
)
ensure_local_plugin_installed = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = ensure_local_plugin_installed
spec.loader.exec_module(ensure_local_plugin_installed)


class LocalPluginVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.plugin_root = self.root / "plugins" / "fixture-plugin"
        self.marketplace_path = self.root / ".agents" / "plugins" / "marketplace.json"
        self.config_path = self.root / "config.toml"
        self.cache_root = self.root / "cache"
        self.cache_path = self.cache_root / "local" / "fixture-plugin" / "0.1.0"

        (self.plugin_root / ".codex-plugin").mkdir(parents=True)
        (self.plugin_root / "skills" / "fixture-skill").mkdir(parents=True)
        manifest = {
            "name": "fixture-plugin",
            "version": "0.1.0",
            "description": "Fixture plugin.",
            "author": {"name": "Test"},
            "skills": "./skills/",
            "interface": {
                "displayName": "Fixture Plugin",
                "shortDescription": "Fixture plugin for visibility tests.",
                "longDescription": "Fixture plugin for cache visibility tests.",
                "developerName": "Test",
                "category": "Productivity",
                "capabilities": ["Testing"],
                "defaultPrompt": "Use the fixture plugin.",
            },
        }
        (self.plugin_root / ".codex-plugin" / "plugin.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        (self.plugin_root / "skills" / "fixture-skill" / "SKILL.md").write_text(
            "---\n"
            "name: fixture-skill\n"
            "description: Use for cache visibility fixture tests.\n"
            "---\n\n"
            "# Fixture\n",
            encoding="utf-8",
        )
        (self.plugin_root / "README.md").write_text(
            "# Fixture plugin\n",
            encoding="utf-8",
        )

        self.marketplace_path.parent.mkdir(parents=True)
        self.marketplace_path.write_text(
            json.dumps(
                {
                    "name": "local",
                    "plugins": [
                        {
                            "name": "fixture-plugin",
                            "source": {
                                "source": "local",
                                "path": "./plugins/fixture-plugin",
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.config_path.write_text(
            '[plugins."fixture-plugin@local"]\n' "enabled = true\n",
            encoding="utf-8",
        )
        self.materialize_cache()

    def materialize_cache(self):
        ensure_local_plugin_installed.ensure_cache_materialized(
            plugin_root=self.plugin_root,
            cache_path=self.cache_path,
            dry_run=False,
        )

    def check_only(self):
        return ensure_local_plugin_installed.ensure_installed(
            plugin_path=self.plugin_root,
            marketplace_path=self.marketplace_path,
            config_path=self.config_path,
            cache_root=self.cache_root,
            codex_bin="codex",
            check_only=True,
        )

    def run_cli(self, *extra_args):
        return subprocess.run(
            [
                sys.executable,
                str(HELPER_PATH),
                str(self.plugin_root),
                "--marketplace-path",
                str(self.marketplace_path),
                "--config-path",
                str(self.config_path),
                "--cache-root",
                str(self.cache_root),
                *extra_args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_identical_source_and_cache_verify_stably(self):
        outcome = self.check_only()

        self.assertTrue(outcome.source_validated)
        self.assertTrue(outcome.install_state_verified)
        self.assertTrue(self.check_only().install_state_verified)

    def test_changed_cached_file_fails_install_state_verification(self):
        (self.cache_path / "README.md").write_text(
            "# Stale fixture plugin\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            ValueError,
            r"cache content does not match plugin source.*content-different=1",
        ):
            self.check_only()

    def test_missing_and_unexpected_cached_files_fail_verification(self):
        cached_skill = self.cache_path / "skills" / "fixture-skill" / "SKILL.md"
        cached_skill.unlink()
        with self.assertRaisesRegex(ValueError, r"missing=1"):
            self.check_only()

        self.materialize_cache()
        (self.cache_path / "unexpected.txt").write_text(
            "unexpected\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, r"unexpected=1"):
            self.check_only()

    def test_runtime_transients_are_ignored(self):
        (self.cache_path / ".DS_Store").write_bytes(b"host metadata")
        bytecode = (
            self.cache_path / "skills" / "fixture-skill" / "__pycache__" / "helper.pyc"
        )
        bytecode.parent.mkdir(parents=True)
        bytecode.write_bytes(b"generated bytecode")
        git_metadata = self.cache_path / ".git" / "config"
        git_metadata.parent.mkdir()
        git_metadata.write_text("[core]\n", encoding="utf-8")

        outcome = self.check_only()

        self.assertTrue(outcome.install_state_verified)

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not portable on Windows")
    def test_cached_file_mode_change_fails_verification(self):
        cached_readme = self.cache_path / "README.md"
        cached_readme.chmod(cached_readme.stat().st_mode ^ 0o100)

        with self.assertRaisesRegex(ValueError, r"mode-different=1"):
            self.check_only()

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not portable on Windows")
    def test_cached_root_mode_change_fails_verification(self):
        self.cache_path.chmod(self.cache_path.stat().st_mode ^ 0o020)

        with self.assertRaisesRegex(ValueError, r"mode-different=1"):
            self.check_only()

    def test_source_symlink_is_rejected_before_cache_replacement(self):
        external = self.root / "external.txt"
        external.write_text("sentinel-private-content\n", encoding="utf-8")
        link = self.plugin_root / "linked.txt"
        try:
            link.symlink_to(external)
        except OSError as err:
            self.skipTest(f"symlinks unavailable: {err}")
        cached_readme = (self.cache_path / "README.md").read_bytes()

        with self.assertRaisesRegex(ValueError, r"must not contain symlinks") as error:
            self.materialize_cache()

        self.assertNotIn("sentinel-private-content", str(error.exception))
        self.assertEqual(cached_readme, (self.cache_path / "README.md").read_bytes())

    def test_unsafe_source_is_rejected_before_cli_or_config_mutation(self):
        external = self.root / "external.txt"
        external.write_text("sentinel-private-content\n", encoding="utf-8")
        try:
            (self.plugin_root / "linked.txt").symlink_to(external)
        except OSError as err:
            self.skipTest(f"symlinks unavailable: {err}")
        missing_config = self.root / "missing-config.toml"

        with mock.patch.object(
            ensure_local_plugin_installed,
            "try_cli_install",
            return_value="installed",
        ) as cli_install:
            with self.assertRaisesRegex(ValueError, r"must not contain symlinks"):
                ensure_local_plugin_installed.ensure_installed(
                    plugin_path=self.plugin_root,
                    marketplace_path=self.marketplace_path,
                    config_path=missing_config,
                    cache_root=self.cache_root,
                    codex_bin="codex",
                )

        cli_install.assert_not_called()
        self.assertFalse(missing_config.exists())

    def test_successful_cli_result_still_requires_cache_equivalence(self):
        (self.cache_path / "README.md").write_text(
            "# Stale fixture plugin\n",
            encoding="utf-8",
        )

        with mock.patch.object(
            ensure_local_plugin_installed,
            "try_cli_install",
            return_value="installed",
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"cache content does not match plugin source",
            ):
                ensure_local_plugin_installed.ensure_installed(
                    plugin_path=self.plugin_root,
                    marketplace_path=self.marketplace_path,
                    config_path=self.config_path,
                    cache_root=self.cache_root,
                    codex_bin="codex",
                )

    def test_expected_source_must_match_selected_source_and_cache(self):
        expected_source = self.root / "expected-source"
        shutil.copytree(self.plugin_root, expected_source)

        outcome = ensure_local_plugin_installed.ensure_installed(
            plugin_path=self.plugin_root,
            marketplace_path=self.marketplace_path,
            config_path=self.config_path,
            cache_root=self.cache_root,
            codex_bin="codex",
            expected_source_path=expected_source,
            check_only=True,
        )

        self.assertTrue(outcome.expected_source_verified)
        changed_text = "# Derived stale fixture plugin\n"
        (self.plugin_root / "README.md").write_text(changed_text, encoding="utf-8")
        (self.cache_path / "README.md").write_text(changed_text, encoding="utf-8")

        with self.assertRaisesRegex(
            ValueError,
            r"selected marketplace source does not match expected plugin source"
            r".*content-different=1",
        ):
            ensure_local_plugin_installed.ensure_installed(
                plugin_path=self.plugin_root,
                marketplace_path=self.marketplace_path,
                config_path=self.config_path,
                cache_root=self.cache_root,
                codex_bin="codex",
                expected_source_path=expected_source,
                check_only=True,
            )

    def test_expected_selected_and_cache_share_one_anchored_snapshot(self):
        expected_source = self.root / "expected-source"
        shutil.copytree(self.plugin_root, expected_source)
        original_config_check = ensure_local_plugin_installed.ensure_config_enabled
        mutated = False

        def mutate_between_source_and_cache_checks(*args, **kwargs):
            nonlocal mutated
            result = original_config_check(*args, **kwargs)
            if not mutated:
                mutated = True
                changed_text = "# Changed between verification phases\n"
                (self.plugin_root / "README.md").write_text(
                    changed_text,
                    encoding="utf-8",
                )
                (self.cache_path / "README.md").write_text(
                    changed_text,
                    encoding="utf-8",
                )
            return result

        with mock.patch.object(
            ensure_local_plugin_installed,
            "ensure_config_enabled",
            side_effect=mutate_between_source_and_cache_checks,
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"(selected marketplace source does not match expected plugin source"
                r"|plugin source changed after validation)",
            ):
                ensure_local_plugin_installed.ensure_installed(
                    plugin_path=self.plugin_root,
                    marketplace_path=self.marketplace_path,
                    config_path=self.config_path,
                    cache_root=self.cache_root,
                    codex_bin="codex",
                    expected_source_path=expected_source,
                    check_only=True,
                )

    def test_source_validation_is_bound_to_final_cache_snapshot(self):
        original_provenance_check = ensure_local_plugin_installed.verify_expected_source

        def invalidate_after_source_check(**kwargs):
            result = original_provenance_check(**kwargs)
            relative_skill = Path("skills") / "fixture-skill" / "SKILL.md"
            (self.plugin_root / relative_skill).unlink()
            (self.cache_path / relative_skill).unlink()
            return result

        with mock.patch.object(
            ensure_local_plugin_installed,
            "verify_expected_source",
            side_effect=invalidate_after_source_check,
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"plugin source changed after validation",
            ):
                self.check_only()

    def test_enabled_config_is_revalidated_after_tree_verification(self):
        original_tree_check = (
            ensure_local_plugin_installed.ensure_installation_state_matches
        )

        def verify_then_disable(**kwargs):
            original_tree_check(**kwargs)
            self.config_path.write_text(
                '[plugins."fixture-plugin@local"]\n' "enabled = false\n",
                encoding="utf-8",
            )

        with mock.patch.object(
            ensure_local_plugin_installed,
            "ensure_installation_state_matches",
            side_effect=verify_then_disable,
        ):
            with self.assertRaisesRegex(ValueError, r"does not enable"):
                self.check_only()

    def test_marketplace_selection_is_revalidated_after_tree_verification(self):
        original_tree_check = (
            ensure_local_plugin_installed.ensure_installation_state_matches
        )

        def verify_then_redirect(**kwargs):
            original_tree_check(**kwargs)
            marketplace = json.loads(self.marketplace_path.read_text(encoding="utf-8"))
            marketplace["plugins"][0]["source"]["path"] = "./plugins/redirected-plugin"
            self.marketplace_path.write_text(
                json.dumps(marketplace),
                encoding="utf-8",
            )

        with mock.patch.object(
            ensure_local_plugin_installed,
            "ensure_installation_state_matches",
            side_effect=verify_then_redirect,
        ):
            with self.assertRaisesRegex(
                FileNotFoundError,
                r"resolves to missing source path",
            ):
                self.check_only()

    def test_overlapping_cache_parent_is_rejected_before_writes(self):
        overlapping_cache = (
            self.plugin_root / "runtime-cache" / "fixture-plugin" / "0.1.0"
        )

        with self.assertRaisesRegex(ValueError, r"must be disjoint"):
            ensure_local_plugin_installed.ensure_cache_materialized(
                plugin_root=self.plugin_root,
                cache_path=overlapping_cache,
                dry_run=False,
            )

        self.assertFalse((self.plugin_root / "runtime-cache").exists())

    def test_expected_source_inside_cache_deletion_scope_is_preserved(self):
        expected_source = self.cache_path.parent / "9.9.9"
        shutil.copytree(self.plugin_root, expected_source)
        cached_readme = (self.cache_path / "README.md").read_bytes()

        with self.assertRaisesRegex(ValueError, r"must be disjoint"):
            ensure_local_plugin_installed.ensure_installed(
                plugin_path=self.plugin_root,
                marketplace_path=self.marketplace_path,
                config_path=self.config_path,
                cache_root=self.cache_root,
                codex_bin="codex",
                expected_source_path=expected_source,
                force_manual=True,
            )

        self.assertTrue(expected_source.is_dir())
        self.assertEqual(
            cached_readme,
            (self.cache_path / "README.md").read_bytes(),
        )

    def test_unsafe_install_identifiers_cannot_retarget_cache_pruning(self):
        victim = self.cache_root / "victim" / "9.9.9" / "sentinel.txt"
        victim.parent.mkdir(parents=True)
        victim.write_text("keep\n", encoding="utf-8")
        manifest_path = self.plugin_root / ".codex-plugin" / "plugin.json"
        marketplace_payload = json.loads(
            self.marketplace_path.read_text(encoding="utf-8")
        )

        for field, unsafe_name in (
            ("plugin", "../victim"),
            ("marketplace", "../victim-marketplace"),
        ):
            with self.subTest(field=field):
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["name"] = (
                    unsafe_name if field == "plugin" else "fixture-plugin"
                )
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                marketplace_payload["name"] = (
                    unsafe_name if field == "marketplace" else "local"
                )
                marketplace_payload["plugins"][0]["name"] = manifest["name"]
                self.marketplace_path.write_text(
                    json.dumps(marketplace_payload),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(
                    ValueError,
                    rf"{field} name must start with an ASCII letter or digit",
                ):
                    ensure_local_plugin_installed.ensure_installed(
                        plugin_path=self.plugin_root,
                        marketplace_path=self.marketplace_path,
                        config_path=self.root / f"{field}-config.toml",
                        cache_root=self.cache_root,
                        codex_bin="codex",
                        force_manual=True,
                    )

                self.assertEqual("keep\n", victim.read_text(encoding="utf-8"))

    def test_symlinked_plugin_and_cache_roots_are_rejected(self):
        plugin_link = self.root / "linked-plugin"
        cache_link = self.root / "linked-cache"
        try:
            plugin_link.symlink_to(self.plugin_root, target_is_directory=True)
            cache_link.symlink_to(self.cache_root, target_is_directory=True)
        except OSError as err:
            self.skipTest(f"symlinks unavailable: {err}")

        with self.assertRaisesRegex(ValueError, r"plugin source root must not be"):
            ensure_local_plugin_installed.ensure_installed(
                plugin_path=plugin_link,
                marketplace_path=self.marketplace_path,
                config_path=self.config_path,
                cache_root=self.cache_root,
                codex_bin="codex",
                check_only=True,
            )
        with self.assertRaisesRegex(ValueError, r"plugin cache root must not be"):
            ensure_local_plugin_installed.ensure_installed(
                plugin_path=self.plugin_root,
                marketplace_path=self.marketplace_path,
                config_path=self.config_path,
                cache_root=cache_link,
                codex_bin="codex",
                check_only=True,
            )

    def test_symlinked_cache_component_is_rejected_before_writes(self):
        guarded_cache = self.root / "guarded-cache"
        redirected = guarded_cache / "redirected"
        redirected.mkdir(parents=True)
        sentinel = redirected / "sentinel.txt"
        sentinel.write_text("keep\n", encoding="utf-8")
        try:
            (guarded_cache / "local").symlink_to(
                redirected,
                target_is_directory=True,
            )
        except OSError as err:
            self.skipTest(f"symlinks unavailable: {err}")

        with self.assertRaisesRegex(ValueError, r"components must not be symlinks"):
            ensure_local_plugin_installed.ensure_installed(
                plugin_path=self.plugin_root,
                marketplace_path=self.marketplace_path,
                config_path=self.root / "guarded-config.toml",
                cache_root=guarded_cache,
                codex_bin="codex",
                force_manual=True,
            )

        self.assertEqual("keep\n", sentinel.read_text(encoding="utf-8"))
        self.assertFalse((self.root / "guarded-config.toml").exists())

    def test_tree_changes_during_verification_fail_closed(self):
        stable = {
            ".": ensure_local_plugin_installed.TreeEntry(
                kind="directory",
                mode=0o755,
                size=0,
                content_digest="",
            )
        }
        changed = {
            ".": stable["."],
            "changed.txt": ensure_local_plugin_installed.TreeEntry(
                kind="file",
                mode=0o644,
                size=1,
                content_digest="0" * 64,
            ),
        }

        with mock.patch.object(
            ensure_local_plugin_installed,
            "build_installable_tree_manifest",
            side_effect=[stable, stable, changed, stable],
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"changed during verification",
            ):
                ensure_local_plugin_installed.ensure_installable_trees_match(
                    expected_root=self.plugin_root,
                    actual_root=self.cache_path,
                    mismatch_subject="trees differ",
                    remediation="stabilize them",
                )

    def test_file_symlink_swap_is_rejected_before_target_bytes_are_read(self):
        candidate = self.root / "candidate.txt"
        external = self.root / "external-private.txt"
        candidate.write_text("safe\n", encoding="utf-8")
        external.write_text("PRIVATE_SENTINEL=external\n", encoding="utf-8")
        metadata = candidate.stat(follow_symlinks=False)
        candidate.unlink()
        try:
            candidate.symlink_to(external)
        except OSError as err:
            self.skipTest(f"symlinks unavailable: {err}")

        with self.assertRaisesRegex(
            ValueError,
            r"changed or contains an unsafe file",
        ) as error:
            ensure_local_plugin_installed.digest_file(
                candidate,
                expected_metadata=metadata,
            )

        self.assertNotIn("PRIVATE_SENTINEL", str(error.exception))

    def test_internal_tree_digest_uses_canonical_utf8_names(self):
        (self.plugin_root / "café.txt").write_text("coffee\n", encoding="utf-8")
        self.materialize_cache()

        first = ensure_local_plugin_installed.digest_tree_manifest(
            ensure_local_plugin_installed.build_installable_tree_manifest(
                self.plugin_root
            )
        )
        second = ensure_local_plugin_installed.digest_tree_manifest(
            ensure_local_plugin_installed.build_installable_tree_manifest(
                self.plugin_root
            )
        )

        self.assertEqual(first, second)
        with self.assertRaisesRegex(ValueError, r"encodable as UTF-8"):
            ensure_local_plugin_installed.canonical_utf8("\udcff")

    def test_dry_run_does_not_verify_install_or_invoke_cli(self):
        dry_cache_root = self.root / "dry-cache"
        with mock.patch.object(
            ensure_local_plugin_installed,
            "try_cli_install",
            return_value="installed",
        ) as cli_install:
            outcome = ensure_local_plugin_installed.ensure_installed(
                plugin_path=self.plugin_root,
                marketplace_path=self.marketplace_path,
                config_path=self.root / "missing-config.toml",
                cache_root=dry_cache_root,
                codex_bin="codex",
                dry_run=True,
            )

        cli_install.assert_not_called()
        self.assertFalse(outcome.install_state_verified)
        self.assertFalse(dry_cache_root.exists())

    def test_cli_dry_run_reports_required_changes_without_claiming_writes(self):
        result = self.run_cli(
            "--dry-run",
            "--config-path",
            str(self.root / "dry-run-config.toml"),
            "--cache-root",
            str(self.root / "dry-run-cache"),
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("install mode: dry-run", result.stdout)
        self.assertIn("config change required: true", result.stdout)
        self.assertIn("cache refresh required: true", result.stdout)
        self.assertIn("install/cache state verified: false", result.stdout)
        self.assertNotIn("config changed: true", result.stdout)
        self.assertNotIn("cache changed: true", result.stdout)
        self.assertFalse((self.root / "dry-run-config.toml").exists())
        self.assertFalse((self.root / "dry-run-cache").exists())

    def test_check_only_and_dry_run_are_mutually_exclusive(self):
        result = self.run_cli("--check-only", "--dry-run")

        self.assertEqual(1, result.returncode)
        self.assertIn("cannot be combined", result.stderr)

    def test_cli_receipt_separates_install_state_from_runtime_discovery(self):
        result = self.run_cli("--check-only")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("source validated: true", result.stdout)
        self.assertIn("install/cache state verified: true", result.stdout)
        self.assertIn("runtime discovery: not checked", result.stdout)
        self.assertNotIn("sha256:", result.stdout)
        self.assertNotIn("visibility check passed", result.stdout)

    def test_cli_mismatch_fails_without_a_success_receipt(self):
        (self.cache_path / "README.md").write_text(
            "# Stale fixture plugin\n",
            encoding="utf-8",
        )

        result = self.run_cli("--check-only")

        self.assertEqual(1, result.returncode)
        self.assertIn("cache content does not match plugin source", result.stderr)
        self.assertNotIn("install/cache state verified: true", result.stdout)
        self.assertNotIn("visibility check passed", result.stdout)

    def test_mismatch_output_does_not_expose_private_file_details(self):
        private_name = ".env"
        private_source = "PRIVATE_SENTINEL=small-secret\n"
        (self.plugin_root / private_name).write_text(
            private_source,
            encoding="utf-8",
        )
        self.materialize_cache()
        (self.cache_path / private_name).write_text(
            "PRIVATE_SENTINEL=other-secret\n",
            encoding="utf-8",
        )

        result = self.run_cli("--check-only")
        combined = f"{result.stdout}\n{result.stderr}"

        self.assertEqual(1, result.returncode)
        self.assertIn("content-different=1", result.stderr)
        self.assertNotIn(private_name, combined)
        self.assertNotIn("small-secret", combined)
        self.assertNotIn("other-secret", combined)
        self.assertNotIn(str(self.root), combined)
        self.assertNotIn("sha256:", combined)


if __name__ == "__main__":
    unittest.main()
