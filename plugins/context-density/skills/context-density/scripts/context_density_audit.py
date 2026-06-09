#!/usr/bin/env python3
"""Audit token hotspots and prompt-contract risks in deterministic source files."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from token_count import count_paths, iter_files, read_text

CONTRACT_TERMS = re.compile(
    r"(assistant|completion|llm|model|model_output|message|response|answer|reason|summary)",
    re.IGNORECASE,
)
PROSE_PARSERS = [
    (re.compile(r"\.split\s*\("), "split_over_text"),
    (re.compile(r"\.(includes|startsWith|endsWith|contains)\s*\("), "substring_match"),
    (re.compile(r"\bre\.(search|match|findall|split)\s*\("), "regex_parse"),
    (re.compile(r"\b(regex|RegExp)\s*\("), "regex_parse"),
]
CONTEXT_RISK_PATTERNS = [
    (re.compile(r"\b(latest changes|changelog|change log|task diary|old notes|misc)\b", re.IGNORECASE), "history_in_context", "medium"),
    (re.compile(r"\b(raw payload|terminal log|transcript|full output)\b", re.IGNORECASE), "evidence_in_context", "medium"),
    (re.compile(r"\bTODO\b|\bTBD\b"), "unfinished_context", "low"),
]
REQUEST_TRIGGER_RE = re.compile(
    r"\b(when|if)\s+the\s+user\s+(asks?|requests?|says?|wants?|needs?|names?)\b|"
    r"\buser[- ](?:request|wording|phrase|prompt)s?\b",
    re.IGNORECASE,
)
TRIGGER_SURFACE_RE = re.compile(
    r"\b(description|trigger|use when|use for|route|routing|invoke|load this skill)\b",
    re.IGNORECASE,
)
CONSENT_OR_SCOPE_RE = re.compile(
    r"\b(consent|approval|permission|install|global|cache|credential|secret|destructive|target binding|named target|explicit)\b",
    re.IGNORECASE,
)
ANTI_BRITTLE_TRIGGER_RE = re.compile(
    r"\b(avoid|do not|don't|not only|not just|instead of|rather than|literal|exact user wording only)\b",
    re.IGNORECASE,
)
LONG_CONTEXT_TERMS = re.compile(
    r"\b(long[- ]context|large context|context window|window size|128k|200k|1m token|million token)\b",
    re.IGNORECASE,
)
CAPACITY_CONFIDENCE_TERMS = re.compile(
    r"\b(enough|guarantee[sd]?|safe|reliable|solves?|no need|always|just include|can hold|will remember)\b",
    re.IGNORECASE,
)
PLACEMENT_OR_VALIDATION_TERMS = re.compile(
    r"\b(position|placement|middle|anchor|source order|validation|validator|task success|benchmark|recall|evidence|source_ref|recovery)\b",
    re.IGNORECASE,
)
LONG_CONTEXT_SUCCESS_TERMS = re.compile(
    r"\b(use|uses|using|pack|packed|packing|place|placed|include|includes|fit|fits|handle|handles|support|supports|optimi[sz]e)\b",
    re.IGNORECASE,
)
HIGH_AUTHORITY_TERMS = re.compile(
    r"\b(must|must not|required|never|do not|don't|preserve|permission|approval|consent|credential|secret|destructive|safety|security|exact|verbatim|authority|source of truth|non-negotiable|hard rule)\b",
    re.IGNORECASE,
)
COMPRESSION_TERMS = re.compile(
    r"\b(compress|compression|summari[sz]e|truncate|trim|prune|condense|fold)\b",
    re.IGNORECASE,
)
TOKEN_SAVINGS_TERMS = re.compile(
    r"\b(token|tokens|cost|cheap|savings?|reduce[ds]?|reduction|smaller|shorter)\b",
    re.IGNORECASE,
)
TOTAL_COST_TERMS = re.compile(
    r"\b(output|total cost|input\+output|latency|task success|validation|validator|accuracy|similarity|quality|preserved|recall)\b",
    re.IGNORECASE,
)
RELEVANCE_TERMS = re.compile(
    r"\b(relevance|faithfulness|precision|recall|coverage|preserved|commitments?|critical atoms|provenance|recovery|source_refs?|evidence_refs?|task success|validation)\b",
    re.IGNORECASE,
)
RETRIEVAL_TERMS = re.compile(
    r"\b(retriev(?:e|al|ed)|recall(?:ed)?|memory|memories|archive|artifact|persistent state|store[d]?)\b",
    re.IGNORECASE,
)
COMMITMENT_TERMS = re.compile(
    r"\b(instruction|constraint|decision|evidence|source|source_ref|reference|recovery|verbatim|authority|provenance|warning|error|path|id|date|risk|commitment|commitments|contract|validation|capability)\b",
    re.IGNORECASE,
)
CACHE_TERMS = re.compile(
    r"\b(prompt cach(?:e|ing)|cached tokens?|cache hits?|cache reads?|cache writes?|cache[-_ ]?control|cached prefix|cache prefix|prompt_cache|cache breakpoint)\b",
    re.IGNORECASE,
)
CACHE_EVIDENCE_TERMS = re.compile(
    r"\b(cached_tokens|cache_read|cache_creation|usage|metrics?|hit rate|latency|cost|ttl|breakpoint|static|dynamic|prefix|suffix|monitor|measure)\b",
    re.IGNORECASE,
)
SCHEMA_OUTPUT_TERMS = re.compile(
    r"\b(structured output|json schema|schema-valid|strict json|json mode|constrained decoding|format restriction|typed output)\b",
    re.IGNORECASE,
)
SCHEMA_SUCCESS_TERMS = re.compile(
    r"\b(success|successful|reliable|valid|validity|ensure[sd]?|guarantee[sd]?|accepted|sufficient|safe|done)\b",
    re.IGNORECASE,
)
TASK_VALIDATION_TERMS = re.compile(
    r"\b(task success|semantic|semantics|cross-field|source support|consumer|validator|validation|test|fixture|accuracy|quality|schema and task|task validity)\b",
    re.IGNORECASE,
)


def is_middle_band(line_no: int, total_lines: int) -> bool:
    return total_lines >= 80 and (total_lines * 0.30) <= line_no <= (total_lines * 0.70)


def classify_load_path(path: Path) -> str:
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if name in {"agents.md", "skill.md"} or "prompts" in parts:
        return "hot"
    if name in {"readme.md", "index.md"} or "indexes" in parts:
        return "router"
    if "references" in parts or "docs" in parts:
        return "reference"
    if "reports" in parts or "sources" in parts or "logs" in parts or "evidence" in parts:
        return "evidence"
    return "unknown"


def is_test_path(path: Path) -> bool:
    return any(part.lower() in {"test", "tests"} for part in path.parts)


def scan_contract_risks(path: Path, text: str) -> list[dict]:
    risks: list[dict] = []
    if is_test_path(path):
        return risks
    lines = text.splitlines()
    in_code_block = False
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not CONTRACT_TERMS.search(line):
            if not SCHEMA_OUTPUT_TERMS.search(line):
                continue
        if CONTRACT_TERMS.search(line):
            if not (line.lstrip().startswith(("#", "-", "*")) and "(" not in line and "." not in line):
                for pattern, kind in PROSE_PARSERS:
                    if pattern.search(line):
                        severity = "high" if kind in {"split_over_text", "substring_match", "regex_parse"} else "medium"
                        risks.append(
                            {
                                "path": str(path),
                                "line": line_no,
                                "kind": "prose_parsing",
                                "parser": kind,
                                "severity": severity,
                                "message": "Possible parsing of generated model prose for machine state.",
                                "suggested_contract": "Move consumed values into strict JSON/schema, tool arguments, typed protocol fields, or closed enum keys.",
                                "excerpt": line.strip()[:220],
                            }
                        )
                        break
        window = "\n".join(lines[max(0, line_no - 4) : min(len(lines), line_no + 4)])
        if (
            path.suffix.lower() != ".py"
            and
            SCHEMA_OUTPUT_TERMS.search(line)
            and SCHEMA_SUCCESS_TERMS.search(window)
            and not TASK_VALIDATION_TERMS.search(window)
        ):
            risks.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "kind": "schema_without_task_validation",
                    "severity": "medium",
                    "message": "Structured-output or schema success is mentioned without nearby semantic, source-support, consumer, or task validation checks.",
                    "suggested_contract": "Treat schema validity as necessary but not sufficient; add semantic constraints, source support, and task-success validation for the consumer.",
                    "excerpt": line.strip()[:220],
                }
            )
    return risks


def scan_context_risks(path: Path, text: str, load_path: str) -> list[dict]:
    risks: list[dict] = []
    if is_test_path(path):
        return risks
    lines = text.splitlines()
    total_lines = len(lines)
    in_code_block = False
    current_section = ""
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip().lower()
        if load_path == "hot" and len(line) > 240:
            risks.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "kind": "dense_hot_line",
                    "severity": "low",
                    "message": "Long hot-context line; verify it is directive rather than narrative.",
                    "excerpt": line.strip()[:220],
                }
            )
        if load_path in {"hot", "router"}:
            if (
                REQUEST_TRIGGER_RE.search(line)
                and TRIGGER_SURFACE_RE.search(line)
                and not CONSENT_OR_SCOPE_RE.search(line)
                and not ANTI_BRITTLE_TRIGGER_RE.search(line)
            ):
                risks.append(
                    {
                        "path": str(path),
                        "line": line_no,
                        "kind": "brittle_request_trigger",
                        "severity": "medium",
                        "message": "Trigger wording appears tied to literal user phrasing instead of task context or source evidence.",
                        "suggested_contract": "Design skill/plugin descriptions around task contexts, artifacts, files, failures, and agent decision points; keep exact user wording only for consent, target binding, or behavior-critical output.",
                        "excerpt": line.strip()[:220],
                    }
                )
            for pattern, kind, severity in CONTEXT_RISK_PATTERNS:
                if pattern.search(line):
                    risks.append(
                        {
                            "path": str(path),
                            "line": line_no,
                            "kind": kind,
                            "severity": severity,
                            "message": "Potential low-value or volatile context in a surface future agents may reread.",
                            "excerpt": line.strip()[:220],
                        }
                    )
                    break
            if (
                is_middle_band(line_no, total_lines)
                and HIGH_AUTHORITY_TERMS.search(line)
                and not stripped.startswith(("#", "|"))
                and current_section != "hard rules"
                and not re.match(r"\d+\.", stripped)
            ):
                risks.append(
                    {
                        "path": str(path),
                        "line": line_no,
                        "kind": "middle_buried_commitment",
                        "severity": "medium",
                        "message": "High-authority or behavior-critical wording appears in the middle band of a long hot/router file.",
                        "suggested_contract": "Keep an anchor, source-order note, or explicit state pointer near the top of the load path, and leave detailed wording in a reference when appropriate.",
                        "excerpt": line.strip()[:220],
                    }
                )
            if (
                LONG_CONTEXT_TERMS.search(line)
                and CAPACITY_CONFIDENCE_TERMS.search(line)
                and not PLACEMENT_OR_VALIDATION_TERMS.search(line)
            ):
                risks.append(
                    {
                        "path": str(path),
                        "line": line_no,
                        "kind": "context_window_assumption",
                        "severity": "medium",
                        "message": "Line appears to rely on context-window capacity without placement, recall, evidence, or validation safeguards.",
                        "suggested_contract": "State validation scope, keep action-critical commitments anchored, and do not treat window size as proof of reliable recall or reasoning.",
                        "excerpt": line.strip()[:220],
                    }
                )
            if (
                LONG_CONTEXT_TERMS.search(line)
                and LONG_CONTEXT_SUCCESS_TERMS.search(line)
                and not PLACEMENT_OR_VALIDATION_TERMS.search(line)
            ):
                risks.append(
                    {
                        "path": str(path),
                        "line": line_no,
                        "kind": "long_context_without_placement_check",
                        "severity": "medium",
                        "message": "Long-context usage is mentioned without nearby placement, middle-position, recall, source-order, or validation checks.",
                        "suggested_contract": "Add placement stress, anchors, source-order notes, or task validation before relying on long-context packing.",
                        "excerpt": line.strip()[:220],
                    }
                )
    return risks


def scan_compression_risks(path: Path, text: str, load_path: str) -> list[dict]:
    risks: list[dict] = []
    if is_test_path(path):
        return risks
    if load_path not in {"hot", "router", "reference"}:
        return risks
    lines = text.splitlines()
    in_code_block = False
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    current_section = ""
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if line_no > 1 and stripped == "---" and in_frontmatter:
            in_frontmatter = False
            continue
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip().lower()
        if in_frontmatter:
            continue
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or stripped.startswith("#") or stripped.startswith("|") or current_section == "source map":
            continue
        if not COMPRESSION_TERMS.search(line):
            if not RETRIEVAL_TERMS.search(line) and not CACHE_TERMS.search(line):
                continue
        window = "\n".join(lines[max(0, line_no - 5) : min(len(lines), line_no + 5)])
        if COMPRESSION_TERMS.search(line) and not COMMITMENT_TERMS.search(window):
            risks.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "kind": "commitment_loss_risk",
                    "severity": "medium",
                    "message": "Compression or summarization is mentioned without nearby commitment, evidence, provenance, or recovery safeguards.",
                    "suggested_contract": "Preserve critical atoms: instructions, constraints, decisions, exact IDs/paths/dates/errors, evidence refs, and recovery pointers.",
                    "excerpt": line.strip()[:220],
                }
            )
        if COMPRESSION_TERMS.search(line) and TOKEN_SAVINGS_TERMS.search(window) and not TOTAL_COST_TERMS.search(window):
            risks.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "kind": "token_only_metric",
                    "severity": "medium",
                    "message": "Compression appears evaluated by token/cost reduction without nearby output, total-cost, quality, or validation checks.",
                    "suggested_contract": "Report input and output token effects, total cost, preserved facts, and task validation when claiming compression success.",
                    "excerpt": line.strip()[:220],
                }
            )
        if COMPRESSION_TERMS.search(line) and not RELEVANCE_TERMS.search(window):
            risks.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "kind": "compression_without_relevance_check",
                    "severity": "medium",
                    "message": "Compression is mentioned without nearby relevance, faithfulness, preservation, or task-validation checks.",
                    "suggested_contract": "Evaluate preserved critical atoms, relevance/faithfulness, downstream task behavior, output cost, and recovery before claiming compression success.",
                    "excerpt": line.strip()[:220],
                }
            )
        if RETRIEVAL_TERMS.search(line) and not COMMITMENT_TERMS.search(window):
            risks.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "kind": "retrieval_commitment_risk",
                    "severity": "medium",
                    "message": "Recall, retrieval, archive, or memory state is mentioned without nearby provenance, authority, evidence, or validation safeguards.",
                    "suggested_contract": "Keep artifact recall separate from committed state until confidence, trust boundary, and validation are explicit.",
                    "excerpt": line.strip()[:220],
                }
            )
        if CACHE_TERMS.search(line) and not CACHE_EVIDENCE_TERMS.search(window):
            risks.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "kind": "cache_claim_without_metrics",
                    "severity": "medium",
                    "message": "Prompt-cache or cached-prefix behavior is mentioned without nearby layout reasoning or cache usage metrics.",
                    "suggested_contract": "Report static prefix, dynamic suffix, cache breakpoint, cached token/read/write metrics, hit rate, latency, or cost when claiming cache benefits.",
                    "excerpt": line.strip()[:220],
                }
            )
    return risks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit a JSON audit of token hotspots, context risks, and prompt-contract risks."
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to audit.")
    parser.add_argument("--encoding", default="o200k_base", help="tiktoken encoding name.")
    parser.add_argument("--top", type=int, default=20, help="Token hotspots to include.")
    parser.add_argument("--json", action="store_true", help="Emit JSON. This is the default.")
    args = parser.parse_args()

    total, rows = count_paths(args.paths, args.encoding)
    row_by_path = {row["path"]: row for row in rows}
    context_risks: list[dict] = []
    compression_risks: list[dict] = []
    contract_risks: list[dict] = []

    for path in iter_files(args.paths):
        text = read_text(path)
        if text is None:
            continue
        load_path = classify_load_path(path)
        row_by_path.setdefault(str(path), {})["load_path"] = load_path
        context_risks.extend(scan_context_risks(path, text, load_path))
        compression_risks.extend(scan_compression_risks(path, text, load_path))
        contract_risks.extend(scan_contract_risks(path, text))

    hotspots = []
    for row in rows[: args.top]:
        path = Path(row["path"])
        hotspots.append(
            {
                "path": row["path"],
                "tokens": row["tokens"],
                "chars": row["chars"],
                "lines": row["lines"],
                "load_path": row_by_path.get(row["path"], {}).get("load_path", classify_load_path(path)),
            }
        )

    payload = {
        "schema": "context_density.audit.v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "mode": total["mode"],
        "encoding": total["encoding"],
        "token_summary": {
            "files": total["files"],
            "tokens": total["tokens"],
            "chars": total["chars"],
            "lines": total["lines"],
        },
        "token_hotspots": hotspots,
        "context_risks": context_risks,
        "compression_risks": compression_risks,
        "contract_risks": contract_risks,
        "risk_counts": {
            "context": len(context_risks),
            "compression": len(compression_risks),
            "contract": len(contract_risks),
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
