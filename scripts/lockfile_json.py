#!/usr/bin/env python3
"""Strict JSON loading and syntax patterns shared by lockfile validators.

The external-dependency and first-party-plugin lockfiles are both immutable
supply-chain records, so they need the same guarantees: duplicate object keys
are rejected instead of silently collapsed, the payload must be a JSON object,
and identifiers, repositories, and digests must match one canonical syntax.
Each validator wraps `StrictJsonError` in its own error type so its command
line keeps reporting failures the way it always has.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
GITHUB_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
GITHUB_REPOSITORY_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/"
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$"
)
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class StrictJsonError(ValueError):
    """Raised when a document is unreadable, not an object, or has duplicate keys."""


def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"JSON object: duplicate key {key!r}")
        result[key] = value
    return result


def load_object(
    path: Path,
    location: str,
    *,
    require_file: bool = False,
    read_error_template: str = (
        "{location}: cannot read valid nonblank UTF-8 JSON from {path}: {error}"
    ),
    non_object_template: str = "{location}: must be a JSON object",
) -> dict[str, Any]:
    if require_file and not path.is_file():
        raise StrictJsonError(f"{location}: does not exist or is not a file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=object_pairs)
    except StrictJsonError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StrictJsonError(
            read_error_template.format(
                location=location,
                path=path,
                error=exc,
            )
        ) from exc
    if not isinstance(payload, dict):
        raise StrictJsonError(
            non_object_template.format(location=location, path=path)
        )
    return payload
