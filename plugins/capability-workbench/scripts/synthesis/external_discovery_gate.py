#!/usr/bin/env python3
"""Validate external discovery evidence before capability synthesis claims."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger_gate import (  # noqa: E402
    check_schema,
    emit_result,
    load_json,
    non_empty_list,
)


SCHEMA = "capability.external_discovery.v1"
DEPRECATED_SCHEMAS = {"codex.external_discovery.v1"}
VALID_BREADTH = {"external-broad", "external-light", "local-only"}
VALID_STATUS = {"complete", "partial", "skipped"}
VALID_STOP = {"diminishing_returns", "budget_limit", "blocked", "skipped"}


TEMPLATE = {
    "schema": SCHEMA,
    "target": "",
    "breadth": "external-broad",
    "status": "partial",
    "source_families": [],
    "search_waves": [
        {
            "wave": 1,
            "source_family": "public_repos",
            "queries": [],
            "tools": [],
            "results_reviewed": 0,
            "new_mechanisms": [],
        }
    ],
    "candidates": [],
    "stop_condition": "blocked",
    "blockers": ["fill this before claiming synthesis complete"],
    "local_sources_used": [],
    "notes": "",
}


def validate(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    check_schema(data, SCHEMA, DEPRECATED_SCHEMAS, errors, warnings)

    breadth = data.get("breadth")
    status = data.get("status")
    stop = data.get("stop_condition")

    if breadth not in VALID_BREADTH:
        errors.append("invalid_breadth")
    if status not in VALID_STATUS:
        errors.append("invalid_status")
    if stop not in VALID_STOP:
        errors.append("invalid_stop_condition")

    source_families = data.get("source_families")
    waves = data.get("search_waves")
    candidates = data.get("candidates")

    if status == "skipped":
        if not data.get("skip_reason"):
            errors.append("skipped_requires_skip_reason")
        return errors, warnings

    if breadth == "local-only":
        if not data.get("skip_reason") and status != "partial":
            errors.append("local_only_requires_skip_reason_or_partial_status")
        warnings.append("local_only_cannot_claim_global_optimum")
        return errors, warnings

    if not non_empty_list(source_families):
        errors.append("missing_source_families")
    if not isinstance(waves, list) or not waves:
        errors.append("missing_search_waves")
    if not isinstance(candidates, list):
        errors.append("candidates_must_be_list")

    if breadth == "external-broad":
        if status == "complete":
            if len(source_families or []) < 3:
                errors.append("external_broad_complete_requires_three_source_families")
            if len(waves or []) < 2:
                errors.append("external_broad_complete_requires_two_search_waves")
            if stop != "diminishing_returns":
                errors.append("external_broad_complete_requires_diminishing_returns")
            if not non_empty_list(candidates):
                errors.append("external_broad_complete_requires_candidates")
        elif status == "partial":
            if not non_empty_list(data.get("blockers")):
                errors.append("partial_requires_blockers")
            warnings.append("partial_must_not_claim_global_convergence")

    if breadth == "external-light" and status == "complete":
        if len(source_families or []) < 1:
            errors.append("external_light_complete_requires_source_family")
        if len(waves or []) < 1:
            errors.append("external_light_complete_requires_search_wave")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate external discovery evidence for Workbench synthesis.")
    parser.add_argument("ledger", nargs="?", help="Path to external-discovery-ledger.json")
    parser.add_argument("--template", action="store_true", help="Print a ledger template.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result.")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(TEMPLATE, indent=2, ensure_ascii=False))
        return 0
    if not args.ledger:
        parser.error("ledger path is required unless --template is used")

    path = Path(args.ledger)
    data = load_json(path)
    errors, warnings = validate(data)
    result = {
        "schema": "capability.external_discovery_gate.result.v1",
        "path": str(path),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "status": data.get("status"),
        "breadth": data.get("breadth"),
        "stop_condition": data.get("stop_condition"),
    }
    return emit_result(result, indent=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
