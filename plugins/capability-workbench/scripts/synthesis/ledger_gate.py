#!/usr/bin/env python3
"""Shared helpers for synthesis ledger gates.

Every gate in this folder reads a JSON ledger, checks its schema tag (allowing
retired tags with a warning), validates it, and prints one result object whose
exit status is derived from the error list. These helpers keep that contract in
one place so gates only carry their own validation rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"invalid_json:{path}:{exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("ledger_must_be_object")
    return data


def non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(value)


def check_schema(
    data: dict[str, Any],
    schema: str,
    deprecated: set[str],
    errors: list[str],
    warnings: list[str],
) -> None:
    tag = data.get("schema")
    if tag in deprecated:
        warnings.append(f"schema_{tag}_is_deprecated_use_{schema}")
    elif tag != schema:
        errors.append(f"schema_must_be_{schema}")


def emit_result(result: dict[str, Any], *, indent: bool) -> int:
    print(json.dumps(result, indent=2 if indent else None, ensure_ascii=False))
    return 0 if not result["errors"] else 1
