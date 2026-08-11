#!/usr/bin/env python3
"""Deterministic local tooling for the Technology Intelligence snapshot.

Validation, query, staleness, diff, and trigger checks never use the network.
The refresh command is the sole network path and requires explicit acknowledgement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PLUGIN_ROOT / "data"
TRIGGER_CASES = PLUGIN_ROOT / "tests" / "fixtures" / "trigger-cases.v1.json"

DATASET_FILES = {
    "sources": ("source-registry.v1.json", "sources"),
    "technologies": ("technologies.v1.json", "technologies"),
    "observations": ("observations.v1.json", "observations"),
    "assessments": ("assessments.v1.json", "assessments"),
}
SINGLETON_FILES = {
    "runtime-capability-schema": "runtime-capability.schema.v1.json",
    "trigger-contract": "trigger-contract.v1.json",
}
EXPECTED_SCHEMA_VERSIONS = {
    "sources": "technology_intelligence.sources.v1",
    "technologies": "technology_intelligence.technologies.v1",
    "observations": "technology_intelligence.observations.v1",
    "assessments": "technology_intelligence.assessments.v1",
    "runtime-capability-schema": "technology_intelligence.runtime_capability_schema.v1",
    "trigger-contract": "technology_intelligence.trigger_contract.v1",
}
SAFE_RECORD_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
POSITIVE_DISPOSITIONS = {"recommend", "consider", "pilot"}
ALLOWED_DISPOSITIONS = POSITIVE_DISPOSITIONS | {"watch", "avoid"}
ALLOWED_ROLES = {"first-party", "independent-signal"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}
EXPECTED_FAMILIES = {
    "frontend-fullstack",
    "backend-data-infrastructure",
    "agent-delivery",
}
FORBIDDEN_SCORE_KEYS = {"score", "scores", "rank", "ranking", "weighted_score", "universal_score"}
RUNTIME_STATE_KEYS = {"installed", "enabled", "auth_state", "health", "checked_at", "permissions"}


class SnapshotError(ValueError):
    """Raised when an operation cannot safely use the snapshot."""


def _read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"cannot read JSON {path}: {exc}") from exc


def _parse_date(value: Any, label: str) -> date:
    if not isinstance(value, str):
        raise SnapshotError(f"{label} must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SnapshotError(f"{label} is not an ISO date: {value!r}") from exc


def _parse_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise SnapshotError(f"{label} must be an ISO datetime string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SnapshotError(f"{label} is not an ISO datetime: {value!r}") from exc
    if parsed.tzinfo is None:
        raise SnapshotError(f"{label} must include a timezone")
    return parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _ids(records: Any, label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(records, list):
        errors.append(f"{label} must be an array")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"{label}[{position}] must be an object")
            continue
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            errors.append(f"{label}[{position}] has no non-empty id")
        elif SAFE_RECORD_ID.fullmatch(record_id) is None:
            errors.append(f"{label}[{position}] id must be a lowercase kebab-case identifier: {record_id!r}")
        elif record_id in indexed:
            errors.append(f"duplicate {label} id: {record_id}")
        else:
            indexed[record_id] = record
    return indexed


def _walk_keys(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, key
            yield from _walk_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def _profile_identity(profile: dict[str, Any]) -> tuple[tuple[str, ...], ...] | None:
    """Return an order-insensitive identity for a valid decision profile."""
    normalized_fields: list[tuple[str, ...]] = []
    for field in ("stages", "use_cases", "constraints"):
        values = profile.get(field)
        if not isinstance(values, list) or not values:
            return None
        normalized: list[str] = []
        for value in values:
            if not isinstance(value, str) or not value.strip():
                return None
            normalized.append(" ".join(value.split()).casefold())
        normalized_fields.append(tuple(sorted(set(normalized))))
    return tuple(normalized_fields)


def _record_unique_profile(
    assessment_id: str,
    technology_id: Any,
    profile: Any,
    assessed_profiles: dict[tuple[str, tuple[tuple[str, ...], ...]], str],
    errors: list[str],
) -> None:
    """Record a valid profile identity or report a duplicate for one technology."""
    if not isinstance(technology_id, str) or not isinstance(profile, dict):
        return
    profile_identity = _profile_identity(profile)
    if profile_identity is None:
        return
    profile_key = (technology_id, profile_identity)
    previous_assessment = assessed_profiles.get(profile_key)
    if previous_assessment is not None:
        errors.append(f"assessment {assessment_id} duplicates decision profile from {previous_assessment}")
    else:
        assessed_profiles[profile_key] = assessment_id


def load_snapshot(data_dir: Path | str = DATA_DIR) -> dict[str, Any]:
    """Load the durable datasets without performing network access."""
    directory = Path(data_dir)
    snapshot: dict[str, Any] = {"data_dir": directory}
    for name, (filename, _) in DATASET_FILES.items():
        snapshot[name] = _read_json(directory / filename)
    for name, filename in SINGLETON_FILES.items():
        snapshot[name] = _read_json(directory / filename)
    manifest_path = directory / "snapshot-manifest.v1.json"
    snapshot["manifest"] = _read_json(manifest_path) if manifest_path.exists() else None
    return snapshot


def classify_prompt(prompt: str, contract: dict[str, Any]) -> str | None:
    """Apply the intentionally small deterministic trigger guard."""
    normalized = " ".join(prompt.casefold().split())
    if any(marker.casefold() in normalized for marker in contract.get("maintainer_markers", [])):
        return "technology-evidence-maintainer"
    if any(marker.casefold() in normalized for marker in contract.get("advisor_markers", [])):
        return "technology-advisor"
    return None


def validate_runtime_inventory(
    inventory: Any,
    schema: dict[str, Any],
    *,
    known_technology_ids: set[str] | None = None,
    reference_time: datetime | None = None,
) -> list[str]:
    """Validate caller-supplied runtime facts without retaining them."""
    errors: list[str] = []
    if not isinstance(inventory, dict):
        return ["runtime inventory must be an object"]
    required = schema.get("required_top_level", [])
    optional = schema.get("optional_top_level", [])
    allowed_top_level = set(required) | set(optional)
    for field in required:
        if field not in inventory:
            errors.append(f"runtime inventory missing {field}")
    for field in inventory:
        if field not in allowed_top_level:
            errors.append(f"runtime inventory has unsupported field {field}")
    forbidden = {str(item).casefold() for item in schema.get("forbidden_fields", [])}
    for key_path, key in _walk_keys(inventory):
        if key.casefold() in forbidden:
            errors.append(f"{key_path} is forbidden")
    if inventory.get("schema_version") != schema.get("runtime_schema_version"):
        errors.append("runtime inventory schema_version does not match runtime schema")
    observed_at: datetime | None = None
    try:
        observed_at = _parse_datetime(inventory.get("observed_at"), "runtime inventory observed_at")
    except SnapshotError as exc:
        errors.append(str(exc))
    capabilities = inventory.get("capabilities")
    if not isinstance(capabilities, list):
        errors.append("runtime inventory capabilities must be an array")
        return errors
    allowed_surfaces = set(schema.get("allowed_surfaces", []))
    allowed_auth = set(schema.get("allowed_auth_states", []))
    allowed_health = set(schema.get("allowed_health_states", []))
    required_capability = schema.get("capability_required", [])
    optional_capability = schema.get("capability_optional", [])
    allowed_capability = set(required_capability) | set(optional_capability)
    max_age_seconds = schema.get("max_capability_age_seconds")
    consumed_at = reference_time or datetime.now(timezone.utc)
    if consumed_at.tzinfo is None:
        errors.append("runtime inventory reference_time must include a timezone")
        consumed_at = consumed_at.replace(tzinfo=timezone.utc)
    consumed_at = consumed_at.astimezone(timezone.utc)
    if observed_at is not None:
        observed_at = observed_at.astimezone(timezone.utc)
        if observed_at > consumed_at:
            errors.append("runtime inventory observed_at cannot be in the future")
        elif isinstance(max_age_seconds, int) and (consumed_at - observed_at).total_seconds() > max_age_seconds:
            errors.append(f"runtime inventory observed_at exceeds max age of {max_age_seconds} seconds")
    seen_capabilities: set[tuple[str, str, str]] = set()
    for index, capability in enumerate(capabilities):
        label = f"runtime capability[{index}]"
        if not isinstance(capability, dict):
            errors.append(f"{label} must be an object")
            continue
        for field in required_capability:
            if field not in capability:
                errors.append(f"{label} missing {field}")
        for field in capability:
            if field not in allowed_capability:
                errors.append(f"{label} has unsupported field {field}")
        for field in ("technology_id", "surface", "identifier", "auth_state", "health"):
            value = capability.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label} {field} must be a non-empty string")
        technology_id = capability.get("technology_id")
        if known_technology_ids is not None and technology_id not in known_technology_ids:
            errors.append(f"{label} references unknown technology {technology_id!r}")
        if capability.get("surface") not in allowed_surfaces:
            errors.append(f"{label} has unsupported surface")
        if capability.get("auth_state") not in allowed_auth:
            errors.append(f"{label} has unsupported auth_state")
        if capability.get("health") not in allowed_health:
            errors.append(f"{label} has unsupported health")
        if not isinstance(capability.get("installed"), bool):
            errors.append(f"{label} installed must be boolean")
        if not isinstance(capability.get("enabled"), bool):
            errors.append(f"{label} enabled must be boolean")
        if capability.get("installed") is False and capability.get("enabled") is True:
            errors.append(f"{label} cannot be enabled when not installed")
        if capability.get("installed") is False and capability.get("health") == "healthy":
            errors.append(f"{label} cannot be healthy when not installed")
        if capability.get("enabled") is False and capability.get("health") == "healthy":
            errors.append(f"{label} cannot be healthy when disabled")
        if capability.get("auth_state") == "verified" and (
            capability.get("installed") is not True or capability.get("enabled") is not True
        ):
            errors.append(f"{label} cannot have verified auth unless installed and enabled")
        if "version" in capability and not isinstance(capability.get("version"), str):
            errors.append(f"{label} version must be a string")
        if "permissions" in capability:
            permissions = capability.get("permissions")
            if not isinstance(permissions, list) or any(
                not isinstance(permission, str) or not permission.strip() for permission in permissions
            ):
                errors.append(f"{label} permissions must be an array of non-empty strings")
        if "notes" in capability and not isinstance(capability.get("notes"), str):
            errors.append(f"{label} notes must be a string")
        checked_at: datetime | None = None
        try:
            checked_at = _parse_datetime(capability.get("checked_at"), f"{label} checked_at")
        except SnapshotError as exc:
            errors.append(str(exc))
        if checked_at is not None and observed_at is not None:
            if checked_at > observed_at:
                errors.append(f"{label} checked_at cannot follow observed_at")
            elif isinstance(max_age_seconds, int) and (observed_at - checked_at).total_seconds() > max_age_seconds:
                errors.append(f"{label} checked_at exceeds max age of {max_age_seconds} seconds")
        identity = (
            str(capability.get("technology_id")),
            str(capability.get("surface")),
            str(capability.get("identifier")),
        )
        if identity in seen_capabilities:
            errors.append(f"{label} duplicates capability identity {identity!r}")
        seen_capabilities.add(identity)
    return errors


def validate_plugin(root: Path | str = PLUGIN_ROOT, check_manifest: bool = True) -> list[str]:
    """Return every deterministic validation error; never access the network."""
    plugin_root = Path(root)
    data_dir = plugin_root / "data"
    errors: list[str] = []
    try:
        snapshot = load_snapshot(data_dir)
    except SnapshotError as exc:
        return [str(exc)]

    # Manifest parity and focused plugin shape.
    try:
        codex_manifest = _read_json(plugin_root / ".codex-plugin" / "plugin.json")
        claude_manifest = _read_json(plugin_root / ".claude-plugin" / "plugin.json")
    except SnapshotError as exc:
        errors.append(str(exc))
        codex_manifest, claude_manifest = {}, {}
    shared_fields = ("name", "version", "description", "author", "license", "keywords")
    for field in shared_fields:
        if codex_manifest.get(field) != claude_manifest.get(field):
            errors.append(f"manifest parity mismatch for {field}")
    if codex_manifest.get("name") != "technology-intelligence":
        errors.append("Codex manifest name must be technology-intelligence")
    skill_names = sorted(path.parent.name for path in (plugin_root / "skills").glob("*/SKILL.md"))
    if skill_names != ["technology-advisor", "technology-evidence-maintainer"]:
        errors.append(f"expected exactly two focused skills, found {skill_names}")
    for skill_name in skill_names:
        if not (plugin_root / "skills" / skill_name / "agents" / "openai.yaml").is_file():
            errors.append(f"missing agents/openai.yaml for {skill_name}")
    for reference in (
        "evidence-methodology.md",
        "decision-evidence-contract.md",
        "source-and-licensing-ledger.md",
        "refresh-policy.md",
        "runtime-boundary.md",
    ):
        if not (plugin_root / "references" / reference).is_file():
            errors.append(f"missing reference {reference}")
    try:
        icon_prompt = _read_json(plugin_root / "assets" / "icon-prompt.json")
        if icon_prompt.get("recommended_asset_path") != "assets/icon.png":
            errors.append("icon prompt recommended_asset_path must be assets/icon.png")
    except SnapshotError as exc:
        errors.append(str(exc))

    source_doc = snapshot["sources"]
    technology_doc = snapshot["technologies"]
    observation_doc = snapshot["observations"]
    assessment_doc = snapshot["assessments"]
    for name, expected in EXPECTED_SCHEMA_VERSIONS.items():
        if snapshot[name].get("schema_version") != expected:
            errors.append(f"{name} schema_version must be {expected}")
    snapshot_ids = {
        document.get("snapshot_id")
        for document in (source_doc, technology_doc, observation_doc, assessment_doc)
    }
    if len(snapshot_ids) != 1 or None in snapshot_ids:
        errors.append("core dataset snapshot_id values must be identical and non-null")
    manifest = snapshot.get("manifest")
    snapshot_generated_at: datetime | None = None
    snapshot_cutoff: date | None = None
    if isinstance(manifest, dict):
        try:
            snapshot_generated_at = _parse_datetime(
                manifest.get("generated_at"), "snapshot manifest generated_at"
            ).astimezone(timezone.utc)
            snapshot_cutoff = snapshot_generated_at.date()
        except SnapshotError as exc:
            errors.append(str(exc))
    for document_name, document in (
        ("sources", source_doc),
        ("technologies", technology_doc),
        ("observations", observation_doc),
        ("assessments", assessment_doc),
    ):
        if "generated_at" not in document:
            continue
        try:
            generated_at = _parse_datetime(document.get("generated_at"), f"{document_name} generated_at")
            if snapshot_generated_at is not None and generated_at.astimezone(timezone.utc) != snapshot_generated_at:
                errors.append(f"{document_name} generated_at does not match snapshot manifest")
        except SnapshotError as exc:
            errors.append(str(exc))

    sources = _ids(source_doc.get("sources"), "sources", errors)
    technologies = _ids(technology_doc.get("technologies"), "technologies", errors)
    observations = _ids(observation_doc.get("observations"), "observations", errors)
    assessments = _ids(assessment_doc.get("assessments"), "assessments", errors)

    for source_id, source in sources.items():
        for field in ("publisher", "title", "source_type", "edition", "scope", "limitations"):
            if not isinstance(source.get(field), str) or not source.get(field).strip():
                errors.append(f"source {source_id} {field} must be a non-empty string")
        if source.get("evidence_role") not in ALLOWED_ROLES:
            errors.append(f"source {source_id} has unsupported evidence_role")
        parsed_url = urllib.parse.urlparse(str(source.get("url", "")))
        if parsed_url.scheme != "https" or not parsed_url.hostname:
            errors.append(f"source {source_id} must use an absolute HTTPS URL")
        retrieved: date | None = None
        published: date | None = None
        try:
            retrieved = _parse_date(source.get("retrieved_at"), f"source {source_id} retrieved_at")
        except SnapshotError as exc:
            errors.append(str(exc))
        if retrieved is not None and snapshot_cutoff is not None and retrieved > snapshot_cutoff:
            errors.append(f"source {source_id} retrieved_at follows snapshot generation")
        if source.get("published_at") is not None:
            try:
                published = _parse_date(source.get("published_at"), f"source {source_id} published_at")
            except SnapshotError as exc:
                errors.append(str(exc))
        if retrieved is not None and published is not None and published > retrieved:
            errors.append(f"source {source_id} published_at cannot follow retrieved_at")
        measurement_window = source.get("measurement_window")
        if measurement_window is not None:
            if not isinstance(measurement_window, dict):
                errors.append(f"source {source_id} measurement_window must be an object")
            else:
                try:
                    measured_from = _parse_date(measurement_window.get("start"), f"source {source_id} measurement_window.start")
                    measured_to = _parse_date(measurement_window.get("end"), f"source {source_id} measurement_window.end")
                    if measured_to < measured_from:
                        errors.append(f"source {source_id} measurement_window end must not precede start")
                    if retrieved is not None and measured_to > retrieved:
                        errors.append(f"source {source_id} measurement_window cannot follow retrieved_at")
                except SnapshotError as exc:
                    errors.append(str(exc))
        if not isinstance(source.get("freshness_days"), int) or source.get("freshness_days", 0) <= 0:
            errors.append(f"source {source_id} freshness_days must be a positive integer")
        rights = source.get("rights")
        if not isinstance(rights, dict) or not rights.get("usage_mode") or not rights.get("license"):
            errors.append(f"source {source_id} must declare rights usage_mode and license")
        refresh = source.get("refresh")
        if not isinstance(refresh, dict):
            errors.append(f"source {source_id} must declare refresh policy")
        else:
            hosts = refresh.get("allowed_hosts")
            if not isinstance(hosts, list) or not hosts:
                errors.append(f"source {source_id} refresh allowed_hosts must be non-empty")
            elif parsed_url.hostname and parsed_url.hostname.casefold() not in {str(h).casefold() for h in hosts}:
                errors.append(f"source {source_id} URL host is absent from refresh allowlist")
            if not isinstance(refresh.get("enabled"), bool):
                errors.append(f"source {source_id} refresh enabled must be boolean")
            if not isinstance(refresh.get("max_bytes"), int) or refresh.get("max_bytes", 0) <= 0:
                errors.append(f"source {source_id} refresh max_bytes must be positive")

    if not 18 <= len(technologies) <= 24:
        errors.append(f"technology count must be 18-24, found {len(technologies)}")
    family_counts = Counter(record.get("family") for record in technologies.values())
    if set(family_counts) != EXPECTED_FAMILIES:
        errors.append(f"technology families must be {sorted(EXPECTED_FAMILIES)}")
    if any(family_counts[family] == 0 for family in EXPECTED_FAMILIES):
        errors.append("each technology family must contain a candidate")
    for technology_id, technology in technologies.items():
        if not technology.get("name") or not technology.get("kind") or not technology.get("summary"):
            errors.append(f"technology {technology_id} is missing identity fields")
        official_ids = technology.get("official_source_ids")
        if not isinstance(official_ids, list):
            errors.append(f"technology {technology_id} official_source_ids must be an array")
            continue
        for source_id in official_ids:
            if source_id not in sources:
                errors.append(f"technology {technology_id} references unknown source {source_id}")
            elif sources[source_id].get("evidence_role") != "first-party":
                errors.append(f"technology {technology_id} official source {source_id} is not first-party")
    for source_id, source in sources.items():
        affiliations = source.get("affiliated_technology_ids", [])
        if not isinstance(affiliations, list):
            errors.append(f"source {source_id} affiliated_technology_ids must be an array")
        else:
            for technology_id in affiliations:
                if technology_id not in technologies:
                    errors.append(f"source {source_id} has unknown technology affiliation {technology_id}")

    observations_by_technology: dict[str, list[dict[str, Any]]] = {}
    for observation_id, observation in observations.items():
        technology_id = observation.get("technology_id")
        source_id = observation.get("source_id")
        if technology_id not in technologies:
            errors.append(f"observation {observation_id} references unknown technology {technology_id}")
        else:
            observations_by_technology.setdefault(technology_id, []).append(observation)
        if source_id not in sources:
            errors.append(f"observation {observation_id} references unknown source {source_id}")
        for field in ("signal", "claim", "scope", "confidence", "limitations"):
            if not isinstance(observation.get(field), str) or not observation.get(field):
                errors.append(f"observation {observation_id} missing {field}")
        if observation.get("confidence") not in ALLOWED_CONFIDENCE:
            errors.append(f"observation {observation_id} has unsupported confidence")
        try:
            observed = _parse_date(observation.get("observed_at"), f"observation {observation_id} observed_at")
            source = sources.get(source_id)
            if source is not None:
                retrieved = _parse_date(source.get("retrieved_at"), f"source {source_id} retrieved_at")
                if observed < retrieved:
                    errors.append(f"observation {observation_id} observed_at precedes source retrieval")
            if snapshot_cutoff is not None and observed > snapshot_cutoff:
                errors.append(f"observation {observation_id} observed_at follows snapshot generation")
        except SnapshotError as exc:
            errors.append(str(exc))
    for technology_id in technologies:
        if technology_id not in observations_by_technology:
            errors.append(f"technology {technology_id} has no observation")

    assessed_technologies: set[str] = set()
    assessed_profiles: dict[tuple[str, tuple[tuple[str, ...], ...]], str] = {}
    for assessment_id, assessment in assessments.items():
        technology_id = assessment.get("technology_id")
        if technology_id not in technologies:
            errors.append(f"assessment {assessment_id} references unknown technology {technology_id}")
        else:
            assessed_technologies.add(technology_id)
        disposition = assessment.get("disposition")
        if disposition not in ALLOWED_DISPOSITIONS:
            errors.append(f"assessment {assessment_id} has unsupported disposition")
        profile = assessment.get("profile")
        if not isinstance(profile, dict):
            errors.append(f"assessment {assessment_id} profile must be an object")
        else:
            for field in ("stages", "use_cases", "constraints"):
                if not isinstance(profile.get(field), list) or not profile.get(field):
                    errors.append(f"assessment {assessment_id} profile {field} must be non-empty")
                elif any(not isinstance(item, str) or not item.strip() for item in profile[field]):
                    errors.append(f"assessment {assessment_id} profile {field} values must be non-empty strings")
            _record_unique_profile(assessment_id, technology_id, profile, assessed_profiles, errors)
        for field in ("rationale", "hard_gates"):
            if not isinstance(assessment.get(field), list) or not assessment.get(field):
                errors.append(f"assessment {assessment_id} {field} must be non-empty")
        if not isinstance(assessment.get("alternatives"), list):
            errors.append(f"assessment {assessment_id} alternatives must be an array")
        else:
            for alternative in assessment.get("alternatives", []):
                if alternative not in technologies:
                    errors.append(f"assessment {assessment_id} references unknown alternative {alternative}")
                if alternative == technology_id:
                    errors.append(f"assessment {assessment_id} cannot list itself as an alternative")
        evidence_ids = assessment.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            errors.append(f"assessment {assessment_id} evidence_ids must be non-empty")
            evidence_records: list[dict[str, Any]] = []
        else:
            evidence_records = []
            for evidence_id in evidence_ids:
                observation = observations.get(evidence_id)
                if observation is None:
                    errors.append(f"assessment {assessment_id} references unknown observation {evidence_id}")
                elif observation.get("technology_id") != technology_id:
                    errors.append(f"assessment {assessment_id} uses evidence for another technology")
                else:
                    evidence_records.append(observation)
        if disposition in POSITIVE_DISPOSITIONS:
            official_source_ids = set(technologies.get(technology_id, {}).get("official_source_ids", []))
            has_candidate_first_party_signal = any(
                item.get("source_id") in official_source_ids
                and sources[item["source_id"]].get("evidence_role") == "first-party"
                for item in evidence_records
                if item.get("source_id") in sources
            )
            has_candidate_independent_signal = any(
                sources[item["source_id"]].get("evidence_role") == "independent-signal"
                and technology_id not in sources[item["source_id"]].get("affiliated_technology_ids", [])
                for item in evidence_records
                if item.get("source_id") in sources
            )
            gap = assessment.get("verification_gap")
            if not has_candidate_first_party_signal:
                errors.append(f"positive assessment {assessment_id} lacks candidate first-party evidence")
            if not has_candidate_independent_signal and not (isinstance(gap, str) and gap.strip()):
                errors.append(f"positive assessment {assessment_id} needs an independent signal or explicit gap")
        if assessment.get("confidence") not in ALLOWED_CONFIDENCE:
            errors.append(f"assessment {assessment_id} has unsupported confidence")
        try:
            reviewed = _parse_date(assessment.get("reviewed_at"), f"assessment {assessment_id} reviewed_at")
            expires = _parse_date(assessment.get("expires_at"), f"assessment {assessment_id} expires_at")
            if expires <= reviewed:
                errors.append(f"assessment {assessment_id} expires_at must follow reviewed_at")
            evidence_dates = [
                _parse_date(item.get("observed_at"), f"observation {item.get('id')} observed_at")
                for item in evidence_records
            ]
            if evidence_dates and reviewed < max(evidence_dates):
                errors.append(f"assessment {assessment_id} reviewed_at precedes cited evidence")
            if snapshot_cutoff is not None and reviewed > snapshot_cutoff:
                errors.append(f"assessment {assessment_id} reviewed_at follows snapshot generation")
        except SnapshotError as exc:
            errors.append(str(exc))
    if assessed_technologies != set(technologies):
        missing = sorted(set(technologies) - assessed_technologies)
        errors.append(f"every technology needs at least one assessment; missing {missing}")

    for document_name in ("sources", "technologies", "observations", "assessments"):
        for key_path, key in _walk_keys(snapshot[document_name]):
            if key.casefold() in FORBIDDEN_SCORE_KEYS:
                errors.append(f"opaque score key forbidden at {document_name}:{key_path}")
            if document_name != "sources" and key.casefold() in RUNTIME_STATE_KEYS:
                errors.append(f"runtime state key forbidden in durable data at {document_name}:{key_path}")

    runtime_schema = snapshot["runtime-capability-schema"]
    if runtime_schema.get("persistence") != "never" or runtime_schema.get("join_key") != "technology_id":
        errors.append("runtime capability schema must declare persistence=never and join_key=technology_id")
    if runtime_schema.get("runtime_schema_version") != "technology_intelligence.runtime_inventory.v1":
        errors.append("runtime capability schema has unexpected runtime_schema_version")
    if not isinstance(runtime_schema.get("max_capability_age_seconds"), int) or runtime_schema.get("max_capability_age_seconds", 0) <= 0:
        errors.append("runtime capability schema max_capability_age_seconds must be positive")
    required_runtime = runtime_schema.get("capability_required", [])
    optional_runtime = runtime_schema.get("capability_optional", [])
    if not isinstance(required_runtime, list) or not isinstance(optional_runtime, list):
        errors.append("runtime capability schema field lists must be arrays")
    elif set(required_runtime) & set(optional_runtime):
        errors.append("runtime capability required and optional fields must not overlap")

    try:
        trigger_cases_doc = _read_json(plugin_root / "tests" / "fixtures" / "trigger-cases.v1.json")
        cases = trigger_cases_doc.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append("trigger cases must be a non-empty array")
        else:
            case_ids: set[str] = set()
            expected_values: set[str | None] = set()
            for case in cases:
                case_id = case.get("id") if isinstance(case, dict) else None
                if not case_id or case_id in case_ids:
                    errors.append(f"trigger case has missing or duplicate id: {case_id}")
                    continue
                case_ids.add(case_id)
                expected = case.get("expected_skill")
                expected_values.add(expected)
                actual = classify_prompt(str(case.get("prompt", "")), snapshot["trigger-contract"])
                if actual != expected:
                    errors.append(f"trigger case {case_id}: expected {expected!r}, got {actual!r}")
            required_outcomes = {"technology-advisor", "technology-evidence-maintainer", None}
            if not required_outcomes.issubset(expected_values):
                errors.append("trigger cases must cover both skills and negative routing")
    except SnapshotError as exc:
        errors.append(str(exc))

    if check_manifest:
        if not isinstance(manifest, dict):
            errors.append("missing snapshot-manifest.v1.json")
        else:
            if manifest.get("schema_version") != "technology_intelligence.snapshot_manifest.v1":
                errors.append("snapshot manifest schema_version is invalid")
            if manifest.get("snapshot_id") not in snapshot_ids:
                errors.append("snapshot manifest snapshot_id does not match core datasets")
            entries = manifest.get("files")
            if not isinstance(entries, list) or not entries:
                errors.append("snapshot manifest files must be non-empty")
            else:
                seen_paths: set[str] = set()
                expected_paths = {
                    filename for filename, _ in DATASET_FILES.values()
                } | set(SINGLETON_FILES.values())
                for entry in entries:
                    relative = entry.get("path") if isinstance(entry, dict) else None
                    if not isinstance(relative, str) or relative in seen_paths:
                        errors.append(f"snapshot manifest has invalid or duplicate path {relative!r}")
                        continue
                    seen_paths.add(relative)
                    if relative not in expected_paths:
                        errors.append(f"snapshot manifest includes unexpected file {relative}")
                        continue
                    path = data_dir / relative
                    if not path.is_file():
                        errors.append(f"snapshot manifest file missing: {relative}")
                        continue
                    if entry.get("sha256") != _sha256(path):
                        errors.append(f"snapshot manifest hash mismatch: {relative}")
                    document = _read_json(path)
                    expected_count = 1
                    for _, (candidate_file, record_key) in DATASET_FILES.items():
                        if candidate_file == relative:
                            expected_count = len(document.get(record_key, []))
                    if entry.get("record_count") != expected_count:
                        errors.append(f"snapshot manifest count mismatch: {relative}")
                    if entry.get("schema_version") != document.get("schema_version"):
                        errors.append(f"snapshot manifest schema mismatch: {relative}")
                if seen_paths != expected_paths:
                    errors.append(f"snapshot manifest paths mismatch; expected {sorted(expected_paths)}")
    return errors


def staleness_report(snapshot: dict[str, Any], as_of: date) -> dict[str, Any]:
    """Return source and assessment expiry facts for a specified date."""
    stale_sources: list[dict[str, Any]] = []
    for source in snapshot["sources"].get("sources", []):
        retrieved = _parse_date(source["retrieved_at"], f"source {source['id']} retrieved_at")
        due_on = retrieved + timedelta(days=int(source["freshness_days"]))
        if as_of > due_on:
            stale_sources.append(
                {
                    "id": source["id"],
                    "retrieved_at": retrieved.isoformat(),
                    "due_on": due_on.isoformat(),
                    "days_overdue": (as_of - due_on).days,
                }
            )
    expired_assessments: list[dict[str, Any]] = []
    for assessment in snapshot["assessments"].get("assessments", []):
        expires = _parse_date(assessment["expires_at"], f"assessment {assessment['id']} expires_at")
        if as_of > expires:
            expired_assessments.append(
                {
                    "id": assessment["id"],
                    "technology_id": assessment["technology_id"],
                    "expires_at": expires.isoformat(),
                    "days_overdue": (as_of - expires).days,
                }
            )
    return {
        "as_of": as_of.isoformat(),
        "stale_sources": sorted(stale_sources, key=lambda item: item["id"]),
        "expired_assessments": sorted(expired_assessments, key=lambda item: item["id"]),
    }


def evidence_window_report(snapshot: dict[str, Any], since: date, as_of: date) -> dict[str, Any]:
    """Separate publication currency from retrieval freshness for one bounded window."""
    if since > as_of:
        raise SnapshotError("evidence window since date must not follow as-of date")
    sources = {item["id"]: item for item in snapshot["sources"].get("sources", [])}
    technologies = {item["id"]: item for item in snapshot["technologies"].get("technologies", [])}
    published_in_window: list[str] = []
    older_publications: list[str] = []
    undated_or_live: list[str] = []
    future_publications: list[str] = []
    for source_id, source in sources.items():
        published_at = source.get("published_at")
        if published_at is None:
            undated_or_live.append(source_id)
            continue
        published = _parse_date(published_at, f"source {source_id} published_at")
        if published > as_of:
            future_publications.append(source_id)
        elif published >= since:
            published_in_window.append(source_id)
        else:
            older_publications.append(source_id)
    window_observations: dict[str, list[str]] = {}
    for observation in snapshot["observations"].get("observations", []):
        source = sources.get(observation.get("source_id"))
        if source is None or source.get("published_at") is None:
            continue
        observed = _parse_date(observation.get("observed_at"), f"observation {observation.get('id')} observed_at")
        published = _parse_date(source.get("published_at"), f"source {source.get('id')} published_at")
        if since <= observed <= as_of and since <= published <= as_of:
            window_observations.setdefault(observation["technology_id"], []).append(observation["id"])
    coverage = [
        {
            "technology_id": technology_id,
            "name": technology["name"],
            "fresh_observation_ids": sorted(window_observations.get(technology_id, [])),
            "status": "covered" if window_observations.get(technology_id) else "gap",
        }
        for technology_id, technology in sorted(technologies.items())
    ]
    return {
        "since": since.isoformat(),
        "as_of": as_of.isoformat(),
        "definition": "covered requires both source publication and observation dates inside the window; retrieval date alone does not qualify",
        "source_counts": {
            "published_in_window": len(published_in_window),
            "older_publications": len(older_publications),
            "undated_or_live": len(undated_or_live),
            "future_publications": len(future_publications),
        },
        "published_in_window": sorted(published_in_window),
        "older_publications": sorted(older_publications),
        "undated_or_live": sorted(undated_or_live),
        "future_publications": sorted(future_publications),
        "technology_coverage": coverage,
        "covered_technology_count": sum(item["status"] == "covered" for item in coverage),
        "technology_gap_count": sum(item["status"] == "gap" for item in coverage),
    }


def query_snapshot(
    snapshot: dict[str, Any],
    *,
    family: str | None = None,
    stage: str | None = None,
    use_case: str | None = None,
    disposition: str | None = None,
    technology: str | None = None,
    limit: int | None = None,
    as_of: date | None = None,
    runtime_inventory: dict[str, Any] | None = None,
    runtime_reference_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """Query profile-specific assessments and attach their dated evidence."""
    technologies = {item["id"]: item for item in snapshot["technologies"]["technologies"]}
    observations = {item["id"]: item for item in snapshot["observations"]["observations"]}
    sources = {item["id"]: item for item in snapshot["sources"]["sources"]}
    runtime_by_technology: dict[str, list[dict[str, Any]]] = {}
    if runtime_inventory is not None:
        runtime_errors = validate_runtime_inventory(
            runtime_inventory,
            snapshot["runtime-capability-schema"],
            known_technology_ids=set(technologies),
            reference_time=runtime_reference_time,
        )
        if runtime_errors:
            raise SnapshotError("invalid runtime inventory: " + "; ".join(runtime_errors))
        for capability in runtime_inventory["capabilities"]:
            runtime_by_technology.setdefault(capability["technology_id"], []).append(dict(capability))
    query_name = technology.casefold() if technology else None
    query_use_case = use_case.casefold() if use_case else None
    rows: list[dict[str, Any]] = []
    for assessment in snapshot["assessments"]["assessments"]:
        candidate = technologies[assessment["technology_id"]]
        if family and candidate.get("family") != family:
            continue
        if stage and stage not in assessment["profile"].get("stages", []):
            continue
        if disposition and assessment.get("disposition") != disposition:
            continue
        if query_use_case:
            haystack = " ".join(assessment["profile"].get("use_cases", []) + candidate.get("tags", [])).casefold()
            if query_use_case not in haystack:
                continue
        if query_name:
            names = [candidate["id"], candidate["name"], *candidate.get("aliases", [])]
            if not any(query_name in name.casefold() for name in names):
                continue
        evidence: list[dict[str, Any]] = []
        for evidence_id in assessment["evidence_ids"]:
            observation = observations[evidence_id]
            source = sources[observation["source_id"]]
            evidence.append(
                {
                    "observation_id": evidence_id,
                    "signal": observation["signal"],
                    "claim": observation["claim"],
                    "scope": observation["scope"],
                    "confidence": observation["confidence"],
                    "limitations": observation["limitations"],
                    "observed_at": observation["observed_at"],
                    "source": {
                        "id": source["id"],
                        "title": source["title"],
                        "publisher": source["publisher"],
                        "role": source["evidence_role"],
                        "candidate_independent": source["evidence_role"] == "independent-signal"
                        and candidate["id"] not in source.get("affiliated_technology_ids", []),
                        "url": source["url"],
                        "edition": source["edition"],
                        "published_at": source.get("published_at"),
                        "measurement_window": source.get("measurement_window"),
                        "retrieved_at": source["retrieved_at"],
                        "limitations": source["limitations"],
                    },
                }
            )
        row: dict[str, Any] = {
            "technology": candidate,
            "assessment": assessment,
            "evidence": evidence,
        }
        if as_of is not None:
            row["assessment_status"] = "expired" if as_of > _parse_date(assessment["expires_at"], "expires_at") else "current"
            stale_source_ids: list[str] = []
            for item in evidence:
                source = item["source"]
                source_record = sources[source["id"]]
                due_on = _parse_date(source["retrieved_at"], "retrieved_at") + timedelta(
                    days=int(source_record["freshness_days"])
                )
                source["retrieval_due_on"] = due_on.isoformat()
                source["retrieval_status"] = "stale" if as_of > due_on else "current"
                if as_of > due_on:
                    stale_source_ids.append(source["id"])
            row["evidence_status"] = {
                "stale_source_ids": sorted(set(stale_source_ids)),
                "retrieval_freshness_note": "Retrieval freshness is separate from publication currency and measurement age.",
            }
        if runtime_inventory is not None:
            row["runtime_capabilities"] = sorted(
                runtime_by_technology.get(candidate["id"], []),
                key=lambda item: (str(item.get("surface")), str(item.get("identifier"))),
            )
        rows.append(row)
    rows.sort(
        key=lambda row: (
            row["technology"]["family"],
            row["technology"]["name"].casefold(),
            row["technology"]["id"],
            row["assessment"]["id"],
        )
    )
    if limit is not None:
        if limit < 1:
            raise SnapshotError("limit must be a positive integer")
        rows = rows[:limit]
    return rows


def validate_data_directory(data_dir: Path | str) -> list[str]:
    """Validate the integrity envelope required before comparing a data directory."""
    directory = Path(data_dir)
    try:
        snapshot = load_snapshot(directory)
    except SnapshotError as exc:
        return [str(exc)]
    errors: list[str] = []
    for name, expected in EXPECTED_SCHEMA_VERSIONS.items():
        if snapshot[name].get("schema_version") != expected:
            errors.append(f"{name} schema_version must be {expected}")
    indexed = {
        name: _ids(snapshot[name].get(record_key), name, errors)
        for name, (_, record_key) in DATASET_FILES.items()
    }
    sources = indexed["sources"]
    technologies = indexed["technologies"]
    observations = indexed["observations"]
    assessments = indexed["assessments"]
    for technology_id, technology in technologies.items():
        official_ids = technology.get("official_source_ids")
        if not isinstance(official_ids, list):
            errors.append(f"technology {technology_id} official_source_ids must be an array")
        else:
            for source_id in official_ids:
                if source_id not in sources:
                    errors.append(f"technology {technology_id} references unknown source {source_id}")
    for source_id, source in sources.items():
        affiliations = source.get("affiliated_technology_ids", [])
        if not isinstance(affiliations, list):
            errors.append(f"source {source_id} affiliated_technology_ids must be an array")
        else:
            for technology_id in affiliations:
                if technology_id not in technologies:
                    errors.append(f"source {source_id} has unknown technology affiliation {technology_id}")
    observed_technologies: set[str] = set()
    for observation_id, observation in observations.items():
        technology_id = observation.get("technology_id")
        source_id = observation.get("source_id")
        if technology_id not in technologies:
            errors.append(f"observation {observation_id} references unknown technology {technology_id}")
        else:
            observed_technologies.add(technology_id)
        if source_id not in sources:
            errors.append(f"observation {observation_id} references unknown source {source_id}")
    assessed_technologies: set[str] = set()
    assessed_profiles: dict[tuple[str, tuple[tuple[str, ...], ...]], str] = {}
    for assessment_id, assessment in assessments.items():
        technology_id = assessment.get("technology_id")
        if technology_id not in technologies:
            errors.append(f"assessment {assessment_id} references unknown technology {technology_id}")
        else:
            assessed_technologies.add(technology_id)
        _record_unique_profile(
            assessment_id,
            technology_id,
            assessment.get("profile"),
            assessed_profiles,
            errors,
        )
        evidence_ids = assessment.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            errors.append(f"assessment {assessment_id} evidence_ids must be non-empty")
        else:
            for evidence_id in evidence_ids:
                observation = observations.get(evidence_id)
                if observation is None:
                    errors.append(f"assessment {assessment_id} references unknown observation {evidence_id}")
                elif observation.get("technology_id") != technology_id:
                    errors.append(f"assessment {assessment_id} uses evidence for another technology")
        alternatives = assessment.get("alternatives")
        if not isinstance(alternatives, list):
            errors.append(f"assessment {assessment_id} alternatives must be an array")
        else:
            for alternative in alternatives:
                if alternative not in technologies:
                    errors.append(f"assessment {assessment_id} references unknown alternative {alternative}")
    for technology_id in sorted(set(technologies) - observed_technologies):
        errors.append(f"technology {technology_id} has no observation")
    for technology_id in sorted(set(technologies) - assessed_technologies):
        errors.append(f"technology {technology_id} has no assessment")
    snapshot_ids = {
        snapshot[name].get("snapshot_id")
        for name in DATASET_FILES
    }
    if len(snapshot_ids) != 1 or None in snapshot_ids:
        errors.append("core dataset snapshot_id values must be identical and non-null")
    manifest = snapshot.get("manifest")
    if not isinstance(manifest, dict):
        return errors + ["missing snapshot-manifest.v1.json"]
    if manifest.get("schema_version") != "technology_intelligence.snapshot_manifest.v1":
        errors.append("snapshot manifest schema_version is invalid")
    if manifest.get("snapshot_id") not in snapshot_ids:
        errors.append("snapshot manifest snapshot_id does not match core datasets")
    manifest_generated_at: datetime | None = None
    try:
        manifest_generated_at = _parse_datetime(
            manifest.get("generated_at"), "snapshot manifest generated_at"
        ).astimezone(timezone.utc)
    except SnapshotError as exc:
        errors.append(str(exc))
    for name in DATASET_FILES:
        if "generated_at" not in snapshot[name]:
            continue
        try:
            generated_at = _parse_datetime(snapshot[name].get("generated_at"), f"{name} generated_at")
            if manifest_generated_at is not None and generated_at.astimezone(timezone.utc) != manifest_generated_at:
                errors.append(f"{name} generated_at does not match snapshot manifest")
        except SnapshotError as exc:
            errors.append(str(exc))
    entries = manifest.get("files")
    expected_paths = {filename for filename, _ in DATASET_FILES.values()} | set(SINGLETON_FILES.values())
    if not isinstance(entries, list):
        return errors + ["snapshot manifest files must be an array"]
    seen_paths: set[str] = set()
    for entry in entries:
        relative = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(relative, str) or relative in seen_paths:
            errors.append(f"snapshot manifest has invalid or duplicate path {relative!r}")
            continue
        seen_paths.add(relative)
        if relative not in expected_paths:
            errors.append(f"snapshot manifest includes unexpected file {relative}")
            continue
        path = directory / relative
        if not path.is_file():
            errors.append(f"snapshot manifest file missing: {relative}")
            continue
        if entry.get("sha256") != _sha256(path):
            errors.append(f"snapshot manifest hash mismatch: {relative}")
        document = _read_json(path)
        expected_count = 1
        for _, (candidate_file, record_key) in DATASET_FILES.items():
            if candidate_file == relative:
                records = document.get(record_key)
                if not isinstance(records, list):
                    errors.append(f"{relative} {record_key} must be an array")
                    records = []
                expected_count = len(records)
        if entry.get("record_count") != expected_count:
            errors.append(f"snapshot manifest count mismatch: {relative}")
        if entry.get("schema_version") != document.get("schema_version"):
            errors.append(f"snapshot manifest schema mismatch: {relative}")
    if seen_paths != expected_paths:
        errors.append(f"snapshot manifest paths mismatch; expected {sorted(expected_paths)}")
    return errors


def diff_directories(old_dir: Path | str, new_dir: Path | str) -> dict[str, Any]:
    """Produce a stable, semantic diff between two complete data directories."""
    old_errors = validate_data_directory(old_dir)
    new_errors = validate_data_directory(new_dir)
    if old_errors or new_errors:
        messages = [*(f"old:{error}" for error in old_errors), *(f"new:{error}" for error in new_errors)]
        raise SnapshotError("cannot diff invalid data directories: " + "; ".join(messages))
    old_snapshot = load_snapshot(Path(old_dir))
    new_snapshot = load_snapshot(Path(new_dir))
    datasets: dict[str, Any] = {}
    for name, (_, record_key) in DATASET_FILES.items():
        old_records = {record["id"]: record for record in old_snapshot[name].get(record_key, [])}
        new_records = {record["id"]: record for record in new_snapshot[name].get(record_key, [])}
        datasets[name] = {
            "added": sorted(set(new_records) - set(old_records)),
            "removed": sorted(set(old_records) - set(new_records)),
            "changed": sorted(
                record_id
                for record_id in set(old_records) & set(new_records)
                if old_records[record_id] != new_records[record_id]
            ),
        }
    for name in SINGLETON_FILES:
        datasets[name] = {
            "added": [],
            "removed": [],
            "changed": [name] if old_snapshot[name] != new_snapshot[name] else [],
        }
    metadata_changed: list[str] = []
    for name, (_, record_key) in DATASET_FILES.items():
        old_metadata = {key: value for key, value in old_snapshot[name].items() if key != record_key}
        new_metadata = {key: value for key, value in new_snapshot[name].items() if key != record_key}
        if old_metadata != new_metadata:
            metadata_changed.append(name)
    old_manifest_metadata = {
        key: value for key, value in old_snapshot["manifest"].items() if key != "files"
    }
    new_manifest_metadata = {
        key: value for key, value in new_snapshot["manifest"].items() if key != "files"
    }
    if old_manifest_metadata != new_manifest_metadata:
        metadata_changed.append("manifest")
    datasets["snapshot-metadata"] = {
        "added": [],
        "removed": [],
        "changed": sorted(metadata_changed),
    }
    change_count = sum(
        len(values[change_kind])
        for values in datasets.values()
        for change_kind in ("added", "removed", "changed")
    )
    return {"change_count": change_count, "datasets": datasets}


class _AllowlistedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = {host.casefold() for host in allowed_hosts}
        self.redirects: list[str] = []

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        parsed = urllib.parse.urlparse(newurl)
        host = parsed.hostname
        if parsed.scheme != "https" or not host or host.casefold() not in self.allowed_hosts:
            raise SnapshotError(f"redirect target host is not allowlisted: {host!r}")
        self.redirects.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def capture_source(
    source_id: str,
    output_dir: Path | str,
    *,
    acknowledge_network: bool,
    timeout: float = 20.0,
    opener: Any | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Capture one allowlisted source outside tracked plugin state and emit a receipt."""
    if not acknowledge_network:
        raise SnapshotError("refresh requires --acknowledge-network")
    validation_errors = validate_plugin(PLUGIN_ROOT)
    if validation_errors:
        raise SnapshotError("snapshot validation failed before refresh: " + "; ".join(validation_errors))
    registry_path = DATA_DIR / DATASET_FILES["sources"][0]
    try:
        registry_bytes = registry_path.read_bytes()
        source_document = json.loads(registry_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"cannot bind source registry before refresh: {exc}") from exc
    registry_digest = hashlib.sha256(registry_bytes).hexdigest()
    registry_generated_at = _parse_datetime(
        source_document.get("generated_at"), "source registry generated_at"
    ).astimezone(timezone.utc)
    if now is not None:
        if now.tzinfo is None:
            raise SnapshotError("capture time must include a timezone")
        captured_at = now.astimezone(timezone.utc)
        if captured_at < registry_generated_at:
            raise SnapshotError("capture time precedes source registry generation")
    validation_errors = validate_plugin(PLUGIN_ROOT)
    if validation_errors or _sha256(registry_path) != registry_digest:
        details = "; ".join(validation_errors) if validation_errors else "source registry changed during validation"
        raise SnapshotError("snapshot changed before refresh: " + details)
    sources = {item["id"]: item for item in source_document["sources"]}
    if source_id not in sources:
        raise SnapshotError(f"unknown source id: {source_id}")
    source = sources[source_id]
    refresh = source["refresh"]
    if not refresh.get("enabled"):
        raise SnapshotError(f"refresh is disabled for source: {source_id}")
    parsed = urllib.parse.urlparse(source["url"])
    allowed_hosts = {str(host).casefold() for host in refresh["allowed_hosts"]}
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.casefold() not in allowed_hosts:
        raise SnapshotError("source URL must be HTTPS and use an allowlisted host")
    destination_root = Path(output_dir).expanduser().resolve()
    if _is_within(destination_root, PLUGIN_ROOT.resolve()):
        raise SnapshotError("refresh output must be outside the plugin source tree")
    if timeout <= 0 or timeout > 120:
        raise SnapshotError("timeout must be greater than zero and no more than 120 seconds")
    redirect_handler: _AllowlistedRedirectHandler | None = None
    if opener is None:
        redirect_handler = _AllowlistedRedirectHandler(allowed_hosts)
        opener = urllib.request.build_opener(redirect_handler)
    request = urllib.request.Request(
        source["url"],
        headers={
            "User-Agent": "technology-intelligence-refresh/0.1 (+https://github.com/Xopoko/plug-n-skills)",
            "Accept": "text/html,application/json,application/pdf,text/plain;q=0.9,*/*;q=0.1",
        },
        method="GET",
    )
    with opener.open(request, timeout=timeout) as response:
        final_url = response.geturl()
        final_parsed = urllib.parse.urlparse(final_url)
        final_host = final_parsed.hostname
        if (
            final_parsed.scheme != "https"
            or not final_host
            or final_host.casefold() not in allowed_hosts
        ):
            raise SnapshotError(f"final response host is not allowlisted: {final_host!r}")
        max_bytes = int(refresh["max_bytes"])
        status = getattr(response, "status", None)
        if not isinstance(status, int) or not 200 <= status < 300:
            raise SnapshotError(f"source returned non-success HTTP status: {status!r}")
        headers = getattr(response, "headers", {})
        content_length = headers.get("Content-Length") if hasattr(headers, "get") else None
        if content_length is not None:
            try:
                if int(content_length) > max_bytes:
                    raise SnapshotError(f"source Content-Length exceeds max_bytes={max_bytes}")
            except ValueError as exc:
                raise SnapshotError(f"source returned invalid Content-Length: {content_length!r}") from exc
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise SnapshotError(f"source response exceeds max_bytes={max_bytes}")
        content_type = headers.get("Content-Type") if hasattr(headers, "get") else None
        etag = headers.get("ETag") if hasattr(headers, "get") else None
        last_modified = headers.get("Last-Modified") if hasattr(headers, "get") else None
    captured_at = captured_at if now is not None else datetime.now(timezone.utc)
    if captured_at < registry_generated_at:
        raise SnapshotError("capture time precedes source registry generation")
    if _sha256(registry_path) != registry_digest:
        raise SnapshotError("source registry changed during capture; no artifact was written")
    timestamp = captured_at.strftime("%Y%m%dT%H%M%S.%fZ")
    capture_dir = destination_root / source_id / timestamp
    if capture_dir.exists():
        raise SnapshotError(f"capture directory already exists: {capture_dir}")
    capture_dir.mkdir(parents=True)
    raw_path = capture_dir / "raw.bin"
    receipt_path = capture_dir / "receipt.json"
    digest = hashlib.sha256(raw).hexdigest()
    receipt = {
        "schema_version": "technology_intelligence.refresh_receipt.v1",
        "snapshot_id": source_document["snapshot_id"],
        "source_registry_sha256": registry_digest,
        "source_id": source_id,
        "source_edition": source["edition"],
        "source_rights": dict(source["rights"]),
        "requested_url": source["url"],
        "final_url": final_url,
        "retrieved_at": captured_at.isoformat().replace("+00:00", "Z"),
        "http_status": status,
        "content_type": content_type,
        "etag": etag,
        "last_modified": last_modified,
        "sha256": digest,
        "bytes": len(raw),
        "redirects": redirect_handler.redirects if redirect_handler else [],
        "raw_artifact": "raw.bin",
        "adapter": {"name": "generic-http-get", "version": "1"},
        "cache_status": "not-used",
        "masked_fields": [],
        "network_explicit": True,
        "normalization_performed": False,
        "recommendations_changed": False,
    }
    _atomic_write(raw_path, raw)
    _atomic_write(receipt_path, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return {"capture_dir": str(capture_dir), "receipt_path": str(receipt_path), "receipt": receipt}


def _render_query_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No candidates matched the supplied profile filters."
    sections: list[str] = []
    for row in rows:
        technology = row["technology"]
        assessment = row["assessment"]
        lines = [
            f"## {technology['name']} - {assessment['disposition']}",
            "",
            technology["summary"],
            "",
            "Profile stages: " + "; ".join(assessment["profile"]["stages"]),
            "",
            "Profile use cases: " + "; ".join(assessment["profile"]["use_cases"]),
            "",
            "Profile constraints: " + "; ".join(assessment["profile"]["constraints"]),
            "",
            f"Assessment confidence: {assessment['confidence']}",
            "",
            "Rationale:",
            "",
        ]
        lines.extend(f"- {reason}" for reason in assessment["rationale"])
        lines.extend([
            "",
            "Hard gates:",
            "",
        ])
        lines.extend(f"- {gate}" for gate in assessment["hard_gates"])
        alternatives = ", ".join(assessment["alternatives"]) if assessment["alternatives"] else "None recorded"
        lines.extend([
            "",
            f"Alternatives: {alternatives}",
            "",
            f"Verification gap: {assessment['verification_gap']}",
            "",
            "Evidence:",
            "",
        ])
        for evidence in row["evidence"]:
            source = evidence["source"]
            publication = source["published_at"] or "undated/live"
            measurement = source.get("measurement_window")
            measurement_text = (
                f", measured {measurement['start']} through {measurement['end']}" if measurement else ""
            )
            lines.append(
                f"- {evidence['claim']} [{source['publisher']}: {source['title']}]({source['url']}) "
                f"({source['role']}, published {publication}{measurement_text}, retrieved {source['retrieved_at']}, "
                f"observed {evidence['observed_at']}, confidence {evidence['confidence']}). "
                f"Observation limitation: {evidence['limitations']} Source limitation: {source['limitations']}"
            )
        if "assessment_status" in row:
            lines.extend(["", f"Assessment status: {row['assessment_status']} (expires {assessment['expires_at']})."])
            stale_ids = row["evidence_status"]["stale_source_ids"]
            lines.append("Cited-source retrieval status: " + (f"stale: {', '.join(stale_ids)}" if stale_ids else "current"))
            lines.append(row["evidence_status"]["retrieval_freshness_note"])
        if "runtime_capabilities" in row:
            lines.extend(["", "Caller-supplied runtime facts:", ""])
            if row["runtime_capabilities"]:
                for capability in row["runtime_capabilities"]:
                    lines.append(
                        f"- {capability['surface']} `{capability['identifier']}`: installed={capability['installed']}, "
                        f"enabled={capability['enabled']}, auth={capability['auth_state']}, health={capability['health']}."
                    )
            else:
                lines.append("- No matching capability was present in the supplied inventory.")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _print_staleness_text(report: dict[str, Any]) -> None:
    print(f"As of {report['as_of']}: {len(report['stale_sources'])} stale sources, "
          f"{len(report['expired_assessments'])} expired assessments")
    for source in report["stale_sources"]:
        print(f"SOURCE {source['id']} due {source['due_on']} ({source['days_overdue']} days overdue)")
    for assessment in report["expired_assessments"]:
        print(f"ASSESSMENT {assessment['id']} expired {assessment['expires_at']} "
              f"({assessment['days_overdue']} days overdue)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate the plugin and snapshot without network access")
    validate_parser.add_argument("--json", action="store_true", help="emit machine-readable output")

    query_parser = subparsers.add_parser("query", help="query context-specific assessments without network access")
    query_parser.add_argument("--family", choices=sorted(EXPECTED_FAMILIES))
    query_parser.add_argument("--stage")
    query_parser.add_argument("--use-case")
    query_parser.add_argument("--disposition", choices=sorted(ALLOWED_DISPOSITIONS))
    query_parser.add_argument("--technology")
    query_parser.add_argument("--limit", type=int)
    query_parser.add_argument("--as-of", type=date.fromisoformat)
    query_parser.add_argument("--runtime-inventory", type=Path)
    query_parser.add_argument("--format", choices=("json", "markdown"), default="markdown")

    stale_parser = subparsers.add_parser("stale", help="report source and assessment expiry without network access")
    stale_parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    stale_parser.add_argument("--json", action="store_true")

    window_parser = subparsers.add_parser(
        "evidence-window",
        help="report publication-window coverage separately from retrieval freshness",
    )
    window_parser.add_argument("--since", type=date.fromisoformat, required=True)
    window_parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    window_parser.add_argument("--json", action="store_true")

    diff_parser = subparsers.add_parser("diff", help="compare two complete data directories without network access")
    diff_parser.add_argument("--old-dir", type=Path, required=True)
    diff_parser.add_argument("--new-dir", type=Path, required=True)
    diff_parser.add_argument("--json", action="store_true")

    trigger_parser = subparsers.add_parser("check-triggers", help="run the synthetic trigger contract")
    trigger_parser.add_argument("--json", action="store_true")

    refresh_parser = subparsers.add_parser("refresh", help="explicitly capture one allowlisted source outside the plugin")
    refresh_parser.add_argument("--source-id", required=True)
    refresh_parser.add_argument("--acknowledge-network", action="store_true")
    refresh_parser.add_argument("--output-dir", type=Path, required=True)
    refresh_parser.add_argument("--timeout", type=float, default=20.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            errors = validate_plugin()
            payload = {"valid": not errors, "errors": errors}
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            elif errors:
                print("FAIL")
                for error in errors:
                    print(f"- {error}")
            else:
                snapshot = load_snapshot()
                print(
                    "PASS: "
                    f"{len(snapshot['technologies']['technologies'])} technologies, "
                    f"{len(snapshot['observations']['observations'])} observations, "
                    f"{len(snapshot['assessments']['assessments'])} assessments"
                )
            return 0 if not errors else 1
        if args.command == "query":
            errors = validate_plugin()
            if errors:
                raise SnapshotError("snapshot validation failed: " + "; ".join(errors))
            snapshot = load_snapshot()
            runtime_inventory = _read_json(args.runtime_inventory) if args.runtime_inventory else None
            rows = query_snapshot(
                snapshot,
                family=args.family,
                stage=args.stage,
                use_case=args.use_case,
                disposition=args.disposition,
                technology=args.technology,
                limit=args.limit,
                as_of=args.as_of,
                runtime_inventory=runtime_inventory,
            )
            print(json.dumps(rows, indent=2, sort_keys=True) if args.format == "json" else _render_query_markdown(rows))
            return 0
        if args.command == "stale":
            errors = validate_plugin()
            if errors:
                raise SnapshotError("snapshot validation failed: " + "; ".join(errors))
            report = staleness_report(load_snapshot(), args.as_of)
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                _print_staleness_text(report)
            return 0
        if args.command == "evidence-window":
            errors = validate_plugin()
            if errors:
                raise SnapshotError("snapshot validation failed: " + "; ".join(errors))
            report = evidence_window_report(load_snapshot(), args.since, args.as_of)
            if args.json:
                print(json.dumps(report, indent=2, sort_keys=True))
            else:
                counts = report["source_counts"]
                print(
                    f"{report['since']}..{report['as_of']}: "
                    f"{counts['published_in_window']} published sources; "
                    f"{report['covered_technology_count']} covered technologies; "
                    f"{report['technology_gap_count']} gaps"
                )
                for item in report["technology_coverage"]:
                    observations = ", ".join(item["fresh_observation_ids"]) or "-"
                    print(f"{item['status'].upper()} {item['technology_id']}: {observations}")
            return 0
        if args.command == "diff":
            result = diff_directories(args.old_dir, args.new_dir)
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(f"Changes: {result['change_count']}")
                for name, values in result["datasets"].items():
                    for kind in ("added", "removed", "changed"):
                        for record_id in values[kind]:
                            print(f"{name} {kind[:-1].upper()} {record_id}")
            return 0
        if args.command == "check-triggers":
            contract = load_snapshot()["trigger-contract"]
            cases = _read_json(TRIGGER_CASES)["cases"]
            failures = [
                {"id": case["id"], "expected": case["expected_skill"], "actual": classify_prompt(case["prompt"], contract)}
                for case in cases
                if classify_prompt(case["prompt"], contract) != case["expected_skill"]
            ]
            payload = {"valid": not failures, "case_count": len(cases), "failures": failures}
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True))
            elif failures:
                print(f"FAIL: {len(failures)} of {len(cases)} trigger cases")
                for failure in failures:
                    print(f"- {failure['id']}: expected {failure['expected']!r}, got {failure['actual']!r}")
            else:
                print(f"PASS: {len(cases)} trigger cases")
            return 0 if not failures else 1
        if args.command == "refresh":
            result = capture_source(
                args.source_id,
                args.output_dir,
                acknowledge_network=args.acknowledge_network,
                timeout=args.timeout,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
    except (SnapshotError, OSError, urllib.error.URLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
