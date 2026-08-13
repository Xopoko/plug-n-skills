from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent.parent
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40,64}$")

EXPECTED_SKILLS = {
    "agent-harness",
    "agent-harness-engineering",
    "agent-harness-evaluation",
    "claude-agent-worktrees",
    "claude-code",
    "claude-doctor-debugger",
    "claude-hooks-settings",
    "claude-plugin-mcp-manager",
    "claude-print-automation",
    "codex-cli",
    "codex-deferred-completion",
    "codex-doctor-debugger",
    "codex-environments",
    "codex-exec-automation",
    "codex-log-reader",
    "codex-plugin-mcp-manager",
    "codex-thread-supervisor",
    "credential-handoff",
    "scheduled-automation-runtime",
}


def load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class AgentHarnessPluginContractTests(unittest.TestCase):
    def test_exact_skill_inventory_and_frontmatter_names(self) -> None:
        skill_dirs = {
            path.name
            for path in (ROOT / "skills").iterdir()
            if path.is_dir() and not path.name.startswith(".")
        }
        self.assertEqual(EXPECTED_SKILLS, skill_dirs)

        for skill_name in sorted(skill_dirs):
            with self.subTest(skill=skill_name):
                text = (ROOT / "skills" / skill_name / "SKILL.md").read_text(
                    encoding="utf-8"
                )
                match = re.search(r"^name:\s*([^\s]+)\s*$", text, re.MULTILINE)
                self.assertIsNotNone(match)
                self.assertEqual(skill_name, match.group(1))

    def test_router_trigger_prefix_and_exclusions_are_explicit(self) -> None:
        router = (ROOT / "skills" / "agent-harness" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "  Agent runtimes and human credential handoff: route harnesses, Codex/Claude",
            router,
        )
        self.assertIn("Use Capability Workbench for skill or plugin authoring", router)
        self.assertRegex(router, r"generic\s+(?:app|application)\s+architecture")
        self.assertIn("scheduled-automation-runtime", router)
        self.assertIn("credential-handoff", router)

    def test_manifests_are_aligned_and_searchable(self) -> None:
        codex = load_json(".codex-plugin/plugin.json")
        claude = load_json(".claude-plugin/plugin.json")
        for field in ("name", "version", "description", "author", "license", "keywords"):
            self.assertEqual(codex[field], claude[field], field)
        self.assertEqual("agent-harness", codex["name"])
        self.assertEqual("0.1.4", codex["version"])
        self.assertEqual("Agent Harness", codex["interface"]["displayName"])
        self.assertIsInstance(codex["interface"]["defaultPrompt"], list)
        self.assertTrue(codex["interface"]["defaultPrompt"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertEqual("./.codex-mcp.json", codex["mcpServers"])
        self.assertEqual("./assets/icon.png", codex["interface"]["composerIcon"])
        self.assertTrue((ROOT / "assets" / "icon.png").is_file())
        self.assertTrue(
            {
                "agent-harness",
                "codex",
                "credentials",
                "claude-code",
                "hooks",
                "mcp",
                "scheduler",
                "sessions",
                "evaluation",
            }.issubset(set(codex["keywords"]))
        )

    def test_current_codex_cli_command_shapes(self) -> None:
        exec_skill = (ROOT / "skills" / "codex-exec-automation" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        plugin_skill = (
            ROOT / "skills" / "codex-plugin-mcp-manager" / "SKILL.md"
        ).read_text(encoding="utf-8")
        doctor_skill = (
            ROOT / "skills" / "codex-doctor-debugger" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("codex --ask-for-approval never exec", exec_skill)
        self.assertIn('codex -C "$PROJECT" review --uncommitted', exec_skill)
        self.assertNotIn("codex exec -C \"$PROJECT\" --sandbox read-only --ask-for-approval", exec_skill)
        self.assertIn("codex plugin marketplace add <source>", plugin_skill)
        self.assertNotIn("marketplace add <name> <source>", plugin_skill)
        self.assertIn("--permission-profile <name>", doctor_skill)
        self.assertNotIn("--permissions-profile", doctor_skill)

    def test_mcp_companions_keep_the_bounded_server(self) -> None:
        codex = load_json(".codex-mcp.json")["mcpServers"]
        claude = load_json(".mcp.json")["mcpServers"]
        self.assertEqual({"codex-deferred-completion"}, set(codex))
        self.assertEqual({"codex-deferred-completion"}, set(claude))
        self.assertEqual(["./mcp/server.py"], codex["codex-deferred-completion"]["args"])
        self.assertEqual(
            ["${CLAUDE_PLUGIN_ROOT}/mcp/server.py"],
            claude["codex-deferred-completion"]["args"],
        )
        self.assertTrue((ROOT / "mcp" / "server.py").is_file())
        self.assertTrue((ROOT / "lib" / "native_completion_contract.py").is_file())

    def test_icon_prompt_provenance_matches_the_final_rgb_asset(self) -> None:
        prompt = load_json("assets/icon-prompt.json")
        asset = prompt["provenance"]["selected_asset"]
        payload = (ROOT / asset["path"]).read_bytes()
        self.assertEqual("agent-harness", prompt["plugin_name"])
        self.assertEqual("built-in image_gen", prompt["provenance"]["generated_by"])
        self.assertIsNone(prompt["provenance"]["generator_model_version_receipt"])
        self.assertEqual(asset["bytes"], len(payload))
        self.assertEqual(asset["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(b"\x89PNG\r\n\x1a\n", payload[:8])
        self.assertEqual(asset["width"], int.from_bytes(payload[16:20], "big"))
        self.assertEqual(asset["height"], int.from_bytes(payload[20:24], "big"))
        self.assertEqual(2, payload[25], "PNG must use opaque RGB color type 2")

    def test_reference_collision_preserves_both_vendor_contracts(self) -> None:
        codex_reference = ROOT / "references" / "codex-cli-operation-contracts.md"
        claude_reference = ROOT / "references" / "claude-cli-operation-contracts.md"
        self.assertIn("codex-cli", codex_reference.read_text(encoding="utf-8"))
        self.assertIn("claude-code", claude_reference.read_text(encoding="utf-8"))
        self.assertFalse((ROOT / "references" / "cli-operation-contracts.md").exists())

        for skill in ("claude-code", "claude-doctor-debugger"):
            contents = (ROOT / "skills" / skill / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("references/claude-cli-operation-contracts.md", contents)
            self.assertNotIn("references/cli-operation-contracts.md", contents)

    def test_bundled_plugin_root_references_resolve(self) -> None:
        pattern = re.compile(
            r"\$PLUGIN_ROOT/((?:references|scripts)/[A-Za-z0-9_./-]+\.(?:md|py))"
        )
        documents = [
            *sorted((ROOT / "skills").glob("*/SKILL.md")),
            *sorted((ROOT / "references").glob("*.md")),
        ]
        observed: set[str] = set()
        for document in documents:
            for relative in pattern.findall(document.read_text(encoding="utf-8")):
                observed.add(relative)
                self.assertTrue(
                    (ROOT / relative).is_file(),
                    f"{document.relative_to(ROOT)} references missing {relative}",
                )
        self.assertGreaterEqual(len(observed), 10)

    def test_router_trigger_fixture_covers_owned_and_excluded_routes(self) -> None:
        fixture = load_json("tests/fixtures/router-trigger-cases.json")
        self.assertEqual("agent_harness.router_trigger_cases.v1", fixture["schema"])
        routed = {case["id"]: case for case in fixture["should_route"]}
        excluded = {case["id"]: case for case in fixture["should_not_route"]}
        self.assertTrue(
            {
                "harness-control-loop",
                "harness-release-gate",
                "codex-exec",
                "codex-rollout",
                "deferred-completion",
                "claude-print",
                "claude-hooks",
                "vendor-mcp",
                "claude-session",
                "scheduler-proof",
                "credential-handoff",
            }.issubset(routed)
        )
        self.assertEqual("capability-workbench", excluded["skill-authoring"]["expected_owner"])
        self.assertEqual(
            "architecture-intelligence",
            excluded["generic-architecture"]["expected_owner"],
        )

    def test_strict_source_migration_ledger(self) -> None:
        ledger = load_json("references/source-migration-ledger.json")
        self.assertEqual("agent_harness.portfolio_migration.v1", ledger["schema"])
        self.assertEqual(18, ledger["target_plugin"]["expected_skill_count"])
        self.assertEqual(
            {"codex-cli", "claude-code", "scheduled-automation"},
            {entry["source_plugin"] for entry in ledger["whole_plugin_merges"]},
        )
        self.assertEqual(
            {"agent-harness-engineering", "agent-harness-evaluation"},
            {entry["skill"] for entry in ledger["workbench_moves"]},
        )
        self.assertEqual(
            "keep_plugin_and_non_harness_capabilities",
            ledger["workbench_keep"]["action"],
        )

        snapshot = ledger["source_snapshot"]
        snapshot_entries = snapshot["entries"]
        snapshot_by_path = {
            entry["source_path"]: entry for entry in snapshot_entries
        }
        self.assertEqual(69, snapshot["entry_count"])
        self.assertEqual(60, snapshot["retired_plugin_file_count"])
        self.assertEqual(9, snapshot["workbench_harness_file_count"])
        self.assertRegex(snapshot["commit"], GIT_OBJECT_RE)
        self.assertRegex(snapshot["root_tree"], GIT_OBJECT_RE)
        self.assertEqual(69, len(snapshot_entries))
        self.assertEqual(69, len(snapshot_by_path))
        self.assertEqual(
            {
                "plugins/codex-cli": 33,
                "plugins/claude-code": 15,
                "plugins/scheduled-automation": 12,
                "plugins/capability-workbench": 9,
            },
            {
                entry["source_root"]: entry["expected_file_count"]
                for entry in snapshot["source_roots"]
            },
        )
        for entry in snapshot_entries:
            with self.subTest(snapshot_path=entry["source_path"]):
                self.assertRegex(entry["source_git_blob"], GIT_OBJECT_RE)
                self.assertRegex(entry["source_sha256"], SHA256_RE)
                self.assertGreater(entry["source_bytes"], 0)

        inventory = ledger["source_inventory"]
        inventory_by_path = {entry["source_path"]: entry for entry in inventory}
        self.assertEqual(69, len(inventory))
        self.assertEqual(69, len(inventory_by_path))
        self.assertEqual(set(snapshot_by_path), set(inventory_by_path))
        self.assertEqual(
            {"mapped": 54, "replaced": 9, "omitted": 6},
            {
                disposition: sum(
                    entry["disposition"] == disposition for entry in inventory
                )
                for disposition in ("mapped", "replaced", "omitted")
            },
        )
        for entry in inventory:
            with self.subTest(inventory_path=entry["source_path"]):
                if entry["disposition"] == "mapped":
                    self.assertIsInstance(entry.get("destination_path"), str)
                    self.assertTrue(entry["destination_path"])
                else:
                    self.assertNotIn("destination_path", entry)
                if entry["disposition"] == "replaced":
                    self.assertRegex(
                        entry["source_path"],
                        r"/(?:README\.md|\.(?:codex|claude)-plugin/plugin\.json)$",
                    )
                    self.assertTrue(entry["replacement_surface"])
                if entry["disposition"] == "omitted":
                    self.assertIn("/assets/", entry["source_path"])

        mappings = ledger["file_mappings"]
        self.assertEqual(54, len(mappings))
        self.assertEqual(
            len(mappings),
            len({entry["source_path"] for entry in mappings}),
        )
        self.assertEqual(
            len(mappings),
            len({entry["destination_path"] for entry in mappings}),
        )
        mapped_inventory = {
            entry["source_path"]: entry["destination_path"]
            for entry in inventory
            if entry["disposition"] == "mapped"
        }
        mapped_files = {
            entry["source_path"]: entry["destination_path"] for entry in mappings
        }
        self.assertEqual(mapped_files, mapped_inventory)

        rewrite_allowlist = {
            entry["source_path"]: entry for entry in ledger["rewrite_allowlist"]
        }
        declared_rewrites = {
            entry["source_path"]
            for entry in mappings
            if entry["treatment"] not in {"verbatim", "rename_for_collision"}
        }
        self.assertEqual(declared_rewrites, set(rewrite_allowlist))

        for entry in mappings:
            with self.subTest(path=entry["destination_path"]):
                source = snapshot_by_path[entry["source_path"]]
                self.assertEqual(source["source_plugin"], entry["source_plugin"])
                self.assertEqual(source["source_git_blob"], entry["source_git_blob"])
                self.assertEqual(source["source_sha256"], entry["source_sha256"])
                self.assertEqual(source["source_bytes"], entry["source_bytes"])
                self.assertRegex(entry["source_sha256"], SHA256_RE)
                self.assertRegex(entry["source_git_blob"], GIT_OBJECT_RE)

                path = ROOT / entry["destination_path"]
                self.assertTrue(path.is_file())
                payload = path.read_bytes()
                self.assertEqual(entry["destination_bytes"], len(payload))
                self.assertEqual(
                    entry["destination_sha256"],
                    hashlib.sha256(payload).hexdigest(),
                )
                unchanged = entry["treatment"] in {
                    "verbatim",
                    "rename_for_collision",
                }
                if unchanged:
                    self.assertEqual(
                        (entry["source_sha256"], entry["source_bytes"]),
                        (
                            entry["destination_sha256"],
                            entry["destination_bytes"],
                        ),
                    )
                    self.assertNotIn(entry["source_path"], rewrite_allowlist)
                else:
                    allow = rewrite_allowlist[entry["source_path"]]
                    self.assertEqual(entry["destination_path"], allow["destination_path"])
                    self.assertEqual(entry["treatment"], allow["treatment"])
                    self.assertTrue(allow["allowed_changes"])
                    self.assertNotEqual(
                        (
                            entry["source_sha256"],
                            entry["source_bytes"],
                        ),
                        (
                            entry["destination_sha256"],
                            entry["destination_bytes"],
                        ),
                    )

    def test_git_source_snapshot_blobs_when_available(self) -> None:
        git_marker = REPO_ROOT / ".git"
        if not git_marker.exists():
            self.skipTest("source archive has no Git metadata")

        ledger = load_json("references/source-migration-ledger.json")
        snapshot = ledger["source_snapshot"]
        commit = snapshot["commit"]
        available = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=False,
        )
        if available.returncode != 0:
            self.skipTest("declared source snapshot commit is unavailable")

        def git_text(*args: str) -> str:
            return subprocess.check_output(
                ["git", *args],
                cwd=REPO_ROOT,
                text=True,
                encoding="utf-8",
            ).strip()

        self.assertEqual(
            snapshot["root_tree"],
            git_text("rev-parse", f"{commit}^{{tree}}"),
        )
        for source_root in snapshot["source_roots"]:
            with self.subTest(source_root=source_root["source_root"]):
                self.assertEqual(
                    source_root["git_tree"],
                    git_text(
                        "rev-parse",
                        f"{commit}:{source_root['source_root']}",
                    ),
                )

        complete_roots = [
            entry["source_root"]
            for entry in snapshot["source_roots"]
            if entry["coverage"] == "complete_retired_plugin_tree"
        ]
        selected_paths = {
            path
            for entry in snapshot["source_roots"]
            if entry["coverage"] == "selected_harness_files"
            for path in entry["selected_paths"]
        }
        retired_paths = set(
            subprocess.check_output(
                [
                    "git",
                    "ls-tree",
                    "-r",
                    "--name-only",
                    commit,
                    "--",
                    *complete_roots,
                ],
                cwd=REPO_ROOT,
                text=True,
                encoding="utf-8",
            ).splitlines()
        )
        snapshot_paths = {
            entry["source_path"] for entry in snapshot["entries"]
        }
        self.assertEqual(snapshot_paths, retired_paths | selected_paths)

        for entry in snapshot["entries"]:
            with self.subTest(git_blob=entry["source_path"]):
                self.assertEqual(
                    entry["source_git_blob"],
                    git_text("rev-parse", f"{commit}:{entry['source_path']}"),
                )
                payload = subprocess.check_output(
                    ["git", "show", f"{commit}:{entry['source_path']}"],
                    cwd=REPO_ROOT,
                )
                self.assertEqual(entry["source_bytes"], len(payload))
                self.assertEqual(
                    entry["source_sha256"],
                    hashlib.sha256(payload).hexdigest(),
                )

        for allow in ledger["rewrite_allowlist"]:
            changes = [
                change
                for change in allow["allowed_changes"]
                if {"old", "new", "expected_replacements"}.issubset(change)
            ]
            if not changes:
                continue
            source_text = subprocess.check_output(
                ["git", "show", f"{commit}:{allow['source_path']}"],
                cwd=REPO_ROOT,
                text=True,
                encoding="utf-8",
            )
            for change in changes:
                self.assertEqual(
                    change["expected_replacements"],
                    source_text.count(change["old"]),
                )
                source_text = source_text.replace(change["old"], change["new"])
            self.assertEqual(
                source_text,
                (ROOT / allow["destination_path"]).read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
