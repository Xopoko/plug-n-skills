#!/usr/bin/env python3
"""Validate action-safe context-density state commitment bundles.

The command is deliberately read-only and dependency-free:

    state_commitment_guard.py validate --input FILE

Exit codes are 0 for a valid bundle, 1 for malformed or unsafe input, and 2
for a well-formed bundle whose semantics, digest, or companions have drifted.
Every outcome is a deterministic JSON object written to stdout.
"""

from __future__ import annotations

import hashlib
import errno
import json
import os
import re
import stat
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

STATE_SCHEMA = "context_density.state_commitment.v2"
VALIDATION_SCHEMA = "context_density.state_commitment_validation.v1"
ERROR_SCHEMA = "context_density.state_commitment_error.v1"
UNICODE_DB = unicodedata.ucd_3_2_0
UNICODE_VERSION = UNICODE_DB.unidata_version
ASCII_WHITESPACE = " \t\n\r\v\f"

MAX_INPUT_BYTES = 1_048_576
MAX_COMPANION_BYTES = 1_048_576
MAX_STRING_CHARS = 4096
MAX_ARRAY_ITEMS = 1024
MAX_OBJECT_FIELDS = 32
MAX_NESTING = 16

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
ACTION_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")
KIND_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,63}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UTC_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T"
    r"(?P<time>\d{2}:\d{2}:\d{2})(?P<fraction>\.\d{1,6})?Z$"
)
MARKER_RE = re.compile(r"<!-- cda:state-commitment sha256:([0-9a-f]{64}) -->")
MARKER_PREFIX = "<!-- cda:state-commitment"

TOP_FIELDS = {
    "schema",
    "state_version",
    "cutoff_utc",
    "entities",
    "stop_scopes",
    "source_refs",
    "commitment_digest",
    "companions",
}
ENTITY_FIELDS = {
    "id",
    "identities",
    "current_identity_ids",
    "source_review",
    "executable_proof",
    "authority",
    "confidence",
    "conflict",
}
IDENTITY_FIELDS = {
    "id",
    "kind",
    "value",
    "status",
    "source_ref_ids",
    "superseded_by",
}
REVIEW_FIELDS = {"status", "identity_ids", "source_ref_ids"}
PROOF_FIELDS = {"status", "identity_ids", "source_ref_ids", "execution_count"}
AUTHORITY_FIELDS = {"mode", "actions", "source_ref_ids"}
CONFIDENCE_FIELDS = {"level", "source_ref_ids"}
CONFLICT_FIELDS = {"status", "fallback", "source_ref_ids"}
SOURCE_REF_FIELDS = {"id", "origin_id", "kind", "location", "observed_at_utc"}
STOP_FIELDS = {"id", "status", "entity_ids", "actions", "source_ref_ids"}
COMPANION_FIELDS = {"path", "sha256"}

SOURCE_KINDS = {
    "identity",
    "review",
    "executable_proof",
    "authority",
    "confidence",
    "conflict",
    "stop",
}
REVIEW_STATUSES = {
    "not_reviewed",
    "in_progress",
    "accepted",
    "changes_requested",
    "rejected",
    "unavailable",
}
PROOF_STATUSES = {"not_run", "running", "passed", "failed", "unavailable"}
AUTHORITY_MODES = {"read_only", "scoped_write", "unknown"}
CONFIDENCE_LEVELS = {"high", "medium", "low", "unknown"}
CONFLICT_STATUSES = {"none", "resolved", "unresolved"}
FALLBACKS = {"none", "fail_closed", "revalidate", "ask_user"}
IDENTITY_STATUSES = {"current", "superseded"}
STOP_STATUSES = {"active", "inactive"}
INPUT_ERROR_CODES = {
    "array_too_large",
    "blank_identity_value",
    "blank_source_location",
    "duplicate_companion_path",
    "duplicate_companion_target",
    "duplicate_id",
    "duplicate_value",
    "empty_array",
    "empty_string",
    "invalid_action",
    "invalid_enum",
    "invalid_execution_count",
    "invalid_id",
    "invalid_identity_value_character",
    "invalid_identity_kind",
    "invalid_sha256",
    "invalid_source_location_character",
    "invalid_state_version",
    "invalid_type",
    "invalid_utc_timestamp",
    "missing_field",
    "nesting_too_deep",
    "noncanonical_identity_value",
    "object_too_large",
    "string_too_long",
    "unknown_field",
    "wrong_schema",
}


class InputProblem(Exception):
    """Malformed or unsafe input that must exit 1."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


class DuplicateKey(ValueError):
    """Raised by the JSON decoder for duplicate object keys."""


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKey(f"duplicate object key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _json_line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _error_payload(problem: InputProblem) -> dict[str, Any]:
    return {
        "schema": ERROR_SCHEMA,
        "status": "error",
        "valid": False,
        "error": {
            "code": problem.code,
            "path": problem.path,
            "message": problem.message,
        },
    }


def canonical_core(bundle: dict[str, Any]) -> bytes:
    """Return canonical UTF-8 JSON for the commitment-covered fields."""
    core = {
        key: value
        for key, value in bundle.items()
        if key not in {"commitment_digest", "companions"}
    }
    return json.dumps(
        core,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def compute_digest(bundle: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_core(bundle)).hexdigest()


def compute_snapshot_digest(
    commitment_digest: str, companions: list[dict[str, Any]]
) -> str:
    """Bind the committed core to a canonical, path-sorted sidecar manifest."""
    manifest = sorted(
        ({"path": item["path"], "sha256": item["sha256"]} for item in companions),
        key=lambda item: item["path"],
    )
    payload = {
        "commitment_digest": commitment_digest,
        "companions": manifest,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class BoundedReadProblem(Exception):
    """Stable internal classification for descriptor-based file reads."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _same_snapshot(left: os.stat_result, right: os.stat_result) -> bool:
    """Compare identity plus metadata that changes when a regular file mutates."""
    return (
        _same_file(left, right)
        and left.st_mode == right.st_mode
        and left.st_nlink == right.st_nlink
        and left.st_uid == right.st_uid
        and left.st_gid == right.st_gid
        and left.st_size == right.st_size
        and left.st_mtime_ns == right.st_mtime_ns
        and left.st_ctime_ns == right.st_ctime_ns
    )


def _safe_relative_io_supported() -> bool:
    return (
        bool(getattr(os, "O_NOFOLLOW", 0))
        and bool(getattr(os, "O_DIRECTORY", 0))
        and os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )


def _directory_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
    )


def _file_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )


def _open_pinned_directory(path: Path) -> int:
    """Open every component of one absolute directory without following links."""
    if not _safe_relative_io_supported():
        raise BoundedReadProblem("unsupported")
    if not path.is_absolute() or not path.anchor:
        raise BoundedReadProblem("unsafe_path")
    try:
        descriptor = os.open(path.anchor, _directory_flags())
    except FileNotFoundError:
        raise BoundedReadProblem("missing") from None
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise BoundedReadProblem("unsafe_path") from None
        raise BoundedReadProblem("unreadable") from None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode):
            raise BoundedReadProblem("unsafe_path")
        for part in path.parts[1:]:
            try:
                child = _open_child_directory(descriptor, part)
            except BoundedReadProblem as problem:
                if problem.kind == "symlink":
                    raise BoundedReadProblem("unsafe_path") from None
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_child_directory(parent_descriptor: int, name: str) -> int:
    """Open and pin one already-validated relative directory component."""
    try:
        before = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        raise BoundedReadProblem("missing") from None
    except OSError:
        raise BoundedReadProblem("unreadable") from None
    if stat.S_ISLNK(before.st_mode):
        raise BoundedReadProblem("symlink")
    if not stat.S_ISDIR(before.st_mode):
        raise BoundedReadProblem("unsafe_path")
    try:
        descriptor = os.open(
            name,
            _directory_flags(),
            dir_fd=parent_descriptor,
        )
    except FileNotFoundError:
        raise BoundedReadProblem("changed") from None
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise BoundedReadProblem("symlink") from None
        raise BoundedReadProblem("unreadable") from None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode):
            raise BoundedReadProblem("unsafe_path")
        if not _same_file(before, opened):
            raise BoundedReadProblem("changed")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular_at(
    parent_descriptor: int,
    name: str,
    max_bytes: int,
) -> tuple[bytes, os.stat_result]:
    """Read one regular leaf relative to a pinned parent directory."""
    try:
        before = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        raise BoundedReadProblem("missing") from None
    except OSError:
        raise BoundedReadProblem("unreadable") from None
    if stat.S_ISLNK(before.st_mode):
        raise BoundedReadProblem("symlink")
    if not stat.S_ISREG(before.st_mode):
        raise BoundedReadProblem("not_regular")
    try:
        descriptor = os.open(
            name,
            _file_flags(),
            dir_fd=parent_descriptor,
        )
    except FileNotFoundError:
        raise BoundedReadProblem("changed") from None
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise BoundedReadProblem("symlink") from None
        raise BoundedReadProblem("unreadable") from None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise BoundedReadProblem("not_regular")
        if not _same_snapshot(before, opened):
            raise BoundedReadProblem("changed")
        if opened.st_size > max_bytes:
            raise BoundedReadProblem("too_large")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        if len(raw) > max_bytes:
            raise BoundedReadProblem("too_large")
        after_opened = os.fstat(descriptor)
        if not _same_snapshot(opened, after_opened):
            raise BoundedReadProblem("changed")
        if after_opened.st_size > max_bytes:
            raise BoundedReadProblem("too_large")
        try:
            after = os.stat(
                name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError:
            raise BoundedReadProblem("changed") from None
        if not _same_snapshot(after_opened, after):
            raise BoundedReadProblem("changed")
        return raw, opened
    finally:
        os.close(descriptor)


def _read_regular_beneath(
    base_descriptor: int,
    parts: tuple[str, ...],
    max_bytes: int,
) -> tuple[bytes, os.stat_result]:
    """Traverse validated components without reopening a multi-component path."""
    if not _safe_relative_io_supported():
        raise BoundedReadProblem("unsupported")
    current = os.dup(base_descriptor)
    try:
        for part in parts[:-1]:
            child = _open_child_directory(current, part)
            os.close(current)
            current = child
        return _read_regular_at(current, parts[-1], max_bytes)
    finally:
        os.close(current)


def _load_input(path_text: str) -> tuple[dict[str, Any], int]:
    if "\x00" in path_text:
        raise InputProblem(
            "input_unsafe_path",
            "$",
            "input path must not contain an embedded NUL",
        )
    path = Path(os.path.abspath(path_text))
    base: int | None = None
    try:
        base = _open_pinned_directory(path.parent)
        raw, _ = _read_regular_at(base, path.name, MAX_INPUT_BYTES)
    except BoundedReadProblem as problem:
        if base is not None:
            os.close(base)
        if problem.kind == "too_large":
            raise InputProblem(
                "input_too_large", "$", f"input exceeds {MAX_INPUT_BYTES} bytes"
            ) from None
        if problem.kind == "not_regular":
            raise InputProblem(
                "input_not_regular", "$", "input must be a regular file"
            ) from None
        if problem.kind == "symlink":
            raise InputProblem(
                "input_symlink", "$", "input must not be a symlink"
            ) from None
        if problem.kind == "unsupported":
            raise InputProblem(
                "safe_traversal_unavailable",
                "$",
                "safe descriptor-relative input traversal is unavailable",
            ) from None
        if problem.kind == "unsafe_path":
            raise InputProblem(
                "input_unsafe_path",
                "$",
                "input parent must be a safely opened directory",
            ) from None
        if problem.kind == "changed":
            raise InputProblem(
                "input_changed", "$", "input changed while it was read"
            ) from None
        raise InputProblem("input_unreadable", "$", "input could not be read") from None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        os.close(base)
        raise InputProblem("invalid_utf8", "$", "input is not valid UTF-8") from None
    try:
        data = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except DuplicateKey:
        os.close(base)
        raise InputProblem(
            "duplicate_key", "$", "input contains a duplicate object key"
        ) from None
    except (ValueError, RecursionError):
        os.close(base)
        raise InputProblem(
            "malformed_json", "$", "input is not valid strict JSON"
        ) from None
    if not isinstance(data, dict):
        os.close(base)
        raise InputProblem(
            "invalid_type", "$", "top-level JSON value must be an object"
        )
    try:
        _check_bounds(data, "$", 0)
    except BaseException:
        os.close(base)
        raise
    return data, base


def _check_bounds(value: Any, path: str, depth: int) -> None:
    if depth > MAX_NESTING:
        raise InputProblem(
            "nesting_too_deep",
            path,
            f"JSON nesting exceeds {MAX_NESTING}",
        )
    if isinstance(value, str):
        if _contains_surrogate(value):
            raise InputProblem(
                "invalid_unicode", path, "strings must not contain lone surrogates"
            )
        if len(value) > MAX_STRING_CHARS:
            raise InputProblem(
                "string_too_long",
                path,
                f"string exceeds {MAX_STRING_CHARS} characters",
            )
    elif isinstance(value, list):
        if len(value) > MAX_ARRAY_ITEMS:
            raise InputProblem(
                "array_too_large",
                path,
                f"array exceeds {MAX_ARRAY_ITEMS} items",
            )
        for index, item in enumerate(value):
            _check_bounds(item, f"{path}[{index}]", depth + 1)
    elif isinstance(value, dict):
        if len(value) > MAX_OBJECT_FIELDS:
            raise InputProblem(
                "object_too_large",
                path,
                f"object exceeds {MAX_OBJECT_FIELDS} fields",
            )
        for key, item in value.items():
            if _contains_surrogate(key):
                raise InputProblem(
                    "invalid_unicode",
                    f"{path}.<key>",
                    "object keys must not contain lone surrogates",
                )
            if len(key) > MAX_STRING_CHARS:
                raise InputProblem(
                    "string_too_long",
                    f"{path}.<key>",
                    f"object key exceeds {MAX_STRING_CHARS} characters",
                )
            _check_bounds(item, f"{path}.{key}", depth + 1)


def _contains_surrogate(value: str) -> bool:
    return any("\ud800" <= character <= "\udfff" for character in value)


def _strip_ascii_whitespace(value: str) -> str:
    return value.strip(ASCII_WHITESPACE)


def _contains_disallowed_text_character(value: str) -> bool:
    for character in value:
        category = UNICODE_DB.category(character)
        if category.startswith("C"):
            return True
        if category.startswith("Z") and character != " ":
            return True
    return False


def _has_visible_character(value: str) -> bool:
    return any(
        UNICODE_DB.category(character)[0] in {"L", "N", "P", "S"} for character in value
    )


def _schema_object(
    value: Any,
    expected: set[str],
    path: str,
    errors: list[dict[str, str]],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _add(errors, "invalid_type", path, "must be an object")
        return None
    unknown = sorted(set(value) - expected)
    missing = sorted(expected - set(value))
    for key in unknown:
        _add(
            errors,
            "unknown_field",
            f"{path}.{key}",
            "field is not allowed",
        )
    for key in missing:
        _add(errors, "missing_field", f"{path}.{key}", "field is required")
    return value


def _array(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
    *,
    nonempty: bool = False,
) -> list[Any]:
    if not isinstance(value, list):
        _add(errors, "invalid_type", path, "must be an array")
        return []
    if nonempty and not value:
        _add(errors, "empty_array", path, "must not be empty")
    return value


def _string(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
    *,
    nonempty: bool = True,
) -> str | None:
    if not isinstance(value, str):
        _add(errors, "invalid_type", path, "must be a string")
        return None
    if nonempty and not value:
        _add(errors, "empty_string", path, "must not be empty")
        return None
    return value


def _enum(
    value: Any,
    allowed: set[str],
    path: str,
    errors: list[dict[str, str]],
) -> str | None:
    result = _string(value, path, errors)
    if result is not None and result not in allowed:
        _add(
            errors,
            "invalid_enum",
            path,
            f"must be one of {', '.join(sorted(allowed))}",
        )
        return None
    return result


def _identifier(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
) -> str | None:
    result = _string(value, path, errors)
    if result is not None and not ID_RE.fullmatch(result):
        _add(errors, "invalid_id", path, "must be a portable identifier")
        return None
    return result


def _string_array(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
    *,
    identifiers: bool = False,
    actions: bool = False,
    nonempty: bool = False,
) -> list[str]:
    raw = _array(value, path, errors, nonempty=nonempty)
    result: list[str] = []
    for index, item in enumerate(raw):
        item_path = f"{path}[{index}]"
        parsed = (
            _identifier(item, item_path, errors)
            if identifiers
            else _string(item, item_path, errors)
        )
        if parsed is not None:
            if actions and not ACTION_RE.fullmatch(parsed):
                _add(
                    errors,
                    "invalid_action",
                    item_path,
                    "must be a portable lower-case action",
                )
            else:
                result.append(parsed)
    if len(result) != len(set(result)):
        _add(errors, "duplicate_value", path, "array values must be unique")
    return result


def _utc(
    value: Any,
    path: str,
    errors: list[dict[str, str]],
) -> datetime | None:
    text = _string(value, path, errors)
    if text is None:
        return None
    match = UTC_RE.fullmatch(text)
    if match is None:
        _add(
            errors,
            "invalid_utc_timestamp",
            path,
            "must be an RFC 3339 UTC timestamp ending in Z",
        )
        return None
    try:
        return datetime.fromisoformat(text[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError:
        _add(
            errors,
            "invalid_utc_timestamp",
            path,
            "timestamp has an invalid calendar value",
        )
        return None


def _add(
    errors: list[dict[str, str]],
    code: str,
    path: str,
    message: str,
) -> None:
    errors.append({"code": code, "path": path, "message": message})


def _unique_id(
    identifier: str | None,
    path: str,
    all_ids: dict[str, str],
    errors: list[dict[str, str]],
) -> None:
    if identifier is None:
        return
    if identifier in all_ids:
        _add(
            errors,
            "duplicate_id",
            path,
            f"duplicates {all_ids[identifier]}",
        )
    else:
        all_ids[identifier] = path


def _ref_kind_check(
    ids: list[str],
    expected: str,
    path: str,
    source_refs: dict[str, dict[str, Any]],
    errors: list[dict[str, str]],
) -> None:
    for index, ref_id in enumerate(ids):
        item_path = f"{path}[{index}]"
        ref = source_refs.get(ref_id)
        if ref is None:
            _add(errors, "dangling_source_ref", item_path, "source ref does not exist")
        elif ref.get("kind") != expected:
            _add(
                errors,
                "wrong_source_ref_kind",
                item_path,
                f"must reference kind {expected}",
            )


def _identity_binding_check(
    ids: list[str],
    current: set[str],
    path: str,
    errors: list[dict[str, str]],
) -> None:
    for index, identity_id in enumerate(ids):
        if identity_id not in current:
            _add(
                errors,
                "non_current_identity_ref",
                f"{path}[{index}]",
                "must reference a current identity in this entity",
            )


def _validate_source_refs(
    raw_refs: Any,
    cutoff: datetime | None,
    all_ids: dict[str, str],
    errors: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    location_origins: dict[str, str] = {}
    for index, raw in enumerate(
        _array(raw_refs, "$.source_refs", errors, nonempty=True)
    ):
        path = f"$.source_refs[{index}]"
        ref = _schema_object(raw, SOURCE_REF_FIELDS, path, errors)
        if ref is None:
            continue
        ref_id = _identifier(ref.get("id"), f"{path}.id", errors)
        _unique_id(ref_id, f"{path}.id", all_ids, errors)
        origin_id = _identifier(ref.get("origin_id"), f"{path}.origin_id", errors)
        kind = _enum(ref.get("kind"), SOURCE_KINDS, f"{path}.kind", errors)
        location = _string(ref.get("location"), f"{path}.location", errors)
        location_valid = location is not None
        if location is not None:
            trimmed_location = _strip_ascii_whitespace(location)
            if not trimmed_location:
                _add(
                    errors,
                    "blank_source_location",
                    f"{path}.location",
                    "source location must contain visible text",
                )
                location_valid = False
            elif _contains_disallowed_text_character(location):
                _add(
                    errors,
                    "invalid_source_location_character",
                    f"{path}.location",
                    "source location must not contain control, format, surrogate, "
                    "private-use, unassigned, or non-ASCII separator characters",
                )
                location_valid = False
            elif not _has_visible_character(location):
                _add(
                    errors,
                    "blank_source_location",
                    f"{path}.location",
                    "source location must contain visible text",
                )
                location_valid = False
        if location_valid and location is not None and origin_id is not None:
            location_key = _strip_ascii_whitespace(location)
            prior_origin = location_origins.get(location_key)
            if prior_origin is not None and prior_origin != origin_id:
                _add(
                    errors,
                    "source_location_origin_conflict",
                    f"{path}.origin_id",
                    "one source location must not declare multiple origins",
                )
            else:
                location_origins[location_key] = origin_id
        observed = _utc(ref.get("observed_at_utc"), f"{path}.observed_at_utc", errors)
        if observed is not None and cutoff is not None and observed > cutoff:
            _add(
                errors,
                "source_after_cutoff",
                f"{path}.observed_at_utc",
                "source observation is later than cutoff_utc",
            )
        if ref_id is not None and ref_id not in refs:
            refs[ref_id] = {
                "origin_id": origin_id,
                "kind": kind,
                "location": location,
                "observed_at_utc": observed,
            }
    return refs


def _validate_identity(
    raw: Any,
    path: str,
    all_ids: dict[str, str],
    errors: list[dict[str, str]],
) -> dict[str, Any] | None:
    identity = _schema_object(raw, IDENTITY_FIELDS, path, errors)
    if identity is None:
        return None
    identity_id = _identifier(identity.get("id"), f"{path}.id", errors)
    _unique_id(identity_id, f"{path}.id", all_ids, errors)
    kind = _string(identity.get("kind"), f"{path}.kind", errors)
    if kind is not None and not KIND_RE.fullmatch(kind):
        _add(
            errors,
            "invalid_identity_kind",
            f"{path}.kind",
            "must be a portable lower-case kind",
        )
    value = _string(identity.get("value"), f"{path}.value", errors)
    if value is not None:
        trimmed_value = _strip_ascii_whitespace(value)
        if not trimmed_value:
            _add(
                errors,
                "blank_identity_value",
                f"{path}.value",
                "identity value must contain visible text",
            )
            value = None
        elif _contains_disallowed_text_character(value):
            _add(
                errors,
                "invalid_identity_value_character",
                f"{path}.value",
                "identity value must not contain control, format, surrogate, "
                "private-use, unassigned, or non-ASCII separator characters",
            )
            value = None
        elif not _has_visible_character(value):
            _add(
                errors,
                "blank_identity_value",
                f"{path}.value",
                "identity value must contain visible text",
            )
            value = None
        elif value != trimmed_value:
            _add(
                errors,
                "noncanonical_identity_value",
                f"{path}.value",
                "identity value must not have outer whitespace",
            )
            value = None
    status_value = _enum(
        identity.get("status"), IDENTITY_STATUSES, f"{path}.status", errors
    )
    refs = _string_array(
        identity.get("source_ref_ids"),
        f"{path}.source_ref_ids",
        errors,
        identifiers=True,
        nonempty=True,
    )
    superseded = identity.get("superseded_by")
    if superseded is not None:
        superseded = _identifier(superseded, f"{path}.superseded_by", errors)
    if status_value == "current" and superseded is not None:
        _add(
            errors,
            "current_has_successor",
            f"{path}.superseded_by",
            "current identity must use null",
        )
    if status_value == "superseded" and superseded is None:
        _add(
            errors,
            "superseded_missing_current",
            f"{path}.superseded_by",
            "superseded identity must reference its current replacement",
        )
    return {
        "id": identity_id,
        "kind": kind,
        "value": value,
        "status": status_value,
        "source_ref_ids": refs,
        "superseded_by": superseded,
    }


def _validate_review(
    raw: Any,
    path: str,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    review = _schema_object(raw, REVIEW_FIELDS, path, errors)
    if review is None:
        return {"status": None, "identity_ids": [], "source_ref_ids": []}
    status_value = _enum(
        review.get("status"), REVIEW_STATUSES, f"{path}.status", errors
    )
    identities = _string_array(
        review.get("identity_ids"),
        f"{path}.identity_ids",
        errors,
        identifiers=True,
    )
    refs = _string_array(
        review.get("source_ref_ids"),
        f"{path}.source_ref_ids",
        errors,
        identifiers=True,
    )
    if status_value != "not_reviewed":
        if not identities:
            _add(
                errors,
                "review_missing_identity",
                f"{path}.identity_ids",
                "review state must bind at least one current identity",
            )
        if not refs:
            _add(
                errors,
                "review_missing_evidence",
                f"{path}.source_ref_ids",
                "review state must reference review evidence",
            )
    elif status_value == "not_reviewed" and (identities or refs):
        _add(
            errors,
            "not_reviewed_has_evidence",
            path,
            "not_reviewed must have empty identity_ids and source_ref_ids",
        )
    return {"status": status_value, "identity_ids": identities, "source_ref_ids": refs}


def _validate_proof(
    raw: Any,
    path: str,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    proof = _schema_object(raw, PROOF_FIELDS, path, errors)
    if proof is None:
        return {
            "status": None,
            "identity_ids": [],
            "source_ref_ids": [],
            "execution_count": None,
        }
    status_value = _enum(proof.get("status"), PROOF_STATUSES, f"{path}.status", errors)
    identities = _string_array(
        proof.get("identity_ids"),
        f"{path}.identity_ids",
        errors,
        identifiers=True,
    )
    refs = _string_array(
        proof.get("source_ref_ids"),
        f"{path}.source_ref_ids",
        errors,
        identifiers=True,
    )
    count = proof.get("execution_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        _add(
            errors,
            "invalid_execution_count",
            f"{path}.execution_count",
            "must be a non-negative integer",
        )
        count = None
    if status_value in {"passed", "failed"}:
        if count is not None and count <= 0:
            _add(
                errors,
                "executed_proof_zero_count",
                f"{path}.execution_count",
                "passed or failed proof must have execution_count greater than zero",
            )
        if not identities:
            _add(
                errors,
                "proof_missing_identity",
                f"{path}.identity_ids",
                "executed proof must bind at least one current identity",
            )
        if not refs:
            _add(
                errors,
                "proof_missing_evidence",
                f"{path}.source_ref_ids",
                "executed proof must reference executable proof evidence",
            )
    elif status_value == "not_run":
        if count not in {0, None}:
            _add(
                errors,
                "not_run_has_execution",
                f"{path}.execution_count",
                "not_run proof must have execution_count zero",
            )
        if identities or refs:
            _add(
                errors,
                "not_run_has_evidence",
                path,
                "not_run must have empty identity_ids and source_ref_ids",
            )
    elif status_value in {"running", "unavailable"}:
        if not identities:
            _add(
                errors,
                "proof_missing_identity",
                f"{path}.identity_ids",
                "proof state must bind at least one current identity",
            )
        if not refs:
            _add(
                errors,
                "proof_missing_evidence",
                f"{path}.source_ref_ids",
                "proof state must reference executable proof evidence",
            )
        if status_value == "unavailable" and count not in {0, None}:
            _add(
                errors,
                "unavailable_has_execution",
                f"{path}.execution_count",
                "unavailable proof must have execution_count zero",
            )
    return {
        "status": status_value,
        "identity_ids": identities,
        "source_ref_ids": refs,
        "execution_count": count,
    }


def _validate_authority(
    raw: Any,
    path: str,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    authority = _schema_object(raw, AUTHORITY_FIELDS, path, errors)
    if authority is None:
        return {"mode": None, "actions": [], "source_ref_ids": []}
    mode = _enum(authority.get("mode"), AUTHORITY_MODES, f"{path}.mode", errors)
    actions = _string_array(
        authority.get("actions"), f"{path}.actions", errors, actions=True
    )
    refs = _string_array(
        authority.get("source_ref_ids"),
        f"{path}.source_ref_ids",
        errors,
        identifiers=True,
        nonempty=True,
    )
    if mode in {"read_only", "unknown"} and actions:
        _add(
            errors,
            "non_write_authority_has_actions",
            f"{path}.actions",
            f"{mode} authority cannot authorize actions",
        )
    if mode == "scoped_write" and not actions:
        _add(
            errors,
            "scoped_write_missing_actions",
            f"{path}.actions",
            "scoped_write authority must authorize at least one action",
        )
    return {"mode": mode, "actions": actions, "source_ref_ids": refs}


def _validate_confidence(
    raw: Any,
    path: str,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    confidence = _schema_object(raw, CONFIDENCE_FIELDS, path, errors)
    if confidence is None:
        return {"level": None, "source_ref_ids": []}
    level = _enum(confidence.get("level"), CONFIDENCE_LEVELS, f"{path}.level", errors)
    refs = _string_array(
        confidence.get("source_ref_ids"),
        f"{path}.source_ref_ids",
        errors,
        identifiers=True,
    )
    if level != "unknown" and not refs:
        _add(
            errors,
            "confidence_missing_evidence",
            f"{path}.source_ref_ids",
            "known confidence must reference confidence evidence",
        )
    if level == "unknown" and refs:
        _add(
            errors,
            "unknown_confidence_has_evidence",
            f"{path}.source_ref_ids",
            "unknown confidence must not claim evidence",
        )
    return {"level": level, "source_ref_ids": refs}


def _validate_conflict(
    raw: Any,
    path: str,
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    conflict = _schema_object(raw, CONFLICT_FIELDS, path, errors)
    if conflict is None:
        return {"status": None, "fallback": None, "source_ref_ids": []}
    status_value = _enum(
        conflict.get("status"), CONFLICT_STATUSES, f"{path}.status", errors
    )
    fallback = _enum(conflict.get("fallback"), FALLBACKS, f"{path}.fallback", errors)
    refs = _string_array(
        conflict.get("source_ref_ids"),
        f"{path}.source_ref_ids",
        errors,
        identifiers=True,
    )
    if status_value == "none":
        if fallback != "none" or refs:
            _add(
                errors,
                "no_conflict_has_fallback",
                path,
                "no conflict must use fallback none and empty evidence",
            )
    elif status_value in {"resolved", "unresolved"}:
        if not refs:
            _add(
                errors,
                "conflict_missing_evidence",
                f"{path}.source_ref_ids",
                "conflict must reference conflict evidence",
            )
        if status_value == "resolved" and fallback != "none":
            _add(
                errors,
                "resolved_conflict_has_fallback",
                f"{path}.fallback",
                "resolved conflict must use fallback none",
            )
        if status_value == "unresolved" and fallback == "none":
            _add(
                errors,
                "unresolved_conflict_missing_fallback",
                f"{path}.fallback",
                "unresolved conflict must use a fail-closed fallback",
            )
    return {"status": status_value, "fallback": fallback, "source_ref_ids": refs}


def _validate_entities(
    raw_entities: Any,
    source_refs: dict[str, dict[str, Any]],
    all_ids: dict[str, str],
    errors: list[dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    entities: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    current_identity_owners: dict[tuple[str, str], str] = {}
    for entity_index, raw in enumerate(
        _array(raw_entities, "$.entities", errors, nonempty=True)
    ):
        path = f"$.entities[{entity_index}]"
        entity = _schema_object(raw, ENTITY_FIELDS, path, errors)
        if entity is None:
            continue
        entity_id = _identifier(entity.get("id"), f"{path}.id", errors)
        _unique_id(entity_id, f"{path}.id", all_ids, errors)

        identities: list[dict[str, Any]] = []
        by_id: dict[str, dict[str, Any]] = {}
        for identity_index, identity_raw in enumerate(
            _array(
                entity.get("identities"), f"{path}.identities", errors, nonempty=True
            )
        ):
            identity = _validate_identity(
                identity_raw,
                f"{path}.identities[{identity_index}]",
                all_ids,
                errors,
            )
            if identity is not None:
                identities.append(identity)
                identity_id = identity["id"]
                if identity_id is not None and identity_id not in by_id:
                    by_id[identity_id] = identity

        current_ids = _string_array(
            entity.get("current_identity_ids"),
            f"{path}.current_identity_ids",
            errors,
            identifiers=True,
            nonempty=True,
        )
        declared_current = {
            item["id"]
            for item in identities
            if item["id"] is not None and item["status"] == "current"
        }
        if set(current_ids) != declared_current:
            _add(
                errors,
                "current_identity_mismatch",
                f"{path}.current_identity_ids",
                "must equal the identities whose status is current",
            )
        current_kinds: dict[str, str] = {}
        for current_index, identity_id in enumerate(current_ids):
            identity = by_id.get(identity_id)
            if identity is None:
                _add(
                    errors,
                    "dangling_identity_ref",
                    f"{path}.current_identity_ids",
                    f"identity {identity_id} does not exist in this entity",
                )
                continue
            kind = identity["kind"]
            if kind in current_kinds:
                _add(
                    errors,
                    "multiple_current_identities_per_kind",
                    f"{path}.current_identity_ids",
                    f"kind {kind} has more than one current identity",
                )
            elif kind is not None:
                current_kinds[kind] = identity_id
            value = identity["value"]
            if kind is not None and value is not None:
                identity_key = (kind, value)
                prior_path = current_identity_owners.get(identity_key)
                if prior_path is not None:
                    _add(
                        errors,
                        "duplicate_current_identity",
                        f"{path}.current_identity_ids[{current_index}]",
                        "current (kind, value) pair already belongs to "
                        f"{prior_path}",
                    )
                else:
                    current_identity_owners[identity_key] = (
                        f"{path}.current_identity_ids[{current_index}]"
                    )

        for identity_index, identity in enumerate(identities):
            identity_path = f"{path}.identities[{identity_index}]"
            _ref_kind_check(
                identity["source_ref_ids"],
                "identity",
                f"{identity_path}.source_ref_ids",
                source_refs,
                errors,
            )
            if identity["status"] != "superseded":
                continue
            successor = by_id.get(identity["superseded_by"])
            if successor is None or successor["id"] not in set(current_ids):
                _add(
                    errors,
                    "superseded_target_not_current",
                    f"{identity_path}.superseded_by",
                    "must reference a current identity in this entity",
                )
            elif successor["kind"] != identity["kind"]:
                _add(
                    errors,
                    "superseded_target_wrong_kind",
                    f"{identity_path}.superseded_by",
                    "replacement identity must have the same kind",
                )

        review = _validate_review(
            entity.get("source_review"), f"{path}.source_review", errors
        )
        proof = _validate_proof(
            entity.get("executable_proof"), f"{path}.executable_proof", errors
        )
        authority = _validate_authority(
            entity.get("authority"), f"{path}.authority", errors
        )
        confidence = _validate_confidence(
            entity.get("confidence"), f"{path}.confidence", errors
        )
        conflict = _validate_conflict(
            entity.get("conflict"), f"{path}.conflict", errors
        )
        current_set = set(current_ids)
        _identity_binding_check(
            review["identity_ids"],
            current_set,
            f"{path}.source_review.identity_ids",
            errors,
        )
        _identity_binding_check(
            proof["identity_ids"],
            current_set,
            f"{path}.executable_proof.identity_ids",
            errors,
        )
        _ref_kind_check(
            review["source_ref_ids"],
            "review",
            f"{path}.source_review.source_ref_ids",
            source_refs,
            errors,
        )
        _ref_kind_check(
            proof["source_ref_ids"],
            "executable_proof",
            f"{path}.executable_proof.source_ref_ids",
            source_refs,
            errors,
        )
        _ref_kind_check(
            authority["source_ref_ids"],
            "authority",
            f"{path}.authority.source_ref_ids",
            source_refs,
            errors,
        )
        _ref_kind_check(
            confidence["source_ref_ids"],
            "confidence",
            f"{path}.confidence.source_ref_ids",
            source_refs,
            errors,
        )
        _ref_kind_check(
            conflict["source_ref_ids"],
            "conflict",
            f"{path}.conflict.source_ref_ids",
            source_refs,
            errors,
        )
        review_origins = {
            source_refs[ref_id]["origin_id"]
            for ref_id in review["source_ref_ids"]
            if ref_id in source_refs and source_refs[ref_id]["origin_id"] is not None
        }
        proof_origins = {
            source_refs[ref_id]["origin_id"]
            for ref_id in proof["source_ref_ids"]
            if ref_id in source_refs and source_refs[ref_id]["origin_id"] is not None
        }
        if review_origins & proof_origins:
            _add(
                errors,
                "review_proof_not_independent",
                path,
                "source review and executable proof origins must be disjoint",
            )

        parsed = {
            "id": entity_id,
            "current_identity_ids": current_ids,
            "identity_count": len(identities),
            "authority": authority,
            "review": review,
            "proof": proof,
            "confidence": confidence,
            "conflict": conflict,
        }
        ordered.append(parsed)
        if entity_id is not None and entity_id not in entities:
            entities[entity_id] = parsed
    return entities, ordered


def _validate_stops(
    raw_stops: Any,
    entities: dict[str, dict[str, Any]],
    source_refs: dict[str, dict[str, Any]],
    all_ids: dict[str, str],
    errors: list[dict[str, str]],
) -> list[dict[str, Any]]:
    stops: list[dict[str, Any]] = []
    for index, raw in enumerate(_array(raw_stops, "$.stop_scopes", errors)):
        path = f"$.stop_scopes[{index}]"
        stop = _schema_object(raw, STOP_FIELDS, path, errors)
        if stop is None:
            continue
        stop_id = _identifier(stop.get("id"), f"{path}.id", errors)
        _unique_id(stop_id, f"{path}.id", all_ids, errors)
        status_value = _enum(
            stop.get("status"), STOP_STATUSES, f"{path}.status", errors
        )
        entity_ids = _string_array(
            stop.get("entity_ids"),
            f"{path}.entity_ids",
            errors,
            identifiers=True,
        )
        actions = _string_array(
            stop.get("actions"), f"{path}.actions", errors, actions=True
        )
        refs = _string_array(
            stop.get("source_ref_ids"),
            f"{path}.source_ref_ids",
            errors,
            identifiers=True,
        )
        for entity_index, entity_id in enumerate(entity_ids):
            if entity_id not in entities:
                _add(
                    errors,
                    "dangling_entity_ref",
                    f"{path}.entity_ids[{entity_index}]",
                    "entity does not exist",
                )
        _ref_kind_check(refs, "stop", f"{path}.source_ref_ids", source_refs, errors)
        if status_value == "active":
            if not entity_ids:
                _add(
                    errors,
                    "active_stop_missing_entities",
                    f"{path}.entity_ids",
                    "active stop must bind at least one entity",
                )
            if not actions:
                _add(
                    errors,
                    "active_stop_missing_actions",
                    f"{path}.actions",
                    "active stop must name at least one stopped action",
                )
            if not refs:
                _add(
                    errors,
                    "active_stop_missing_evidence",
                    f"{path}.source_ref_ids",
                    "active stop must reference stop evidence",
                )
        elif status_value == "inactive" and (entity_ids or actions or refs):
            _add(
                errors,
                "inactive_stop_has_effect",
                path,
                "inactive stop must have empty entity_ids, actions, and "
                "source_ref_ids",
            )
        stops.append(
            {
                "id": stop_id,
                "status": status_value,
                "entity_ids": entity_ids,
                "actions": actions,
                "source_ref_ids": refs,
            }
        )
    return stops


def _safe_companion_parts(path_text: str, path: str) -> tuple[str, ...]:
    if "\\" in path_text:
        raise InputProblem(
            "unsafe_companion_path",
            path,
            "companion path must use portable forward slashes",
        )
    if _contains_disallowed_text_character(path_text):
        raise InputProblem(
            "unsafe_companion_path",
            path,
            "companion path contains a disallowed or non-portable character",
        )
    relative = PurePosixPath(path_text)
    if relative.is_absolute() or not relative.parts:
        raise InputProblem(
            "unsafe_companion_path",
            path,
            "companion path must be relative",
        )
    if relative.as_posix() != path_text:
        raise InputProblem(
            "unsafe_companion_path",
            path,
            "companion path must use its canonical relative spelling",
        )
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise InputProblem(
            "unsafe_companion_path",
            path,
            "companion path must not contain empty, dot, or parent segments",
        )
    if relative.suffix.lower() != ".md":
        raise InputProblem(
            "unsafe_companion_path",
            path,
            "companion path must name a Markdown file",
        )
    return relative.parts


def _validate_companions(
    raw_companions: Any,
    base_descriptor: int,
    digest: str | None,
    errors: list[dict[str, str]],
) -> None:
    seen_paths: set[str] = set()
    seen_targets: dict[tuple[int, int], str] = {}
    for index, raw in enumerate(
        _array(raw_companions, "$.companions", errors, nonempty=True)
    ):
        path = f"$.companions[{index}]"
        companion = _schema_object(raw, COMPANION_FIELDS, path, errors)
        if companion is None:
            continue
        path_text = _string(companion.get("path"), f"{path}.path", errors)
        expected_hash = _string(companion.get("sha256"), f"{path}.sha256", errors)
        if expected_hash is not None and not SHA256_RE.fullmatch(expected_hash):
            _add(
                errors,
                "invalid_sha256",
                f"{path}.sha256",
                "must be a lower-case SHA-256 digest",
            )
        if path_text is None:
            continue
        if path_text in seen_paths:
            _add(
                errors,
                "duplicate_companion_path",
                f"{path}.path",
                "companion paths must be unique",
            )
        seen_paths.add(path_text)
        parts = _safe_companion_parts(path_text, f"{path}.path")
        try:
            raw_bytes, opened = _read_regular_beneath(
                base_descriptor,
                parts,
                MAX_COMPANION_BYTES,
            )
        except BoundedReadProblem as problem:
            if problem.kind == "symlink":
                raise InputProblem(
                    "unsafe_companion_symlink",
                    f"{path}.path",
                    "companion path must not traverse symlinks",
                ) from None
            if problem.kind == "changed":
                raise InputProblem(
                    "unsafe_companion_changed",
                    f"{path}.path",
                    "companion changed while it was read",
                ) from None
            if problem.kind == "unsupported":
                raise InputProblem(
                    "safe_traversal_unavailable",
                    f"{path}.path",
                    "safe descriptor-relative companion traversal is unavailable",
                ) from None
            if problem.kind == "unsafe_path":
                raise InputProblem(
                    "unsafe_companion_path",
                    f"{path}.path",
                    "companion path must traverse directories only",
                ) from None
            if problem.kind == "missing":
                _add(
                    errors,
                    "companion_missing",
                    f"{path}.path",
                    "companion file does not exist",
                )
            elif problem.kind == "not_regular":
                _add(
                    errors,
                    "companion_not_regular",
                    f"{path}.path",
                    "companion must be a regular file",
                )
            elif problem.kind == "too_large":
                _add(
                    errors,
                    "companion_too_large",
                    f"{path}.path",
                    f"companion exceeds {MAX_COMPANION_BYTES} bytes",
                )
            else:
                _add(
                    errors,
                    "companion_unreadable",
                    f"{path}.path",
                    "companion could not be read",
                )
            continue
        target_identity = (opened.st_dev, opened.st_ino)
        if target_identity in seen_targets:
            _add(
                errors,
                "duplicate_companion_target",
                f"{path}.path",
                f"duplicates target of {seen_targets[target_identity]}",
            )
        else:
            seen_targets[target_identity] = path_text
        actual_hash = hashlib.sha256(raw_bytes).hexdigest()
        if expected_hash is not None and actual_hash != expected_hash:
            _add(
                errors,
                "companion_hash_mismatch",
                f"{path}.sha256",
                "companion SHA-256 does not match",
            )
        try:
            markdown = raw_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            _add(
                errors,
                "companion_invalid_utf8",
                f"{path}.path",
                "companion is not valid UTF-8",
            )
            continue
        markers = MARKER_RE.findall(markdown)
        if markdown.count(MARKER_PREFIX) != 1 or len(markers) != 1:
            _add(
                errors,
                "companion_marker_count",
                f"{path}.path",
                "companion must contain exactly one state-commitment marker",
            )
        elif digest is not None and markers[0] != digest:
            _add(
                errors,
                "companion_marker_mismatch",
                f"{path}.path",
                "companion marker does not match commitment_digest",
            )


def _entity_results(
    ordered_entities: list[dict[str, Any]],
    stops: list[dict[str, Any]],
    *,
    valid: bool,
) -> list[dict[str, Any]]:
    results = []
    for entity in ordered_entities:
        entity_id = entity["id"]
        authorized = sorted(set(entity["authority"]["actions"]))
        applicable = [
            stop
            for stop in stops
            if stop["status"] == "active" and entity_id in stop["entity_ids"]
        ]
        stopped = sorted({action for stop in applicable for action in stop["actions"]})
        evidence = sorted(
            {ref_id for stop in applicable for ref_id in stop["source_ref_ids"]}
        )
        blockers = []
        if entity["authority"]["mode"] != "scoped_write":
            blockers.append(f"authority:{entity['authority']['mode']}")
        if entity["conflict"]["status"] == "unresolved":
            blockers.append("conflict:unresolved")
        blockers.extend(f"active_stop:{stop['id']}" for stop in applicable)
        effective = sorted(set(authorized) - set(stopped))
        fail_closed = (
            entity["authority"]["mode"] in {"read_only", "unknown"}
            or entity["conflict"]["status"] == "unresolved"
        )
        if fail_closed or not valid:
            effective = []
        evidence_refs = sorted(
            {
                ref_id
                for group in (
                    entity["review"]["source_ref_ids"],
                    entity["proof"]["source_ref_ids"],
                    entity["authority"]["source_ref_ids"],
                    entity["confidence"]["source_ref_ids"],
                    entity["conflict"]["source_ref_ids"],
                    evidence,
                )
                for ref_id in group
            }
        )
        results.append(
            {
                "id": entity_id,
                "has_effective_authority": bool(effective) and valid,
                "blockers": sorted(blockers),
                "current_identity_ids": sorted(entity["current_identity_ids"]),
                "source_review_status": entity["review"]["status"],
                "executable_proof_status": entity["proof"]["status"],
                "execution_count": entity["proof"]["execution_count"],
                "authority_mode": entity["authority"]["mode"],
                "authorized_actions": authorized,
                "stopped_actions": stopped,
                "effective_actions": effective,
                "confidence_level": entity["confidence"]["level"],
                "conflict_status": entity["conflict"]["status"],
                "fallback": entity["conflict"]["fallback"],
                "evidence_ref_ids": evidence_refs,
            }
        )
    return sorted(results, key=lambda item: item["id"] or "")


def validate_bundle(
    bundle: dict[str, Any],
    companion_base_descriptor: int,
) -> tuple[dict[str, Any], int]:
    """Validate a decoded bundle and return a deterministic result and exit."""
    errors: list[dict[str, str]] = []
    top = _schema_object(bundle, TOP_FIELDS, "$", errors)
    if top is None:
        return _validation_payload(errors, []), 2

    schema = _string(bundle.get("schema"), "$.schema", errors)
    if schema is not None and schema != STATE_SCHEMA:
        _add(
            errors,
            "wrong_schema",
            "$.schema",
            f"must equal {STATE_SCHEMA}",
        )
    state_version = bundle.get("state_version")
    if (
        isinstance(state_version, bool)
        or not isinstance(state_version, int)
        or state_version < 1
    ):
        _add(
            errors,
            "invalid_state_version",
            "$.state_version",
            "must be an integer greater than zero",
        )
    cutoff = _utc(bundle.get("cutoff_utc"), "$.cutoff_utc", errors)
    declared_digest = _string(
        bundle.get("commitment_digest"), "$.commitment_digest", errors
    )
    if declared_digest is not None and not SHA256_RE.fullmatch(declared_digest):
        _add(
            errors,
            "invalid_sha256",
            "$.commitment_digest",
            "must be a lower-case SHA-256 digest",
        )

    all_ids: dict[str, str] = {}
    source_refs = _validate_source_refs(
        bundle.get("source_refs"), cutoff, all_ids, errors
    )
    entities, ordered_entities = _validate_entities(
        bundle.get("entities"), source_refs, all_ids, errors
    )
    stops = _validate_stops(
        bundle.get("stop_scopes"), entities, source_refs, all_ids, errors
    )
    computed_digest = compute_digest(bundle)
    if declared_digest is not None and declared_digest != computed_digest:
        _add(
            errors,
            "commitment_digest_mismatch",
            "$.commitment_digest",
            "commitment_digest does not match canonical core",
        )
    _validate_companions(
        bundle.get("companions"),
        companion_base_descriptor,
        declared_digest,
        errors,
    )
    input_errors = [error for error in errors if error["code"] in INPUT_ERROR_CODES]
    if input_errors:
        first = sorted(
            input_errors,
            key=lambda item: (item["path"], item["code"], item["message"]),
        )[0]
        return _error_payload(
            InputProblem(first["code"], first["path"], first["message"])
        ), 1
    results = _entity_results(ordered_entities, stops, valid=not errors)
    snapshot_digest = compute_snapshot_digest(computed_digest, bundle["companions"])
    metadata = {
        "state_version": state_version,
        "cutoff_utc": bundle.get("cutoff_utc"),
        "commitment_digest": computed_digest,
        "snapshot_digest": snapshot_digest,
        "counts": {
            "entities": len(ordered_entities),
            "identities": sum(entity["identity_count"] for entity in ordered_entities),
            "source_refs": len(source_refs),
            "companions": (
                len(bundle.get("companions"))
                if isinstance(bundle.get("companions"), list)
                else 0
            ),
        },
        "active_stop_scope_ids": sorted(
            stop["id"]
            for stop in stops
            if stop["status"] == "active" and stop["id"] is not None
        ),
    }
    return (
        _validation_payload(errors, results, metadata=metadata),
        2 if errors else 0,
    )


def _validation_payload(
    errors: list[dict[str, str]],
    entities: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": VALIDATION_SCHEMA,
        "status": "fail" if errors else "pass",
        "valid": not errors,
        "errors": sorted(
            errors,
            key=lambda item: (item["path"], item["code"], item["message"]),
        ),
        "entities": entities,
    }
    if metadata is not None:
        payload.update(metadata)
    return payload


def _parse_cli(argv: list[str]) -> str:
    if len(argv) == 3 and argv[0] == "validate" and argv[1] == "--input":
        if argv[2]:
            return argv[2]
    if len(argv) == 2 and argv[0] == "validate" and argv[1].startswith("--input="):
        value = argv[1].split("=", 1)[1]
        if value:
            return value
    raise InputProblem(
        "invalid_arguments",
        "$",
        "usage: state_commitment_guard.py validate --input FILE",
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    companion_base_descriptor: int | None = None
    try:
        input_path = _parse_cli(args)
        bundle, companion_base_descriptor = _load_input(input_path)
        payload, exit_code = validate_bundle(bundle, companion_base_descriptor)
    except InputProblem as problem:
        payload = _error_payload(problem)
        exit_code = 1
    except (OSError, RecursionError, ValueError):
        payload = _error_payload(
            InputProblem("input_error", "$", "input validation could not complete")
        )
        exit_code = 1
    finally:
        if companion_base_descriptor is not None:
            os.close(companion_base_descriptor)
    sys.stdout.write(_json_line(payload) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
