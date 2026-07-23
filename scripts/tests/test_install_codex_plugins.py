import importlib.util
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

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
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
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


if __name__ == "__main__":
    unittest.main()
