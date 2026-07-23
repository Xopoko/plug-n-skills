#!/usr/bin/env python3
"""Build and validate read-only, fail-closed GitLab review evidence."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, NoReturn
from urllib.parse import urlsplit


SNAPSHOT_SCHEMA = "gitlab_review_guard.snapshot.v2"
COMPARE_SCHEMA = "gitlab_review_guard.compare.v2"
HEAD_SCHEMA = "gitlab_review_guard.exact_head.v2"
PLAN_SCHEMA = "gitlab_review_guard.plan_validation.v2"
ERROR_SCHEMA = "gitlab_review_guard.error.v2"
PLAN_INPUT_SCHEMA = "gitlab_review_guard.plan.v2"
DEDUPE_SCHEMA = "gitlab_review_guard.reply_dedupe.v2"
BODY_HASH_SCHEMA = "gitlab_review_guard.body_hash.v2"
DEDUPE_OUTPUT_SCHEMA = "gitlab_review_guard.dedupe_key.v2"

SUCCESS_PIPELINE_STATUSES = {"success"}
AUTHORIZATION_SOURCES = {"user", "repository-policy"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
RESPONSE_MARKER_RE = re.compile(
    r"<!--\s*gitlab-review-response:v2:([0-9a-f]{64})\s*-->"
)

MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_PAGES = 1_000
MAX_DISCUSSIONS = 10_000
MAX_NOTES = 50_000
MAX_PIPELINES = 5_000
MAX_ACTIONS = 100


class GuardError(ValueError):
    """Raised for malformed or structurally incomplete local input."""


class JsonArgumentParser(argparse.ArgumentParser):
    """Convert argparse usage failures into the guard's JSON error contract."""

    def error(self, message: str) -> NoReturn:
        raise GuardError("argument error: " + message)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def stable_hash(value: Any) -> str:
    """Return a deterministic SHA-256 digest for a JSON-compatible value."""

    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _as_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _nonempty_string(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    return value


def _as_bool(value: Any) -> bool:
    return value is True


def _normalized_body(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _valid_sha(value: Any) -> bool:
    return bool(GIT_SHA_RE.fullmatch(_as_id(value)))


def _normalize_sha(value: Any) -> str:
    text = _as_id(value)
    return text.lower() if _valid_sha(text) else ""


def _positive_id(value: Any) -> str:
    text = _as_id(value)
    if not text.isdecimal() or int(text) <= 0:
        return ""
    return str(int(text))


def _valid_sha256(value: Any) -> bool:
    return bool(SHA256_RE.fullmatch(_as_id(value)))


def _normalize_host(value: Any) -> str:
    raw = _as_id(value).strip().lower()
    if not raw:
        raise GuardError("host must not be empty")
    try:
        parsed = urlsplit(raw if "://" in raw else "//" + raw)
    except ValueError as exc:
        raise GuardError("host is malformed") from exc
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        raise GuardError("host scheme must be http or https")
    if parsed.username or parsed.password:
        raise GuardError("host must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise GuardError("host must not contain a path, query, or fragment")
    try:
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise GuardError("host is malformed") from exc
    if not hostname:
        raise GuardError("host is not a valid explicit hostname")
    hostname = hostname.rstrip(".")
    if ":" in hostname:
        try:
            ipaddress.IPv6Address(hostname)
        except ipaddress.AddressValueError as exc:
            raise GuardError("host contains an invalid IPv6 address") from exc
        normalized_host = "[" + hostname + "]"
    else:
        if len(hostname) > 253 or any(
            not DNS_LABEL_RE.fullmatch(label)
            for label in hostname.split(".")
        ):
            raise GuardError("host contains an invalid DNS label")
        normalized_host = hostname
    if port is not None:
        normalized_host += ":" + str(port)
    return normalized_host


def _read_text(path: str) -> str:
    if path == "-":
        text = sys.stdin.read(MAX_INPUT_BYTES + 1)
        if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
            raise GuardError("stdin exceeds the input size limit")
        return text
    file_path = Path(path)
    if file_path.stat().st_size > MAX_INPUT_BYTES:
        raise GuardError(f"input file exceeds the size limit: {file_path.name}")
    return file_path.read_text(encoding="utf-8")


def load_json_file(path: str, label: str) -> Any:
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise GuardError(f"invalid {label} JSON: {exc.msg}") from exc


def _parse_json_or_ndjson(text: str, label: str) -> tuple[Any, str]:
    stripped = text.strip()
    if not stripped:
        raise GuardError(f"{label} input is empty")
    try:
        return json.loads(stripped), "json"
    except json.JSONDecodeError:
        records: list[Any] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            if len(records) >= MAX_PAGES + MAX_DISCUSSIONS:
                raise GuardError(f"{label} NDJSON record limit exceeded")
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise GuardError(
                    f"invalid {label} NDJSON on line {line_number}: {exc.msg}"
                ) from exc
        if not records:
            raise GuardError(f"{label} NDJSON input is empty")
        return records, "ndjson"


def _value_from_layers(value: dict[str, Any], key: str) -> tuple[bool, Any]:
    pagination = value.get("pagination")
    if "pagination" in value and not isinstance(pagination, dict):
        raise GuardError("pagination metadata must be an object")
    pagination_map = pagination if isinstance(pagination, dict) else {}
    top_present = key in value
    nested_present = key in pagination_map
    if top_present and nested_present:
        top_value = value.get(key)
        nested_value = pagination_map.get(key)
        if top_value != nested_value or type(top_value) is not type(nested_value):
            raise GuardError(
                f"conflicting top-level and pagination values for {key!r}"
            )
        return True, top_value
    if top_present:
        return True, value.get(key)
    if nested_present:
        return True, pagination_map.get(key)
    return False, None


def _page_number(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.isdecimal():
        number = int(value)
    else:
        return None
    return number if number > 0 else None


def _terminal_next(value: Any) -> bool:
    return value is None or value is False or _as_id(value).strip() in {"", "0"}


def _page_items(
    value: dict[str, Any], keys: tuple[str, ...], label: str
) -> list[Any]:
    present = [key for key in keys if key in value]
    if len(present) != 1:
        raise GuardError(
            f"{label} page must contain exactly one of {', '.join(keys)}"
        )
    items = value.get(present[0])
    if not isinstance(items, list):
        raise GuardError(f"{label} page field {present[0]!r} must be an array")
    return items


def _collect_strict_pages(
    raw_pages: list[Any],
    *,
    item_keys: tuple[str, ...],
    label: str,
    source_format: str,
    declared_complete: bool | None,
    item_limit: int,
) -> dict[str, Any]:
    if not raw_pages:
        raise GuardError(f"{label} page collection is empty")
    if len(raw_pages) > MAX_PAGES:
        raise GuardError(f"{label} page limit exceeded")

    records: list[Any] = []
    pages: list[dict[str, Any]] = []
    reasons: list[str] = []
    for index, raw_page in enumerate(raw_pages, 1):
        if not isinstance(raw_page, dict):
            raise GuardError(f"{label} pages must be objects")
        if "pagination" in raw_page and not isinstance(
            raw_page.get("pagination"), dict
        ):
            raise GuardError(f"{label} page pagination must be an object")
        items = _page_items(raw_page, item_keys, label)
        if len(records) + len(items) > item_limit:
            raise GuardError(f"{label} record limit exceeded")
        records.extend(items)

        has_current, current_raw = _value_from_layers(
            raw_page, "current_page"
        )
        has_page_alias, page_alias_raw = _value_from_layers(raw_page, "page")
        if has_current and has_page_alias:
            if (
                _page_number(current_raw) is None
                or _page_number(current_raw) != _page_number(page_alias_raw)
            ):
                raise GuardError(
                    f"{label} page has conflicting current-page aliases"
                )
        elif has_page_alias:
            has_current, current_raw = True, page_alias_raw
        current = _page_number(current_raw)
        if not has_current:
            current = index
        elif current is None:
            reasons.append("invalid_current_page")

        has_next, next_raw = _value_from_layers(raw_page, "next_page")
        next_page = None if _terminal_next(next_raw) else _page_number(next_raw)
        if has_next and not _terminal_next(next_raw) and next_page is None:
            reasons.append("invalid_next_page")

        has_total, total_raw = _value_from_layers(raw_page, "total_pages")
        total_pages = _page_number(total_raw)
        if has_total and total_pages is None:
            reasons.append("invalid_total_pages")

        has_complete, complete_raw = _value_from_layers(raw_page, "complete")
        if has_complete and not isinstance(complete_raw, bool):
            reasons.append("invalid_page_complete")

        pages.append(
            {
                "index": index,
                "current_page": current,
                "has_current": has_current,
                "next_page": next_page,
                "has_next": has_next,
                "next_terminal": has_next and _terminal_next(next_raw),
                "total_pages": total_pages,
                "has_total": has_total,
                "complete": complete_raw if isinstance(complete_raw, bool) else None,
                "item_count": len(items),
            }
        )

    expected_order = list(range(1, len(pages) + 1))
    actual_order = [page["current_page"] for page in pages]
    if actual_order != expected_order:
        reasons.append("page_order_or_coverage_invalid")
    implicit_single_page = (
        len(pages) == 1
        and (
            declared_complete is True
            or pages[0]["complete"] is True
        )
    )
    if any(not page["has_current"] for page in pages) and not implicit_single_page:
        reasons.append("current_page_missing")

    next_claims = [page for page in pages if page["has_next"]]
    terminal_pages = [
        page["current_page"] for page in pages if page["next_terminal"]
    ]
    if terminal_pages:
        if len(terminal_pages) != 1:
            reasons.append("multiple_terminal_pages")
        if any(page != len(pages) for page in terminal_pages):
            reasons.append("terminal_before_last_page")
    for page in pages:
        current = page["current_page"]
        if page["has_next"] and not page["next_terminal"]:
            if current is None or page["next_page"] != current + 1:
                reasons.append("non_sequential_next_page")
            if page["next_page"] not in expected_order:
                reasons.append("missing_next_page")
        elif not page["has_next"] and len(pages) > 1 and not page["has_total"]:
            reasons.append("next_page_missing")

    total_claims = [page["total_pages"] for page in pages if page["has_total"]]
    if total_claims:
        if len(total_claims) != len(pages):
            reasons.append("partial_total_pages")
        if len(set(total_claims)) != 1:
            reasons.append("conflicting_total_pages")
        elif total_claims[0] != len(pages):
            reasons.append("total_pages_not_fully_fetched")

    complete_pages = [
        page["current_page"] for page in pages if page["complete"] is True
    ]
    incomplete_pages = [
        page["current_page"] for page in pages if page["complete"] is False
    ]
    if incomplete_pages:
        reasons.append("page_marked_incomplete")
    if complete_pages:
        if len(complete_pages) != 1:
            reasons.append("multiple_complete_pages")
        if complete_pages[-1] != len(pages):
            reasons.append("complete_before_last_page")

    if declared_complete is False:
        reasons.append("collection_marked_incomplete")

    next_evidence = (
        len(next_claims) == len(pages)
        and len(terminal_pages) == 1
        and terminal_pages[-1] == len(pages)
    )
    total_evidence = (
        len(total_claims) == len(pages)
        and len(set(total_claims)) == 1
        and total_claims[0] == len(pages)
    )
    page_evidence = (
        len(complete_pages) == 1 and complete_pages[-1] == len(pages)
    )
    top_level_single_page_evidence = declared_complete is True and len(pages) == 1
    completion_evidence = (
        next_evidence
        or total_evidence
        or page_evidence
        or top_level_single_page_evidence
    )
    if not completion_evidence:
        reasons.append("pagination_completion_not_proven")

    reasons = sorted(set(reasons))
    return {
        "records": records,
        "pagination": {
            "source_format": source_format,
            "page_count": len(pages),
            "record_count": len(records),
            "complete": not reasons,
            "completion_basis": sorted(
                basis
                for basis, proven in (
                    ("next_page_terminal", next_evidence),
                    ("total_pages", total_evidence),
                    ("page_complete", page_evidence),
                    ("top_level_complete_single_page", top_level_single_page_evidence),
                )
                if proven
            ),
            "reasons": reasons,
            "pages": [
                {
                    "current_page": page["current_page"],
                    "item_count": page["item_count"],
                    "next_page": page["next_page"],
                    "terminal": page["next_terminal"],
                    "total_pages": page["total_pages"],
                    "complete": page["complete"],
                }
                for page in pages
            ],
        },
    }


def _raw_collection(
    records: list[Any],
    *,
    label: str,
    source_format: str,
    assume_complete: bool,
    item_limit: int,
) -> dict[str, Any]:
    if len(records) > item_limit:
        raise GuardError(f"{label} record limit exceeded")
    reasons = [] if assume_complete else ["caller_completeness_declaration_missing"]
    return {
        "records": records,
        "pagination": {
            "source_format": source_format,
            "page_count": 1,
            "record_count": len(records),
            "complete": assume_complete,
            "completion_basis": (
                ["caller_declared_complete_raw_collection"]
                if assume_complete
                else []
            ),
            "reasons": reasons,
            "pages": [
                {
                    "current_page": None,
                    "item_count": len(records),
                    "next_page": None,
                    "terminal": False,
                    "total_pages": None,
                    "complete": None,
                }
            ],
        },
    }


def _is_discussion(value: Any) -> bool:
    return isinstance(value, dict) and "id" in value and isinstance(
        value.get("notes"), list
    )


def _is_pipeline(value: Any) -> bool:
    return isinstance(value, dict) and any(
        key in value for key in ("id", "pipeline_id")
    ) and any(key in value for key in ("sha", "head_sha", "source_sha"))


def _reject_direct_collection_mix(
    value: dict[str, Any], *, label: str
) -> None:
    collection_fields = {
        "complete",
        "current_page",
        "data",
        "discussions",
        "items",
        "next_page",
        "page",
        "pages",
        "pagination",
        "pipelines",
        "total_pages",
    }
    if collection_fields & set(value):
        raise GuardError(
            f"{label} input must not mix direct record and collection fields"
        )


def parse_discussions_text(
    text: str, *, assume_complete_array: bool = False
) -> dict[str, Any]:
    """Parse discussions without inferring completeness from a raw array."""

    value, source = _parse_json_or_ndjson(text, "discussion")
    if source == "ndjson":
        assert isinstance(value, list)
        if all(_is_discussion(record) for record in value):
            for record in value:
                _reject_direct_collection_mix(record, label="discussion")
            return _raw_collection(
                value,
                label="discussion",
                source_format="ndjson-discussions",
                assume_complete=assume_complete_array,
                item_limit=MAX_DISCUSSIONS,
            )
        sentinels = [
            index
            for index, record in enumerate(value)
            if isinstance(record, dict)
            and set(record) <= {"complete", "pagination"}
            and _value_from_layers(record, "complete")[0]
            and not any(key in record for key in ("discussions", "items", "data"))
        ]
        if len(sentinels) > 1:
            raise GuardError("discussion NDJSON contains multiple completion sentinels")
        ndjson_declared_complete: bool | None = None
        if sentinels:
            if sentinels[0] != len(value) - 1:
                raise GuardError("discussion completion sentinel must be last")
            sentinel = value.pop()
            _, complete = _value_from_layers(sentinel, "complete")
            if not isinstance(complete, bool):
                raise GuardError("discussion completion sentinel must be boolean")
            sentinel_pagination = sentinel.get("pagination")
            if isinstance(sentinel_pagination, dict) and (
                set(sentinel_pagination) - {"complete"}
            ):
                raise GuardError(
                    "discussion completion sentinel contains page metadata"
                )
            ndjson_declared_complete = complete
        if not value:
            raise GuardError("discussion NDJSON contains no pages")
        return _collect_strict_pages(
            value,
            item_keys=("discussions", "items", "data"),
            label="discussion",
            source_format="ndjson-pages",
            declared_complete=ndjson_declared_complete,
            item_limit=MAX_DISCUSSIONS,
        )

    if isinstance(value, list):
        if all(_is_discussion(item) for item in value):
            for item in value:
                _reject_direct_collection_mix(item, label="discussion")
            return _raw_collection(
                value,
                label="discussion",
                source_format="json-array",
                assume_complete=assume_complete_array,
                item_limit=MAX_DISCUSSIONS,
            )
        return _collect_strict_pages(
            value,
            item_keys=("discussions", "items", "data"),
            label="discussion",
            source_format="json-pages",
            declared_complete=None,
            item_limit=MAX_DISCUSSIONS,
        )
    if not isinstance(value, dict):
        raise GuardError("discussion JSON must be an array or object")
    if _is_discussion(value):
        _reject_direct_collection_mix(value, label="discussion")
        return _raw_collection(
            [value],
            label="discussion",
            source_format="json-single-discussion",
            assume_complete=assume_complete_array,
            item_limit=MAX_DISCUSSIONS,
        )

    declared_complete: bool | None = None
    has_complete, complete_value = _value_from_layers(value, "complete")
    if has_complete:
        if not isinstance(complete_value, bool):
            raise GuardError("discussion top-level complete must be boolean")
        declared_complete = complete_value
    pages = value.get("pages")
    if pages is not None:
        if not isinstance(pages, list):
            raise GuardError("discussion pages must be an array")
        if any(key in value for key in ("discussions", "items", "data")):
            raise GuardError(
                "discussion pages envelope must not contain a top-level collection"
            )
        if any(
            _value_from_layers(value, key)[0]
            for key in ("page", "current_page", "next_page", "total_pages")
        ):
            raise GuardError(
                "discussion pages envelope contains page-level metadata"
            )
        return _collect_strict_pages(
            pages,
            item_keys=("discussions", "items", "data"),
            label="discussion",
            source_format="json-pages-envelope",
            declared_complete=declared_complete,
            item_limit=MAX_DISCUSSIONS,
        )
    return _collect_strict_pages(
        [value],
        item_keys=("discussions", "items", "data"),
        label="discussion",
        source_format="json-envelope",
        declared_complete=declared_complete,
        item_limit=MAX_DISCUSSIONS,
    )


def load_discussions_file(
    path: str, *, assume_complete_array: bool = False
) -> dict[str, Any]:
    return parse_discussions_text(
        _read_text(path), assume_complete_array=assume_complete_array
    )


def _require_string(
    value: dict[str, Any], key: str, context: str, *, allow_empty: bool = False
) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or (not allow_empty and not raw):
        raise GuardError(f"{context} requires string field {key!r}")
    return raw


def _require_bool(value: dict[str, Any], key: str, context: str) -> bool:
    raw = value.get(key)
    if not isinstance(raw, bool):
        raise GuardError(f"{context} requires boolean field {key!r}")
    return raw


def _actor_id_hash(value: Any, context: str) -> str:
    if not isinstance(value, dict):
        raise GuardError(f"{context} author must be an object")
    actor_id = _positive_id(value.get("id"))
    if not actor_id:
        raise GuardError(f"{context} author requires a positive numeric id")
    return stable_hash(actor_id)


def _response_marker_evidence(body: str) -> tuple[list[str], list[dict[str, str]]]:
    normalized = _normalized_body(body)
    matches = list(RESPONSE_MARKER_RE.finditer(normalized))
    response_keys = sorted(match.group(1) for match in matches)
    bindings: list[dict[str, str]] = []
    if len(matches) == 1:
        match = matches[0]
        response_key = match.group(1)
        exact_marker = (
            "<!-- gitlab-review-response:v2:" + response_key + " -->"
        )
        if (
            match.group(0) == exact_marker
            and match.end() == len(normalized)
            and match.start() >= 2
            and normalized[match.start() - 2 : match.start()] == "\n\n"
        ):
            bindings.append(
                {
                    "response_key": response_key,
                    "response_hash": stable_hash(
                        normalized[: match.start() - 2]
                    ),
                }
            )
    return response_keys, bindings


def _normalize_note(note: dict[str, Any], discussion_id: str) -> dict[str, Any]:
    context = f"discussion {discussion_id!r} note"
    note_id = _positive_id(note.get("id"))
    if not note_id:
        raise GuardError(f"{context} requires a positive numeric id")
    body = _require_string(note, "body", context, allow_empty=True)
    note_type_raw = note.get("type")
    if note_type_raw is not None and not isinstance(note_type_raw, str):
        raise GuardError(f"{context} field 'type' must be a string or null")
    note_type = _as_id(note_type_raw)
    author_id_hash = _actor_id_hash(note.get("author"), context)
    created_at = _require_string(note, "created_at", context)
    updated_at = _require_string(note, "updated_at", context)
    system = _require_bool(note, "system", context)
    resolvable = _require_bool(note, "resolvable", context)
    resolved: bool | None = None
    if resolvable or note_type == "DiffNote":
        resolved = _require_bool(note, "resolved", context)
    elif "resolved" in note:
        resolved = _require_bool(note, "resolved", context)

    position = note.get("position")
    if note_type == "DiffNote":
        if not isinstance(position, dict):
            raise GuardError(f"{context} DiffNote requires a position object")
        _require_string(position, "position_type", context + " position")
        for sha_key in ("base_sha", "head_sha"):
            if not _valid_sha(position.get(sha_key)):
                raise GuardError(
                    f"{context} position requires exact Git SHA field {sha_key!r}"
                )
        if not any(
            isinstance(position.get(key), str) and position.get(key)
            for key in ("new_path", "old_path")
        ):
            raise GuardError(f"{context} position requires a file path")
    elif position is not None and not isinstance(position, dict):
        raise GuardError(f"{context} position must be an object or null")

    state = {
        "confidential": (
            _require_bool(note, "confidential", context)
            if "confidential" in note
            else False
        ),
        "created_at": created_at,
        "internal": (
            _require_bool(note, "internal", context)
            if "internal" in note
            else False
        ),
        "resolvable": resolvable,
        "resolved": resolved,
        "resolved_by_id_hash": (
            _actor_id_hash(note.get("resolved_by"), context + " resolved_by")
            if note.get("resolved_by") is not None
            else ""
        ),
        "system": system,
        "type": note_type,
        "updated_at": updated_at,
    }
    body_hash = stable_hash(_normalized_body(body))
    response_keys, response_bindings = _response_marker_evidence(body)
    response_bindings_hash = stable_hash(response_bindings)
    response_keys_hash = stable_hash(response_keys)
    position_hash = stable_hash(position)
    resolution_hash = stable_hash(
        {
            "resolvable": resolvable,
            "resolved": resolved,
            "type": note_type,
        }
    )
    state_hash = stable_hash(state)
    identity_hash = stable_hash(
        {
            "discussion_id": discussion_id,
            "note_id": note_id,
            "author_id_hash": author_id_hash,
            "system": system,
            "type": note_type,
        }
    )
    fingerprint = stable_hash(
        {
            "body_hash": body_hash,
            "identity_hash": identity_hash,
            "position_hash": position_hash,
            "response_bindings_hash": response_bindings_hash,
            "response_keys_hash": response_keys_hash,
            "resolution_hash": resolution_hash,
            "state_hash": state_hash,
        }
    )
    return {
        "id": note_id,
        "author_id_hash": author_id_hash,
        "body_hash": body_hash,
        "identity_hash": identity_hash,
        "position_hash": position_hash,
        "response_bindings": response_bindings,
        "response_bindings_hash": response_bindings_hash,
        "response_keys": response_keys,
        "response_keys_hash": response_keys_hash,
        "resolution_hash": resolution_hash,
        "state_hash": state_hash,
        "fingerprint": fingerprint,
        "resolvable": resolvable,
        "resolved": resolved,
        "system": system,
        "type": note_type,
    }


def _normalize_discussion(discussion: dict[str, Any]) -> dict[str, Any]:
    discussion_id = _nonempty_string(discussion.get("id"))
    if not discussion_id:
        raise GuardError("discussion record requires a non-empty string id")
    if "individual_note" in discussion and not isinstance(
        discussion.get("individual_note"), bool
    ):
        raise GuardError(
            f"discussion {discussion_id!r} individual_note must be boolean"
        )
    raw_notes = discussion.get("notes")
    if not isinstance(raw_notes, list) or not raw_notes:
        raise GuardError(f"discussion {discussion_id!r} requires a non-empty notes array")
    if len(raw_notes) > MAX_NOTES:
        raise GuardError(f"discussion {discussion_id!r} note limit exceeded")

    notes: list[dict[str, Any]] = []
    for raw_note in raw_notes:
        if not isinstance(raw_note, dict):
            raise GuardError(f"discussion {discussion_id!r} contains a non-object note")
        notes.append(_normalize_note(raw_note, discussion_id))
    notes.sort(key=lambda item: item["id"])

    resolvable = [note for note in notes if note["resolvable"]]
    if "resolved" in discussion:
        resolved = _require_bool(discussion, "resolved", f"discussion {discussion_id!r}")
        if resolvable and resolved is not all(
            note["resolved"] is True for note in resolvable
        ):
            raise GuardError(
                f"discussion {discussion_id!r} resolved state conflicts with notes"
            )
    elif resolvable:
        resolved = all(note["resolved"] is True for note in resolvable)
    else:
        resolved = None
    state_hash = stable_hash(
        {
            "id": discussion_id,
            "individual_note": _as_bool(discussion.get("individual_note")),
            "resolved": resolved,
        }
    )
    resolution_hash = stable_hash({"resolved": resolved})
    digest = stable_hash(
        {
            "id": discussion_id,
            "notes": [
                {"id": note["id"], "fingerprint": note["fingerprint"]}
                for note in notes
            ],
            "resolution_hash": resolution_hash,
            "state_hash": state_hash,
        }
    )
    return {
        "id": discussion_id,
        "resolved": resolved,
        "resolution_hash": resolution_hash,
        "state_hash": state_hash,
        "digest": digest,
        "note_count": len(notes),
        "notes": notes,
    }


def _unwrap_mr(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and "merge_request" in value:
        nested = value.get("merge_request")
        if not isinstance(nested, dict):
            raise GuardError("merge_request wrapper must contain an object")
        direct_fields = {
            "id",
            "iid",
            "project_id",
            "source_project_id",
            "target_project_id",
            "state",
            "source_branch",
            "target_branch",
            "sha",
            "head_sha",
            "diff_refs",
            "head_pipeline",
        }
        if direct_fields & set(value):
            raise GuardError(
                "merge request input must not mix wrapper and direct fields"
            )
        value = nested
    if not isinstance(value, dict):
        raise GuardError("merge request JSON must be an object")
    return value


def _normalized_alias(
    value: dict[str, Any],
    keys: tuple[str, ...],
    normalizer: Any,
    label: str,
) -> str:
    normalized: list[tuple[str, str]] = []
    for key in keys:
        raw = value.get(key)
        if raw is None or raw == "":
            continue
        item = normalizer(raw)
        if not item:
            raise GuardError(f"{label} field {key} is invalid")
        normalized.append((key, item))
    variants = {item for _key, item in normalized}
    if len(variants) > 1:
        raise GuardError(f"{label} aliases conflict")
    return normalized[0][1] if normalized else ""


def _pipeline_status(pipeline: dict[str, Any]) -> str:
    status = pipeline.get("status")
    if status is not None and not isinstance(status, str):
        raise GuardError("pipeline status must be a string or null")
    if isinstance(status, str) and status.strip():
        return status.strip().lower().replace("-", "_").replace(" ", "_")
    detailed = pipeline.get("detailed_status")
    if detailed is None:
        return ""
    if not isinstance(detailed, dict):
        raise GuardError("pipeline detailed_status must be an object or null")
    for key in ("group", "label"):
        item = detailed.get(key)
        if item is not None and not isinstance(item, str):
            raise GuardError(
                f"pipeline detailed_status {key} must be a string or null"
            )
        if isinstance(item, str) and item.strip():
            return item.strip().lower().replace("-", "_").replace(" ", "_")
    return ""


def _normalize_pipeline(pipeline: dict[str, Any]) -> dict[str, str]:
    pipeline_id = _normalized_alias(
        pipeline,
        ("id", "pipeline_id"),
        _positive_id,
        "pipeline id",
    )
    sha = _normalized_alias(
        pipeline,
        ("sha", "head_sha", "source_sha"),
        _normalize_sha,
        "pipeline sha",
    )
    status = _pipeline_status(pipeline)
    source = pipeline.get("source")
    if source is not None and not isinstance(source, str):
        raise GuardError("pipeline source must be a string or null")
    if not pipeline_id:
        pipeline_id = "invalid-" + stable_hash(pipeline)[:16]
    return {
        "id": pipeline_id,
        "sha": sha,
        "status": status,
        "source": source or "",
    }


def _normalize_mr(value: Any) -> tuple[dict[str, Any], list[str]]:
    mr = _unwrap_mr(value)
    reasons: list[str] = []
    for key in ("state", "source_branch", "target_branch"):
        if key in mr and mr.get(key) is not None and not isinstance(
            mr.get(key), str
        ):
            raise GuardError(f"merge request {key} must be a string")
    diff_refs_raw = mr.get("diff_refs")
    diff_refs = diff_refs_raw if isinstance(diff_refs_raw, dict) else {}
    direct_head = _normalized_alias(
        mr,
        ("sha", "head_sha"),
        _normalize_sha,
        "merge request head",
    )
    diff_head = _normalize_sha(diff_refs.get("head_sha"))
    head_sha = direct_head or diff_head
    if not direct_head:
        reasons.append("mr_head_missing_or_invalid")
    if not diff_head:
        reasons.append("diff_head_missing_or_invalid")
    if direct_head and diff_head and direct_head != diff_head:
        reasons.append("mr_head_diff_ref_mismatch")

    normalized_diff_refs = {
        "base_sha": _normalize_sha(diff_refs.get("base_sha")),
        "head_sha": diff_head,
        "start_sha": _normalize_sha(diff_refs.get("start_sha")),
    }
    for key, sha in normalized_diff_refs.items():
        if not sha:
            reasons.append("diff_" + key + "_missing_or_invalid")

    head_pipeline_raw = mr.get("head_pipeline")
    if (
        "head_pipeline" in mr
        and head_pipeline_raw is not None
        and not isinstance(head_pipeline_raw, dict)
    ):
        raise GuardError("merge request head_pipeline must be an object or null")
    head_pipeline = (
        _normalize_pipeline(head_pipeline_raw)
        if isinstance(head_pipeline_raw, dict)
        else None
    )
    if head_pipeline is not None:
        if head_pipeline["id"].startswith("invalid-"):
            reasons.append("head_pipeline_id_missing_or_invalid")
        if not head_pipeline["sha"]:
            reasons.append("head_pipeline_sha_missing_or_invalid")
        elif head_sha and head_pipeline["sha"] != head_sha:
            reasons.append("head_pipeline_sha_mismatch")
        if not head_pipeline["status"]:
            reasons.append("head_pipeline_status_missing_or_invalid")

    normalized = {
        "project_id": _positive_id(mr.get("project_id")),
        "id": _positive_id(mr.get("id")),
        "iid": _positive_id(mr.get("iid")),
        "source_project_id": _positive_id(mr.get("source_project_id")),
        "target_project_id": _positive_id(mr.get("target_project_id")),
        "state": _nonempty_string(mr.get("state")),
        "source_branch": _nonempty_string(mr.get("source_branch")),
        "target_branch": _nonempty_string(mr.get("target_branch")),
        "direct_head_sha": direct_head,
        "head_sha": head_sha,
        "diff_refs": normalized_diff_refs,
        "head_pipeline": head_pipeline,
    }
    for key in ("project_id", "id", "iid", "source_project_id", "target_project_id"):
        if not normalized[key]:
            reasons.append(key + "_missing_or_invalid")
    if normalized["project_id"] and normalized["target_project_id"]:
        if normalized["project_id"] != normalized["target_project_id"]:
            reasons.append("project_target_project_mismatch")
    if normalized["state"] != "opened":
        reasons.append("merge_request_not_opened")
    if not normalized["source_branch"]:
        reasons.append("source_branch_missing")
    if not normalized["target_branch"]:
        reasons.append("target_branch_missing")
    return normalized, sorted(set(reasons))


def _normalize_diff_version(value: Any) -> tuple[dict[str, str], list[str]]:
    if isinstance(value, dict) and "diff_version" in value:
        nested = value.get("diff_version")
        if not isinstance(nested, dict):
            raise GuardError("diff_version wrapper must contain an object")
        direct_fields = {
            "id",
            "base_commit_sha",
            "base_sha",
            "head_commit_sha",
            "head_sha",
            "start_commit_sha",
            "start_sha",
        }
        if direct_fields & set(value):
            raise GuardError(
                "diff version input must not mix wrapper and direct fields"
            )
        value = nested
    if not isinstance(value, dict):
        raise GuardError("diff version JSON must be an object")
    normalized = {
        "id": _positive_id(value.get("id")),
        "base_sha": _normalized_alias(
            value,
            ("base_commit_sha", "base_sha"),
            _normalize_sha,
            "diff version base sha",
        ),
        "head_sha": _normalized_alias(
            value,
            ("head_commit_sha", "head_sha"),
            _normalize_sha,
            "diff version head sha",
        ),
        "start_sha": _normalized_alias(
            value,
            ("start_commit_sha", "start_sha"),
            _normalize_sha,
            "diff version start sha",
        ),
    }
    reasons = [
        "diff_version_" + key + "_missing_or_invalid"
        for key, item in normalized.items()
        if not item
    ]
    return normalized, reasons


def _review_context_digest(
    mr: dict[str, Any], binding: dict[str, Any]
) -> str:
    return stable_hash(
        {
            "merge_request": mr,
            "source_ref_head": binding.get("source_ref_head"),
            "target_ref_head": binding.get("target_ref_head"),
            "diff_version": binding.get("diff_version"),
        }
    )


def build_snapshot(
    mr_value: Any,
    discussion_collection: dict[str, Any],
    *,
    host: str,
    actor_id: str,
    source_ref_head: str,
    target_ref_head: str,
    diff_version_value: Any,
) -> dict[str, Any]:
    """Build a deterministic, body-free review epoch snapshot."""

    if not isinstance(discussion_collection, dict):
        raise GuardError("discussion collection must be an object")
    records = discussion_collection.get("records")
    pagination = discussion_collection.get("pagination")
    if not isinstance(records, list) or not isinstance(pagination, dict):
        raise GuardError("discussion collection is missing records or pagination")

    normalized_host = _normalize_host(host)
    normalized_actor = _positive_id(actor_id)
    if not normalized_actor:
        raise GuardError("actor id must be a positive numeric GitLab user id")
    source_ref = _normalize_sha(source_ref_head)
    target_ref = _normalize_sha(target_ref_head)
    mr, mr_reasons = _normalize_mr(mr_value)
    diff_version, diff_version_reasons = _normalize_diff_version(diff_version_value)

    binding_reasons: list[str] = []
    if not source_ref:
        binding_reasons.append("source_ref_head_missing_or_invalid")
    if not target_ref:
        binding_reasons.append("target_ref_head_missing_or_invalid")
    if source_ref and mr["head_sha"] and source_ref != mr["head_sha"]:
        binding_reasons.append("source_ref_mr_head_mismatch")
    for key in ("base_sha", "head_sha", "start_sha"):
        if diff_version[key] and mr["diff_refs"][key]:
            if diff_version[key] != mr["diff_refs"][key]:
                binding_reasons.append("diff_version_" + key + "_mismatch")

    discussion_variants: dict[str, list[dict[str, Any]]] = {}
    note_occurrences: dict[str, list[tuple[str, str]]] = {}
    total_notes = 0
    for raw_discussion in records:
        if not isinstance(raw_discussion, dict):
            raise GuardError("discussion collection contains a non-object record")
        normalized = _normalize_discussion(raw_discussion)
        total_notes += normalized["note_count"]
        if total_notes > MAX_NOTES:
            raise GuardError("total discussion note limit exceeded")
        discussion_variants.setdefault(normalized["id"], []).append(normalized)
        for note in normalized["notes"]:
            note_occurrences.setdefault(note["id"], []).append(
                (normalized["id"], note["fingerprint"])
            )

    discussions: list[dict[str, Any]] = []
    duplicate_discussion_ids: list[str] = []
    conflicting_discussion_ids: list[str] = []
    for discussion_id, variants in sorted(discussion_variants.items()):
        if len(variants) > 1:
            duplicate_discussion_ids.append(discussion_id)
        unique = {_canonical(item): item for item in variants}
        if len(unique) > 1:
            conflicting_discussion_ids.append(discussion_id)
        discussions.append(unique[sorted(unique)[0]])

    duplicate_note_ids = sorted(
        note_id for note_id, occurrences in note_occurrences.items() if len(occurrences) > 1
    )
    conflicting_note_ids = sorted(
        note_id
        for note_id, occurrences in note_occurrences.items()
        if len(set(occurrences)) > 1
    )
    inventory_digest = stable_hash(
        [
            {"id": discussion["id"], "digest": discussion["digest"]}
            for discussion in discussions
        ]
    )
    binding = {
        "host_hash": stable_hash(normalized_host),
        "actor_id_hash": stable_hash(normalized_actor),
        "source_ref_head": source_ref,
        "target_ref_head": target_ref,
        "diff_version": diff_version,
    }
    mr_digest = stable_hash(mr)
    review_context_digest = _review_context_digest(mr, binding)
    complete = pagination.get("complete") is True
    conflicts = {
        "discussion_ids": conflicting_discussion_ids,
        "note_ids": conflicting_note_ids,
    }
    mutation_reasons = list(mr_reasons)
    mutation_reasons.extend(diff_version_reasons)
    mutation_reasons.extend(binding_reasons)
    mutation_reasons.extend(
        _as_id(item) for item in pagination.get("reasons", [])
    )
    if duplicate_discussion_ids:
        mutation_reasons.append("duplicate_discussion_id")
    if duplicate_note_ids:
        mutation_reasons.append("duplicate_note_id")
    if conflicts["discussion_ids"]:
        mutation_reasons.append("conflicting_duplicate_discussion_id")
    if conflicts["note_ids"]:
        mutation_reasons.append("conflicting_duplicate_note_id")
    mutation_reasons = sorted(set(filter(None, mutation_reasons)))
    mutation_safe = complete and not mutation_reasons
    pagination_output = {
        "source_format": _as_id(pagination.get("source_format")),
        "page_count": int(pagination.get("page_count") or 0),
        "record_count": int(pagination.get("record_count") or 0),
        "complete": complete,
        "completion_basis": sorted(
            {_as_id(item) for item in pagination.get("completion_basis", [])}
        ),
        "reasons": sorted(
            {_as_id(item) for item in pagination.get("reasons", [])}
        ),
        "pages": pagination.get("pages", []),
        "unique_discussion_count": len(discussions),
        "duplicate_discussion_ids": duplicate_discussion_ids,
        "duplicate_note_ids": duplicate_note_ids,
        "conflicting_discussion_ids": conflicts["discussion_ids"],
        "conflicting_note_ids": conflicts["note_ids"],
    }
    pagination_digest = stable_hash(pagination_output)
    epoch_digest = stable_hash(
        {
            "binding": binding,
            "complete": complete,
            "conflicts": conflicts,
            "inventory_digest": inventory_digest,
            "merge_request_digest": mr_digest,
            "mutation_blockers": mutation_reasons,
            "mutation_safe": mutation_safe,
            "pagination_digest": pagination_digest,
        }
    )
    return {
        "schema": SNAPSHOT_SCHEMA,
        "complete": complete,
        "mutation_safe": mutation_safe,
        "mutation_blockers": mutation_reasons,
        "binding": binding,
        "merge_request": mr,
        "merge_request_digest": mr_digest,
        "review_context_digest": review_context_digest,
        "pagination": pagination_output,
        "pagination_digest": pagination_digest,
        "discussions": discussions,
        "inventory_digest": inventory_digest,
        "epoch_digest": epoch_digest,
    }


def snapshot_from_files(
    mr_path: str,
    discussions_path: str,
    diff_version_path: str,
    *,
    host: str,
    actor_id: str,
    source_ref_head: str,
    target_ref_head: str,
    assume_complete_discussion_array: bool = False,
) -> dict[str, Any]:
    return build_snapshot(
        load_json_file(mr_path, "merge request"),
        load_discussions_file(
            discussions_path,
            assume_complete_array=assume_complete_discussion_array,
        ),
        host=host,
        actor_id=actor_id,
        source_ref_head=source_ref_head,
        target_ref_head=target_ref_head,
        diff_version_value=load_json_file(diff_version_path, "diff version"),
    )


def _snapshot_discussions(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    discussions = snapshot.get("discussions")
    if not isinstance(discussions, list):
        raise GuardError("snapshot is missing discussions")
    result: dict[str, dict[str, Any]] = {}
    for item in discussions:
        if not isinstance(item, dict) or not _nonempty_string(item.get("id")):
            raise GuardError("snapshot contains an invalid discussion")
        item_id = _nonempty_string(item["id"])
        if item_id in result:
            raise GuardError("snapshot contains duplicate discussion ids")
        result[item_id] = item
    return result


def _validate_snapshot_integrity(snapshot: dict[str, Any]) -> None:
    """Reject accidentally edited or internally inconsistent snapshot files."""

    if not isinstance(snapshot, dict):
        raise GuardError("snapshot JSON must be an object")
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise GuardError("snapshot schema is not v2")
    mr = snapshot.get("merge_request")
    binding = snapshot.get("binding")
    pagination = snapshot.get("pagination")
    if not isinstance(mr, dict) or not isinstance(binding, dict):
        raise GuardError("snapshot is missing merge_request or binding")
    if not isinstance(pagination, dict):
        raise GuardError("snapshot is missing pagination")
    if not isinstance(snapshot.get("complete"), bool):
        raise GuardError("snapshot complete flag must be boolean")
    if snapshot.get("complete") is not (pagination.get("complete") is True):
        raise GuardError("snapshot and pagination completeness disagree")

    structural_blockers: list[str] = []
    for key in ("host_hash", "actor_id_hash"):
        if not _valid_sha256(binding.get(key)):
            structural_blockers.append("binding_" + key + "_invalid")
    for key in ("source_ref_head", "target_ref_head"):
        if not _valid_sha(binding.get(key)):
            structural_blockers.append("binding_" + key + "_invalid")
    diff_version = binding.get("diff_version")
    if not isinstance(diff_version, dict):
        structural_blockers.append("binding_diff_version_missing")
        diff_version = {}
    if not _positive_id(diff_version.get("id")):
        structural_blockers.append("binding_diff_version_id_invalid")
    for key in ("base_sha", "head_sha", "start_sha"):
        if not _valid_sha(diff_version.get(key)):
            structural_blockers.append("binding_diff_version_" + key + "_invalid")

    for key in ("project_id", "id", "iid", "source_project_id", "target_project_id"):
        if not _positive_id(mr.get(key)):
            structural_blockers.append("merge_request_" + key + "_invalid")
    if _nonempty_string(mr.get("state")) != "opened":
        structural_blockers.append("merge_request_not_opened")
    if not _nonempty_string(mr.get("source_branch")):
        structural_blockers.append("merge_request_source_branch_missing")
    if not _nonempty_string(mr.get("target_branch")):
        structural_blockers.append("merge_request_target_branch_missing")
    if not _valid_sha(mr.get("head_sha")):
        structural_blockers.append("merge_request_head_invalid")
    if not _valid_sha(mr.get("direct_head_sha")):
        structural_blockers.append("merge_request_direct_head_invalid")
    elif _as_id(mr.get("direct_head_sha")) != _as_id(mr.get("head_sha")):
        structural_blockers.append("merge_request_direct_head_mismatch")
    diff_refs = mr.get("diff_refs")
    if not isinstance(diff_refs, dict):
        structural_blockers.append("merge_request_diff_refs_missing")
        diff_refs = {}
    for key in ("base_sha", "head_sha", "start_sha"):
        if not _valid_sha(diff_refs.get(key)):
            structural_blockers.append("merge_request_diff_" + key + "_invalid")
        if _as_id(diff_version.get(key)) != _as_id(diff_refs.get(key)):
            structural_blockers.append("diff_version_" + key + "_mismatch")
    if _as_id(mr.get("head_sha")) != _as_id(diff_refs.get("head_sha")):
        structural_blockers.append("merge_request_head_diff_mismatch")
    if _as_id(binding.get("source_ref_head")) != _as_id(mr.get("head_sha")):
        structural_blockers.append("source_ref_head_mismatch")
    if _as_id(mr.get("project_id")) != _as_id(mr.get("target_project_id")):
        structural_blockers.append("project_target_project_mismatch")
    head_pipeline = mr.get("head_pipeline")
    if head_pipeline is not None:
        if not isinstance(head_pipeline, dict):
            structural_blockers.append("merge_request_head_pipeline_invalid")
        else:
            if not _positive_id(head_pipeline.get("id")):
                structural_blockers.append(
                    "merge_request_head_pipeline_id_invalid"
                )
            if not _valid_sha(head_pipeline.get("sha")):
                structural_blockers.append(
                    "merge_request_head_pipeline_sha_invalid"
                )
            elif _as_id(head_pipeline.get("sha")) != _as_id(
                mr.get("head_sha")
            ):
                structural_blockers.append(
                    "merge_request_head_pipeline_sha_mismatch"
                )
            if not _nonempty_string(head_pipeline.get("status")):
                structural_blockers.append(
                    "merge_request_head_pipeline_status_invalid"
                )
            if not isinstance(head_pipeline.get("source"), str):
                structural_blockers.append(
                    "merge_request_head_pipeline_source_invalid"
                )

    discussions = _snapshot_discussions(snapshot)
    global_note_ids: set[str] = set()
    calculated_discussions: list[dict[str, str]] = []
    for discussion_id, discussion in sorted(discussions.items()):
        notes = _discussion_notes(discussion)
        if (
            isinstance(discussion.get("note_count"), bool)
            or not isinstance(discussion.get("note_count"), int)
            or discussion.get("note_count") != len(notes)
        ):
            structural_blockers.append("discussion_note_count_invalid")
        for key in ("resolution_hash", "state_hash", "digest"):
            if not _valid_sha256(discussion.get(key)):
                structural_blockers.append(
                    "discussion_" + key + "_invalid"
                )
        if not notes:
            structural_blockers.append("discussion_notes_empty")
        resolvable_notes = [
            note for note in notes.values() if note.get("resolvable") is True
        ]
        if resolvable_notes and discussion.get("resolved") is not all(
            note.get("resolved") is True for note in resolvable_notes
        ):
            structural_blockers.append(
                "discussion_resolution_state_inconsistent"
            )
        calculated_notes: list[dict[str, str]] = []
        for note_id, note in sorted(notes.items()):
            if note_id in global_note_ids:
                structural_blockers.append("duplicate_note_id")
            global_note_ids.add(note_id)
            for key in (
                "author_id_hash",
                "body_hash",
                "identity_hash",
                "position_hash",
                "response_bindings_hash",
                "response_keys_hash",
                "resolution_hash",
                "state_hash",
                "fingerprint",
            ):
                if not _valid_sha256(note.get(key)):
                    structural_blockers.append("note_" + key + "_invalid")
            response_keys = note.get("response_keys")
            if (
                not isinstance(response_keys, list)
                or any(not _valid_sha256(item) for item in response_keys)
                or response_keys != sorted(response_keys)
                or stable_hash(response_keys) != _as_id(
                    note.get("response_keys_hash")
                )
            ):
                structural_blockers.append("note_response_keys_invalid")
            normalized_response_keys = (
                response_keys if isinstance(response_keys, list) else []
            )
            response_bindings = note.get("response_bindings")
            if not isinstance(response_bindings, list):
                structural_blockers.append("note_response_bindings_invalid")
                response_bindings = []
            else:
                normalized_bindings: list[dict[str, str]] = []
                for binding_item in response_bindings:
                    if (
                        not isinstance(binding_item, dict)
                        or set(binding_item)
                        != {"response_key", "response_hash"}
                        or not _valid_sha256(
                            binding_item.get("response_key")
                        )
                        or not _valid_sha256(
                            binding_item.get("response_hash")
                        )
                    ):
                        structural_blockers.append(
                            "note_response_bindings_invalid"
                        )
                        continue
                    normalized_bindings.append(
                        {
                            "response_key": _as_id(
                                binding_item.get("response_key")
                            ),
                            "response_hash": _as_id(
                                binding_item.get("response_hash")
                            ),
                        }
                    )
                if (
                    normalized_bindings != response_bindings
                    or normalized_bindings
                    != sorted(
                        normalized_bindings,
                        key=lambda item: (
                            item["response_key"],
                            item["response_hash"],
                        ),
                    )
                    or len(
                        {
                            (
                                item["response_key"],
                                item["response_hash"],
                            )
                            for item in normalized_bindings
                        }
                    )
                    != len(normalized_bindings)
                    or any(
                        item["response_key"] not in normalized_response_keys
                        for item in normalized_bindings
                    )
                    or stable_hash(normalized_bindings)
                    != _as_id(note.get("response_bindings_hash"))
                ):
                    structural_blockers.append(
                        "note_response_bindings_invalid"
                    )
            calculated_fingerprint = stable_hash(
                {
                    "body_hash": _as_id(note.get("body_hash")),
                    "identity_hash": _as_id(note.get("identity_hash")),
                    "position_hash": _as_id(note.get("position_hash")),
                    "response_bindings_hash": _as_id(
                        note.get("response_bindings_hash")
                    ),
                    "response_keys_hash": _as_id(
                        note.get("response_keys_hash")
                    ),
                    "resolution_hash": _as_id(
                        note.get("resolution_hash")
                    ),
                    "state_hash": _as_id(note.get("state_hash")),
                }
            )
            calculated_identity_hash = stable_hash(
                {
                    "discussion_id": discussion_id,
                    "note_id": note_id,
                    "author_id_hash": _as_id(
                        note.get("author_id_hash")
                    ),
                    "system": note.get("system"),
                    "type": note.get("type"),
                }
            )
            if (
                not isinstance(note.get("system"), bool)
                or calculated_identity_hash
                != _as_id(note.get("identity_hash"))
            ):
                structural_blockers.append("note_identity_hash_mismatch")
            calculated_resolution_hash = stable_hash(
                {
                    "resolvable": note.get("resolvable"),
                    "resolved": note.get("resolved"),
                    "type": note.get("type"),
                }
            )
            if calculated_resolution_hash != _as_id(
                note.get("resolution_hash")
            ):
                structural_blockers.append(
                    "note_resolution_hash_mismatch"
                )
            if calculated_fingerprint != _as_id(note.get("fingerprint")):
                structural_blockers.append("note_fingerprint_mismatch")
            calculated_notes.append(
                {"id": note_id, "fingerprint": calculated_fingerprint}
            )
        calculated_resolution_hash = stable_hash(
            {"resolved": discussion.get("resolved")}
        )
        if calculated_resolution_hash != _as_id(
            discussion.get("resolution_hash")
        ):
            structural_blockers.append(
                "discussion_resolution_hash_mismatch"
            )
        calculated_digest = stable_hash(
            {
                "id": discussion_id,
                "notes": calculated_notes,
                "resolution_hash": calculated_resolution_hash,
                "state_hash": _as_id(discussion.get("state_hash")),
            }
        )
        if calculated_digest != _as_id(discussion.get("digest")):
            structural_blockers.append("discussion_digest_mismatch")
        calculated_discussions.append(
            {"id": discussion_id, "digest": calculated_digest}
        )

    calculated_inventory = stable_hash(calculated_discussions)
    if calculated_inventory != _as_id(snapshot.get("inventory_digest")):
        structural_blockers.append("inventory_digest_mismatch")
    calculated_mr_digest = stable_hash(mr)
    if calculated_mr_digest != _as_id(snapshot.get("merge_request_digest")):
        structural_blockers.append("merge_request_digest_mismatch")
    calculated_review_context = _review_context_digest(mr, binding)
    if calculated_review_context != _as_id(
        snapshot.get("review_context_digest")
    ):
        structural_blockers.append("review_context_digest_mismatch")
    conflicts = {
        "discussion_ids": pagination.get("conflicting_discussion_ids", []),
        "note_ids": pagination.get("conflicting_note_ids", []),
    }
    calculated_pagination_digest = stable_hash(pagination)
    if calculated_pagination_digest != _as_id(
        snapshot.get("pagination_digest")
    ):
        structural_blockers.append("pagination_digest_mismatch")
    calculated_epoch = stable_hash(
        {
            "binding": binding,
            "complete": snapshot.get("complete"),
            "conflicts": conflicts,
            "inventory_digest": calculated_inventory,
            "merge_request_digest": calculated_mr_digest,
            "mutation_blockers": snapshot.get("mutation_blockers"),
            "mutation_safe": snapshot.get("mutation_safe"),
            "pagination_digest": calculated_pagination_digest,
        }
    )
    if calculated_epoch != _as_id(snapshot.get("epoch_digest")):
        structural_blockers.append("epoch_digest_mismatch")

    pagination_reasons = pagination.get("reasons")
    completion_basis = pagination.get("completion_basis")
    if not isinstance(pagination_reasons, list):
        structural_blockers.append("pagination_reasons_invalid")
        pagination_reasons = []
    elif (
        any(not isinstance(item, str) or not item for item in pagination_reasons)
        or pagination_reasons != sorted(set(pagination_reasons))
    ):
        structural_blockers.append("pagination_reasons_invalid")
    if not isinstance(completion_basis, list):
        structural_blockers.append("pagination_completion_basis_invalid")
        completion_basis = []
    allowed_completion_basis = {
        "caller_declared_complete_raw_collection",
        "next_page_terminal",
        "page_complete",
        "top_level_complete_single_page",
        "total_pages",
    }
    if (
        any(
            not isinstance(item, str)
            or item not in allowed_completion_basis
            for item in completion_basis
        )
        or completion_basis != sorted(set(completion_basis))
    ):
        structural_blockers.append("pagination_completion_basis_invalid")
    if snapshot.get("complete") and (pagination_reasons or not completion_basis):
        structural_blockers.append("pagination_completion_evidence_invalid")
    pages = pagination.get("pages")
    if not isinstance(pages, list):
        structural_blockers.append("pagination_pages_invalid")
        pages = []
    page_count = pagination.get("page_count")
    record_count = pagination.get("record_count")
    unique_count = pagination.get("unique_discussion_count")
    page_item_counts: list[int] = []
    pages_valid = True
    for page in pages:
        if not isinstance(page, dict):
            pages_valid = False
            continue
        item_count = page.get("item_count")
        if (
            isinstance(item_count, bool)
            or not isinstance(item_count, int)
            or item_count < 0
        ):
            pages_valid = False
            continue
        page_item_counts.append(item_count)
    if (
        isinstance(page_count, bool)
        or not isinstance(page_count, int)
        or page_count != len(pages)
        or page_count <= 0
    ):
        structural_blockers.append("pagination_page_count_invalid")
    if (
        isinstance(record_count, bool)
        or not isinstance(record_count, int)
        or record_count < len(discussions)
        or not pages_valid
        or sum(page_item_counts) != record_count
    ):
        structural_blockers.append("pagination_record_count_invalid")
    if (
        isinstance(unique_count, bool)
        or not isinstance(unique_count, int)
        or unique_count != len(discussions)
    ):
        structural_blockers.append(
            "pagination_unique_discussion_count_invalid"
        )
    for key in (
        "duplicate_discussion_ids",
        "duplicate_note_ids",
        "conflicting_discussion_ids",
        "conflicting_note_ids",
    ):
        value = pagination.get(key)
        if not isinstance(value, list):
            structural_blockers.append("pagination_" + key + "_invalid")
        elif value:
            structural_blockers.append("pagination_" + key)

    blockers = snapshot.get("mutation_blockers")
    if not isinstance(blockers, list):
        raise GuardError("snapshot mutation_blockers must be an array")
    if (
        any(not isinstance(item, str) or not item for item in blockers)
        or blockers != sorted(set(blockers))
    ):
        raise GuardError(
            "snapshot mutation_blockers must be sorted unique strings"
        )
    if snapshot.get("mutation_safe") is True:
        if blockers or structural_blockers or not snapshot.get("complete"):
            raise GuardError(
                "snapshot claims mutation safety but fails integrity checks: "
                + ",".join(sorted(set(structural_blockers + blockers)))
            )
    elif not isinstance(snapshot.get("mutation_safe"), bool):
        raise GuardError("snapshot mutation_safe flag must be boolean")
    if any(
        blocker.endswith("_digest_mismatch") or blocker == "epoch_digest_mismatch"
        for blocker in structural_blockers
    ):
        raise GuardError(
            "snapshot digest integrity check failed: "
            + ",".join(sorted(set(structural_blockers)))
        )


def compare_snapshots(
    before: dict[str, Any], after: dict[str, Any]
) -> dict[str, Any]:
    """Compare two normalized epochs and report safety-relevant drift."""

    _validate_snapshot_integrity(before)
    _validate_snapshot_integrity(after)
    before_mr = before.get("merge_request")
    after_mr = after.get("merge_request")
    if not isinstance(before_mr, dict) or not isinstance(after_mr, dict):
        raise GuardError("snapshot is missing merge_request")
    before_binding = before.get("binding")
    after_binding = after.get("binding")
    if not isinstance(before_binding, dict) or not isinstance(after_binding, dict):
        raise GuardError("snapshot is missing binding")

    mr_changes = {
        "identity_changed": any(
            before_mr.get(key) != after_mr.get(key)
            for key in (
                "project_id",
                "id",
                "iid",
                "source_project_id",
                "target_project_id",
            )
        ),
        "state_changed": before_mr.get("state") != after_mr.get("state"),
        "head_changed": before_mr.get("head_sha") != after_mr.get("head_sha"),
        "direct_head_changed": before_mr.get("direct_head_sha")
        != after_mr.get("direct_head_sha"),
        "diff_refs_changed": before_mr.get("diff_refs") != after_mr.get("diff_refs"),
        "head_pipeline_changed": before_mr.get("head_pipeline")
        != after_mr.get("head_pipeline"),
        "source_branch_changed": before_mr.get("source_branch")
        != after_mr.get("source_branch"),
        "target_branch_changed": before_mr.get("target_branch")
        != after_mr.get("target_branch"),
    }
    binding_changes = {
        key + "_changed": before_binding.get(key) != after_binding.get(key)
        for key in (
            "host_hash",
            "actor_id_hash",
            "source_ref_head",
            "target_ref_head",
            "diff_version",
        )
    }
    before_discussions = _snapshot_discussions(before)
    after_discussions = _snapshot_discussions(after)
    before_ids = set(before_discussions)
    after_ids = set(after_discussions)
    changed_discussions: list[dict[str, Any]] = []
    for discussion_id in sorted(before_ids & after_ids):
        left = before_discussions[discussion_id]
        right = after_discussions[discussion_id]
        if left.get("digest") == right.get("digest"):
            continue
        left_notes = {
            _as_id(note.get("id")): note
            for note in left.get("notes", [])
            if isinstance(note, dict)
        }
        right_notes = {
            _as_id(note.get("id")): note
            for note in right.get("notes", [])
            if isinstance(note, dict)
        }
        note_changes: list[dict[str, Any]] = []
        for note_id in sorted(set(left_notes) & set(right_notes)):
            old_note = left_notes[note_id]
            new_note = right_notes[note_id]
            if old_note.get("fingerprint") == new_note.get("fingerprint"):
                continue
            note_changes.append(
                {
                    "id": note_id,
                    "body_changed": old_note.get("body_hash")
                    != new_note.get("body_hash"),
                    "identity_changed": old_note.get("identity_hash")
                    != new_note.get("identity_hash"),
                    "state_changed": old_note.get("state_hash")
                    != new_note.get("state_hash"),
                    "position_changed": old_note.get("position_hash")
                    != new_note.get("position_hash"),
                }
            )
        changed_discussions.append(
            {
                "id": discussion_id,
                "resolution_changed": left.get("resolved") != right.get("resolved"),
                "added_note_ids": sorted(set(right_notes) - set(left_notes)),
                "removed_note_ids": sorted(set(left_notes) - set(right_notes)),
                "changed_notes": note_changes,
            }
        )

    equivalent = before.get("epoch_digest") == after.get("epoch_digest")
    mutation_reasons: list[str] = []
    if not before.get("mutation_safe"):
        mutation_reasons.append("before_snapshot_not_mutation_safe")
    if not after.get("mutation_safe"):
        mutation_reasons.append("after_snapshot_not_mutation_safe")
    for change_set in (mr_changes, binding_changes):
        mutation_reasons.extend(key for key, changed in change_set.items() if changed)
    if before.get("inventory_digest") != after.get("inventory_digest"):
        mutation_reasons.append("discussion_state_changed")
    pagination_changed = before.get("pagination_digest") != after.get(
        "pagination_digest"
    )
    if pagination_changed:
        mutation_reasons.append("pagination_evidence_changed")
    if not equivalent and not mutation_reasons:
        mutation_reasons.append("epoch_digest_changed")
    mutation_reasons = sorted(set(mutation_reasons))
    mutation_safe = not mutation_reasons and equivalent
    return {
        "schema": COMPARE_SCHEMA,
        "ok": mutation_safe,
        "equivalent": equivalent,
        "mutation_safe": mutation_safe,
        "mutation_blockers": mutation_reasons,
        "changes": {
            "merge_request": mr_changes,
            "binding": binding_changes,
            "added_discussion_ids": sorted(after_ids - before_ids),
            "removed_discussion_ids": sorted(before_ids - after_ids),
            "changed_discussions": changed_discussions,
            "pagination": {
                "changed": pagination_changed,
                "before_digest": _as_id(before.get("pagination_digest")),
                "after_digest": _as_id(after.get("pagination_digest")),
            },
        },
        "before_epoch_digest": _as_id(before.get("epoch_digest")),
        "after_epoch_digest": _as_id(after.get("epoch_digest")),
    }


def parse_pipelines_text(
    text: str, *, assume_complete_array: bool = False
) -> dict[str, Any]:
    """Parse pipelines without treating a partial list as complete."""

    value, source = _parse_json_or_ndjson(text, "pipeline")
    if source == "ndjson":
        assert isinstance(value, list)
        if all(_is_pipeline(record) for record in value):
            for record in value:
                _reject_direct_collection_mix(record, label="pipeline")
            return _raw_collection(
                value,
                label="pipeline",
                source_format="ndjson-pipelines",
                assume_complete=assume_complete_array,
                item_limit=MAX_PIPELINES,
            )
        return _collect_strict_pages(
            value,
            item_keys=("pipelines", "items", "data"),
            label="pipeline",
            source_format="ndjson-pages",
            declared_complete=None,
            item_limit=MAX_PIPELINES,
        )

    if isinstance(value, list):
        if all(_is_pipeline(item) for item in value):
            for item in value:
                _reject_direct_collection_mix(item, label="pipeline")
            return _raw_collection(
                value,
                label="pipeline",
                source_format="json-array",
                assume_complete=assume_complete_array,
                item_limit=MAX_PIPELINES,
            )
        return _collect_strict_pages(
            value,
            item_keys=("pipelines", "items", "data"),
            label="pipeline",
            source_format="json-pages",
            declared_complete=None,
            item_limit=MAX_PIPELINES,
        )
    if not isinstance(value, dict):
        raise GuardError("pipeline JSON must be an array or object")
    if "pipeline" in value:
        nested = value.get("pipeline")
        if not isinstance(nested, dict):
            raise GuardError("pipeline wrapper must contain an object")
        direct_fields = {
            "id",
            "pipeline_id",
            "sha",
            "head_sha",
            "source_sha",
            "status",
            "detailed_status",
            "source",
        }
        if direct_fields & set(value):
            raise GuardError(
                "pipeline input must not mix wrapper and direct fields"
            )
        if any(key in value for key in ("pipelines", "items", "data")):
            raise GuardError(
                "pipeline wrapper must not contain a collection"
            )
        complete = value.get("complete")
        if complete is not None and not isinstance(complete, bool):
            raise GuardError("pipeline top-level complete must be boolean")
        if any(
            key in value
            for key in (
                "page",
                "current_page",
                "next_page",
                "total_pages",
                "pagination",
                "pages",
            )
        ):
            raise GuardError(
                "single pipeline wrapper must not contain pagination metadata"
            )
        return _raw_collection(
            [nested],
            label="pipeline",
            source_format="json-pipeline-wrapper",
            assume_complete=complete is True,
            item_limit=MAX_PIPELINES,
        )
    if _is_pipeline(value):
        _reject_direct_collection_mix(value, label="pipeline")
        return _raw_collection(
            [value],
            label="pipeline",
            source_format="json-single-pipeline",
            assume_complete=assume_complete_array,
            item_limit=MAX_PIPELINES,
        )
    declared_complete: bool | None = None
    has_complete, complete_value = _value_from_layers(value, "complete")
    if has_complete:
        if not isinstance(complete_value, bool):
            raise GuardError("pipeline top-level complete must be boolean")
        declared_complete = complete_value
    pages = value.get("pages")
    if pages is not None:
        if not isinstance(pages, list):
            raise GuardError("pipeline pages must be an array")
        if any(key in value for key in ("pipelines", "items", "data")):
            raise GuardError(
                "pipeline pages envelope must not contain a top-level collection"
            )
        if any(
            _value_from_layers(value, key)[0]
            for key in ("page", "current_page", "next_page", "total_pages")
        ):
            raise GuardError(
                "pipeline pages envelope contains page-level metadata"
            )
        return _collect_strict_pages(
            pages,
            item_keys=("pipelines", "items", "data"),
            label="pipeline",
            source_format="json-pages-envelope",
            declared_complete=declared_complete,
            item_limit=MAX_PIPELINES,
        )
    return _collect_strict_pages(
        [value],
        item_keys=("pipelines", "items", "data"),
        label="pipeline",
        source_format="json-envelope",
        declared_complete=declared_complete,
        item_limit=MAX_PIPELINES,
    )


def load_pipelines_file(
    path: str, *, assume_complete_array: bool = False
) -> dict[str, Any]:
    return parse_pipelines_text(
        _read_text(path), assume_complete_array=assume_complete_array
    )


def _normalize_pipelines(
    pipeline_values: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, str]], list[str], list[str], list[str]]:
    variants: dict[str, list[dict[str, str]]] = {}
    invalid_ids: list[str] = []
    for index, raw in enumerate(pipeline_values):
        if not isinstance(raw, dict):
            raise GuardError("pipeline collection contains a non-object record")
        pipeline = _normalize_pipeline(raw)
        if pipeline["id"].startswith("invalid-"):
            invalid_ids.append(f"index-{index}")
        variants.setdefault(pipeline["id"], []).append(pipeline)

    pipelines: list[dict[str, str]] = []
    duplicate_ids: list[str] = []
    conflicting_ids: list[str] = []
    for pipeline_id, items in sorted(variants.items()):
        if len(items) > 1:
            duplicate_ids.append(pipeline_id)
        unique = {_canonical(item): item for item in items}
        if len(unique) > 1:
            conflicting_ids.append(pipeline_id)
        pipelines.extend(unique[key] for key in sorted(unique))
    pipelines.sort(key=lambda item: (item["sha"], item["id"], item["status"]))
    return pipelines, duplicate_ids, conflicting_ids, invalid_ids


def verify_exact_head(
    snapshot: dict[str, Any],
    expected_head: str,
    *,
    local_head: str | None,
    source_ref_head: str | None,
    pipeline_collection: dict[str, Any] | None,
) -> dict[str, Any]:
    """Verify immutable source-head and complete exact-head pipeline evidence."""

    _validate_snapshot_integrity(snapshot)
    expected = _normalize_sha(expected_head)
    if not expected:
        raise GuardError("expected head must be exactly 40 or 64 hexadecimal characters")
    mr = snapshot.get("merge_request")
    binding = snapshot.get("binding")
    if not isinstance(mr, dict) or not isinstance(binding, dict):
        raise GuardError("snapshot is missing merge_request or binding")

    inputs = {
        "expected_head": expected,
        "snapshot_epoch_digest": _as_id(snapshot.get("epoch_digest")),
        "mr_head": _as_id(mr.get("head_sha")),
        "diff_head": _as_id(
            mr.get("diff_refs", {}).get("head_sha")
            if isinstance(mr.get("diff_refs"), dict)
            else ""
        ),
        "snapshot_source_ref_head": _as_id(binding.get("source_ref_head")),
        "local_head": _normalize_sha(local_head) if local_head is not None else "",
        "source_ref_head": (
            _normalize_sha(source_ref_head) if source_ref_head is not None else ""
        ),
    }
    reasons: list[str] = []
    if not snapshot.get("mutation_safe"):
        reasons.append("snapshot_not_mutation_safe")
    for key in (
        "mr_head",
        "diff_head",
        "snapshot_source_ref_head",
        "local_head",
        "source_ref_head",
    ):
        if inputs[key] != expected:
            reasons.append(key + "_mismatch")

    pipelines: list[dict[str, str]] = []
    duplicate_ids: list[str] = []
    conflicting_ids: list[str] = []
    invalid_ids: list[str] = []
    pagination: dict[str, Any] = {}
    if not isinstance(pipeline_collection, dict):
        reasons.append("pipeline_collection_missing")
    else:
        records = pipeline_collection.get("records")
        pagination_raw = pipeline_collection.get("pagination")
        if not isinstance(records, list) or not isinstance(pagination_raw, dict):
            raise GuardError("pipeline collection is missing records or pagination")
        pagination = pagination_raw
        if pagination.get("complete") is not True:
            reasons.append("pipeline_collection_incomplete")
        pipelines, duplicate_ids, conflicting_ids, invalid_ids = _normalize_pipelines(
            records
        )

    exact = [pipeline for pipeline in pipelines if pipeline["sha"] == expected]
    stale = [
        pipeline for pipeline in pipelines if pipeline["sha"] and pipeline["sha"] != expected
    ]
    unclassified = [pipeline for pipeline in pipelines if not pipeline["sha"]]
    if duplicate_ids:
        reasons.append("duplicate_pipeline_id")
    if conflicting_ids:
        reasons.append("conflicting_pipeline_id")
    if invalid_ids:
        reasons.append("pipeline_id_missing_or_invalid")
    for pipeline in unclassified:
        reasons.append("pipeline_sha_missing_or_invalid:" + pipeline["id"])
    if not exact:
        reasons.append("no_exact_head_pipeline")

    head_pipeline = mr.get("head_pipeline")
    required_pipeline_id = (
        _as_id(head_pipeline.get("id"))
        if isinstance(head_pipeline, dict)
        else ""
    )
    if required_pipeline_id and not any(
        pipeline["id"] == required_pipeline_id for pipeline in exact
    ):
        reasons.append("mr_head_pipeline_missing_from_proof")
    required_pipeline = next(
        (
            pipeline
            for pipeline in exact
            if pipeline["id"] == required_pipeline_id
        ),
        None,
    )
    pipelines_requiring_success = (
        [required_pipeline]
        if required_pipeline is not None
        else exact
    )
    for pipeline in pipelines_requiring_success:
        if pipeline["status"] not in SUCCESS_PIPELINE_STATUSES:
            reasons.append(
                "exact_head_pipeline_not_success:"
                + pipeline["id"]
                + ":"
                + (pipeline["status"] or "unknown")
            )
    pipeline_proven = bool(exact) and not any(
        reason.startswith(
            (
                "pipeline_",
                "duplicate_pipeline",
                "conflicting_pipeline",
                "no_exact_head_pipeline",
                "mr_head_pipeline",
                "exact_head_pipeline",
            )
        )
        for reason in reasons
    )
    reasons = sorted(set(reasons))
    return {
        "schema": HEAD_SCHEMA,
        "ok": not reasons,
        "expected_head": expected,
        "snapshot_epoch_digest": _as_id(snapshot.get("epoch_digest")),
        "inputs": inputs,
        "pipeline_proof": {
            "collection_complete": pagination.get("complete") is True,
            "collection_digest": stable_hash(pipelines),
            "completion_basis": pagination.get("completion_basis", []),
            "proven": pipeline_proven,
            "required_pipeline_id": required_pipeline_id,
            "exact_head": exact,
            "stale_head": stale,
            "unclassified": unclassified,
            "duplicate_ids": duplicate_ids,
            "conflicting_ids": conflicting_ids,
            "invalid_ids": invalid_ids,
        },
        "blockers": reasons,
    }


def _check_object_keys(
    value: Any,
    *,
    required: set[str],
    optional: set[str],
    label: str,
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(label + "_not_object")
        return {}
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    errors.extend(label + "_missing_" + key for key in missing)
    errors.extend(label + "_unknown_" + key for key in unknown)
    return value


def make_dedupe_key(
    action: dict[str, Any], expected: dict[str, Any]
) -> str:
    """Derive the deterministic response key for one bound discussion."""

    note_ids = action.get("addressed_note_ids")
    if not isinstance(note_ids, list):
        note_ids = []
    return stable_hash(
        {
            "schema": DEDUPE_SCHEMA,
            "host_hash": _as_id(expected.get("host_hash")),
            "project_id": _as_id(expected.get("project_id")),
            "source_project_id": _as_id(expected.get("source_project_id")),
            "target_project_id": _as_id(expected.get("target_project_id")),
            "mr_iid": _as_id(expected.get("mr_iid")),
            "head_sha": _as_id(expected.get("head_sha")),
            "review_context_digest": _as_id(
                expected.get("review_context_digest")
            ),
            "discussion_id": _as_id(action.get("discussion_id")),
            "addressed_note_ids": sorted(_as_id(item) for item in note_ids),
            "response_hash": _as_id(action.get("response_hash")),
            "delivery_head": _as_id(action.get("delivery_head")),
            "fix_commit": _as_id(action.get("fix_commit")),
            "no_change_evidence_hash": _as_id(
                action.get("no_change_evidence_hash")
            ),
        }
    )


def _exact_head_proof_errors(
    proof: Any, snapshot: dict[str, Any], expected_head: str
) -> list[str]:
    if not isinstance(proof, dict):
        return ["missing"]
    errors: list[str] = []
    if proof.get("schema") != HEAD_SCHEMA:
        errors.append("schema_invalid")
    if proof.get("ok") is not True or proof.get("blockers"):
        errors.append("gate_not_passed")
    if _as_id(proof.get("expected_head")) != expected_head:
        errors.append("head_mismatch")
    if _as_id(proof.get("snapshot_epoch_digest")) != _as_id(
        snapshot.get("epoch_digest")
    ):
        errors.append("epoch_mismatch")
    inputs = proof.get("inputs")
    if not isinstance(inputs, dict):
        errors.append("inputs_missing")
    else:
        expected_input_keys = {
            "expected_head",
            "snapshot_epoch_digest",
            "mr_head",
            "diff_head",
            "snapshot_source_ref_head",
            "local_head",
            "source_ref_head",
        }
        if set(inputs) != expected_input_keys:
            errors.append("inputs_schema_invalid")
        for key in (
            "expected_head",
            "mr_head",
            "diff_head",
            "snapshot_source_ref_head",
            "local_head",
            "source_ref_head",
        ):
            if _as_id(inputs.get(key)) != expected_head:
                errors.append(key + "_mismatch")
        if _as_id(inputs.get("snapshot_epoch_digest")) != _as_id(
            snapshot.get("epoch_digest")
        ):
            errors.append("input_epoch_mismatch")
    pipeline_proof = proof.get("pipeline_proof")
    if not isinstance(pipeline_proof, dict):
        errors.append("pipeline_missing")
    else:
        expected_pipeline_keys = {
            "collection_complete",
            "collection_digest",
            "completion_basis",
            "proven",
            "required_pipeline_id",
            "exact_head",
            "stale_head",
            "unclassified",
            "duplicate_ids",
            "conflicting_ids",
            "invalid_ids",
        }
        if set(pipeline_proof) != expected_pipeline_keys:
            errors.append("pipeline_schema_invalid")
        exact = pipeline_proof.get("exact_head")
        stale = pipeline_proof.get("stale_head")
        unclassified = pipeline_proof.get("unclassified")
        if (
            pipeline_proof.get("collection_complete") is not True
            or pipeline_proof.get("proven") is not True
            or not isinstance(exact, list)
            or not exact
        ):
            errors.append("pipeline_not_proven")
        elif any(
            not isinstance(item, dict)
            or _as_id(item.get("sha")) != expected_head
            or not _positive_id(item.get("id"))
            or not _as_id(item.get("status"))
            for item in exact
        ):
            errors.append("pipeline_result_invalid")
        if pipeline_proof.get("duplicate_ids"):
            errors.append("pipeline_ids_duplicate")
        if pipeline_proof.get("conflicting_ids"):
            errors.append("pipeline_ids_conflict")
        if pipeline_proof.get("invalid_ids") or unclassified:
            errors.append("pipeline_records_invalid")
        completion_basis = pipeline_proof.get("completion_basis")
        allowed_basis = {
            "caller_declared_complete_raw_collection",
            "next_page_terminal",
            "total_pages",
            "page_complete",
            "top_level_complete_single_page",
        }
        if (
            not isinstance(completion_basis, list)
            or not completion_basis
            or any(item not in allowed_basis for item in completion_basis)
            or len(set(completion_basis)) != len(completion_basis)
        ):
            errors.append("pipeline_completion_basis_invalid")
        if not isinstance(stale, list) or not isinstance(unclassified, list):
            errors.append("pipeline_records_missing")
        elif isinstance(exact, list):
            all_pipelines = exact + stale + unclassified
            if any(not isinstance(item, dict) for item in all_pipelines):
                errors.append("pipeline_record_invalid")
            else:
                normalized_records = sorted(
                    all_pipelines,
                    key=lambda item: (
                        _as_id(item.get("sha")),
                        _as_id(item.get("id")),
                        _as_id(item.get("status")),
                    ),
                )
                if stable_hash(normalized_records) != _as_id(
                    pipeline_proof.get("collection_digest")
                ):
                    errors.append("pipeline_collection_digest_mismatch")
        mr = snapshot.get("merge_request")
        head_pipeline = mr.get("head_pipeline") if isinstance(mr, dict) else None
        required_pipeline_id = (
            _as_id(head_pipeline.get("id"))
            if isinstance(head_pipeline, dict)
            else ""
        )
        if _as_id(pipeline_proof.get("required_pipeline_id")) != required_pipeline_id:
            errors.append("required_pipeline_id_mismatch")
        if required_pipeline_id and isinstance(exact, list):
            selected = [
                item
                for item in exact
                if isinstance(item, dict)
                and _as_id(item.get("id")) == required_pipeline_id
            ]
            if len(selected) != 1:
                errors.append("required_pipeline_result_missing")
            elif _as_id(selected[0].get("status")) not in (
                SUCCESS_PIPELINE_STATUSES
            ):
                errors.append("required_pipeline_result_not_success")
        elif isinstance(exact, list):
            if any(
                isinstance(item, dict)
                and _as_id(item.get("status"))
                not in SUCCESS_PIPELINE_STATUSES
                for item in exact
            ):
                errors.append("pipeline_result_not_success")
    return sorted(set(errors))


def _discussion_notes(discussion: dict[str, Any]) -> dict[str, dict[str, Any]]:
    notes = discussion.get("notes")
    if not isinstance(notes, list):
        raise GuardError("snapshot discussion is missing notes")
    result: dict[str, dict[str, Any]] = {}
    for note in notes:
        if not isinstance(note, dict) or not _as_id(note.get("id")):
            raise GuardError("snapshot discussion contains an invalid note")
        note_id = _as_id(note["id"])
        if note_id in result:
            raise GuardError("snapshot discussion contains duplicate note ids")
        result[note_id] = note
    return result


def _prewrite_discussion_notes(
    proof: Any,
    *,
    discussion_id: str,
    discussion_digest: str,
    label: str,
    errors: list[str],
) -> tuple[dict[str, str], str, str]:
    proof = _check_object_keys(
        proof,
        required={"id", "resolution_hash", "state_hash", "notes"},
        optional=set(),
        label=label,
        errors=errors,
    )
    proof_id = _as_id(proof.get("id"))
    if proof_id != discussion_id:
        errors.append(label + "_id_mismatch")
    resolution_hash = _as_id(proof.get("resolution_hash"))
    state_hash = _as_id(proof.get("state_hash"))
    if not _valid_sha256(resolution_hash):
        errors.append(label + "_resolution_hash_invalid")
    if not _valid_sha256(state_hash):
        errors.append(label + "_state_hash_invalid")
    raw_notes = proof.get("notes")
    if not isinstance(raw_notes, list) or not raw_notes:
        errors.append(label + "_notes_missing")
        raw_notes = []
    normalized_notes: list[dict[str, str]] = []
    note_fingerprints: dict[str, str] = {}
    for index, raw_note in enumerate(raw_notes):
        note_label = label + f"_note_{index}"
        note_value = _check_object_keys(
            raw_note,
            required={"id", "fingerprint"},
            optional=set(),
            label=note_label,
            errors=errors,
        )
        note_id = _positive_id(note_value.get("id"))
        fingerprint = _as_id(note_value.get("fingerprint"))
        if not note_id:
            errors.append(note_label + "_id_invalid")
            continue
        if not _valid_sha256(fingerprint):
            errors.append(note_label + "_fingerprint_invalid")
            continue
        if note_id in note_fingerprints:
            errors.append(label + "_note_ids_duplicate")
            continue
        note_fingerprints[note_id] = fingerprint
        normalized_notes.append(
            {"id": note_id, "fingerprint": fingerprint}
        )
    normalized_notes.sort(key=lambda item: item["id"])
    if raw_notes != normalized_notes:
        errors.append(label + "_notes_not_normalized")
    calculated_digest = stable_hash(
        {
            "id": proof_id,
            "notes": normalized_notes,
            "resolution_hash": resolution_hash,
            "state_hash": state_hash,
        }
    )
    if calculated_digest != discussion_digest:
        errors.append(label + "_digest_mismatch")
    return note_fingerprints, state_hash, resolution_hash


def _validate_confirmed_receipt(
    receipt: Any,
    *,
    discussion: dict[str, Any] | None,
    snapshot: dict[str, Any],
    expected: dict[str, Any],
    expected_actor_hash: str,
    label: str,
) -> list[str]:
    errors: list[str] = []
    receipt = _check_object_keys(
        receipt,
        required={
            "status",
            "note_id",
            "response_hash",
            "posted_body_hash",
            "response_key",
            "delivery_head",
            "fix_commit",
            "addressed_note_ids",
            "author_id_hash",
            "note_fingerprint",
            "readback_epoch_digest",
            "reply_epoch_digest",
            "reply_review_context_digest",
            "reply_discussion_digest",
            "prewrite_discussion",
        },
        optional={"no_change_evidence_hash"},
        label=label,
        errors=errors,
    )
    if _as_id(receipt.get("status")) != "confirmed":
        errors.append(label + "_status_not_confirmed")
    note_id = _as_id(receipt.get("note_id"))
    response_hash = _as_id(receipt.get("response_hash"))
    if not _valid_sha256(response_hash):
        errors.append(label + "_response_hash_invalid")
    posted_body_hash = _as_id(receipt.get("posted_body_hash"))
    if not _valid_sha256(posted_body_hash):
        errors.append(label + "_posted_body_hash_invalid")
    response_key = _as_id(receipt.get("response_key"))
    if not _valid_sha256(response_key):
        errors.append(label + "_response_key_invalid")
    expected_head = _as_id(expected.get("head_sha"))
    if _as_id(receipt.get("delivery_head")) != expected_head:
        errors.append(label + "_delivery_head_mismatch")
    reply_epoch_digest = _as_id(receipt.get("reply_epoch_digest"))
    reply_review_context_digest = _as_id(
        receipt.get("reply_review_context_digest")
    )
    reply_discussion_digest = _as_id(receipt.get("reply_discussion_digest"))
    if not _valid_sha256(reply_epoch_digest):
        errors.append(label + "_reply_epoch_digest_invalid")
    if not _valid_sha256(reply_discussion_digest):
        errors.append(label + "_reply_discussion_digest_invalid")
    if not _valid_sha256(reply_review_context_digest):
        errors.append(label + "_reply_review_context_digest_invalid")
    if reply_review_context_digest != _as_id(
        snapshot.get("review_context_digest")
    ):
        errors.append(label + "_review_context_changed_since_reply")
    if reply_epoch_digest == _as_id(snapshot.get("epoch_digest")):
        errors.append(label + "_reply_epoch_not_pre_write")
    if (
        discussion is not None
        and reply_discussion_digest == _as_id(discussion.get("digest"))
    ):
        errors.append(label + "_reply_discussion_not_pre_write")
    (
        prewrite_note_fingerprints,
        prewrite_state_hash,
        prewrite_resolution_hash,
    ) = _prewrite_discussion_notes(
        receipt.get("prewrite_discussion"),
        discussion_id=_as_id(expected.get("discussion_id")),
        discussion_digest=reply_discussion_digest,
        label=label + "_prewrite_discussion",
        errors=errors,
    )

    addressed = receipt.get("addressed_note_ids")
    if not isinstance(addressed, list) or not addressed:
        addressed = []
        errors.append(label + "_addressed_note_ids_missing")
    addressed_ids = [_as_id(item) for item in addressed]
    if (
        any(not item for item in addressed_ids)
        or len(set(addressed_ids)) != len(addressed_ids)
    ):
        errors.append(label + "_addressed_note_ids_invalid")
    if note_id in addressed_ids:
        errors.append(label + "_receipt_note_cannot_be_addressed")
    if any(
        item not in prewrite_note_fingerprints for item in addressed_ids
    ):
        errors.append(label + "_addressed_note_not_prewrite")
    if note_id in prewrite_note_fingerprints:
        errors.append(label + "_receipt_note_was_prewrite")
    fix_commit = _as_id(receipt.get("fix_commit"))
    if fix_commit == "no-change":
        if not _valid_sha256(receipt.get("no_change_evidence_hash")):
            errors.append(label + "_no_change_evidence_hash_invalid")
    else:
        if fix_commit != expected_head:
            errors.append(label + "_fix_commit_not_expected_head")
        if "no_change_evidence_hash" in receipt:
            errors.append(label + "_unexpected_no_change_evidence_hash")

    reply_expected = dict(expected)
    reply_expected["epoch_digest"] = reply_epoch_digest
    reply_expected["review_context_digest"] = reply_review_context_digest
    reply_expected["discussion_digest"] = reply_discussion_digest
    receipt_action = {
        "discussion_id": _as_id(expected.get("discussion_id")),
        "addressed_note_ids": addressed_ids,
        "response_hash": response_hash,
        "delivery_head": _as_id(receipt.get("delivery_head")),
        "fix_commit": fix_commit,
    }
    if "no_change_evidence_hash" in receipt:
        receipt_action["no_change_evidence_hash"] = _as_id(
            receipt.get("no_change_evidence_hash")
        )
    if response_key != make_dedupe_key(receipt_action, reply_expected):
        errors.append(label + "_response_key_context_mismatch")
    if _as_id(receipt.get("author_id_hash")) != expected_actor_hash:
        errors.append(label + "_author_mismatch")
    if _as_id(receipt.get("readback_epoch_digest")) != _as_id(
        snapshot.get("epoch_digest")
    ):
        errors.append(label + "_readback_epoch_mismatch")
    if discussion is None:
        errors.append(label + "_discussion_missing")
        return sorted(set(errors))
    if _as_id(discussion.get("state_hash")) != prewrite_state_hash:
        errors.append(label + "_discussion_state_changed_since_reply")
    if (
        _as_id(discussion.get("resolution_hash"))
        != prewrite_resolution_hash
    ):
        errors.append(label + "_discussion_resolution_changed_since_reply")
    current_notes = _discussion_notes(discussion)
    expected_current_note_ids = set(prewrite_note_fingerprints) | {note_id}
    if set(current_notes) != expected_current_note_ids:
        errors.append(label + "_discussion_notes_changed_since_reply")
    if any(
        item not in current_notes
        or _as_id(current_notes[item].get("fingerprint"))
        != fingerprint
        for item, fingerprint in prewrite_note_fingerprints.items()
    ):
        errors.append(label + "_discussion_notes_changed_since_reply")
    if any(item not in current_notes for item in addressed_ids):
        errors.append(label + "_addressed_note_not_current")
    if any(
        item in current_notes
        and _as_id(current_notes[item].get("fingerprint"))
        != prewrite_note_fingerprints.get(item)
        for item in addressed_ids
    ):
        errors.append(label + "_addressed_note_changed_since_reply")
    marker_occurrences = 0
    verified_matching_note_ids: list[str] = []
    for current_note_id, current_note in current_notes.items():
        current_response_keys = current_note.get("response_keys")
        if isinstance(current_response_keys, list):
            marker_occurrences += current_response_keys.count(response_key)
        current_bindings = current_note.get("response_bindings")
        if (
            _as_id(current_note.get("author_id_hash"))
            == expected_actor_hash
            and current_note.get("system") is False
            and isinstance(current_bindings, list)
            and sum(
                1
                for item in current_bindings
                if isinstance(item, dict)
                and _as_id(item.get("response_key")) == response_key
                and _as_id(item.get("response_hash")) == response_hash
            )
            == 1
        ):
            verified_matching_note_ids.append(current_note_id)
    verified_matching_note_ids.sort()
    if marker_occurrences != 1:
        errors.append(label + "_response_key_discussion_not_unique")
    if verified_matching_note_ids != [note_id]:
        errors.append(label + "_response_receipt_note_mismatch")
    note = current_notes.get(note_id)
    if note is None:
        errors.append(label + "_note_not_in_current_discussion")
    else:
        if note.get("system") is not False:
            errors.append(label + "_note_must_be_non_system")
        if _as_id(note.get("body_hash")) != posted_body_hash:
            errors.append(label + "_note_body_mismatch")
        response_keys = note.get("response_keys")
        if not isinstance(response_keys, list) or response_keys.count(response_key) != 1:
            errors.append(label + "_response_key_marker_not_unique")
        response_bindings = note.get("response_bindings")
        if (
            not isinstance(response_bindings, list)
            or sum(
                1
                for item in response_bindings
                if isinstance(item, dict)
                and _as_id(item.get("response_key")) == response_key
                and _as_id(item.get("response_hash")) == response_hash
            )
            != 1
        ):
            errors.append(label + "_response_hash_body_mismatch")
        if _as_id(note.get("author_id_hash")) != expected_actor_hash:
            errors.append(label + "_note_author_mismatch")
        if _as_id(note.get("fingerprint")) != _as_id(
            receipt.get("note_fingerprint")
        ):
            errors.append(label + "_note_fingerprint_mismatch")
    return sorted(set(errors))


def _expected_contract_errors(
    snapshot: dict[str, Any],
    expected: Any,
    discussions: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    required = {
        "host_hash",
        "actor_id_hash",
        "project_id",
        "source_project_id",
        "target_project_id",
        "mr_iid",
        "head_sha",
        "diff_version_id",
        "review_context_digest",
        "epoch_digest",
        "inventory_digest",
        "discussion_id",
        "discussion_digest",
    }
    expected = _check_object_keys(
        expected,
        required=required,
        optional=set(),
        label="expected",
        errors=errors,
    )
    mr = snapshot.get("merge_request")
    binding = snapshot.get("binding")
    if not isinstance(mr, dict) or not isinstance(binding, dict):
        raise GuardError("snapshot is missing merge_request or binding")
    diff_version = binding.get("diff_version")
    if not isinstance(diff_version, dict):
        raise GuardError("snapshot is missing diff_version binding")
    actual = {
        "host_hash": _as_id(binding.get("host_hash")),
        "actor_id_hash": _as_id(binding.get("actor_id_hash")),
        "project_id": _as_id(mr.get("project_id")),
        "source_project_id": _as_id(mr.get("source_project_id")),
        "target_project_id": _as_id(mr.get("target_project_id")),
        "mr_iid": _as_id(mr.get("iid")),
        "head_sha": _as_id(mr.get("head_sha")),
        "diff_version_id": _as_id(diff_version.get("id")),
        "review_context_digest": _as_id(
            snapshot.get("review_context_digest")
        ),
        "epoch_digest": _as_id(snapshot.get("epoch_digest")),
        "inventory_digest": _as_id(snapshot.get("inventory_digest")),
    }
    for key, actual_value in actual.items():
        if _as_id(expected.get(key)) != actual_value:
            errors.append("expected_" + key + "_mismatch")
    discussion_id = _as_id(expected.get("discussion_id"))
    if not _nonempty_string(expected.get("discussion_id")):
        errors.append("expected_discussion_id_invalid")
    discussion = discussions.get(discussion_id)
    if discussion is None:
        errors.append("expected_discussion_unknown")
    elif _as_id(expected.get("discussion_digest")) != _as_id(
        discussion.get("digest")
    ):
        errors.append("expected_discussion_digest_mismatch")
    return expected, discussion, sorted(set(errors))


def validate_action_plan(
    snapshot: dict[str, Any],
    plan: dict[str, Any],
    *,
    exact_head_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one bound reply or resolution plan without executing it."""

    _validate_snapshot_integrity(snapshot)
    if not isinstance(plan, dict):
        raise GuardError("plan JSON must be an object")
    errors: list[str] = []
    warnings: list[str] = []
    _check_object_keys(
        plan,
        required={"schema", "mode", "writer", "expected", "actions"},
        optional=set(),
        label="plan",
        errors=errors,
    )
    if plan.get("schema") != PLAN_INPUT_SCHEMA:
        errors.append("unsupported_plan_schema")
    mode = _as_id(plan.get("mode"))
    if mode not in {"plan-only", "reply-only", "resolve-only"}:
        errors.append("invalid_mode")

    writer = _check_object_keys(
        plan.get("writer"),
        required={"id"},
        optional=set(),
        label="writer",
        errors=errors,
    )
    writer_id = _positive_id(writer.get("id"))
    if not writer_id:
        errors.append("writer_id_missing_or_invalid")

    discussions = _snapshot_discussions(snapshot)
    expected, expected_discussion, expected_errors = _expected_contract_errors(
        snapshot, plan.get("expected"), discussions
    )
    errors.extend(expected_errors)
    expected_head = _as_id(expected.get("head_sha"))
    expected_actor_hash = _as_id(expected.get("actor_id_hash"))
    if writer_id and stable_hash(writer_id) != expected_actor_hash:
        errors.append("writer_does_not_match_snapshot_actor")

    actions = plan.get("actions")
    if not isinstance(actions, list):
        actions = []
        errors.append("actions_must_be_array")
    if not actions:
        errors.append("actions_empty")
    if len(actions) > MAX_ACTIONS:
        errors.append("action_limit_exceeded")
    if len(actions) != 1:
        errors.append("exactly_one_action_required")

    action_results: list[dict[str, Any]] = []
    proposed_mutations = False
    reply_write_present = False
    resolve_write_present = False
    for index, raw_action in enumerate(actions[:MAX_ACTIONS]):
        if not isinstance(raw_action, dict):
            errors.append(f"action_{index}:not_an_object")
            continue
        action_errors: list[str] = []
        action_type = _as_id(raw_action.get("type"))
        action_id = _nonempty_string(raw_action.get("id"))
        if not action_id:
            action_errors.append("action_id_missing_or_invalid")
            action_id = f"index-{index}"
        prefix = f"action_{action_id}:"
        operation = _as_id(raw_action.get("operation"))
        discussion_id = _nonempty_string(raw_action.get("discussion_id"))
        if not discussion_id:
            action_errors.append("discussion_id_missing_or_invalid")
        if discussion_id != _as_id(expected.get("discussion_id")):
            action_errors.append("discussion_not_bound_to_expected")
        discussion = discussions.get(discussion_id)

        if action_type == "reply":
            action = _check_object_keys(
                raw_action,
                required={
                    "id",
                    "type",
                    "operation",
                    "discussion_id",
                    "addressed_note_ids",
                    "fix_commit",
                    "response_hash",
                    "posted_body_hash",
                    "dedupe_key",
                    "dedupe",
                    "receipt",
                    "delivery_head",
                },
                optional={"no_change_evidence_hash"},
                label="reply_action",
                errors=action_errors,
            )
            if mode not in {"plan-only", "reply-only"}:
                action_errors.append("reply_not_enabled_by_mode")
            if operation != "post":
                action_errors.append("invalid_reply_operation")
            if operation == "post":
                proposed_mutations = True
                reply_write_present = True
            if "body" in action:
                action_errors.append("raw_body_not_allowed")
            response_hash = _as_id(action.get("response_hash"))
            if not _valid_sha256(response_hash):
                action_errors.append("response_hash_invalid")
            if not _valid_sha256(action.get("posted_body_hash")):
                action_errors.append("posted_body_hash_invalid")
            if _as_id(action.get("delivery_head")) != expected_head:
                action_errors.append("delivery_head_mismatch")

            addressed = action.get("addressed_note_ids")
            if not isinstance(addressed, list) or not addressed:
                action_errors.append("addressed_note_ids_missing")
                addressed = []
            normalized_addressed = [_as_id(item) for item in addressed]
            if any(not item for item in normalized_addressed):
                action_errors.append("addressed_note_id_invalid")
            if len(set(normalized_addressed)) != len(normalized_addressed):
                action_errors.append("addressed_note_ids_duplicate")
            if discussion is not None:
                available_notes = set(_discussion_notes(discussion))
                if any(item not in available_notes for item in normalized_addressed):
                    action_errors.append("addressed_note_unknown")

            fix_commit = _as_id(action.get("fix_commit"))
            if fix_commit == "no-change":
                if not _valid_sha256(action.get("no_change_evidence_hash")):
                    action_errors.append("no_change_evidence_hash_invalid")
            else:
                if fix_commit != expected_head:
                    action_errors.append("fix_commit_not_expected_head")
                if "no_change_evidence_hash" in action:
                    action_errors.append("unexpected_no_change_evidence_hash")

            if _as_id(action.get("dedupe_key")) != make_dedupe_key(
                action, expected
            ):
                action_errors.append("dedupe_key_mismatch")
            response_key = _as_id(action.get("dedupe_key"))
            marker_note_ids: list[str] = []
            verified_note_ids: list[str] = []
            if discussion is not None and _valid_sha256(response_key):
                for note_id, note in _discussion_notes(discussion).items():
                    response_keys = note.get("response_keys")
                    if (
                        not isinstance(response_keys, list)
                        or response_key not in response_keys
                    ):
                        continue
                    marker_note_ids.append(note_id)
                    response_bindings = note.get("response_bindings")
                    if (
                        _as_id(note.get("author_id_hash"))
                        == expected_actor_hash
                        and note.get("system") is False
                        and isinstance(response_bindings, list)
                        and sum(
                            1
                            for item in response_bindings
                            if isinstance(item, dict)
                            and _as_id(item.get("response_key"))
                            == response_key
                            and _as_id(item.get("response_hash"))
                            == response_hash
                        )
                        == 1
                    ):
                        verified_note_ids.append(note_id)
            marker_note_ids.sort()
            verified_note_ids.sort()
            if not marker_note_ids:
                derived_dedupe_status = "clear"
                derived_matching_note_ids: list[str] = []
            elif (
                len(marker_note_ids) == 1
                and marker_note_ids == verified_note_ids
            ):
                derived_dedupe_status = "found"
                derived_matching_note_ids = verified_note_ids
            else:
                derived_dedupe_status = "ambiguous"
                derived_matching_note_ids = marker_note_ids
            if derived_dedupe_status == "found":
                action_errors.append("response_already_exists")
            elif derived_dedupe_status == "ambiguous":
                action_errors.append("response_receipt_ambiguous")
            dedupe = _check_object_keys(
                action.get("dedupe"),
                required={
                    "status",
                    "matching_note_ids",
                    "readback_complete",
                    "readback_epoch_digest",
                },
                optional=set(),
                label="dedupe",
                errors=action_errors,
            )
            dedupe_status = _as_id(dedupe.get("status"))
            matches = dedupe.get("matching_note_ids")
            if not isinstance(matches, list):
                matches = []
                action_errors.append("dedupe_matches_must_be_array")
            normalized_matches = [_as_id(item) for item in matches]
            if (
                any(not item for item in normalized_matches)
                or len(set(normalized_matches)) != len(normalized_matches)
            ):
                action_errors.append("dedupe_matches_ambiguous")
            if dedupe_status != derived_dedupe_status:
                action_errors.append("dedupe_status_snapshot_mismatch")
            if normalized_matches != derived_matching_note_ids:
                action_errors.append("dedupe_matches_snapshot_mismatch")
            if dedupe.get("readback_complete") is not True:
                action_errors.append("dedupe_readback_not_complete")
            if _as_id(dedupe.get("readback_epoch_digest")) != _as_id(
                snapshot.get("epoch_digest")
            ):
                action_errors.append("dedupe_readback_epoch_mismatch")
            if dedupe_status == "clear":
                if normalized_matches:
                    action_errors.append("dedupe_clear_has_matches")
            elif dedupe_status == "found":
                if len(normalized_matches) != 1:
                    action_errors.append("dedupe_found_not_unique")
            elif dedupe_status in {"ambiguous", "unknown"}:
                action_errors.append("dedupe_not_resolved")
            else:
                action_errors.append("dedupe_status_invalid")

            receipt = action.get("receipt")
            receipt_object = _check_object_keys(
                receipt,
                required={"status"},
                optional=set(),
                label="receipt",
                errors=action_errors,
            )
            if _as_id(receipt_object.get("status")) != "not_attempted":
                action_errors.append("post_receipt_must_be_not_attempted")
            if dedupe_status != "clear":
                action_errors.append("post_requires_clear_dedupe")

        elif action_type == "resolve":
            action = _check_object_keys(
                raw_action,
                required={
                    "id",
                    "type",
                    "operation",
                    "discussion_id",
                    "authorization",
                    "all_active_requests_addressed",
                    "reread_discussion_digest",
                    "reply_receipt",
                },
                optional=set(),
                label="resolve_action",
                errors=action_errors,
            )
            if mode not in {"plan-only", "resolve-only"}:
                action_errors.append("resolve_not_enabled_by_mode")
            if operation != "resolve":
                action_errors.append("invalid_resolve_operation")
            if operation == "resolve":
                proposed_mutations = True
                resolve_write_present = True
            authorization = _check_object_keys(
                action.get("authorization"),
                required={"source", "evidence_id", "evidence_hash"},
                optional=set(),
                label="authorization",
                errors=action_errors,
            )
            if _as_id(authorization.get("source")) not in AUTHORIZATION_SOURCES:
                action_errors.append("authorization_source_invalid")
            if not _nonempty_string(authorization.get("evidence_id")):
                action_errors.append("authorization_evidence_id_missing")
            evidence_hash = _as_id(authorization.get("evidence_hash"))
            if not _valid_sha256(evidence_hash) or evidence_hash == "0" * 64:
                action_errors.append("authorization_evidence_hash_invalid")
            if action.get("all_active_requests_addressed") is not True:
                action_errors.append("active_requests_not_confirmed_addressed")
            if discussion is None:
                action_errors.append("unknown_discussion")
            else:
                if _as_id(action.get("reread_discussion_digest")) != _as_id(
                    discussion.get("digest")
                ):
                    action_errors.append("resolve_discussion_not_reread")
                if discussion.get("resolved") is True and operation == "resolve":
                    action_errors.append("discussion_already_resolved")
                discussion_notes = _discussion_notes(discussion)
                if not any(
                    note.get("resolvable") is True
                    and note.get("resolved") is False
                    for note in discussion_notes.values()
                ):
                    action_errors.append(
                        "discussion_has_no_unresolved_resolvable_note"
                    )
                if (
                    discussion.get("resolved") is not False
                    and operation == "resolve"
                ):
                    action_errors.append("discussion_not_confirmed_unresolved")
            action_errors.extend(
                _validate_confirmed_receipt(
                    action.get("reply_receipt"),
                    discussion=discussion,
                    snapshot=snapshot,
                    expected=expected,
                    expected_actor_hash=expected_actor_hash,
                    label="reply_receipt",
                )
            )
        else:
            action_errors.append("unsupported_action_type")

        if action_errors:
            errors.extend(prefix + item for item in action_errors)
        action_results.append(
            {
                "id": action_id,
                "type": action_type,
                "discussion_id": discussion_id,
                "operation": operation,
                "status": "blocked" if action_errors else "valid",
                "blockers": sorted(set(action_errors)),
            }
        )

    if reply_write_present and resolve_write_present:
        errors.append("reply_and_resolve_writes_must_be_separate")
    if resolve_write_present and len(actions) != 1:
        errors.append("at_most_one_resolution_per_plan")
    mutation_requested = proposed_mutations and mode != "plan-only"
    if mutation_requested:
        for proof_error in _exact_head_proof_errors(
            exact_head_proof, snapshot, expected_head
        ):
            errors.append("exact_head_proof_" + proof_error)
    elif proposed_mutations and exact_head_proof is None:
        warnings.append("exact_head_proof_required_before_execution")

    if proposed_mutations and not snapshot.get("mutation_safe"):
        message = "snapshot_not_mutation_safe"
        if mutation_requested:
            errors.append(message)
        else:
            warnings.append(message)
    if proposed_mutations and not snapshot.get("complete"):
        message = "incomplete_pagination_blocks_mutation"
        if mutation_requested:
            errors.append(message)
        else:
            warnings.append(message)

    errors = sorted(set(errors))
    warnings = sorted(set(warnings))
    valid = not errors
    mutation_ready = (
        valid
        and mutation_requested
        and snapshot.get("mutation_safe") is True
    )
    return {
        "schema": PLAN_SCHEMA,
        "ok": valid,
        "valid": valid,
        "mode": mode,
        "writer_id_hash": stable_hash(writer_id) if writer_id else "",
        "proposed_mutations": proposed_mutations,
        "mutation_requested": mutation_requested,
        "mutation_ready": mutation_ready,
        "actions": action_results,
        "errors": errors,
        "warnings": warnings,
    }


def _print_json(value: Any, *, stream: Any = None) -> None:
    if stream is None:
        stream = sys.stdout
    json.dump(value, stream, ensure_ascii=True, indent=2, sort_keys=True)
    stream.write("\n")


def body_hash_from_file(path: str) -> dict[str, Any]:
    body = _normalized_body(_read_text(path))
    return {
        "schema": BODY_HASH_SCHEMA,
        "ok": True,
        "body_hash": stable_hash(body),
    }


def dedupe_key_from_plan(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise GuardError("dedupe-key plan JSON must be an object")
    errors: list[str] = []
    _check_object_keys(
        plan,
        required={"schema", "mode", "writer", "expected", "actions"},
        optional=set(),
        label="plan",
        errors=errors,
    )
    if plan.get("schema") != PLAN_INPUT_SCHEMA:
        errors.append("unsupported_plan_schema")
    if plan.get("mode") not in {"plan-only", "reply-only"}:
        errors.append("invalid_mode")

    writer = _check_object_keys(
        plan.get("writer"),
        required={"id"},
        optional=set(),
        label="writer",
        errors=errors,
    )
    writer_id = _positive_id(writer.get("id"))
    if not writer_id:
        errors.append("writer_id_missing_or_invalid")

    expected_required = {
        "host_hash",
        "actor_id_hash",
        "project_id",
        "source_project_id",
        "target_project_id",
        "mr_iid",
        "head_sha",
        "diff_version_id",
        "review_context_digest",
        "epoch_digest",
        "inventory_digest",
        "discussion_id",
        "discussion_digest",
    }
    expected = _check_object_keys(
        plan.get("expected"),
        required=expected_required,
        optional=set(),
        label="expected",
        errors=errors,
    )
    for key in (
        "host_hash",
        "actor_id_hash",
        "review_context_digest",
        "epoch_digest",
        "inventory_digest",
        "discussion_digest",
    ):
        if not _valid_sha256(expected.get(key)):
            errors.append("expected_" + key + "_invalid")
    for key in (
        "project_id",
        "source_project_id",
        "target_project_id",
        "mr_iid",
        "diff_version_id",
    ):
        if not _positive_id(expected.get(key)):
            errors.append("expected_" + key + "_invalid")
    if not _valid_sha(expected.get("head_sha")):
        errors.append("expected_head_sha_invalid")
    if not _nonempty_string(expected.get("discussion_id")):
        errors.append("expected_discussion_id_invalid")
    if writer_id and stable_hash(writer_id) != _as_id(
        expected.get("actor_id_hash")
    ):
        errors.append("writer_does_not_match_expected_actor")

    actions = plan.get("actions")
    if not isinstance(actions, list) or len(actions) != 1:
        errors.append("exactly_one_action_required")
        actions = []
    action = actions[0] if actions and isinstance(actions[0], dict) else {}
    if actions and not isinstance(actions[0], dict):
        errors.append("action_not_object")
    action = _check_object_keys(
        action,
        required={
            "id",
            "type",
            "operation",
            "discussion_id",
            "addressed_note_ids",
            "fix_commit",
            "response_hash",
            "dedupe",
            "receipt",
            "delivery_head",
        },
        optional={
            "no_change_evidence_hash",
            "dedupe_key",
            "posted_body_hash",
        },
        label="reply_action",
        errors=errors,
    )
    if not _nonempty_string(action.get("id")):
        errors.append("reply_action_id_invalid")
    if action.get("type") != "reply":
        errors.append("reply_action_type_invalid")
    if action.get("operation") != "post":
        errors.append("reply_action_operation_invalid")
    if (
        not _nonempty_string(action.get("discussion_id"))
        or action.get("discussion_id") != expected.get("discussion_id")
    ):
        errors.append("reply_action_discussion_id_invalid")
    addressed = action.get("addressed_note_ids")
    if not isinstance(addressed, list) or not addressed:
        errors.append("reply_action_addressed_note_ids_invalid")
        addressed = []
    normalized_addressed = [_positive_id(item) for item in addressed]
    if (
        any(not item for item in normalized_addressed)
        or len(set(normalized_addressed)) != len(normalized_addressed)
    ):
        errors.append("reply_action_addressed_note_ids_invalid")
    if not _valid_sha256(action.get("response_hash")):
        errors.append("reply_action_response_hash_invalid")
    expected_head = _as_id(expected.get("head_sha"))
    if (
        not _valid_sha(action.get("delivery_head"))
        or _as_id(action.get("delivery_head")) != expected_head
    ):
        errors.append("reply_action_delivery_head_invalid")
    fix_commit = _as_id(action.get("fix_commit"))
    if fix_commit == "no-change":
        if not _valid_sha256(action.get("no_change_evidence_hash")):
            errors.append("reply_action_no_change_evidence_hash_invalid")
    else:
        if fix_commit != expected_head:
            errors.append("reply_action_fix_commit_invalid")
        if "no_change_evidence_hash" in action:
            errors.append("reply_action_unexpected_no_change_evidence_hash")

    dedupe = _check_object_keys(
        action.get("dedupe"),
        required={
            "status",
            "matching_note_ids",
            "readback_complete",
            "readback_epoch_digest",
        },
        optional=set(),
        label="dedupe",
        errors=errors,
    )
    if dedupe.get("status") not in {"clear", "found", "ambiguous", "unknown"}:
        errors.append("dedupe_status_invalid")
    matching_ids = dedupe.get("matching_note_ids")
    if not isinstance(matching_ids, list):
        errors.append("dedupe_matching_note_ids_invalid")
        matching_ids = []
    normalized_matches = [_positive_id(item) for item in matching_ids]
    if (
        any(not item for item in normalized_matches)
        or len(set(normalized_matches)) != len(normalized_matches)
    ):
        errors.append("dedupe_matching_note_ids_invalid")
    if not isinstance(dedupe.get("readback_complete"), bool):
        errors.append("dedupe_readback_complete_invalid")
    if (
        not _valid_sha256(dedupe.get("readback_epoch_digest"))
        or dedupe.get("readback_epoch_digest") != expected.get("epoch_digest")
    ):
        errors.append("dedupe_readback_epoch_digest_invalid")

    receipt = _check_object_keys(
        action.get("receipt"),
        required={"status"},
        optional=set(),
        label="receipt",
        errors=errors,
    )
    if receipt.get("status") != "not_attempted":
        errors.append("receipt_status_invalid")
    if "dedupe_key" in action:
        supplied_key = action.get("dedupe_key")
        if not _valid_sha256(supplied_key):
            errors.append("reply_action_dedupe_key_invalid")
        elif supplied_key != make_dedupe_key(action, expected):
            errors.append("reply_action_dedupe_key_mismatch")
    if "posted_body_hash" in action and not _valid_sha256(
        action.get("posted_body_hash")
    ):
        errors.append("reply_action_posted_body_hash_invalid")
    if errors:
        raise GuardError(
            "dedupe-key plan invalid: " + ",".join(sorted(set(errors)))
        )
    response_key = make_dedupe_key(action, expected)
    return {
        "schema": DEDUPE_OUTPUT_SCHEMA,
        "ok": True,
        "response_key": response_key,
        "marker": "<!-- gitlab-review-response:v2:" + response_key + " -->",
    }


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(
        description=(
            "Evaluate already-fetched GitLab review evidence. "
            "This helper never calls GitLab, git, or glab."
        )
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, parser_class=JsonArgumentParser
    )

    snapshot = subparsers.add_parser(
        "snapshot", help="Build a normalized immutable review epoch."
    )
    snapshot.add_argument("--mr", required=True, help="Fetched merge request JSON.")
    snapshot.add_argument(
        "--discussions", required=True, help="Fetched discussion JSON or NDJSON."
    )
    snapshot.add_argument(
        "--diff-version", required=True, help="Fetched selected diff version JSON."
    )
    snapshot.add_argument("--host", required=True, help="Explicit GitLab hostname.")
    snapshot.add_argument(
        "--actor-id", required=True, help="Visible numeric id from GET /user."
    )
    snapshot.add_argument("--source-ref-head", required=True)
    snapshot.add_argument("--target-ref-head", required=True)
    snapshot.add_argument(
        "--assume-complete-discussion-array",
        action="store_true",
        help="Explicitly declare a raw discussion array complete.",
    )

    compare = subparsers.add_parser("compare", help="Compare two normalized epochs.")
    compare.add_argument("--before", required=True)
    compare.add_argument("--after", required=True)

    verify = subparsers.add_parser(
        "verify-head", help="Verify exact-head and complete pipeline proof inputs."
    )
    verify.add_argument("--snapshot", required=True)
    verify.add_argument("--expected-head", required=True)
    verify.add_argument("--local-head", required=True)
    verify.add_argument("--source-ref-head", required=True)
    verify.add_argument(
        "--pipeline", required=True, help="Fetched pipeline JSON, array, or NDJSON."
    )
    verify.add_argument(
        "--assume-complete-pipelines",
        action="store_true",
        help="Explicitly declare a raw pipeline object or array complete.",
    )

    validate = subparsers.add_parser(
        "validate-plan", help="Validate a reply or resolution action plan."
    )
    validate.add_argument("--snapshot", required=True)
    validate.add_argument("--plan", required=True)
    validate.add_argument("--expected-head", required=True)
    validate.add_argument("--local-head", required=True)
    validate.add_argument("--source-ref-head", required=True)
    validate.add_argument(
        "--pipeline", required=True, help="Fetched pipeline JSON, array, or NDJSON."
    )
    validate.add_argument(
        "--assume-complete-pipelines",
        action="store_true",
        help="Explicitly declare a raw pipeline object or array complete.",
    )

    hash_body = subparsers.add_parser(
        "hash-body", help="Hash one LF-normalized response body without printing it."
    )
    hash_body.add_argument(
        "--body-file",
        required=True,
        help="Bounded response body file, or - for stdin.",
    )

    dedupe_key = subparsers.add_parser(
        "dedupe-key", help="Derive the response key and marker for one reply plan."
    )
    dedupe_key.add_argument("--plan", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "snapshot":
            result = snapshot_from_files(
                args.mr,
                args.discussions,
                args.diff_version,
                host=args.host,
                actor_id=args.actor_id,
                source_ref_head=args.source_ref_head,
                target_ref_head=args.target_ref_head,
                assume_complete_discussion_array=(
                    args.assume_complete_discussion_array
                ),
            )
            _print_json(result)
            return 0 if result["mutation_safe"] else 2
        if args.command == "compare":
            result = compare_snapshots(
                load_json_file(args.before, "before snapshot"),
                load_json_file(args.after, "after snapshot"),
            )
            _print_json(result)
            return 0 if result["ok"] else 2
        if args.command == "verify-head":
            result = verify_exact_head(
                load_json_file(args.snapshot, "snapshot"),
                args.expected_head,
                local_head=args.local_head,
                source_ref_head=args.source_ref_head,
                pipeline_collection=load_pipelines_file(
                    args.pipeline,
                    assume_complete_array=args.assume_complete_pipelines,
                ),
            )
            _print_json(result)
            return 0 if result["ok"] else 2
        if args.command == "validate-plan":
            snapshot_value = load_json_file(args.snapshot, "snapshot")
            proof = verify_exact_head(
                snapshot_value,
                args.expected_head,
                local_head=args.local_head,
                source_ref_head=args.source_ref_head,
                pipeline_collection=load_pipelines_file(
                    args.pipeline,
                    assume_complete_array=args.assume_complete_pipelines,
                ),
            )
            result = validate_action_plan(
                snapshot_value,
                load_json_file(args.plan, "plan"),
                exact_head_proof=proof,
            )
            _print_json(result)
            return 0 if result["ok"] else 2
        if args.command == "hash-body":
            _print_json(body_hash_from_file(args.body_file))
            return 0
        if args.command == "dedupe-key":
            _print_json(dedupe_key_from_plan(load_json_file(args.plan, "plan")))
            return 0
        raise GuardError("unsupported command")
    except (GuardError, OSError, UnicodeError, ValueError) as exc:
        _print_json(
            {
                "schema": ERROR_SCHEMA,
                "ok": False,
                "error": str(exc),
            },
            stream=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
