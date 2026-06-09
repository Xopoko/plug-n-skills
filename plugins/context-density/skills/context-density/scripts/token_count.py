#!/usr/bin/env python3
"""Count tokens for files or directories with tiktoken when available."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

TEXT_SUFFIXES = {
    ".adoc",
    ".css",
    ".go",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".kt",
    ".md",
    ".mdx",
    ".py",
    ".rb",
    ".rs",
    ".rst",
    ".sh",
    ".swift",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".build", "dist", "build"}


def load_encoder(name: str):
    try:
        import tiktoken  # type: ignore

        return tiktoken.get_encoding(name), "exact"
    except Exception:
        return None, "approx"


def iter_files(paths: list[str]) -> list[Path]:
    files: set[Path] = set()
    for raw in paths:
        path = Path(raw).expanduser()
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and not any(part in SKIP_DIRS for part in child.parts):
                    files.add(child)
        elif path.is_file():
            files.add(path)
        else:
            print(f"warning: skipped missing path: {path}", file=sys.stderr)
    return sorted(
        p for p in files if p.suffix.lower() in TEXT_SUFFIXES or not p.suffix
    )


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            print(f"warning: skipped unreadable file {path}: {exc}", file=sys.stderr)
            return None
    except Exception as exc:
        print(f"warning: skipped unreadable file {path}: {exc}", file=sys.stderr)
        return None


def count_text(text: str, encoder) -> int:
    if encoder is not None:
        return len(encoder.encode(text))
    return int(math.ceil(len(text) / 4))


def count_paths(paths: list[str], encoding: str) -> tuple[dict, list[dict]]:
    encoder, mode = load_encoder(encoding)
    rows = []
    source_files = iter_files(paths) if paths else []
    if source_files:
        for path in source_files:
            text = read_text(path)
            if text is None:
                continue
            rows.append(
                {
                    "path": str(path),
                    "tokens": count_text(text, encoder),
                    "chars": len(text),
                    "lines": text.count("\n") + (1 if text else 0),
                }
            )
    else:
        text = sys.stdin.read()
        rows.append(
            {
                "path": "<stdin>",
                "tokens": count_text(text, encoder),
                "chars": len(text),
                "lines": text.count("\n") + (1 if text else 0),
            }
        )
    rows.sort(key=lambda row: row["tokens"], reverse=True)
    total = {
        "mode": mode,
        "encoding": encoding if mode == "exact" else None,
        "files": len(rows),
        "tokens": sum(row["tokens"] for row in rows),
        "chars": sum(row["chars"] for row in rows),
        "lines": sum(row["lines"] for row in rows),
    }
    return total, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Count tokens in text files.")
    parser.add_argument("paths", nargs="*", help="Files or directories to measure.")
    parser.add_argument("--encoding", default="o200k_base", help="tiktoken encoding name.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    parser.add_argument("--top", type=int, default=0, help="Show only top N files.")
    args = parser.parse_args()

    total, rows = count_paths(args.paths, args.encoding)
    shown = rows[: args.top] if args.top else rows
    if args.json:
        print(json.dumps({"total": total, "files": shown}, indent=2, ensure_ascii=False))
        return 0

    suffix = "" if total["mode"] == "exact" else " (approx; install tiktoken for exact counts)"
    print(f"total tokens: {total['tokens']} across {total['files']} file(s){suffix}")
    print(f"total chars: {total['chars']}  total lines: {total['lines']}")
    if shown:
        print()
        width = max(len(row["path"]) for row in shown)
        for row in shown:
            print(f"{row['path']:<{width}}  {row['tokens']:>8} tokens  {row['lines']:>6} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
