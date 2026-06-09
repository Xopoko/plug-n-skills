#!/usr/bin/env python3
"""Token-efficient, safe-ish inspection helpers for Codex rollout JSONL logs.

The default output is deliberately compact and redacted. Use raw log files only
after this tool has narrowed the path/line range that actually matters.
"""

from __future__ import annotations

import argparse
import collections
import datetime as _dt
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
SECRET_REPLACEMENTS = [
    (
        re.compile(
            r"(?i)(authorization\s*[:=]\s*bearer\s+)([A-Za-z0-9._~+/=-]+)"
        ),
        r"\1[REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(api[_-]?key|token|secret|password|passwd|private[_-]?key|access[_-]?token)"
            r"(\s*[=:]\s*[\"']?)([^\"'\s,;\\]+)"
        ),
        r"\1\2[REDACTED]",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "sk-[REDACTED]"),
    (re.compile(r"\bghp_[A-Za-z0-9_]{20,}\b"), "ghp_[REDACTED]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "github_pat_[REDACTED]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"), "xox[REDACTED]"),
]


def codex_home(args: argparse.Namespace) -> Path:
    return Path(args.codex_home or os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def redact(value: Any) -> str:
    text = stringify(value)
    for pattern, repl in SECRET_REPLACEMENTS:
        text = pattern.sub(repl, text)
    text = LONG_TOKEN_RE.sub("[REDACTED-LONG-BLOB]", text)
    return text


def clip(text: Any, max_chars: int) -> str:
    value = re.sub(r"\s+", " ", redact(text)).strip()
    if max_chars > 0 and len(value) > max_chars:
        return value[: max_chars - 1].rstrip() + "…"
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


def payload(obj: dict[str, Any]) -> dict[str, Any]:
    value = obj.get("payload")
    return value if isinstance(value, dict) else {}


def message_text(obj: dict[str, Any]) -> tuple[str, str]:
    pl = payload(obj)
    top_type = obj.get("type")
    payload_type = pl.get("type")
    if top_type == "response_item" and payload_type == "message":
        return str(pl.get("role") or "message"), stringify(pl.get("content"))
    if top_type == "event_msg" and payload_type == "user_message":
        return "user", stringify(pl.get("message") or pl.get("text_elements"))
    if top_type == "event_msg" and payload_type == "agent_message":
        return "assistant", stringify(pl.get("message"))
    return "", ""


def function_call_summary(obj: dict[str, Any], max_chars: int) -> tuple[str, str]:
    pl = payload(obj)
    name = str(pl.get("name") or "")
    raw_args = pl.get("arguments")
    if raw_args is None:
        raw_args = pl.get("input")
    parsed: Any = None
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError:
            parsed = raw_args
    else:
        parsed = raw_args

    if isinstance(parsed, dict):
        if name == "exec_command":
            fields = []
            if parsed.get("cmd"):
                fields.append(f"cmd={parsed.get('cmd')}")
            if parsed.get("workdir"):
                fields.append(f"workdir={parsed.get('workdir')}")
            if parsed.get("sandbox_permissions"):
                fields.append(f"sandbox={parsed.get('sandbox_permissions')}")
            return name, clip(" | ".join(fields), max_chars)
        for key in ("cmd", "command", "query", "pattern", "path", "file", "ref_id"):
            if parsed.get(key):
                return name, clip(f"{key}={parsed.get(key)}", max_chars)
        return name, clip(parsed, max_chars)
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


def digest_session(path: Path, query: str = "", cwd: str = "", max_chars: int = 220) -> dict[str, Any]:
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
    line_count = 0
    session_id = thread_id_from_path(path)
    first_ts = ""
    last_ts = ""
    token_summary = ""
    score = 0
    reasons: set[str] = set()

    for line_no, obj, error, raw_line in iter_records(path):
        line_count = line_no
        if error:
            malformed += 1
            continue
        assert obj is not None
        first_ts = first_ts or str(obj.get("timestamp") or "")
        last_ts = str(obj.get("timestamp") or last_ts)
        top_type = str(obj.get("type") or "")
        pl = payload(obj)
        pl_type = str(pl.get("type") or "")
        counts[top_type] += 1
        if pl_type:
            payload_counts[pl_type] += 1

        if top_type == "session_meta":
            session_id = str(pl.get("id") or session_id)
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
            snippet = clip(text, max_chars)
            if role == "user":
                user_snippets.append(snippet)
            elif role in {"assistant", "assistant_final", "assistant_message"}:
                assistant_snippets.append(snippet)
            score += score_text(text, query_tokens, "message", query_hits, line_no)

        if top_type == "response_item" and pl_type in {"function_call", "custom_tool_call"}:
            tool, summary = function_call_summary(obj, max_chars=max_chars)
            if tool:
                tool_counts[tool] += 1
                score += score_text(tool, query_tokens, "tool", query_hits, line_no)
                if summary:
                    score += score_text(summary, query_tokens, "command", query_hits, line_no)
                if tool == "exec_command" and summary:
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
        "mtime": mtime_iso(path),
        "rollout_time": parse_rollout_timestamp(path),
        "size_mb": round(size_mb(path), 2),
        "line_count": line_count,
        "malformed_lines": malformed,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
        "cwd": unique_cwds[:5],
        "models": unique_models[:5],
        "record_types": dict(counts.most_common()),
        "payload_types": dict(payload_counts.most_common()),
        "tools": dict(tool_counts.most_common(12)),
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
                hits.append(f"{label}{suffix}:{token}")
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
    paths = filtered_paths(args)
    if args.thread_id:
        exact = [p for p in paths if args.thread_id in p.name]
        if exact:
            paths = exact
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
        digest = digest_session(path, query=args.query or args.thread_id or "", cwd=args.cwd or "", max_chars=args.max_chars)
        if args.thread_id and args.thread_id in (digest.get("id") or ""):
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
    digest = digest_session(path, query=args.query or "", cwd="", max_chars=args.max_chars)
    if args.json:
        print(json.dumps(digest, ensure_ascii=False, indent=2))
        return 0
    print(f"path: {digest['path']}")
    print(f"id: {digest.get('id') or '-'}")
    print(f"mtime: {digest.get('mtime')}  size: {digest.get('size_mb')}MB  lines: {digest.get('line_count')}")
    print(f"malformed_lines: {digest.get('malformed_lines')}")
    print(f"cwd: {'; '.join(digest.get('cwd') or []) or '-'}")
    print(f"models: {', '.join(digest.get('models') or []) or '-'}")
    print(f"record_types: {digest.get('record_types')}")
    print(f"payload_types: {digest.get('payload_types')}")
    print(f"tools: {digest.get('tools')}")
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
    events: list[dict[str, Any]] = []
    for line_no, obj, error, raw_line in iter_records(path):
        if error:
            events.append({"line": line_no, "kind": "malformed", "summary": error})
            continue
        assert obj is not None
        pl = payload(obj)
        top_type = str(obj.get("type") or "")
        pl_type = str(pl.get("type") or "")
        role, text = message_text(obj)
        if text:
            events.append(
                {
                    "line": line_no,
                    "time": obj.get("timestamp"),
                    "kind": role,
                    "summary": clip(text, args.max_chars),
                }
            )
        elif top_type == "response_item" and pl_type in {"function_call", "custom_tool_call"}:
            tool, summary = function_call_summary(obj, args.max_chars)
            events.append(
                {
                    "line": line_no,
                    "time": obj.get("timestamp"),
                    "kind": f"tool:{tool or '?'}",
                    "summary": summary,
                }
            )
        elif top_type == "event_msg" and pl_type in {
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
        elif top_type in {"turn_context", "session_meta", "compacted"}:
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
    rows: list[dict[str, Any]] = []
    for line_no, obj, error, raw_line in iter_records(path):
        if error or obj is None:
            continue
        role, text = message_text(obj)
        if not text:
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
    rows: list[dict[str, Any]] = []
    for line_no, obj, error, raw_line in iter_records(path):
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
        for line_no, obj, error, raw_line in iter_records(path):
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
    p_brief.add_argument("target", help="Rollout path or CODEX_THREAD_ID")
    p_brief.add_argument("--query", default="", help="Highlight why this file may match query")
    p_brief.set_defaults(func=cmd_brief)

    p_timeline = sub.add_parser("timeline", help="Compact event timeline for one rollout")
    add_common(p_timeline)
    p_timeline.add_argument("target")
    p_timeline.add_argument("--limit", type=int, default=80)
    p_timeline.add_argument("--tail", type=int, default=0)
    p_timeline.set_defaults(func=cmd_timeline)

    p_messages = sub.add_parser("messages", help="Show redacted user/assistant messages")
    add_common(p_messages)
    p_messages.add_argument("target")
    p_messages.add_argument("--role", choices=["all", "user", "assistant"], default="all")
    p_messages.add_argument("--limit", type=int, default=60)
    p_messages.add_argument("--tail", type=int, default=0)
    p_messages.set_defaults(func=cmd_messages)

    p_commands = sub.add_parser("commands", help="Show tool calls, especially exec_command")
    add_common(p_commands)
    p_commands.add_argument("target")
    p_commands.add_argument("--tool", help="Filter by tool name, e.g. exec_command")
    p_commands.add_argument("--limit", type=int, default=80)
    p_commands.add_argument("--tail", type=int, default=0)
    p_commands.set_defaults(func=cmd_commands)

    p_search = sub.add_parser("search", help="Search selected safe fields or redacted raw lines")
    add_common(p_search)
    add_scan_common(p_search)
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
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
