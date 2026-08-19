import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-repository.py"

SPEC = importlib.util.spec_from_file_location("validate_repository", SCRIPT)
assert SPEC and SPEC.loader
validate_repository = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate_repository)

# Forbidden-content probes are assembled from fragments so this test file stays
# clean for the scanner it exercises.
CYRILLIC_WORD = "".join(chr(code) for code in (0x043F, 0x0440, 0x0438))
LOCAL_HOME_PATH = "/" + "Users/" + "someone/" + "notes.md"
LOCAL_PROJECT_PATH = "~/" + "Projects/" + "demo"
PRIVATE_PROJECT = "PAN-" + "1234"
GRANDIOSE_WORD = "world-" + "class"
PRIVATE_ORG_WORD = "custom" + "ers"
LEGACY_BRAND = "xopoko-" + "power" + "packs"
PRIVATE_TOOL = "codex-" + "token-" + "lens"
FAKE_SECRET = "sk-" + "a" * 24


def manifest(**overrides):
    payload = {
        "name": "demo",
        "license": "MIT",
        "repository": "https://github.com/Xopoko/plug-n-skills",
        "author": {"name": "Xopoko"},
        "interface": {
            "websiteURL": validate_repository.CATALOG_WEBSITE_URL,
            "developerName": "Xopoko",
        },
    }
    payload.update(overrides)
    return payload


class TempRootTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patcher = mock.patch.object(validate_repository, "repo_root", return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_json(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def write_text(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class LoadJsonTests(TempRootTestCase):
    def test_object_payload_is_returned(self):
        path = self.write_json("a.json", {"key": "value"})
        errors = []

        self.assertEqual({"key": "value"}, validate_repository.load_json(path, errors))
        self.assertEqual([], errors)

    def test_missing_file_is_reported(self):
        errors = []

        self.assertIsNone(validate_repository.load_json(self.root / "absent.json", errors))
        self.assertEqual(1, len(errors))
        self.assertIn("missing JSON file", errors[0])

    def test_invalid_json_is_reported(self):
        path = self.write_text("bad.json", "{")
        errors = []

        self.assertIsNone(validate_repository.load_json(path, errors))
        self.assertIn("invalid JSON", errors[0])

    def test_non_object_payload_is_reported(self):
        path = self.write_json("list.json", ["a"])
        errors = []

        self.assertIsNone(validate_repository.load_json(path, errors))
        self.assertIn("must contain an object", errors[0])


class ManifestMetadataTests(unittest.TestCase):
    def check(self, payload):
        errors = []
        validate_repository.validate_manifest_metadata("demo", payload, errors)
        return errors

    def test_compliant_manifest_produces_no_errors(self):
        self.assertEqual([], self.check(manifest()))

    def test_name_license_and_repository_are_enforced(self):
        errors = self.check(
            manifest(name="other", license="Apache-2.0", repository="git@github.com:x/y.git")
        )

        self.assertEqual(3, len(errors))
        self.assertTrue(any("manifest name must match directory" in item for item in errors))
        self.assertTrue(any("license must be MIT" in item for item in errors))
        self.assertTrue(any("repository must be a GitHub URL" in item for item in errors))

    def test_local_only_branding_is_rejected(self):
        errors = self.check(
            manifest(
                author={"name": "Local Author"},
                interface={
                    "websiteURL": validate_repository.CATALOG_WEBSITE_URL,
                    "developerName": "Local Dev",
                },
            )
        )

        self.assertEqual(2, len(errors))
        self.assertTrue(any("author name" in item for item in errors))
        self.assertTrue(any("developerName" in item for item in errors))

    def test_interface_must_be_an_object_with_the_catalog_website(self):
        self.assertIn("interface must be an object", self.check(manifest(interface="nope"))[0])
        self.assertIn(
            "interface.websiteURL must be",
            self.check(manifest(interface={"websiteURL": "https://example.invalid"}))[0],
        )


class MarketplaceTests(TempRootTestCase):
    def setUp(self):
        super().setUp()
        self.first_party = {
            "standalone": {
                "name": "standalone",
                "description": "Standalone pack.",
                "manifest": {"version": "1.2.3"},
                "source": {"repository": "Xopoko/standalone", "commit": "a" * 40},
            }
        }

    def local_plugin(self, name):
        self.write_json(f"plugins/{name}/.claude-plugin/plugin.json", {"name": name})

    def marketplace(self, plugins, schema=None):
        self.write_json(
            ".claude-plugin/marketplace.json",
            {
                "$schema": schema or "https://json.schemastore.org/claude-code-marketplace.json",
                "plugins": plugins,
            },
        )

    def standalone_entry(self, **overrides):
        entry = {
            "name": "standalone",
            "source": {"source": "github", "repo": "Xopoko/standalone", "sha": "a" * 40},
            "description": "Standalone pack.",
            "version": "1.2.3",
        }
        entry.update(overrides)
        return entry

    def validate(self, local_names=("demo",)):
        return validate_repository.validate_marketplace(
            self.root, list(local_names), self.first_party
        )

    def test_matching_marketplace_passes(self):
        self.local_plugin("demo")
        self.marketplace([{"name": "demo", "source": "./plugins/demo"}, self.standalone_entry()])

        self.assertEqual([], self.validate())

    def test_missing_marketplace_file_short_circuits(self):
        errors = self.validate()

        self.assertEqual(1, len(errors))
        self.assertIn("missing JSON file", errors[0])

    def test_schema_and_plugins_array_are_enforced(self):
        self.write_json(".claude-plugin/marketplace.json", {"$schema": "other", "plugins": {}})

        errors = self.validate()

        self.assertTrue(any("$schema must be" in item for item in errors))
        self.assertTrue(any("'plugins' must be an array" in item for item in errors))

    def test_entry_without_name_is_reported(self):
        self.local_plugin("demo")
        self.marketplace(
            ["not-an-object", {"name": "demo", "source": "./plugins/demo"}, self.standalone_entry()]
        )

        errors = self.validate()

        self.assertTrue(any("entry missing 'name'" in item for item in errors))

    def test_first_party_source_description_and_version_must_match_the_pin(self):
        self.local_plugin("demo")
        self.marketplace(
            [
                {"name": "demo", "source": "./plugins/demo"},
                self.standalone_entry(
                    source={"source": "github", "repo": "Xopoko/standalone", "sha": "b" * 40},
                    description="Drifted.",
                    version="9.9.9",
                ),
            ]
        )

        errors = self.validate()

        self.assertTrue(any("first-party source mismatch" in item for item in errors))
        self.assertTrue(any("description mismatch" in item for item in errors))
        self.assertTrue(any("version mismatch" in item for item in errors))

    def test_local_entry_requires_a_source_path_and_claude_manifest(self):
        (self.root / "plugins" / "demo").mkdir(parents=True)
        self.marketplace(
            [{"name": "demo", "source": "./plugins/other"}, self.standalone_entry()]
        )

        errors = self.validate()

        self.assertTrue(any("bad source for demo" in item for item in errors))
        self.assertTrue(any("lacks a Claude manifest" in item for item in errors))

    def test_plugin_set_and_uniqueness_are_enforced(self):
        self.local_plugin("demo")
        self.marketplace(
            [
                {"name": "demo", "source": "./plugins/demo"},
                {"name": "demo", "source": "./plugins/demo"},
                self.standalone_entry(),
            ]
        )

        errors = self.validate(local_names=("demo", "absent"))

        self.assertTrue(any("plugin set does not match" in item for item in errors))
        self.assertTrue(any("names must be unique" in item for item in errors))


class ScanFilesTests(TempRootTestCase):
    def test_clean_tree_produces_no_errors(self):
        self.write_text("README.md", "# Title\n\nPlain publication-safe text.\n")

        self.assertEqual([], validate_repository.scan_files(self.root))

    def test_generated_artifacts_are_rejected(self):
        self.write_text("module.pyc", "compiled")
        self.write_text(".DS_Store", "junk")

        errors = validate_repository.scan_files(self.root)

        self.assertEqual(2, len(errors))
        self.assertTrue(all("generated artifact must not be committed" in item for item in errors))

    def test_binary_and_unlisted_extensions_are_ignored(self):
        self.write_text("notes.rst", GRANDIOSE_WORD)
        (self.root / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff")

        self.assertEqual([], validate_repository.scan_files(self.root))

    def test_undecodable_text_extension_is_reported(self):
        (self.root / "broken.md").write_bytes(b"\xff\xfe\x00binary")

        errors = validate_repository.scan_files(self.root)

        self.assertTrue(
            any("broken.md: text source must be valid UTF-8" in error for error in errors),
            errors,
        )

    def test_each_content_policy_is_reported(self):
        cases = {
            "cyrillic.md": (CYRILLIC_WORD, "contains Cyrillic characters"),
            "home.md": (LOCAL_HOME_PATH, "machine-specific home path"),
            "project-path.md": (LOCAL_PROJECT_PATH, "machine-specific home path"),
            "issue.md": (PRIVATE_PROJECT, "private project or issue-key reference"),
            "hype.md": (GRANDIOSE_WORD, "inflated publication wording"),
            "org.md": (PRIVATE_ORG_WORD, "private-organization wording"),
            "brand.md": (LEGACY_BRAND, "legacy repository branding"),
            "tool.md": (PRIVATE_TOOL, "private local tool dependency"),
            "secret.md": (FAKE_SECRET, "matches sensitive pattern"),
        }
        for name, (content, _) in cases.items():
            self.write_text(name, content + "\n")

        errors = validate_repository.scan_files(self.root)

        for name, (_, expected) in cases.items():
            matching = [item for item in errors if item.startswith(f"{name}:")]
            self.assertEqual(1, len(matching), f"{name} produced {matching}")
            self.assertIn(expected, matching[0])

    def test_scratch_and_cache_directories_are_not_scanned(self):
        for relative in (
            "tmp/draft.md",
            "research-2026/draft.md",
            "docs/superpowers/draft.md",
            "plugins/demo/research/draft.md",
            "__pycache__/draft.md",
            ".agents/draft.md",
        ):
            self.write_text(relative, GRANDIOSE_WORD + "\n")

        self.assertEqual([], validate_repository.scan_files(self.root))


class ShouldSkipScanTests(TempRootTestCase):
    def skipped(self, relative):
        return validate_repository.should_skip_scan(self.root, self.root / relative)

    def test_tracked_source_paths_are_scanned(self):
        self.assertFalse(self.skipped("README.md"))
        self.assertFalse(self.skipped("plugins/demo/skills/demo/SKILL.md"))
        self.assertFalse(self.skipped("docs/ARCHITECTURE.md"))

    def test_skip_rules_cover_caches_scratch_and_plugin_scratch(self):
        self.assertTrue(self.skipped(".git/config"))
        self.assertTrue(self.skipped("plugins/demo/__pycache__/mod.pyc"))
        self.assertTrue(self.skipped("scratch/draft.md"))
        self.assertTrue(self.skipped("reports-2026/draft.md"))
        self.assertTrue(self.skipped("docs/superpowers/draft.md"))
        self.assertTrue(self.skipped("plugins/demo/tmp/draft.md"))


class RepoRootTests(unittest.TestCase):
    def test_repo_root_points_at_the_checkout(self):
        self.assertEqual(ROOT, validate_repository.repo_root())


SURFACE_VALIDATORS = (
    validate_repository.validate_capability_workbench_surface,
    validate_repository.validate_agent_harness_surface,
    validate_repository.validate_technology_intelligence_surface,
    validate_repository.validate_architecture_intelligence_surface,
)


class SurfaceValidatorTests(unittest.TestCase):
    def test_checkout_satisfies_every_surface_contract(self):
        self.assertEqual(ROOT, validate_repository.repo_root())
        for validator in SURFACE_VALIDATORS:
            with self.subTest(validator=validator.__name__):
                self.assertEqual([], validator(ROOT))

    def test_empty_tree_reports_missing_surfaces(self):
        with tempfile.TemporaryDirectory() as temp:
            empty_root = Path(temp)
            with mock.patch.object(
                validate_repository, "repo_root", return_value=empty_root
            ):
                for validator in SURFACE_VALIDATORS:
                    with self.subTest(validator=validator.__name__):
                        errors = validator(empty_root)
                        self.assertTrue(errors)
                        self.assertTrue(any("missing" in error for error in errors))


class MainTests(TempRootTestCase):
    def run_main(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            try:
                validate_repository.main()
            except SystemExit as exc:
                return exc.code, stdout.getvalue()
        return 0, stdout.getvalue()

    def patch_checks(self, **overrides):
        defaults = {
            "load_json": mock.Mock(
                side_effect=lambda path, errors: {
                    "name": path.parent.parent.name,
                    "license": "MIT",
                }
            ),
            "validate_manifest_metadata": mock.Mock(),
            "validate_marketplace": mock.Mock(return_value=[]),
            "validate_capability_workbench_surface": mock.Mock(return_value=[]),
            "validate_agent_harness_surface": mock.Mock(return_value=[]),
            "validate_technology_intelligence_surface": mock.Mock(return_value=[]),
            "validate_architecture_intelligence_surface": mock.Mock(return_value=[]),
            "scan_files": mock.Mock(return_value=[]),
        }
        defaults.update(overrides)
        for name, replacement in defaults.items():
            patcher = mock.patch.object(validate_repository, name, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        run = mock.patch.object(
            validate_repository.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
        ).start()
        self.addCleanup(mock.patch.stopall)
        return run

    def test_clean_repository_passes(self):
        self.patch_checks()
        with mock.patch.object(validate_repository, "repo_root", return_value=ROOT):
            code, out = self.run_main()

        self.assertEqual(0, code)
        self.assertIn("Repository validation passed", out)

    def test_manifest_name_and_license_drift_are_reported(self):
        load_json = mock.Mock(return_value={"name": "other", "license": "Apache-2.0"})
        self.patch_checks(load_json=load_json)
        with mock.patch.object(validate_repository, "repo_root", return_value=ROOT):
            code, out = self.run_main()

        self.assertEqual(1, code)
        self.assertIn("Repository validation failed", out)
        self.assertIn("name must match directory", out)
        self.assertIn("license must be MIT", out)

    def test_helper_failures_and_scan_errors_are_surfaced(self):
        run = self.patch_checks(scan_files=mock.Mock(return_value=["forbidden content"]))
        run.return_value = SimpleNamespace(returncode=1, stdout="helper said no", stderr="")
        with mock.patch.object(validate_repository, "repo_root", return_value=ROOT):
            code, out = self.run_main()

        self.assertEqual(1, code)
        self.assertIn("- forbidden content", out)
        self.assertIn("helper said no", out)
        self.assertIn("External dependency validation failed", out)

    def test_missing_validators_and_catalog_failure_are_reported(self):
        error = validate_repository.plugin_catalog.CatalogError("catalog broken")
        with mock.patch.object(
            validate_repository.plugin_catalog, "validate_catalog", side_effect=error
        ), mock.patch.object(validate_repository, "repo_root", return_value=self.root):
            code, out = self.run_main()

        self.assertEqual(1, code)
        self.assertIn("missing validator", out)
        self.assertIn("First-party plugin catalog validation failed: catalog broken", out)
        self.assertIn("missing plugin directory", out)

    def test_vendored_first_party_plugin_is_rejected(self):
        self.patch_checks()
        catalog = {"plugins": [{"name": "capability-workbench"}]}
        with mock.patch.object(
            validate_repository.plugin_catalog, "validate_catalog", return_value=catalog
        ), mock.patch.object(validate_repository, "repo_root", return_value=ROOT):
            code, out = self.run_main()

        self.assertEqual(1, code)
        self.assertIn("standalone first-party plugin must not be vendored", out)

    def test_unexpected_manifest_directories_are_reported(self):
        self.patch_checks()
        plugins = self.root / "plugins"
        (plugins / "rogue" / ".codex-plugin").mkdir(parents=True)
        (plugins / "rogue" / ".codex-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
        for name in validate_repository.LOCAL_PLUGIN_NAMES:
            (plugins / name).mkdir(parents=True)
        with mock.patch.object(validate_repository, "repo_root", return_value=self.root):
            code, out = self.run_main()

        self.assertEqual(1, code)
        self.assertIn("unexpected manifest-bearing plugin directories: rogue", out)


if __name__ == "__main__":
    unittest.main()
