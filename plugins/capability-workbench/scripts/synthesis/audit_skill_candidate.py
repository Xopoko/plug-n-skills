#!/usr/bin/env python3
"""Static triage for candidate skill folders.

This script never executes candidate code. It reads text files, extracts coarse
metadata, and reports risk and quality indicators for manual review.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


TEXT_EXTENSIONS = {
    ".bash",
    ".cjs",
    ".conf",
    ".css",
    ".csv",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
    ".zsh",
}

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
}

PATTERNS = {
    "credentials_or_secrets": [
        r"\b[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PRIVATE_KEY|CREDENTIAL|COOKIE)[A-Z0-9_]*\b",
        r"\b[A-Z0-9_]*(?:AUTH_TOKEN|AUTHORIZATION)[A-Z0-9_]*\b",
        r"\b(?:keychain|password manager|pass\b|op item|get-secret)\b",
        r"\b(?:Authorization|Bearer|Basic)\b",
    ],
    "private_paths": [
        r"~/(?:\.ssh|\.aws|\.config|\.gnupg|Library/Application Support)",
        r"\b(?:id_rsa|known_hosts|aws_access_key|credentials|\.env)\b",
        r"\b(?:Cookies|Login Data|Local State|browser cookies)\b",
    ],
    "network_calls": [
        r"\b(?:curl|wget)\b",
        r"\b(?:fetch|axios|requests\.|urllib\.request|httpx\.|aiohttp\.|socket\.)\b",
        r"https?://",
    ],
    "telemetry_or_tracking": [
        r"\b(?:telemetry|analytics|tracking|segment|posthog|sentry|amplitude|mixpanel)\b",
        r"\b(?:usage metrics|install counts|phone home)\b",
    ],
    "unsafe_shell": [
        r"\b(?:eval|exec)\s*\(",
        r"\bos\.system\s*\(",
        r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\b",
        r"\bchild_process\.(?:exec|spawn|execSync|spawnSync)\b",
    ],
    "installers": [
        r"\b(?:npm|pnpm|yarn|pip|pip3|uv|brew|cargo|go)\s+(?:install|add|get)\b",
        r"\bcurl\b.+\|\s*(?:sh|bash|zsh)",
        r"\bwget\b.+\|\s*(?:sh|bash|zsh)",
    ],
    "obfuscation": [
        r"\bbase64\s+(?:-d|--decode)\b",
        r"\bfromCharCode\b",
        r"\batob\s*\(",
        r"\beval\s*\(",
        r"[A-Za-z0-9+/]{120,}={0,2}",
    ],
    "broad_file_writes_or_deletes": [
        r"\brm\s+-rf\s+(?:/|~|\$HOME|\*)",
        r"\b(?:unlink|rmdir|shutil\.rmtree|fs\.rmSync)\b",
        r">\s*/(?:etc|usr|bin|sbin|var|System|Library)/",
    ],
    "paid_or_api_services": [
        r"\b(?:OpenAI|Anthropic|Claude|Gemini|Stability|Replicate|Runway|Midjourney|Tavily|SerpAPI|Pinecone)\b",
        r"\b(?:AWS|Azure|Google Cloud|GCP|Firebase|Supabase|Convex)\b",
        r"\b(?:paid plan|subscription|billing|credit card|API key required)\b",
    ],
    "quality_mechanisms": [
        r"\b(?:validate|validator|schema|strict json|typed|contract|dry[- ]run)\b",
        r"\b(?:test|pytest|vitest|playwright|snapshot|golden|fixture)\b",
        r"\b(?:retry|backoff|timeout|idempotent|checksum|hash|cache)\b",
        r"\b(?:progressive disclosure|context budget|deterministic|lint)\b",
    ],
    "pipeline_indicators": [
        r"\b(?:workflow|pipeline|stage|step [0-9]|phase|inputs?|outputs?)\b",
        r"\b(?:preprocess|postprocess|normalize|render|export|verify)\b",
    ],
}


@dataclass
class Match:
    file: str
    line: int
    text: str
    context: str
    risk_class: str


@dataclass
class CandidateAudit:
    path: str
    exists: bool
    skill_file: str | None = None
    frontmatter: dict[str, object] = field(default_factory=dict)
    files_total: int = 0
    text_files_reviewed: int = 0
    binary_or_skipped_files: list[str] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    declared_env: list[str] = field(default_factory=list)
    declared_bins: list[str] = field(default_factory=list)
    indicators: dict[str, list[Match]] = field(default_factory=dict)
    risk_summary: dict[str, object] = field(default_factory=dict)
    risk_level: str = "unknown"
    verdict_hint: str = "manual_review_required"
    notes: list[str] = field(default_factory=list)


def is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    mime, _ = mimetypes.guess_type(str(path))
    return bool(mime and mime.startswith("text/"))


def iter_files(root: Path) -> Iterable[Path]:
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(files):
            yield Path(current_root) / name


def read_text(path: Path, max_bytes: int) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > max_bytes:
        data = data[:max_bytes]
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            return None


def extract_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return {}, text
    raw = match.group(1)
    parsed: dict[str, object] = {"_raw": raw}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top:
            current_key = top.group(1)
            value = top.group(2).strip().strip("\"'")
            parsed[current_key] = value
            continue
        item = re.match(r"^\s*-\s*([A-Za-z0-9_.-]+)\s*$", line)
        if item and current_key:
            existing = parsed.get(current_key)
            if not isinstance(existing, list):
                existing = []
                parsed[current_key] = existing
            existing.append(item.group(1))
    return parsed, text[match.end() :]


def collect_declared_requirements(frontmatter_raw: str) -> tuple[list[str], list[str]]:
    env = sorted(set(re.findall(r"\b[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|AUTH|CREDENTIAL|PRIVATE)[A-Z0-9_]*\b", frontmatter_raw)))
    bins: set[str] = set()
    for block_name in ("bins", "anyBins"):
        block_match = re.search(rf"{block_name}\s*:\s*(?:\[(.*?)\]|((?:\n\s*-\s*[A-Za-z0-9_.-]+)+))", frontmatter_raw)
        if block_match:
            inline = block_match.group(1) or ""
            listed = block_match.group(2) or ""
            bins.update(x.strip().strip("\"'") for x in inline.split(",") if x.strip())
            bins.update(re.findall(r"-\s*([A-Za-z0-9_.-]+)", listed))
    return env, sorted(bins)


CODE_EXTENSIONS = {".bash", ".cjs", ".js", ".jsx", ".mjs", ".py", ".rb", ".rs", ".sh", ".ts", ".tsx", ".zsh"}
SHELL_LANGS = {"bash", "console", "fish", "sh", "shell", "terminal", "zsh"}
CODE_LANGS = {"js", "javascript", "json", "jsx", "python", "rb", "rs", "rust", "ts", "tsx", "typescript"}
ADVISORY_RE = re.compile(
    r"\b(?:avoid|blocked|caution|do not|don't|forbid|hidden|never|no credentials|no installs|no secrets|no telemetry|reject|rejected|risk|unsafe|warn|warning|without explicit)\b",
    re.IGNORECASE,
)


def frontmatter_line_count(text: str) -> int:
    if not text.startswith("---"):
        return 0
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return 0
    return text[: match.end()].count("\n")


def classify_line_context(relative: str, line: str, line_no: int, in_fence: bool, fence_lang: str, fm_lines: int) -> str:
    suffix = Path(relative).suffix.lower()
    stripped = line.strip()
    if line_no <= fm_lines:
        return "metadata"
    if suffix in CODE_EXTENSIONS:
        return "code"
    if in_fence:
        if fence_lang in SHELL_LANGS:
            return "command_example"
        if fence_lang in CODE_LANGS:
            return "code_block"
        return "fenced_example"
    if ADVISORY_RE.search(stripped):
        return "advisory"
    return "prose"


def risk_class_for(category: str, context: str, line: str) -> str:
    stripped = line.strip()
    if re.match(r"^[rubf]*[\"'].*(?:\\b|\(\?:|\[[A-Za-z0-9_])", stripped):
        return "mention"
    if context == "advisory" or ADVISORY_RE.search(stripped):
        return "advisory"
    if category == "quality_mechanisms" or category == "pipeline_indicators":
        return "positive_signal"
    if context in {"code", "command_example", "metadata", "code_block"}:
        return "active"
    if re.search(r"\b(?:curl|wget)\b.+\|\s*(?:sh|bash|zsh)", stripped, re.IGNORECASE):
        return "active"
    return "mention"


def scan_text(relative: str, text: str, max_matches: int) -> dict[str, list[Match]]:
    result: dict[str, list[Match]] = {key: [] for key in PATTERNS}
    lines = text.splitlines()
    fm_lines = frontmatter_line_count(text)
    in_fence = False
    fence_lang = ""
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        context = classify_line_context(relative, line, index, in_fence, fence_lang, fm_lines)
        for key, patterns in PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    if len(result[key]) < max_matches:
                        result[key].append(
                            Match(relative, index, stripped[:240], context, risk_class_for(key, context, line))
                        )
                    break
        fence_match = re.match(r"^```+([A-Za-z0-9_-]+)?", stripped)
        if fence_match:
            if in_fence:
                in_fence = False
                fence_lang = ""
            else:
                in_fence = True
                fence_lang = (fence_match.group(1) or "").lower()
    return {k: v for k, v in result.items() if v}


def merge_indicators(target: dict[str, list[Match]], source: dict[str, list[Match]], max_matches: int) -> None:
    for key, matches in source.items():
        existing = target.setdefault(key, [])
        slots = max(0, max_matches - len(existing))
        existing.extend(matches[:slots])


def summarize_risk(indicators: dict[str, list[Match]]) -> dict[str, object]:
    summary: dict[str, object] = {
        "active_categories": [],
        "advisory_categories": [],
        "mention_categories": [],
        "positive_signal_categories": [],
        "active_match_count": 0,
        "advisory_match_count": 0,
        "mention_match_count": 0,
    }
    active_categories: set[str] = set()
    advisory_categories: set[str] = set()
    mention_categories: set[str] = set()
    positive_categories: set[str] = set()
    for category, matches in indicators.items():
        for match in matches:
            if match.risk_class == "active":
                active_categories.add(category)
                summary["active_match_count"] = int(summary["active_match_count"]) + 1
            elif match.risk_class == "advisory":
                advisory_categories.add(category)
                summary["advisory_match_count"] = int(summary["advisory_match_count"]) + 1
            elif match.risk_class == "positive_signal":
                positive_categories.add(category)
            else:
                mention_categories.add(category)
                summary["mention_match_count"] = int(summary["mention_match_count"]) + 1
    summary["active_categories"] = sorted(active_categories)
    summary["advisory_categories"] = sorted(advisory_categories)
    summary["mention_categories"] = sorted(mention_categories)
    summary["positive_signal_categories"] = sorted(positive_categories)
    return summary


def classify(indicators: dict[str, list[Match]]) -> tuple[str, str, dict[str, object]]:
    summary = summarize_risk(indicators)
    active = set(summary["active_categories"])
    advisory = set(summary["advisory_categories"])
    mentions = set(summary["mention_categories"])

    high_active = {"obfuscation", "telemetry_or_tracking"}
    medium_active = {
        "credentials_or_secrets",
        "installers",
        "network_calls",
        "paid_or_api_services",
        "private_paths",
        "unsafe_shell",
    }

    destructive_matches = [
        match
        for match in indicators.get("broad_file_writes_or_deletes", [])
        if match.risk_class == "active" and re.search(r"rm\s+-rf\s+(?:/|~|\$HOME|\*)|/(?:etc|usr|bin|sbin|var|System|Library)/", match.text)
    ]

    if active & high_active or destructive_matches:
        return "high", "reject_or_strongly_adapt", summary
    if active & medium_active:
        return "medium", "manual_review_required", summary
    if advisory or mentions:
        return "low", "review_mentions_but_no_active_risk_detected", summary
    return "low", "eligible_for_manual_distillation", summary


def audit_candidate(path: Path, max_file_bytes: int, max_matches: int) -> CandidateAudit:
    audit = CandidateAudit(path=str(path), exists=path.exists())
    if not path.exists():
        audit.notes.append("Path does not exist.")
        return audit
    if path.is_file():
        root = path.parent
        files = [path]
    else:
        root = path
        files = list(iter_files(root))

    audit.files_total = len(files)
    skill_candidates = [p for p in files if p.name in {"SKILL.md", "skill.md", "skills.md"}]
    if skill_candidates:
        audit.skill_file = str(skill_candidates[0].relative_to(root))
    else:
        audit.notes.append("No SKILL.md, skill.md, or skills.md found.")

    for file_path in files:
        try:
            relative = str(file_path.relative_to(root))
        except ValueError:
            relative = file_path.name

        parts = set(file_path.parts)
        if "scripts" in parts or file_path.suffix.lower() in {".py", ".sh", ".js", ".ts", ".rb"}:
            audit.scripts.append(relative)
        if "references" in parts or "reference" in parts:
            audit.references.append(relative)
        if "assets" in parts:
            audit.assets.append(relative)

        if not is_probably_text(file_path):
            audit.binary_or_skipped_files.append(relative)
            continue

        text = read_text(file_path, max_file_bytes)
        if text is None:
            audit.binary_or_skipped_files.append(relative)
            continue

        audit.text_files_reviewed += 1
        if relative == audit.skill_file:
            frontmatter, _ = extract_frontmatter(text)
            audit.frontmatter = frontmatter
            raw = str(frontmatter.get("_raw", ""))
            audit.declared_env, audit.declared_bins = collect_declared_requirements(raw)

        merge_indicators(audit.indicators, scan_text(relative, text, max_matches), max_matches)

    audit.scripts = sorted(set(audit.scripts))
    audit.references = sorted(set(audit.references))
    audit.assets = sorted(set(audit.assets))
    audit.binary_or_skipped_files = sorted(set(audit.binary_or_skipped_files))
    audit.risk_level, audit.verdict_hint, audit.risk_summary = classify(audit.indicators)
    return audit


def to_jsonable(audit: CandidateAudit) -> dict[str, object]:
    data = audit.__dict__.copy()
    data["indicators"] = {
        key: [match.__dict__ for match in matches]
        for key, matches in audit.indicators.items()
    }
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Statically audit candidate skill folders.")
    parser.add_argument("paths", nargs="+", help="Candidate skill folders or files to scan.")
    parser.add_argument("--output", "-o", help="Write JSON output to this path.")
    parser.add_argument("--max-file-bytes", type=int, default=500_000, help="Maximum bytes read per text file.")
    parser.add_argument("--max-matches", type=int, default=25, help="Maximum matches retained per indicator category.")
    args = parser.parse_args()

    audits = [
        to_jsonable(audit_candidate(Path(raw).expanduser(), args.max_file_bytes, args.max_matches))
        for raw in args.paths
    ]
    payload = {"schema": "skill-synthesizer.candidate-audits.v1", "candidates": audits}
    rendered = json.dumps(payload, indent=2, sort_keys=True)

    if args.output:
        Path(args.output).expanduser().write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
