#!/usr/bin/env python3
"""Token-efficient, safe-ish inspection helpers for Codex rollout JSONL logs.

The default output is deliberately compact and redacted. Use raw log files only
after this tool has narrowed the path/line range that actually matters.
"""

from __future__ import annotations

import argparse
import collections
import datetime as _dt
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Iterable


UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
ROLLOUT_TS_RE = re.compile(r"rollout-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})")
LONG_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_./-])[A-Za-z0-9_+/=-]{120,}(?![A-Za-z0-9_./-])")
SENSITIVE_KEY_PATTERN = (
    r"(?:[A-Za-z0-9]+[_-])*(?:api[_-]?key|token|secret|password|passwd|"
    r"private[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"client[_-]?secret|authorization|credentials?|cookie|set[_-]?cookie)"
)
SENSITIVE_KEYS = {
    "apikey",
    "token",
    "secret",
    "password",
    "passwd",
    "privatekey",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "clientsecret",
    "authorization",
    "cookie",
    "setcookie",
    "credential",
    "credentials",
}
QUOTED_SECRET_RE = re.compile(
    rf"(?i)(?P<prefix>[\"']?\b(?:{SENSITIVE_KEY_PATTERN})\b[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)"
)
QUOTED_ENV_RE = re.compile(
    r"(?m)(?P<prefix>(?<![A-Za-z0-9_])(?:export\s+|\$env:)?"
    r"[A-Z][A-Z0-9_]{1,63}\s*=\s*)"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)"
)
BARE_ENV_RE = re.compile(
    r"(?m)(?P<prefix>(?<![A-Za-z0-9_])(?:export\s+|\$env:)?"
    r"[A-Z][A-Z0-9_]{1,63}\s*=\s*)(?P<value>[^\s,;\\\"']+)"
)
COOKIE_HEADER_RE = re.compile(
    r"(?i)\b(?P<name>set-cookie|cookie)(?P<sep>\s*:\s*)[^\"\r\n]+"
)
PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----.*?"
    r"-----END (?:RSA |OPENSSH |EC )?PRIVATE KEY-----",
    re.DOTALL,
)
PRIVATE_KEY_MARKER_RE = re.compile(
    r"-----(?:BEGIN|END) (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"
)
URL_CREDENTIAL_RE = re.compile(
    r"(?i)(\b[a-z][a-z0-9+.-]*://)([^/\s:@]+):([^@/\s]+)@"
)
ANSI_OSC_RE = re.compile(r"\x1b\].*?(?:\x07|\x1b\\)", re.DOTALL)
ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
BIDI_CONTROL_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
OTHER_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
SECRET_REPLACEMENTS = [
    (
        re.compile(
            r"(?i)(authorization\s*[:=]\s*(?:bearer|basic)\s+)([^\s\"']+)"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            rf"(?i)([\"']?\b(?:{SENSITIVE_KEY_PATTERN})\b[\"']?)"
            r"(\s*[=:]\s*)([^\"'\s,;\\]+)"
        ),
        r"\1\2[REDACTED]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "sk-[REDACTED]"),
    (re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"), "ghp_[REDACTED]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "github_pat_[REDACTED]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "xox[REDACTED]"),
]

class RolloutIdentity:
    """Normalized identity and execution boundary for one rollout file."""

    def __init__(
        self,
        *,
        rollout_id: str,
        root_id: str | None,
        parent_id: str | None,
        ancestor_ids: list[str],
        session_meta_ids: list[str],
        active_start_line: int,
        pre_active_lines: int,
        pre_active_bytes: int,
        inherited_prefix_lines: int,
        inherited_prefix_bytes: int,
        inherited_prefix_ratio: float,
        boundary_basis: str,
        subagent_depth: int | None = None,
    ) -> None:
        self.rollout_id = rollout_id
        self.root_id = root_id
        self.parent_id = parent_id
        self.ancestor_ids = ancestor_ids
        self.session_meta_ids = session_meta_ids
        self.active_start_line = active_start_line
        self.pre_active_lines = pre_active_lines
        self.pre_active_bytes = pre_active_bytes
        self.inherited_prefix_lines = inherited_prefix_lines
        self.inherited_prefix_bytes = inherited_prefix_bytes
        self.inherited_prefix_ratio = inherited_prefix_ratio
        self.boundary_basis = boundary_basis
        self.subagent_depth = subagent_depth

    def as_dict(self) -> dict[str, Any]:
        confidence = {
            "root": "high",
            "uuidv7-turn": "high",
            "timestamp-gap": "low",
            "only-task-start": "low",
            "undetermined": "none",
        }.get(self.boundary_basis, "low")
        return {
            "rollout_id": self.rollout_id,
            "root_id": self.root_id,
            "parent_id": self.parent_id,
            "ancestor_ids": self.ancestor_ids,
            "session_meta_ids": self.session_meta_ids,
            "active_start_line": self.active_start_line,
            "pre_active_lines": self.pre_active_lines,
            "pre_active_bytes": self.pre_active_bytes,
            "inherited_prefix_lines": self.inherited_prefix_lines,
            "inherited_prefix_bytes": self.inherited_prefix_bytes,
            "inherited_prefix_ratio": self.inherited_prefix_ratio,
            "boundary_basis": self.boundary_basis,
            "active_scope_confidence": confidence,
            "subagent_depth": self.subagent_depth,
        }


class MessageMirrorDeduper:
    """Collapse adjacent event/response mirrors without hiding real repeats."""

    def __init__(self) -> None:
        self._last: tuple[str, str, str] | None = None

    def is_mirror(self, obj: dict[str, Any], role: str, text: str) -> bool:
        source = str(obj.get("type") or "")
        current = (source, role, text)
        previous = self._last
        if (
            previous is not None
            and previous[0] != source
            and previous[1] == role
            and previous[2] == text
            and {previous[0], source} == {"event_msg", "response_item"}
        ):
            # A mirror is a pair. Clearing the candidate prevents a third,
            # semantically distinct message from being swallowed.
            self._last = None
            return True
        self._last = current
        return False

    def break_adjacency(self) -> None:
        self._last = None


def codex_home(args: argparse.Namespace) -> Path:
    return Path(args.codex_home or os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def _sanitize_structure(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[Any, Any] = {}
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            is_sensitive = normalized in SENSITIVE_KEYS or any(
                normalized.endswith(suffix)
                for suffix in (
                    "apikey",
                    "token",
                    "secret",
                    "password",
                    "passwd",
                    "privatekey",
                    "credential",
                    "credentials",
                    "cookie",
                )
            )
            clean[key] = "[REDACTED]" if is_sensitive else _sanitize_structure(child)
        return clean
    if isinstance(value, list):
        return [_sanitize_structure(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(parsed, (dict, list)):
                    return json.dumps(
                        _sanitize_structure(parsed),
                        ensure_ascii=False,
                        sort_keys=True,
                    )
    return value


def _redact_quoted_secret(match: re.Match[str]) -> str:
    quote = match.group("quote")
    return f"{match.group('prefix')}{quote}[REDACTED]{quote}"


def redact(value: Any) -> str:
    parsed_outer: Any = None
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            candidate = json.loads(value)
        except json.JSONDecodeError:
            pass
        else:
            if isinstance(candidate, (dict, list)):
                parsed_outer = candidate
    if parsed_outer is not None:
        text = json.dumps(
            _sanitize_structure(parsed_outer),
            ensure_ascii=False,
            sort_keys=True,
        )
    else:
        safe_value = (
            _sanitize_structure(value) if isinstance(value, (dict, list)) else value
        )
        text = stringify(safe_value)
    text = ANSI_OSC_RE.sub("[CONTROL]", text)
    text = ANSI_CSI_RE.sub("[CONTROL]", text)
    text = BIDI_CONTROL_RE.sub("[CONTROL]", text)
    text = OTHER_CONTROL_RE.sub("[CONTROL]", text)
    text = PRIVATE_KEY_BLOCK_RE.sub("[REDACTED-PRIVATE-KEY]", text)
    text = PRIVATE_KEY_MARKER_RE.sub("[REDACTED-PRIVATE-KEY]", text)
    text = URL_CREDENTIAL_RE.sub(r"\1[REDACTED]@", text)
    text = QUOTED_ENV_RE.sub(_redact_quoted_secret, text)
    text = BARE_ENV_RE.sub(r"\g<prefix>[REDACTED]", text)
    text = QUOTED_SECRET_RE.sub(_redact_quoted_secret, text)
    text = COOKIE_HEADER_RE.sub(
        lambda match: f"{match.group('name')}{match.group('sep')}[REDACTED]", text
    )
    for pattern, repl in SECRET_REPLACEMENTS:
        text = pattern.sub(repl, text)
    text = LONG_TOKEN_RE.sub("[REDACTED-LONG-BLOB]", text)
    return text


def clip(text: Any, max_chars: int) -> str:
    value = re.sub(r"\s+", " ", redact(text)).strip()
    if max_chars > 0 and len(value) > max_chars:
        return value[: max(1, max_chars - 3)].rstrip() + "..."
    return value


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for key in ("text", "message", "content", "input"):
                    if isinstance(item.get(key), str):
                        parts.append(item[key])
                        break
        return "\n".join(parts) if parts else json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        for key in ("text", "message", "content", "summary"):
            if isinstance(value.get(key), str):
                return value[key]
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def parse_rollout_timestamp(path: Path) -> str:
    match = ROLLOUT_TS_RE.search(path.name)
    if not match:
        return ""
    date, time = match.group(1).split("T", 1)
    return f"{date} {time.replace('-', ':')}"


def thread_id_from_path(path: Path) -> str:
    match = UUID_RE.search(path.name)
    return match.group(0) if match else ""


def mtime_iso(path: Path) -> str:
    try:
        return _dt.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return ""


def size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def iter_session_paths(home: Path, include_archived: bool = True) -> list[Path]:
    roots = [home / "sessions"]
    if include_archived:
        roots.append(home / "archived_sessions")
    paths: list[Path] = []
    for root in roots:
        if root.exists():
            paths.extend(root.rglob("rollout-*.jsonl"))
    return sorted(paths, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)


def iter_records(path: Path) -> Iterable[tuple[int, dict[str, Any] | None, str | None, str]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                yield line_no, None, f"{exc.msg} at column {exc.colno}", line
                continue
            if isinstance(obj, dict):
                yield line_no, obj, None, line
            else:
                yield line_no, None, "JSON line is not an object", line


def _uuid_v7_millis(value: Any) -> int | None:
    """Return the UUIDv7 timestamp prefix without requiring uuid.version support."""

    text = str(value or "")
    if not UUID_RE.fullmatch(text):
        return None
    compact = text.replace("-", "")
    # UUIDv7 stores Unix milliseconds in its first 48 bits. Requiring the
    # version nibble avoids treating arbitrary UUIDs as comparable clocks.
    if len(compact) != 32 or compact[12] != "7":
        return None
    try:
        return int(compact[:12], 16)
    except ValueError:
        return None


def _parse_timestamp(value: Any) -> _dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def _thread_spawn(pl: dict[str, Any]) -> dict[str, Any]:
    source = pl.get("source")
    if not isinstance(source, dict):
        return {}
    subagent = source.get("subagent")
    if not isinstance(subagent, dict):
        return {}
    spawn = subagent.get("thread_spawn")
    return spawn if isinstance(spawn, dict) else {}


def inspect_rollout_identity(path: Path) -> RolloutIdentity:
    """Separate the file's child identity from copied ancestor metadata.

    Modern full-history forks prepend a child ``session_meta`` and then copy
    ancestor records into the same JSONL. UUIDv7 turn ids provide the clearest
    active-boundary signal: inherited turn ids predate the child rollout id,
    while the first child turn does not. Synthetic/early formats without UUIDv7
    turn ids use the largest pre-task timestamp gap as a conservative fallback.
    """

    filename_id = thread_id_from_path(path)
    rollout_id = filename_id
    parent_id: str | None = None
    depth: int | None = None
    meta_ids: list[str] = []
    root_meta_ids: list[str] = []
    meta_parent_by_id: dict[str, str] = {}
    task_candidates: list[dict[str, Any]] = []
    cumulative_bytes = 0
    previous_timestamp: _dt.datetime | None = None
    selected: dict[str, Any] | None = None
    selected_basis = "root"
    own_meta_bytes = 0

    for line_no, obj, error, raw_line in iter_records(path):
        offset_before = cumulative_bytes
        cumulative_bytes += len(raw_line.encode("utf-8", errors="replace"))
        if error or obj is None:
            continue
        pl = payload(obj)
        top_type = obj.get("type")
        pl_type = pl.get("type")

        if top_type == "session_meta":
            meta_id = str(pl.get("id") or pl.get("session_id") or "")
            if meta_id:
                meta_ids.append(meta_id)
                meta_spawn = _thread_spawn(pl)
                meta_parent = (
                    pl.get("parent_thread_id")
                    or pl.get("forked_from_id")
                    or meta_spawn.get("parent_thread_id")
                )
                if not meta_parent:
                    root_meta_ids.append(meta_id)
                else:
                    meta_parent_by_id[meta_id] = str(meta_parent)
                if len(meta_ids) == 1:
                    rollout_id = meta_id
                    spawn = meta_spawn
                    explicit_parent = (
                        pl.get("parent_thread_id")
                        or pl.get("forked_from_id")
                        or spawn.get("parent_thread_id")
                    )
                    parent_id = str(explicit_parent) if explicit_parent else None
                    raw_depth = spawn.get("depth")
                    if isinstance(raw_depth, int):
                        depth = raw_depth
                    if line_no == 1:
                        own_meta_bytes = len(raw_line.encode("utf-8", errors="replace"))

        current_timestamp = _parse_timestamp(obj.get("timestamp"))
        gap_seconds = 0.0
        if current_timestamp is not None and previous_timestamp is not None:
            gap_seconds = max(0.0, (current_timestamp - previous_timestamp).total_seconds())

        if top_type == "event_msg" and pl_type == "task_started":
            candidate = {
                "line": line_no,
                "bytes": offset_before,
                "turn_id": str(pl.get("turn_id") or pl.get("id") or ""),
                "gap_seconds": gap_seconds,
            }
            task_candidates.append(candidate)
            rollout_ms = _uuid_v7_millis(rollout_id)
            turn_ms = _uuid_v7_millis(candidate["turn_id"])
            if parent_id and rollout_ms is not None and turn_ms is not None and turn_ms >= rollout_ms:
                selected = candidate
                selected_basis = "uuidv7-turn"
                break
            if (
                parent_id is None
                and meta_ids
                and meta_ids[0] in root_meta_ids
            ):
                # Root identity is established before its first task. Avoid a
                # second full-file pass merely to prove there are no ancestors.
                break

        if current_timestamp is not None:
            previous_timestamp = current_timestamp

    unique_meta_ids = uniq(meta_ids)
    if parent_id is None and len(unique_meta_ids) > 1:
        parent_id = unique_meta_ids[1]
    if parent_id and rollout_id not in meta_parent_by_id:
        meta_parent_by_id[rollout_id] = parent_id

    ancestor_ids: list[str] = []
    cursor = rollout_id
    seen_lineage = {rollout_id}
    while cursor in meta_parent_by_id:
        next_id = meta_parent_by_id[cursor]
        if not next_id or next_id in seen_lineage:
            break
        ancestor_ids.append(next_id)
        seen_lineage.add(next_id)
        cursor = next_id

    is_child = parent_id is not None
    if not is_child:
        root_id: str | None = rollout_id
        active_start_line = 1
        prefix_bytes = 0
        selected_basis = "root"
    else:
        copied_root_ids = [
            value for value in uniq(root_meta_ids) if value != rollout_id
        ]
        non_parent_root_ids = [
            value for value in copied_root_ids if value != parent_id
        ]
        if depth is not None and depth > 0 and len(ancestor_ids) >= depth:
            root_id = ancestor_ids[depth - 1]
        elif len(non_parent_root_ids) == 1:
            root_id = non_parent_root_ids[0]
        elif depth == 1:
            root_id = parent_id
        else:
            # A context-free or nested child exposes its direct parent but not
            # enough lineage to name the root safely unless copied metadata
            # identifies an ancestor with no parent.
            root_id = None

        if root_id and root_id not in ancestor_ids:
            ancestor_ids.append(root_id)

        if selected is None and task_candidates:
            if len(task_candidates) == 1:
                selected = task_candidates[0]
                selected_basis = "only-task-start"
            else:
                # Used only when modern UUIDv7 turn ids are unavailable. Copied
                # history is serialized as a tight burst; the real child turn
                # begins after the largest gap. Prefer a later candidate on a
                # tie so the first inherited task is not mislabeled active.
                selected = max(
                    task_candidates,
                    key=lambda row: (row["gap_seconds"], row["line"]),
                )
                selected_basis = "timestamp-gap"

        if selected is None:
            active_start_line = 1
            prefix_bytes = 0
            selected_basis = "undetermined"
        else:
            active_start_line = int(selected["line"])
            prefix_bytes = int(selected["bytes"])

    file_bytes = 0
    try:
        file_bytes = path.stat().st_size
    except OSError:
        pass
    pre_active_lines = max(0, active_start_line - 1) if is_child else 0
    pre_active_bytes = prefix_bytes if is_child else 0
    inherited_lines = max(0, pre_active_lines - (1 if own_meta_bytes else 0))
    inherited_bytes = max(0, pre_active_bytes - own_meta_bytes)
    ratio = (inherited_bytes / file_bytes) if file_bytes else 0.0
    return RolloutIdentity(
        rollout_id=rollout_id,
        root_id=root_id,
        parent_id=parent_id,
        ancestor_ids=ancestor_ids,
        session_meta_ids=unique_meta_ids,
        active_start_line=active_start_line,
        pre_active_lines=pre_active_lines,
        pre_active_bytes=pre_active_bytes,
        inherited_prefix_lines=inherited_lines,
        inherited_prefix_bytes=inherited_bytes,
        inherited_prefix_ratio=round(ratio, 6) if is_child else 0.0,
        boundary_basis=selected_basis,
        subagent_depth=depth,
    )


def payload(obj: dict[str, Any]) -> dict[str, Any]:
    value = obj.get("payload")
    return value if isinstance(value, dict) else {}


def message_text(obj: dict[str, Any]) -> tuple[str, str]:
    pl = payload(obj)
    top_type = obj.get("type")
    payload_type = pl.get("type")
    if top_type == "response_item" and payload_type == "message":
        return str(pl.get("role") or "message"), stringify(pl.get("content"))
    if top_type == "response_item" and payload_type == "agent_message":
        return "assistant", stringify(pl.get("message") or pl.get("content"))
    if top_type == "event_msg" and payload_type == "user_message":
        return "user", stringify(pl.get("message") or pl.get("text_elements"))
    if top_type == "event_msg" and payload_type == "agent_message":
        return "assistant", stringify(pl.get("message"))
    return "", ""


def line_in_scope(
    line_no: int, identity: RolloutIdentity, include_inherited: bool
) -> bool:
    start = scope_start_line(identity, include_inherited)
    return start is not None and line_no >= start


def scope_start_line(
    identity: RolloutIdentity, include_inherited: bool
) -> int | None:
    if include_inherited or identity.parent_id is None:
        return 1
    if identity.boundary_basis != "uuidv7-turn":
        # A low-confidence heuristic is useful metadata but is not safe as a
        # content boundary. Require an explicit all-history request.
        return None
    return identity.active_start_line


def scope_name(identity: RolloutIdentity, include_inherited: bool) -> str:
    if include_inherited:
        return "all"
    if identity.parent_id and scope_start_line(identity, False) is None:
        return "boundary-undetermined"
    return "active"


def _parse_tool_input(pl: dict[str, Any]) -> Any:
    raw_args = pl.get("arguments")
    if raw_args is None:
        raw_args = pl.get("input")
    if isinstance(raw_args, str):
        try:
            return json.loads(raw_args)
        except json.JSONDecodeError:
            return raw_args
    return raw_args


def function_call_summary(obj: dict[str, Any], max_chars: int) -> tuple[str, str]:
    pl = payload(obj)
    name = str(pl.get("name") or "")
    parsed = _parse_tool_input(pl)

    if isinstance(parsed, dict):
        if name in {"exec_command", "shell_command"}:
            fields = []
            command = parsed.get("cmd") or parsed.get("command")
            if command:
                fields.append(f"command={command}")
            if parsed.get("workdir"):
                fields.append(f"workdir={parsed.get('workdir')}")
            if parsed.get("sandbox_permissions"):
                fields.append(f"sandbox={parsed.get('sandbox_permissions')}")
            return name, clip(" | ".join(fields), max_chars)
        for key in ("cmd", "command", "query", "pattern", "path", "file", "ref_id"):
            if parsed.get(key):
                return name, clip(f"{key}={parsed.get(key)}", max_chars)
        return name, clip(parsed, max_chars)
    # Custom `exec` inputs are JavaScript source. Treat them as opaque redacted
    # text; inferring nested calls from source would overstate executed work.
    return name, clip(parsed, max_chars)


def latest_token_summary(obj: dict[str, Any]) -> str:
    pl = payload(obj)
    info = pl.get("info")
    if not isinstance(info, dict):
        return ""
    total = (
        info.get("total_token_usage")
        or info.get("total_tokens")
        or info.get("token_usage")
        or info.get("usage")
    )
    return clip(total, 160)


def digest_session(
    path: Path,
    query: str = "",
    cwd: str = "",
    max_chars: int = 220,
    include_inherited: bool = False,
) -> dict[str, Any]:
    identity = inspect_rollout_identity(path)
    query_tokens = [t.lower() for t in re.findall(r"[\w./:-]{2,}", query)]
    cwd_l = cwd.lower()
    counts: collections.Counter[str] = collections.Counter()
    payload_counts: collections.Counter[str] = collections.Counter()
    tool_counts: collections.Counter[str] = collections.Counter()
    cwds: list[str] = []
    models: list[str] = []
    user_snippets: collections.deque[str] = collections.deque(maxlen=3)
    assistant_snippets: collections.deque[str] = collections.deque(maxlen=3)
    command_snippets: collections.deque[str] = collections.deque(maxlen=5)
    query_hits: list[str] = []
    malformed = 0
    total_malformed = 0
    line_count = 0
    session_id = identity.rollout_id
    first_ts = ""
    last_ts = ""
    token_summary = ""
    score = 0
    reasons: set[str] = set()
    mirror_count = 0
    message_deduper = MessageMirrorDeduper()

    for line_no, obj, error, raw_line in iter_records(path):
        line_count = line_no
        if error:
            total_malformed += 1
            if line_in_scope(line_no, identity, include_inherited):
                malformed += 1
            message_deduper.break_adjacency()
            continue
        assert obj is not None
        top_type = str(obj.get("type") or "")
        pl = payload(obj)
        pl_type = str(pl.get("type") or "")

        # The first metadata row belongs to this rollout even when a child's
        # active scope begins later. Preserve its cwd/model without scanning
        # copied ancestor metadata into the active summary.
        if line_no == 1 and top_type == "session_meta":
            if pl.get("cwd"):
                cwds.append(str(pl.get("cwd")))
            if pl.get("model") or pl.get("model_provider"):
                models.append(str(pl.get("model") or pl.get("model_provider")))

        if not line_in_scope(line_no, identity, include_inherited):
            message_deduper.break_adjacency()
            continue

        first_ts = first_ts or str(obj.get("timestamp") or "")
        last_ts = str(obj.get("timestamp") or last_ts)
        counts[top_type] += 1
        if pl_type:
            payload_counts[pl_type] += 1

        if top_type == "session_meta":
            if pl.get("cwd"):
                cwds.append(str(pl.get("cwd")))
            if pl.get("model") or pl.get("model_provider"):
                models.append(str(pl.get("model") or pl.get("model_provider")))
        elif top_type == "turn_context":
            if pl.get("cwd"):
                cwds.append(str(pl.get("cwd")))
            if pl.get("model"):
                models.append(str(pl.get("model")))

        role, text = message_text(obj)
        if text:
            if message_deduper.is_mirror(obj, role, text):
                mirror_count += 1
                continue
            snippet = clip(text, max_chars)
            if role == "user":
                user_snippets.append(snippet)
            elif role in {"assistant", "assistant_final", "assistant_message"}:
                assistant_snippets.append(snippet)
            score += score_text(text, query_tokens, "message", query_hits, line_no)
        else:
            message_deduper.break_adjacency()

        if top_type == "response_item" and pl_type in {"function_call", "custom_tool_call"}:
            tool, summary = function_call_summary(obj, max_chars=max_chars)
            if tool:
                tool_counts[tool] += 1
                score += score_text(tool, query_tokens, "tool", query_hits, line_no)
                if summary:
                    score += score_text(summary, query_tokens, "command", query_hits, line_no)
                if tool in {"exec_command", "shell_command"} and summary:
                    command_snippets.append(summary)
                elif tool == "exec" and summary:
                    command_snippets.append(summary)

        if top_type == "event_msg" and pl_type == "token_count":
            token_summary = latest_token_summary(obj) or token_summary

    unique_cwds = uniq(cwds)
    unique_models = uniq(models)
    path_text = str(path)
    score += score_text(path_text, query_tokens, "path", query_hits, 0)
    if cwd_l:
        for seen_cwd in unique_cwds:
            lower = seen_cwd.lower()
            if cwd_l == lower:
                score += 260
                reasons.add("cwd-exact")
            elif cwd_l in lower or lower in cwd_l:
                score += 140
                reasons.add("cwd-related")
    if query and query.lower() in path_text.lower():
        reasons.add("query-in-path")

    age_bonus = recency_bonus(path)
    if age_bonus:
        score += age_bonus
        reasons.add("recent")
    if malformed:
        reasons.add("malformed-jsonl")

    return {
        "path": str(path),
        "id": session_id,
        **identity.as_dict(),
        "mtime": mtime_iso(path),
        "rollout_time": parse_rollout_timestamp(path),
        "size_mb": round(size_mb(path), 2),
        "line_count": line_count,
        "malformed_lines": malformed,
        "total_malformed_lines": total_malformed,
        "scope": scope_name(identity, include_inherited),
        "scope_start_line": scope_start_line(identity, include_inherited),
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "cwd": unique_cwds[:5],
        "models": unique_models[:5],
        "record_types": dict(counts.most_common()),
        "payload_types": dict(payload_counts.most_common()),
        "tools": dict(tool_counts.most_common(12)),
        "mirrored_messages_deduplicated": mirror_count,
        "last_user": list(user_snippets),
        "last_assistant": list(assistant_snippets),
        "last_commands": list(command_snippets),
        "token_summary": token_summary,
        "score": score,
        "reasons": sorted(reasons | set(query_hits[:12])),
    }


def score_text(text: Any, tokens: list[str], label: str, hits: list[str], line_no: int) -> int:
    if not tokens:
        return 0
    haystack = stringify(text).lower()
    score = 0
    for token in tokens:
        if token and token in haystack:
            score += 28 if label in {"message", "command"} else 14
            if len(hits) < 20:
                suffix = f":{line_no}" if line_no else ""
                # Preserve evidence location without echoing a query that may
                # itself be a credential or other sensitive literal.
                hits.append(f"{label}{suffix}")
    return score


def recency_bonus(path: Path) -> int:
    try:
        age_days = max(0.0, (_dt.datetime.now().timestamp() - path.stat().st_mtime) / 86400)
    except OSError:
        return 0
    if age_days < 1:
        return 20
    if age_days < 7:
        return 12
    if age_days < 30:
        return 5
    return 0


def uniq(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def resolve_target(target: str, home: Path) -> Path:
    path = Path(target).expanduser()
    if path.exists():
        if (
            not path.is_file()
            or path.suffix.lower() != ".jsonl"
            or not path.name.startswith("rollout-")
        ):
            raise SystemExit(
                "target path must be a rollout-*.jsonl regular file"
            )
        return path
    if UUID_RE.fullmatch(target):
        matches = [p for p in iter_session_paths(home) if target in p.name]
        if matches:
            return matches[0]
    raise SystemExit(f"target not found as path or CODEX_THREAD_ID: {target}")


def filtered_paths(args: argparse.Namespace) -> list[Path]:
    home = codex_home(args)
    paths = iter_session_paths(home, include_archived=not getattr(args, "no_archived", False))
    since_days = getattr(args, "since_days", None)
    if since_days is not None:
        cutoff = _dt.datetime.now().timestamp() - since_days * 86400
        paths = [p for p in paths if p.stat().st_mtime >= cutoff]
    return paths[: getattr(args, "scan_limit", len(paths))]


def cmd_find(args: argparse.Namespace) -> int:
    home = codex_home(args)
    if args.thread_id:
        # Exact lookup must not be defeated by recency, scan-limit, or size
        # defaults. The filename is the rollout identity source of truth.
        paths = [
            path
            for path in iter_session_paths(
                home, include_archived=not getattr(args, "no_archived", False)
            )
            if thread_id_from_path(path).lower() == args.thread_id.lower()
        ]
    else:
        paths = filtered_paths(args)
    rows: list[dict[str, Any]] = []
    for path in paths:
        large = size_mb(path) > args.max_mb
        if large and not (args.thread_id and args.thread_id in path.name) and not args.include_large:
            if args.query or args.cwd or args.thread_id:
                path_l = str(path).lower()
                if args.query.lower() not in path_l and args.cwd.lower() not in path_l:
                    continue
            rows.append(metadata_row(path, skipped_reason=f"large>{args.max_mb:g}MB"))
            continue
        digest = digest_session(
            path,
            query=args.query or args.thread_id or "",
            cwd=args.cwd or "",
            max_chars=args.max_chars,
        )
        if args.thread_id and args.thread_id.lower() == str(digest.get("id") or "").lower():
            digest["score"] += 1000
            digest["reasons"] = sorted(set(digest["reasons"]) | {"thread-id"})
        if args.query or args.cwd or args.thread_id:
            if digest["score"] <= 0 and not (args.thread_id and args.thread_id in path.name):
                continue
        rows.append(digest)
    rows.sort(key=lambda row: (row.get("score", 0), row.get("mtime", "")), reverse=True)
    rows = rows[: args.limit]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print_find_rows(rows)
    return 0


def metadata_row(path: Path, skipped_reason: str = "") -> dict[str, Any]:
    return {
        "path": str(path),
        "id": thread_id_from_path(path),
        "mtime": mtime_iso(path),
        "rollout_time": parse_rollout_timestamp(path),
        "size_mb": round(size_mb(path), 2),
        "score": recency_bonus(path),
        "reasons": [skipped_reason] if skipped_reason else ["metadata-only"],
        "cwd": [],
        "last_user": [],
        "last_assistant": [],
        "last_commands": [],
    }


def print_find_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No matching Codex rollout logs found.")
        return
    for i, row in enumerate(rows, 1):
        cwd = "; ".join(row.get("cwd") or []) or "-"
        reasons = ", ".join(row.get("reasons") or [])
        print(f"{i}. score={row.get('score', 0)} size={row.get('size_mb')}MB mtime={row.get('mtime')}")
        print(f"   id: {row.get('id') or '-'}")
        print(f"   cwd: {clip(cwd, 180)}")
        print(f"   reasons: {clip(reasons, 180)}")
        print(f"   path: {row.get('path')}")


def cmd_brief(args: argparse.Namespace) -> int:
    path = resolve_target(args.target, codex_home(args))
    digest = digest_session(
        path,
        query=args.query or "",
        cwd="",
        max_chars=args.max_chars,
        include_inherited=args.include_inherited,
    )
    if args.json:
        print(json.dumps(digest, ensure_ascii=False, indent=2))
        return 0
    print(f"path: {digest['path']}")
    print(f"id: {digest.get('id') or '-'}")
    print(
        f"scope: {digest.get('scope')}  start_line: {digest.get('scope_start_line')} "
        f"confidence: {digest.get('active_scope_confidence')}  "
        f"basis: {digest.get('boundary_basis')}"
    )
    if digest.get("parent_id"):
        print(
            f"lineage: rollout={digest.get('rollout_id')} parent={digest.get('parent_id')} "
            f"root={digest.get('root_id') or '?'}"
        )
        print(
            f"active_start_line: {digest.get('active_start_line')}  "
            f"inherited_prefix: {digest.get('inherited_prefix_lines')} lines / "
            f"{digest.get('inherited_prefix_bytes')} bytes "
            f"({digest.get('inherited_prefix_ratio'):.2%})"
        )
    print(f"mtime: {digest.get('mtime')}  size: {digest.get('size_mb')}MB  lines: {digest.get('line_count')}")
    print(f"malformed_lines: {digest.get('malformed_lines')}")
    print(f"cwd: {'; '.join(digest.get('cwd') or []) or '-'}")
    print(f"models: {', '.join(digest.get('models') or []) or '-'}")
    print(f"record_types: {digest.get('record_types')}")
    print(f"payload_types: {digest.get('payload_types')}")
    print(f"tools: {digest.get('tools')}")
    if digest.get("mirrored_messages_deduplicated"):
        print(f"mirrored_messages_deduplicated: {digest.get('mirrored_messages_deduplicated')}")
    if digest.get("token_summary"):
        print(f"latest_token_summary: {digest['token_summary']}")
    print_list("last_user", digest.get("last_user") or [])
    print_list("last_assistant", digest.get("last_assistant") or [])
    print_list("last_commands", digest.get("last_commands") or [])
    return 0


def print_list(title: str, values: list[str]) -> None:
    print(f"{title}:")
    if not values:
        print("  -")
        return
    for value in values:
        print(f"  - {value}")


def cmd_timeline(args: argparse.Namespace) -> int:
    path = resolve_target(args.target, codex_home(args))
    identity = inspect_rollout_identity(path)
    events: list[dict[str, Any]] = []
    message_deduper = MessageMirrorDeduper()
    for line_no, obj, error, raw_line in iter_records(path):
        if not line_in_scope(line_no, identity, args.include_inherited):
            message_deduper.break_adjacency()
            continue
        if error:
            message_deduper.break_adjacency()
            events.append({"line": line_no, "kind": "malformed", "summary": error})
            continue
        assert obj is not None
        if identity.parent_id and line_no == identity.active_start_line:
            events.append(
                {
                    "line": line_no,
                    "time": obj.get("timestamp"),
                    "kind": "active_boundary",
                    "summary": (
                        f"rollout={identity.rollout_id} parent={identity.parent_id} "
                        f"root={identity.root_id or '?'} basis={identity.boundary_basis}"
                    ),
                }
            )
        pl = payload(obj)
        top_type = str(obj.get("type") or "")
        pl_type = str(pl.get("type") or "")
        role, text = message_text(obj)
        if text:
            if message_deduper.is_mirror(obj, role, text):
                continue
            events.append(
                {
                    "line": line_no,
                    "time": obj.get("timestamp"),
                    "kind": role,
                    "summary": clip(text, args.max_chars),
                }
            )
        else:
            message_deduper.break_adjacency()
        if not text and top_type == "response_item" and pl_type in {"function_call", "custom_tool_call"}:
            tool, summary = function_call_summary(obj, args.max_chars)
            events.append(
                {
                    "line": line_no,
                    "time": obj.get("timestamp"),
                    "kind": f"tool:{tool or '?'}",
                    "summary": summary,
                }
            )
        elif not text and top_type == "event_msg" and pl_type in {
            "task_started",
            "task_complete",
            "turn_aborted",
            "thread_rolled_back",
            "token_count",
        }:
            summary = latest_token_summary(obj) if pl_type == "token_count" else clip(pl, args.max_chars)
            events.append(
                {
                    "line": line_no,
                    "time": obj.get("timestamp"),
                    "kind": pl_type,
                    "summary": summary,
                }
            )
        elif not text and top_type in {"turn_context", "session_meta", "compacted"}:
            events.append(
                {
                    "line": line_no,
                    "time": obj.get("timestamp"),
                    "kind": top_type,
                    "summary": clip(pl, args.max_chars),
                }
            )
    events = select_tail_limit(events, args.limit, args.tail)
    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
    else:
        for event in events:
            print(f"{event['line']:>6} {event.get('kind','-'):<22} {event.get('summary','')}")
    return 0


def select_tail_limit(items: list[dict[str, Any]], limit: int, tail: int) -> list[dict[str, Any]]:
    if tail:
        return items[-tail:]
    return items[:limit]


def cmd_messages(args: argparse.Namespace) -> int:
    path = resolve_target(args.target, codex_home(args))
    identity = inspect_rollout_identity(path)
    rows: list[dict[str, Any]] = []
    message_deduper = MessageMirrorDeduper()
    for line_no, obj, error, raw_line in iter_records(path):
        if not line_in_scope(line_no, identity, args.include_inherited):
            message_deduper.break_adjacency()
            continue
        if error or obj is None:
            message_deduper.break_adjacency()
            continue
        role, text = message_text(obj)
        if not text:
            message_deduper.break_adjacency()
            continue
        if message_deduper.is_mirror(obj, role, text):
            continue
        if args.role != "all" and role != args.role:
            continue
        rows.append(
            {
                "line": line_no,
                "time": obj.get("timestamp"),
                "role": role,
                "message": clip(text, args.max_chars),
            }
        )
    rows = select_tail_limit(rows, args.limit, args.tail)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['line']:>6} {row['role']:<10} {row['message']}")
    return 0


def cmd_commands(args: argparse.Namespace) -> int:
    path = resolve_target(args.target, codex_home(args))
    identity = inspect_rollout_identity(path)
    rows: list[dict[str, Any]] = []
    for line_no, obj, error, raw_line in iter_records(path):
        if not line_in_scope(line_no, identity, args.include_inherited):
            continue
        if error or obj is None:
            continue
        pl = payload(obj)
        if obj.get("type") != "response_item" or pl.get("type") not in {"function_call", "custom_tool_call"}:
            continue
        tool, summary = function_call_summary(obj, args.max_chars)
        if args.tool and tool != args.tool:
            continue
        rows.append(
            {
                "line": line_no,
                "time": obj.get("timestamp"),
                "tool": tool,
                "summary": summary,
            }
        )
    rows = select_tail_limit(rows, args.limit, args.tail)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['line']:>6} {row['tool']:<24} {row['summary']}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    if args.target:
        paths = [resolve_target(args.target, codex_home(args))]
    else:
        paths = filtered_paths(args)
    flags = 0 if args.case_sensitive else re.IGNORECASE
    pattern = re.compile(args.pattern if args.regex else re.escape(args.pattern), flags)
    rows: list[dict[str, Any]] = []
    for path in paths:
        if size_mb(path) > args.max_mb and not args.include_large:
            continue
        identity = inspect_rollout_identity(path)
        message_deduper = MessageMirrorDeduper()
        for line_no, obj, error, raw_line in iter_records(path):
            if not line_in_scope(line_no, identity, args.include_inherited):
                message_deduper.break_adjacency()
                continue
            if not args.raw_line:
                if error or obj is None:
                    message_deduper.break_adjacency()
                else:
                    role, message = message_text(obj)
                    if message:
                        if message_deduper.is_mirror(obj, role, message):
                            continue
                    else:
                        message_deduper.break_adjacency()
            text = raw_line if args.raw_line else searchable_text(obj, error, raw_line)
            safe_full = redact(text)
            if pattern.search(safe_full):
                rows.append(
                    {
                        "path": str(path),
                        "line": line_no,
                        "kind": record_kind(obj, error),
                        "snippet": clip(safe_full, args.max_chars),
                    }
                )
                if len(rows) >= args.limit:
                    break
        if len(rows) >= args.limit:
            break
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['path']}:{row['line']} {row['kind']} {row['snippet']}")
    return 0


def searchable_text(obj: dict[str, Any] | None, error: str | None, raw_line: str) -> str:
    if error or obj is None:
        return raw_line
    role, text = message_text(obj)
    if text:
        return text
    pl = payload(obj)
    if obj.get("type") == "response_item" and pl.get("type") in {"function_call", "custom_tool_call"}:
        tool, summary = function_call_summary(obj, 1000)
        return f"{tool} {summary}"
    if obj.get("type") in {"session_meta", "turn_context"}:
        return stringify({k: pl.get(k) for k in ("id", "cwd", "model", "model_provider", "source", "summary")})
    return stringify({"type": obj.get("type"), "payload_type": pl.get("type")})


def record_kind(obj: dict[str, Any] | None, error: str | None) -> str:
    if error or obj is None:
        return "malformed"
    pl_type = payload(obj).get("type")
    return f"{obj.get('type')}/{pl_type}" if pl_type else str(obj.get("type"))


EXIT_CODE_RE = re.compile(
    r"(?im)^(?:exit[ _-]?code|return[ _-]?code)\s*[:=]\s*(-?\d+)\s*$"
)
SHELL_FAILURE_MARKER_RE = re.compile(r"(?im)^script (?:failed|error)\b")


def _tool_call_id(pl: dict[str, Any]) -> str:
    return str(pl.get("call_id") or pl.get("id") or "")


def _tool_signature(obj: dict[str, Any]) -> tuple[str, str, str]:
    pl = payload(obj)
    tool, summary = function_call_summary(obj, 220)
    normalized = re.sub(r"\s+", " ", redact(_parse_tool_input(pl))).strip()
    digest = hashlib.sha256(
        f"{tool}\0{normalized}".encode("utf-8", errors="replace")
    ).hexdigest()[:16]
    return tool, summary, digest


def _parsed_output(pl: dict[str, Any]) -> Any:
    value = pl.get("output")
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _explicit_failure_reason(obj: dict[str, Any]) -> str:
    """Return only structured or numeric failure evidence, never sentiment."""

    pl = payload(obj)
    parsed = _parsed_output(pl)
    for location, value in (("record", obj), ("payload", pl), ("output", parsed)):
        if isinstance(value, dict):
            for key in ("isError", "is_error"):
                if value.get(key) is True:
                    return f"{location}.{key}=true"
            for key in ("exit_code", "exitCode", "return_code", "returncode"):
                if key not in value:
                    continue
                try:
                    code = int(value[key])
                except (TypeError, ValueError):
                    continue
                if code != 0:
                    return f"{location}.{key}={code}"
        elif isinstance(value, str) and SHELL_FAILURE_MARKER_RE.search(value):
            match = EXIT_CODE_RE.search(value)
            if match and int(match.group(1)) != 0:
                return f"{location}.exit_code={match.group(1)}"
    return ""


def audit_session(path: Path, include_inherited: bool = False) -> dict[str, Any]:
    identity = inspect_rollout_identity(path)
    message_counts: collections.Counter[str] = collections.Counter()
    tool_counts: collections.Counter[str] = collections.Counter()
    call_records: dict[str, dict[str, Any]] = {}
    output_records: dict[str, int] = {}
    signatures: dict[tuple[str, str], dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    compaction_lines: list[int] = []
    mirror_count = 0
    malformed = 0
    total_malformed = 0
    records_in_scope = 0
    line_count = 0
    first_timestamp = ""
    last_timestamp = ""
    message_deduper = MessageMirrorDeduper()

    for line_no, obj, error, raw_line in iter_records(path):
        line_count = line_no
        if error or obj is None:
            total_malformed += 1
            if line_in_scope(line_no, identity, include_inherited):
                malformed += 1
            message_deduper.break_adjacency()
            continue
        if not line_in_scope(line_no, identity, include_inherited):
            message_deduper.break_adjacency()
            continue

        records_in_scope += 1
        first_timestamp = first_timestamp or str(obj.get("timestamp") or "")
        last_timestamp = str(obj.get("timestamp") or last_timestamp)
        pl = payload(obj)
        top_type = str(obj.get("type") or "")
        pl_type = str(pl.get("type") or "")

        role, text = message_text(obj)
        if text:
            if message_deduper.is_mirror(obj, role, text):
                mirror_count += 1
            else:
                message_counts[role] += 1
        else:
            message_deduper.break_adjacency()

        if top_type == "compacted" or (
            top_type == "event_msg" and pl_type in {"compacted", "context_compacted"}
        ):
            compaction_lines.append(line_no)

        if top_type != "response_item":
            continue
        if pl_type in {"function_call", "custom_tool_call"}:
            tool, summary, signature = _tool_signature(obj)
            tool_counts[tool or "?"] += 1
            call_id = _tool_call_id(pl)
            call_row = {
                "line": line_no,
                "tool": tool,
                "summary": summary,
                "signature": signature,
            }
            if call_id:
                call_records[call_id] = call_row
            key = (tool, signature)
            bucket = signatures.setdefault(
                key,
                {
                    "tool": tool,
                    "signature": signature,
                    "summary": summary,
                    "lines": [],
                },
            )
            bucket["lines"].append(line_no)
        elif pl_type in {"function_call_output", "custom_tool_call_output"}:
            call_id = _tool_call_id(pl)
            if call_id:
                output_records[call_id] = line_no
            reason = _explicit_failure_reason(obj)
            if reason:
                call = call_records.get(call_id, {})
                failures.append(
                    {
                        "line": line_no,
                        "call_id": call_id or None,
                        "tool": call.get("tool"),
                        "call_line": call.get("line"),
                        "reason": reason,
                    }
                )

    paired_ids = sorted(set(call_records) & set(output_records))
    unpaired_call_ids = sorted(set(call_records) - set(output_records))
    orphan_output_ids = sorted(set(output_records) - set(call_records))
    repeat_candidates = []
    for bucket in signatures.values():
        count = len(bucket["lines"])
        if count < 2:
            continue
        repeat_candidates.append(
            {
                **bucket,
                "count": count,
                "potential_duplicate_calls": count - 1,
            }
        )
    repeat_candidates.sort(key=lambda row: (-row["count"], row["lines"][0]))

    outer_total = sum(tool_counts.values())
    return {
        "path": str(path),
        "id": identity.rollout_id,
        **identity.as_dict(),
        "scope": scope_name(identity, include_inherited),
        "scope_start_line": scope_start_line(identity, include_inherited),
        "line_count": line_count,
        "records_in_scope": records_in_scope,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "logical_messages": {
            "total": sum(message_counts.values()),
            "by_role": dict(message_counts.most_common()),
        },
        "mirrored_messages_suppressed": mirror_count,
        "outer_tool_calls": {
            "total": outer_total,
            "by_tool": dict(tool_counts.most_common()),
            "opaque_exec_calls": tool_counts.get("exec", 0),
        },
        "call_output_pairs": {
            "paired": len(paired_ids),
            "calls_with_ids": len(call_records),
            "outputs_with_ids": len(output_records),
            "unpaired_call_ids": unpaired_call_ids,
            "orphan_output_ids": orphan_output_ids,
        },
        "explicit_failures": failures,
        "repeat_candidates": repeat_candidates,
        "potential_duplicate_calls": sum(
            row["potential_duplicate_calls"] for row in repeat_candidates
        ),
        "compactions": {
            "count": len(compaction_lines),
            "lines": compaction_lines,
        },
        "malformed_lines": malformed,
        "total_malformed_lines": total_malformed,
        "limitations": [
            "repeat_candidates_require surrounding-state review",
            "outer exec JavaScript is opaque; nested calls are not inferred",
            "compaction records are markers, not unique causal episodes",
        ],
    }


def cmd_audit(args: argparse.Namespace) -> int:
    path = resolve_target(args.target, codex_home(args))
    report = audit_session(path, include_inherited=args.include_inherited)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(f"path: {report['path']}")
    print(f"id: {report['id']}  scope: {report['scope']}")
    print(
        f"lineage: parent={report.get('parent_id') or '-'} "
        f"root={report.get('root_id') or '?'} basis={report.get('boundary_basis')}"
    )
    print(
        f"inherited_prefix: {report.get('inherited_prefix_lines')} lines / "
        f"{report.get('inherited_prefix_bytes')} bytes "
        f"({report.get('inherited_prefix_ratio'):.2%})"
    )
    print(
        f"logical_messages: {report['logical_messages']['total']}  "
        f"mirrors_suppressed: {report['mirrored_messages_suppressed']}"
    )
    print(
        f"outer_tool_calls: {report['outer_tool_calls']['total']}  "
        f"paired_outputs: {report['call_output_pairs']['paired']}  "
        f"explicit_failures: {len(report['explicit_failures'])}"
    )
    print(
        f"repeat_candidates: {len(report['repeat_candidates'])}  "
        f"potential_duplicate_calls: {report['potential_duplicate_calls']}  "
        f"compactions: {report['compactions']['count']}"
    )
    for row in report["repeat_candidates"][:10]:
        print(
            f"  repeat {row['tool']} x{row['count']} lines={row['lines']} "
            f"summary={row['summary']}"
        )
    for row in report["explicit_failures"][:10]:
        print(
            f"  failure line={row['line']} tool={row.get('tool') or '?'} "
            f"reason={row['reason']}"
        )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    paths = [resolve_target(args.target, codex_home(args))] if args.target else filtered_paths(args)
    rows: list[dict[str, Any]] = []
    for path in paths[: args.limit]:
        malformed = 0
        lines = 0
        if size_mb(path) <= args.max_mb or args.include_large or args.target:
            for line_no, obj, error, raw_line in iter_records(path):
                lines = line_no
                if error:
                    malformed += 1
        mode = None
        world_readable = False
        if os.name != "nt":
            try:
                mode = stat.S_IMODE(path.stat().st_mode)
                world_readable = bool(mode & stat.S_IROTH)
            except OSError:
                pass
        issues = []
        mb = size_mb(path)
        if mb > 400:
            issues.append("very-large-rollout")
        if malformed:
            issues.append("malformed-jsonl")
        if world_readable:
            issues.append("world-readable")
        if "archived_sessions" in path.parts:
            issues.append("archived")
        rows.append(
            {
                "path": str(path),
                "id": thread_id_from_path(path),
                "mtime": mtime_iso(path),
                "size_mb": round(mb, 2),
                "line_count": lines,
                "malformed_lines": malformed,
                "mode": oct(mode) if mode is not None else "",
                "issues": issues,
            }
        )
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            issues = ", ".join(row["issues"]) if row["issues"] else "ok"
            print(
                f"{row['path']} size={row['size_mb']}MB lines={row['line_count']} "
                f"mode={row['mode']} issues={issues}"
            )
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--codex-home", help="Override CODEX_HOME / ~/.codex")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of compact text")
    parser.add_argument("--max-chars", type=int, default=220, help="Max characters per snippet")


def add_scan_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scan-limit", type=int, default=500, help="Max recent rollout files to scan")
    parser.add_argument("--since-days", type=float, help="Only scan files modified within N days")
    parser.add_argument("--no-archived", action="store_true", help="Skip ~/.codex/archived_sessions")
    parser.add_argument("--max-mb", type=float, default=200, help="Skip content scan for larger files")
    parser.add_argument("--include-large", action="store_true", help="Scan files larger than --max-mb")


def add_scope_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--include-inherited",
        action="store_true",
        help="Include copied ancestor history in child rollout views",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_find = sub.add_parser("find", help="Rank likely relevant rollout files")
    add_common(p_find)
    add_scan_common(p_find)
    p_find.add_argument("--thread-id", help="Exact CODEX_THREAD_ID")
    p_find.add_argument("--query", default="", help="Text/project/issue key to rank against")
    p_find.add_argument("--cwd", default="", help="Prefer sessions whose cwd matches this path")
    p_find.add_argument("--limit", type=int, default=12)
    p_find.set_defaults(func=cmd_find)

    p_brief = sub.add_parser("brief", help="Summarize one rollout without raw output")
    add_common(p_brief)
    add_scope_option(p_brief)
    p_brief.add_argument("target", help="Rollout path or CODEX_THREAD_ID")
    p_brief.add_argument("--query", default="", help="Highlight why this file may match query")
    p_brief.set_defaults(func=cmd_brief)

    p_timeline = sub.add_parser("timeline", help="Compact event timeline for one rollout")
    add_common(p_timeline)
    add_scope_option(p_timeline)
    p_timeline.add_argument("target")
    p_timeline.add_argument("--limit", type=int, default=80)
    p_timeline.add_argument("--tail", type=int, default=0)
    p_timeline.set_defaults(func=cmd_timeline)

    p_messages = sub.add_parser("messages", help="Show redacted user/assistant messages")
    add_common(p_messages)
    add_scope_option(p_messages)
    p_messages.add_argument("target")
    p_messages.add_argument("--role", choices=["all", "user", "assistant"], default="all")
    p_messages.add_argument("--limit", type=int, default=60)
    p_messages.add_argument("--tail", type=int, default=0)
    p_messages.set_defaults(func=cmd_messages)

    p_commands = sub.add_parser("commands", help="Show redacted outer tool calls")
    add_common(p_commands)
    add_scope_option(p_commands)
    p_commands.add_argument("target")
    p_commands.add_argument("--tool", help="Filter by tool name, e.g. exec_command")
    p_commands.add_argument("--limit", type=int, default=80)
    p_commands.add_argument("--tail", type=int, default=0)
    p_commands.set_defaults(func=cmd_commands)

    p_audit = sub.add_parser(
        "audit", help="Measure lineage, messages, tool calls, failures, and repeats"
    )
    add_common(p_audit)
    add_scope_option(p_audit)
    p_audit.add_argument("target", help="Rollout path or CODEX_THREAD_ID")
    p_audit.set_defaults(func=cmd_audit)

    p_search = sub.add_parser("search", help="Search selected safe fields or redacted raw lines")
    add_common(p_search)
    add_scan_common(p_search)
    add_scope_option(p_search)
    p_search.add_argument("pattern")
    p_search.add_argument("target", nargs="?", help="Optional rollout path or CODEX_THREAD_ID")
    p_search.add_argument("--regex", action="store_true")
    p_search.add_argument("--case-sensitive", action="store_true")
    p_search.add_argument("--raw-line", action="store_true", help="Search redacted full JSONL lines")
    p_search.add_argument("--limit", type=int, default=40)
    p_search.set_defaults(func=cmd_search)

    p_doctor = sub.add_parser("doctor", help="Check malformed JSONL, large files, and loose perms")
    add_common(p_doctor)
    add_scan_common(p_doctor)
    p_doctor.add_argument("target", nargs="?")
    p_doctor.add_argument("--limit", type=int, default=80)
    p_doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows terminals may default to a legacy code page even though rollout
    # JSONL is UTF-8. StringIO and other redirected streams need no reconfigure.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
