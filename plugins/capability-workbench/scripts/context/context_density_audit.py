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
WORKFLOW_DESCRIPTION_RE = re.compile(
    r"^\s*description\s*:\s*.*\b("
    r"workflow|step|steps|procedure|checklist|then|after that|followed by"
    r")\b",
    re.IGNORECASE,
)
COMPRESSION_TERMS = re.compile(
    r"\b(compress|compression|summari[sz]e|summary|truncate|trim|prune|compact|condense|fold)\b",
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
RETRIEVAL_TERMS = re.compile(
    r"\b(retriev(?:e|al|ed)|recall(?:ed)?|memory|memories|archive|artifact|persistent state|store[d]?)\b",
    re.IGNORECASE,
)
COMMITMENT_TERMS = re.compile(
    r"\b(instruction|constraint|decision|evidence|source|source_ref|reference|recovery|verbatim|authority|provenance|warning|error|path|id|date|risk|commitment|commitments|contract|validation|capability)\b",
    re.IGNORECASE,
)


def classify_load_path(path: Path) -> str:
    name = path.name.lower()
    parts = {part.lower() for part in path.parts}
    if name in {"agents.md", "skill.md"} or "prompts" in parts:
        return "hot"
    if name in {"readme.md", "index.md"} or "indexes" in parts:
        return "router"
    if "references" in parts or "docs" in parts:
        return "reference"
    if "reports" in parts or "research" in parts or "logs" in parts or "evidence" in parts:
        return "evidence"
    return "unknown"


def scan_contract_risks(path: Path, text: str) -> list[dict]:
    risks: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not CONTRACT_TERMS.search(line):
            continue
        if line.lstrip().startswith(("#", "-", "*")) and "(" not in line and "." not in line:
            continue
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
    return risks


def scan_context_risks(path: Path, text: str, load_path: str) -> list[dict]:
    risks: list[dict] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
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
            if WORKFLOW_DESCRIPTION_RE.search(line) and not ANTI_BRITTLE_TRIGGER_RE.search(line):
                risks.append(
                    {
                        "path": str(path),
                        "line": line_no,
                        "kind": "workflow_summary_description",
                        "severity": "medium",
                        "message": "Description appears to include workflow/procedure terms that may let the agent act from metadata instead of reading SKILL.md.",
                        "suggested_contract": "Keep descriptions as trigger contracts: use-when, inputs/signals, non-use boundaries, failure symptoms, and adjacent skills. Put procedure in the skill body.",
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
    return risks


def scan_compression_risks(path: Path, text: str, load_path: str) -> list[dict]:
    risks: list[dict] = []
    if load_path not in {"hot", "router", "reference"}:
        return risks
    lines = text.splitlines()
    in_code_block = False
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or stripped.startswith("#"):
            continue
        if not COMPRESSION_TERMS.search(line):
            if not RETRIEVAL_TERMS.search(line):
                continue
        window = "\n".join(lines[max(0, line_no - 4) : min(len(lines), line_no + 3)])
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
