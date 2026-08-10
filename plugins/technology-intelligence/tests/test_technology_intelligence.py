from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PLUGIN_ROOT / "scripts" / "technology_intelligence.py"
SPEC = importlib.util.spec_from_file_location("technology_intelligence", MODULE_PATH)
assert SPEC and SPEC.loader
technology_intelligence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(technology_intelligence)


class FakeResponse:
    def __init__(self, payload: bytes, final_url: str, headers: dict[str, str] | None = None) -> None:
        self.payload = payload
        self.final_url = final_url
        self.headers = headers or {"Content-Type": "text/plain", "ETag": '"fixture"'}
        self.status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def geturl(self) -> str:
        return self.final_url

    def read(self, amount: int) -> bytes:
        return self.payload[:amount]


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests = []

    def open(self, request, timeout: float):
        self.requests.append((request, timeout))
        return self.response


class TechnologyIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = technology_intelligence.load_snapshot()

    def test_snapshot_validates_offline(self) -> None:
        self.assertEqual([], technology_intelligence.validate_plugin())

    def test_seed_has_21_candidates_across_all_families(self) -> None:
        technologies = self.snapshot["technologies"]["technologies"]
        self.assertEqual(21, len(technologies))
        counts: dict[str, int] = {}
        for technology in technologies:
            counts[technology["family"]] = counts.get(technology["family"], 0) + 1
        self.assertEqual(
            {
                "frontend-fullstack": 7,
                "backend-data-infrastructure": 8,
                "agent-delivery": 6,
            },
            counts,
        )

    def test_positive_assessments_have_first_party_and_triangulation_or_gap(self) -> None:
        sources = {record["id"]: record for record in self.snapshot["sources"]["sources"]}
        observations = {record["id"]: record for record in self.snapshot["observations"]["observations"]}
        for assessment in self.snapshot["assessments"]["assessments"]:
            if assessment["disposition"] not in technology_intelligence.POSITIVE_DISPOSITIONS:
                continue
            roles = {
                sources[observations[evidence_id]["source_id"]]["evidence_role"]
                for evidence_id in assessment["evidence_ids"]
            }
            self.assertIn("first-party", roles, assessment["id"])
            self.assertTrue(
                "independent-signal" in roles or assessment.get("verification_gap"),
                assessment["id"],
            )

    def test_durable_data_contains_no_universal_score_or_runtime_inventory(self) -> None:
        for document_name in ("sources", "technologies", "observations", "assessments"):
            for path, key in technology_intelligence._walk_keys(self.snapshot[document_name]):
                self.assertNotIn(
                    key.casefold(), technology_intelligence.FORBIDDEN_SCORE_KEYS, f"{document_name}:{path}"
                )
                if document_name != "sources":
                    self.assertNotIn(
                        key.casefold(), technology_intelligence.RUNTIME_STATE_KEYS, f"{document_name}:{path}"
                    )

    def test_query_is_deterministic_and_profile_filtered(self) -> None:
        first = technology_intelligence.query_snapshot(
            self.snapshot,
            family="frontend-fullstack",
            stage="startup",
        )
        second = technology_intelligence.query_snapshot(
            self.snapshot,
            family="frontend-fullstack",
            stage="startup",
        )
        self.assertEqual(first, second)
        self.assertEqual(7, len(first))
        self.assertEqual(
            sorted(row["technology"]["name"].casefold() for row in first),
            [row["technology"]["name"].casefold() for row in first],
        )
        react = technology_intelligence.query_snapshot(self.snapshot, technology="react")
        self.assertEqual(["react"], [row["technology"]["id"] for row in react])

    def test_runtime_inventory_is_validated_joined_and_not_persisted(self) -> None:
        before = json.dumps(self.snapshot, default=str, sort_keys=True)
        inventory = {
            "schema_version": "technology_intelligence.runtime_inventory.v1",
            "observed_at": "2026-08-10T12:00:00Z",
            "capabilities": [
                {
                    "technology_id": "mcp-stdio",
                    "surface": "mcp",
                    "identifier": "fixture.local/server",
                    "installed": True,
                    "enabled": False,
                    "auth_state": "not-required",
                    "health": "unknown",
                    "checked_at": "2026-08-10T12:00:00Z",
                }
            ],
        }
        self.assertEqual(
            [],
            technology_intelligence.validate_runtime_inventory(
                inventory, self.snapshot["runtime-capability-schema"]
            ),
        )
        rows = technology_intelligence.query_snapshot(
            self.snapshot,
            technology="mcp-stdio",
            runtime_inventory=inventory,
        )
        self.assertEqual("fixture.local/server", rows[0]["runtime_capabilities"][0]["identifier"])
        self.assertEqual(before, json.dumps(self.snapshot, default=str, sort_keys=True))

    def test_runtime_inventory_rejects_secret_fields(self) -> None:
        inventory = {
            "schema_version": "technology_intelligence.runtime_inventory.v1",
            "observed_at": "2026-08-10T12:00:00Z",
            "capabilities": [
                {
                    "technology_id": "http-json-api",
                    "surface": "api",
                    "identifier": "fixture",
                    "installed": True,
                    "enabled": True,
                    "auth_state": "configured",
                    "health": "healthy",
                    "checked_at": "2026-08-10T12:00:00Z",
                    "token": "synthetic-secret",
                }
            ],
        }
        errors = technology_intelligence.validate_runtime_inventory(
            inventory, self.snapshot["runtime-capability-schema"]
        )
        self.assertTrue(any("forbidden" in error for error in errors))

    def test_staleness_is_explicit_for_seed_and_future_date(self) -> None:
        current = technology_intelligence.staleness_report(self.snapshot, date(2026, 8, 10))
        self.assertEqual([], current["stale_sources"])
        self.assertEqual([], current["expired_assessments"])
        future = technology_intelligence.staleness_report(self.snapshot, date(2032, 1, 1))
        self.assertEqual(len(self.snapshot["sources"]["sources"]), len(future["stale_sources"]))
        self.assertEqual(len(self.snapshot["assessments"]["assessments"]), len(future["expired_assessments"]))

    def test_diff_reports_changed_observation_without_reclassifying_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            old_dir = temporary_path / "old"
            new_dir = temporary_path / "new"
            shutil.copytree(PLUGIN_ROOT / "data", old_dir)
            shutil.copytree(PLUGIN_ROOT / "data", new_dir)
            observation_path = new_dir / "observations.v1.json"
            document = json.loads(observation_path.read_text(encoding="utf-8"))
            changed_id = document["observations"][0]["id"]
            document["observations"][0]["limitations"] += " Synthetic test change."
            observation_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            result = technology_intelligence.diff_directories(old_dir, new_dir)
            self.assertEqual([changed_id], result["datasets"]["observations"]["changed"])
            self.assertEqual([], result["datasets"]["assessments"]["changed"])

    def test_all_synthetic_trigger_cases_match_contract(self) -> None:
        fixture = json.loads(
            (PLUGIN_ROOT / "tests" / "fixtures" / "trigger-cases.v1.json").read_text(encoding="utf-8")
        )
        contract = self.snapshot["trigger-contract"]
        self.assertEqual(24, len(fixture["cases"]))
        for case in fixture["cases"]:
            self.assertEqual(
                case["expected_skill"],
                technology_intelligence.classify_prompt(case["prompt"], contract),
                case["id"],
            )

    def test_refresh_requires_acknowledgement_before_network_or_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            opener = FakeOpener(FakeResponse(b"fixture", "https://www.thoughtworks.com/en-us/radar/faq"))
            with self.assertRaisesRegex(technology_intelligence.SnapshotError, "acknowledge-network"):
                technology_intelligence.capture_source(
                    "thoughtworks-radar-faq",
                    temporary,
                    acknowledge_network=False,
                    opener=opener,
                )
            self.assertEqual([], opener.requests)
            self.assertEqual([], list(Path(temporary).iterdir()))

    def test_refresh_rejects_output_inside_plugin(self) -> None:
        opener = FakeOpener(FakeResponse(b"fixture", "https://www.thoughtworks.com/en-us/radar/faq"))
        with self.assertRaisesRegex(technology_intelligence.SnapshotError, "outside the plugin"):
            technology_intelligence.capture_source(
                "thoughtworks-radar-faq",
                PLUGIN_ROOT / "tmp" / "refresh-fixture",
                acknowledge_network=True,
                opener=opener,
            )
        self.assertEqual([], opener.requests)

    def test_refresh_mock_writes_immutable_artifact_and_receipt_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            payload = b"synthetic source bytes"
            opener = FakeOpener(
                FakeResponse(
                    payload,
                    "https://www.thoughtworks.com/en-us/radar/faq",
                    {"Content-Type": "text/plain", "ETag": '"fixture"', "Last-Modified": "Sun, 10 Aug 2026 00:00:00 GMT"},
                )
            )
            result = technology_intelligence.capture_source(
                "thoughtworks-radar-faq",
                temporary,
                acknowledge_network=True,
                opener=opener,
                now=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
            )
            receipt = result["receipt"]
            capture_dir = Path(result["capture_dir"])
            self.assertEqual(payload, (capture_dir / "raw.bin").read_bytes())
            self.assertTrue((capture_dir / "receipt.json").is_file())
            self.assertTrue(receipt["network_explicit"])
            self.assertFalse(receipt["normalization_performed"])
            self.assertFalse(receipt["recommendations_changed"])
            self.assertEqual(len(payload), receipt["bytes"])
            self.assertEqual(1, len(opener.requests))

    def test_refresh_rejects_unallowlisted_final_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            opener = FakeOpener(FakeResponse(b"fixture", "https://example.invalid/redirect"))
            with self.assertRaisesRegex(technology_intelligence.SnapshotError, "not allowlisted"):
                technology_intelligence.capture_source(
                    "thoughtworks-radar-faq",
                    temporary,
                    acknowledge_network=True,
                    opener=opener,
                )
            self.assertEqual([], list(Path(temporary).iterdir()))

    def test_refresh_rejects_non_https_final_url_on_allowlisted_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            opener = FakeOpener(
                FakeResponse(
                    b"fixture",
                    "http://www.thoughtworks.com/en-us/radar/faq",
                )
            )
            with self.assertRaisesRegex(
                technology_intelligence.SnapshotError,
                "final response host is not allowlisted",
            ):
                technology_intelligence.capture_source(
                    "thoughtworks-radar-faq",
                    temp_dir,
                    acknowledge_network=True,
                    opener=opener,
                )
            self.assertEqual([], list(Path(temp_dir).iterdir()))

    def test_refresh_rejects_non_success_status_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            response = FakeResponse(b"not found", "https://www.thoughtworks.com/en-us/radar/faq")
            response.status = 404
            opener = FakeOpener(response)
            with self.assertRaisesRegex(technology_intelligence.SnapshotError, "non-success"):
                technology_intelligence.capture_source(
                    "thoughtworks-radar-faq",
                    temporary,
                    acknowledge_network=True,
                    opener=opener,
                )
            self.assertEqual([], list(Path(temporary).iterdir()))


if __name__ == "__main__":
    unittest.main()
