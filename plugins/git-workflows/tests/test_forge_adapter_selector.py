from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "forge_adapter_selector.py"
FIXTURE = ROOT / "tests" / "fixtures" / "forge-adapter-inventory.json"
CONTRACT = ROOT / "references" / "forge-adapter-contract.md"
SPEC = importlib.util.spec_from_file_location("forge_adapter_selector", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
selector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(selector)


def inventory() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def only(adapter_id: str) -> dict:
    value = inventory()
    value["adapters"] = [
        item for item in value["adapters"] if item["id"] == adapter_id
    ]
    return value


def plan(
    profile: str,
    *,
    forge: str = "gitlab",
    host: str = "gitlab.example.test",
    actor: str | None = "101",
    preferred: list[str] | None = None,
    degraded: bool = False,
    operation: str = "none",
    outcome: str = "not-attempted",
    adapter_id: str | None = None,
) -> dict:
    return {
        "schema": selector.PLAN_SCHEMA,
        "profile": profile,
        "forge": forge,
        "host": host,
        "expected_actor_id": actor,
        "preferred_adapter_ids": preferred or [],
        "allow_degraded_read": degraded,
        "write_state": {
            "operation": operation,
            "outcome": outcome,
            "adapter_id": adapter_id,
        },
    }


class ForgeAdapterSelectorTests(unittest.TestCase):
    def test_inventory_covers_mcp_connector_cli_and_rest(self):
        validated = selector.validate_inventory(inventory())
        self.assertEqual(
            {item["kind"] for item in validated["adapters"]},
            {"mcp", "connector", "cli", "rest"},
        )
        self.assertTrue(CONTRACT.is_file())

    def test_full_mcp_is_selected_without_glab_dependency(self):
        result = selector.select_adapter(
            inventory(),
            plan(
                "gitlab-review-reply",
                preferred=["full-gitlab-mcp"],
            ),
        )
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["selected_adapter_id"], "full-gitlab-mcp")

    def test_glab_or_rest_adapter_is_one_capability_equivalent(self):
        result = selector.select_adapter(
            inventory(),
            plan(
                "gitlab-review-resolve",
                preferred=["glab-or-rest"],
            ),
        )
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["selected_adapter_id"], "glab-or-rest")

    def test_read_only_github_connector_supports_forge_code_review(self):
        result = selector.select_adapter(
            only("github-read-connector"),
            plan(
                "forge-code-review",
                forge="github",
                host="github.example.test",
                actor=None,
            ),
        )
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["selected_adapter_id"], "github-read-connector")

    def test_wrong_identity_is_not_a_fallback_hint(self):
        result = selector.select_adapter(
            only("wrong-identity-mcp"),
            plan("gitlab-review-reply"),
        )
        self.assertEqual(result["status"], "REPORT_ONLY")
        self.assertIn("WRONG_IDENTITY", result["reason_codes"])
        self.assertIsNone(result["selected_adapter_id"])

    def test_opaque_pagination_cannot_claim_complete_review(self):
        result = selector.select_adapter(
            only("opaque-github-connector"),
            plan(
                "forge-code-review",
                forge="github",
                host="github.example.test",
                actor=None,
            ),
        )
        self.assertEqual(result["status"], "REPORT_ONLY")
        self.assertIn("PAGINATION_OPAQUE", result["reason_codes"])

    def test_hidden_diff_truncation_cannot_claim_complete_review(self):
        value = only("github-read-connector")
        value["adapters"][0]["evidence"]["change_diff_truncation"] = "hidden"
        result = selector.select_adapter(
            value,
            plan(
                "forge-code-review",
                forge="github",
                host="github.example.test",
                actor=None,
            ),
        )
        self.assertEqual(result["status"], "REPORT_ONLY")
        self.assertIn("DIFF_TRUNCATION_OPAQUE", result["reason_codes"])

    def test_missing_complete_changed_file_inventory_is_rejected(self):
        value = only("github-read-connector")
        value["adapters"][0]["capabilities"].pop(
            "forge.change.files.list-complete.v1"
        )
        result = selector.select_adapter(
            value,
            plan(
                "forge-code-review",
                forge="github",
                host="github.example.test",
                actor=None,
            ),
        )
        self.assertEqual(result["status"], "REPORT_ONLY")
        self.assertIn("CAPABILITY_MISSING", result["reason_codes"])

    def test_unsafe_write_semantics_are_rejected(self):
        result = selector.select_adapter(
            only("unsafe-gitlab-writer"),
            plan("gitlab-review-reply"),
        )
        self.assertEqual(result["status"], "REPORT_ONLY")
        self.assertIn("UNSAFE_WRITE_RETRY", result["reason_codes"])
        self.assertIn("UNKNOWN_WRITE_HIDDEN", result["reason_codes"])
        self.assertIn("SERVER_RECEIPT_UNAVAILABLE", result["reason_codes"])

    def test_ambiguous_write_selects_readback_only_and_never_a_writer(self):
        result = selector.select_adapter(
            inventory(),
            plan(
                "gitlab-review-reply",
                operation="reply",
                outcome="ambiguous",
                adapter_id="full-gitlab-mcp",
            ),
        )
        self.assertEqual(result["status"], "READBACK_ONLY")
        self.assertIsNone(result["selected_adapter_id"])
        self.assertIn("full-gitlab-mcp", result["readback_adapter_ids"])
        self.assertIn("AMBIGUOUS_WRITE_READBACK_ONLY", result["reason_codes"])

    def test_ambiguous_write_can_use_narrow_exact_thread_readback(self):
        value = only("full-gitlab-mcp")
        capabilities = value["adapters"][0]["capabilities"]
        value["adapters"][0]["capabilities"] = {
            "forge.change.discussion.read.v1": capabilities[
                "forge.change.discussion.read.v1"
            ]
        }
        result = selector.select_adapter(
            value,
            plan(
                "gitlab-review-reply",
                operation="reply",
                outcome="ambiguous",
                adapter_id="full-gitlab-mcp",
            ),
        )
        self.assertEqual(result["status"], "READBACK_ONLY")
        self.assertEqual(result["readback_adapter_ids"], ["full-gitlab-mcp"])
        self.assertIsNone(result["selected_adapter_id"])

    def test_reply_can_degrade_to_read_only_when_explicitly_allowed(self):
        value = only("full-gitlab-mcp")
        capabilities = value["adapters"][0]["capabilities"]
        capabilities.pop("gitlab.change.discussion.reply.create.v1")
        capabilities.pop("gitlab.change.discussion.resolve.set.v1")
        capabilities.pop("gitlab.change.pipelines.list-complete.v1")
        result = selector.select_adapter(
            value,
            plan("gitlab-review-reply", degraded=True),
        )
        self.assertEqual(result["status"], "DEGRADED")
        self.assertEqual(result["selected_profile"], "gitlab-review-read")

    def test_declared_capability_does_not_satisfy_a_plan(self):
        value = only("github-read-connector")
        value["adapters"][0]["capabilities"][
            "forge.change.diff.read.v1"
        ]["support"] = "declared"
        result = selector.select_adapter(
            value,
            plan(
                "forge-code-review",
                forge="github",
                host="github.example.test",
                actor=None,
            ),
        )
        self.assertEqual(result["status"], "REPORT_ONLY")
        self.assertIn("CAPABILITY_MISSING", result["reason_codes"])

    def test_contract_is_exact_and_unknown_fields_fail(self):
        value = inventory()
        value["adapters"][0]["surprise"] = True
        with self.assertRaises(selector.ContractError):
            selector.validate_inventory(value)

    def test_selector_has_no_network_or_subprocess_surface(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        imported = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        self.assertTrue(
            {"requests", "httpx", "socket", "subprocess", "urllib"}.isdisjoint(
                imported
            )
        )
        self.assertTrue(
            {"Popen", "run", "system", "urlopen"}.isdisjoint(calls)
        )

    def test_cli_emits_json_and_report_only_exit_two(self):
        value = only("opaque-github-connector")
        request = plan(
            "forge-code-review",
            forge="github",
            host="github.example.test",
            actor=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory_path = root / "inventory.json"
            plan_path = root / "plan.json"
            inventory_path.write_text(json.dumps(value), encoding="utf-8")
            plan_path.write_text(json.dumps(request), encoding="utf-8")
            import contextlib
            import io

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = selector.main(
                    [
                        "select",
                        "--inventory",
                        str(inventory_path),
                        "--plan",
                        str(plan_path),
                    ]
                )
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "REPORT_ONLY")


if __name__ == "__main__":
    unittest.main()
