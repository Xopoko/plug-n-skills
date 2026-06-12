#!/usr/bin/env python3
"""Static triage for candidate skill folders.

This script never executes candidate code. It reads text files, extracts coarse
metadata, and reports risk and quality indicators for manual review.
"""

# Portions of the detection patterns in this file (several risk-category regular
# expressions) are adapted from NVIDIA SkillSpector
# (https://github.com/NVIDIA/SkillSpector), licensed under the Apache License,
# Version 2.0: http://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
#
# Changes from the original (Apache-2.0 section 4(b) notice of modification):
# multi-line / re.DOTALL / AST / taint-flow patterns were degraded to single-line
# case-insensitive regexes; the zero-width-character class was narrowed; the
# setuid chmod patterns were tightened; POST/GET tokens were scoped case-sensitive;
# per-pattern confidences and severity values were dropped and remapped onto this
# script's risk tiers; Unicode/codepoint analysis was partially ported (narrowed
# to ASCII-escaped bidi/invisible char-classes plus a small Cyrillic/Greek
# confusables-in-identifier check via unicodedata); the static-runner, OSV/CVE
# network lookups, YARA rules, and LLM-based analyzers were not ported.
#
# This file as a whole is distributed under the MIT license of this repository.
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import unicodedata
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
        r"\bfor\s+\w+\s*,\s*\w+\s+in\s+os\.environ\.items\s*\(\s*\)",
        r"\bObject\.keys\s*\(\s*process\.env\s*\)",
        r"\benv\s*\|\s*grep\s+(?:-i\s+)?(?:key|secret|token|password)",
        r"\bos\.environ\.copy\s*\(\s*\)",
    ],
    "private_paths": [
        r"~/(?:\.ssh|\.aws|\.config|\.gnupg|Library/Application Support)",
        r"\b(?:id_rsa|known_hosts|aws_access_key|credentials|\.env)\b",
        r"\b(?:Cookies|Login Data|Local State|browser cookies)\b",
        r"/etc/(?:passwd|shadow)\b",
        r"~?/?\.(?:kube/config|docker/config\.json|npmrc|git-credentials|netrc|azure/)",
        r"\b(?:kubeconfig|application_default_credentials\.json|accessTokens\.json)\b",
        r"\b(?:id_ed25519|id_ecdsa|id_dsa|authorized_keys)\b",
        r"glob\s*\.\s*glob\s*\([^)]*(?:\.env|\.ssh|\.aws|\.config|credentials)",
        r"os\s*\.\s*(?:walk|listdir|scandir)\s*\([^)]*(?:\.ssh|\.aws|\.config|\.gnupg|/Users|/home)",
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
        r"\bsudo\s+(?!-v\b|-l\b|--version\b|--list\b)\S",
        r"\b(?:doas|pkexec)\s+\S",
        r"\bchmod\s+(?:[4567][0-7]{3})\b",
        r"chmod\s+[ugo]*[-+=]s\b",
    ],
    "installers": [
        r"\b(?:npm|pnpm|yarn|pip|pip3|uv|brew|cargo|go)\s+(?:install|add|get)\b",
        r"\bcurl\b.+\|\s*(?:sh|bash|zsh)",
        r"\bwget\b.+\|\s*(?:sh|bash|zsh)",
        r"\b(?:curl|wget)\b[^|]*\|\s*(?:sudo\s+)?(?:python|python3|node|ruby|perl)\b",
        r"\bcurl\b[^&]*-o\s+\S+\s*&&\s*(?:sudo\s+)?(?:ba)?sh\b",
    ],
    "obfuscation": [
        r"\bbase64\s+(?:-d|--decode)\b",
        r"\bfromCharCode\b",
        r"\batob\s*\(",
        r"\beval\s*\(",
        r"[A-Za-z0-9+/]{120,}={0,2}",
        r"\bmarshal\.loads\s*\(",
        r"\bexec\s*\(\s*(?:base64\.)?b64decode\s*\(",
        r"\bexec\s*\(\s*bytes\.fromhex\s*\(",
        r"\b__import__\s*\(\s*['\"]os['\"]\s*\)\s*\.\s*system",
        r"_0x[a-f0-9]{4,}\s*\(",
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
    "prompt_injection": [
        r"ignore\s+(?:all\s+)?previous\s+instructions?",
        r"ignore\s+(?:all\s+)?(?:safety|security)\s+(?:rules?|constraints?|guidelines?)",
        r"override\s+(?:safety|security|system)\s+(?:prompt|instructions?|rules?)",
        r"disregard\s+(?:all\s+)?(?:previous|safety|security)",
        r"forget\s+(?:all\s+)?(?:previous|your)\s+instructions?",
        r"you\s+are\s+now\s+(?:in\s+)?(?:jailbreak|unrestricted|unfiltered)\s+mode",
    ],
    "system_prompt_leakage": [
        r"(?:verbatim|exactly|word\s+for\s+word)\s+(?:repeat|output|print)\s+(?:the\s+)?(?:your\s+)?(?:system\s+)?(?:prompt|instructions?)",
        r"(?:share|disclose|leak|give\s+me)\s+(?:your\s+)?(?:internal|hidden|system|secret)\s+(?:prompt|instructions?|rules?|config)",
        r"(?:repeat|recite|reproduce)\s+(?:everything|all|the\s+text)\s+(?:above|before|prior|preceding)",
        r"(?:encode|encrypt|rot13|base64|reverse)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions?|rules?)",
        r"(?:send|post|upload|transmit)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions?|rules?)\s+(?:to|via)\s+(?:https?://|external|remote|webhook|api|server)",
        r"(?:write|save|store|log|dump)\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions?|rules?)\s+(?:to|into|in)\s+(?:a\s+)?(?:file|disk|log|database|storage)",
    ],
    "instruction_exfiltration": [
        r"(?:send|transmit|upload|post|forward)\s+(?:the\s+)?(?:conversation|context|chat|history)\s+to",
        r"(?:silently|quietly|secretly|covertly)\s+(?:send|transmit|log|record)",
        r"(?:copy|extract|collect)\s+(?:the\s+)?(?:conversation|context|session)\s+(?:and\s+)?(?:send|upload|transmit)",
        r"include\s+(?:the\s+)?(?:full\s+)?(?:conversation|context|history)\s+in\s+(?:the\s+)?(?:request|payload|body)",
        r"(?:export|dump|save)\s+(?:the\s+)?(?:conversation|chat|messages?)\s+to\s+(?:external|remote|server)",
        r"log\s+(?:all\s+)?(?:user\s+)?(?:input|messages?|queries?|prompts?)\s+to\s+(?:external|remote|server)",
    ],
    "memory_poisoning": [
        r"(?:clear|reset|wipe|erase|delete|purge)\s+(?:your\s+)?(?:memory|context|state|history|conversation)",
        r"(?:forget|discard|drop|abandon)\s+(?:all\s+)?(?:previous|prior|earlier|past)\s+(?:instructions?|context|conversation|messages?|rules?)",
        r"(?:you\s+are\s+no\s+longer|stop\s+being|cease\s+to\s+be)\s+(?:a\s+)?(?:\w+\s+){0,3}(?:assistant|helper|agent|bot)",
        r"(?:inject|insert|plant)\s+(?:false|fake|fabricated|malicious)\s+(?:memories?|information|context|data|history)",
        r"(?:poison|contaminate|corrupt|taint)\s+(?:your\s+)?(?:memory|context|state|knowledge|training)",
        r"(?:overwrite|replace|substitute|swap)\s+(?:your\s+)?(?:memory|context|state|instructions?|rules?)",
    ],
    "self_modification": [
        r"open\s*\(\s*__file__\s*,\s*['\"]w",
        r"(?:Path|pathlib)\s*\(\s*__file__\s*\)\s*\.\s*write_text",
        r"self[_-]?(?:modify|rewrite|patch|evolve)",
        r"(?:modify|edit|change|rewrite|alter)\s+(?:your\s+own|its\s+own)\s+(?:code|source|script|instructions?|rules?)",
        r"(?:disable|remove|delete|bypass)\s+(?:the\s+)?(?:safety|security|guard|protection|constraint)\s+(?:check|rule|mechanism|feature)",
        r"open\s*\(\s*['\"]skill\.md['\"][^)]*['\"][wa]",
    ],
    "excessive_agency": [
        r"(?:skip|bypass|disable)\s+(?:user\s+)?(?:confirmation|approval|consent|verification)\b",
        r"\bauto[_-]?(?:approve|confirm|execute|deploy)\s+(?:all|every|any|each)\b",
        r"(?:auto(?:matically)?|autonomously)\s+(?:execute|run|perform|delete|remove|modify|send|deploy)",
        r"without\s+(?:asking|confirmation|approval|consent)",
        r"(?:proceed|continue|execute)\s+without\s+(?:waiting|asking)\s+(?:for\s+)?(?:user|human|permission)",
    ],
    "hidden_instructions": [
        r"<!--.*?(?:system|instructions?|ignore|(?-i:POST|GET)|send|transmit).*?-->",
        r"\[//\]:\s*#\s*\(.*?(?:system|instructions?|ignore|(?-i:POST|GET)|send|transmit).*?\)",
        r"[\u200b\u2060]",
        r"data:text/[^;,]+;base64,[A-Za-z0-9+/=]{50,}",
    ],
    "harmful_content": [
        r"add\s+(?:a\s+)?(?:dash|pinch|bit|drop|amount)\s+of\s+(?:cyanide|arsenic|ricin|botulinum|strychnine|thallium|polonium|sarin|anthrax|hemlock|oleander|aconite)",
        r"mix\s+bleach\s+(?:and|with)\s+ammonia",
        r"mix\s+ammonia\s+(?:and|with)\s+bleach",
        r"(?:drink|consume|ingest)\s+(?:the\s+)?(?:bleach|antifreeze|drain\s+cleaner)",
        r"(?:instructions?\s+(?:for|to|on)\s+)?(?:make|build|create)\s+(?:an?\s+)?(?:bomb|explosive|weapon)",
        r"(?:how\s+to\s+)?(?:poison|kill|murder)\s+(?:someone|a\s+person|people)",
    ],
    "unsafe_defaults": [
        r"\bverify\s*=\s*False\b",
        r"(?:ssl|tls)[._]?verify\s*=\s*(?:False|0|off|no|disable)",
        r"\bNODE_TLS_REJECT_UNAUTHORIZED\s*=\s*['\"]?0['\"]?",
        r"\b(?:curl|wget)\b[^|]*(?:--insecure|--no-check-certificate|\s-k\b)",
        r"(?:disable|skip|ignore|bypass)[_-](?:security|auth|authentication|validation|sanitization|encoding|escaping)\b",
        r"\bchmod\s+(?:-R\s+)?(?:(?:0?o?)?(?:777|666)|a\+rwx)\b",
    ],
    # Authored as ASCII \uXXXX escapes, never literal codepoints: the regex must
    # match the real characters in scanned content without matching its own
    # ASCII source line (the file stays pure ASCII).
    "unicode_deception": [
        r"[\u202a-\u202e\u2066-\u2069]",
        r"[\u00ad\u034f\u2061-\u2064]",
    ],
    "session_persistence": [
        r"\bcrontab\s+(?:-[el]|.*?>>?\s*/)",
        r"\b(?:add|create|install|register)\s+(?:a\s+)?(?:cron\s+)?(?:job|task|entry)\s+(?:for|to|that)\b",
        r"(?:>>?|append|write|install)\s+(?:to\s+)?(?:~/)?\.(?:bashrc|zshrc|profile|bash_profile|login|cshrc)\b",
        r"\b(?:systemctl|launchctl)\s+(?:enable|load|install|register|bootstrap)\b",
        r"\b(?:systemd|launchd|init\.d)\b.*\b(?:enable|install|register|create)\b",
        r"\b(?:create|install|register|add)\s+(?:a\s+)?(?:systemd\s+)?(?:service|daemon|agent)\s+(?:file|unit)\b",
        r"\b(?:nohup|disown|setsid)\b",
        r"\b(?:defaults\s+write|launchctl\s+load)\b",
        r"\b(?:LaunchAgents|LaunchDaemons)\b",
        r"(?:persist|maintain|keep|preserve)\s+(?:the\s+)?(?:state|data|context|session)\s+(?:across|between|through)\s+(?:sessions?|restarts?|reboots?|invocations?)",
    ],
    "output_handling": [
        r"\b(?:exec|eval)\s*\(\s*(?:response|output|result|answer|completion|reply|generated)",
        r"\bsubprocess\.\w+\s*\([^)]*\b(?:response|output|result|answer|completion)\b",
        r"\bos\.system\s*\(\s*[^)]*\b(?:response|output|result|answer|completion)\b",
        r"\b(?:innerHTML|outerHTML)\s*=\s*[^=].*\b(?:response|output|result|answer|completion)\b",
        r"\bdocument\.write\s*\(\s*[^)]*\b(?:response|output|result|answer|completion)\b",
        r"\bdangerouslySetInnerHTML\s*=\s*\{",
        r"\bf['\"](?:SELECT|INSERT|UPDATE|DELETE)\b[^'\"]*\{\s*(?:response|output|result)\b",
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

# Instruction-attack categories: the skill's own prose is the attack surface, so
# plain prose counts as active. unsafe_defaults stays out: it is a code/config
# category whose prose mentions must remain inert.
PROSE_ATTACK_CATEGORIES = {
    "excessive_agency",
    "harmful_content",
    "hidden_instructions",
    "instruction_exfiltration",
    "memory_poisoning",
    "prompt_injection",
    "self_modification",
    "system_prompt_leakage",
    "unicode_deception",
}

# Cyrillic/Greek glyphs that look like Latin letters. Applied ONLY to the parsed
# frontmatter name (an identifier), never to prose, mirroring SkillSpector's
# is_identifier scoping so legitimate non-Latin documentation does not trip it.
CONFUSABLE_TO_LATIN = {
    0x0430: "a", 0x0435: "e", 0x043E: "o", 0x0440: "p", 0x0441: "c", 0x0445: "x",
    0x0443: "y", 0x0456: "i", 0x0458: "j", 0x0455: "s", 0x051B: "q",
    0x0410: "A", 0x0412: "B", 0x0415: "E", 0x041A: "K", 0x041C: "M", 0x041D: "H",
    0x041E: "O", 0x0420: "P", 0x0421: "C", 0x0422: "T", 0x0425: "X", 0x0405: "S",
    0x0406: "I", 0x0408: "J",
    0x03B1: "a", 0x03BF: "o", 0x03C1: "p", 0x03BD: "v", 0x0391: "A", 0x0392: "B",
    0x0395: "E", 0x0397: "H", 0x0399: "I", 0x039A: "K", 0x039C: "M", 0x039D: "N",
    0x039F: "O", 0x03A1: "P", 0x03A4: "T", 0x03A7: "X", 0x0396: "Z",
}


def detect_name_confusables(name: str) -> list["Match"]:
    """Flag Cyrillic/Greek Latin-lookalikes in a skill name identifier.

    A mixed Latin+confusable name is a deliberate typosquat (active); an
    all-non-Latin name still surfaces as a milder signal (mention).
    """
    out: list[Match] = []
    if not name:
        return out
    has_latin = any("a" <= c.lower() <= "z" for c in name)
    for ch in name:
        cp = ord(ch)
        if cp in CONFUSABLE_TO_LATIN:
            try:
                uname = unicodedata.name(ch)
            except ValueError:
                uname = "UNNAMED"
            out.append(
                Match(
                    "<frontmatter:name>",
                    0,
                    f"name contains {uname} (U+{cp:04X}) lookalike for '{CONFUSABLE_TO_LATIN[cp]}'",
                    "metadata",
                    "active" if has_latin else "mention",
                )
            )
    return out


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
    if category in PROSE_ATTACK_CATEGORIES and context == "prose":
        return "active"
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

    high_active = {
        "harmful_content",
        "hidden_instructions",
        "instruction_exfiltration",
        "obfuscation",
        "prompt_injection",
        "self_modification",
        "telemetry_or_tracking",
        "unicode_deception",
    }
    medium_active = {
        "credentials_or_secrets",
        "excessive_agency",
        "installers",
        "memory_poisoning",
        "network_calls",
        "output_handling",
        "paid_or_api_services",
        "private_paths",
        "session_persistence",
        "system_prompt_leakage",
        "unsafe_defaults",
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
            name_val = frontmatter.get("name")
            if isinstance(name_val, str):
                confusables = detect_name_confusables(name_val)
                if confusables:
                    audit.indicators.setdefault("unicode_deception", []).extend(confusables[:max_matches])

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
