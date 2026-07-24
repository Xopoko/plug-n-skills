#!/usr/bin/env python3
"""Audit and repair one external Git worktree convenience symlink safely."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Sequence


AUDIT_SCHEMA = "git_worktree_safety.audit.v1"
REPAIR_SCHEMA = "git_worktree_safety.repair.v1"
ERROR_SCHEMA = "git_worktree_safety.error.v1"
MAX_COMMAND_BYTES = 2 * 1024 * 1024
MAX_JSON_BYTES = 64 * 1024
MAX_WORKTREES = 512
MAX_EXPECTED_COMMITS = 32
MAX_REFLOG_BYTES = 1024 * 1024
MAX_REFLOG_ENTRIES = 4096
COMMAND_TIMEOUT_SECONDS = 15
OID_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
ZERO_OIDS = {"0" * 40, "0" * 64}
STATUS_ARGS = (
    "status",
    "--porcelain=v2",
    "--branch",
    "-z",
    "--untracked-files=all",
    "--ignore-submodules=none",
)
WORKTREE_ARGS = (
    "worktree",
    "list",
    "--porcelain",
    "-z",
    "--expire=now",
)
IN_PROGRESS_MARKERS = (
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
    "BISECT_LOG",
    "rebase-merge",
    "rebase-apply",
    "sequencer",
)


class GuardError(Exception):
    """Base class for public-safe failures."""


class InputError(GuardError):
    """Malformed or contradictory caller input."""


class EvidenceError(GuardError):
    """Required read-only evidence could not be collected safely."""


class RepairIOError(GuardError):
    """The exact pointer repair could not be completed."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError("argument_error")


def stable_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def bytes_digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def raw_string_id(value: str) -> str:
    return f"sha256:{hashlib.sha256(os.fsencode(value)).hexdigest()}"


def normalized_absolute(raw: str) -> str:
    if not raw or "\x00" in raw or len(os.fsencode(raw)) > 8192:
        raise InputError("invalid_path")
    return os.path.abspath(os.path.expanduser(raw))


def path_id(raw: str, *, follow: bool) -> str:
    value = os.path.realpath(raw) if follow else os.path.abspath(raw)
    value = os.path.normcase(value)
    return raw_string_id(value)


def same_path(left: str, right: str) -> bool:
    try:
        return os.path.samefile(left, right)
    except (FileNotFoundError, NotADirectoryError, OSError):
        return os.path.normcase(os.path.realpath(left)) == os.path.normcase(
            os.path.realpath(right)
        )


def inspect_target_exists(path: str) -> bool:
    try:
        os.stat(path)
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError as exc:
        raise EvidenceError("link_target_uninspectable") from exc


def same_existing_path(left: str, right: str) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError as exc:
        raise EvidenceError("link_target_uninspectable") from exc


def path_is_within(candidate: str, parent: str) -> bool:
    candidate_parent = os.path.realpath(os.path.dirname(candidate))
    candidate_key = os.path.join(candidate_parent, os.path.basename(candidate))
    parent_key = os.path.realpath(parent)
    try:
        return os.path.commonpath((candidate_key, parent_key)) == parent_key
    except ValueError:
        return False


def add_reason(reasons: list[str], code: str) -> None:
    if code not in reasons:
        reasons.append(code)


def valid_oid(value: str | None) -> bool:
    return isinstance(value, str) and OID_RE.fullmatch(value) is not None


def valid_ref(value: str) -> bool:
    return (
        value.startswith("refs/heads/")
        and len(value.encode("utf-8", "surrogateescape")) <= 4096
        and "\x00" not in value
        and "\n" not in value
        and "\r" not in value
    )


def git_command_allowed(arguments: Sequence[str]) -> bool:
    args = tuple(arguments)
    if args in {
        ("rev-parse", "--git-common-dir"),
        ("rev-parse", "--git-dir"),
        ("rev-parse", "--show-object-format"),
        WORKTREE_ARGS,
        STATUS_ARGS,
        ("symbolic-ref", "-q", "HEAD"),
        ("rev-parse", "--verify", "HEAD^{commit}"),
        ("config", "--get", "extensions.refStorage"),
    }:
        return True
    if len(args) == 2 and args[0] == "check-ref-format":
        return valid_ref(args[1])
    if (
        len(args) == 4
        and args[:3] == ("show-ref", "--verify", "--hash")
        and valid_ref(args[3])
    ):
        return True
    if (
        len(args) == 3
        and args[:2] == ("cat-file", "-t")
        and valid_oid(args[2])
    ):
        return True
    if (
        len(args) == 4
        and args[:2] == ("merge-base", "--is-ancestor")
        and valid_oid(args[2])
        and valid_oid(args[3])
    ):
        return True
    return False


class GitRunner:
    """Run only the fixed read-only Git probes used by this guard."""

    def __init__(self, cwd: str):
        self.cwd = normalized_absolute(cwd)

    def run(
        self,
        arguments: Sequence[str],
        *,
        accepted: Iterable[int] = (0,),
    ) -> subprocess.CompletedProcess[bytes]:
        args = tuple(arguments)
        if not git_command_allowed(args):
            raise InputError("git_command_not_allowlisted")

        environment = os.environ.copy()
        for key in list(environment):
            if key.startswith("GIT_"):
                environment.pop(key, None)
        environment.update(
            {
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_NO_LAZY_FETCH": "1",
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_GRAFT_FILE": os.devnull,
                "GIT_TERMINAL_PROMPT": "0",
                "LC_ALL": "C",
            }
        )
        command = [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            "-C",
            self.cwd,
            *args,
        ]
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
            )
        except OSError as exc:
            raise EvidenceError("git_probe_unavailable") from exc

        assert process.stdout is not None
        assert process.stderr is not None
        overflow = threading.Event()
        read_failed = threading.Event()
        stdout_box: list[bytes] = []
        stderr_box: list[bytes] = []

        def read_bounded(stream: Any, destination: list[bytes]) -> None:
            chunks: list[bytes] = []
            remaining = MAX_COMMAND_BYTES + 1
            try:
                while remaining:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                destination.append(b"".join(chunks))
                if remaining == 0:
                    overflow.set()
            except OSError:
                read_failed.set()
            finally:
                try:
                    stream.close()
                except OSError:
                    pass

        readers = (
            threading.Thread(
                target=read_bounded,
                args=(process.stdout, stdout_box),
                daemon=True,
            ),
            threading.Thread(
                target=read_bounded,
                args=(process.stderr, stderr_box),
                daemon=True,
            ),
        )
        for reader in readers:
            reader.start()

        def stop_process() -> None:
            if process.poll() is not None:
                return
            try:
                process.terminate()
                process.wait(timeout=0.5)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
                try:
                    process.wait(timeout=0.5)
                except (OSError, subprocess.TimeoutExpired):
                    pass

        deadline = time.monotonic() + COMMAND_TIMEOUT_SECONDS
        timed_out = False
        while process.poll() is None:
            if overflow.is_set() or read_failed.is_set():
                stop_process()
                break
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                timed_out = True
                stop_process()
                break
            try:
                process.wait(timeout=min(0.05, remaining_time))
            except subprocess.TimeoutExpired:
                continue
        for reader in readers:
            reader.join(timeout=1)
        if any(reader.is_alive() for reader in readers):
            stop_process()
            raise EvidenceError("git_probe_unavailable")
        if timed_out or read_failed.is_set():
            raise EvidenceError("git_probe_unavailable")
        if overflow.is_set():
            raise EvidenceError("git_probe_output_too_large")
        stdout = stdout_box[0] if stdout_box else b""
        stderr = stderr_box[0] if stderr_box else b""
        result = subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout,
            stderr,
        )
        if result.returncode not in set(accepted):
            raise EvidenceError("git_probe_failed")
        return result


def _decode_single_line(data: bytes, code: str) -> str:
    if data.endswith(b"\n"):
        data = data[:-1]
    if not data or b"\x00" in data or b"\n" in data or b"\r" in data:
        raise EvidenceError(code)
    return os.fsdecode(data)


def _read_oid(result: subprocess.CompletedProcess[bytes]) -> str:
    oid = _decode_single_line(result.stdout, "invalid_oid_evidence")
    if not valid_oid(oid):
        raise EvidenceError("invalid_oid_evidence")
    return oid


def resolve_git_path(runner: GitRunner, option: str) -> str:
    result = runner.run(("rev-parse", option))
    raw = _decode_single_line(result.stdout, "invalid_git_path_evidence")
    if os.path.isabs(raw):
        return os.path.realpath(raw)
    return os.path.realpath(os.path.join(runner.cwd, raw))


def parse_worktree_porcelain(data: bytes) -> list[dict[str, Any]]:
    if len(data) > MAX_COMMAND_BYTES:
        raise EvidenceError("worktree_inventory_too_large")
    tokens = data.split(b"\x00")
    if len(tokens) < 3 or tokens[-2:] != [b"", b""]:
        raise EvidenceError("malformed_worktree_inventory")
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    seen_fields: set[str] = set()

    def finish() -> None:
        nonlocal current, seen_fields
        if not current:
            raise EvidenceError("malformed_worktree_inventory")
        if "path" not in current:
            raise EvidenceError("malformed_worktree_inventory")
        if current.get("bare"):
            if any(
                key in current
                for key in ("head", "branch", "detached")
            ):
                raise EvidenceError("malformed_worktree_inventory")
        else:
            if "head" not in current:
                raise EvidenceError("malformed_worktree_inventory")
            if current.get("detached"):
                if current.get("branch") is not None:
                    raise EvidenceError("malformed_worktree_inventory")
            elif current.get("branch") is None:
                raise EvidenceError("malformed_worktree_inventory")
        current.setdefault("head", None)
        current.setdefault("branch", None)
        current.setdefault("bare", False)
        current.setdefault("detached", False)
        current.setdefault("locked", False)
        current.setdefault("prunable", False)
        current.setdefault("unknown_fields", [])
        records.append(current)
        if len(records) > MAX_WORKTREES:
            raise EvidenceError("too_many_worktrees")
        current = {}
        seen_fields = set()

    for token in tokens[:-1]:
        if token == b"":
            finish()
            continue
        key_bytes, separator, value = token.partition(b" ")
        try:
            key = key_bytes.decode("ascii")
        except UnicodeDecodeError as exc:
            raise EvidenceError("malformed_worktree_inventory") from exc
        if not current and key != "worktree":
            raise EvidenceError("malformed_worktree_inventory")
        mapped = {"worktree": "path", "HEAD": "head"}.get(key, key)
        if mapped in seen_fields:
            raise EvidenceError("duplicate_worktree_field")
        seen_fields.add(mapped)
        if key == "worktree":
            if separator != b" " or not value:
                raise EvidenceError("malformed_worktree_inventory")
            path = os.fsdecode(value)
            if not os.path.isabs(path):
                raise EvidenceError("malformed_worktree_inventory")
            current["path"] = path
        elif key == "HEAD":
            if set(current) != {"path"}:
                raise EvidenceError("malformed_worktree_inventory")
            head = value.decode("ascii", "strict") if separator else ""
            if not valid_oid(head):
                raise EvidenceError("malformed_worktree_inventory")
            current["head"] = head
        elif key == "branch":
            if separator != b" " or not value:
                raise EvidenceError("malformed_worktree_inventory")
            branch = os.fsdecode(value)
            if "head" not in current or not valid_ref(branch):
                raise EvidenceError("malformed_worktree_inventory")
            current["branch"] = branch
        elif key in {"bare", "detached"}:
            if separator or (
                key == "bare" and set(current) != {"path"}
            ) or (
                key == "detached" and "head" not in current
            ):
                raise EvidenceError("malformed_worktree_inventory")
            current[key] = True
        elif key in {"locked", "prunable"}:
            if "head" not in current and not current.get("bare"):
                raise EvidenceError("malformed_worktree_inventory")
            current[key] = True
        else:
            current.setdefault("unknown_fields", []).append(key)
    if current:
        raise EvidenceError("malformed_worktree_inventory")
    if not records:
        raise EvidenceError("empty_worktree_inventory")
    return records


def parse_status_evidence(data: bytes) -> dict[str, Any]:
    if not data or not data.endswith(b"\x00"):
        raise EvidenceError("malformed_status_evidence")
    records = data[:-1].split(b"\x00")
    if len(records) < 2 or any(not record for record in records):
        raise EvidenceError("malformed_status_evidence")
    if not records[0].startswith(b"# branch.oid "):
        raise EvidenceError("malformed_status_evidence")
    oid_bytes = records[0][len(b"# branch.oid "):]
    if oid_bytes == b"(initial)":
        status_oid = "(initial)"
    else:
        try:
            status_oid = oid_bytes.decode("ascii")
        except UnicodeDecodeError as exc:
            raise EvidenceError("malformed_status_evidence") from exc
        if not valid_oid(status_oid):
            raise EvidenceError("malformed_status_evidence")
    if not records[1].startswith(b"# branch.head "):
        raise EvidenceError("malformed_status_evidence")
    head_bytes = records[1][len(b"# branch.head "):]
    if not head_bytes or b"\n" in head_bytes or b"\r" in head_bytes:
        raise EvidenceError("malformed_status_evidence")
    status_head = os.fsdecode(head_bytes)

    optional_headers: set[bytes] = set()
    clean = True
    entries_started = False
    for record in records[2:]:
        if not record.startswith(b"# "):
            clean = False
            entries_started = True
            continue
        if entries_started:
            raise EvidenceError("malformed_status_evidence")
        if record.startswith(b"# branch.upstream "):
            kind = b"upstream"
            if len(record) == len(b"# branch.upstream "):
                raise EvidenceError("malformed_status_evidence")
        elif record.startswith(b"# branch.ab "):
            kind = b"ab"
            if re.fullmatch(rb"# branch\.ab \+[0-9]+ -[0-9]+", record) is None:
                raise EvidenceError("malformed_status_evidence")
        else:
            raise EvidenceError("malformed_status_evidence")
        if kind in optional_headers:
            raise EvidenceError("malformed_status_evidence")
        optional_headers.add(kind)
    return {
        "clean": clean,
        "oid": status_oid,
        "head": status_head,
    }


def read_branch_reflog(
    common_dir: str,
    branch_ref: str,
    backend: str,
    oid_length: int,
) -> dict[str, Any]:
    result = {
        "backend": backend,
        "state": "absent",
        "complete": True,
        "oids": set(),
        "entry_count": 0,
    }
    if backend not in {"files", "unspecified"}:
        result["state"] = "unsupported"
        result["complete"] = False
        return result

    logs_root = os.path.realpath(os.path.join(common_dir, "logs"))
    reflog_path = os.path.realpath(os.path.join(logs_root, *branch_ref.split("/")))
    try:
        if os.path.commonpath((reflog_path, logs_root)) != logs_root:
            raise EvidenceError("unsafe_reflog_path")
    except ValueError as exc:
        raise EvidenceError("unsafe_reflog_path") from exc

    try:
        before = os.lstat(reflog_path)
    except FileNotFoundError:
        return result
    except OSError as exc:
        raise EvidenceError("reflog_unreadable") from exc
    if not stat.S_ISREG(before.st_mode):
        result["state"] = "unsupported"
        result["complete"] = False
        return result
    if before.st_size > MAX_REFLOG_BYTES:
        result["state"] = "truncated"
        result["complete"] = False
        start = before.st_size - MAX_REFLOG_BYTES
    else:
        result["state"] = "present"
        start = 0

    try:
        with open(reflog_path, "rb") as stream:
            if start:
                stream.seek(start)
                stream.readline()
            data = stream.read(MAX_REFLOG_BYTES + 1)
        after = os.lstat(reflog_path)
    except OSError as exc:
        raise EvidenceError("reflog_unreadable") from exc
    if len(data) > MAX_REFLOG_BYTES:
        data = data[:MAX_REFLOG_BYTES]
        result["state"] = "truncated"
        result["complete"] = False
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        result["state"] = "changed"
        result["complete"] = False
    if data and not data.endswith(b"\n"):
        result["state"] = "truncated"
        result["complete"] = False

    lines = data.splitlines()
    if len(lines) > MAX_REFLOG_ENTRIES:
        lines = lines[-MAX_REFLOG_ENTRIES:]
        result["state"] = "truncated"
        result["complete"] = False
    parsed = 0
    for line in lines:
        fields = line.split(b" ", 2)
        if len(fields) < 3:
            result["state"] = "malformed"
            result["complete"] = False
            continue
        try:
            old_oid = fields[0].decode("ascii")
            new_oid = fields[1].decode("ascii")
        except UnicodeDecodeError:
            result["state"] = "malformed"
            result["complete"] = False
            continue
        if (
            not valid_oid(old_oid)
            or not valid_oid(new_oid)
            or len(old_oid) != oid_length
            or len(new_oid) != oid_length
        ):
            result["state"] = "malformed"
            result["complete"] = False
            continue
        parsed += 1
        if old_oid not in ZERO_OIDS:
            result["oids"].add(old_oid)
        if new_oid not in ZERO_OIDS:
            result["oids"].add(new_oid)
    result["entry_count"] = parsed
    return result


def collect_ref_evidence(
    runner: GitRunner,
    common_dir: str,
    branch_ref: str,
    expected_commits: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []
    check = runner.run(("check-ref-format", branch_ref), accepted=(0, 1))
    if check.returncode != 0:
        raise InputError("invalid_branch_ref")

    object_format_result = runner.run(("rev-parse", "--show-object-format"))
    object_format = _decode_single_line(
        object_format_result.stdout,
        "invalid_object_format",
    )
    if object_format == "sha1":
        oid_length = 40
    elif object_format == "sha256":
        oid_length = 64
    else:
        raise EvidenceError("unsupported_object_format")

    show = runner.run(
        ("show-ref", "--verify", "--hash", branch_ref),
        accepted=(0, 1),
    )
    ref_oid: str | None = None
    ref_state = "missing"
    if show.returncode == 0:
        ref_oid = _read_oid(show)
        commit = runner.run(
            ("cat-file", "-t", ref_oid),
            accepted=(0, 1, 128),
        )
        if (
            commit.returncode == 0
            and _decode_single_line(
                commit.stdout,
                "invalid_object_type_evidence",
            )
            == "commit"
        ):
            ref_state = "live"
        else:
            ref_state = "non-commit"
            add_reason(reasons, "branch_ref_not_commit")
    else:
        add_reason(reasons, "branch_ref_missing")

    backend_result = runner.run(
        ("config", "--get", "extensions.refStorage"),
        accepted=(0, 1),
    )
    backend = "unspecified"
    if backend_result.returncode == 0:
        raw_backend = _decode_single_line(
            backend_result.stdout,
            "invalid_ref_backend",
        )
        backend = raw_backend.lower()
    reflog = read_branch_reflog(
        common_dir,
        branch_ref,
        backend,
        oid_length,
    )
    if reflog["state"] == "absent":
        warnings.append("branch_reflog_absent")
    elif not reflog["complete"]:
        warnings.append("branch_reflog_incomplete")

    classifications: list[dict[str, str]] = []
    for oid in expected_commits:
        if len(oid) != oid_length:
            classifications.append(
                {"oid": oid, "retention": "non-canonical-oid"}
            )
            add_reason(reasons, "expected_commit_not_full_oid")
            continue
        object_result = runner.run(
            ("cat-file", "-t", oid),
            accepted=(0, 1, 128),
        )
        object_exists = object_result.returncode == 0
        object_is_commit = False
        if object_exists:
            object_is_commit = (
                _decode_single_line(
                    object_result.stdout,
                    "invalid_object_type_evidence",
                )
                == "commit"
            )
        branch_reachable = False
        if object_is_commit and ref_state == "live" and ref_oid is not None:
            ancestor = runner.run(
                ("merge-base", "--is-ancestor", oid, ref_oid),
                accepted=(0, 1),
            )
            branch_reachable = ancestor.returncode == 0

        if object_exists and not object_is_commit:
            retention = "not-commit"
            add_reason(reasons, "expected_object_not_commit")
        elif branch_reachable:
            retention = "branch-reachable"
        elif object_exists and oid in reflog["oids"]:
            retention = "reflog-only"
            add_reason(reasons, "expected_commit_reflog_only")
        elif not object_exists:
            retention = "missing"
            add_reason(reasons, "expected_commit_missing")
        elif not reflog["complete"]:
            retention = "retention-unknown"
            add_reason(reasons, "expected_commit_retention_unknown")
        else:
            retention = "object-only"
            add_reason(reasons, "expected_commit_object_only")
        classifications.append({"oid": oid, "retention": retention})

    public = {
        "branch_ref": branch_ref,
        "object_format": object_format,
        "oid_length": oid_length,
        "ref_oid": ref_oid,
        "ref_state": ref_state,
        "reflog_backend": reflog["backend"],
        "reflog_state": reflog["state"],
        "reflog_complete": reflog["complete"],
        "reflog_entry_count": reflog["entry_count"],
        "expected_commits": classifications,
    }
    private = {
        "ref_oid": ref_oid,
        "ref_state": ref_state,
        "classifications": classifications,
    }
    return public, private, reasons, warnings


def collect_operation_state(git_dir: str) -> list[str]:
    active: list[str] = []
    root = os.path.realpath(git_dir)
    for marker in IN_PROGRESS_MARKERS:
        candidate = os.path.realpath(os.path.join(root, marker))
        try:
            if os.path.commonpath((candidate, root)) != root:
                raise EvidenceError("unsafe_git_state_path")
        except ValueError as exc:
            raise EvidenceError("unsafe_git_state_path") from exc
        if os.path.lexists(candidate):
            active.append(marker.lower().replace("_", "-"))
    return active


def collect_worktree_evidence(
    repo_runner: GitRunner,
    replacement_runner: GitRunner,
    common_dir: str,
    replacement: str,
    branch_ref: str,
    ref_oid: str | None,
    records: Sequence[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    reasons: list[str] = []
    replacement_exists = os.path.isdir(replacement)
    replacement_is_symlink = os.path.islink(replacement)
    if not replacement_exists:
        add_reason(reasons, "replacement_missing")
    if replacement_is_symlink:
        add_reason(reasons, "replacement_path_is_symlink")

    path_records = [
        item for item in records if same_path(item["path"], replacement)
    ]
    branch_records = [
        item for item in records if item.get("branch") == branch_ref
    ]
    if not path_records:
        add_reason(reasons, "replacement_not_registered")
    elif len(path_records) > 1:
        add_reason(reasons, "replacement_registration_ambiguous")
    if not branch_records:
        add_reason(reasons, "branch_not_registered")
    elif len(branch_records) > 1:
        add_reason(reasons, "branch_registration_ambiguous")

    entry = path_records[0] if len(path_records) == 1 else None
    if entry is not None and entry.get("branch") != branch_ref:
        add_reason(reasons, "replacement_wrong_branch")
    if (
        len(branch_records) == 1
        and not same_path(branch_records[0]["path"], replacement)
    ):
        add_reason(reasons, "replacement_wrong_branch")
    if entry is not None:
        for field, code in (
            ("bare", "replacement_bare"),
            ("detached", "replacement_detached"),
            ("locked", "replacement_locked"),
            ("prunable", "replacement_prunable"),
        ):
            if entry.get(field):
                add_reason(reasons, code)
        if entry.get("unknown_fields"):
            add_reason(reasons, "replacement_record_unsupported")

    replacement_common_id: str | None = None
    symbolic_ref: str | None = None
    head_oid: str | None = None
    clean = False
    status_hash: str | None = None
    status_oid: str | None = None
    status_branch_head: str | None = None
    status_oid_matches_head = False
    status_branch_matches_ref = False
    operation_state: list[str] = []
    git_dir_id: str | None = None
    if replacement_exists:
        replacement_common = resolve_git_path(
            replacement_runner,
            "--git-common-dir",
        )
        replacement_common_id = path_id(replacement_common, follow=True)
        if not same_path(common_dir, replacement_common):
            add_reason(reasons, "repository_common_dir_mismatch")

        symbolic = replacement_runner.run(
            ("symbolic-ref", "-q", "HEAD"),
            accepted=(0, 1),
        )
        if symbolic.returncode == 0:
            symbolic_ref = _decode_single_line(
                symbolic.stdout,
                "invalid_symbolic_ref_evidence",
            )
        else:
            add_reason(reasons, "replacement_detached")
        if symbolic_ref != branch_ref:
            add_reason(reasons, "symbolic_branch_mismatch")

        head = replacement_runner.run(
            ("rev-parse", "--verify", "HEAD^{commit}"),
            accepted=(0, 128),
        )
        if head.returncode == 0:
            head_oid = _read_oid(head)
        else:
            add_reason(reasons, "replacement_head_missing")
        if ref_oid is None or head_oid != ref_oid:
            add_reason(reasons, "replacement_head_ref_mismatch")
        if entry is not None and entry.get("head") != head_oid:
            add_reason(reasons, "worktree_record_head_mismatch")

        status_result = replacement_runner.run(STATUS_ARGS)
        status_hash = bytes_digest(status_result.stdout)
        status_evidence = parse_status_evidence(status_result.stdout)
        clean = bool(status_evidence["clean"])
        status_oid = status_evidence["oid"]
        status_branch_head = status_evidence["head"]
        status_oid_matches_head = (
            head_oid is not None
            and status_oid == head_oid
            and status_oid != "(initial)"
        )
        expected_branch_head = branch_ref[len("refs/heads/"):]
        status_branch_matches_ref = (
            status_branch_head == expected_branch_head
            and status_branch_head != "(detached)"
        )
        if not clean:
            add_reason(reasons, "replacement_dirty")
        if not status_oid_matches_head:
            add_reason(reasons, "status_oid_mismatch")
        if not status_branch_matches_ref:
            add_reason(reasons, "status_branch_mismatch")

        git_dir = resolve_git_path(replacement_runner, "--git-dir")
        git_dir_id = path_id(git_dir, follow=True)
        operation_state = collect_operation_state(git_dir)
        if operation_state:
            add_reason(reasons, "git_operation_in_progress")

    public = {
        "repository_id": path_id(common_dir, follow=True),
        "inventory_count": len(records),
        "branch_registration_count": len(branch_records),
        "replacement_registration_count": len(path_records),
        "replacement_id": path_id(replacement, follow=True),
        "replacement_common_id": replacement_common_id,
        "registered_head_oid": entry.get("head") if entry else None,
        "symbolic_ref": symbolic_ref,
        "head_oid": head_oid,
        "clean": clean,
        "locked": bool(entry and entry.get("locked")),
        "prunable": bool(entry and entry.get("prunable")),
        "detached": bool(entry and entry.get("detached")),
        "operation_state": operation_state,
        "status_hash": status_hash,
        "status_oid": status_oid,
        "status_branch_head": status_branch_head,
        "status_oid_matches_head": status_oid_matches_head,
        "status_branch_matches_ref": status_branch_matches_ref,
    }
    private = {
        "eligible": not reasons,
        "entry": entry,
        "git_dir_id": git_dir_id,
        "operation_state": operation_state,
    }
    return public, private, reasons


def dir_fd_repair_supported() -> bool:
    required = (os.stat, os.readlink, os.symlink, os.unlink)
    try:
        replace_parameters = inspect.signature(os.replace).parameters
    except (TypeError, ValueError):
        return False
    return (
        os.name == "posix"
        and hasattr(os, "O_DIRECTORY")
        and hasattr(os, "O_NOFOLLOW")
        and all(function in os.supports_dir_fd for function in required)
        and os.stat in os.supports_follow_symlinks
        and {"src_dir_fd", "dst_dir_fd"}.issubset(replace_parameters)
    )


def open_link_parent(link: str) -> tuple[int, tuple[int, int, int, int]]:
    parent = os.path.dirname(link)
    try:
        before = os.lstat(parent)
    except OSError as exc:
        raise EvidenceError("link_parent_unavailable") from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISDIR(before.st_mode):
        raise EvidenceError("link_parent_unsafe")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(parent, flags)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise EvidenceError("link_parent_unavailable") from exc
    before_key = (
        before.st_dev,
        before.st_ino,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    after_key = (
        after.st_dev,
        after.st_ino,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if before_key[:2] != after_key[:2]:
        os.close(descriptor)
        raise EvidenceError("link_parent_changed")
    return descriptor, after_key


def inspect_link(
    link: str,
    replacement: str,
    expected_old_target: str | None,
    new_target: str | None,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    reasons: list[str] = []
    name = os.path.basename(link)
    if not name:
        raise InputError("invalid_link_path")
    parent_id = path_id(os.path.dirname(link), follow=True)
    platform_supported = dir_fd_repair_supported()
    descriptor: int | None = None
    parent_signature: tuple[int, int, int, int] | None = None
    try:
        if platform_supported:
            descriptor, parent_signature = open_link_parent(link)
            try:
                link_stat = os.stat(
                    name,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                link_stat = None
        else:
            try:
                link_stat = os.lstat(link)
            except FileNotFoundError:
                link_stat = None

        raw_target: str | None = None
        target_exists = False
        resolves_to_replacement = False
        if link_stat is None:
            state = "missing"
            add_reason(reasons, "link_missing")
        elif stat.S_ISLNK(link_stat.st_mode):
            raw_target = (
                os.readlink(name, dir_fd=descriptor)
                if descriptor is not None
                else os.readlink(link)
            )
            resolved = (
                raw_target
                if os.path.isabs(raw_target)
                else os.path.join(os.path.dirname(link), raw_target)
            )
            target_exists = inspect_target_exists(resolved)
            resolves_to_replacement = target_exists and same_existing_path(
                resolved,
                replacement,
            )
            if resolves_to_replacement:
                state = "current"
            elif target_exists:
                state = "live-other"
                add_reason(reasons, "link_target_exists")
            else:
                state = "broken"
                if expected_old_target is None:
                    add_reason(reasons, "expected_old_target_required")
                elif raw_target != expected_old_target:
                    add_reason(reasons, "link_raw_target_mismatch")
                if new_target is None:
                    add_reason(reasons, "new_target_required")
                else:
                    proposed = (
                        new_target
                        if os.path.isabs(new_target)
                        else os.path.join(os.path.dirname(link), new_target)
                    )
                    if not inspect_target_exists(proposed) or not same_existing_path(
                        proposed,
                        replacement,
                    ):
                        add_reason(reasons, "new_target_not_replacement")
                if not platform_supported:
                    add_reason(reasons, "repair_platform_unsupported")
        elif stat.S_ISDIR(link_stat.st_mode):
            state = "directory"
            add_reason(reasons, "link_is_directory")
        else:
            state = "file"
            add_reason(reasons, "link_not_symlink")

        signature = None
        if link_stat is not None:
            signature = (
                link_stat.st_dev,
                link_stat.st_ino,
                link_stat.st_mtime_ns,
                link_stat.st_ctime_ns,
                raw_string_id(raw_target) if raw_target is not None else None,
            )
        public = {
            "path_id": path_id(link, follow=False),
            "parent_id": parent_id,
            "state": state,
            "raw_target_id": (
                raw_string_id(raw_target) if raw_target is not None else None
            ),
            "target_exists": target_exists,
            "resolves_to_replacement": resolves_to_replacement,
            "repair_platform_supported": platform_supported,
        }
        private = {
            "raw_target": raw_target,
            "signature": signature,
            "parent_signature": parent_signature,
            "state": state,
        }
        return public, private, reasons
    finally:
        if descriptor is not None:
            os.close(descriptor)


def collect_audit(options: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    repo_runner = GitRunner(options.repo)
    replacement_runner = GitRunner(options.replacement)
    common_dir = resolve_git_path(repo_runner, "--git-common-dir")
    records = parse_worktree_porcelain(repo_runner.run(WORKTREE_ARGS).stdout)

    ref_public, ref_private, ref_reasons, warnings = collect_ref_evidence(
        repo_runner,
        common_dir,
        options.branch_ref,
        options.expected_commit,
    )
    worktree_public, worktree_private, worktree_reasons = (
        collect_worktree_evidence(
            repo_runner,
            replacement_runner,
            common_dir,
            options.replacement,
            options.branch_ref,
            ref_private["ref_oid"],
            records,
        )
    )

    location_reasons: list[str] = []
    protected_roots = [common_dir]
    protected_roots.extend(item["path"] for item in records)
    for protected in protected_roots:
        if path_is_within(options.link, protected):
            add_reason(location_reasons, "link_inside_git_or_worktree")
            break

    link_public, link_private, link_reasons = inspect_link(
        options.link,
        options.replacement,
        options.expected_old_target,
        options.new_target,
    )
    if link_public["state"] == "broken":
        warnings.append("missing_target_uncommitted_state_unverifiable")

    reasons: list[str] = []
    for code in (
        *ref_reasons,
        *worktree_reasons,
        *location_reasons,
        *link_reasons,
    ):
        add_reason(reasons, code)

    expected_branch_reachable = bool(options.expected_commit) and all(
        item["retention"] == "branch-reachable"
        for item in ref_private["classifications"]
    )
    git_eligible = (
        ref_private["ref_state"] == "live"
        and expected_branch_reachable
        and worktree_private["eligible"]
        and not location_reasons
    )
    if git_eligible:
        authority = "repoint"
    elif any(
        item["retention"] in {
            "reflog-only",
            "object-only",
            "retention-unknown",
        }
        for item in ref_private["classifications"]
    ):
        authority = "salvage-only"
    else:
        authority = "none"

    git_material = {
        "branch": ref_public,
        "worktree": {
            key: worktree_public[key]
            for key in (
                "repository_id",
                "replacement_id",
                "replacement_common_id",
                "registered_head_oid",
                "symbolic_ref",
                "head_oid",
                "clean",
                "locked",
                "prunable",
                "detached",
                "operation_state",
                "status_hash",
                "status_oid",
                "status_branch_head",
                "status_oid_matches_head",
                "status_branch_matches_ref",
                "branch_registration_count",
                "replacement_registration_count",
            )
        },
    }
    git_fingerprint = stable_digest(git_material)
    audit_material = {
        "git_fingerprint": git_fingerprint,
        "link": link_public,
        "link_signature": link_private["signature"],
        "parent_signature": link_private["parent_signature"],
        "expected_old_target_id": (
            raw_string_id(options.expected_old_target)
            if options.expected_old_target is not None
            else None
        ),
        "new_target_id": (
            raw_string_id(options.new_target)
            if options.new_target is not None
            else None
        ),
    }
    fingerprint = stable_digest(audit_material)

    if not reasons and link_public["state"] == "current":
        status_value = "noop"
    elif not reasons and link_public["state"] == "broken" and git_eligible:
        status_value = "ready"
    else:
        status_value = "blocked"
    repair_allowed = status_value == "ready"
    public = {
        "schema": AUDIT_SCHEMA,
        "operation": "audit",
        "status": status_value,
        "authority": authority,
        "branch": ref_public,
        "worktree": worktree_public,
        "link": link_public,
        "git_fingerprint": git_fingerprint,
        "fingerprint": fingerprint,
        "decision": {
            "repair_allowed": repair_allowed,
            "reasons": reasons,
            "warnings": warnings,
        },
    }
    private = {
        "git_fingerprint": git_fingerprint,
        "fingerprint": fingerprint,
        "link": link_private,
        "records": records,
    }
    return public, private


def _repair_blocked(
    audit: dict[str, Any],
    reasons: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema": REPAIR_SCHEMA,
        "operation": "repair-link",
        "status": "blocked",
        "mutation_performed": False,
        "authority": audit.get("authority", "none"),
        "audit_status": audit.get("status"),
        "fingerprint": audit.get("fingerprint"),
        "git_fingerprint": audit.get("git_fingerprint"),
        "link": audit.get("link"),
        "decision": {
            "repair_allowed": False,
            "reasons": list(dict.fromkeys(reasons)),
        },
    }


def _postcondition_unavailable(
    audit: dict[str, Any],
    private: dict[str, Any],
    reasons: Sequence[str],
    immediate_raw_target: str | None,
) -> dict[str, Any]:
    return {
        "schema": REPAIR_SCHEMA,
        "operation": "repair-link",
        "status": "postcondition-unavailable",
        "mutation_performed": True,
        "authority_before": audit["authority"],
        "audit_fingerprint_before": private["fingerprint"],
        "git_fingerprint_before": private["git_fingerprint"],
        "immediate_raw_target_id": (
            raw_string_id(immediate_raw_target)
            if immediate_raw_target is not None
            else None
        ),
        "decision": {
            "repair_allowed": False,
            "reasons": list(dict.fromkeys(reasons)),
        },
    }


def _link_snapshot_at(descriptor: int, name: str) -> tuple[Any, ...]:
    try:
        value = os.stat(
            name,
            dir_fd=descriptor,
            follow_symlinks=False,
        )
    except OSError as exc:
        raise RepairIOError("link_recheck_failed") from exc
    if not stat.S_ISLNK(value.st_mode):
        raise RepairIOError("link_recheck_failed")
    try:
        raw_target = os.readlink(name, dir_fd=descriptor)
    except OSError as exc:
        raise RepairIOError("link_recheck_failed") from exc
    return (
        value.st_dev,
        value.st_ino,
        value.st_mtime_ns,
        value.st_ctime_ns,
        raw_string_id(raw_target),
        raw_target,
    )


def replace_link_entry(
    descriptor: int,
    source_name: str,
    destination_name: str,
) -> None:
    os.replace(
        source_name,
        destination_name,
        src_dir_fd=descriptor,
        dst_dir_fd=descriptor,
    )


def read_replaced_link(descriptor: int, name: str) -> str:
    return os.readlink(name, dir_fd=descriptor)


def close_repair_descriptor(descriptor: int) -> None:
    os.close(descriptor)


def repair_link(options: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    audit, private = collect_audit(options)
    if audit["status"] != "ready":
        return 2, _repair_blocked(
            audit,
            audit["decision"]["reasons"],
        )
    if audit["fingerprint"] != options.expected_fingerprint:
        return 2, _repair_blocked(audit, ["audit_fingerprint_changed"])
    if not audit["link"]["repair_platform_supported"]:
        return 2, _repair_blocked(audit, ["repair_platform_unsupported"])
    if private["link"]["raw_target"] != options.expected_old_target:
        return 2, _repair_blocked(audit, ["link_raw_target_mismatch"])

    descriptor, parent_signature = open_link_parent(options.link)
    temporary_name: str | None = None
    raw_target_after_replace: str | None = None
    immediate_verification_reason: str | None = None
    close_verification_reason: str | None = None
    mutation_performed = False
    name = os.path.basename(options.link)
    try:
        current = _link_snapshot_at(descriptor, name)
        expected_signature = private["link"]["signature"]
        if current[:5] != expected_signature or current[5] != options.expected_old_target:
            return 2, _repair_blocked(audit, ["link_changed_before_replace"])
        if parent_signature != private["link"]["parent_signature"]:
            return 2, _repair_blocked(audit, ["link_parent_changed"])

        for _ in range(16):
            candidate = f".git-worktree-safety-{secrets.token_hex(12)}"
            try:
                os.symlink(options.new_target, candidate, dir_fd=descriptor)
            except FileExistsError:
                continue
            except OSError as exc:
                raise RepairIOError("temporary_link_create_failed") from exc
            temporary_name = candidate
            break
        if temporary_name is None:
            raise RepairIOError("temporary_link_name_exhausted")

        final_check = _link_snapshot_at(descriptor, name)
        if (
            final_check[:5] != expected_signature
            or final_check[5] != options.expected_old_target
        ):
            return 2, _repair_blocked(audit, ["link_changed_before_replace"])
        try:
            replace_link_entry(
                descriptor,
                temporary_name,
                name,
            )
        except OSError as exc:
            raise RepairIOError("link_replace_failed") from exc
        mutation_performed = True
        temporary_name = None
        try:
            raw_target_after_replace = read_replaced_link(descriptor, name)
        except OSError:
            immediate_verification_reason = (
                "immediate_link_postcondition_unavailable"
            )
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=descriptor)
            except OSError:
                pass
        try:
            close_repair_descriptor(descriptor)
        except OSError as exc:
            if mutation_performed:
                close_verification_reason = (
                    "link_parent_close_unavailable"
                )
            else:
                raise RepairIOError("link_parent_close_failed") from exc

    unavailable_reasons = [
        reason
        for reason in (
            immediate_verification_reason,
            close_verification_reason,
        )
        if reason is not None
    ]
    if unavailable_reasons:
        return 1, _postcondition_unavailable(
            audit,
            private,
            unavailable_reasons,
            raw_target_after_replace,
        )
    try:
        post_audit, post_private = collect_audit(options)
    except Exception:
        return 1, _postcondition_unavailable(
            audit,
            private,
            ["post_audit_unavailable"],
            raw_target_after_replace,
        )
    post_reasons: list[str] = []
    if (
        post_audit["status"] != "noop"
        or post_audit["authority"] != "repoint"
        or post_audit["decision"]["reasons"]
    ):
        add_reason(post_reasons, "post_audit_not_authoritative")
    if post_audit["link"]["state"] != "current":
        add_reason(post_reasons, "link_postcondition_failed")
    expected_new_target_id = raw_string_id(options.new_target)
    if (
        raw_target_after_replace != options.new_target
        or post_private["link"]["raw_target"] != options.new_target
        or post_audit["link"]["raw_target_id"] != expected_new_target_id
    ):
        add_reason(post_reasons, "link_raw_target_postcondition_failed")
    if post_audit["git_fingerprint"] != private["git_fingerprint"]:
        add_reason(post_reasons, "git_state_changed_after_repair")
    if post_reasons:
        return 2, {
            "schema": REPAIR_SCHEMA,
            "operation": "repair-link",
            "status": "postcondition-failed",
            "mutation_performed": True,
            "authority": post_audit["authority"],
            "audit_fingerprint_before": private["fingerprint"],
            "fingerprint": post_audit["fingerprint"],
            "git_fingerprint_before": private["git_fingerprint"],
            "git_fingerprint_after": post_audit["git_fingerprint"],
            "immediate_raw_target_id": raw_string_id(
                raw_target_after_replace
            ),
            "link": post_audit["link"],
            "decision": {
                "repair_allowed": False,
                "reasons": post_reasons,
            },
        }
    return 0, {
        "schema": REPAIR_SCHEMA,
        "operation": "repair-link",
        "status": "repaired",
        "mutation_performed": True,
        "authority": post_audit["authority"],
        "audit_fingerprint_before": private["fingerprint"],
        "fingerprint": post_audit["fingerprint"],
        "git_fingerprint_before": private["git_fingerprint"],
        "git_fingerprint_after": post_audit["git_fingerprint"],
        "link": post_audit["link"],
        "decision": {
            "repair_allowed": False,
            "reasons": [],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        description=(
            "Read-only Git worktree recovery audit with an explicitly gated "
            "exact-symlink repair mode."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("audit", "repair-link"),
        default="audit",
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch-ref", required=True)
    parser.add_argument("--replacement", required=True)
    parser.add_argument("--link", required=True)
    parser.add_argument("--expected-commit", action="append", default=[])
    parser.add_argument("--expected-old-target")
    parser.add_argument("--new-target")
    parser.add_argument("--expected-fingerprint")
    parser.add_argument("--apply", action="store_true")
    return parser


def validate_options(options: argparse.Namespace) -> argparse.Namespace:
    options.repo = normalized_absolute(options.repo)
    options.replacement = normalized_absolute(options.replacement)
    options.link = normalized_absolute(options.link)
    if not valid_ref(options.branch_ref):
        raise InputError("invalid_branch_ref")
    if not options.expected_commit:
        raise InputError("expected_commit_required")
    if len(options.expected_commit) > MAX_EXPECTED_COMMITS:
        raise InputError("too_many_expected_commits")
    expected: list[str] = []
    for oid in options.expected_commit:
        if not valid_oid(oid):
            raise InputError("invalid_expected_commit")
        if oid not in expected:
            expected.append(oid)
    options.expected_commit = expected
    for value in (options.expected_old_target, options.new_target):
        if value is not None and (
            not value
            or "\x00" in value
            or len(os.fsencode(value)) > 8192
        ):
            raise InputError("invalid_link_target")
    if options.mode == "audit":
        if options.apply or options.expected_fingerprint is not None:
            raise InputError("audit_mode_is_read_only")
    else:
        if not options.apply:
            raise InputError("repair_requires_apply")
        if options.expected_old_target is None or options.new_target is None:
            raise InputError("repair_targets_required")
        if (
            options.expected_fingerprint is None
            or FINGERPRINT_RE.fullmatch(options.expected_fingerprint) is None
        ):
            raise InputError("repair_fingerprint_required")
    return options


def error_payload(code: str) -> dict[str, Any]:
    return {
        "schema": ERROR_SCHEMA,
        "operation": "error",
        "status": "error",
        "error_code": code,
    }


def execute(argv: Sequence[str]) -> tuple[int, dict[str, Any]]:
    try:
        options = validate_options(build_parser().parse_args(list(argv)))
        if options.mode == "repair-link":
            return repair_link(options)
        public, _ = collect_audit(options)
        return (0 if public["status"] in {"ready", "noop"} else 2), public
    except InputError:
        return 1, error_payload("invalid_input")
    except EvidenceError:
        return 1, error_payload("evidence_unavailable")
    except RepairIOError:
        return 1, error_payload("repair_io_error")
    except Exception:
        return 1, error_payload("unexpected_failure")


def serialize_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    if len(encoded.encode("ascii")) > MAX_JSON_BYTES:
        return json.dumps(
            error_payload("output_too_large"),
            sort_keys=True,
            separators=(",", ":"),
        )
    return encoded


def main(argv: Sequence[str] | None = None) -> int:
    exit_code, payload = execute(sys.argv[1:] if argv is None else argv)
    print(serialize_payload(payload))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
