#!/usr/bin/env python3
"""Validate aggregate evidence claims against an exact item-by-dimension matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any


INPUT_SCHEMA = "capability.evidence_coverage.v1"
RESULT_SCHEMA = "capability.evidence_coverage_gate.result.v1"
VALID_UNIVERSE_STATUS = {"complete", "partial"}
VALID_CLAIM_KINDS = {"full_matrix", "bounded_matrix"}
VALID_OUTCOMES = {"pass", "fail", "blocked"}

MAX_INPUT_BYTES = 2_000_000
MAX_ITEMS = 2_048
MAX_DIMENSIONS = 32
MAX_PAIRS = 4_096
MAX_TOTAL_CLAIM_PAIRS = MAX_PAIRS
MAX_CHECKS = MAX_PAIRS
MAX_CLAIMS = 128
MAX_EVIDENCE_REFS = 16
MAX_ERRORS = 256
MAX_ERROR_LENGTH = 256

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,127}")
DIMENSION = re.compile(r"[a-z][a-z0-9-]{0,63}")

TEMPLATE = {
    "schema": INPUT_SCHEMA,
    "subject": "replace-with-bounded-subject",
    "cutoff": "replace-with-snapshot-or-revision",
    "universe": {
        "status": "partial",
        "items": ["alpha", "beta"],
        "dimensions": ["metadata", "source-review"],
        "evidence_refs": ["inventory-ref"],
    },
    "checks": [
        {
            "item": "alpha",
            "dimension": "metadata",
            "outcome": "pass",
            "evidence_refs": ["alpha-metadata-ref"],
        }
    ],
    "claims": [
        {
            "id": "full-review",
            "kind": "full_matrix",
            "items": ["alpha", "beta"],
            "dimensions": ["metadata", "source-review"],
        }
    ],
}


class DuplicateKeyError(ValueError):
    """Raised when JSON contains an ambiguous duplicate object key."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def single_line(value: Any, *, max_length: int) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= max_length
        and value == value.strip()
        and all(ord(char) >= 32 and char not in "\r\n" for char in value)
    )


def identifier(value: Any, pattern: re.Pattern[str] = IDENTIFIER) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def unknown_fields(
    value: dict[str, Any],
    allowed: set[str],
    location: str,
    errors: list[str],
) -> None:
    for field in sorted(set(value) - allowed):
        safe_field = field if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", field) else "<invalid>"
        errors.append(f"unknown_field:{location}.{safe_field}")


def bounded_errors(errors: list[str]) -> list[str]:
    normalized = [
        error if len(error) <= MAX_ERROR_LENGTH else "validation_error_redacted"
        for error in errors
    ]
    unique = sorted(set(normalized))
    if len(unique) <= MAX_ERRORS:
        return unique
    return [*unique[: MAX_ERRORS - 1], "validation_errors_truncated"]


def validate_identifier_list(
    value: Any,
    *,
    location: str,
    pattern: re.Pattern[str],
    limit: int,
    errors: list[str],
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"must_be_list:{location}")
        return []
    if not value:
        errors.append(f"must_not_be_empty:{location}")
        return []
    if len(value) > limit:
        errors.append(f"too_many_values:{location}")
    valid: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value[:limit]):
        if not identifier(item, pattern):
            errors.append(f"invalid_identifier:{location}[{index}]")
            continue
        if item in seen:
            errors.append(f"duplicate_value:{location}:{item}")
            continue
        seen.add(item)
        valid.append(item)
    return valid


def validate_evidence_refs(
    value: Any,
    *,
    location: str,
    errors: list[str],
) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"must_be_list:{location}")
        return []
    if not value:
        errors.append(f"must_not_be_empty:{location}")
        return []
    if len(value) > MAX_EVIDENCE_REFS:
        errors.append(f"too_many_values:{location}")
    valid: list[str] = []
    seen: set[str] = set()
    for index, ref in enumerate(value[:MAX_EVIDENCE_REFS]):
        if not single_line(ref, max_length=512):
            errors.append(f"invalid_evidence_ref:{location}[{index}]")
            continue
        if ref in seen:
            errors.append(f"duplicate_value:{location}")
            continue
        seen.add(ref)
        valid.append(ref)
    return valid


def load_ledger(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    descriptor: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None, ["ledger_must_be_regular_file"]
        stream = os.fdopen(descriptor, "rb")
        descriptor = None
        with stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            return None, ["input_too_large"]
        text = raw.decode("utf-8")
    except (OSError, UnicodeError):
        return None, ["ledger_unreadable"]
    finally:
        if descriptor is not None:
            os.close(descriptor)
    try:
        value = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except DuplicateKeyError:
        return None, ["duplicate_json_key"]
    except json.JSONDecodeError:
        return None, ["invalid_json"]
    except (ValueError, RecursionError):
        return None, ["invalid_json"]
    if not isinstance(value, dict):
        return None, ["ledger_must_be_object"]
    return value, []


def validate_ledger(data: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    unknown_fields(
        data,
        {"schema", "subject", "cutoff", "universe", "checks", "claims"},
        "$",
        errors,
    )
    if data.get("schema") != INPUT_SCHEMA:
        errors.append(f"schema_must_be:{INPUT_SCHEMA}")
    if not single_line(data.get("subject"), max_length=256):
        errors.append("invalid_subject")
    if not single_line(data.get("cutoff"), max_length=256):
        errors.append("invalid_cutoff")
    subject = data.get("subject")
    cutoff = data.get("cutoff")

    universe_value = data.get("universe")
    if not isinstance(universe_value, dict):
        errors.append("universe_must_be_object")
        universe_value = {}
    unknown_fields(
        universe_value,
        {"status", "items", "dimensions", "evidence_refs"},
        "$.universe",
        errors,
    )
    universe_status = universe_value.get("status")
    if not isinstance(universe_status, str) or universe_status not in VALID_UNIVERSE_STATUS:
        errors.append("invalid_universe_status")
    items = validate_identifier_list(
        universe_value.get("items"),
        location="$.universe.items",
        pattern=IDENTIFIER,
        limit=MAX_ITEMS,
        errors=errors,
    )
    dimensions = validate_identifier_list(
        universe_value.get("dimensions"),
        location="$.universe.dimensions",
        pattern=DIMENSION,
        limit=MAX_DIMENSIONS,
        errors=errors,
    )
    universe_evidence_refs = validate_evidence_refs(
        universe_value.get("evidence_refs"),
        location="$.universe.evidence_refs",
        errors=errors,
    )
    if items and dimensions and len(items) * len(dimensions) > MAX_PAIRS:
        errors.append("universe_matrix_too_large")

    item_set = set(items)
    dimension_set = set(dimensions)

    checks_value = data.get("checks")
    if not isinstance(checks_value, list):
        errors.append("checks_must_be_list")
        checks_value = []
    elif len(checks_value) > MAX_CHECKS:
        errors.append("too_many_checks")
    checks: dict[tuple[str, str], dict[str, Any]] = {}
    for index, raw_check in enumerate(checks_value[:MAX_CHECKS]):
        location = f"$.checks[{index}]"
        if not isinstance(raw_check, dict):
            errors.append(f"must_be_object:{location}")
            continue
        unknown_fields(
            raw_check,
            {"item", "dimension", "outcome", "evidence_refs"},
            location,
            errors,
        )
        item = raw_check.get("item")
        dimension = raw_check.get("dimension")
        outcome = raw_check.get("outcome")
        item_known = identifier(item) and item in item_set
        dimension_known = identifier(dimension, DIMENSION) and dimension in dimension_set
        if not identifier(item):
            errors.append(f"invalid_identifier:{location}.item")
        elif not item_known:
            errors.append(f"unknown_item:{location}:{item}")
        if not identifier(dimension, DIMENSION):
            errors.append(f"invalid_identifier:{location}.dimension")
        elif not dimension_known:
            errors.append(f"unknown_dimension:{location}:{dimension}")
        if not isinstance(outcome, str) or outcome not in VALID_OUTCOMES:
            errors.append(f"invalid_outcome:{location}")
        check_evidence_refs = validate_evidence_refs(
            raw_check.get("evidence_refs"),
            location=f"{location}.evidence_refs",
            errors=errors,
        )
        if item_known and dimension_known:
            pair = (item, dimension)
            if pair in checks:
                errors.append(f"duplicate_check:{item}:{dimension}")
            else:
                checks[pair] = {
                    "item": item,
                    "dimension": dimension,
                    "outcome": outcome,
                    "evidence_refs": sorted(check_evidence_refs),
                }

    claims_value = data.get("claims")
    if not isinstance(claims_value, list):
        errors.append("claims_must_be_list")
        claims_value = []
    elif not claims_value:
        errors.append("claims_must_not_be_empty")
    elif len(claims_value) > MAX_CLAIMS:
        errors.append("too_many_claims")
    claims: list[dict[str, Any]] = []
    claim_ids: set[str] = set()
    total_claim_pairs = 0
    for index, raw_claim in enumerate(claims_value[:MAX_CLAIMS]):
        location = f"$.claims[{index}]"
        if not isinstance(raw_claim, dict):
            errors.append(f"must_be_object:{location}")
            continue
        unknown_fields(
            raw_claim,
            {"id", "kind", "items", "dimensions"},
            location,
            errors,
        )
        claim_id = raw_claim.get("id")
        claim_label = claim_id if identifier(claim_id) else f"index-{index}"
        kind = raw_claim.get("kind")
        kind_valid = isinstance(kind, str) and kind in VALID_CLAIM_KINDS
        if not identifier(claim_id):
            errors.append(f"invalid_identifier:{location}.id")
        elif claim_id in claim_ids:
            errors.append(f"duplicate_claim_id:{claim_id}")
        else:
            claim_ids.add(claim_id)
        if not kind_valid:
            errors.append(f"invalid_claim_kind:{location}")
        claim_items = validate_identifier_list(
            raw_claim.get("items"),
            location=f"{location}.items",
            pattern=IDENTIFIER,
            limit=MAX_ITEMS,
            errors=errors,
        )
        claim_dimensions = validate_identifier_list(
            raw_claim.get("dimensions"),
            location=f"{location}.dimensions",
            pattern=DIMENSION,
            limit=MAX_DIMENSIONS,
            errors=errors,
        )
        for item in sorted(set(claim_items) - item_set):
            errors.append(f"unknown_claim_item:{claim_label}:{item}")
        for dimension in sorted(set(claim_dimensions) - dimension_set):
            errors.append(f"unknown_claim_dimension:{claim_label}:{dimension}")
        claim_pair_count = len(claim_items) * len(claim_dimensions)
        if claim_items and claim_dimensions and claim_pair_count > MAX_PAIRS:
            errors.append(f"claim_matrix_too_large:{claim_label}")
        total_claim_pairs += claim_pair_count
        if kind == "full_matrix":
            if set(claim_items) != item_set:
                errors.append(f"full_matrix_items_must_equal_universe:{claim_label}")
            if set(claim_dimensions) != dimension_set:
                errors.append(f"full_matrix_dimensions_must_equal_universe:{claim_label}")
        if (
            identifier(claim_id)
            and kind_valid
            and set(claim_items).issubset(item_set)
            and set(claim_dimensions).issubset(dimension_set)
        ):
            claims.append(
                {
                    "id": claim_id,
                    "kind": kind,
                    "items": sorted(claim_items),
                    "dimensions": sorted(claim_dimensions),
                }
            )
    if total_claim_pairs > MAX_TOTAL_CLAIM_PAIRS:
        errors.append("total_claim_matrix_too_large")

    if errors:
        return None, bounded_errors(errors)
    normalized = {
        "subject": subject,
        "cutoff": cutoff,
        "universe_status": universe_status,
        "universe_evidence_refs": sorted(universe_evidence_refs),
        "items": sorted(items),
        "dimensions": sorted(dimensions),
        "checks": checks,
        "claims": sorted(claims, key=lambda claim: claim["id"]),
    }
    return normalized, []


def ledger_fingerprint(normalized: dict[str, Any]) -> str:
    canonical = {
        "schema": INPUT_SCHEMA,
        "subject": normalized["subject"],
        "cutoff": normalized["cutoff"],
        "universe": {
            "status": normalized["universe_status"],
            "items": normalized["items"],
            "dimensions": normalized["dimensions"],
            "evidence_refs": normalized["universe_evidence_refs"],
        },
        "checks": [
            {
                "item": check["item"],
                "dimension": check["dimension"],
                "outcome": check["outcome"],
                "evidence_refs": check["evidence_refs"],
            }
            for _, check in sorted(normalized["checks"].items())
        ],
        "claims": normalized["claims"],
    }
    payload = json.dumps(
        canonical,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def evaluate(normalized: dict[str, Any]) -> dict[str, Any]:
    checks: dict[tuple[str, str], dict[str, Any]] = normalized["checks"]
    claim_results: list[dict[str, Any]] = []
    satisfied_kinds: set[str] = set()
    for claim in normalized["claims"]:
        required_pairs = sorted(
            (item, dimension)
            for item in claim["items"]
            for dimension in claim["dimensions"]
        )
        missing_pairs: list[dict[str, str]] = []
        nonpassing_pairs: list[dict[str, str]] = []
        reasons: list[str] = []
        if claim["kind"] == "full_matrix" and normalized["universe_status"] != "complete":
            reasons.append("declared_universe_is_partial")
        for item, dimension in required_pairs:
            check = checks.get((item, dimension))
            if check is None:
                missing_pairs.append({"item": item, "dimension": dimension})
            elif check["outcome"] != "pass":
                nonpassing_pairs.append(
                    {
                        "item": item,
                        "dimension": dimension,
                        "outcome": check["outcome"],
                    }
                )
        satisfied = not reasons and not missing_pairs and not nonpassing_pairs
        if satisfied:
            satisfied_kinds.add(claim["kind"])
        claim_results.append(
            {
                "id": claim["id"],
                "kind": claim["kind"],
                "satisfied": satisfied,
                "required_pairs": len(required_pairs),
                "passed_pairs": len(required_pairs) - len(missing_pairs) - len(nonpassing_pairs),
                "missing_pairs": missing_pairs,
                "nonpassing_pairs": nonpassing_pairs,
                "reasons": sorted(reasons),
            }
        )
    all_satisfied = all(result["satisfied"] for result in claim_results)
    if "full_matrix" in satisfied_kinds:
        highest = "full_matrix"
    elif "bounded_matrix" in satisfied_kinds:
        highest = "bounded_matrix"
    else:
        highest = "none"
    return {
        "schema": RESULT_SCHEMA,
        "subject": normalized["subject"],
        "cutoff": normalized["cutoff"],
        "ledger_fingerprint": ledger_fingerprint(normalized),
        "declared_universe_status": normalized["universe_status"],
        "input_valid": True,
        "all_claims_satisfied": all_satisfied,
        "highest_satisfied_claim": highest,
        "errors": [],
        "claim_results": claim_results,
        "summary": {
            "declared_items": len(normalized["items"]),
            "declared_dimensions": len(normalized["dimensions"]),
            "recorded_pairs": len(checks),
            "passing_pairs": sum(1 for check in checks.values() if check["outcome"] == "pass"),
            "satisfied_claims": sum(1 for result in claim_results if result["satisfied"]),
            "unsatisfied_claims": sum(1 for result in claim_results if not result["satisfied"]),
        },
    }


def invalid_result(errors: list[str]) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "subject": None,
        "cutoff": None,
        "ledger_fingerprint": None,
        "declared_universe_status": None,
        "input_valid": False,
        "all_claims_satisfied": False,
        "highest_satisfied_claim": "none",
        "errors": bounded_errors(errors),
        "claim_results": [],
        "summary": {
            "declared_items": 0,
            "declared_dimensions": 0,
            "recorded_pairs": 0,
            "passing_pairs": 0,
            "satisfied_claims": 0,
            "unsatisfied_claims": 0,
        },
    }


def emit(result: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print(
            json.dumps(
                result,
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            )
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", nargs="?", help="Path to an evidence coverage ledger.")
    parser.add_argument("--template", action="store_true", help="Print an intentionally incomplete template.")
    parser.add_argument("--json", action="store_true", help="Pretty-print the canonical JSON result.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.template and args.ledger:
        result = invalid_result(["template_and_ledger_are_mutually_exclusive"])
        emit(result, pretty=args.json)
        return 2
    if args.template:
        print(json.dumps(TEMPLATE, indent=2, sort_keys=True, ensure_ascii=True))
        return 0
    if not args.ledger:
        result = invalid_result(["ledger_path_required"])
        emit(result, pretty=args.json)
        return 2
    data, load_errors = load_ledger(Path(args.ledger))
    if load_errors or data is None:
        result = invalid_result(load_errors or ["ledger_unreadable"])
        emit(result, pretty=args.json)
        return 2
    normalized, validation_errors = validate_ledger(data)
    if validation_errors or normalized is None:
        result = invalid_result(validation_errors or ["invalid_ledger"])
        emit(result, pretty=args.json)
        return 2
    result = evaluate(normalized)
    emit(result, pretty=args.json)
    return 0 if result["all_claims_satisfied"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
