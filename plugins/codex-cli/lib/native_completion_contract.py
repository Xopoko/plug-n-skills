"""Strict parser for producer-owned native completion receipts."""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any, Mapping, Sequence


MAX_RECEIPT_BYTES = 256 * 1024
MAX_POINTER_LENGTH = 300
MAX_POINTER_SEGMENTS = 24
BASE_FIELDS = frozenset(
    {
        "schema",
        "outcome",
        "exitCode",
        "startedAt",
        "completedAt",
        "elapsedSeconds",
        "transitionCount",
    }
)


class NativeCompletionContractError(ValueError):
    """The receipt does not match its reserved producer contract."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise NativeCompletionContractError(
                "receipt contains a duplicate JSON field"
            )
        result[key] = value
    return result


def _reject_non_json_constant(_: str) -> None:
    raise NativeCompletionContractError("receipt must not contain non-JSON numbers")


def parse_json_pointer(value: Any) -> tuple[str, ...]:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or len(value) > MAX_POINTER_LENGTH
    ):
        raise NativeCompletionContractError(
            "receipt pointer must be a bounded non-root JSON Pointer"
        )
    raw_segments = value[1:].split("/")
    if not raw_segments or len(raw_segments) > MAX_POINTER_SEGMENTS:
        raise NativeCompletionContractError(
            "receipt pointer has too many path segments"
        )
    segments: list[str] = []
    for raw in raw_segments:
        decoded: list[str] = []
        index = 0
        while index < len(raw):
            character = raw[index]
            if character != "~":
                decoded.append(character)
                index += 1
                continue
            if index + 1 >= len(raw) or raw[index + 1] not in {"0", "1"}:
                raise NativeCompletionContractError(
                    "receipt pointer contains an invalid escape"
                )
            decoded.append("~" if raw[index + 1] == "0" else "/")
            index += 2
        segment = "".join(decoded)
        if len(segment) > 100 or any(
            ord(character) < 32 or ord(character) == 127 for character in segment
        ):
            raise NativeCompletionContractError(
                "receipt pointer contains an invalid path segment"
            )
        segments.append(segment)
    return tuple(segments)


def validate_bounded_json_value(value: Any) -> Any:
    nodes = 0

    def visit(current: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > 128 or depth > 8:
            raise NativeCompletionContractError(
                "identity assertion value is too complex"
            )
        if current is None or isinstance(current, bool):
            return
        if isinstance(current, str):
            if len(current) > 1000 or any(
                ord(character) < 32 and character not in "\t\n\r"
                for character in current
            ):
                raise NativeCompletionContractError(
                    "identity assertion string is outside the supported range"
                )
            return
        if isinstance(current, int):
            if abs(current) > 2**63 - 1:
                raise NativeCompletionContractError(
                    "identity assertion integer is outside the supported range"
                )
            return
        if isinstance(current, float):
            if not math.isfinite(current):
                raise NativeCompletionContractError(
                    "identity assertion number must be finite"
                )
            return
        if isinstance(current, list):
            if len(current) > 64:
                raise NativeCompletionContractError(
                    "identity assertion array is too large"
                )
            for item in current:
                visit(item, depth + 1)
            return
        if isinstance(current, dict):
            if len(current) > 64:
                raise NativeCompletionContractError(
                    "identity assertion object is too large"
                )
            for key, item in current.items():
                if not isinstance(key, str) or len(key) > 100:
                    raise NativeCompletionContractError(
                        "identity assertion object has an invalid key"
                    )
                visit(item, depth + 1)
            return
        raise NativeCompletionContractError(
            "identity assertion must contain only JSON values"
        )

    visit(value, 0)
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(encoded) > 16 * 1024:
        raise NativeCompletionContractError(
            "identity assertion value exceeds the fixed size limit"
        )
    return value


def _parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise NativeCompletionContractError(
            f"{label} must be a bounded ISO-8601 timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NativeCompletionContractError(
            f"{label} must be an ISO-8601 timestamp"
        ) from exc
    if parsed.tzinfo is None:
        raise NativeCompletionContractError(f"{label} must include a timezone")
    return parsed


def _require_number(value: Any, label: str, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NativeCompletionContractError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0 or number > maximum:
        raise NativeCompletionContractError(f"{label} is outside the supported range")
    return number


def _resolve_pointer(value: Any, segments: Sequence[str]) -> Any:
    current = value
    for segment in segments:
        if isinstance(current, dict):
            if segment not in current:
                raise NativeCompletionContractError(
                    "receipt is missing a reserved identity field"
                )
            current = current[segment]
            continue
        if isinstance(current, list) and segment.isdigit():
            index = int(segment)
            if index >= len(current):
                raise NativeCompletionContractError(
                    "receipt is missing a reserved identity field"
                )
            current = current[index]
            continue
        raise NativeCompletionContractError(
            "receipt is missing a reserved identity field"
        )
    return current


def _json_values_equal(left: Any, right: Any) -> bool:
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        return bool(left == right)
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _json_values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_values_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return bool(left == right)


def parse_receipt_bytes(raw: bytes, expectation: Mapping[str, Any]) -> dict[str, Any]:
    if len(raw) > MAX_RECEIPT_BYTES:
        raise NativeCompletionContractError(
            f"receipt exceeds the {MAX_RECEIPT_BYTES}-byte limit"
        )
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_non_json_constant,
        )
    except UnicodeDecodeError as exc:
        raise NativeCompletionContractError("receipt must be UTF-8 JSON") from exc
    except (json.JSONDecodeError, RecursionError) as exc:
        raise NativeCompletionContractError(
            "receipt must contain bounded valid JSON"
        ) from exc
    return validate_receipt(payload, expectation)


def validate_receipt(payload: Any, expectation: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(payload, dict)
        or len(payload) > 64
        or not BASE_FIELDS.issubset(payload)
    ):
        raise NativeCompletionContractError(
            "receipt does not contain the fixed completion envelope"
        )
    if payload["schema"] != expectation["schema"]:
        raise NativeCompletionContractError(
            "receipt schema does not match the reservation"
        )

    outcome = payload["outcome"]
    if not isinstance(outcome, str) or len(outcome) > 64:
        raise NativeCompletionContractError("receipt outcome is not recognized")
    terminal_outcomes = expectation["terminalOutcomes"]
    if outcome != "running" and outcome not in terminal_outcomes:
        raise NativeCompletionContractError("receipt outcome is not recognized")

    exit_code = payload["exitCode"]
    if isinstance(exit_code, bool) or (
        exit_code is not None and not isinstance(exit_code, int)
    ):
        raise NativeCompletionContractError("exitCode must be an integer or null")
    _parse_timestamp(payload["startedAt"], "startedAt")
    _require_number(payload["elapsedSeconds"], "elapsedSeconds", 7 * 24 * 3600)
    transition_count = payload["transitionCount"]
    if (
        isinstance(transition_count, bool)
        or not isinstance(transition_count, int)
        or transition_count < 0
        or transition_count > 100_000
    ):
        raise NativeCompletionContractError(
            "transitionCount is outside the supported range"
        )

    if outcome == "running":
        if exit_code is not None or payload["completedAt"] is not None:
            raise NativeCompletionContractError("running receipt has terminal fields")
    else:
        if exit_code != terminal_outcomes[outcome]:
            raise NativeCompletionContractError(
                "terminal outcome and exitCode are inconsistent"
            )
        _parse_timestamp(payload["completedAt"], "completedAt")

    result_path = _resolve_pointer(payload, expectation["resultPathPointer"])
    if result_path != expectation["resultPath"]:
        raise NativeCompletionContractError(
            "receipt result path does not match the reservation"
        )

    for assertion in expectation["assertions"]:
        outcomes = assertion["outcomes"]
        if outcomes is not None and outcome not in outcomes:
            continue
        actual = _resolve_pointer(payload, assertion["pointer"])
        if not _json_values_equal(actual, assertion["value"]):
            raise NativeCompletionContractError("receipt identity assertion failed")
    return payload
