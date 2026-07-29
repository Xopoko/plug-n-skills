import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = ROOT / "scripts" / "install-codex-plugins.py"

spec = importlib.util.spec_from_file_location("install_codex_plugins", INSTALLER_PATH)
install_codex_plugins = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(install_codex_plugins)


class CodexInstallerTest(unittest.TestCase):
    def test_check_only_defaults_target_active_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            active_home = root / "active-codex"
            active_home.mkdir()
            argv = [
                str(INSTALLER_PATH),
                "--plugin",
                "capability-workbench",
                "--check-only",
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(
                    os.environ,
                    {"CODEX_HOME": str(active_home)},
                    clear=False,
                ),
                mock.patch.object(install_codex_plugins, "run") as run,
            ):
                install_codex_plugins.main()

            helper_command = run.call_args_list[-1].args[0]
            self.assertIn(
                str(active_home.resolve() / "config.toml"),
                helper_command,
            )
            self.assertIn(
                str(active_home.resolve() / "plugins" / "cache"),
                helper_command,
            )

    def test_explicit_state_paths_bypass_invalid_codex_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "state" / "config.toml"
            cache_root = root / "state" / "cache"
            argv = [
                str(INSTALLER_PATH),
                "--plugin",
                "capability-workbench",
                "--config-path",
                str(config_path),
                "--cache-root",
                str(cache_root),
                "--check-only",
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(
                    os.environ,
                    {"CODEX_HOME": str(root / "missing-home")},
                    clear=False,
                ),
                mock.patch.object(install_codex_plugins, "run") as run,
            ):
                install_codex_plugins.main()

            helper_command = run.call_args_list[-1].args[0]
            self.assertIn(str(config_path.resolve()), helper_command)
            self.assertIn(str(cache_root), helper_command)

    def test_invalid_codex_home_fails_before_any_installer_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            argv = [
                str(INSTALLER_PATH),
                "--plugin",
                "capability-workbench",
                "--check-only",
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(
                    os.environ,
                    {"CODEX_HOME": str(root / "missing-home")},
                    clear=False,
                ),
                mock.patch.object(install_codex_plugins, "run") as run,
                self.assertRaisesRegex(SystemExit, "existing directory"),
            ):
                install_codex_plugins.main()

            run.assert_not_called()
            self.assertFalse((root / "missing-home").exists())

    def test_invalid_personal_codex_home_fails_before_marketplace_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            home.mkdir()
            fallback = home / ".codex"
            fallback.write_bytes(b"codex-home-sentinel\n")
            marketplace_path = root / "marketplace.json"
            marketplace_path.write_bytes(b"marketplace-sentinel\n")
            argv = [
                str(INSTALLER_PATH),
                "--plugin",
                "capability-workbench",
                "--marketplace-path",
                str(marketplace_path),
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.dict(os.environ, {"HOME": str(home)}, clear=True),
                mock.patch.object(install_codex_plugins, "run") as run,
                self.assertRaisesRegex(
                    SystemExit,
                    "default Codex home must resolve to an existing directory",
                ),
            ):
                install_codex_plugins.main()

            run.assert_not_called()
            self.assertEqual(b"codex-home-sentinel\n", fallback.read_bytes())
            self.assertEqual(b"marketplace-sentinel\n", marketplace_path.read_bytes())

    def test_install_rejects_cache_symlink_before_any_control_plane_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marketplace_path = root / "marketplace.json"
            config_path = root / "config.toml"
            marketplace_path.write_bytes(b"marketplace-sentinel\n")
            config_path.write_bytes(b"config-sentinel\n")
            global_source_root = root / "legacy-plugins"
            destination = global_source_root / "capability-workbench"
            destination.mkdir(parents=True)
            source_sentinel = destination / "sentinel.txt"
            source_sentinel.write_bytes(b"source-sentinel\n")
            cache_target = root / "cache-target"
            cache_target.mkdir()
            cache_link = root / "cache-link"
            try:
                cache_link.symlink_to(cache_target, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            argv = [
                str(INSTALLER_PATH),
                "--plugin",
                "capability-workbench",
                "--global-source-root",
                str(global_source_root),
                "--marketplace-path",
                str(marketplace_path),
                "--config-path",
                str(config_path),
                "--cache-root",
                str(cache_link),
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(install_codex_plugins, "run") as run,
                self.assertRaisesRegex(SystemExit, "cache root must not be a symlink"),
            ):
                install_codex_plugins.main()

            run.assert_not_called()
            self.assertEqual(b"marketplace-sentinel\n", marketplace_path.read_bytes())
            self.assertEqual(b"config-sentinel\n", config_path.read_bytes())
            self.assertEqual(b"source-sentinel\n", source_sentinel.read_bytes())
            self.assertEqual(
                ["sentinel.txt"],
                sorted(path.name for path in destination.iterdir()),
            )

    def test_install_rejects_config_directory_before_any_control_plane_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marketplace_path = root / "marketplace.json"
            marketplace_path.write_bytes(b"marketplace-sentinel\n")
            config_directory = root / "config.toml"
            config_directory.mkdir()
            config_sentinel = config_directory / "sentinel.txt"
            config_sentinel.write_bytes(b"config-sentinel\n")
            global_source_root = root / "legacy-plugins"
            destination = global_source_root / "capability-workbench"
            destination.mkdir(parents=True)
            source_sentinel = destination / "sentinel.txt"
            source_sentinel.write_bytes(b"source-sentinel\n")
            cache_root = root / "cache"
            argv = [
                str(INSTALLER_PATH),
                "--plugin",
                "capability-workbench",
                "--global-source-root",
                str(global_source_root),
                "--marketplace-path",
                str(marketplace_path),
                "--config-path",
                str(config_directory),
                "--cache-root",
                str(cache_root),
            ]

            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(install_codex_plugins, "run") as run,
                self.assertRaisesRegex(
                    SystemExit,
                    "config path must be a regular file",
                ),
            ):
                install_codex_plugins.main()

            run.assert_not_called()
            self.assertEqual(b"marketplace-sentinel\n", marketplace_path.read_bytes())
            self.assertEqual(b"config-sentinel\n", config_sentinel.read_bytes())
            self.assertEqual(b"source-sentinel\n", source_sentinel.read_bytes())
            self.assertEqual(
                ["sentinel.txt"],
                sorted(path.name for path in destination.iterdir()),
            )

    def test_installer_plugin_names_match_repository_and_marketplace(self):
        repository_names = {
            path.parent.parent.name
            for path in (ROOT / "plugins").glob("*/.codex-plugin/plugin.json")
        }
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        marketplace_names = {entry["name"] for entry in marketplace["plugins"]}

        self.assertEqual(set(install_codex_plugins.PLUGIN_NAMES), repository_names)
        self.assertEqual(set(install_codex_plugins.PLUGIN_NAMES), marketplace_names)

    def test_marketplace_source_path_is_valid_toml_with_windows_backslashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.toml"

            install_codex_plugins.ensure_codex_marketplace_config(
                config_path=config_path,
                marketplace_root=Path("D:\\agent-work\\plug-n-skills"),
                dry_run=False,
            )

            parsed = tomllib.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(
                parsed["marketplaces"]["local"]["source"],
                "D:\\agent-work\\plug-n-skills",
            )

    def test_toml_basic_string_accepts_posix_paths(self):
        encoded = install_codex_plugins.toml_basic_string(
            "/opt/agent-work/plug-n-skills"
        )

        parsed = tomllib.loads(f"source = {encoded}\n")
        self.assertEqual(parsed["source"], "/opt/agent-work/plug-n-skills")

    def test_toml_basic_string_escapes_quotes_and_backslashes(self):
        encoded = install_codex_plugins.toml_basic_string(
            'D:\\agent-work\\Plug "N" Skills'
        )

        parsed = tomllib.loads(f"source = {encoded}\n")
        self.assertEqual(parsed["source"], 'D:\\agent-work\\Plug "N" Skills')

    def test_exclude_plugins_removes_default_plugins(self):
        selected = install_codex_plugins.select_plugins(
            None,
            ["build-swift-apps", "tauri", "pixijs", "kotlin-multiplatform"],
        )

        self.assertNotIn("build-swift-apps", selected)
        self.assertNotIn("tauri", selected)
        self.assertIn("capability-workbench", selected)

    def test_plugin_cannot_be_selected_and_excluded(self):
        with self.assertRaises(SystemExit):
            install_codex_plugins.select_plugins(["codex-cli"], ["codex-cli"])

    def test_custom_global_source_check_binds_repository_source_to_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            global_source_root = root / "plugins"
            marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
            config_path = root / "config.toml"
            cache_root = root / "cache"
            common_args = [
                sys.executable,
                str(INSTALLER_PATH),
                "--plugin",
                "capability-workbench",
                "--global-source-root",
                str(global_source_root),
                "--marketplace-path",
                str(marketplace_path),
                "--config-path",
                str(config_path),
                "--cache-root",
                str(cache_root),
            ]

            install = subprocess.run(
                common_args,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, install.returncode, install.stderr)

            global_plugin = global_source_root / "capability-workbench"
            manifest = json.loads(
                (global_plugin / ".codex-plugin" / "plugin.json").read_text(
                    encoding="utf-8"
                )
            )
            cache_plugin = (
                cache_root / "local" / "capability-workbench" / manifest["version"]
            )
            relative_file = Path("references") / "provenance.md"
            stale_content = (global_plugin / relative_file).read_text(
                encoding="utf-8"
            ) + "\nDerived stale copy.\n"
            (global_plugin / relative_file).write_text(
                stale_content,
                encoding="utf-8",
            )
            (cache_plugin / relative_file).write_text(
                stale_content,
                encoding="utf-8",
            )

            check = subprocess.run(
                [*common_args, "--check-only"],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(0, check.returncode)
            self.assertIn(
                "selected marketplace source does not match expected plugin source",
                check.stderr,
            )
            self.assertNotIn("check-only passed", check.stdout)

    def test_custom_global_install_fails_if_derived_source_diverges_after_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            global_source_root = root / "plugins"
            marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
            config_path = root / "config.toml"
            cache_root = root / "cache"
            original_sync = install_codex_plugins.sync_plugin_source

            def sync_then_diverge(source, destination, *, dry_run):
                original_sync(source, destination, dry_run=dry_run)
                provenance = destination / "references" / "provenance.md"
                provenance.write_text(
                    provenance.read_text(encoding="utf-8") + "\nDiverged after sync.\n",
                    encoding="utf-8",
                )

            argv = [
                str(INSTALLER_PATH),
                "--plugin",
                "capability-workbench",
                "--global-source-root",
                str(global_source_root),
                "--marketplace-path",
                str(marketplace_path),
                "--config-path",
                str(config_path),
                "--cache-root",
                str(cache_root),
            ]
            with (
                mock.patch.object(
                    install_codex_plugins,
                    "sync_plugin_source",
                    side_effect=sync_then_diverge,
                ),
                mock.patch.object(sys, "argv", argv),
                self.assertRaises(subprocess.CalledProcessError),
            ):
                install_codex_plugins.main()

            self.assertFalse(cache_root.exists())


if __name__ == "__main__":
    unittest.main()
