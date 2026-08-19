import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "first-party-plugins.py"

with mock.patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    SPEC = importlib.util.spec_from_file_location("first_party_plugins_cli", SCRIPT)
    assert SPEC and SPEC.loader
    cli = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(cli)

PLUGIN = {
    "name": "standalone",
    "description": "Standalone pack.",
    "manifest": {"version": "1.2.3"},
    "source": {"repository": "Xopoko/standalone", "commit": "a" * 40},
    "selection": {"default": False},
}
PAYLOAD = {"publishers": [{"id": "xopoko"}], "plugins": [PLUGIN]}


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.catalog = mock.patch.multiple(
            cli.catalog,
            validate_catalog=mock.DEFAULT,
            select_plugins=mock.DEFAULT,
            verify_remote=mock.DEFAULT,
            materialize=mock.DEFAULT,
            checkout=mock.DEFAULT,
            generate_receipt=mock.DEFAULT,
            verify_plugin_tree=mock.DEFAULT,
            receipt_for=mock.DEFAULT,
        ).start()
        self.addCleanup(mock.patch.stopall)
        self.catalog["validate_catalog"].return_value = PAYLOAD
        self.catalog["select_plugins"].return_value = [PLUGIN]

    def run_cli(self, *argv):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = cli.main(["--root", str(self.root), *argv])
        return code, stdout.getvalue(), stderr.getvalue()


class ValidateAndListTests(CliTestCase):
    def test_validate_summarizes_the_catalog(self):
        code, out, _ = self.run_cli("validate")

        self.assertEqual(0, code)
        self.assertEqual("first-party catalog valid: 1 publishers, 1 plugins\n", out)
        self.catalog["validate_catalog"].assert_called_once_with(self.root)

    def test_list_emits_pin_and_selection_columns(self):
        code, out, _ = self.run_cli("list")

        self.assertEqual(0, code)
        self.assertEqual(
            ["standalone", "1.2.3", f"Xopoko/standalone@{'a' * 40}", "default=false"],
            out.strip().split("\t"),
        )

    def test_catalog_error_is_reported_on_stderr(self):
        self.catalog["validate_catalog"].side_effect = cli.catalog.CatalogError("bad pin")

        code, out, err = self.run_cli("validate")

        self.assertEqual(2, code)
        self.assertEqual("", out)
        self.assertEqual("error: bad pin\n", err)

    def test_root_defaults_to_the_repository_checkout(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(0, cli.main(["validate"]))

        self.catalog["validate_catalog"].assert_called_once_with(ROOT)

    def test_command_is_required(self):
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            cli.main([])


class SourceCommandTests(CliTestCase):
    def test_verify_source_prints_one_json_receipt_per_selected_plugin(self):
        self.catalog["verify_remote"].return_value = {"name": "standalone", "verified": True}

        code, out, _ = self.run_cli("verify-source", "standalone")

        self.assertEqual(0, code)
        self.assertEqual({"name": "standalone", "verified": True}, json.loads(out))
        self.catalog["select_plugins"].assert_called_once_with(PAYLOAD, ["standalone"])
        self.catalog["verify_remote"].assert_called_once_with(PLUGIN, catalog_root=self.root)

    def test_materialize_passes_offline_and_cache_root(self):
        self.catalog["materialize"].return_value = self.root / "cache" / "standalone"

        code, out, _ = self.run_cli(
            "materialize", "standalone", "--offline", "--cache-root", str(self.root / "cache")
        )

        self.assertEqual(0, code)
        self.assertIn("standalone", out)
        self.catalog["materialize"].assert_called_once_with(
            self.root, "standalone", offline=True, cache_root=self.root / "cache"
        )

    def test_checkout_requires_a_destination_and_forwards_it(self):
        self.catalog["checkout"].return_value = self.root / "dest"

        code, _, _ = self.run_cli("checkout", "standalone", "--dest", str(self.root / "dest"))

        self.assertEqual(0, code)
        self.catalog["checkout"].assert_called_once_with(
            self.root, "standalone", self.root / "dest", cache_root=None
        )

    def test_receipt_skips_catalog_validation(self):
        self.catalog["generate_receipt"].return_value = "receipt.json"

        code, out, _ = self.run_cli("receipt", "standalone", "--source", str(self.root / "src"))

        self.assertEqual(0, code)
        self.assertEqual("receipt.json\n", out)
        self.catalog["validate_catalog"].assert_not_called()
        self.catalog["generate_receipt"].assert_called_once_with(
            self.root, "standalone", self.root / "src"
        )


class StatusTests(CliTestCase):
    def cache_target(self, base):
        target = base / "standalone" / ("a" * 40)
        target.mkdir(parents=True)
        return target

    def test_absent_cache_is_reported(self):
        code, out, _ = self.run_cli("status")

        self.assertEqual(0, code)
        name, state, path = out.strip().split("\t")
        self.assertEqual(("standalone", "absent"), (name, state))
        self.assertTrue(path.endswith(str(Path(".agents/first-party-sources/standalone") / ("a" * 40))))

    def test_verified_cache_is_reported_from_the_default_root(self):
        self.cache_target(self.root / ".agents" / "first-party-sources")

        code, out, _ = self.run_cli("status")

        self.assertEqual(0, code)
        self.assertEqual("verified", out.strip().split("\t")[1])
        self.catalog["verify_plugin_tree"].assert_called_once()

    def test_failed_verification_is_reported_as_invalid(self):
        target = self.cache_target(self.root / "cache")
        self.catalog["verify_plugin_tree"].side_effect = cli.catalog.CatalogError("tree drift")

        code, out, _ = self.run_cli("status", "--cache-root", str(self.root / "cache"))

        self.assertEqual(0, code)
        self.assertEqual(["standalone", "invalid", str(target)], out.strip().split("\t"))


if __name__ == "__main__":
    unittest.main()
