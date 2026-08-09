#!/usr/bin/env python3
"""Validate and inspect pinned external skill-source dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


LOCKFILE_NAME = "external-dependencies.lock.json"
REPORT_PREFIX = ("docs", "external-dependencies")
TOP_LEVEL_KEYS = {"schemaVersion", "dependencies"}
DEPENDENCY_KEYS = {
    "id",
    "kind",
    "reviewedBy",
    "source",
    "policy",
    "license",
    "audit",
}
SOURCE_KEYS = {"provider", "repository", "commit", "tree"}
POLICY_KEYS = {"mode", "allowInstall", "allowExecute", "allowVendor"}
LICENSE_KEYS = {"root", "exceptions"}
LICENSE_EXCEPTION_KEYS = {"path", "license"}
AUDIT_KEYS = {"reviewedAt", "verdict", "report", "receipt"}
RECEIPT_KEYS = {
    "schemaVersion",
    "dependency",
    "reviewedBy",
    "source",
    "reviewedAt",
    "verdict",
    "license",
    "report",
    "reportSha256",
}

KEBAB_CASE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GITHUB_REPOSITORY_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/"
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$"
)
SPDXISH_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9.+-]*"
    r"(?: (?:AND|OR|WITH) [A-Za-z0-9][A-Za-z0-9.+-]*)*$"
)
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:")
PLACEHOLDER_RE = re.compile(
    r"(?:"
    r"<[^>]+>|\$\{[^}]+\}|"
    r"\b(?:todo|tbd|placeholder|changeme|change-me|replace-me|"
    r"your-owner|your-repo|owner/repo|example\.com)\b"
    r")",
    re.IGNORECASE,
)


class ValidationError(ValueError):
    """Raised when an external dependency lock violates its contract."""


class SourceVerificationError(RuntimeError):
    """Raised when pinned GitHub source identity cannot be proven."""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fail(location: str, message: str) -> None:
    raise ValidationError(f"{location}: {message}")


def _require_object(value: Any, location: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(location, "must be an object")
    actual = set(value)
    missing = sorted(keys - actual)
    unknown = sorted(actual - keys)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append("missing keys " + ", ".join(missing))
        if unknown:
            details.append("unknown keys " + ", ".join(unknown))
        _fail(location, "; ".join(details))
    return value


def _require_string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(location, "must be a nonempty string")
    if value != value.strip():
        _fail(location, "must not have leading or trailing whitespace")
    if PLACEHOLDER_RE.search(value):
        _fail(location, "must not contain a placeholder")
    return value


def _require_safe_posix_path(value: Any, location: str) -> PurePosixPath:
    raw = _require_string(value, location)
    if "\\" in raw:
        _fail(location, "must use POSIX separators, not backslashes")
    if WINDOWS_ABSOLUTE_RE.match(raw):
        _fail(location, "must be relative, not a Windows absolute path")
    if any(ord(character) < 32 for character in raw):
        _fail(location, "must not contain control characters")

    path = PurePosixPath(raw)
    if path.is_absolute():
        _fail(location, "must be a relative path")
    if raw != path.as_posix():
        _fail(location, "must be a normalized POSIX path")
    if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        _fail(location, "must not contain empty, current, or parent segments")
    return path


def _path_under_root(root: Path, relative: PurePosixPath) -> Path:
    return root.joinpath(*relative.parts)


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"JSON object: duplicate key {key!r}")
        result[key] = value
    return result


def _load_json(path: Path, location: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValidationError(f"{location}: does not exist or is not a file: {path}")
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_json_keys)
    except ValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(
            f"{location}: cannot read valid nonblank UTF-8 JSON from {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"{location}: must contain a JSON object")
    return payload


def _validate_source(value: Any, location: str) -> tuple[str, str, str, str]:
    source = _require_object(value, location, SOURCE_KEYS)
    if source["provider"] != "github":
        _fail(f"{location}.provider", "must equal 'github'")

    repository = _require_string(source["repository"], f"{location}.repository")
    if not GITHUB_REPOSITORY_RE.fullmatch(repository) or repository.endswith(".git"):
        _fail(f"{location}.repository", "must be a strict GitHub owner/repo name")

    commit = _require_string(source["commit"], f"{location}.commit")
    tree = _require_string(source["tree"], f"{location}.tree")
    if not SHA_RE.fullmatch(commit):
        _fail(f"{location}.commit", "must be exactly 40 lowercase hexadecimal characters")
    if not SHA_RE.fullmatch(tree):
        _fail(f"{location}.tree", "must be exactly 40 lowercase hexadecimal characters")
    return ("github", repository, commit, tree)


def _validate_policy(value: Any, location: str) -> None:
    policy = _require_object(value, location, POLICY_KEYS)
    if policy["mode"] != "reference-only":
        _fail(f"{location}.mode", "must equal 'reference-only'")
    for key in ("allowInstall", "allowExecute", "allowVendor"):
        if policy[key] is not False:
            _fail(f"{location}.{key}", "must be the boolean false")


def _validate_spdxish(value: Any, location: str) -> str:
    license_name = _require_string(value, location)
    if not SPDXISH_RE.fullmatch(license_name):
        _fail(location, "must be a nonempty SPDX-style license identifier or expression")
    return license_name


def _validate_license(value: Any, location: str) -> None:
    license_data = _require_object(value, location, LICENSE_KEYS)
    _validate_spdxish(license_data["root"], f"{location}.root")
    exceptions = license_data["exceptions"]
    if not isinstance(exceptions, list):
        _fail(f"{location}.exceptions", "must be an array")

    seen_paths: set[str] = set()
    for index, raw_exception in enumerate(exceptions):
        exception_location = f"{location}.exceptions[{index}]"
        exception = _require_object(
            raw_exception,
            exception_location,
            LICENSE_EXCEPTION_KEYS,
        )
        path = _require_safe_posix_path(
            exception["path"],
            f"{exception_location}.path",
        ).as_posix()
        if path in seen_paths:
            _fail(f"{exception_location}.path", "duplicates an earlier exception path")
        seen_paths.add(path)
        _validate_spdxish(exception["license"], f"{exception_location}.license")


def _require_existing_audit_file(
    value: Any,
    location: str,
    root: Path,
) -> tuple[str, Path]:
    relative = _require_safe_posix_path(value, location)
    if relative.parts[: len(REPORT_PREFIX)] != REPORT_PREFIX or len(
        relative.parts
    ) <= len(REPORT_PREFIX):
        _fail(location, "must be a file below docs/external-dependencies")

    local_path = _path_under_root(root, relative)
    if not local_path.is_file() or local_path.is_symlink():
        _fail(location, "must name an existing regular file")

    try:
        resolved_root = root.resolve(strict=True)
        resolved_base = (root / REPORT_PREFIX[0] / REPORT_PREFIX[1]).resolve(strict=True)
        resolved_file = local_path.resolve(strict=True)
        resolved_base.relative_to(resolved_root)
        resolved_file.relative_to(resolved_base)
    except (OSError, ValueError) as exc:
        raise ValidationError(
            f"{location}: resolved path must stay below docs/external-dependencies"
        ) from exc
    return relative.as_posix(), local_path


def _normalized_report_sha256(path: Path, location: str) -> str:
    try:
        report = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError(
            f"{location}: cannot read the report as UTF-8 text"
        ) from exc
    normalized = report.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        _fail(location, "must contain a nonblank Markdown report")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_audit(
    value: Any,
    location: str,
    root: Path,
    dependency_id: str,
    reviewed_by: list[str],
    source: dict[str, Any],
    license_data: dict[str, Any],
) -> None:
    audit = _require_object(value, location, AUDIT_KEYS)
    reviewed_at = _require_string(audit["reviewedAt"], f"{location}.reviewedAt")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed_at):
        _fail(f"{location}.reviewedAt", "must use YYYY-MM-DD")
    try:
        if date.fromisoformat(reviewed_at).isoformat() != reviewed_at:
            raise ValueError
    except ValueError as exc:
        raise ValidationError(
            f"{location}.reviewedAt: must be a real calendar date in YYYY-MM-DD form"
        ) from exc

    if audit["verdict"] != "isolate":
        _fail(f"{location}.verdict", "must equal 'isolate'")

    report, report_path = _require_existing_audit_file(
        audit["report"],
        f"{location}.report",
        root,
    )
    receipt_name, receipt_path = _require_existing_audit_file(
        audit["receipt"],
        f"{location}.receipt",
        root,
    )
    if not report.endswith(".md"):
        _fail(f"{location}.report", "must use the .md extension")
    if not receipt_name.endswith(".json"):
        _fail(f"{location}.receipt", "must use the .json extension")
    if report == receipt_name:
        _fail(f"{location}.receipt", "must differ from the Markdown report path")

    report_sha256 = _normalized_report_sha256(
        report_path,
        f"{location}.report",
    )
    receipt_location = f"{location}.receipt payload"
    receipt = _require_object(
        _load_json(receipt_path, receipt_location),
        receipt_location,
        RECEIPT_KEYS,
    )
    if type(receipt["schemaVersion"]) is not int or receipt["schemaVersion"] != 1:
        _fail(f"{receipt_location}.schemaVersion", "must be the integer 1")

    expected_receipt = {
        "schemaVersion": 1,
        "dependency": dependency_id,
        "reviewedBy": reviewed_by,
        "source": source,
        "reviewedAt": reviewed_at,
        "verdict": audit["verdict"],
        "license": license_data,
        "report": report,
        "reportSha256": report_sha256,
    }
    if receipt != expected_receipt:
        _fail(
            receipt_location,
            "must exactly match dependency, source, audit, license, and report in the lockfile",
        )


def validate_lockfile(root: Path | str, lock_path: Path | str | None = None) -> dict[str, Any]:
    """Validate a dependency lock without network access or filesystem writes."""

    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise ValidationError(f"repository root does not exist or is not a directory: {root_path}")

    if lock_path is None:
        resolved_lock_path = root_path / LOCKFILE_NAME
    else:
        requested_lock_path = Path(lock_path)
        resolved_lock_path = (
            requested_lock_path
            if requested_lock_path.is_absolute()
            else root_path / requested_lock_path
        )

    payload = _require_object(
        _load_json(resolved_lock_path, "lockfile"),
        "lockfile",
        TOP_LEVEL_KEYS,
    )
    if type(payload["schemaVersion"]) is not int or payload["schemaVersion"] != 1:
        _fail("lockfile.schemaVersion", "must be the integer 1")

    dependencies = payload["dependencies"]
    if not isinstance(dependencies, list):
        _fail("lockfile.dependencies", "must be an array")

    seen_ids: set[str] = set()
    seen_sources: set[tuple[str, str, str, str]] = set()
    for index, raw_dependency in enumerate(dependencies):
        location = f"lockfile.dependencies[{index}]"
        dependency = _require_object(raw_dependency, location, DEPENDENCY_KEYS)

        dependency_id = _require_string(dependency["id"], f"{location}.id")
        if not KEBAB_CASE_RE.fullmatch(dependency_id):
            _fail(f"{location}.id", "must be unique lowercase kebab-case")
        if dependency_id in seen_ids:
            _fail(f"{location}.id", "duplicates an earlier dependency id")
        seen_ids.add(dependency_id)

        if dependency["kind"] != "agent-skill-source":
            _fail(f"{location}.kind", "must equal 'agent-skill-source'")

        reviewed_by = dependency["reviewedBy"]
        if not isinstance(reviewed_by, list) or not reviewed_by:
            _fail(f"{location}.reviewedBy", "must be a nonempty array")
        seen_consumers: set[str] = set()
        for consumer_index, raw_consumer in enumerate(reviewed_by):
            consumer_location = f"{location}.reviewedBy[{consumer_index}]"
            consumer = _require_string(raw_consumer, consumer_location)
            if not KEBAB_CASE_RE.fullmatch(consumer):
                _fail(consumer_location, "must be a plugin directory name")
            if consumer in seen_consumers:
                _fail(consumer_location, "duplicates an earlier consumer")
            seen_consumers.add(consumer)
            if not (root_path / "plugins" / consumer).is_dir():
                _fail(consumer_location, f"missing plugins/{consumer}")

        source_key = _validate_source(dependency["source"], f"{location}.source")
        if source_key in seen_sources:
            _fail(f"{location}.source", "duplicates an earlier dependency source")
        seen_sources.add(source_key)

        _validate_policy(dependency["policy"], f"{location}.policy")
        _validate_license(dependency["license"], f"{location}.license")
        _validate_audit(
            dependency["audit"],
            f"{location}.audit",
            root_path,
            dependency_id,
            dependency["reviewedBy"],
            dependency["source"],
            dependency["license"],
        )

    return payload


Requester = Callable[[Request], Any]


def _default_requester(request: Request) -> bytes:
    with urlopen(request, timeout=20) as response:
        return response.read()


def _parse_github_response(raw_response: Any, url: str) -> dict[str, Any]:
    if isinstance(raw_response, dict):
        return raw_response
    if hasattr(raw_response, "read"):
        raw_response = raw_response.read()
    if isinstance(raw_response, bytes):
        try:
            raw_response = raw_response.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceVerificationError(
                f"GitHub returned non-UTF-8 metadata for {url}"
            ) from exc
    if isinstance(raw_response, str):
        try:
            payload = json.loads(
                raw_response,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            raise SourceVerificationError(
                f"GitHub returned invalid JSON metadata for {url}: {exc}"
            ) from exc
        if isinstance(payload, dict):
            return payload
    raise SourceVerificationError(f"GitHub returned a non-object response for {url}")


def verify_sources(
    root: Path | str,
    lock_path: Path | str | None = None,
    dependency_id: str | None = None,
    *,
    requester: Requester | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    """Verify pinned GitHub commit and tree identities without fetching source trees."""

    payload = validate_lockfile(root, lock_path)
    dependencies = payload["dependencies"]
    selected = dependencies
    if dependency_id is not None:
        selected = [
            dependency
            for dependency in dependencies
            if dependency["id"] == dependency_id
        ]
        if not selected:
            raise SourceVerificationError(
                f"unknown external dependency id: {dependency_id}"
            )

    environment = os.environ if environ is None else environ
    token = environment.get("GITHUB_TOKEN") or environment.get("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "plug-n-skills-external-dependency-verifier",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if isinstance(token, str) and token:
        if token != token.strip() or any(
            ord(character) < 33 or ord(character) > 126 for character in token
        ):
            raise SourceVerificationError(
                "GitHub token contains unsupported whitespace or control characters"
            )
        headers["Authorization"] = f"Bearer {token}"

    perform_request = _default_requester if requester is None else requester
    verified: list[dict[str, str]] = []
    for dependency in selected:
        source = dependency["source"]
        url = (
            f"https://api.github.com/repos/{source['repository']}"
            f"/git/commits/{source['commit']}"
        )
        try:
            request = Request(url, headers=headers, method="GET")
        except (TypeError, ValueError):
            raise SourceVerificationError(
                f"could not construct a safe GitHub metadata request for {dependency['id']}"
            ) from None
        try:
            raw_response = perform_request(request)
        except HTTPError as exc:
            raise SourceVerificationError(
                f"GitHub metadata request failed for {dependency['id']} with HTTP {exc.code}"
            ) from exc
        except (URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise SourceVerificationError(
                f"GitHub metadata request failed for {dependency['id']}: {reason}"
            ) from exc

        response = _parse_github_response(raw_response, url)
        actual_commit = response.get("sha")
        tree = response.get("tree")
        actual_tree = tree.get("sha") if isinstance(tree, dict) else None
        if actual_commit != source["commit"]:
            raise SourceVerificationError(
                f"{dependency['id']}: GitHub commit mismatch; "
                f"expected {source['commit']}, got {actual_commit!r}"
            )
        if actual_tree != source["tree"]:
            raise SourceVerificationError(
                f"{dependency['id']}: GitHub tree mismatch; "
                f"expected {source['tree']}, got {actual_tree!r}"
            )
        verified.append(
            {
                "id": dependency["id"],
                "url": url,
                "commit": actual_commit,
                "tree": actual_tree,
            }
        )
    return verified


def _common_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--root",
        type=Path,
        default=argparse.SUPPRESS,
        help="repository root (default: root containing this script)",
    )
    parser.add_argument(
        "--lockfile",
        type=Path,
        default=argparse.SUPPRESS,
        help=f"lockfile path (default: <root>/{LOCKFILE_NAME})",
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    common = _common_cli_parser()
    parser = argparse.ArgumentParser(
        description=__doc__,
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "validate",
        parents=[common],
        help="validate the lockfile",
    )
    subparsers.add_parser(
        "list",
        parents=[common],
        help="list pinned dependencies",
    )
    show_parser = subparsers.add_parser(
        "show",
        parents=[common],
        help="show one pinned dependency as JSON",
    )
    show_parser.add_argument("id", help="dependency id")
    verify_parser = subparsers.add_parser(
        "verify-source",
        parents=[common],
        help="verify pinned GitHub commit/tree metadata without downloading source",
    )
    verify_parser.add_argument(
        "id",
        nargs="?",
        help="optional dependency id (default: verify every dependency)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = getattr(args, "root", repo_root())
    lockfile = getattr(args, "lockfile", None)
    if args.command == "verify-source":
        try:
            verified = verify_sources(root, lockfile, args.id)
        except (ValidationError, SourceVerificationError) as exc:
            print(f"External source verification failed: {exc}", file=sys.stderr)
            return 1
        for result in verified:
            print(
                f"{result['id']}\tcommit={result['commit']}\ttree={result['tree']}"
            )
        return 0

    try:
        payload = validate_lockfile(root, lockfile)
    except ValidationError as exc:
        print(f"External dependency validation failed: {exc}", file=sys.stderr)
        return 1

    dependencies = payload["dependencies"]
    if args.command == "validate":
        print(f"External dependency lock is valid ({len(dependencies)} dependencies)")
        return 0
    if args.command == "list":
        for dependency in dependencies:
            source = dependency["source"]
            print(
                f"{dependency['id']}\t{source['provider']}:{source['repository']}"
                f"@{source['commit']}\ttree={source['tree']}"
            )
        return 0
    if args.command == "show":
        for dependency in dependencies:
            if dependency["id"] == args.id:
                print(json.dumps(dependency, indent=2, sort_keys=True))
                return 0
        print(f"Unknown external dependency id: {args.id}", file=sys.stderr)
        return 2

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
