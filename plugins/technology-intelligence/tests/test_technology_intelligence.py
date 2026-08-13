from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LEGACY_V02_FIXTURE = PLUGIN_ROOT / "tests" / "fixtures" / "legacy-v0.2"
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

    def test_snapshot_has_24_candidates_across_all_families(self) -> None:
        technologies = self.snapshot["technologies"]["technologies"]
        self.assertEqual(24, len(technologies))
        counts: dict[str, int] = {}
        for technology in technologies:
            counts[technology["family"]] = counts.get(technology["family"], 0) + 1
        self.assertEqual(
            {
                "frontend-fullstack": 7,
                "backend-data-infrastructure": 8,
                "agent-delivery": 8,
                "document-processing": 1,
            },
            counts,
        )

    def test_capability_query_resolves_anydoc_and_exposes_interfaces(self) -> None:
        rows = technology_intelligence.query_snapshot(
            self.snapshot,
            capability="document-to-markdown",
        )
        self.assertEqual(["anydoc"], [row["technology"]["id"] for row in rows])
        self.assertEqual(
            ["document-to-markdown"],
            [capability["id"] for capability in rows[0]["capabilities"]],
        )
        interfaces = {interface["id"]: interface for interface in rows[0]["interfaces"]}
        self.assertEqual(
            {
                "anydoc-agent-skill",
                "anydoc-cli",
                "anydoc-node-sdk",
                "anydoc-python-sdk",
                "anydoc-rust-sdk",
                "anydoc-wasm",
            },
            set(interfaces),
        )
        self.assertEqual({"cli", "sdk", "skill", "wasm"}, {item["surface"] for item in interfaces.values()})
        interface_rows = technology_intelligence.query_snapshot(self.snapshot, interface="anydoc-cli")
        self.assertEqual(["anydoc"], [row["technology"]["id"] for row in interface_rows])
        self.assertEqual(
            ["anydoc-cli"],
            [item["id"] for item in interface_rows[0]["interfaces"]],
        )

    def test_cli_accepts_capability_and_interface_filters(self) -> None:
        args = technology_intelligence._build_parser().parse_args(
            [
                "query",
                "--capability",
                "document-to-markdown",
                "--interface",
                "anydoc-cli",
                "--format",
                "json",
            ]
        )
        self.assertEqual("document-to-markdown", args.capability)
        self.assertEqual("anydoc-cli", args.interface)

    def test_positive_assessments_have_first_party_and_triangulation_or_gap(self) -> None:
        sources = {record["id"]: record for record in self.snapshot["sources"]["sources"]}
        technologies = {record["id"]: record for record in self.snapshot["technologies"]["technologies"]}
        observations = {record["id"]: record for record in self.snapshot["observations"]["observations"]}
        for assessment in self.snapshot["assessments"]["assessments"]:
            if assessment["disposition"] not in technology_intelligence.POSITIVE_DISPOSITIONS:
                continue
            evidence_sources = [
                sources[observations[evidence_id]["source_id"]]
                for evidence_id in assessment["evidence_ids"]
            ]
            official_ids = set(technologies[assessment["technology_id"]]["official_source_ids"])
            self.assertTrue(
                any(source["id"] in official_ids for source in evidence_sources),
                assessment["id"],
            )
            self.assertTrue(
                any(
                    source["evidence_role"] == "independent-signal"
                    and assessment["technology_id"] not in source.get("affiliated_technology_ids", [])
                    for source in evidence_sources
                )
                or assessment.get("verification_gap"),
                assessment["id"],
            )

    def test_durable_data_contains_no_universal_score_or_runtime_inventory(self) -> None:
        for document_name in technology_intelligence.DATASET_FILES:
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
        self.assertEqual([], react[0]["capabilities"])
        self.assertEqual([], react[0]["interfaces"])

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
                inventory,
                self.snapshot["runtime-capability-schema"],
                reference_time=datetime(2026, 8, 10, 12, 30, tzinfo=timezone.utc),
            ),
        )
        rows = technology_intelligence.query_snapshot(
            self.snapshot,
            technology="mcp-stdio",
            runtime_inventory=inventory,
            runtime_reference_time=datetime(2026, 8, 10, 12, 30, tzinfo=timezone.utc),
        )
        self.assertEqual("fixture.local/server", rows[0]["runtime_capabilities"][0]["identifier"])
        self.assertEqual(before, json.dumps(self.snapshot, default=str, sort_keys=True))

    def test_runtime_inventory_can_join_a_known_interface(self) -> None:
        before = json.dumps(self.snapshot, default=str, sort_keys=True)
        interfaces = {item["id"]: item for item in self.snapshot["interfaces"]["interfaces"]}
        inventory = {
            "schema_version": "technology_intelligence.runtime_inventory.v1",
            "observed_at": "2026-08-11T18:30:00Z",
            "capabilities": [
                {
                    "technology_id": "anydoc",
                    "interface_id": "anydoc-cli",
                    "surface": "cli",
                    "identifier": "anydoc",
                    "provisioning_mode": "preinstalled",
                    "installed": True,
                    "enabled": True,
                    "auth_state": "not-required",
                    "health": "healthy",
                    "checked_at": "2026-08-11T18:30:00Z",
                    "version": "0.1.8",
                },
                {
                    "technology_id": "anydoc",
                    "interface_id": "anydoc-wasm",
                    "surface": "wasm",
                    "identifier": "@firecrawl/anydoc-wasm",
                    "provisioning_mode": "bundled",
                    "installed": True,
                    "enabled": True,
                    "auth_state": "not-required",
                    "health": "healthy",
                    "checked_at": "2026-08-11T18:30:00Z",
                    "version": "0.1.8",
                }
            ],
        }
        self.assertEqual(
            [],
            technology_intelligence.validate_runtime_inventory(
                inventory,
                self.snapshot["runtime-capability-schema"],
                known_technology_ids={item["id"] for item in self.snapshot["technologies"]["technologies"]},
                known_interfaces=interfaces,
                reference_time=datetime(2026, 8, 11, 18, 45, tzinfo=timezone.utc),
            ),
        )
        rows = technology_intelligence.query_snapshot(
            self.snapshot,
            capability="document-to-markdown",
            runtime_inventory=inventory,
            runtime_reference_time=datetime(2026, 8, 11, 18, 45, tzinfo=timezone.utc),
        )
        self.assertEqual(2, len(rows[0]["runtime_capabilities"]))
        runtime = rows[0]["runtime_capabilities"][0]
        self.assertEqual("anydoc-cli", runtime["interface"]["id"])
        self.assertEqual("preinstalled", runtime["provisioning_mode"])
        cli_rows = technology_intelligence.query_snapshot(
            self.snapshot,
            interface="anydoc-cli",
            runtime_inventory=inventory,
            runtime_reference_time=datetime(2026, 8, 11, 18, 45, tzinfo=timezone.utc),
        )
        self.assertEqual(["anydoc-cli"], [item["id"] for item in cli_rows[0]["interfaces"]])
        self.assertEqual(
            ["anydoc-cli"],
            [item["interface_id"] for item in cli_rows[0]["runtime_capabilities"]],
        )
        self.assertEqual(before, json.dumps(self.snapshot, default=str, sort_keys=True))

    def test_runtime_inventory_rejects_wrong_interface_owner_and_surface(self) -> None:
        interfaces = {item["id"]: item for item in self.snapshot["interfaces"]["interfaces"]}
        inventory = {
            "schema_version": "technology_intelligence.runtime_inventory.v1",
            "observed_at": "2026-08-11T18:30:00Z",
            "capabilities": [
                {
                    "technology_id": "react",
                    "interface_id": "anydoc-cli",
                    "surface": "sdk",
                    "identifier": "fixture",
                    "provisioning_mode": "bundled",
                    "installed": True,
                    "enabled": True,
                    "auth_state": "not-required",
                    "health": "healthy",
                    "checked_at": "2026-08-11T18:30:00Z",
                }
            ],
        }
        errors = technology_intelligence.validate_runtime_inventory(
            inventory,
            self.snapshot["runtime-capability-schema"],
            known_technology_ids={item["id"] for item in self.snapshot["technologies"]["technologies"]},
            known_interfaces=interfaces,
            reference_time=datetime(2026, 8, 11, 18, 45, tzinfo=timezone.utc),
        )
        joined = "\n".join(errors)
        self.assertIn("belongs to another technology", joined)
        self.assertIn("has a different surface", joined)
        self.assertIn("provisioning_mode is not documented", joined)

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

    def test_runtime_inventory_rejects_unknown_stale_blank_and_impossible_facts(self) -> None:
        inventory = {
            "schema_version": "technology_intelligence.runtime_inventory.v1",
            "observed_at": "2026-08-10T12:00:00Z",
            "access_token": "synthetic-secret",
            "capabilities": [
                {
                    "technology_id": "unknown-technology",
                    "surface": "api",
                    "identifier": "",
                    "installed": False,
                    "enabled": True,
                    "auth_state": "verified",
                    "health": "healthy",
                    "checked_at": "2020-01-01T00:00:00Z",
                    "access_token": "synthetic-secret",
                }
            ],
        }
        known_ids = {item["id"] for item in self.snapshot["technologies"]["technologies"]}
        errors = technology_intelligence.validate_runtime_inventory(
            inventory,
            self.snapshot["runtime-capability-schema"],
            known_technology_ids=known_ids,
        )
        joined = "\n".join(errors)
        self.assertIn("$.access_token is forbidden", joined)
        self.assertIn("unsupported field access_token", joined)
        self.assertIn("unknown technology", joined)
        self.assertIn("identifier must be a non-empty string", joined)
        self.assertIn("cannot be enabled when not installed", joined)
        self.assertIn("cannot be healthy when not installed", joined)
        self.assertIn("cannot have verified auth unless installed and enabled", joined)
        self.assertIn("exceeds max age", joined)

    def test_query_rejects_unknown_runtime_technology(self) -> None:
        inventory = {
            "schema_version": "technology_intelligence.runtime_inventory.v1",
            "observed_at": "2026-08-11T12:00:00Z",
            "capabilities": [
                {
                    "technology_id": "unknown-technology",
                    "surface": "api",
                    "identifier": "fixture",
                    "installed": True,
                    "enabled": True,
                    "auth_state": "configured",
                    "health": "degraded",
                    "checked_at": "2026-08-11T12:00:00Z",
                }
            ],
        }
        with self.assertRaisesRegex(technology_intelligence.SnapshotError, "unknown technology"):
            technology_intelligence.query_snapshot(
                self.snapshot,
                runtime_inventory=inventory,
                runtime_reference_time=datetime(2026, 8, 11, 12, 30, tzinfo=timezone.utc),
            )

    def test_runtime_inventory_rejects_an_old_observation_even_when_checks_match_it(self) -> None:
        inventory = {
            "schema_version": "technology_intelligence.runtime_inventory.v1",
            "observed_at": "2020-01-01T00:00:00Z",
            "capabilities": [
                {
                    "technology_id": "mcp-stdio",
                    "surface": "mcp",
                    "identifier": "fixture",
                    "installed": True,
                    "enabled": True,
                    "auth_state": "not-required",
                    "health": "healthy",
                    "checked_at": "2020-01-01T00:00:00Z",
                }
            ],
        }
        errors = technology_intelligence.validate_runtime_inventory(
            inventory,
            self.snapshot["runtime-capability-schema"],
            known_technology_ids={item["id"] for item in self.snapshot["technologies"]["technologies"]},
            reference_time=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        )
        self.assertTrue(any("observed_at exceeds max age" in error for error in errors))

    def test_staleness_is_explicit_for_seed_and_future_date(self) -> None:
        current = technology_intelligence.staleness_report(self.snapshot, date(2026, 8, 10))
        self.assertEqual([], current["stale_sources"])
        self.assertEqual([], current["expired_assessments"])
        future = technology_intelligence.staleness_report(self.snapshot, date(2032, 1, 1))
        self.assertEqual(len(self.snapshot["sources"]["sources"]), len(future["stale_sources"]))
        self.assertEqual(len(self.snapshot["assessments"]["assessments"]), len(future["expired_assessments"]))

    def test_six_month_window_does_not_treat_recent_retrieval_as_recent_publication(self) -> None:
        report = technology_intelligence.evidence_window_report(
            self.snapshot,
            date(2026, 2, 11),
            date(2026, 8, 11),
        )
        self.assertEqual(18, report["source_counts"]["published_in_window"])
        self.assertEqual(14, report["covered_technology_count"])
        self.assertEqual(10, report["technology_gap_count"])
        coverage = {item["technology_id"]: item for item in report["technology_coverage"]}
        self.assertEqual("covered", coverage["a2a-protocol"]["status"])
        self.assertEqual("covered", coverage["agent-client-protocol"]["status"])
        self.assertEqual("gap", coverage["vue"]["status"])
        self.assertEqual("covered", coverage["anydoc"]["status"])
        self.assertIn("vue-official", report["undated_or_live"])

    def test_record_ids_are_path_safe_lowercase_slugs(self) -> None:
        errors: list[str] = []
        technology_intelligence._ids([{"id": "../escape"}], "sources", errors)
        self.assertTrue(any("lowercase kebab-case" in error for error in errors))

    def test_query_supports_multiple_profile_assessments_per_technology(self) -> None:
        snapshot = copy.deepcopy(self.snapshot)
        second = copy.deepcopy(snapshot["assessments"]["assessments"][0])
        second["id"] = second["id"] + "-enterprise"
        second["profile"] = {
            "stages": ["enterprise-critical"],
            "use_cases": ["synthetic second profile"],
            "constraints": ["synthetic fixture only"],
        }
        snapshot["assessments"]["assessments"].append(second)
        rows = technology_intelligence.query_snapshot(
            snapshot,
            technology=second["technology_id"],
        )
        self.assertEqual(2, len(rows))
        self.assertEqual(
            sorted(row["assessment"]["id"] for row in rows),
            [row["assessment"]["id"] for row in rows],
        )

    def test_validator_allows_multiple_profile_assessments_per_technology(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin_root = Path(temporary) / "technology-intelligence"
            shutil.copytree(PLUGIN_ROOT, plugin_root)
            assessment_path = plugin_root / "data" / "assessments.v1.json"
            document = json.loads(assessment_path.read_text(encoding="utf-8"))
            second = copy.deepcopy(document["assessments"][0])
            second["id"] = second["id"] + "-enterprise"
            second["profile"] = {
                "stages": ["enterprise-critical"],
                "use_cases": ["synthetic second profile"],
                "constraints": ["synthetic fixture only"],
            }
            document["assessments"].append(second)
            assessment_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            manifest_path = plugin_root / "data" / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "assessments.v1.json":
                    entry["record_count"] += 1
                    entry["sha256"] = technology_intelligence._sha256(assessment_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            self.assertEqual([], technology_intelligence.validate_plugin(plugin_root))

    def test_validator_rejects_duplicate_decision_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin_root = Path(temporary) / "technology-intelligence"
            shutil.copytree(PLUGIN_ROOT, plugin_root)
            assessment_path = plugin_root / "data" / "assessments.v1.json"
            document = json.loads(assessment_path.read_text(encoding="utf-8"))
            duplicate = copy.deepcopy(document["assessments"][0])
            duplicate["id"] = duplicate["id"] + "-duplicate"
            for field in ("stages", "use_cases", "constraints"):
                duplicate["profile"][field] = list(reversed(duplicate["profile"][field]))
            document["assessments"].append(duplicate)
            assessment_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            manifest_path = plugin_root / "data" / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "assessments.v1.json":
                    entry["record_count"] += 1
                    entry["sha256"] = technology_intelligence._sha256(assessment_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            errors = technology_intelligence.validate_plugin(plugin_root)
            self.assertTrue(any("duplicates decision profile" in error for error in errors))

    def test_markdown_query_surfaces_context_confidence_limitations_and_freshness(self) -> None:
        rows = technology_intelligence.query_snapshot(
            self.snapshot,
            technology="nextjs",
            as_of=date(2026, 8, 11),
        )
        markdown = technology_intelligence._render_query_markdown(rows)
        for expected in (
            "Profile constraints:",
            "Assessment confidence:",
            "Rationale:",
            "Alternatives:",
            "Observation limitation:",
            "published 2026-03-18",
            "Cited-source retrieval status:",
            "Retrieval freshness is separate from publication currency",
        ):
            self.assertIn(expected, markdown)

    def test_capability_and_interface_relationships_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin_root = Path(temporary) / "technology-intelligence"
            shutil.copytree(PLUGIN_ROOT, plugin_root)
            interface_path = plugin_root / "data" / "interfaces.v1.json"
            document = json.loads(interface_path.read_text(encoding="utf-8"))
            document["interfaces"][0]["capability_ids"] = ["missing-capability"]
            document["interfaces"][0]["installed"] = True
            interface_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            manifest_path = plugin_root / "data" / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "interfaces.v1.json":
                    entry["sha256"] = technology_intelligence._sha256(interface_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            errors = technology_intelligence.validate_plugin(plugin_root)
            joined = "\n".join(errors)
            self.assertIn("references unknown capability missing-capability", joined)
            self.assertIn("runtime state key forbidden", joined)

        with tempfile.TemporaryDirectory() as temporary:
            plugin_root = Path(temporary) / "technology-intelligence"
            shutil.copytree(PLUGIN_ROOT, plugin_root)
            technology_path = plugin_root / "data" / "technologies.v1.json"
            document = json.loads(technology_path.read_text(encoding="utf-8"))
            react = next(item for item in document["technologies"] if item["id"] == "react")
            react["capability_ids"] = ["document-to-markdown"]
            technology_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            manifest_path = plugin_root / "data" / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "technologies.v1.json":
                    entry["sha256"] = technology_intelligence._sha256(technology_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            errors = technology_intelligence.validate_plugin(plugin_root)
            self.assertIn(
                "technology react capability document-to-markdown has no matching interface",
                errors,
            )

    def test_load_and_query_frozen_v02_snapshot_without_additive_datasets(self) -> None:
        snapshot = technology_intelligence.load_snapshot(LEGACY_V02_FIXTURE)
        self.assertEqual([], snapshot["capabilities"]["capabilities"])
        self.assertEqual([], snapshot["interfaces"]["interfaces"])
        rows = technology_intelligence.query_snapshot(snapshot, technology="legacy-react")
        self.assertEqual(["legacy-react"], [row["technology"]["id"] for row in rows])
        self.assertEqual([], rows[0]["capabilities"])
        self.assertEqual([], rows[0]["interfaces"])

    def test_diff_accepts_legacy_directory_without_additive_datasets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            old_dir = temporary_path / "old"
            new_dir = temporary_path / "new"
            shutil.copytree(PLUGIN_ROOT / "data", old_dir)
            shutil.copytree(PLUGIN_ROOT / "data", new_dir)
            for filename in ("capabilities.v1.json", "interfaces.v1.json"):
                (old_dir / filename).unlink()
            manifest_path = old_dir / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"] = [
                entry
                for entry in manifest["files"]
                if entry["path"] not in {"capabilities.v1.json", "interfaces.v1.json"}
            ]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            result = technology_intelligence.diff_directories(old_dir, new_dir)
            self.assertEqual(
                ["document-to-markdown"],
                result["datasets"]["capabilities"]["added"],
            )
            self.assertEqual(
                sorted(item["id"] for item in self.snapshot["interfaces"]["interfaces"]),
                result["datasets"]["interfaces"]["added"],
            )

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
            manifest_path = new_dir / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "observations.v1.json":
                    entry["sha256"] = technology_intelligence._sha256(observation_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            result = technology_intelligence.diff_directories(old_dir, new_dir)
            self.assertEqual([changed_id], result["datasets"]["observations"]["changed"])
            self.assertEqual([], result["datasets"]["assessments"]["changed"])

    def test_diff_rejects_a_directory_with_an_unbound_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            old_dir = temporary_path / "old"
            new_dir = temporary_path / "new"
            shutil.copytree(PLUGIN_ROOT / "data", old_dir)
            shutil.copytree(PLUGIN_ROOT / "data", new_dir)
            observation_path = new_dir / "observations.v1.json"
            document = json.loads(observation_path.read_text(encoding="utf-8"))
            document["observations"][0]["limitations"] += " Unbound change."
            observation_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(technology_intelligence.SnapshotError, "manifest hash mismatch"):
                technology_intelligence.diff_directories(old_dir, new_dir)

    def test_diff_rejects_hash_bound_but_semantically_invalid_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            old_dir = temporary_path / "old"
            new_dir = temporary_path / "new"
            shutil.copytree(PLUGIN_ROOT / "data", old_dir)
            shutil.copytree(PLUGIN_ROOT / "data", new_dir)
            observation_path = new_dir / "observations.v1.json"
            document = json.loads(observation_path.read_text(encoding="utf-8"))
            document["observations"][0]["source_id"] = "missing-source"
            observation_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            manifest_path = new_dir / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "observations.v1.json":
                    entry["sha256"] = technology_intelligence._sha256(observation_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(technology_intelligence.SnapshotError, "unknown source missing-source"):
                technology_intelligence.diff_directories(old_dir, new_dir)

    def test_diff_rejects_hash_bound_duplicate_decision_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            old_dir = temporary_path / "old"
            new_dir = temporary_path / "new"
            shutil.copytree(PLUGIN_ROOT / "data", old_dir)
            shutil.copytree(PLUGIN_ROOT / "data", new_dir)
            assessment_path = new_dir / "assessments.v1.json"
            document = json.loads(assessment_path.read_text(encoding="utf-8"))
            duplicate = copy.deepcopy(document["assessments"][0])
            duplicate["id"] = duplicate["id"] + "-duplicate"
            for field in ("stages", "use_cases", "constraints"):
                duplicate["profile"][field] = [
                    value.swapcase() for value in reversed(duplicate["profile"][field])
                ]
            document["assessments"].append(duplicate)
            assessment_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            manifest_path = new_dir / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "assessments.v1.json":
                    entry["record_count"] += 1
                    entry["sha256"] = technology_intelligence._sha256(assessment_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(technology_intelligence.SnapshotError, "duplicates decision profile"):
                technology_intelligence.diff_directories(old_dir, new_dir)

    def test_all_synthetic_trigger_cases_match_contract(self) -> None:
        fixture = json.loads(
            (PLUGIN_ROOT / "tests" / "fixtures" / "trigger-cases.v1.json").read_text(encoding="utf-8")
        )
        contract = self.snapshot["trigger-contract"]
        required_cases = {
            "advisor-anydoc-compare",
            "advisor-anydoc-adopt",
            "maintainer-anydoc-evidence",
            "none-anydoc-convert",
            "none-anydoc-install",
        }
        self.assertTrue(required_cases.issubset({case["id"] for case in fixture["cases"]}))
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

    def test_refresh_mock_writes_hash_bound_artifact_and_receipt_only(self) -> None:
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
                now=datetime(2026, 8, 11, 19, 0, tzinfo=timezone.utc),
            )
            receipt = result["receipt"]
            capture_dir = Path(result["capture_dir"])
            self.assertEqual(payload, (capture_dir / "raw.bin").read_bytes())
            self.assertTrue((capture_dir / "receipt.json").is_file())
            self.assertTrue(receipt["network_explicit"])
            self.assertFalse(receipt["normalization_performed"])
            self.assertFalse(receipt["recommendations_changed"])
            self.assertEqual(len(payload), receipt["bytes"])
            self.assertEqual("research-2026-08-11-capability-model-v1", receipt["snapshot_id"])
            self.assertEqual(64, len(receipt["source_registry_sha256"]))
            self.assertEqual("generic-http-get", receipt["adapter"]["name"])
            self.assertEqual("not-used", receipt["cache_status"])
            self.assertEqual([], receipt["masked_fields"])
            self.assertEqual("citation-only", receipt["source_rights"]["usage_mode"])
            self.assertEqual(1, len(opener.requests))

    def test_refresh_rejects_capture_before_registry_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            opener = FakeOpener(FakeResponse(b"fixture", "https://www.thoughtworks.com/en-us/radar/faq"))
            with self.assertRaisesRegex(technology_intelligence.SnapshotError, "precedes source registry"):
                technology_intelligence.capture_source(
                    "thoughtworks-radar-faq",
                    temporary,
                    acknowledge_network=True,
                    opener=opener,
                    now=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
                )
            self.assertEqual([], opener.requests)
            self.assertEqual([], list(Path(temporary).iterdir()))

    def test_refresh_rejects_naive_capture_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            opener = FakeOpener(FakeResponse(b"fixture", "https://www.thoughtworks.com/en-us/radar/faq"))
            with self.assertRaisesRegex(technology_intelligence.SnapshotError, "must include a timezone"):
                technology_intelligence.capture_source(
                    "thoughtworks-radar-faq",
                    temporary,
                    acknowledge_network=True,
                    opener=opener,
                    now=datetime(2026, 8, 11, 12, 0),
                )
            self.assertEqual([], opener.requests)
            self.assertEqual([], list(Path(temporary).iterdir()))

    def test_refresh_rejects_a_registry_change_during_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            data_dir = temporary_path / "data"
            shutil.copytree(PLUGIN_ROOT / "data", data_dir)
            registry_path = data_dir / "source-registry.v1.json"

            class MutatingOpener(FakeOpener):
                def open(self, request, timeout: float):
                    document = json.loads(registry_path.read_text(encoding="utf-8"))
                    document["sources"][0]["edition"] = "concurrent-edit"
                    registry_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
                    return super().open(request, timeout)

            opener = MutatingOpener(FakeResponse(b"fixture", "https://www.thoughtworks.com/en-us/radar/faq"))
            with (
                mock.patch.object(technology_intelligence, "DATA_DIR", data_dir),
                mock.patch.object(technology_intelligence, "validate_plugin", return_value=[]),
                self.assertRaisesRegex(technology_intelligence.SnapshotError, "changed during capture"),
            ):
                technology_intelligence.capture_source(
                    "thoughtworks-radar-faq",
                    temporary_path / "output",
                    acknowledge_network=True,
                    opener=opener,
                    now=datetime(2026, 8, 11, 19, 0, tzinfo=timezone.utc),
                )
            self.assertFalse((temporary_path / "output").exists())

    def test_source_edition_is_required_before_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin_root = Path(temporary) / "technology-intelligence"
            shutil.copytree(PLUGIN_ROOT, plugin_root)
            registry_path = plugin_root / "data" / "source-registry.v1.json"
            document = json.loads(registry_path.read_text(encoding="utf-8"))
            document["sources"][0].pop("edition")
            registry_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            manifest_path = plugin_root / "data" / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "source-registry.v1.json":
                    entry["sha256"] = technology_intelligence._sha256(registry_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            errors = technology_intelligence.validate_plugin(plugin_root)
            self.assertTrue(any("edition must be a non-empty string" in error for error in errors))

    def test_snapshot_dates_are_bound_to_manifest_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plugin_root = Path(temporary) / "technology-intelligence"
            shutil.copytree(PLUGIN_ROOT, plugin_root)
            registry_path = plugin_root / "data" / "source-registry.v1.json"
            document = json.loads(registry_path.read_text(encoding="utf-8"))
            document["generated_at"] = "2026-08-10T00:00:00Z"
            document["sources"][0]["retrieved_at"] = "2026-08-12"
            registry_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            manifest_path = plugin_root / "data" / "snapshot-manifest.v1.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest["files"]:
                if entry["path"] == "source-registry.v1.json":
                    entry["sha256"] = technology_intelligence._sha256(registry_path)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            errors = "\n".join(technology_intelligence.validate_plugin(plugin_root))
            self.assertIn("sources generated_at does not match snapshot manifest", errors)
            self.assertIn("retrieved_at follows snapshot generation", errors)

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
