import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "external-dependencies.py"
SPEC = importlib.util.spec_from_file_location("external_dependencies", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
EXTERNAL_DEPENDENCIES = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXTERNAL_DEPENDENCIES)
ValidationError = EXTERNAL_DEPENDENCIES.ValidationError
SourceVerificationError = EXTERNAL_DEPENDENCIES.SourceVerificationError
validate_lockfile = EXTERNAL_DEPENDENCIES.validate_lockfile
verify_sources = EXTERNAL_DEPENDENCIES.verify_sources


class ExternalDependenciesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "plugins" / "capability-workbench").mkdir(parents=True)
        report_dir = self.root / "docs" / "external-dependencies"
        report_dir.mkdir(parents=True)
        (report_dir / "sample-source.md").write_text(
            "# Sample source audit\n\nPinned evidence.\n",
            encoding="utf-8",
        )
        self.receipt_path = report_dir / "sample-source.receipt.json"
        self.lock = self._valid_lock()
        self._write_receipt()
        self.lock_path = self.root / "external-dependencies.lock.json"
        self._write_lock()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _valid_lock(self):
        return {
            "schemaVersion": 1,
            "dependencies": [
                {
                    "id": "sample-source",
                    "kind": "agent-skill-source",
                    "reviewedBy": ["capability-workbench"],
                    "source": {
                        "provider": "github",
                        "repository": "example-org/sample-source",
                        "commit": "1" * 40,
                        "tree": "2" * 40,
                    },
                    "policy": {
                        "mode": "reference-only",
                        "allowInstall": False,
                        "allowExecute": False,
                        "allowVendor": False,
                    },
                    "license": {
                        "root": "MIT",
                        "exceptions": [
                            {
                                "path": "CTF-Sandbox-Orchestrator",
                                "license": "GPL-3.0-only",
                            }
                        ],
                    },
                    "audit": {
                        "reviewedAt": "2026-08-09",
                        "verdict": "isolate",
                        "report": "docs/external-dependencies/sample-source.md",
                        "receipt": (
                            "docs/external-dependencies/sample-source.receipt.json"
                        ),
                    },
                }
            ],
        }

    def _receipt_payload(self):
        dependency = self.lock["dependencies"][0]
        report_path = self.root / dependency["audit"]["report"]
        report = report_path.read_text(encoding="utf-8")
        normalized_report = report.replace("\r\n", "\n").replace("\r", "\n")
        return {
            "schemaVersion": 1,
            "dependency": dependency["id"],
            "reviewedBy": copy.deepcopy(dependency["reviewedBy"]),
            "source": copy.deepcopy(dependency["source"]),
            "reviewedAt": dependency["audit"]["reviewedAt"],
            "verdict": dependency["audit"]["verdict"],
            "license": copy.deepcopy(dependency["license"]),
            "report": dependency["audit"]["report"],
            "reportSha256": hashlib.sha256(
                normalized_report.encode("utf-8")
            ).hexdigest(),
        }

    def _write_receipt(self, payload=None):
        receipt = self._receipt_payload() if payload is None else payload
        self.receipt_path.write_text(
            json.dumps(receipt, indent=2) + "\n",
            encoding="utf-8",
        )

    def _write_lock(self):
        self.lock_path.write_text(
            json.dumps(self.lock, indent=2) + "\n",
            encoding="utf-8",
        )

    def _assert_invalid(self, message_fragment=None):
        self._write_lock()
        with self.assertRaises(ValidationError) as context:
            validate_lockfile(self.root)
        if message_fragment is not None:
            self.assertIn(message_fragment, str(context.exception))

    def test_valid_actual_shape(self):
        payload = validate_lockfile(self.root)
        self.assertEqual(payload, self.lock)
        self.assertEqual(payload["dependencies"][0]["id"], "sample-source")

    def test_repository_lock_tracks_reviewed_i_have_adhd_snapshot(self):
        payload = validate_lockfile(ROOT)
        dependency = next(
            item for item in payload["dependencies"] if item["id"] == "i-have-adhd"
        )
        self.assertEqual(dependency["source"]["repository"], "ayghri/i-have-adhd")
        self.assertEqual(
            dependency["source"]["commit"],
            "2ed064090711586e0c97a2fbbf15465fe8f1808b",
        )
        self.assertEqual(
            dependency["source"]["tree"],
            "f3bcaa2cc34836bcba1d55bb7e3f3db76cfdae2d",
        )
        self.assertEqual(dependency["audit"]["verdict"], "isolate")

    def test_repository_lock_tracks_reviewed_humanlayer_show_me_snapshot(self):
        payload = validate_lockfile(ROOT)
        dependency = next(
            item
            for item in payload["dependencies"]
            if item["id"] == "humanlayer-show-me"
        )
        self.assertEqual(dependency["source"]["repository"], "humanlayer/skills")
        self.assertEqual(
            dependency["source"]["commit"],
            "3c2629142c5d437428269b1b722b08c0b87f574d",
        )
        self.assertEqual(
            dependency["source"]["tree"],
            "2f7121eedbf48e98cf1b42dffae97be6815e1fe9",
        )
        self.assertEqual(dependency["policy"]["mode"], "reference-only")
        self.assertFalse(dependency["policy"]["allowInstall"])
        self.assertFalse(dependency["policy"]["allowExecute"])
        self.assertFalse(dependency["policy"]["allowVendor"])
        self.assertEqual(dependency["audit"]["verdict"], "isolate")

    def test_rejects_mutable_short_or_non_lowercase_sha(self):
        for field, value in (
            ("commit", "main"),
            ("commit", "a" * 39),
            ("tree", "A" * 40),
        ):
            with self.subTest(field=field, value=value):
                self.lock = self._valid_lock()
                self.lock["dependencies"][0]["source"][field] = value
                self._assert_invalid(f"source.{field}")

    def test_rejects_traversal_backslash_and_absolute_paths(self):
        mutations = (
            ("exception traversal", "license", "../COPYING"),
            ("exception backslash", "license", "vendor\\COPYING"),
            ("exception absolute", "license", "/vendor/COPYING"),
            ("report traversal", "report", "docs/external-dependencies/../audit.md"),
            ("report backslash", "report", "docs\\external-dependencies\\audit.md"),
            ("report absolute", "report", "C:/audit.md"),
        )
        for label, target, value in mutations:
            with self.subTest(label=label):
                self.lock = self._valid_lock()
                dependency = self.lock["dependencies"][0]
                if target == "license":
                    dependency["license"]["exceptions"][0]["path"] = value
                else:
                    dependency["audit"]["report"] = value
                self._assert_invalid()

    def test_rejects_enabled_or_automatic_policy(self):
        mutations = (
            ("mode", "auto"),
            ("allowInstall", True),
            ("allowExecute", True),
            ("allowVendor", True),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                self.lock = self._valid_lock()
                self.lock["dependencies"][0]["policy"][field] = value
                self._assert_invalid(f"policy.{field}")

    def test_rejects_unknown_executable_key(self):
        self.lock["dependencies"][0]["executable"] = "scripts/install.py"
        self._assert_invalid("unknown keys executable")

    def test_rejects_duplicate_ids_and_sources(self):
        for duplicate_kind in ("id", "source"):
            with self.subTest(duplicate_kind=duplicate_kind):
                self.lock = self._valid_lock()
                duplicate = copy.deepcopy(self.lock["dependencies"][0])
                if duplicate_kind == "id":
                    duplicate["source"]["repository"] = "example-org/another-source"
                    duplicate["source"]["commit"] = "3" * 40
                    duplicate["source"]["tree"] = "4" * 40
                else:
                    duplicate["id"] = "another-source"
                self.lock["dependencies"].append(duplicate)
                self._assert_invalid("duplicates an earlier")

    def test_reviewed_by_replaces_used_by_and_requires_existing_plugin(self):
        dependency = self.lock["dependencies"][0]
        dependency["usedBy"] = dependency.pop("reviewedBy")
        self._assert_invalid("missing keys reviewedBy; unknown keys usedBy")

        self.lock = self._valid_lock()
        self.lock["dependencies"][0]["reviewedBy"] = ["missing-plugin"]
        self._assert_invalid("missing plugins/missing-plugin")

    def test_rejects_missing_report(self):
        self.lock = self._valid_lock()
        self.lock["dependencies"][0]["audit"]["report"] = (
            "docs/external-dependencies/missing.md"
        )
        self._assert_invalid("existing regular file")

    def test_rejects_receipt_mismatch_staleness_and_blank_content(self):
        mutations = (
            ("mismatched dependency", "dependency", "another-source"),
            ("stale reviewer", "reviewedBy", ["another-reviewer"]),
            ("stale source", "source", {"commit": "3" * 40}),
        )
        for label, field, value in mutations:
            with self.subTest(label=label):
                self.lock = self._valid_lock()
                receipt = self._receipt_payload()
                if field == "source":
                    receipt["source"].update(value)
                else:
                    receipt[field] = value
                self._write_receipt(receipt)
                self._assert_invalid("must exactly match")

        self.lock = self._valid_lock()
        self.receipt_path.write_text("", encoding="utf-8")
        self._assert_invalid("nonblank UTF-8 JSON")

    def test_report_is_distinct_nonblank_markdown_and_digest_bound(self):
        report_path = self.root / self.lock["dependencies"][0]["audit"]["report"]
        report_path.write_text("changed evidence\n", encoding="utf-8")
        self._assert_invalid("must exactly match")

        self.lock = self._valid_lock()
        report_path.write_text(" \r\n\t", encoding="utf-8")
        self._write_receipt()
        self._assert_invalid("nonblank Markdown report")

        self.lock = self._valid_lock()
        report_path.write_text("# restored\n", encoding="utf-8")
        self._write_receipt()
        self.lock["dependencies"][0]["audit"]["report"] = (
            "docs/external-dependencies/sample-source.receipt.json"
        )
        self._assert_invalid(".md extension")

        self.lock = self._valid_lock()
        self.lock["dependencies"][0]["audit"]["receipt"] = (
            "docs/external-dependencies/sample-source.md"
        )
        self._assert_invalid(".json extension")

    def test_receipt_rejects_unknown_and_duplicate_json_keys(self):
        receipt = self._receipt_payload()
        receipt["executable"] = "scripts/install.py"
        self._write_receipt(receipt)
        self._assert_invalid("unknown keys executable")

        self.lock = self._valid_lock()
        self._write_receipt()
        text = self.receipt_path.read_text(encoding="utf-8")
        text = text.replace(
            '"schemaVersion": 1,',
            '"schemaVersion": 1,\n  "schemaVersion": 1,',
            1,
        )
        self.receipt_path.write_text(text, encoding="utf-8")
        self._assert_invalid("duplicate key 'schemaVersion'")

    def test_verify_sources_uses_exact_get_url_and_accepts_good_response(self):
        requests = []

        def requester(request):
            requests.append(request)
            return {"sha": "1" * 40, "tree": {"sha": "2" * 40}}

        result = verify_sources(
            self.root,
            dependency_id="sample-source",
            requester=requester,
            environ={"GITHUB_TOKEN": "test-secret"},
        )

        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "https://api.github.com/repos/example-org/sample-source/git/commits/"
            + "1" * 40,
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(result[0]["commit"], "1" * 40)
        self.assertEqual(result[0]["tree"], "2" * 40)
        self.assertNotIn("test-secret", repr(result))

    def test_verify_sources_rejects_commit_and_tree_mismatch(self):
        responses = (
            ({"sha": "3" * 40, "tree": {"sha": "2" * 40}}, "commit mismatch"),
            ({"sha": "1" * 40, "tree": {"sha": "4" * 40}}, "tree mismatch"),
        )
        for response, message in responses:
            with self.subTest(message=message):
                with self.assertRaises(SourceVerificationError) as context:
                    verify_sources(
                        self.root,
                        requester=lambda _request, payload=response: payload,
                        environ={},
                    )
                self.assertIn(message, str(context.exception))

    def test_verify_sources_reports_network_errors_without_leaking_token(self):
        def requester(_request):
            raise URLError("offline")

        with self.assertRaises(SourceVerificationError) as context:
            verify_sources(
                self.root,
                requester=requester,
                environ={"GH_TOKEN": "test-secret"},
            )
        self.assertIn("metadata request failed", str(context.exception))
        self.assertIn("offline", str(context.exception))
        self.assertNotIn("test-secret", str(context.exception))

    def test_verify_sources_rejects_header_injection_without_leaking_token(self):
        malicious = "test-secret\r\nX-Injected: value"
        with self.assertRaises(SourceVerificationError) as context:
            verify_sources(
                self.root,
                requester=lambda _request: self.fail("request must not run"),
                environ={"GITHUB_TOKEN": malicious},
            )
        self.assertIn("unsupported whitespace", str(context.exception))
        self.assertNotIn("test-secret", str(context.exception))
        self.assertNotIn("X-Injected", str(context.exception))

    def test_cli_validate_list_and_show(self):
        common = [sys.executable, str(SCRIPT), "--root", str(self.root)]
        validate_result = subprocess.run(
            [*common, "validate"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(validate_result.returncode, 0, validate_result.stderr)
        self.assertIn("1 dependencies", validate_result.stdout)

        list_result = subprocess.run(
            [sys.executable, str(SCRIPT), "list", "--root", str(self.root)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(list_result.returncode, 0, list_result.stderr)
        self.assertIn("sample-source", list_result.stdout)
        self.assertIn("example-org/sample-source@", list_result.stdout)

        show_result = subprocess.run(
            [*common, "show", "sample-source"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(show_result.returncode, 0, show_result.stderr)
        shown = json.loads(show_result.stdout)
        self.assertEqual(shown, self.lock["dependencies"][0])


if __name__ == "__main__":
    unittest.main()
