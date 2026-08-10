#!/usr/bin/env python3
"""Prepare and verify a local-only GitLab publication binding."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlsplit, urlunsplit


RECEIPT_SCHEMA = "gitlab_push_binding_guard.receipt.v1"
ERROR_SCHEMA = "gitlab_push_binding_guard.error.v1"
EXECUTION_SCHEMA = "gitlab_push_binding_guard.execution.v1"
PUSH_REMOTE = "gitlab-review-bound"
MAX_INPUT_BYTES = 1024 * 1024
MAX_GIT_OUTPUT_BYTES = 16 * 1024 * 1024
MAX_TOOL_BYTES = 64 * 1024 * 1024
MAX_SCOPED_CREDENTIAL_SUBSECTIONS = 128
MAX_CONFIG_SUBSECTION_BYTES = 4096
GIT_TIMEOUT_SECONDS = 30
SOURCE_INERT_GIT_ENVIRONMENT = frozenset({"GIT_PAGER"})
EXECUTION_UNSET_CASE_INSENSITIVE = (
    "ALL_PROXY",
    "CURL_CA_BUNDLE",
    "CURL_HOME",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "NETRC",
    "REQUESTS_CA_BUNDLE",
    "SSH_ASKPASS",
    "SSH_ASKPASS_REQUIRE",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "USERPROFILE",
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
REMOTE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
URL_PATH_RE = re.compile(r"^/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.git$")
VERSION_RE = re.compile(r"^git version ([0-9]+(?:\.[0-9]+){1,3})(?: [ -~]{1,120})?$")

COUNT_KEYS = (
    "configured_push_urls",
    "effective_push_urls",
    "range_objects",
    "transaction_refs",
)
HASH_KEYS = (
    "api_binding_sha256",
    "branch_ref_sha256",
    "config_graph_sha256",
    "credential_helpers_sha256",
    "endpoint_sha256",
    "execution_plan_sha256",
    "expected_old_sha256",
    "git_toolchain_sha256",
    "object_closure_sha256",
    "prepared_sha256",
    "prior_receipt_sha256",
    "runtime_environment_sha256",
    "source_identity_sha256",
    "transaction_config_sha256",
    "transaction_directory_sha256",
    "transaction_token_sha256",
    "transaction_tree_sha256",
)
RECEIPT_KEYS = {
    "schema",
    "phase",
    "status",
    "reason_codes",
    "git_version",
    "object_format",
    "counts",
    "hashes",
    "receipt_sha256",
}
REPORT_ONLY_CODES = {
    "AMBIENT_PROXY",
    "ANCESTRY_UNPROVEN",
    "CONFIGURATION_DRIFT",
    "DUPLICATE_PUSH_URL",
    "ENDPOINT_MISMATCH",
    "HTTPS_BASELINE_UNAVAILABLE",
    "INCOMPLETE_OBJECT_CLOSURE",
    "LOCAL_GIT_FAILED",
    "LOCAL_GIT_OUTPUT_LIMIT",
    "LOCAL_GIT_TIMEOUT",
    "PREPARED_EQUALS_EXPECTED",
    "SOURCE_IDENTITY_DRIFT",
    "TRANSACTION_DRIFT",
    "TRANSACTION_PREPARE_FAILED",
    "UNSAFE_EVIDENCE_FILE",
    "UNSAFE_REPOSITORY",
    "UNSAFE_TRANSACTION_PATH",
    "UNSUPPORTED_GIT",
    "UNSUPPORTED_OBJECT_FORMAT",
}
ERROR_CODES = {
    "ARGUMENT_ERROR",
    "EVIDENCE_SCHEMA_INVALID",
    "GIT_UNAVAILABLE",
    "INTERNAL_ERROR",
    "RECEIPT_INVALID",
    "TRANSACTION_ALREADY_EXISTS",
}


class GuardError(ValueError):
    """A malformed input or invalid receipt with a redaction-safe code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code if code in ERROR_CODES else "INTERNAL_ERROR"


class ReportOnly(RuntimeError):
    """A safe refusal whose cause can be emitted without private data."""

    def __init__(self, *codes: str):
        safe_codes = sorted({code for code in codes if code in REPORT_ONLY_CODES})
        super().__init__("REPORT_ONLY")
        self.codes = safe_codes or ["LOCAL_GIT_FAILED"]


class JsonArgumentParser(argparse.ArgumentParser):
    """Turn usage failures into the fixed JSON error contract."""

    def error(self, message: str) -> NoReturn:
        del message
        raise GuardError("ARGUMENT_ERROR")

    def exit(self, status: int = 0, message: str | None = None) -> NoReturn:
        if message:
            self._print_message(message, sys.stderr)
        if status == 0:
            raise ParserExit
        raise GuardError("ARGUMENT_ERROR")


class ParserExit(Exception):
    """A successful argparse help exit."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_text(value: str) -> str:
    return _digest_bytes(value.encode("utf-8"))


def _stable_hash(value: Any) -> str:
    return _digest_text(_canonical(value))


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise GuardError("EVIDENCE_SCHEMA_INVALID")
        value[key] = item
    return value


def _safe_path_text(path: Path) -> bool:
    text = str(path)
    return bool(
        path.is_absolute()
        and len(text.encode("utf-8")) <= 4096
        and not any(
            ord(character) < 0x20 or ord(character) == 0x7F for character in text
        )
    )


def _safe_parent_chain(path: Path) -> bool:
    private_anchor = False
    for parent in path.parents:
        try:
            metadata = parent.lstat()
        except OSError:
            return False
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            return False
        if hasattr(os, "geteuid") and metadata.st_uid not in {0, os.geteuid()}:
            return False
        permissions = stat.S_IMODE(metadata.st_mode)
        if (
            hasattr(os, "geteuid")
            and metadata.st_uid == os.geteuid()
            and permissions & 0o077 == 0
        ):
            private_anchor = True
        if permissions & 0o022:
            sticky = bool(metadata.st_mode & stat.S_ISVTX)
            if not (private_anchor and sticky):
                return False
    return True


def _private_regular_file(path: Path) -> bool:
    try:
        metadata = path.lstat()
        canonical = path.resolve(strict=True)
    except OSError:
        return False
    if canonical != path or not _safe_path_text(path):
        return False
    if not stat.S_ISREG(metadata.st_mode):
        return False
    if metadata.st_nlink != 1 or metadata.st_mode & 0o077:
        return False
    if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
        return False
    return True


def _read_private_bytes(path: Path) -> bytes:
    if (
        not _safe_path_text(path)
        or not _safe_parent_chain(path)
        or path.resolve(strict=False) != path
    ):
        raise ReportOnly("UNSAFE_EVIDENCE_FILE")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ReportOnly("UNSAFE_EVIDENCE_FILE") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_mode & 0o077
            or before.st_size > MAX_INPUT_BYTES
            or (hasattr(os, "geteuid") and before.st_uid != os.geteuid())
        ):
            raise ReportOnly("UNSAFE_EVIDENCE_FILE")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                raise ReportOnly("UNSAFE_EVIDENCE_FILE")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise ReportOnly("UNSAFE_EVIDENCE_FILE")
        after = os.fstat(descriptor)
        final_path = path.lstat()
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_uid",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(
            getattr(before, field) != getattr(after, field) for field in stable_fields
        ):
            raise ReportOnly("UNSAFE_EVIDENCE_FILE")
        if final_path.st_dev != after.st_dev or final_path.st_ino != after.st_ino:
            raise ReportOnly("UNSAFE_EVIDENCE_FILE")
        return b"".join(chunks)
    except OSError as exc:
        raise ReportOnly("UNSAFE_EVIDENCE_FILE") from exc
    finally:
        os.close(descriptor)


def _load_private_json(path_text: str, *, canonical: bool = False) -> Any:
    path = Path(path_text)
    try:
        text = _read_private_bytes(path).decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_duplicate_rejecting_object,
        )
        if canonical and text != _canonical(value) + "\n":
            raise GuardError("RECEIPT_INVALID")
        return value
    except UnicodeError as exc:
        raise GuardError("EVIDENCE_SCHEMA_INVALID") from exc
    except json.JSONDecodeError as exc:
        raise GuardError("EVIDENCE_SCHEMA_INVALID") from exc


def _exact_object(
    value: Any,
    keys: set[str],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    return value


def _positive_integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    return value


def _nonempty_string(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    return value


def _normalize_https_endpoint(value: Any) -> str:
    raw = _nonempty_string(value)
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "%" in parsed.path
        or not URL_PATH_RE.fullmatch(parsed.path)
        or any(segment in {".", ".."} for segment in parsed.path.split("/"))
    ):
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    hostname = parsed.hostname.lower().rstrip(".")
    if not hostname or any(
        character not in "abcdefghijklmnopqrstuvwxyz0123456789.-"
        for character in hostname
    ):
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    if hostname.startswith(".") or hostname.endswith(".") or ".." in hostname:
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    if port == 443 or port == 0:
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    authority = hostname if port is None else f"{hostname}:{port}"
    normalized = urlunsplit(("https", authority, parsed.path, "", ""))
    if raw != normalized:
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    return normalized


def _object_format_sha(value: Any, object_format: str) -> str:
    text = _nonempty_string(value).lower()
    matcher = SHA1_RE if object_format == "sha1" else SHA256_RE
    if not matcher.fullmatch(text):
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    return text


def _branch_ref(branch: str) -> str:
    return "refs/heads/" + branch


def _read_api_binding(
    project_path: str,
    mr_path: str,
    branch_path: str,
) -> dict[str, Any]:
    project = _exact_object(
        _load_private_json(project_path),
        {"id", "http_url_to_repo"},
    )
    merge_request = _exact_object(
        _load_private_json(mr_path),
        {"source_project_id", "source_branch", "sha", "diff_refs"},
    )
    branch = _exact_object(
        _load_private_json(branch_path),
        {"name", "commit"},
    )
    diff_refs = _exact_object(
        merge_request["diff_refs"],
        {"head_sha"},
    )
    branch_commit = _exact_object(
        branch["commit"],
        {"id"},
    )
    project_id = _positive_integer(project["id"])
    source_project_id = _positive_integer(merge_request["source_project_id"])
    if project_id != source_project_id:
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    source_branch = _nonempty_string(merge_request["source_branch"])
    if _nonempty_string(branch["name"]) != source_branch:
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    endpoint = _normalize_https_endpoint(project["http_url_to_repo"])
    return {
        "project_id": project_id,
        "branch": source_branch,
        "mr_sha": _nonempty_string(merge_request["sha"]).lower(),
        "diff_head_sha": _nonempty_string(diff_refs["head_sha"]).lower(),
        "branch_sha": _nonempty_string(branch_commit["id"]).lower(),
        "endpoint": endpoint,
    }


def _git_environment(
    *,
    overrides: dict[str, str] | None = None,
    unset_case_insensitive: tuple[str, ...] = (),
) -> dict[str, str]:
    environment = os.environ.copy()
    unset_names = {name.upper() for name in unset_case_insensitive}
    for name in tuple(environment):
        if name.startswith("GIT_") or name.upper() in unset_names:
            del environment[name]
    environment.update(
        {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "LC_ALL": "C",
            "LANG": "C",
        }
    )
    if overrides:
        environment.update(overrides)
    return environment


def _run(
    command: list[str],
    *,
    accepted: tuple[int, ...] = (0,),
    environment_overrides: dict[str, str] | None = None,
    unset_case_insensitive: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[bytes]:
    try:
        result = subprocess.run(
            command,
            env=_git_environment(
                overrides=environment_overrides,
                unset_case_insensitive=unset_case_insensitive,
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GuardError("GIT_UNAVAILABLE") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, subprocess.TimeoutExpired):
            raise ReportOnly("LOCAL_GIT_TIMEOUT") from exc
        raise GuardError("GIT_UNAVAILABLE") from exc
    if (
        len(result.stdout) > MAX_GIT_OUTPUT_BYTES
        or len(result.stderr) > MAX_GIT_OUTPUT_BYTES
    ):
        raise ReportOnly("LOCAL_GIT_OUTPUT_LIMIT")
    if result.returncode not in accepted:
        raise ReportOnly("LOCAL_GIT_FAILED")
    return result


def _git(
    git_binary: str,
    repository: Path | None,
    *arguments: str,
    accepted: tuple[int, ...] = (0,),
) -> subprocess.CompletedProcess[bytes]:
    command = [git_binary]
    if repository is not None:
        command.extend(["-C", str(repository)])
    command.extend(arguments)
    return _run(command, accepted=accepted)


def _git_dir(
    git_binary: str,
    git_directory: Path,
    *arguments: str,
    accepted: tuple[int, ...] = (0,),
    environment_overrides: dict[str, str] | None = None,
    unset_case_insensitive: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[bytes]:
    return _run(
        [git_binary, "--git-dir", str(git_directory), *arguments],
        accepted=accepted,
        environment_overrides=environment_overrides,
        unset_case_insensitive=unset_case_insensitive,
    )


def _decode_output(value: bytes) -> str:
    try:
        return value.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ReportOnly("LOCAL_GIT_FAILED") from exc


def _lines(value: bytes) -> list[str]:
    decoded = _decode_output(value)
    if "\x00" in decoded:
        raise ReportOnly("LOCAL_GIT_FAILED")
    return [line for line in decoded.splitlines() if line]


def _nul_values(value: bytes) -> list[str]:
    try:
        parts = value.decode("utf-8", errors="strict").split("\x00")
    except UnicodeError as exc:
        raise ReportOnly("LOCAL_GIT_FAILED") from exc
    if parts and parts[-1] == "":
        parts.pop()
    if any("\n" in part or "\r" in part for part in parts):
        raise ReportOnly("LOCAL_GIT_FAILED")
    return parts


def _resolve_git_binary(git_binary: str) -> str:
    candidate = shutil.which(git_binary)
    if candidate is None:
        raise GuardError("GIT_UNAVAILABLE")
    try:
        resolved = Path(candidate).resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise GuardError("GIT_UNAVAILABLE") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or not os.access(resolved, os.X_OK)
        or metadata.st_mode & 0o022
    ):
        raise GuardError("GIT_UNAVAILABLE")
    if hasattr(os, "geteuid") and metadata.st_uid not in {0, os.geteuid()}:
        raise GuardError("GIT_UNAVAILABLE")
    return str(resolved)


def _tool_file_identity(path: Path) -> dict[str, Any]:
    try:
        lexical_metadata = path.lstat()
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except OSError as exc:
        raise GuardError("GIT_UNAVAILABLE") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or not os.access(resolved, os.X_OK)
        or metadata.st_mode & 0o022
        or metadata.st_size > MAX_TOOL_BYTES
    ):
        raise GuardError("GIT_UNAVAILABLE")
    if hasattr(os, "geteuid") and metadata.st_uid not in {0, os.geteuid()}:
        raise GuardError("GIT_UNAVAILABLE")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(resolved, flags)
    except OSError as exc:
        raise GuardError("GIT_UNAVAILABLE") from exc
    try:
        before = os.fstat(descriptor)
        if (
            before.st_dev != metadata.st_dev
            or before.st_ino != metadata.st_ino
            or before.st_size != metadata.st_size
            or before.st_mtime_ns != metadata.st_mtime_ns
            or before.st_ctime_ns != metadata.st_ctime_ns
        ):
            raise GuardError("GIT_UNAVAILABLE")
        digest = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise GuardError("GIT_UNAVAILABLE")
            digest.update(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise GuardError("GIT_UNAVAILABLE")
        after = os.fstat(descriptor)
        final_path = resolved.stat()
        if (
            after.st_dev != before.st_dev
            or after.st_ino != before.st_ino
            or after.st_size != before.st_size
            or after.st_mtime_ns != before.st_mtime_ns
            or after.st_ctime_ns != before.st_ctime_ns
            or final_path.st_dev != after.st_dev
            or final_path.st_ino != after.st_ino
        ):
            raise GuardError("GIT_UNAVAILABLE")
    except OSError as exc:
        raise GuardError("GIT_UNAVAILABLE") from exc
    finally:
        os.close(descriptor)
    return {
        "content_sha256": digest.hexdigest(),
        "lexical_kind": (
            "symlink" if stat.S_ISLNK(lexical_metadata.st_mode) else "file"
        ),
        "lexical_path_sha256": _digest_text(str(path)),
        "resolved_path_sha256": _digest_text(str(resolved)),
        "size": metadata.st_size,
    }


def _git_version(git_binary: str) -> tuple[str, str, str, str]:
    resolved = _resolve_git_binary(git_binary)
    output = _lines(_git(resolved, None, "--version").stdout)
    if len(output) != 1:
        raise ReportOnly("UNSUPPORTED_GIT")
    match = VERSION_RE.fullmatch(output[0])
    if not match:
        raise ReportOnly("UNSUPPORTED_GIT")
    version_parts = tuple(int(component) for component in match.group(1).split(".")[:3])
    if version_parts + (0,) * (3 - len(version_parts)) < (2, 31, 0):
        raise ReportOnly("UNSUPPORTED_GIT")
    exec_path_lines = _lines(_git(resolved, None, "--exec-path").stdout)
    if len(exec_path_lines) != 1:
        raise ReportOnly("UNSUPPORTED_GIT")
    try:
        exec_path = Path(exec_path_lines[0]).resolve(strict=True)
        exec_metadata = exec_path.stat()
    except OSError as exc:
        raise GuardError("GIT_UNAVAILABLE") from exc
    if (
        not exec_path.is_dir()
        or exec_metadata.st_mode & 0o022
        or (hasattr(os, "geteuid") and exec_metadata.st_uid not in {0, os.geteuid()})
    ):
        raise GuardError("GIT_UNAVAILABLE")
    tools = {
        "git": _tool_file_identity(Path(resolved)),
    }
    for name in (
        "git-credential",
        "git-pack-objects",
        "git-remote-https",
        "git-send-pack",
    ):
        tools[name] = _tool_file_identity(exec_path / name)
    toolchain = {
        "exec_path_sha256": _digest_text(str(exec_path)),
        "tools": tools,
    }
    return (
        match.group(1),
        _stable_hash(toolchain),
        resolved,
        str(exec_path),
    )


def _validate_repository_path(path_text: str) -> Path:
    path = Path(path_text)
    if not _safe_path_text(path) or not _safe_parent_chain(path):
        raise ReportOnly("UNSAFE_REPOSITORY")
    try:
        metadata = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ReportOnly("UNSAFE_REPOSITORY") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or resolved != path
        or metadata.st_mode & 0o022
    ):
        raise ReportOnly("UNSAFE_REPOSITORY")
    if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
        raise ReportOnly("UNSAFE_REPOSITORY")
    return resolved


def _proxy_present() -> bool:
    proxy_names = {
        "all_proxy",
        "http_proxy",
        "https_proxy",
    }
    return any(
        name.lower() in proxy_names and bool(value)
        for name, value in os.environ.items()
    )


def _reject_runtime_overrides() -> set[str]:
    forbidden_names = {
        "curl_ca_bundle",
        "ld_library_path",
        "ld_preload",
        "requests_ca_bundle",
        "ssh_askpass",
        "ssh_askpass_require",
        "ssl_cert_dir",
        "ssl_cert_file",
    }
    if any(
        (name.lower() in forbidden_names or name.upper().startswith("DYLD_"))
        and bool(value)
        for name, value in os.environ.items()
    ):
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    return forbidden_names


def _execution_path() -> str:
    value = os.environ.get("PATH", "")
    if (
        not value
        or len(value.encode("utf-8")) > MAX_INPUT_BYTES
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
    ):
        raise ReportOnly("CONFIGURATION_DRIFT")
    components = value.split(os.pathsep)
    if any(
        not component
        or len(component.encode("utf-8")) > 4096
        or not Path(component).is_absolute()
        for component in components
    ):
        raise ReportOnly("CONFIGURATION_DRIFT")
    return value


def _reject_source_git_environment() -> None:
    if any(
        name.upper().startswith("GIT_")
        and name.upper() not in SOURCE_INERT_GIT_ENVIRONMENT
        for name in os.environ
    ):
        raise ReportOnly("CONFIGURATION_DRIFT")


def _runtime_environment_identity(exec_path: str, execution_path: str) -> str:
    forbidden_names = _reject_runtime_overrides()
    relevant = {
        "HOME": os.environ.get("HOME", ""),
        "PATH": execution_path,
        "XDG_CONFIG_HOME": os.environ.get("XDG_CONFIG_HOME", ""),
    }
    if any(
        any(ord(character) < 0x20 for character in value) for value in relevant.values()
    ):
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    return _stable_hash(
        {
            "execution_base": "empty",
            "exec_path_sha256": _digest_text(exec_path),
            "forbidden_tls_or_loader_variables": sorted(forbidden_names),
            "relevant_sha256": {
                name: _digest_text(value) for name, value in sorted(relevant.items())
            },
            "required": {
                "GIT_EXEC_PATH": _digest_text(exec_path),
                "GIT_NO_LAZY_FETCH": "1",
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_TERMINAL_PROMPT": "0",
                "LANG": "C",
                "LC_ALL": "C",
            },
            "source_allowed_git_variables": sorted(SOURCE_INERT_GIT_ENVIRONMENT),
            "source_reject_prefixes": ["GIT_"],
        }
    )


def _execution_home_blocker() -> tuple[str, str]:
    blocker = Path(os.devnull)
    if not _safe_path_text(blocker) or not _safe_parent_chain(blocker):
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    try:
        lexical = blocker.lstat()
        resolved = blocker.resolve(strict=True)
        metadata = resolved.stat()
        parent = resolved.parent.stat()
    except OSError as exc:
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE") from exc
    if (
        resolved != blocker
        or stat.S_ISLNK(lexical.st_mode)
        or not stat.S_ISCHR(metadata.st_mode)
        or parent.st_mode & 0o022
        or (hasattr(os, "geteuid") and metadata.st_uid != 0)
        or (hasattr(os, "geteuid") and parent.st_uid != 0)
    ):
        raise ReportOnly("HTTPS_BASELINE_UNAVAILABLE")
    identity = _stable_hash(
        {
            "path": str(resolved),
            "st_dev": metadata.st_dev,
            "st_ino": metadata.st_ino,
            "st_mode": metadata.st_mode,
            "st_rdev": metadata.st_rdev,
            "st_uid": metadata.st_uid,
        }
    )
    return str(resolved), identity


def _raw_remote_urls(
    git_binary: str,
    repository: Path,
    remote: str,
) -> list[str]:
    push_urls = _git(
        git_binary,
        repository,
        "config",
        "--null",
        "--get-all",
        f"remote.{remote}.pushurl",
        accepted=(0, 1),
    )
    values = _nul_values(push_urls.stdout)
    if push_urls.returncode == 0:
        return values
    urls = _git(
        git_binary,
        repository,
        "config",
        "--null",
        "--get-all",
        f"remote.{remote}.url",
        accepted=(0, 1),
    )
    return _nul_values(urls.stdout)


def _source_context(
    *,
    git_binary: str,
    repository_text: str,
    discovery_remote: str,
    api: dict[str, Any],
    prepared_sha_text: str,
) -> dict[str, Any]:
    repository = _validate_repository_path(repository_text)
    if not REMOTE_RE.fullmatch(discovery_remote):
        raise GuardError("ARGUMENT_ERROR")
    _reject_source_git_environment()
    if _proxy_present():
        raise ReportOnly("AMBIENT_PROXY")
    _reject_runtime_overrides()
    execution_path = _execution_path()
    version, toolchain_hash, git_binary, exec_path = _git_version(git_binary)
    runtime_environment_hash = _runtime_environment_identity(
        exec_path,
        execution_path,
    )
    top_level_lines = _lines(
        _git(
            git_binary,
            repository,
            "rev-parse",
            "--path-format=absolute",
            "--show-toplevel",
        ).stdout
    )
    if len(top_level_lines) != 1:
        raise ReportOnly("UNSAFE_REPOSITORY")
    try:
        if Path(top_level_lines[0]).resolve(strict=True) != repository:
            raise ReportOnly("UNSAFE_REPOSITORY")
    except OSError as exc:
        raise ReportOnly("UNSAFE_REPOSITORY") from exc
    format_lines = _lines(
        _git(
            git_binary,
            repository,
            "rev-parse",
            "--show-object-format=storage",
        ).stdout
    )
    if format_lines not in (["sha1"], ["sha256"]):
        raise ReportOnly("UNSUPPORTED_OBJECT_FORMAT")
    object_format = format_lines[0]
    shallow_lines = _lines(
        _git(
            git_binary,
            repository,
            "rev-parse",
            "--is-shallow-repository",
        ).stdout
    )
    if shallow_lines != ["false"]:
        raise ReportOnly("INCOMPLETE_OBJECT_CLOSURE")
    promisor = _git(
        git_binary,
        repository,
        "config",
        "--includes",
        "--null",
        "--get-regexp",
        r"^(extensions\.partialclone|remote\..*\.promisor)$",
        accepted=(0, 1),
    )
    if promisor.returncode == 0 or promisor.stdout:
        raise ReportOnly("INCOMPLETE_OBJECT_CLOSURE")
    prepared_sha = _object_format_sha(prepared_sha_text, object_format)
    expected_candidates = {
        _object_format_sha(api["mr_sha"], object_format),
        _object_format_sha(api["diff_head_sha"], object_format),
        _object_format_sha(api["branch_sha"], object_format),
    }
    if len(expected_candidates) != 1:
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    expected_old = next(iter(expected_candidates))
    if prepared_sha == expected_old:
        raise ReportOnly("PREPARED_EQUALS_EXPECTED")
    branch_ref = _branch_ref(api["branch"])
    ref_check = _git(
        git_binary,
        repository,
        "check-ref-format",
        branch_ref,
        accepted=(0, 1),
    )
    if ref_check.returncode != 0:
        raise GuardError("EVIDENCE_SCHEMA_INVALID")
    head_lines = _lines(
        _git(
            git_binary,
            repository,
            "rev-parse",
            "--verify",
            "HEAD^{commit}",
        ).stdout
    )
    if head_lines != [prepared_sha]:
        raise ReportOnly("SOURCE_IDENTITY_DRIFT")
    for expression in (prepared_sha + "^{commit}", expected_old + "^{commit}"):
        result = _git(
            git_binary,
            repository,
            "cat-file",
            "-e",
            expression,
            accepted=(0, 1),
        )
        if result.returncode != 0:
            raise ReportOnly("INCOMPLETE_OBJECT_CLOSURE")
    ancestry = _git(
        git_binary,
        repository,
        "merge-base",
        "--is-ancestor",
        expected_old,
        prepared_sha,
        accepted=(0, 1),
    )
    if ancestry.returncode != 0:
        raise ReportOnly("ANCESTRY_UNPROVEN")
    closure_output = _git(
        git_binary,
        repository,
        "rev-list",
        "--objects",
        "--missing=print",
        "--no-object-names",
        prepared_sha,
        "^" + expected_old,
    ).stdout
    closure_lines = sorted(_lines(closure_output))
    if not closure_lines or any(line.startswith(("?", "-")) for line in closure_lines):
        raise ReportOnly("INCOMPLETE_OBJECT_CLOSURE")
    if any(
        not (
            SHA1_RE.fullmatch(line)
            if object_format == "sha1"
            else SHA256_RE.fullmatch(line)
        )
        for line in closure_lines
    ):
        raise ReportOnly("INCOMPLETE_OBJECT_CLOSURE")
    raw_urls = _raw_remote_urls(
        git_binary,
        repository,
        discovery_remote,
    )
    if len(raw_urls) != 1:
        raise ReportOnly("DUPLICATE_PUSH_URL")
    endpoint = api["endpoint"]
    if raw_urls[0] != endpoint:
        raise ReportOnly("ENDPOINT_MISMATCH")
    effective_urls = _lines(
        _git(
            git_binary,
            repository,
            "remote",
            "get-url",
            "--push",
            "--all",
            discovery_remote,
        ).stdout
    )
    if len(effective_urls) != 1:
        raise ReportOnly("DUPLICATE_PUSH_URL")
    if effective_urls[0] != endpoint:
        raise ReportOnly("ENDPOINT_MISMATCH")
    config_graph_before = _git(
        git_binary,
        repository,
        "config",
        "--includes",
        "--null",
        "--show-origin",
        "--show-scope",
        "--list",
    ).stdout
    credential_records = _source_config_records(
        git_binary,
        repository,
        r"^credential\.",
    )
    credential_helpers = _normalize_credential_helpers(
        _source_credential_policy(
            git_binary,
            repository,
            endpoint,
            credential_records,
        ),
        exec_path,
        execution_path,
    )
    _credential_helper_identity(credential_helpers)
    config_graph_after = _git(
        git_binary,
        repository,
        "config",
        "--includes",
        "--null",
        "--show-origin",
        "--show-scope",
        "--list",
    ).stdout
    if config_graph_after != config_graph_before:
        raise ReportOnly("CONFIGURATION_DRIFT")
    home_blocker, home_blocker_hash = _execution_home_blocker()
    object_directory_lines = _lines(
        _git(
            git_binary,
            repository,
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            "objects",
        ).stdout
    )
    if len(object_directory_lines) != 1:
        raise ReportOnly("UNSAFE_REPOSITORY")
    object_directory = Path(object_directory_lines[0])
    if not _safe_path_text(object_directory):
        raise ReportOnly("INCOMPLETE_OBJECT_CLOSURE")
    try:
        object_directory = object_directory.resolve(strict=True)
    except OSError as exc:
        raise ReportOnly("INCOMPLETE_OBJECT_CLOSURE") from exc
    object_metadata = object_directory.stat()
    if (
        not object_directory.is_dir()
        or object_metadata.st_mode & 0o022
        or (hasattr(os, "geteuid") and object_metadata.st_uid != os.geteuid())
    ):
        raise ReportOnly("INCOMPLETE_OBJECT_CLOSURE")
    return {
        "api": api,
        "repository": repository,
        "endpoint": endpoint,
        "branch_ref": branch_ref,
        "expected_old": expected_old,
        "prepared_sha": prepared_sha,
        "object_format": object_format,
        "object_directory": object_directory,
        "git_version": version,
        "git_binary": git_binary,
        "git_exec_path": exec_path,
        "git_toolchain_sha256": toolchain_hash,
        "runtime_environment_sha256": runtime_environment_hash,
        "config_graph_sha256": _digest_bytes(config_graph_after),
        "credential_helpers": credential_helpers,
        "execution_path": execution_path,
        "execution_home": home_blocker,
        "execution_home_sha256": home_blocker_hash,
        "closure_sha256": _stable_hash(closure_lines),
        "range_objects": len(closure_lines),
        "configured_push_urls": len(raw_urls),
        "effective_push_urls": len(effective_urls),
    }


def _validate_private_directory(path: Path, *, exact_mode: int = 0o700) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ReportOnly("UNSAFE_TRANSACTION_PATH") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != exact_mode
    ):
        raise ReportOnly("UNSAFE_TRANSACTION_PATH")
    if hasattr(os, "geteuid") and metadata.st_uid != os.geteuid():
        raise ReportOnly("UNSAFE_TRANSACTION_PATH")


def _transaction_paths(transaction_text: str) -> dict[str, Path]:
    root = Path(transaction_text)
    if (
        not _safe_path_text(root)
        or not _safe_parent_chain(root)
        or root.name in {"", ".", ".."}
    ):
        raise ReportOnly("UNSAFE_TRANSACTION_PATH")
    if root.parent.resolve(strict=False) != root.parent:
        raise ReportOnly("UNSAFE_TRANSACTION_PATH")
    return {
        "root": root,
        "template": root / "empty-template",
        "hooks": root / "hooks",
        "git": root / "repository.git",
    }


def _write_private_file(path: Path, content: str) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _configure_transaction(
    git_binary: str,
    git_directory: Path,
    key: str,
    value: str,
    *,
    add: bool = False,
) -> None:
    arguments = ["config", "--local"]
    if add:
        arguments.append("--add")
    arguments.extend([key, value])
    _git_dir(git_binary, git_directory, *arguments)


def _execution_environment_set(
    source: dict[str, Any],
) -> dict[str, str]:
    return {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_EXEC_PATH": source["git_exec_path"],
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": source["execution_home"],
        "LANG": "C",
        "LC_ALL": "C",
        "XDG_CONFIG_HOME": source["execution_home"],
    }


def _execution_manifest(
    source: dict[str, Any],
    paths: dict[str, Path],
    token: str,
    credential_helpers_sha256: str,
) -> dict[str, Any]:
    return {
        "schema": EXECUTION_SCHEMA,
        "git_binary": source["git_binary"],
        "cwd": str(paths["root"]),
        "argv": [
            "--git-dir",
            str(paths["git"]),
            "push",
            "--porcelain",
            "--no-verify",
            "--no-signed",
            "--no-follow-tags",
            "--no-tags",
            "--no-set-upstream",
            "--no-force-if-includes",
            "--no-push-option",
            "--recurse-submodules=no",
            "--force-with-lease=" + source["branch_ref"] + ":" + source["expected_old"],
            PUSH_REMOTE,
            source["prepared_sha"] + ":" + source["branch_ref"],
        ],
        "environment": {
            "base": "empty",
            "operation_order": ["clear", "preserve_exact", "set"],
            "preserve_exact": {
                "PATH": source["execution_path"],
            },
            "set": _execution_environment_set(source),
        },
        "hashes": {
            "credential_helpers_sha256": credential_helpers_sha256,
            "execution_home_sha256": source["execution_home_sha256"],
            "git_toolchain_sha256": source["git_toolchain_sha256"],
            "runtime_environment_sha256": source["runtime_environment_sha256"],
            "transaction_token_sha256": _digest_text(token),
        },
    }


def _normalize_transaction_modes(root: Path) -> None:
    for current_root, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_root)
        current_metadata = current.lstat()
        if (
            not stat.S_ISDIR(current_metadata.st_mode)
            or stat.S_ISLNK(current_metadata.st_mode)
            or (hasattr(os, "geteuid") and current_metadata.st_uid != os.geteuid())
        ):
            raise ReportOnly("TRANSACTION_PREPARE_FAILED")
        os.chmod(current, 0o700, follow_symlinks=False)
        for directory_name in directory_names:
            path = current / directory_name
            metadata = path.lstat()
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or (hasattr(os, "geteuid") and metadata.st_uid != os.geteuid())
            ):
                raise ReportOnly("TRANSACTION_PREPARE_FAILED")
            os.chmod(path, 0o700, follow_symlinks=False)
        for file_name in file_names:
            path = current / file_name
            metadata = path.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_nlink != 1
                or (hasattr(os, "geteuid") and metadata.st_uid != os.geteuid())
            ):
                raise ReportOnly("TRANSACTION_PREPARE_FAILED")
            os.chmod(path, 0o600, follow_symlinks=False)


def _prepare_transaction(
    *,
    git_binary: str,
    transaction_text: str,
    source: dict[str, Any],
) -> None:
    paths = _transaction_paths(transaction_text)
    root = paths["root"]
    if root.exists() or root.is_symlink():
        raise GuardError("TRANSACTION_ALREADY_EXISTS")
    _validate_private_directory(root.parent)
    previous_umask = os.umask(0o077)
    try:
        root.mkdir(mode=0o700)
        paths["template"].mkdir(mode=0o700)
        paths["hooks"].mkdir(mode=0o700)
        init = _git(
            git_binary,
            root,
            "init",
            "--bare",
            "--object-format=" + source["object_format"],
            "--template=" + str(paths["template"]),
            str(paths["git"]),
            accepted=(0, 129),
        )
        if init.returncode != 0:
            raise ReportOnly("UNSUPPORTED_GIT")
        alternates = paths["git"] / "objects" / "info" / "alternates"
        _write_private_file(
            alternates,
            str(source["object_directory"]) + "\n",
        )
        nonce = secrets.token_hex(32)
        sentinel = paths["root"] / "fail-closed" / nonce
        token = sentinel.as_uri()
        endpoint = source["endpoint"]
        settings = (
            ("core.hooksPath", str(paths["hooks"])),
            ("core.askPass", ""),
            (f"remote.{PUSH_REMOTE}.url", token),
            (f"remote.{PUSH_REMOTE}.mirror", "false"),
            (f"url.{endpoint}.pushInsteadOf", token),
            ("push.default", "nothing"),
            ("push.autoSetupRemote", "false"),
            ("push.followTags", "false"),
            ("push.gpgSign", "false"),
            ("push.recurseSubmodules", "no"),
            ("push.useForceIfIncludes", "false"),
            ("http.delegation", "none"),
            ("http.emptyAuth", "false"),
            ("http.followRedirects", "false"),
            ("http.sslVerify", "true"),
            ("http.proxy", ""),
            (f"http.{endpoint}.delegation", "none"),
            (f"http.{endpoint}.emptyAuth", "false"),
            (f"http.{endpoint}.followRedirects", "false"),
            (f"http.{endpoint}.sslVerify", "true"),
            (f"http.{endpoint}.proxy", ""),
            ("credential.interactive", "false"),
            ("credential.username", ""),
            ("credential.useHttpPath", "true"),
            ("protocol.allow", "never"),
            ("protocol.ext.allow", "never"),
            ("protocol.file.allow", "never"),
            ("protocol.ftp.allow", "never"),
            ("protocol.ftps.allow", "never"),
            ("protocol.git.allow", "never"),
            ("protocol.http.allow", "never"),
            ("protocol.https.allow", "always"),
            ("protocol.ssh.allow", "never"),
        )
        for key, value in settings:
            _configure_transaction(
                git_binary,
                paths["git"],
                key,
                value,
            )
        _configure_transaction(
            git_binary,
            paths["git"],
            "credential.helper",
            "",
            add=True,
        )
        for helper in source["credential_helpers"]:
            _configure_transaction(
                git_binary,
                paths["git"],
                "credential.helper",
                helper,
                add=True,
            )
        _configure_transaction(
            git_binary,
            paths["git"],
            "push.pushOption",
            "",
            add=True,
        )
        credential_helpers_sha256 = _credential_helper_identity(
            source["credential_helpers"]
        )
        manifest = _execution_manifest(
            source,
            paths,
            token,
            credential_helpers_sha256,
        )
        _write_private_file(
            paths["root"] / "execution.json",
            _canonical(manifest) + "\n",
        )
        _normalize_transaction_modes(root)
    except (GuardError, ReportOnly):
        raise
    except (OSError, ValueError) as exc:
        raise ReportOnly("TRANSACTION_PREPARE_FAILED") from exc
    finally:
        os.umask(previous_umask)


def _config_values(
    git_binary: str,
    git_directory: Path,
    key: str,
) -> list[str]:
    result = _git_dir(
        git_binary,
        git_directory,
        "config",
        "--local",
        "--null",
        "--get-all",
        key,
        accepted=(0, 1),
    )
    return _nul_values(result.stdout)


def _transaction_file_digest(path: Path, expected: os.stat_result) -> str:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_nlink",
            "st_uid",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(
            getattr(expected, field) != getattr(before, field)
            for field in stable_fields
        ):
            raise ReportOnly("TRANSACTION_DRIFT")
        digest = hashlib.sha256()
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 64 * 1024))
            if not chunk:
                raise ReportOnly("TRANSACTION_DRIFT")
            digest.update(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise ReportOnly("TRANSACTION_DRIFT")
        after = os.fstat(descriptor)
        if any(
            getattr(before, field) != getattr(after, field) for field in stable_fields
        ):
            raise ReportOnly("TRANSACTION_DRIFT")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _tree_identity(root: Path) -> str:
    entries: list[dict[str, Any]] = []
    try:
        for current_root, directory_names, file_names in os.walk(
            root,
            topdown=True,
            followlinks=False,
        ):
            directory_names.sort()
            file_names.sort()
            current = Path(current_root)
            relative_current = current.relative_to(root)
            current_metadata = current.lstat()
            if (
                not stat.S_ISDIR(current_metadata.st_mode)
                or stat.S_ISLNK(current_metadata.st_mode)
                or stat.S_IMODE(current_metadata.st_mode) != 0o700
                or (hasattr(os, "geteuid") and current_metadata.st_uid != os.geteuid())
            ):
                raise ReportOnly("TRANSACTION_DRIFT")
            entries.append(
                {
                    "kind": "directory",
                    "mode": "0700",
                    "path": relative_current.as_posix(),
                }
            )
            for name in directory_names:
                directory_path = current / name
                directory_metadata = directory_path.lstat()
                if (
                    not stat.S_ISDIR(directory_metadata.st_mode)
                    or stat.S_ISLNK(directory_metadata.st_mode)
                    or stat.S_IMODE(directory_metadata.st_mode) != 0o700
                    or (
                        hasattr(os, "geteuid")
                        and directory_metadata.st_uid != os.geteuid()
                    )
                ):
                    raise ReportOnly("TRANSACTION_DRIFT")
            for name in file_names:
                path = current / name
                metadata = path.lstat()
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or stat.S_ISLNK(metadata.st_mode)
                    or metadata.st_nlink != 1
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                    or metadata.st_size > MAX_INPUT_BYTES
                    or (hasattr(os, "geteuid") and metadata.st_uid != os.geteuid())
                ):
                    raise ReportOnly("TRANSACTION_DRIFT")
                entries.append(
                    {
                        "content_sha256": _transaction_file_digest(
                            path,
                            metadata,
                        ),
                        "kind": "file",
                        "mode": "0600",
                        "path": path.relative_to(root).as_posix(),
                        "size": metadata.st_size,
                    }
                )
    except ReportOnly:
        raise
    except OSError as exc:
        raise ReportOnly("TRANSACTION_DRIFT") from exc
    return _stable_hash(entries)


def _single_config_value(
    git_binary: str,
    git_directory: Path,
    key: str,
) -> str:
    values = _config_values(git_binary, git_directory, key)
    if len(values) != 1:
        raise ReportOnly("TRANSACTION_DRIFT")
    return values[0]


def _transaction_context(
    *,
    git_binary: str,
    transaction_text: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    paths = _transaction_paths(transaction_text)
    execution_environment = _execution_environment_set(source)
    _validate_private_directory(paths["root"])
    _validate_private_directory(paths["template"])
    _validate_private_directory(paths["hooks"])
    _validate_private_directory(paths["git"])
    for forbidden_home_entry in (
        ".config",
        ".gitconfig",
        ".netrc",
        "_netrc",
        "git",
    ):
        path = paths["root"] / forbidden_home_entry
        if path.exists() or path.is_symlink():
            raise ReportOnly("TRANSACTION_DRIFT")
    try:
        if any(paths["template"].iterdir()) or any(paths["hooks"].iterdir()):
            raise ReportOnly("TRANSACTION_DRIFT")
    except OSError as exc:
        raise ReportOnly("TRANSACTION_DRIFT") from exc
    object_format = _lines(
        _git_dir(
            git_binary,
            paths["git"],
            "rev-parse",
            "--show-object-format=storage",
            environment_overrides=execution_environment,
            unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
        ).stdout
    )
    if object_format != [source["object_format"]]:
        raise ReportOnly("TRANSACTION_DRIFT")
    refs = _git_dir(
        git_binary,
        paths["git"],
        "show-ref",
        accepted=(0, 1),
        environment_overrides=execution_environment,
        unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
    )
    if refs.returncode == 0 or refs.stdout:
        raise ReportOnly("TRANSACTION_DRIFT")
    alternates = paths["git"] / "objects" / "info" / "alternates"
    if not _private_regular_file(alternates):
        raise ReportOnly("TRANSACTION_DRIFT")
    try:
        if alternates.read_text(encoding="utf-8") != (
            str(source["object_directory"]) + "\n"
        ):
            raise ReportOnly("TRANSACTION_DRIFT")
    except (OSError, UnicodeError) as exc:
        raise ReportOnly("TRANSACTION_DRIFT") from exc
    token = _single_config_value(
        git_binary,
        paths["git"],
        f"remote.{PUSH_REMOTE}.url",
    )
    sentinel_prefix = (paths["root"] / "fail-closed").as_uri() + "/"
    if not re.fullmatch(
        re.escape(sentinel_prefix) + r"[0-9a-f]{64}",
        token,
    ):
        raise ReportOnly("TRANSACTION_DRIFT")
    sentinel_path = paths["root"] / "fail-closed" / token.rsplit("/", 1)[1]
    if sentinel_path.exists() or sentinel_path.is_symlink():
        raise ReportOnly("TRANSACTION_DRIFT")
    if _config_values(
        git_binary,
        paths["git"],
        f"remote.{PUSH_REMOTE}.pushurl",
    ):
        raise ReportOnly("TRANSACTION_DRIFT")
    endpoint = source["endpoint"]
    expected_settings = {
        f"remote.{PUSH_REMOTE}.mirror": "false",
        f"url.{endpoint}.pushInsteadOf": token,
        "core.hooksPath": str(paths["hooks"]),
        "core.askPass": "",
        "push.default": "nothing",
        "push.autoSetupRemote": "false",
        "push.followTags": "false",
        "push.gpgSign": "false",
        "push.recurseSubmodules": "no",
        "push.useForceIfIncludes": "false",
        "http.delegation": "none",
        "http.emptyAuth": "false",
        "http.followRedirects": "false",
        "http.sslVerify": "true",
        "http.proxy": "",
        f"http.{endpoint}.delegation": "none",
        f"http.{endpoint}.emptyAuth": "false",
        f"http.{endpoint}.followRedirects": "false",
        f"http.{endpoint}.sslVerify": "true",
        f"http.{endpoint}.proxy": "",
        "credential.interactive": "false",
        "credential.username": "",
        "credential.useHttpPath": "true",
        "protocol.allow": "never",
        "protocol.ext.allow": "never",
        "protocol.file.allow": "never",
        "protocol.ftp.allow": "never",
        "protocol.ftps.allow": "never",
        "protocol.git.allow": "never",
        "protocol.http.allow": "never",
        "protocol.https.allow": "always",
        "protocol.ssh.allow": "never",
    }
    for key, expected_value in expected_settings.items():
        if (
            _single_config_value(
                git_binary,
                paths["git"],
                key,
            )
            != expected_value
        ):
            raise ReportOnly("TRANSACTION_DRIFT")
    if _config_values(
        git_binary,
        paths["git"],
        "credential.helper",
    ) != ["", *source["credential_helpers"]]:
        raise ReportOnly("TRANSACTION_DRIFT")
    allowed_credential_keys = {
        "credential.helper",
        "credential.interactive",
        "credential.username",
        "credential.usehttppath",
    }
    credential_records = _effective_config_records(
        git_binary,
        paths["git"],
        r"^credential\.",
        execution_environment,
    )
    if any(
        scope != "local" or key.lower() not in allowed_credential_keys
        for scope, key, _value in credential_records
    ):
        raise ReportOnly("CONFIGURATION_DRIFT")
    if _config_values(
        git_binary,
        paths["git"],
        "push.pushOption",
    ) != [""]:
        raise ReportOnly("TRANSACTION_DRIFT")
    bound_remote_records = _effective_bound_remote_records(
        git_binary,
        paths["git"],
        execution_environment,
    )
    if len(bound_remote_records) != 2 or set(bound_remote_records) != {
        (
            "local",
            f"remote.{PUSH_REMOTE}.url",
            token,
        ),
        (
            "local",
            f"remote.{PUSH_REMOTE}.mirror",
            "false",
        ),
    }:
        raise ReportOnly("CONFIGURATION_DRIFT")
    remotes = _lines(
        _git_dir(
            git_binary,
            paths["git"],
            "remote",
            environment_overrides=execution_environment,
            unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
        ).stdout
    )
    if remotes != [PUSH_REMOTE]:
        raise ReportOnly("TRANSACTION_DRIFT")
    resolved = _lines(
        _git_dir(
            git_binary,
            paths["git"],
            "remote",
            "get-url",
            "--push",
            "--all",
            PUSH_REMOTE,
            environment_overrides=execution_environment,
            unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
        ).stdout
    )
    if resolved != [endpoint]:
        raise ReportOnly("TRANSACTION_DRIFT")
    effective_expectations = (
        ("http.delegation", "none"),
        ("http.emptyAuth", "false"),
        ("http.followRedirects", "false"),
        ("http.sslVerify", "true"),
        ("http.proxy", ""),
    )
    for key, expected_value in effective_expectations:
        result = _git_dir(
            git_binary,
            paths["git"],
            "config",
            "--get-urlmatch",
            key,
            endpoint,
            accepted=(0, 1),
            environment_overrides=execution_environment,
            unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
        )
        if result.returncode != 0:
            raise ReportOnly("CONFIGURATION_DRIFT")
        if _decode_output(result.stdout).rstrip("\n") != expected_value:
            raise ReportOnly("CONFIGURATION_DRIFT")
    effective_scalar_expectations = {
        "core.askPass": "",
        "credential.interactive": "false",
        "protocol.allow": "never",
        "protocol.ext.allow": "never",
        "protocol.file.allow": "never",
        "protocol.ftp.allow": "never",
        "protocol.ftps.allow": "never",
        "protocol.git.allow": "never",
        "protocol.http.allow": "never",
        "protocol.https.allow": "always",
        "protocol.ssh.allow": "never",
    }
    for key, expected_value in effective_scalar_expectations.items():
        result = _git_dir(
            git_binary,
            paths["git"],
            "config",
            "--get",
            key,
            accepted=(0, 1),
            environment_overrides=execution_environment,
            unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
        )
        if (
            result.returncode != 0
            or _decode_output(result.stdout).rstrip("\n") != expected_value
        ):
            raise ReportOnly("CONFIGURATION_DRIFT")
    for forbidden_pattern in (r"^core\.alternaterefscommand$",):
        forbidden = _git_dir(
            git_binary,
            paths["git"],
            "config",
            "--includes",
            "--null",
            "--get-regexp",
            forbidden_pattern,
            accepted=(0, 1),
            environment_overrides=execution_environment,
            unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
        )
        if forbidden.returncode == 0 or forbidden.stdout:
            raise ReportOnly("CONFIGURATION_DRIFT")
    disallowed_http_suffixes = (
        ".cookiefile",
        ".curloptresolve",
        ".extraheader",
        ".pinnedpubkey",
        ".proxysslcainfo",
        ".proxysslcert",
        ".proxysslkey",
        ".schannelcheckrevoke",
        ".schannelusesslcainfo",
        ".sslbackend",
        ".sslcainfo",
        ".sslcapath",
        ".sslcert",
        ".sslcertpasswordprotected",
        ".sslcerttype",
        ".sslcipherlist",
        ".sslkey",
        ".sslkeytype",
        ".ssltry",
        ".sslversion",
        ".savecookies",
    )
    for _scope, key, value in _effective_config_records(
        git_binary,
        paths["git"],
        r"^http\.",
        execution_environment,
    ):
        normalized_key = key.lower()
        if normalized_key.endswith(disallowed_http_suffixes):
            raise ReportOnly("CONFIGURATION_DRIFT")
        normalized_value = value.strip().lower()
        if normalized_key.endswith(".delegation") and normalized_value != "none":
            raise ReportOnly("CONFIGURATION_DRIFT")
        if normalized_key.endswith(".emptyauth") and normalized_value != "false":
            raise ReportOnly("CONFIGURATION_DRIFT")
        if normalized_key.endswith(".proxy") and value != "":
            raise ReportOnly("CONFIGURATION_DRIFT")
        if normalized_key.endswith(".followredirects") and normalized_value != "false":
            raise ReportOnly("CONFIGURATION_DRIFT")
        if normalized_key.endswith(".sslverify") and normalized_value != "true":
            raise ReportOnly("CONFIGURATION_DRIFT")
    transaction_config = _git_dir(
        git_binary,
        paths["git"],
        "config",
        "--includes",
        "--null",
        "--show-origin",
        "--show-scope",
        "--list",
        environment_overrides=execution_environment,
        unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
    ).stdout
    credential_helpers_sha256 = _credential_helper_identity(
        source["credential_helpers"]
    )
    expected_manifest = _execution_manifest(
        source,
        paths,
        token,
        credential_helpers_sha256,
    )
    try:
        manifest_text = _read_private_bytes(paths["root"] / "execution.json").decode(
            "utf-8", errors="strict"
        )
        manifest = json.loads(
            manifest_text,
            object_pairs_hook=_duplicate_rejecting_object,
        )
    except (
        GuardError,
        ReportOnly,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ReportOnly("TRANSACTION_DRIFT") from exc
    if manifest_text != _canonical(manifest) + "\n" or manifest != expected_manifest:
        raise ReportOnly("TRANSACTION_DRIFT")
    return {
        "paths": paths,
        "token": token,
        "tree_sha256": _tree_identity(paths["root"]),
        "config_sha256": _digest_bytes(transaction_config),
        "credential_helpers_sha256": credential_helpers_sha256,
        "execution_plan_sha256": _stable_hash(manifest),
        "transaction_refs": 0,
    }


def _effective_bound_remote_records(
    git_binary: str,
    git_directory: Path,
    environment_overrides: dict[str, str],
) -> list[tuple[str, str, str]]:
    return _effective_config_records(
        git_binary,
        git_directory,
        r"^remote\.gitlab-review-bound\.",
        environment_overrides,
    )


def _effective_config_records(
    git_binary: str,
    git_directory: Path,
    pattern: str,
    environment_overrides: dict[str, str],
) -> list[tuple[str, str, str]]:
    result = _git_dir(
        git_binary,
        git_directory,
        "config",
        "--includes",
        "--null",
        "--show-scope",
        "--get-regexp",
        pattern,
        accepted=(0, 1),
        environment_overrides=environment_overrides,
        unset_case_insensitive=EXECUTION_UNSET_CASE_INSENSITIVE,
    )
    if result.returncode == 1:
        return []
    return _parse_config_records(result.stdout)


def _source_config_records(
    git_binary: str,
    repository: Path,
    pattern: str,
) -> list[tuple[str, str, str]]:
    result = _git(
        git_binary,
        repository,
        "config",
        "--includes",
        "--null",
        "--show-scope",
        "--get-regexp",
        pattern,
        accepted=(0, 1),
    )
    if (
        result.stderr
        or (result.returncode == 1 and result.stdout)
        or (result.returncode == 0 and not result.stdout)
    ):
        raise ReportOnly("CONFIGURATION_DRIFT")
    if result.returncode == 1:
        return []
    return _parse_config_records(result.stdout)


def _parse_config_records(output: bytes) -> list[tuple[str, str, str]]:
    try:
        parts = output.decode("utf-8", errors="strict").split("\x00")
    except UnicodeError as exc:
        raise ReportOnly("CONFIGURATION_DRIFT") from exc
    if parts and parts[-1] == "":
        parts.pop()
    if len(parts) % 2:
        raise ReportOnly("CONFIGURATION_DRIFT")
    records: list[tuple[str, str, str]] = []
    for index in range(0, len(parts), 2):
        scope = parts[index]
        key_and_value = parts[index + 1]
        if "\n" not in key_and_value:
            raise ReportOnly("CONFIGURATION_DRIFT")
        key, value = key_and_value.split("\n", 1)
        records.append((scope, key, value))
    return records


def _source_credential_policy(
    git_binary: str,
    repository: Path,
    endpoint: str,
    records: list[tuple[str, str, str]],
) -> list[str]:
    generic_helpers: list[str] = []
    subsections: set[str] = set()
    for _scope, key, value in records:
        if not key.lower().startswith("credential."):
            raise ReportOnly("CONFIGURATION_DRIFT")
        body = key[len("credential.") :]
        if "." not in body:
            if body.lower() != "helper":
                raise ReportOnly("CONFIGURATION_DRIFT")
            generic_helpers.append(value)
            continue
        subsection, variable = body.rsplit(".", 1)
        try:
            encoded = subsection.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ReportOnly("CONFIGURATION_DRIFT") from exc
        if (
            not subsection
            or not variable
            or len(encoded) > MAX_CONFIG_SUBSECTION_BYTES
            or "=" in subsection
            or any(
                ord(character) < 0x20 or ord(character) == 0x7F
                for character in subsection
            )
        ):
            raise ReportOnly("CONFIGURATION_DRIFT")
        subsections.add(subsection)
        if len(subsections) > MAX_SCOPED_CREDENTIAL_SUBSECTIONS:
            raise ReportOnly("CONFIGURATION_DRIFT")
    _reject_matching_scoped_credential_config(
        git_binary,
        repository,
        endpoint,
        sorted(subsections),
    )
    return _active_credential_helpers(generic_helpers)


def _reject_matching_scoped_credential_config(
    git_binary: str,
    repository: Path,
    endpoint: str,
    subsections: list[str],
) -> None:
    if not subsections:
        return
    nonce = secrets.token_hex(16)
    variable = "gitlabreviewprobe" + nonce
    marker = "gitlab-review-probe-" + nonce
    probe_key = "credential." + variable
    collision = _git(
        git_binary,
        repository,
        "config",
        "--null",
        "--get-urlmatch",
        probe_key,
        endpoint,
        accepted=(0, 1),
    )
    if collision.returncode != 1 or collision.stdout or collision.stderr:
        raise ReportOnly("CONFIGURATION_DRIFT")
    for subsection in subsections:
        injected_key = f"credential.{subsection}.{variable}"
        match = _git(
            git_binary,
            repository,
            "-c",
            injected_key + "=" + marker,
            "config",
            "--null",
            "--get-urlmatch",
            probe_key,
            endpoint,
            accepted=(0, 1),
        )
        if match.stderr:
            raise ReportOnly("CONFIGURATION_DRIFT")
        values = _nul_values(match.stdout)
        if match.returncode == 0 and values == [marker]:
            raise ReportOnly("CONFIGURATION_DRIFT")
        if match.returncode != 1 or values:
            raise ReportOnly("CONFIGURATION_DRIFT")


def _active_credential_helpers(values: list[str]) -> list[str]:
    active: list[str] = []
    for value in values:
        if value == "":
            active.clear()
        else:
            active.append(value)
    return active


def _normalize_credential_helpers(
    active: list[str],
    exec_path: str,
    execution_path: str,
) -> list[str]:
    normalized: list[str] = []
    safe_helper = re.compile(r"^[A-Za-z0-9_./:=+,-]+$")
    for value in active:
        if not safe_helper.fullmatch(value):
            raise ReportOnly("CONFIGURATION_DRIFT")
        if Path(value).is_absolute():
            candidate = Path(value)
        else:
            bundled = Path(exec_path) / ("git-credential-" + value)
            if bundled.exists() or bundled.is_symlink():
                candidate = bundled
            else:
                resolved = shutil.which(
                    "git-credential-" + value,
                    path=execution_path,
                )
                if resolved is None:
                    raise ReportOnly("CONFIGURATION_DRIFT")
                candidate = Path(resolved)
        try:
            executable = candidate.resolve(strict=True)
        except OSError as exc:
            raise ReportOnly("CONFIGURATION_DRIFT") from exc
        _credential_helper_tool_identity(executable)
        normalized.append(str(executable))
    return normalized


def _credential_helper_tool_identity(path: Path) -> dict[str, Any]:
    try:
        return _tool_file_identity(path)
    except GuardError as exc:
        raise ReportOnly("CONFIGURATION_DRIFT") from exc


def _credential_helper_identity(
    active: list[str],
) -> str:
    identities: list[dict[str, Any]] = []
    safe_helper = re.compile(r"^[A-Za-z0-9_./:=+,-]+$")
    for value in active:
        executable = Path(value)
        if not safe_helper.fullmatch(value) or not executable.is_absolute():
            raise ReportOnly("CONFIGURATION_DRIFT")
        identities.append(
            {
                "arguments_sha256": _digest_text(value),
                "tool": _credential_helper_tool_identity(executable),
            }
        )
    return _stable_hash(identities)


def _context_hashes(
    source: dict[str, Any],
    transaction: dict[str, Any],
    prior_receipt_sha256: str,
) -> dict[str, str]:
    api_binding = {
        "project_id": source["api"]["project_id"],
        "branch": source["api"]["branch"],
        "expected_old": source["expected_old"],
        "endpoint": source["endpoint"],
    }
    source_identity = {
        "repository": str(source["repository"]),
        "prepared_sha": source["prepared_sha"],
        "expected_old": source["expected_old"],
        "object_format": source["object_format"],
        "object_directory": str(source["object_directory"]),
    }
    return {
        "api_binding_sha256": _stable_hash(api_binding),
        "branch_ref_sha256": _digest_text(source["branch_ref"]),
        "config_graph_sha256": source["config_graph_sha256"],
        "credential_helpers_sha256": transaction["credential_helpers_sha256"],
        "endpoint_sha256": _digest_text(source["endpoint"]),
        "execution_plan_sha256": transaction["execution_plan_sha256"],
        "expected_old_sha256": _digest_text(source["expected_old"]),
        "git_toolchain_sha256": source["git_toolchain_sha256"],
        "object_closure_sha256": source["closure_sha256"],
        "prepared_sha256": _digest_text(source["prepared_sha"]),
        "prior_receipt_sha256": prior_receipt_sha256,
        "runtime_environment_sha256": source["runtime_environment_sha256"],
        "source_identity_sha256": _stable_hash(source_identity),
        "transaction_config_sha256": transaction["config_sha256"],
        "transaction_directory_sha256": _digest_text(str(transaction["paths"]["root"])),
        "transaction_token_sha256": _digest_text(transaction["token"]),
        "transaction_tree_sha256": transaction["tree_sha256"],
    }


def _ready_receipt(
    phase: str,
    source: dict[str, Any],
    transaction: dict[str, Any],
    prior_receipt_sha256: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "phase": phase,
        "status": "READY",
        "reason_codes": [],
        "git_version": source["git_version"],
        "object_format": source["object_format"],
        "counts": {
            "configured_push_urls": source["configured_push_urls"],
            "effective_push_urls": source["effective_push_urls"],
            "range_objects": source["range_objects"],
            "transaction_refs": transaction["transaction_refs"],
        },
        "hashes": _context_hashes(
            source,
            transaction,
            prior_receipt_sha256,
        ),
    }
    body["receipt_sha256"] = _stable_hash(body)
    return body


def _placeholder_hashes(reason_codes: list[str]) -> dict[str, str]:
    return {
        key: _stable_hash(
            {
                "availability": "unavailable",
                "field": key,
                "reason_codes": reason_codes,
            }
        )
        for key in HASH_KEYS
    }


def _report_only_receipt(phase: str, reason_codes: list[str]) -> dict[str, Any]:
    reasons = sorted(set(reason_codes))
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "phase": phase,
        "status": "REPORT_ONLY",
        "reason_codes": reasons,
        "git_version": "unavailable",
        "object_format": "unknown",
        "counts": {key: 0 for key in COUNT_KEYS},
        "hashes": _placeholder_hashes(reasons),
    }
    body["receipt_sha256"] = _stable_hash(body)
    return body


def _error_receipt(phase: str, code: str) -> dict[str, Any]:
    reason = code if code in ERROR_CODES else "INTERNAL_ERROR"
    body: dict[str, Any] = {
        "schema": ERROR_SCHEMA,
        "phase": phase,
        "status": "ERROR",
        "reason_codes": [reason],
    }
    body["receipt_sha256"] = _stable_hash(body)
    return body


def _validate_prepare_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RECEIPT_KEYS:
        raise GuardError("RECEIPT_INVALID")
    if (
        value.get("schema") != RECEIPT_SCHEMA
        or value.get("phase") != "prepare"
        or value.get("status") != "READY"
        or value.get("reason_codes") != []
        or not isinstance(value.get("git_version"), str)
        or value.get("object_format") not in {"sha1", "sha256"}
    ):
        raise GuardError("RECEIPT_INVALID")
    counts = value.get("counts")
    if (
        not isinstance(counts, dict)
        or set(counts) != set(COUNT_KEYS)
        or any(
            isinstance(item, bool) or not isinstance(item, int) or item < 0
            for item in counts.values()
        )
    ):
        raise GuardError("RECEIPT_INVALID")
    hashes = value.get("hashes")
    if (
        not isinstance(hashes, dict)
        or set(hashes) != set(HASH_KEYS)
        or any(
            not isinstance(item, str) or not SHA256_RE.fullmatch(item)
            for item in hashes.values()
        )
    ):
        raise GuardError("RECEIPT_INVALID")
    receipt_hash = value.get("receipt_sha256")
    if not isinstance(receipt_hash, str) or not SHA256_RE.fullmatch(receipt_hash):
        raise GuardError("RECEIPT_INVALID")
    unsigned = dict(value)
    del unsigned["receipt_sha256"]
    if _stable_hash(unsigned) != receipt_hash:
        raise GuardError("RECEIPT_INVALID")
    return value


def _common_context(
    arguments: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    api = _read_api_binding(
        arguments.project,
        arguments.mr,
        arguments.branch,
    )
    source = _source_context(
        git_binary=arguments.git,
        repository_text=arguments.repository,
        discovery_remote=arguments.discovery_remote,
        api=api,
        prepared_sha_text=arguments.prepared_sha,
    )
    transaction = _transaction_context(
        git_binary=source["git_binary"],
        transaction_text=arguments.transaction_dir,
        source=source,
    )
    return source, transaction


def command_prepare(arguments: argparse.Namespace) -> dict[str, Any]:
    api = _read_api_binding(
        arguments.project,
        arguments.mr,
        arguments.branch,
    )
    source = _source_context(
        git_binary=arguments.git,
        repository_text=arguments.repository,
        discovery_remote=arguments.discovery_remote,
        api=api,
        prepared_sha_text=arguments.prepared_sha,
    )
    _prepare_transaction(
        git_binary=source["git_binary"],
        transaction_text=arguments.transaction_dir,
        source=source,
    )
    transaction = _transaction_context(
        git_binary=source["git_binary"],
        transaction_text=arguments.transaction_dir,
        source=source,
    )
    return _ready_receipt(
        "prepare",
        source,
        transaction,
        _digest_text("no-prior-receipt"),
    )


def command_verify(arguments: argparse.Namespace) -> dict[str, Any]:
    prepare_receipt = _validate_prepare_receipt(
        _load_private_json(arguments.receipt, canonical=True)
    )
    source, transaction = _common_context(arguments)
    expected_prepare = _ready_receipt(
        "prepare",
        source,
        transaction,
        _digest_text("no-prior-receipt"),
    )
    if expected_prepare != prepare_receipt:
        raise ReportOnly("CONFIGURATION_DRIFT")
    return _ready_receipt(
        "verify",
        source,
        transaction,
        prepare_receipt["receipt_sha256"],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        description="Prepare or verify a local GitLab publication binding.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "verify"):
        command = subparsers.add_parser(name)
        command.add_argument("--repository", required=True)
        command.add_argument("--discovery-remote", required=True)
        command.add_argument("--transaction-dir", required=True)
        command.add_argument("--project", required=True)
        command.add_argument("--mr", required=True)
        command.add_argument("--branch", required=True)
        command.add_argument("--prepared-sha", required=True)
        command.add_argument("--git", default="git")
        if name == "verify":
            command.add_argument("--receipt", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    phase = "unknown"
    try:
        arguments = build_parser().parse_args(argv)
        phase = arguments.command
        if arguments.command == "prepare":
            receipt = command_prepare(arguments)
        elif arguments.command == "verify":
            receipt = command_verify(arguments)
        else:
            raise GuardError("ARGUMENT_ERROR")
        print(_canonical(receipt))
        return 0
    except ReportOnly as exc:
        print(_canonical(_report_only_receipt(phase, exc.codes)))
        return 2
    except GuardError as exc:
        print(_canonical(_error_receipt(phase, exc.code)))
        return 1
    except ParserExit:
        return 0
    except BaseException:
        print(_canonical(_error_receipt(phase, "INTERNAL_ERROR")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
