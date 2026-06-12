import importlib.util
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


if __name__ == "__main__":
    unittest.main()
