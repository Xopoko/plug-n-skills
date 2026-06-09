#!/usr/bin/env python3
"""Regression checks for the offline KMP inspector."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = ROOT / "scripts" / "kmp_inspector.py"
FIXTURE = ROOT / "tests" / "fixtures" / "risky-kmp"


def main() -> int:
    result = subprocess.run(
        [sys.executable, str(INSPECTOR), "--root", str(FIXTURE), "--json", "--fail-on", "none"],
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
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
    missing = sorted(expected - codes)
    if missing:
        print(f"missing expected diagnostics: {missing}", file=sys.stderr)
        return 1

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
    if missing_areas:
        print(f"missing readiness areas: {missing_areas}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
