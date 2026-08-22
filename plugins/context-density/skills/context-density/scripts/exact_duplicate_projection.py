#!/usr/bin/env python3
"""Project contiguous exact-duplicate text records without dropping unique data.

The caller must classify the evidence surface before invoking this helper. It
does not decide whether Git state, malformed output, authority, effects,
provenance, or other exact/order-sensitive evidence is safe to reduce.

Input must already be safe for model visibility. The helper never writes the
raw input. It emits JSON with either ``mode=project`` and a deterministic
run-length projection, or ``mode=keep_raw`` when UTF-8 decoding fails, no exact
duplicates exist, or the projection is not smaller than the source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA = "context_density.exact_duplicate_projection.v1"
RAW_ID_RE = re.compile(r"raw://[^\s`]+\Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def keep_raw_result(raw: bytes, raw_id: str, reason: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "mode": "keep_raw",
        "reason": reason,
        "raw_id": raw_id,
        "raw_sha256": sha256_bytes(raw),
        "input_bytes": len(raw),
        "projection": None,
    }


def project_bytes(raw: bytes, raw_id: str) -> dict[str, Any]:
    """Return a never-larger contiguous exact-duplicate projection."""
    if not RAW_ID_RE.fullmatch(raw_id):
        raise ValueError("raw_id must be a whitespace-free raw:// identity")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return keep_raw_result(raw, raw_id, "non_utf8_input")

    records = text.splitlines(keepends=True)
    if not records and text:
        records = [text]
    if not records:
        return keep_raw_result(raw, raw_id, "empty_input")

    runs: list[tuple[str, int]] = []
    for record in records:
        if runs and runs[-1][0] == record:
            previous, count = runs[-1]
            runs[-1] = (previous, count + 1)
        else:
            runs.append((record, 1))

    omitted = sum(count - 1 for _, count in runs)
    if omitted == 0:
        return keep_raw_result(raw, raw_id, "no_contiguous_exact_duplicates")

    raw_sha = sha256_bytes(raw)
    header = (
        f"[exact-line-projection raw_id={raw_id} raw_sha256={raw_sha} "
        f"input_records={len(records)} emitted_records={len(runs)} "
        f"omitted_exact_duplicates={omitted}]\n"
    )
    projected_parts = [header]
    run_receipts: list[dict[str, Any]] = []
    for index, (record, count) in enumerate(runs):
        projected_parts.append(record)
        receipt = {
            "run_index": index,
            "count": count,
            "omitted": count - 1,
            "record_sha256": sha256_bytes(record.encode("utf-8")),
        }
        run_receipts.append(receipt)
        if count > 1:
            if not record.endswith(("\n", "\r")):
                projected_parts.append("\n")
            projected_parts.append(
                "[exact-duplicate-run "
                f"count={count} omitted={count - 1} "
                f"record_sha256={receipt['record_sha256']}]\n"
            )

    projection = "".join(projected_parts)
    projected_bytes = projection.encode("utf-8")
    if len(projected_bytes) >= len(raw):
        return keep_raw_result(raw, raw_id, "projection_not_smaller")

    return {
        "schema": SCHEMA,
        "mode": "project",
        "reason": "contiguous_exact_duplicates_only",
        "raw_id": raw_id,
        "raw_sha256": raw_sha,
        "input_bytes": len(raw),
        "input_records": len(records),
        "emitted_records": len(runs),
        "omitted_exact_duplicates": omitted,
        "projected_bytes": len(projected_bytes),
        "reduction_pct": round((1 - len(projected_bytes) / len(raw)) * 100, 3),
        "projection_sha256": sha256_bytes(projected_bytes),
        "raw_recovery_required": True,
        "runs": run_receipts,
        "projection": projection,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UTF-8 tool-output file")
    parser.add_argument("--raw-id", required=True)
    parser.add_argument(
        "--model-safe-input",
        action="store_true",
        help="required acknowledgement that secrets were redacted upstream",
    )
    args = parser.parse_args(argv)
    if not args.model_safe_input:
        parser.error("--model-safe-input is required; redact before model visibility")
    try:
        result = project_bytes(args.input.read_bytes(), args.raw_id)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
