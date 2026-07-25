#!/usr/bin/env python3
"""Regression checks for the offline KMP inspector."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "scripts" / "kmp_inspector.py"
FIXTURE = ROOT / "tests" / "fixtures" / "risky-kmp"


def run_inspector(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(INSPECTOR),
            "--root",
            str(root),
            "--json",
            "--fail-on",
            "none",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


class KmpInspectorTest(unittest.TestCase):
    def test_expected_diagnostics_and_readiness_areas(self):
        report = json.loads(run_inspector(FIXTURE).stdout)
        codes = {item["code"] for item in report["diagnostics"]}
        for module in report["modules"]:
            codes.update(item["code"] for item in module["diagnostics"])

        expected = {
            "project_repositories_not_blocked",
            "module_local_repositories",
            "published_library_without_abi_validation",
            "swiftpm_manifest_validation_needed",
            "cinterop_definition_not_detected",
            "native_transitive_export_enabled",
            "possible_secret_literal_in_common",
            "common_println_logging",
            "platform_test_import_in_common_test",
            "native_gc_disabled",
        }
        missing_codes = sorted(expected - codes)
        self.assertFalse(
            missing_codes,
            f"missing expected diagnostics: {missing_codes}",
        )

        readiness_names = {area["name"] for area in report["readiness"]}
        required_areas = {
            "project-structure",
            "build-governance",
            "testing-quality",
            "ios-native-interop",
            "security-privacy",
            "performance-observability",
            "publishing-release",
        }
        missing_areas = sorted(required_areas - readiness_names)
        self.assertFalse(
            missing_areas,
            f"missing readiness areas: {missing_areas}",
        )

    def test_json_schema_omits_secrets_arbitrary_keys_and_local_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            private_fixture = Path(temp_dir) / "project"
            shutil.copytree(FIXTURE, private_fixture)
            synthetic_secret = "synthetic-private-token-do-not-use"
            arbitrary_key = "privateRepositoryInternalMarker"
            prefix_like_key = "kotlin.native.binary.gc.internalMarker"
            properties_path = private_fixture / "gradle.properties"
            properties_path.write_text(
                properties_path.read_text(encoding="utf-8").replace(
                    "kotlin.native.binary.gc=noop",
                    "kotlin.native.binary.gc=default",
                ),
                encoding="utf-8",
            )
            with properties_path.open("a", encoding="utf-8") as properties:
                properties.write(f"\n{arbitrary_key}={synthetic_secret}\n")
                properties.write(f"{prefix_like_key}=noop\n")

            result = run_inspector(private_fixture)
            report = json.loads(result.stdout)

            self.assertNotIn(synthetic_secret, result.stdout)
            self.assertNotIn(arbitrary_key, result.stdout)
            self.assertNotIn(prefix_like_key, result.stdout)
            self.assertNotIn(str(private_fixture), result.stdout)
            self.assertNotIn(temp_dir, result.stdout)
            self.assertEqual(2, report["schema_version"])
            self.assertEqual(".", report["root"])
            self.assertEqual(
                "gradle/libs.versions.toml",
                report["version_catalog"],
            )
            self.assertTrue(report["gradle_properties_present"])
            self.assertNotIn("gradle_properties", report)
            self.assertEqual(
                [
                    "kotlin.incremental.native",
                    "kotlin.native.binary.gc",
                    "org.gradle.caching",
                    "org.gradle.configuration-cache",
                ],
                report["gradle_property_keys"],
            )
            diagnostic_codes = {item["code"] for item in report["diagnostics"]}
            self.assertNotIn("native_gc_disabled", diagnostic_codes)


if __name__ == "__main__":
    unittest.main()
