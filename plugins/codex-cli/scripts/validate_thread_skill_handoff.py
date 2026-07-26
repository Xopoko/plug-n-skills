#!/usr/bin/env python3
"""Validate version-bound Codex thread skill handoffs and acknowledgements."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
RELATIONS = {"exact", "older", "newer", "absent", "unknown"}
OBSERVED_RELATIONS = {"exact", "older", "newer", "mismatch", "unknown"}
CONSUMPTION_MODES = {"runtime-loaded", "direct-source-read", "unavailable"}
REQUESTED_CONSUMPTION_MODES = {"runtime-loaded", "direct-source-read"}
RUNTIME_DISCOVERY_STATES = {"active", "inactive", "unknown"}
APPLIED_REASONS = {"exact-runtime-loaded", "exact-direct-source-read"}
STALE_REASONS = {"newer-source-supersedes"}
CONFLICT_REASONS = {
    "ambiguous-evidence",
    "id-conflict",
    "reservation-unavailable",
    "runtime-mismatch",
    "source-mismatch",
    "source-unavailable",
    "unauthorized-install-attempt",
}


class ContractValidationError(ValueError):
    """Raised when a handoff or acknowledgement violates the closed contract."""


def _fail(message: str) -> None:
    raise ContractValidationError(message)


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    return value


def _require_exact_keys(
    value: dict[str, Any], expected: set[str], label: str
) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            f"{label} keys differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a non-empty string")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        _fail(f"{label} must be a boolean")
    return value


def _require_digest(value: Any, label: str) -> str:
    digest = _require_string(value, label)
    if DIGEST_RE.fullmatch(digest) is None:
        _fail(f"{label} must be sha256 followed by 64 lowercase hex characters")
    return digest


def _require_portable_path(value: Any, label: str) -> str:
    path = _require_string(value, label)
    if "\\" in path or path.startswith("/") or path.endswith("/"):
        _fail(f"{label} must be a portable repository-relative POSIX path")
    parts = PurePosixPath(path).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        _fail(f"{label} must not contain empty, dot, or parent components")
    if PurePosixPath(*parts).as_posix() != path:
        _fail(f"{label} must be normalized")
    return path


def _parse_semver(value: Any, label: str) -> tuple[str, str, str, tuple[str, ...]]:
    version = _require_string(value, label)
    match = SEMVER_RE.fullmatch(version)
    if match is None:
        _fail(f"{label} must be a semantic version")
    prerelease_text = match.group(4)
    prerelease = tuple(prerelease_text.split(".")) if prerelease_text else ()
    for identifier in prerelease:
        if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
            _fail(f"{label} has a numeric prerelease identifier with a leading zero")
    return match.group(1), match.group(2), match.group(3), prerelease


def _compare_numeric_text(left: str, right: str) -> int:
    if len(left) != len(right):
        return -1 if len(left) < len(right) else 1
    if left == right:
        return 0
    return -1 if left < right else 1


def _compare_semver(left: Any, right: Any, label: str) -> int:
    left_major, left_minor, left_patch, left_pre = _parse_semver(
        left, f"{label}.left"
    )
    right_major, right_minor, right_patch, right_pre = _parse_semver(
        right, f"{label}.right"
    )
    for left_identifier, right_identifier in zip(
        (left_major, left_minor, left_patch),
        (right_major, right_minor, right_patch),
    ):
        comparison = _compare_numeric_text(left_identifier, right_identifier)
        if comparison:
            return comparison
    if not left_pre and not right_pre:
        return 0
    if not left_pre:
        return 1
    if not right_pre:
        return -1
    for left_identifier, right_identifier in zip(left_pre, right_pre):
        if left_identifier == right_identifier:
            continue
        left_numeric = left_identifier.isdigit()
        right_numeric = right_identifier.isdigit()
        if left_numeric and right_numeric:
            return _compare_numeric_text(left_identifier, right_identifier)
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return -1 if left_identifier < right_identifier else 1
    if len(left_pre) == len(right_pre):
        return 0
    return -1 if len(left_pre) < len(right_pre) else 1


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def content_manifest_digest(manifest: dict[str, Any]) -> str:
    """Return the v1 canonical content-manifest digest after validating shape."""

    manifest = _require_object(manifest, "content_manifest")
    _require_exact_keys(
        manifest, {"schema", "entries"}, "content_manifest"
    )
    if manifest["schema"] != "codex.skill_content_manifest.v1":
        _fail("content_manifest.schema must be codex.skill_content_manifest.v1")
    entries = manifest["entries"]
    if not isinstance(entries, list) or not entries:
        _fail("content_manifest.entries must be a non-empty array")

    paths: list[str] = []
    normalized_entries: list[dict[str, Any]] = []
    for index, raw_entry in enumerate(entries):
        entry = _require_object(raw_entry, f"content_manifest.entries[{index}]")
        _require_exact_keys(
            entry,
            {"path", "sha256", "size"},
            f"content_manifest.entries[{index}]",
        )
        path = _require_portable_path(
            entry["path"], f"content_manifest.entries[{index}].path"
        )
        digest = _require_digest(
            entry["sha256"], f"content_manifest.entries[{index}].sha256"
        )
        size = entry["size"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            _fail(
                f"content_manifest.entries[{index}].size "
                "must be a non-negative integer"
            )
        paths.append(path)
        normalized_entries.append(
            {"path": path, "sha256": digest, "size": size}
        )

    if paths != sorted(set(paths)):
        _fail("content manifest paths must be strictly sorted and unique")

    canonical = {
        "schema": "codex.skill_content_manifest.v1",
        "entries": normalized_entries,
    }
    return _sha256(
        b"codex.skill_content_manifest.v1\n" + _canonical_json(canonical)
    )


def payload_fingerprint(handoff: dict[str, Any]) -> str:
    """Return the v2 payload fingerprint, excluding the fingerprint field."""

    payload = copy.deepcopy(_require_object(handoff, "handoff"))
    payload.pop("payload_fingerprint", None)
    return _sha256(
        b"codex.thread_skill_handoff.v2\n" + _canonical_json(payload)
    )


def _source_identity(skill: dict[str, Any]) -> dict[str, str]:
    return {
        "name": skill["name"],
        "source_repository": skill["source_repository"],
        "source_version": skill["source_version"],
        "source_revision": skill["source_revision"],
        "source_path": skill["source_path"],
        "content_digest": skill["content_digest"],
    }


def _validate_skill(skill: Any) -> dict[str, Any]:
    skill = _require_object(skill, "skill")
    _require_exact_keys(
        skill,
        {
            "name",
            "source_repository",
            "source_version",
            "source_revision",
            "source_path",
            "content_manifest",
            "content_digest",
            "verification_state",
        },
        "skill",
    )
    _require_string(skill["name"], "skill.name")
    _require_string(skill["source_repository"], "skill.source_repository")
    _parse_semver(skill["source_version"], "skill.source_version")
    _require_string(skill["source_revision"], "skill.source_revision")
    source_path = _require_portable_path(skill["source_path"], "skill.source_path")
    if skill["verification_state"] != "verified":
        _fail("skill.verification_state must be verified")
    expected_digest = content_manifest_digest(skill["content_manifest"])
    actual_digest = _require_digest(skill["content_digest"], "skill.content_digest")
    if actual_digest != expected_digest:
        _fail("skill.content_digest does not match the canonical content manifest")
    entry_paths = {
        entry["path"] for entry in skill["content_manifest"]["entries"]
    }
    if source_path not in entry_paths:
        _fail("skill.source_path must appear in the content manifest")
    return skill


def _validate_surface(
    surface: Any, source: dict[str, Any], label: str
) -> dict[str, Any]:
    surface = _require_object(surface, label)
    _require_exact_keys(
        surface,
        {
            "version",
            "source_repository",
            "source_revision",
            "content_digest",
            "relation_to_source",
        },
        label,
    )
    for field in (
        "version",
        "source_repository",
        "source_revision",
        "content_digest",
        "relation_to_source",
    ):
        _require_string(surface[field], f"{label}.{field}")

    relation = surface["relation_to_source"]
    if relation not in RELATIONS:
        _fail(f"{label}.relation_to_source is not a closed state")
    identity_fields = {
        "version": source["source_version"],
        "source_repository": source["source_repository"],
        "source_revision": source["source_revision"],
        "content_digest": source["content_digest"],
    }
    if relation == "exact":
        for field, expected in identity_fields.items():
            if surface[field] != expected:
                _fail(f"{label} exact identity does not match source {field}")
    elif relation == "absent":
        if any(surface[field] != "absent" for field in identity_fields):
            _fail(f"{label} absent identity must use absent for every field")
    elif relation == "unknown":
        if "unknown" not in {surface[field] for field in identity_fields}:
            _fail(f"{label} unknown identity must contain an unknown field")
    else:
        if surface["source_repository"] != source["source_repository"]:
            _fail(f"{label} comparable identity must use the source repository")
        for field in ("version", "source_revision"):
            if surface[field] in {"absent", "unknown"}:
                _fail(f"{label}.{field} must be concrete for {relation}")
        comparison = _compare_semver(
            surface["version"],
            source["source_version"],
            f"{label}.version_order",
        )
        if relation == "older" and comparison >= 0:
            _fail(f"{label} older identity must have an older semantic version")
        if relation == "newer" and comparison <= 0:
            _fail(f"{label} newer identity must have a newer semantic version")
        _require_digest(surface["content_digest"], f"{label}.content_digest")
        if (
            surface["source_revision"] == source["source_revision"]
            and surface["content_digest"] == source["content_digest"]
        ):
            _fail(f"{label} {relation} identity cannot equal the exact source")
    return surface


def _validate_receiver_state(
    state: Any, source: dict[str, Any], label: str
) -> dict[str, Any]:
    state = _require_object(state, label)
    _require_exact_keys(state, {"catalog", "cache", "runtime"}, label)
    _validate_surface(state["catalog"], source, f"{label}.catalog")
    _validate_surface(state["cache"], source, f"{label}.cache")

    runtime = _require_object(state["runtime"], f"{label}.runtime")
    _require_exact_keys(runtime, {"discovery", "loaded"}, f"{label}.runtime")
    discovery = _require_string(
        runtime["discovery"], f"{label}.runtime.discovery"
    )
    if discovery not in RUNTIME_DISCOVERY_STATES:
        _fail(f"{label}.runtime.discovery is not a closed state")
    loaded = _validate_surface(
        runtime["loaded"], source, f"{label}.runtime.loaded"
    )
    if discovery == "inactive" and loaded["relation_to_source"] not in {
        "absent",
        "unknown",
    }:
        _fail(f"{label} inactive runtime cannot name loaded skill bytes")
    if discovery == "active" and loaded["relation_to_source"] == "absent":
        _fail(f"{label} active runtime cannot have an absent loaded identity")
    return state


def validate_handoff(handoff: dict[str, Any]) -> None:
    """Validate a sender handoff envelope or raise ContractValidationError."""

    handoff = _require_object(handoff, "handoff")
    _require_exact_keys(
        handoff,
        {
            "schema",
            "handoff_id",
            "payload_fingerprint",
            "skill",
            "why_now",
            "mechanism",
            "receiver_basis",
            "requested_consumption",
            "activation_authorized",
            "scope_effect",
            "authority_effect",
            "ack_required",
        },
        "handoff",
    )
    if handoff["schema"] != "codex.thread_skill_handoff.v2":
        _fail("handoff.schema must be codex.thread_skill_handoff.v2")
    _require_string(handoff["handoff_id"], "handoff.handoff_id")
    _require_string(handoff["why_now"], "handoff.why_now")
    _require_string(handoff["mechanism"], "handoff.mechanism")
    source = _validate_skill(handoff["skill"])
    receiver_basis = _validate_receiver_state(
        handoff["receiver_basis"], source, "handoff.receiver_basis"
    )
    requested = _require_string(
        handoff["requested_consumption"], "handoff.requested_consumption"
    )
    if requested not in REQUESTED_CONSUMPTION_MODES:
        _fail("handoff.requested_consumption is not a closed state")
    if _require_bool(
        handoff["activation_authorized"], "handoff.activation_authorized"
    ):
        _fail("handoff.activation_authorized must remain false")
    if handoff["scope_effect"] != "none":
        _fail("handoff.scope_effect must be none")
    if handoff["authority_effect"] != "none":
        _fail("handoff.authority_effect must be none")
    if _require_bool(handoff["ack_required"], "handoff.ack_required") is not True:
        _fail("handoff.ack_required must be true")

    if requested == "runtime-loaded":
        if receiver_basis["cache"]["relation_to_source"] != "exact":
            _fail("runtime-loaded requires an exact receiver cache basis")
        if receiver_basis["runtime"]["discovery"] != "active":
            _fail("runtime-loaded requires active runtime discovery in the basis")
        if (
            receiver_basis["runtime"]["loaded"]["relation_to_source"]
            != "exact"
        ):
            _fail("runtime-loaded requires the exact runtime loaded identity")

    supplied_fingerprint = _require_digest(
        handoff["payload_fingerprint"], "handoff.payload_fingerprint"
    )
    expected_fingerprint = payload_fingerprint(handoff)
    if supplied_fingerprint != expected_fingerprint:
        _fail("handoff.payload_fingerprint does not match canonical payload")


def _validate_observed_source(
    observed: Any, source: dict[str, Any]
) -> dict[str, Any]:
    observed = _require_object(observed, "ack.observed_source")
    _require_exact_keys(
        observed,
        {
            "name",
            "source_repository",
            "source_version",
            "source_revision",
            "source_path",
            "content_digest",
            "verification_state",
            "relation_to_source",
        },
        "ack.observed_source",
    )
    for field in (
        "name",
        "source_repository",
        "source_version",
        "source_revision",
        "verification_state",
        "relation_to_source",
    ):
        _require_string(observed[field], f"ack.observed_source.{field}")
    _require_portable_path(
        observed["source_path"], "ack.observed_source.source_path"
    )
    _require_digest(
        observed["content_digest"], "ack.observed_source.content_digest"
    )
    if observed["verification_state"] not in {"verified", "unverified"}:
        _fail("ack.observed_source.verification_state is not a closed state")
    relation = observed["relation_to_source"]
    if relation not in OBSERVED_RELATIONS:
        _fail("ack.observed_source.relation_to_source is not a closed state")

    expected = _source_identity(source)
    if relation == "exact":
        if observed["verification_state"] != "verified":
            _fail("an exact observed source must be verified")
        for field, value in expected.items():
            if observed[field] != value:
                _fail(f"observed source exact identity differs at {field}")
    elif relation == "newer":
        if observed["verification_state"] != "verified":
            _fail("a newer observed source must be verified")
        for field in ("name", "source_repository", "source_path"):
            if observed[field] != expected[field]:
                _fail(f"a newer observed source differs at stable field {field}")
        if (
            _compare_semver(
                observed["source_version"],
                expected["source_version"],
                "ack.observed_source.version_order",
            )
            <= 0
        ):
            _fail("a newer observed source must have a newer semantic version")
        if (
            observed["source_revision"] == expected["source_revision"]
            or observed["content_digest"] == expected["content_digest"]
        ):
            _fail("a newer observed source must name different verified content")
    elif relation == "mismatch":
        if all(observed[field] == value for field, value in expected.items()):
            _fail("observed source mismatch label requires a different identity")
    return observed


def _validate_evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        _fail("ack.evidence_refs must be a non-empty array")
    for index, item in enumerate(value):
        _require_string(item, f"ack.evidence_refs[{index}]")
    return value


def validate_acknowledgement(
    handoff: dict[str, Any], acknowledgement: dict[str, Any]
) -> None:
    """Validate one acknowledgement against an already validated handoff."""

    validate_handoff(handoff)
    acknowledgement = _require_object(acknowledgement, "ack")
    _require_exact_keys(
        acknowledgement,
        {
            "schema",
            "handoff_id",
            "payload_fingerprint",
            "expected_source_content_digest",
            "observed_source",
            "receiver_record_fingerprint",
            "status",
            "reason",
            "supersession_evidence_ref",
            "observed_receiver",
            "consumption_mode",
            "runtime_used",
            "install_attempted",
            "evidence_refs",
        },
        "ack",
    )
    if acknowledgement["schema"] != "codex.thread_skill_handoff_ack.v1":
        _fail("ack.schema must be codex.thread_skill_handoff_ack.v1")
    if acknowledgement["handoff_id"] != handoff["handoff_id"]:
        _fail("ack.handoff_id must match the handoff")
    if acknowledgement["payload_fingerprint"] != handoff["payload_fingerprint"]:
        _fail("ack.payload_fingerprint must match the handoff")
    source = handoff["skill"]
    if (
        acknowledgement["expected_source_content_digest"]
        != source["content_digest"]
    ):
        _fail("ack expected source digest must match the handoff")

    observed_source = acknowledgement["observed_source"]
    if observed_source is not None:
        observed_source = _validate_observed_source(observed_source, source)
    record_fingerprint = acknowledgement["receiver_record_fingerprint"]
    if record_fingerprint not in {"none", "unknown"}:
        _require_digest(
            record_fingerprint, "ack.receiver_record_fingerprint"
        )
    status = _require_string(acknowledgement["status"], "ack.status")
    if status not in {"applied", "conflict", "stale"}:
        _fail("ack.status is not a closed state")
    reason = _require_string(acknowledgement["reason"], "ack.reason")
    supersession_evidence_ref = acknowledgement[
        "supersession_evidence_ref"
    ]
    if supersession_evidence_ref is not None:
        _require_string(
            supersession_evidence_ref, "ack.supersession_evidence_ref"
        )
    receiver = _validate_receiver_state(
        acknowledgement["observed_receiver"], source, "ack.observed_receiver"
    )
    mode = _require_string(
        acknowledgement["consumption_mode"], "ack.consumption_mode"
    )
    if mode not in CONSUMPTION_MODES:
        _fail("ack.consumption_mode is not a closed state")
    runtime_used = _require_bool(
        acknowledgement["runtime_used"], "ack.runtime_used"
    )
    install_attempted = _require_bool(
        acknowledgement["install_attempted"], "ack.install_attempted"
    )
    _validate_evidence_refs(acknowledgement["evidence_refs"])
    requested = handoff["requested_consumption"]

    if status == "applied":
        if reason not in APPLIED_REASONS:
            _fail("applied acknowledgement has an invalid reason")
        if mode != requested:
            _fail("applied acknowledgement must match requested consumption")
        if install_attempted:
            _fail("applied acknowledgement requires install_attempted=false")
        if supersession_evidence_ref is not None:
            _fail("applied acknowledgement cannot claim supersession evidence")
        if record_fingerprint != handoff["payload_fingerprint"]:
            _fail("applied acknowledgement requires the reserved fingerprint")
        if observed_source is None or observed_source["relation_to_source"] != "exact":
            _fail("applied acknowledgement requires the exact observed source")
        expected_reason = (
            "exact-runtime-loaded"
            if mode == "runtime-loaded"
            else "exact-direct-source-read"
        )
        if reason != expected_reason:
            _fail("applied reason does not match consumption mode")
        if mode == "runtime-loaded":
            if not runtime_used:
                _fail("runtime-loaded applied acknowledgement requires runtime_used")
            if receiver["cache"]["relation_to_source"] != "exact":
                _fail("runtime-loaded acknowledgement requires exact cache")
            if receiver["runtime"]["discovery"] != "active":
                _fail("runtime-loaded acknowledgement requires active discovery")
            if (
                receiver["runtime"]["loaded"]["relation_to_source"]
                != "exact"
            ):
                _fail(
                    "runtime loaded identity must match the exact handed-off source"
                )
        elif runtime_used:
            _fail("direct-source-read cannot claim runtime_used")
        return

    if status == "stale":
        if reason not in STALE_REASONS:
            _fail("stale acknowledgement has an invalid reason")
        if mode != requested:
            _fail("stale acknowledgement must name requested consumption")
        if runtime_used or install_attempted:
            _fail("stale acknowledgement applies nothing and attempts no install")
        if supersession_evidence_ref is None:
            _fail("stale acknowledgement requires supersession evidence")
        if record_fingerprint != handoff["payload_fingerprint"]:
            _fail("stale acknowledgement requires the reserved fingerprint")
        if (
            observed_source is None
            or observed_source["relation_to_source"] != "newer"
            or observed_source["verification_state"] != "verified"
        ):
            _fail("stale acknowledgement requires a newer observed source")
        return

    if reason not in CONFLICT_REASONS:
        _fail("conflict acknowledgement has an invalid reason")
    if supersession_evidence_ref is not None:
        _fail("conflict acknowledgement cannot claim supersession evidence")
    if runtime_used:
        _fail("conflict acknowledgement cannot claim runtime_used")
    if mode != "unavailable":
        _fail("conflict acknowledgement must use unavailable consumption")
    if reason == "unauthorized-install-attempt":
        if not install_attempted:
            _fail("unauthorized-install-attempt requires install_attempted=true")
    elif install_attempted:
        _fail("install_attempted=true requires unauthorized-install-attempt")

    if reason == "id-conflict":
        if (
            record_fingerprint in {
                "none",
                "unknown",
                handoff["payload_fingerprint"],
            }
        ):
            _fail("id-conflict requires a different stored fingerprint")
        if observed_source is not None:
            _fail("id-conflict cannot read source before rejecting the ID")
    elif reason == "reservation-unavailable":
        if record_fingerprint != "none":
            _fail("reservation-unavailable requires no receiver record")
        if observed_source is not None:
            _fail("reservation-unavailable cannot read source before reservation")
    elif record_fingerprint != handoff["payload_fingerprint"]:
        _fail("conflict requires the matching reserved fingerprint")

    if reason == "source-mismatch":
        if (
            observed_source is None
            or observed_source["relation_to_source"] != "mismatch"
        ):
            _fail("source-mismatch requires a mismatching observed source")
    if reason == "source-unavailable" and observed_source is not None:
        _fail("source-unavailable cannot include an observed source")
    if reason == "runtime-mismatch":
        if requested != "runtime-loaded":
            _fail("runtime-mismatch requires a runtime-loaded request")
        runtime_has_unknown = (
            receiver["cache"]["relation_to_source"] == "unknown"
            or receiver["runtime"]["discovery"] == "unknown"
            or receiver["runtime"]["loaded"]["relation_to_source"] == "unknown"
        )
        if runtime_has_unknown:
            _fail("runtime-mismatch cannot use unknown runtime state")
        runtime_is_exact = (
            receiver["cache"]["relation_to_source"] == "exact"
            and receiver["runtime"]["discovery"] == "active"
            and receiver["runtime"]["loaded"]["relation_to_source"] == "exact"
        )
        if runtime_is_exact:
            _fail("runtime-mismatch requires runtime drift from the exact source")
    if reason == "ambiguous-evidence":
        if observed_source is None:
            _fail("missing observed source must use source-unavailable")
        receiver_relations = {
            receiver["catalog"]["relation_to_source"],
            receiver["cache"]["relation_to_source"],
            receiver["runtime"]["loaded"]["relation_to_source"],
        }
        has_unknown = (
            observed_source["relation_to_source"] == "unknown"
            or observed_source["verification_state"] == "unverified"
            or "unknown" in receiver_relations
            or receiver["runtime"]["discovery"] == "unknown"
        )
        if not has_unknown:
            _fail("ambiguous-evidence requires unknown evidence")


def _load_json(path: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractValidationError(f"unable to read {label}: {exc}") from exc
    return _require_object(value, label)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff", required=True, help="Handoff JSON path")
    parser.add_argument("--ack", help="Optional acknowledgement JSON path")
    args = parser.parse_args()

    try:
        handoff = _load_json(args.handoff, "handoff")
        validate_handoff(handoff)
        ack_state = "not-provided"
        if args.ack:
            acknowledgement = _load_json(args.ack, "ack")
            validate_acknowledgement(handoff, acknowledgement)
            ack_state = "valid"
    except ContractValidationError as exc:
        print(
            json.dumps(
                {
                    "schema": "codex.thread_skill_handoff_validation.v1",
                    "valid": False,
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            {
                "schema": "codex.thread_skill_handoff_validation.v1",
                "valid": True,
                "handoff": "valid",
                "acknowledgement": ack_state,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
