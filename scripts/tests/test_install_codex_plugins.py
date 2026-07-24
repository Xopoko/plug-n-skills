import importlib.util
import json
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
