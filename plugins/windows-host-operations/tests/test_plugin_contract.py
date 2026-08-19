from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "windows-device-diagnostics",
    "windows-effective-settings",
    "windows-host-operations",
    "windows-startup-and-removal",
}


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class WindowsHostOperationsContractTests(unittest.TestCase):
    def test_skill_inventory_and_frontmatter_names(self) -> None:
        skill_dirs = {
            path.name
            for path in (ROOT / "skills").iterdir()
            if path.is_dir() and not path.name.startswith(".")
        }
        self.assertEqual(EXPECTED_SKILLS, skill_dirs)
        for name in sorted(skill_dirs):
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            match = re.search(r"^name:\s*([^\s]+)\s*$", text, re.MULTILINE)
            self.assertIsNotNone(match)
            self.assertEqual(name, match.group(1))

    def test_manifests_are_aligned_and_icon_is_bound(self) -> None:
        codex = load_json(".codex-plugin/plugin.json")
        claude = load_json(".claude-plugin/plugin.json")
        for field in ("name", "version", "description", "author", "license", "keywords"):
            self.assertEqual(codex[field], claude[field], field)
        self.assertEqual("windows-host-operations", codex["name"])
        self.assertEqual("0.1.0", codex["version"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertEqual(
            "https://github.com/Xopoko/plug-n-skills",
            codex["interface"]["websiteURL"],
        )
        self.assertEqual("#0F766E", codex["interface"]["brandColor"])
        self.assertEqual("./assets/icon.png", codex["interface"]["composerIcon"])
        self.assertEqual("./assets/icon.png", codex["interface"]["logo"])

        icon = ROOT / "assets" / "icon.png"
        prompt = load_json("assets/icon-prompt.json")
        receipt = load_json("assets/icon-receipt.json")
        selected = receipt["selected_asset"]
        payload = icon.read_bytes()
        self.assertEqual("capability_workbench.plugin_icon_prompt.v2", prompt["schema"])
        self.assertEqual("RGB", selected["color_mode"])
        self.assertEqual(1024, selected["width"])
        self.assertEqual(1024, selected["height"])
        self.assertEqual(len(payload), selected["bytes"])
        self.assertEqual(hashlib.sha256(payload).hexdigest(), selected["sha256"])
        self.assertEqual(b"\x89PNG\r\n\x1a\n", payload[:8])
        self.assertEqual(1024, int.from_bytes(payload[16:20], "big"))
        self.assertEqual(1024, int.from_bytes(payload[20:24], "big"))
        self.assertEqual(2, payload[25], "icon must be opaque RGB")

    def test_router_and_leaves_keep_distinct_boundaries(self) -> None:
        router = (ROOT / "skills" / "windows-host-operations" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for leaf in EXPECTED_SKILLS - {"windows-host-operations"}:
            self.assertIn(leaf, router)
        for adjacent in (
            "scheduled-automation-runtime",
            "computer-use",
            "credential-handoff",
            "Human Decision Surface",
        ):
            self.assertIn(adjacent, router)
        for control in (
            "UNKNOWN",
            "Win32_Product",
            "ExecutionPolicy Bypass",
            "reboot_required",
            "observed_effect",
        ):
            self.assertIn(control, router)

        settings = (ROOT / "skills" / "windows-effective-settings" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        startup = (
            ROOT / "skills" / "windows-startup-and-removal" / "SKILL.md"
        ).read_text(encoding="utf-8")
        devices = (
            ROOT / "skills" / "windows-device-diagnostics" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("policy_source", settings)
        self.assertIn("powercfg.exe /requests", settings)
        self.assertIn("disable startup before deleting", startup.lower())
        self.assertIn("Win32_Product", startup)
        self.assertIn("present versus remembered", devices)
        self.assertIn("No wildcard", devices)

    def test_read_only_helper_has_typed_unknown_coverage_and_no_mutators(self) -> None:
        script = (ROOT / "scripts" / "Get-WindowsHostEvidence.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("windows_host_operations.evidence.v1", script)
        self.assertIn("UNKNOWN", script)
        self.assertIn("NOT_PROBED", script)
        self.assertIn("mutation_performed = $false", script)
        self.assertIn("raw_device_identifiers_included = $false", script)
        self.assertNotIn("Win32_Product", script)
        for command in (
            "Remove-Item",
            "Set-ItemProperty",
            "Stop-Process",
            "Disable-PnpDevice",
            "Uninstall-Package",
            "Remove-PnpDevice",
            "Invoke-Expression",
        ):
            self.assertNotRegex(script, rf"(?im)^\s*{re.escape(command)}\b")

    @unittest.skipUnless(os.name == "nt", "PowerShell syntax probe is Windows-only")
    def test_powershell_helper_parses(self) -> None:
        script = ROOT / "scripts" / "Get-WindowsHostEvidence.ps1"
        command = (
            "$ErrorActionPreference='Stop'; "
            f"[ScriptBlock]::Create((Get-Content -Raw -LiteralPath '{script}')) | Out-Null"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)

    def test_router_fixture_has_positive_and_near_miss_coverage(self) -> None:
        fixture = load_json("tests/fixtures/router-trigger-cases.json")
        self.assertEqual("windows_host_operations.router_trigger_cases.v1", fixture["schema"])
        routed = {case["expected_leaf"] for case in fixture["should_route"]}
        self.assertEqual(EXPECTED_SKILLS - {"windows-host-operations"}, routed)
        excluded = {case["id"]: case for case in fixture["should_not_route"]}
        self.assertEqual("scheduled-automation-runtime", excluded["scheduler-proof"]["expected_owner"])
        self.assertEqual("computer-use", excluded["pure-ui"]["expected_owner"])

    def test_tracked_text_is_public_safe_and_ascii(self) -> None:
        text_files = [
            *ROOT.glob("**/*.md"),
            *ROOT.glob("**/*.json"),
            *ROOT.glob("**/*.ps1"),
        ]
        private_path = re.compile(r"(?i)(?:[A-Z]:\\Users\\|/(?:home|Users)/[^/<])")
        email = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
        for path in text_files:
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT)):
                text.encode("ascii")
                self.assertIsNone(private_path.search(text))
                self.assertIsNone(email.search(text))


if __name__ == "__main__":
    unittest.main()
