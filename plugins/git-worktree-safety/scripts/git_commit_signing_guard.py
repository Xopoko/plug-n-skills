#!/usr/bin/env python3
"""Create and consume private state for one signed Git commit retry."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence


AUDIT_SCHEMA = "git_commit_signing_recovery.audit.v3"
AUTHORIZATION_SCHEMA = "git_commit_signing_recovery.authorization.v1"
CONSUMED_SCHEMA = "git_commit_signing_recovery.consumed.v1"
VERIFY_SCHEMA = "git_commit_signing_recovery.verify.v3"
ERROR_SCHEMA = "git_commit_signing_recovery.error.v1"
MAX_COMMAND_BYTES = 8 * 1024 * 1024
MAX_TOOL_BYTES = 32 * 1024 * 1024
MAX_UNTRACKED_TOTAL_BYTES = 32 * 1024 * 1024
MAX_UNTRACKED_ENTRIES = 4096
MAX_TRACKED_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TRACKED_ENTRY_BYTES = 32 * 1024 * 1024
MAX_TRACKED_ENTRIES = 65536
MAX_RECEIPT_BYTES = 128 * 1024
MAX_JSON_BYTES = 32 * 1024
COMMAND_TIMEOUT_SECONDS = 20
FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
OID_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
NONCE_RE = re.compile(r"^[0-9a-f]{64}$")
SSH_FINGERPRINT_RE = re.compile(
    rb"\bkey (SHA256:[A-Za-z0-9+/]+={0,2})\b"
)
HOOK_NAMES = (
    "pre-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "reference-transaction",
)
SYSTEM_SEARCH_DIRS = tuple(
    part
    for part in os.defpath.split(os.pathsep)
    if part and Path(part).is_absolute()
)
JOURNAL_DIRECTORY = "git-commit-signing-recovery"


class GuardError(RuntimeError):
    """Base class for public-safe guard failures."""


class InputError(GuardError):
    """Raised for malformed caller input."""


class EvidenceError(GuardError):
    """Raised when bounded Git evidence is unavailable."""


class SafetyRefusal(GuardError):
    """Raised when a single-use authorization cannot be consumed."""


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError("invalid_arguments")


def require_secure_runtime() -> None:
    if (
        os.name != "posix"
        or not hasattr(os, "geteuid")
        or not hasattr(os, "O_NOFOLLOW")
    ):
        raise EvidenceError("secure_runtime_unavailable")


def digest_bytes(domain: str, value: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(domain.encode("ascii"))
    hasher.update(b"\x00")
    hasher.update(value)
    return hasher.hexdigest()


def stable_digest(domain: str, value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return digest_bytes(domain, encoded)


def stable_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def system_executable(name: str) -> Path | None:
    suffixes = ("", ".exe") if os.name == "nt" else ("",)
    for directory in SYSTEM_SEARCH_DIRS:
        for suffix in suffixes:
            candidate = Path(directory) / f"{name}{suffix}"
            try:
                resolved = candidate.resolve(strict=True)
                info = resolved.stat()
            except (OSError, RuntimeError):
                continue
            if (
                resolved.is_absolute()
                and stat.S_ISREG(info.st_mode)
                and os.access(resolved, os.X_OK)
                and not info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                and (
                    not hasattr(os, "geteuid")
                    or info.st_uid in {0, os.geteuid()}
                )
            ):
                try:
                    parent_info = resolved.parent.stat()
                except OSError:
                    continue
                if (
                    parent_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                    or (
                        hasattr(os, "geteuid")
                        and parent_info.st_uid not in {0, os.geteuid()}
                    )
                ):
                    continue
                return resolved
    return None


def read_stable_regular(path: Path, maximum: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise EvidenceError("regular_file_unavailable") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise EvidenceError("regular_file_unavailable")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65536, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise EvidenceError("regular_file_too_large")
        after = os.fstat(descriptor)
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_mode != after.st_mode
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
        ):
            raise EvidenceError("regular_file_changed")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def executable_receipt(name: str) -> dict[str, Any]:
    executable = system_executable(name)
    if executable is None:
        return {
            "available": False,
            "path_id": None,
            "content_id": None,
        }
    try:
        content = read_stable_regular(executable, MAX_TOOL_BYTES)
    except EvidenceError:
        return {
            "available": False,
            "path_id": None,
            "content_id": None,
        }
    return {
        "available": True,
        "path_id": digest_bytes("system-executable-path", os.fsencode(executable)),
        "content_id": digest_bytes("system-executable-content", content),
    }


def safe_git_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("GIT_", "LD_", "DYLD_"))
    }
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_GRAFT_FILE": os.devnull,
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_PAGER": "",
            "LC_ALL": "C",
            "LANG": "C",
            "PATH": os.pathsep.join(SYSTEM_SEARCH_DIRS),
        }
    )
    return environment


def run_git(
    repo: Path,
    arguments: Sequence[str],
    *,
    accepted: Iterable[int] = (0,),
) -> subprocess.CompletedProcess[bytes]:
    git = system_executable("git")
    if git is None:
        raise EvidenceError("system_git_unavailable")
    try:
        result = subprocess.run(
            [
                os.fspath(git),
                "--no-replace-objects",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-c",
                "maintenance.auto=false",
                "-C",
                os.fspath(repo),
                *arguments,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=safe_git_environment(),
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise EvidenceError("git_probe_unavailable") from exc
    if (
        len(result.stdout) > MAX_COMMAND_BYTES
        or len(result.stderr) > MAX_COMMAND_BYTES
    ):
        raise EvidenceError("git_probe_output_too_large")
    if result.returncode not in set(accepted):
        raise EvidenceError("git_probe_failed")
    return result


def ascii_text(value: bytes) -> str:
    try:
        return value.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise EvidenceError("non_ascii_git_identity") from exc


def normalize_repo(raw_repo: str) -> Path:
    try:
        repo = Path(raw_repo).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InputError("invalid_repo") from exc
    if not repo.is_dir():
        raise InputError("invalid_repo")
    inside = ascii_text(
        run_git(repo, ["rev-parse", "--is-inside-work-tree"]).stdout
    )
    if inside != "true":
        raise InputError("repo_is_not_worktree")
    try:
        top_raw = run_git(repo, ["rev-parse", "--show-toplevel"]).stdout
        top = Path(os.fsdecode(top_raw.rstrip(b"\n"))).resolve(strict=True)
    except (EvidenceError, OSError, RuntimeError, UnicodeError) as exc:
        raise InputError("invalid_repo") from exc
    if not top.is_dir():
        raise InputError("invalid_repo")
    return top


def git_path(repo: Path, name: str) -> Path:
    raw = os.fsdecode(
        run_git(repo, ["rev-parse", "--git-path", name]).stdout.rstrip(b"\n")
    )
    path = Path(raw)
    if not path.is_absolute():
        path = repo / path
    return Path(os.path.abspath(path))


def private_path(raw_path: str, *, must_exist: bool) -> Path:
    raw = Path(raw_path).expanduser()
    if not raw.is_absolute() or raw.name in {"", ".", ".."}:
        raise InputError("invalid_private_path")
    try:
        parent = raw.parent.resolve(strict=True)
        parent_info = parent.stat()
    except (OSError, RuntimeError) as exc:
        raise InputError("invalid_private_path") from exc
    if not parent.is_dir():
        raise InputError("invalid_private_path")
    if hasattr(os, "geteuid") and parent_info.st_uid != os.geteuid():
        raise InputError("unsafe_private_directory")
    if parent_info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise InputError("unsafe_private_directory")
    path = parent / raw.name
    try:
        info = path.lstat()
    except FileNotFoundError:
        if must_exist:
            raise InputError("private_file_missing")
        return path
    except OSError as exc:
        raise InputError("invalid_private_path") from exc
    if not must_exist:
        raise InputError("private_file_exists")
    if not stat.S_ISREG(info.st_mode):
        raise InputError("invalid_private_file")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise InputError("unsafe_private_file")
    if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise InputError("unsafe_private_file")
    return path


def write_private_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    raw = stable_json_bytes(payload)
    if len(raw) > MAX_RECEIPT_BYTES:
        raise InputError("private_payload_too_large")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        raise SafetyRefusal("single_use_state_already_exists") from exc
    except OSError as exc:
        raise InputError("private_file_create_failed") from exc
    complete = False
    try:
        offset = 0
        while offset < len(raw):
            offset += os.write(descriptor, raw[offset:])
        os.fsync(descriptor)
        complete = True
    finally:
        os.close(descriptor)
        if not complete:
            try:
                path.unlink()
            except OSError:
                pass


def read_private_json(path: Path) -> dict[str, Any]:
    try:
        raw = read_stable_regular(path, MAX_RECEIPT_BYTES)
        payload = json.loads(raw)
    except (EvidenceError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError("invalid_private_file") from exc
    if not isinstance(payload, dict):
        raise InputError("invalid_private_file")
    return payload


def commit_message_receipt(repo: Path) -> dict[str, Any]:
    path = git_path(repo, "COMMIT_EDITMSG")
    try:
        content = read_stable_regular(path, MAX_COMMAND_BYTES)
    except EvidenceError:
        return {"available": False, "fingerprint": None}
    return {
        "available": True,
        "fingerprint": digest_bytes("commit-message", content),
    }


def operation_markers(repo: Path) -> list[str]:
    candidates = (
        ("merge", "MERGE_HEAD"),
        ("cherry-pick", "CHERRY_PICK_HEAD"),
        ("revert", "REVERT_HEAD"),
        ("rebase-apply", "rebase-apply"),
        ("rebase-merge", "rebase-merge"),
        ("sequencer", "sequencer"),
        ("bisect", "BISECT_LOG"),
    )
    return [
        label
        for label, marker in candidates
        if git_path(repo, marker).exists()
    ]


def config_value(repo: Path, key: str) -> bytes | None:
    result = run_git(repo, ["config", "--get", key], accepted=(0, 1))
    if result.returncode == 1:
        return None
    return result.stdout.rstrip(b"\n")


def configured_value(value: bytes | None, domain: str) -> dict[str, Any]:
    if value is None:
        return {"configured": False, "value_id": None}
    return {
        "configured": True,
        "value_id": digest_bytes(domain, value),
    }


def resolve_configured_path(repo: Path, value: bytes) -> Path:
    try:
        raw_path = os.fsdecode(value)
    except UnicodeError as exc:
        raise EvidenceError("configured_path_unavailable") from exc
    path = Path(os.path.expanduser(raw_path))
    if not path.is_absolute():
        top = os.fsdecode(
            run_git(repo, ["rev-parse", "--show-toplevel"])
            .stdout.rstrip(b"\n")
        )
        path = Path(top) / path
    return Path(os.path.abspath(path))


def configured_file(
    repo: Path,
    value: bytes | None,
    domain: str,
) -> dict[str, Any]:
    base = configured_value(value, f"{domain}-path")
    if value is None:
        return {
            **base,
            "content_available": False,
            "content_id": None,
        }
    try:
        path = resolve_configured_path(repo, value)
        content = read_stable_regular(path, MAX_COMMAND_BYTES)
    except EvidenceError:
        return {
            **base,
            "content_available": False,
            "content_id": None,
        }
    return {
        **base,
        "content_available": True,
        "content_id": digest_bytes(f"{domain}-content", content),
    }


def boolean_config(value: bytes | None) -> bool | None | str:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {b"true", b"yes", b"on", b"1"}:
        return True
    if lowered in {b"false", b"no", b"off", b"0"}:
        return False
    return "invalid"


def parse_ssh_public_identity(raw: bytes) -> str | None:
    try:
        text = raw.decode("ascii").strip()
    except UnicodeDecodeError:
        return None
    if text.startswith("key::"):
        text = text[5:].lstrip()
    fields = text.split()
    for index, field in enumerate(fields[:-1]):
        if not (
            field.startswith("ssh-")
            or field.startswith("ecdsa-")
            or field.startswith("sk-ssh-")
            or field.startswith("sk-ecdsa-")
        ):
            continue
        encoded = fields[index + 1]
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            blob = base64.b64decode(padded, validate=True)
        except (ValueError, base64.binascii.Error):
            return None
        if len(blob) < 8:
            return None
        key_type_size = int.from_bytes(blob[:4], "big")
        key_type = blob[4 : 4 + key_type_size]
        if key_type != field.encode("ascii"):
            return None
        digest = hashlib.sha256(blob).digest()
        rendered = base64.b64encode(digest).decode("ascii").rstrip("=")
        return f"SHA256:{rendered}"
    return None


def ssh_identity_from_config(
    repo: Path,
    raw_key: bytes | None,
) -> dict[str, Any]:
    base = configured_value(raw_key, "git-signing-key")
    if raw_key is None:
        return {
            **base,
            "identity_available": False,
            "identity_id": None,
            "public_material_id": None,
        }
    identity = parse_ssh_public_identity(raw_key)
    public_material: bytes | None = raw_key if identity is not None else None
    if identity is None:
        try:
            key_path = resolve_configured_path(repo, raw_key)
        except EvidenceError:
            key_path = Path()
        candidates: list[Path] = []
        if key_path.name and key_path.suffix == ".pub":
            candidates.append(key_path)
        elif key_path.name:
            candidates.append(key_path.with_name(f"{key_path.name}.pub"))
        for candidate in candidates:
            try:
                material = read_stable_regular(candidate, MAX_COMMAND_BYTES)
            except EvidenceError:
                continue
            candidate_identity = parse_ssh_public_identity(material)
            if candidate_identity is not None:
                identity = candidate_identity
                public_material = material
                break
    if identity is None or public_material is None:
        return {
            **base,
            "identity_available": False,
            "identity_id": None,
            "public_material_id": None,
        }
    return {
        **base,
        "identity_available": True,
        "identity_id": digest_bytes(
            "ssh-signing-identity",
            identity.encode("ascii"),
        ),
        "public_material_id": digest_bytes(
            "ssh-public-material",
            public_material,
        ),
    }


def verifier_name(signing_format: str) -> str | None:
    return "ssh-keygen" if signing_format == "ssh" else None


def signing_config(repo: Path) -> dict[str, Any]:
    raw_format = config_value(repo, "gpg.format")
    if raw_format is None:
        signing_format = "openpgp"
    else:
        lowered = raw_format.strip().lower()
        signing_format = (
            lowered.decode("ascii")
            if lowered in {b"openpgp", b"ssh", b"x509"}
            else "other"
        )
    raw_key = config_value(repo, "user.signingkey")
    identity = ssh_identity_from_config(repo, raw_key)
    if signing_format != "ssh":
        identity = {
            **configured_value(raw_key, "git-signing-key"),
            "identity_available": False,
            "identity_id": None,
            "public_material_id": None,
        }
    verifier = verifier_name(signing_format)
    return {
        "commit_gpgsign": boolean_config(
            config_value(repo, "commit.gpgsign")
        ),
        "format": signing_format,
        "signing_key": identity,
        "gpg_program": configured_value(
            config_value(repo, "gpg.program"),
            "git-gpg-program",
        ),
        "openpgp_program": configured_value(
            config_value(repo, "gpg.openpgp.program"),
            "git-openpgp-signing-program",
        ),
        "ssh_program": configured_value(
            config_value(repo, "gpg.ssh.program"),
            "git-ssh-signing-program",
        ),
        "x509_program": configured_value(
            config_value(repo, "gpg.x509.program"),
            "git-x509-signing-program",
        ),
        "minimum_trust": configured_value(
            config_value(repo, "gpg.minTrustLevel"),
            "git-minimum-signature-trust",
        ),
        "ssh_default_key_command": configured_value(
            config_value(repo, "gpg.ssh.defaultKeyCommand"),
            "git-ssh-default-key-command",
        ),
        "allowed_signers": configured_file(
            repo,
            config_value(repo, "gpg.ssh.allowedSignersFile"),
            "git-allowed-signers",
        ),
        "ssh_revocations": configured_file(
            repo,
            config_value(repo, "gpg.ssh.revocationFile"),
            "git-ssh-revocations",
        ),
        "verifier": (
            executable_receipt(verifier)
            if verifier is not None
            else {
                "available": False,
                "path_id": None,
                "content_id": None,
            }
        ),
    }


def hook_file_receipt(path: Path) -> dict[str, Any]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {
            "exists": False,
            "evidence_available": True,
            "executable": False,
            "content_id": None,
        }
    except OSError:
        return {
            "exists": True,
            "evidence_available": False,
            "executable": False,
            "content_id": None,
        }
    if not stat.S_ISREG(info.st_mode):
        return {
            "exists": True,
            "evidence_available": False,
            "executable": False,
            "content_id": None,
        }
    try:
        content = read_stable_regular(path, MAX_COMMAND_BYTES)
    except EvidenceError:
        return {
            "exists": True,
            "evidence_available": False,
            "executable": bool(info.st_mode & 0o111),
            "content_id": None,
        }
    return {
        "exists": True,
        "evidence_available": True,
        "executable": bool(info.st_mode & 0o111),
        "content_id": digest_bytes("git-hook-content", content),
    }


def absent_hook_receipt() -> dict[str, Any]:
    return {
        "exists": False,
        "evidence_available": True,
        "executable": False,
        "content_id": None,
    }


def hook_directory_receipt(path: Path) -> tuple[dict[str, Any], Path | None]:
    try:
        resolved = path.resolve(strict=False)
        info = resolved.lstat()
    except FileNotFoundError:
        return (
            {
                "evidence_available": True,
                "exists": False,
                "directory": False,
                "mode": None,
                "path_id": digest_bytes(
                    "git-hooks-directory",
                    os.fsencode(path.resolve(strict=False)),
                ),
            },
            None,
        )
    except (OSError, RuntimeError):
        return (
            {
                "evidence_available": False,
                "exists": False,
                "directory": False,
                "mode": None,
                "path_id": None,
            },
            None,
        )
    is_directory = stat.S_ISDIR(info.st_mode)
    return (
        {
            "evidence_available": True,
            "exists": True,
            "directory": is_directory,
            "mode": stat.S_IMODE(info.st_mode),
            "path_id": digest_bytes(
                "git-hooks-directory",
                os.fsencode(resolved),
            ),
        },
        resolved if is_directory else None,
    )


def hook_policy(repo: Path) -> dict[str, Any]:
    raw_path = config_value(repo, "core.hooksPath")
    try:
        effective_paths = {
            name: git_path(repo, f"hooks/{name}")
            for name in HOOK_NAMES
        }
        parents = {path.parent for path in effective_paths.values()}
        if len(parents) != 1:
            raise EvidenceError("configured_hook_path_unavailable")
        base_path = parents.pop()
        directory, resolved = hook_directory_receipt(base_path)
    except (EvidenceError, OSError, RuntimeError, UnicodeError):
        directory = {
            "evidence_available": False,
            "exists": False,
            "directory": False,
            "mode": None,
            "path_id": None,
        }
        resolved = None
        effective_paths = {}
    hooks = (
        {
            name: hook_file_receipt(effective_paths[name])
            for name in HOOK_NAMES
        }
        if resolved is not None
        else {name: absent_hook_receipt() for name in HOOK_NAMES}
    )
    return {
        "configured_path": configured_value(raw_path, "git-hooks-path"),
        "directory": directory,
        "evidence_available": (
            directory["evidence_available"]
            and all(
                item["evidence_available"] for item in hooks.values()
            )
        ),
        "hooks": hooks,
    }


def repository_common_dir(repo: Path) -> Path:
    raw = os.fsdecode(
        run_git(repo, ["rev-parse", "--git-common-dir"]).stdout.rstrip(b"\n")
    )
    common = Path(raw)
    if not common.is_absolute():
        common = repo / common
    try:
        resolved = common.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise EvidenceError("git_common_dir_unavailable") from exc
    if not resolved.is_dir():
        raise EvidenceError("git_common_dir_unavailable")
    return resolved


def repository_git_dir(repo: Path) -> Path:
    raw = os.fsdecode(
        run_git(repo, ["rev-parse", "--git-dir"]).stdout.rstrip(b"\n")
    )
    git_dir = Path(raw)
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    try:
        resolved = git_dir.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise EvidenceError("git_dir_unavailable") from exc
    if not resolved.is_dir():
        raise EvidenceError("git_dir_unavailable")
    return resolved


def repository_identity(repo: Path) -> str:
    return stable_digest(
        "git-worktree-identity",
        {
            "common_dir_id": digest_bytes(
                "git-common-dir",
                os.fsencode(repository_common_dir(repo)),
            ),
            "git_dir_id": digest_bytes(
                "git-dir",
                os.fsencode(repository_git_dir(repo)),
            ),
            "worktree_id": digest_bytes(
                "git-worktree-root",
                os.fsencode(repo),
            ),
        },
    )


def object_substitution_policy(repo: Path) -> dict[str, Any]:
    replace_refs = run_git(
        repo,
        [
            "for-each-ref",
            "--format=%(refname)%00%(objectname)%00",
            "refs/replace/",
        ],
    ).stdout
    info_path = repository_common_dir(repo) / "info"
    try:
        info = info_path.lstat()
    except FileNotFoundError:
        grafts = {
            "exists": False,
            "content_available": True,
            "content_id": None,
        }
    except OSError:
        grafts = {
            "exists": False,
            "content_available": False,
            "content_id": None,
        }
    else:
        if not stat.S_ISDIR(info.st_mode):
            grafts = {
                "exists": False,
                "content_available": False,
                "content_id": None,
            }
        else:
            grafts_path = info_path / "grafts"
            try:
                grafts_info = grafts_path.lstat()
            except FileNotFoundError:
                grafts = {
                    "exists": False,
                    "content_available": True,
                    "content_id": None,
                }
            except OSError:
                grafts = {
                    "exists": True,
                    "content_available": False,
                    "content_id": None,
                }
            else:
                if not stat.S_ISREG(grafts_info.st_mode):
                    grafts = {
                        "exists": True,
                        "content_available": False,
                        "content_id": None,
                    }
                else:
                    try:
                        grafts_content = read_stable_regular(
                            grafts_path,
                            MAX_COMMAND_BYTES,
                        )
                    except EvidenceError:
                        grafts = {
                            "exists": True,
                            "content_available": False,
                            "content_id": None,
                        }
                    else:
                        grafts = {
                            "exists": True,
                            "content_available": True,
                            "content_id": digest_bytes(
                                "git-grafts-content",
                                grafts_content,
                            ),
                        }
    return {
        "evidence_available": grafts["content_available"],
        "present": bool(replace_refs) or grafts["exists"],
        "replace_refs_id": digest_bytes(
            "git-replacement-refs",
            replace_refs,
        ),
        "grafts": grafts,
    }


def safe_worktree_path(top: Path, raw_path: bytes) -> Path:
    decoded = os.fsdecode(raw_path)
    relative = Path(decoded)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise EvidenceError("unsafe_worktree_path")
    cursor = top
    for part in relative.parts[:-1]:
        cursor = cursor / part
        try:
            parent_info = cursor.lstat()
        except FileNotFoundError:
            return top.joinpath(*relative.parts)
        if not stat.S_ISDIR(parent_info.st_mode):
            raise EvidenceError("unsafe_worktree_path")
    return cursor / relative.parts[-1]


def tracked_state(repo: Path, inventory: bytes) -> dict[str, Any]:
    inventory_fingerprint = digest_bytes("tracked-index", inventory)
    raw_records = inventory.split(b"\0")
    if raw_records and raw_records[-1] == b"":
        raw_records.pop()
    if (
        len(raw_records) > MAX_TRACKED_ENTRIES
        or any(not record for record in raw_records)
    ):
        return {
            "evidence_available": False,
            "inventory_fingerprint": inventory_fingerprint,
            "content_fingerprint": None,
        }
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for record in raw_records:
        try:
            metadata, separator, raw_path = record.partition(b"\t")
            fields = metadata.split()
            if (
                not separator
                or not raw_path
                or len(fields) != 3
                or re.fullmatch(rb"[0-7]{6}", fields[0]) is None
                or re.fullmatch(rb"[0-9a-f]{40}(?:[0-9a-f]{24})?", fields[1])
                is None
                or fields[2] != b"0"
                or fields[0] == b"160000"
            ):
                raise EvidenceError("unsupported_tracked_index")
            path = safe_worktree_path(repo, raw_path)
            try:
                before = path.lstat()
            except FileNotFoundError:
                entries.append(
                    {
                        "index_id": digest_bytes(
                            "tracked-index-entry",
                            metadata,
                        ),
                        "path_id": digest_bytes("tracked-path", raw_path),
                        "type": "missing",
                        "mode": None,
                        "content_id": None,
                    }
                )
                continue
            if stat.S_ISREG(before.st_mode):
                content = read_stable_regular(
                    path,
                    MAX_TRACKED_ENTRY_BYTES,
                )
                after = path.lstat()
                if (
                    before.st_dev != after.st_dev
                    or before.st_ino != after.st_ino
                    or before.st_mode != after.st_mode
                    or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns
                ):
                    raise EvidenceError("tracked_regular_changed")
                entry_type = "regular"
            elif stat.S_ISLNK(before.st_mode):
                target = os.readlink(path)
                after = path.lstat()
                if (
                    before.st_dev != after.st_dev
                    or before.st_ino != after.st_ino
                    or before.st_mode != after.st_mode
                    or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns
                ):
                    raise EvidenceError("tracked_symlink_changed")
                content = os.fsencode(target)
                entry_type = "symlink"
            else:
                raise EvidenceError("unsupported_tracked_file")
            total_bytes += len(content)
            if total_bytes > MAX_TRACKED_TOTAL_BYTES:
                raise EvidenceError("tracked_content_too_large")
            entries.append(
                {
                    "index_id": digest_bytes(
                        "tracked-index-entry",
                        metadata,
                    ),
                    "path_id": digest_bytes("tracked-path", raw_path),
                    "type": entry_type,
                    "mode": stat.S_IMODE(before.st_mode),
                    "content_id": digest_bytes(
                        f"tracked-{entry_type}-content",
                        content,
                    ),
                }
            )
        except (EvidenceError, OSError, RuntimeError, UnicodeError):
            return {
                "evidence_available": False,
                "inventory_fingerprint": inventory_fingerprint,
                "content_fingerprint": None,
            }
    return {
        "evidence_available": True,
        "inventory_fingerprint": inventory_fingerprint,
        "content_fingerprint": stable_digest(
            "tracked-worktree-state",
            entries,
        ),
    }


def untracked_state(repo: Path, inventory: bytes) -> dict[str, Any]:
    inventory_fingerprint = digest_bytes("untracked-inventory", inventory)
    raw_paths = inventory.split(b"\0")
    if raw_paths and raw_paths[-1] == b"":
        raw_paths.pop()
    if (
        len(raw_paths) > MAX_UNTRACKED_ENTRIES
        or any(not raw_path for raw_path in raw_paths)
    ):
        return {
            "evidence_available": False,
            "inventory_fingerprint": inventory_fingerprint,
            "content_fingerprint": None,
        }
    try:
        top_raw = run_git(
            repo,
            ["rev-parse", "--show-toplevel"],
        ).stdout.rstrip(b"\n")
        top = Path(os.fsdecode(top_raw)).resolve(strict=True)
    except (EvidenceError, OSError, RuntimeError, UnicodeError):
        return {
            "evidence_available": False,
            "inventory_fingerprint": inventory_fingerprint,
            "content_fingerprint": None,
        }
    entries: list[dict[str, Any]] = []
    total_bytes = 0
    for raw_path in raw_paths:
        try:
            path = safe_worktree_path(top, raw_path)
            before = path.lstat()
            if stat.S_ISREG(before.st_mode):
                content = read_stable_regular(path, MAX_COMMAND_BYTES)
                entry_type = "regular"
            elif stat.S_ISLNK(before.st_mode):
                target = os.readlink(path)
                after = path.lstat()
                if (
                    before.st_dev != after.st_dev
                    or before.st_ino != after.st_ino
                    or before.st_mode != after.st_mode
                    or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns
                ):
                    raise EvidenceError("untracked_symlink_changed")
                content = os.fsencode(target)
                entry_type = "symlink"
            else:
                raise EvidenceError("unsupported_untracked_file")
            total_bytes += len(content)
            if total_bytes > MAX_UNTRACKED_TOTAL_BYTES:
                raise EvidenceError("untracked_content_too_large")
            entries.append(
                {
                    "path_id": digest_bytes("untracked-path", raw_path),
                    "type": entry_type,
                    "mode": stat.S_IMODE(before.st_mode),
                    "content_id": digest_bytes(
                        f"untracked-{entry_type}-content",
                        content,
                    ),
                }
            )
        except (EvidenceError, OSError, RuntimeError, UnicodeError):
            return {
                "evidence_available": False,
                "inventory_fingerprint": inventory_fingerprint,
                "content_fingerprint": None,
            }
    return {
        "evidence_available": True,
        "inventory_fingerprint": inventory_fingerprint,
        "content_fingerprint": stable_digest(
            "untracked-content-state",
            entries,
        ),
    }


def diff_bytes(
    repo: Path,
    *,
    cached: bool = False,
    old: str | None = None,
    new: str | None = None,
) -> bytes:
    if (cached and new is not None) or (
        not cached and (old is None or new is None)
    ):
        raise EvidenceError("unsafe_worktree_diff_refused")
    arguments = [
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        "--no-textconv",
    ]
    if cached:
        arguments.append("--cached")
    if old is not None:
        arguments.append(old)
    if new is not None:
        arguments.append(new)
    arguments.append("--")
    return run_git(repo, arguments).stdout


def current_head(repo: Path) -> str:
    head = ascii_text(
        run_git(repo, ["rev-parse", "--verify", "HEAD^{commit}"]).stdout
    )
    if OID_RE.fullmatch(head) is None:
        raise EvidenceError("noncanonical_head")
    return head


def head_ref_identity(repo: Path) -> dict[str, Any]:
    immediate = run_git(
        repo,
        ["symbolic-ref", "--quiet", "--no-recurse", "HEAD"],
        accepted=(0, 1),
    )
    resolved = run_git(
        repo,
        ["symbolic-ref", "--quiet", "HEAD"],
        accepted=(0, 1),
    )
    if immediate.returncode == 1 and resolved.returncode == 1:
        return {
            "symbolic": False,
            "immediate_ref_id": None,
            "resolved_ref_id": None,
        }
    if immediate.returncode != 0 or resolved.returncode != 0:
        raise EvidenceError("head_ref_unavailable")
    immediate_ref = immediate.stdout.rstrip(b"\n")
    resolved_ref = resolved.stdout.rstrip(b"\n")
    if any(
        not value or b"\0" in value or b"\n" in value
        for value in (immediate_ref, resolved_ref)
    ):
        raise EvidenceError("head_ref_unavailable")
    return {
        "symbolic": True,
        "immediate_ref_id": digest_bytes(
            "git-head-immediate-ref",
            immediate_ref,
        ),
        "resolved_ref_id": digest_bytes(
            "git-head-resolved-ref",
            resolved_ref,
        ),
    }


def collect_state(repo: Path) -> dict[str, Any]:
    head = current_head(repo)
    staged = diff_bytes(repo, cached=True, old="HEAD")
    tracked = run_git(
        repo,
        [
            "ls-files",
            "--stage",
            "--full-name",
            "-z",
        ],
    ).stdout
    tracked_flags = run_git(
        repo,
        [
            "ls-files",
            "-v",
            "--full-name",
            "-z",
        ],
    ).stdout
    tracked_receipt = tracked_state(repo, tracked)
    untracked = run_git(
        repo,
        [
            "ls-files",
            "--full-name",
            "--others",
            "--exclude-standard",
            "-z",
        ],
    ).stdout
    untracked_receipt = untracked_state(repo, untracked)
    return {
        "repo_id": repository_identity(repo),
        "head": head,
        "head_ref": head_ref_identity(repo),
        "staged_diff_fingerprint": digest_bytes("staged-diff", staged),
        "staged_changes": bool(staged),
        "tracked_inventory_fingerprint": tracked_receipt[
            "inventory_fingerprint"
        ],
        "tracked_index_flags_fingerprint": digest_bytes(
            "tracked-index-flags",
            tracked_flags,
        ),
        "tracked_content_evidence_available": tracked_receipt[
            "evidence_available"
        ],
        "tracked_content_fingerprint": tracked_receipt[
            "content_fingerprint"
        ],
        "untracked_inventory_fingerprint": untracked_receipt[
            "inventory_fingerprint"
        ],
        "untracked_content_evidence_available": untracked_receipt[
            "evidence_available"
        ],
        "untracked_content_fingerprint": untracked_receipt[
            "content_fingerprint"
        ],
        "commit_message": commit_message_receipt(repo),
        "operation_markers": operation_markers(repo),
        "object_substitution": object_substitution_policy(repo),
        "hooks": hook_policy(repo),
        "signing": signing_config(repo),
        "git_tool": executable_receipt("git"),
    }


def audit_fingerprint(policy: str, state: dict[str, Any]) -> str:
    return stable_digest(
        "git-commit-signing-audit",
        {"policy": policy, "state": state},
    )


def baseline_identifier(state: dict[str, Any]) -> str:
    return stable_digest("git-commit-signing-baseline", state)


def journal_directory(repo: Path, *, create: bool) -> Path:
    common = repository_common_dir(repo)
    path = common / JOURNAL_DIRECTORY
    try:
        info = path.lstat()
    except FileNotFoundError:
        if not create:
            raise InputError("recovery_journal_missing")
        try:
            os.mkdir(path, 0o700)
            info = path.lstat()
        except OSError as exc:
            raise InputError("recovery_journal_create_failed") from exc
    except OSError as exc:
        raise InputError("invalid_recovery_journal") from exc
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        or (hasattr(os, "geteuid") and info.st_uid != os.geteuid())
    ):
        raise InputError("unsafe_recovery_journal")
    return path


def journal_record_path(
    repo: Path,
    baseline_id: str,
    record_type: str,
    *,
    create_directory: bool,
) -> Path:
    if (
        FINGERPRINT_RE.fullmatch(baseline_id) is None
        or record_type not in {"baseline", "consumed"}
    ):
        raise InputError("invalid_recovery_journal_key")
    directory = journal_directory(repo, create=create_directory)
    return directory / f"{baseline_id}.{record_type}.json"


def authorization_blockers(state: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if state["operation_markers"]:
        reasons.append("git_operation_in_progress")
    if not state["staged_changes"]:
        reasons.append("no_staged_changes")
    if not state["commit_message"]["available"]:
        reasons.append("commit_message_unavailable")
    if not state["tracked_content_evidence_available"]:
        reasons.append("tracked_content_evidence_unavailable")
    if not state["untracked_content_evidence_available"]:
        reasons.append("untracked_content_evidence_unavailable")
    substitution = state["object_substitution"]
    if not substitution["evidence_available"]:
        reasons.append("object_substitution_evidence_unavailable")
    elif substitution["present"]:
        reasons.append("object_substitution_present")
    if not state["hooks"]["evidence_available"]:
        reasons.append("hook_evidence_unavailable")
    signing = state["signing"]
    if signing["format"] != "ssh":
        reasons.append("unsupported_signing_format")
    if not signing["signing_key"]["identity_available"]:
        reasons.append("signing_identity_evidence_unavailable")
    if not signing["verifier"]["available"]:
        reasons.append("system_verifier_unavailable")
    if signing["format"] == "ssh":
        allowed_signers = signing["allowed_signers"]
        revocations = signing["ssh_revocations"]
        if (
            not allowed_signers["configured"]
            or not allowed_signers["content_available"]
            or (
                revocations["configured"]
                and not revocations["content_available"]
            )
        ):
            reasons.append("ssh_trust_evidence_unavailable")
    if not state["git_tool"]["available"]:
        reasons.append("system_git_unavailable")
    return reasons


def receipt_identifier(receipt: dict[str, Any]) -> str:
    return digest_bytes("private-audit-receipt", stable_json_bytes(receipt))


def audit_receipt(options: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    require_secure_runtime()
    repo = normalize_repo(options.repo)
    receipt_path = private_path(options.receipt, must_exist=False)
    authorization_path = private_path(
        options.authorization,
        must_exist=False,
    )
    state = collect_state(repo)
    fingerprint = audit_fingerprint(options.policy, state)
    baseline_id = baseline_identifier(state)
    nonce = secrets.token_hex(32)
    receipt = {
        "schema": AUDIT_SCHEMA,
        "operation": "audit",
        "policy": options.policy,
        "fingerprint": fingerprint,
        "baseline_id": baseline_id,
        "state": state,
        "authorization_nonce": nonce,
    }
    authorization = {
        "schema": AUTHORIZATION_SCHEMA,
        "status": "fresh",
        "receipt_id": receipt_identifier(receipt),
        "authorization_id": digest_bytes(
            "authorization-nonce",
            nonce.encode("ascii"),
        ),
    }
    write_private_json_exclusive(receipt_path, receipt)
    try:
        write_private_json_exclusive(authorization_path, authorization)
        write_private_json_exclusive(
            journal_record_path(
                repo,
                baseline_id,
                "baseline",
                create_directory=True,
            ),
            {
                "schema": AUTHORIZATION_SCHEMA,
                "status": "baseline",
                "baseline_id": baseline_id,
                "receipt_id": receipt_identifier(receipt),
                "authorization_id": authorization["authorization_id"],
            },
        )
    except GuardError:
        for path in (receipt_path, authorization_path):
            try:
                path.unlink()
            except OSError:
                pass
        raise
    reasons = authorization_blockers(state)
    reasons.append("single_use_authorization_required")
    public_receipt = {
        key: value
        for key, value in receipt.items()
        if key != "authorization_nonce"
    }
    public_receipt.update(
        {
            "status": "snapshot",
            "decision": {
                "signed_retry_allowed": False,
                "unsigned_fallback_allowed": False,
                "reasons": reasons,
            },
            "proof_boundary": (
                "Private single-use state prevents accidental repeated "
                "authorization; it is not hostile-local-principal or "
                "cryptographic timestamp attestation."
            ),
        }
    )
    return 0, public_receipt


def load_audit_receipt(path: Path) -> dict[str, Any]:
    payload = read_private_json(path)
    policy = payload.get("policy")
    state = payload.get("state")
    fingerprint = payload.get("fingerprint")
    baseline_id = payload.get("baseline_id")
    nonce = payload.get("authorization_nonce")
    if (
        payload.get("schema") != AUDIT_SCHEMA
        or payload.get("operation") != "audit"
        or policy not in {"required", "optional", "unknown"}
        or not isinstance(state, dict)
        or not isinstance(fingerprint, str)
        or FINGERPRINT_RE.fullmatch(fingerprint) is None
        or not isinstance(baseline_id, str)
        or FINGERPRINT_RE.fullmatch(baseline_id) is None
        or not isinstance(nonce, str)
        or NONCE_RE.fullmatch(nonce) is None
        or audit_fingerprint(policy, state) != fingerprint
        or baseline_identifier(state) != baseline_id
    ):
        raise InputError("invalid_receipt")
    expected_fields = {
        "repo_id",
        "head",
        "head_ref",
        "staged_diff_fingerprint",
        "staged_changes",
        "tracked_inventory_fingerprint",
        "tracked_index_flags_fingerprint",
        "tracked_content_evidence_available",
        "tracked_content_fingerprint",
        "untracked_inventory_fingerprint",
        "untracked_content_evidence_available",
        "untracked_content_fingerprint",
        "commit_message",
        "operation_markers",
        "object_substitution",
        "hooks",
        "signing",
        "git_tool",
    }
    if not expected_fields.issubset(state):
        raise InputError("invalid_receipt")
    if (
        not isinstance(state["head"], str)
        or OID_RE.fullmatch(state["head"]) is None
        or not state["staged_changes"]
    ):
        raise InputError("invalid_receipt")
    return payload


def validate_authorization_binding(
    receipt: dict[str, Any],
    authorization: dict[str, Any],
) -> None:
    nonce = receipt["authorization_nonce"]
    if (
        authorization.get("schema") != AUTHORIZATION_SCHEMA
        or authorization.get("status") != "fresh"
        or authorization.get("receipt_id") != receipt_identifier(receipt)
        or authorization.get("authorization_id")
        != digest_bytes("authorization-nonce", nonce.encode("ascii"))
    ):
        raise InputError("invalid_authorization")


def load_recovery_files(
    receipt_text: str,
    authorization_text: str,
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    receipt_path = private_path(receipt_text, must_exist=True)
    authorization_path = private_path(authorization_text, must_exist=True)
    receipt = load_audit_receipt(receipt_path)
    authorization = read_private_json(authorization_path)
    validate_authorization_binding(receipt, authorization)
    return receipt_path, authorization_path, receipt, authorization


def consumed_record(
    receipt: dict[str, Any],
    authorization: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": CONSUMED_SCHEMA,
        "status": "consumed",
        "baseline_id": receipt["baseline_id"],
        "receipt_id": receipt_identifier(receipt),
        "authorization_id": authorization["authorization_id"],
    }


def authorize_retry(options: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    require_secure_runtime()
    _, authorization_path, receipt, authorization = load_recovery_files(
        options.receipt,
        options.authorization,
    )
    repo = normalize_repo(options.repo)
    baseline_path = private_path(
        os.fspath(
            journal_record_path(
                repo,
                receipt["baseline_id"],
                "baseline",
                create_directory=False,
            )
        ),
        must_exist=True,
    )
    baseline_record = read_private_json(baseline_path)
    expected_baseline_record = {
        "schema": AUTHORIZATION_SCHEMA,
        "status": "baseline",
        "baseline_id": receipt["baseline_id"],
        "receipt_id": receipt_identifier(receipt),
        "authorization_id": authorization["authorization_id"],
    }
    if baseline_record != expected_baseline_record:
        raise InputError("invalid_recovery_journal")
    state = collect_state(repo)
    reasons = authorization_blockers(state)
    if (
        audit_fingerprint(receipt["policy"], state)
        != receipt["fingerprint"]
    ):
        reasons.append("recovery_state_drift")
    if options.signer_probe != "verified":
        reasons.append("signer_change_not_verified")
    if options.commit_shape != "verified-plain-index":
        reasons.append("commit_invocation_not_verified")
    consumed = journal_record_path(
        repo,
        receipt["baseline_id"],
        "consumed",
        create_directory=False,
    )
    if consumed.exists():
        reasons.append("retry_budget_exhausted")
    if reasons:
        return 2, {
            "schema": AUTHORIZATION_SCHEMA,
            "operation": "authorize",
            "status": "blocked",
            "policy": receipt["policy"],
            "receipt_fingerprint": receipt["fingerprint"],
            "decision": {
                "signed_retry_allowed": False,
                "unsigned_fallback_allowed": False,
                "reasons": reasons,
            },
            "proof_boundary": (
                "Signer-probe and plain-index invocation evidence are caller "
                "supplied; authorization state controls one helper-issued "
                "retry token, not the command that consumes it."
            ),
        }
    try:
        write_private_json_exclusive(
            consumed,
            consumed_record(receipt, authorization),
        )
    except SafetyRefusal:
        return 2, {
            "schema": AUTHORIZATION_SCHEMA,
            "operation": "authorize",
            "status": "blocked",
            "policy": receipt["policy"],
            "receipt_fingerprint": receipt["fingerprint"],
            "decision": {
                "signed_retry_allowed": False,
                "unsigned_fallback_allowed": False,
                "reasons": ["retry_budget_exhausted"],
            },
            "proof_boundary": (
                "Signer-probe and plain-index invocation evidence are caller "
                "supplied; authorization state controls one helper-issued "
                "retry token, not the command that consumes it."
            ),
        }
    final_state = collect_state(repo)
    if (
        audit_fingerprint(receipt["policy"], final_state)
        != receipt["fingerprint"]
        or authorization_blockers(final_state)
    ):
        return 2, {
            "schema": AUTHORIZATION_SCHEMA,
            "operation": "authorize",
            "status": "blocked",
            "policy": receipt["policy"],
            "receipt_fingerprint": receipt["fingerprint"],
            "decision": {
                "signed_retry_allowed": False,
                "unsigned_fallback_allowed": False,
                "reasons": ["state_drift_after_token_consumption"],
            },
            "proof_boundary": (
                "The token remains consumed after late state drift; no "
                "replacement authorization is issued."
            ),
        }
    return 0, {
        "schema": AUTHORIZATION_SCHEMA,
        "operation": "authorize",
        "status": "ready",
        "policy": receipt["policy"],
        "receipt_fingerprint": receipt["fingerprint"],
        "decision": {
            "signed_retry_allowed": True,
            "unsigned_fallback_allowed": False,
            "reasons": [],
        },
        "proof_boundary": (
            "Signer-probe and plain-index invocation evidence are caller "
            "supplied; authorization state controls one helper-issued retry "
            "token, not the command that consumes it."
        ),
    }


def load_consumed(
    repo: Path,
    receipt: dict[str, Any],
    authorization: dict[str, Any],
) -> dict[str, Any]:
    path = private_path(
        os.fspath(
            journal_record_path(
                repo,
                receipt["baseline_id"],
                "consumed",
                create_directory=False,
            )
        ),
        must_exist=True,
    )
    payload = read_private_json(path)
    if payload != consumed_record(receipt, authorization):
        raise InputError("invalid_consumed_authorization")
    return payload


def signature_evidence(
    repo: Path,
    commit: str,
    signing: dict[str, Any],
) -> tuple[bool, str | None]:
    signing_format = signing["format"]
    executable_name = verifier_name(signing_format)
    if executable_name is None:
        return False, None
    executable = system_executable(executable_name)
    if executable is None:
        return False, None
    if signing_format != "ssh":
        return False, None
    config_keys = ("gpg.ssh.program",)
    overrides: list[str] = []
    for key in config_keys:
        overrides.extend(["-c", f"{key}={executable}"])
    result = run_git(
        repo,
        [*overrides, "verify-commit", "--raw", commit],
        accepted=(0, 1, 2, 128),
    )
    if result.returncode != 0:
        return False, None
    output = result.stdout + b"\n" + result.stderr
    identities = set(SSH_FINGERPRINT_RE.findall(output))
    if len(identities) != 1:
        return True, None
    identity = identities.pop()
    return True, digest_bytes("ssh-signing-identity", identity)


def parent_list(repo: Path, commit: str) -> list[str]:
    raw = ascii_text(
        run_git(repo, ["rev-list", "--parents", "-n", "1", commit]).stdout
    )
    values = raw.split()
    if not values or values[0] != commit:
        raise EvidenceError("parent_evidence_unavailable")
    return values[1:]


def committed_message_fingerprint(repo: Path, commit: str) -> str:
    raw = run_git(repo, ["cat-file", "commit", commit]).stdout
    separator = raw.find(b"\n\n")
    if separator < 0:
        raise EvidenceError("commit_message_unavailable")
    return digest_bytes("commit-message", raw[separator + 2 :])


def verify_receipt(options: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    require_secure_runtime()
    _, _, receipt, authorization = load_recovery_files(
        options.receipt,
        options.authorization,
    )
    repo = normalize_repo(options.repo)
    load_consumed(repo, receipt, authorization)
    before = receipt["state"]
    after = collect_state(repo)
    old_head = before["head"]
    new_head = after["head"]
    reasons: list[str] = []

    if before["repo_id"] != after["repo_id"]:
        reasons.append("repository_identity_changed")
    if before["head_ref"] != after["head_ref"]:
        reasons.append("head_ref_changed")
    if new_head == old_head:
        reasons.append("head_not_advanced")

    parents = parent_list(repo, new_head)
    parent_matches = parents == [old_head]
    if not parent_matches:
        reasons.append("unexpected_parent_transition")

    committed_diff = diff_bytes(repo, old=old_head, new=new_head)
    diff_matches = (
        digest_bytes("staged-diff", committed_diff)
        == before["staged_diff_fingerprint"]
    )
    if not diff_matches:
        reasons.append("committed_diff_changed")
    message_matches = (
        committed_message_fingerprint(repo, new_head)
        == before["commit_message"]["fingerprint"]
    )
    if not message_matches:
        reasons.append("commit_message_changed")
    if after["staged_changes"]:
        reasons.append("residual_staged_changes")
    if (
        after["tracked_inventory_fingerprint"]
        != before["tracked_inventory_fingerprint"]
    ):
        reasons.append("tracked_inventory_changed")
    if (
        after["tracked_index_flags_fingerprint"]
        != before["tracked_index_flags_fingerprint"]
    ):
        reasons.append("tracked_index_flags_changed")
    if (
        not after["tracked_content_evidence_available"]
        or after["tracked_content_fingerprint"]
        != before["tracked_content_fingerprint"]
    ):
        reasons.append("tracked_content_changed")
    if (
        after["untracked_inventory_fingerprint"]
        != before["untracked_inventory_fingerprint"]
    ):
        reasons.append("untracked_inventory_changed")
    if (
        not after["untracked_content_evidence_available"]
        or after["untracked_content_fingerprint"]
        != before["untracked_content_fingerprint"]
    ):
        reasons.append("untracked_content_changed")
    if after["hooks"] != before["hooks"]:
        reasons.append("hook_policy_changed")
    if after["object_substitution"] != before["object_substitution"]:
        reasons.append("object_substitution_changed")
    if not after["object_substitution"]["evidence_available"]:
        reasons.append("object_substitution_evidence_unavailable")
    elif after["object_substitution"]["present"]:
        reasons.append("object_substitution_present")
    if after["signing"] != before["signing"]:
        reasons.append("signing_configuration_changed")
    if after["git_tool"] != before["git_tool"]:
        reasons.append("git_tool_changed")
    if after["operation_markers"]:
        reasons.append("git_operation_in_progress")

    signature_valid = False
    observed_identity: str | None = None
    if (
        after["signing"] == before["signing"]
        and after["git_tool"] == before["git_tool"]
    ):
        signature_valid, observed_identity = signature_evidence(
            repo,
            new_head,
            before["signing"],
        )
    if not signature_valid:
        reasons.append("signature_verification_failed")
    expected_identity = before["signing"]["signing_key"]["identity_id"]
    identity_matches = (
        signature_valid
        and observed_identity is not None
        and observed_identity == expected_identity
    )
    if signature_valid and observed_identity is None:
        reasons.append("signing_identity_evidence_unavailable")
    elif signature_valid and not identity_matches:
        reasons.append("signing_identity_changed")

    after_verifier = collect_state(repo)
    verifier_preserved_state = after_verifier == after
    if not verifier_preserved_state:
        reasons.append("verifier_changed_repository_state")

    verified = not reasons
    return (0 if verified else 2), {
        "schema": VERIFY_SCHEMA,
        "operation": "verify",
        "status": "verified" if verified else "failed",
        "policy": receipt["policy"],
        "old_head": old_head,
        "new_head": new_head,
        "receipt_fingerprint": receipt["fingerprint"],
        "verification": {
            "one_parent_advance": parent_matches,
            "head_ref_matches": after["head_ref"] == before["head_ref"],
            "committed_diff_matches": diff_matches,
            "commit_message_matches": message_matches,
            "signature_valid": signature_valid,
            "signing_identity_matches": identity_matches,
            "verifier_preserved_repository_state": verifier_preserved_state,
            "tracked_inventory_matches": (
                after["tracked_inventory_fingerprint"]
                == before["tracked_inventory_fingerprint"]
            ),
            "tracked_index_flags_match": (
                after["tracked_index_flags_fingerprint"]
                == before["tracked_index_flags_fingerprint"]
            ),
            "tracked_content_matches": (
                after["tracked_content_evidence_available"]
                and after["tracked_content_fingerprint"]
                == before["tracked_content_fingerprint"]
            ),
            "untracked_inventory_matches": (
                after["untracked_inventory_fingerprint"]
                == before["untracked_inventory_fingerprint"]
            ),
            "untracked_content_matches": (
                after["untracked_content_evidence_available"]
                and after["untracked_content_fingerprint"]
                == before["untracked_content_fingerprint"]
            ),
            "persistent_hook_policy_matches": (
                after["hooks"] == before["hooks"]
            ),
            "object_substitution_matches": (
                after["object_substitution"]
                == before["object_substitution"]
                and after["object_substitution"]["evidence_available"]
                and not after["object_substitution"]["present"]
            ),
            "persistent_signing_configuration_matches": (
                after["signing"] == before["signing"]
            ),
        },
        "decision": {
            "verified": verified,
            "reasons": reasons,
        },
        "proof_boundary": (
            "Verification proves consistency with the private receipt and "
            "consumed token; it does not attest the actual commit invocation, "
            "command-scoped overrides, or receipt time against a hostile "
            "process running as the same local principal."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        description=(
            "Private receipts and one-use authorization for a failed "
            "ordinary signed Git commit."
        )
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    audit = subparsers.add_parser("audit")
    audit.add_argument("--repo", required=True)
    audit.add_argument(
        "--policy",
        choices=("required", "optional", "unknown"),
        required=True,
    )
    audit.add_argument("--receipt", required=True)
    audit.add_argument("--authorization", required=True)

    authorize = subparsers.add_parser("authorize")
    authorize.add_argument("--repo", required=True)
    authorize.add_argument("--receipt", required=True)
    authorize.add_argument("--authorization", required=True)
    authorize.add_argument(
        "--signer-probe",
        choices=("unknown", "failed", "verified"),
        default="unknown",
    )
    authorize.add_argument(
        "--commit-shape",
        choices=("unverified", "verified-plain-index"),
        default="unverified",
    )

    verify = subparsers.add_parser("verify")
    verify.add_argument("--repo", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--authorization", required=True)
    return parser


def error_payload(code: str) -> dict[str, Any]:
    return {
        "schema": ERROR_SCHEMA,
        "operation": "error",
        "status": "error",
        "error_code": code,
    }


def execute(argv: Sequence[str]) -> tuple[int, dict[str, Any]]:
    try:
        options = build_parser().parse_args(list(argv))
        if options.mode == "verify":
            return verify_receipt(options)
        if options.mode == "authorize":
            return authorize_retry(options)
        return audit_receipt(options)
    except InputError:
        return 1, error_payload("invalid_input")
    except SafetyRefusal:
        return 2, error_payload("safety_refusal")
    except EvidenceError:
        return 1, error_payload("evidence_unavailable")
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
