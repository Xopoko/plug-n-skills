#!/usr/bin/env python3
"""Audit token hotspots and prompt-contract risks in deterministic source files."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
PACK_VERB_TERMS = re.compile(
    r"\b(includ\w*|add\w*|load\w*|pack\w*|paste\w*|dump\w*|inline[sd]?|append\w*|attach\w*|inject\w*|cop(?:y|ies|ied|ying)|put[s]?|keep\w*)\b",
    re.IGNORECASE,
)
PACK_ALL_TERMS = re.compile(
    r"\b(all|every|entire|whole|full|everything|complete)\b[^.\n]{0,30}"
    r"\b(files?|history|contexts?|logs?|transcripts?|docs?|documents?|notes?|sources?|outputs?|conversations?|code|codebase|repo|reports?)\b"
    r"|\bjust in case\b",
    re.IGNORECASE,
)
RELEVANCE_FILTER_TERMS = re.compile(
    r"\b(relevan\w*|filter\w*|select\w*|prune[sd]?|pruning|rank\w*|curat\w*|top[- ]?\d+|budget\w*|only (?:what|the|when)|needed|necessary|criterion|criteria|distractor\w*)\b",
    re.IGNORECASE,
)
FORMAT_CHANGE_TERMS = re.compile(
    r"\b(reformat\w*|reword\w*|rephras\w*|restructur\w*|rewrit\w*|rewrote|re-?templat\w*|convert\w*[^.\n]{0,25}\b(?:to|into)\b[^.\n]{0,20}\b(?:json|yaml|markdown|xml|table|prose)\b)",
    re.IGNORECASE,
)
EQUIVALENCE_TERMS = re.compile(
    r"\b(same|equivalent|identical|unchanged|preserv\w*|lossless|behavio[u]?r[- ]neutral|no behavio[u]?r change|semantically|meaning[- ]preserving)\b",
    re.IGNORECASE,
)
FORMAT_VALIDATION_TERMS = re.compile(
    r"\b(valid\w*|test\w*|eval\w*|spot[- ]?check\w*|a/b|benchmark\w*|measur\w*|task success|commitment ledger|atoms|fixture\w*)\b",
    re.IGNORECASE,
)
HANDOFF_TERMS = re.compile(
    r"\b(hand[- ]?offs?|hand(?:s|ed|ing)? off|delegat\w*|sub-?agents?|spawn\w*[^.\n]{0,12}agents?|"
    r"pass\w*[^.\n]{0,12}(?:context|state|findings)|transfer\w*[^.\n]{0,12}(?:context|state)|compact\w*[^.\n]{0,16}(?:context|conversation|history))\b",
    re.IGNORECASE,
)
HANDOFF_CONTRACT_TERMS = re.compile(
    r"\b(contracts?|schemas?|typed|structured state|state shape|checklists?|atoms|source refs?|evidence refs?|verif\w*|validat\w*|explicit state|STATE v\d|recovery pointers?|provenance)\b",
    re.IGNORECASE,
)
RESEARCH_GATE_RULES = {
    "long_context_placement": {
        "risk_kinds": {
            "context_window_assumption",
            "long_context_without_placement_check",
            "middle_buried_commitment",
            "oversized_hot_surface",
        },
        "source_basis": [
            "arxiv:2307.03172",
            "arxiv:2406.16008",
            "arxiv:2402.14848",
            "arxiv:2404.06654",
            "arxiv:2502.05167",
        ],
        "required_evidence": [
            "action-critical anchors or compact state pointers",
            "middle-position or source-order placement check",
            "task validation on the actual packed context shape",
        ],
    },
    "compression_break_even": {
        "risk_kinds": {
            "commitment_loss_risk",
            "token_only_metric",
            "compression_without_relevance_check",
        },
        "source_basis": ["doi:10.18653/v1/2024.acl-long.91", "arxiv:2403.17411"],
        "required_evidence": [
            "input and hot-path token delta",
            "output token, latency, or total-cost effect",
            "task success plus preserved commitments and provenance",
            "compressor preprocessing overhead when applicable",
        ],
    },
    "schema_task_validity": {
        "risk_kinds": {"prose_parsing", "schema_without_task_validation"},
        "source_basis": ["OpenAI Structured Outputs", "doi:10.31234/osf.io/jqx7n_v1"],
        "required_evidence": [
            "strict schema, tool arguments, typed protocol, or closed keys",
            "unknown-field and invalid-output policy",
            "semantic constraints and consumer task-success validation",
        ],
    },
    "retrieval_citation_promotion": {
        "risk_kinds": {"retrieval_commitment_risk"},
        "source_basis": ["doi:10.48550/arxiv.2403.03187", "doi:10.3390/bdcc9120320"],
        "required_evidence": [
            "stable source key, URL, DOI, file path, or recovery pointer",
            "authority, confidence, and conflict status",
            "spot-check or validation before promotion into committed state",
        ],
    },
    "cache_aware_layout": {
        "risk_kinds": {"cache_claim_without_metrics"},
        "source_basis": ["OpenAI Prompt Caching", "Anthropic Prompt Caching", "arxiv:2312.07104"],
        "required_evidence": [
            "static prefix and dynamic suffix layout",
            "cache read, write, hit-rate, cached-token, latency, or cost metrics",
            "task-quality result reported separately from cache savings",
        ],
    },
    "relevance_distractor_budget": {
        "risk_kinds": {"context_stuffing"},
        "source_basis": [
            "arxiv:2302.00093",
            "arxiv:2404.03302",
            "arxiv:2401.14887",
            "arxiv:2402.08939",
        ],
        "required_evidence": [
            "per-block relevance criterion or consumer decision it changes",
            "distractor audit for related-but-non-answering material",
            "ordering aligned to consumer reasoning or execution order",
            "validation on the packed shape",
        ],
    },
    "format_sensitivity": {
        "risk_kinds": {"format_equivalence_assumption"},
        "source_basis": [
            "arxiv:2310.11324",
            "arxiv:2411.10541",
            "doi:10.18653/v1/2024.emnlp-industry.91",
        ],
        "required_evidence": [
            "task-level spot check, eval, or A/B on the actual consumer",
            "verbatim preservation or commitment ledger for behavior-critical wording",
        ],
    },
    "multi_agent_handoff": {
        "risk_kinds": {"handoff_without_contract"},
        "source_basis": ["arxiv:2503.13657", "arxiv:2507.13334"],
        "required_evidence": [
            "typed handoff contract or explicit state shape",
            "source refs and authority on transferred claims",
            "receiver-side verification before acting on handed-off state",
        ],
    },
}
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
COMMITMENT_SCHEMA = "context_density.commitment_ledger.v1"


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


def load_commitment_ledger(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        atoms = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        data = json.loads(text)
        atoms = data.get("atoms", data) if isinstance(data, dict) else data
    if not isinstance(atoms, list):
        raise SystemExit("commitment_ledger_atoms_must_be_list")
    if not all(isinstance(atom, dict) for atom in atoms):
        raise SystemExit("commitment_ledger_atoms_must_be_objects")
    return atoms


def collect_texts(paths: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in iter_files(paths):
        text = read_text(path)
        if text is not None:
            texts[str(path)] = text
    return texts


def path_matches_scope(path: str, scopes: Any) -> bool:
    if not scopes:
        return True
    values = scopes if isinstance(scopes, list) else [scopes]
    return any(str(path).endswith(str(scope)) or str(scope) in str(path) for scope in values)


def atom_present(atom: dict, texts: dict[str, str]) -> tuple[bool, str]:
    pattern = str(atom.get("text", ""))
    if not pattern:
        return False, "missing_text"
    scoped_texts = {
        path: text
        for path, text in texts.items()
        if path_matches_scope(path, atom.get("paths", atom.get("path", "")))
    }
    if not scoped_texts:
        return False, "no_matching_files"
    match_type = str(atom.get("match", "literal"))
    flags = 0 if atom.get("case_sensitive", True) else re.IGNORECASE
    if match_type == "literal":
        needle = pattern if atom.get("case_sensitive", True) else pattern.lower()
        for path, text in scoped_texts.items():
            haystack = text if atom.get("case_sensitive", True) else text.lower()
            if needle in haystack:
                return True, path
        return False, "not_found"
    if match_type == "regex":
        try:
            compiled = re.compile(pattern, flags)
        except re.error:
            return False, "invalid_regex"
        for path, text in scoped_texts.items():
            if compiled.search(text):
                return True, path
        return False, "not_found"
    return False, "invalid_match"


def validate_commitment_atoms(atoms: list[dict], texts: dict[str, str]) -> dict:
    results = []
    missing = []
    malformed = []
    for index, atom in enumerate(atoms, start=1):
        atom_id = str(atom.get("atom_id", atom.get("id", f"atom-{index:03d}")))
        required = bool(atom.get("required", True))
        present, detail = atom_present(atom, texts)
        result = {
            "atom_id": atom_id,
            "present": present,
            "required": required,
            "severity": atom.get("severity", "high" if required else "medium"),
            "match": atom.get("match", "literal"),
            "path": detail if present else "",
            "failure": "" if present else detail,
            "source_ref": atom.get("source_ref", ""),
        }
        results.append(result)
        if not present and detail in {"missing_text", "invalid_regex", "invalid_match"}:
            malformed.append(result)
        elif required and not present:
            missing.append(result)
    return {
        "schema": "context_density.commitment_validation.v1",
        "ledger_schema": COMMITMENT_SCHEMA,
        "checked": len(results),
        "passed": not missing and not malformed,
        "missing_required": missing,
        "malformed_atoms": malformed,
        "results": results,
    }


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


def research_gate_risks(*risk_groups: list[dict]) -> list[dict]:
    gate_risks: list[dict] = []
    for risks in risk_groups:
        for risk in risks:
            kind = str(risk.get("kind", ""))
            for gate_id, rule in RESEARCH_GATE_RULES.items():
                if kind not in rule["risk_kinds"]:
                    continue
                gate_risks.append(
                    {
                        "path": risk.get("path", ""),
                        "line": risk.get("line", 0),
                        "gate": gate_id,
                        "triggered_by": kind,
                        "severity": risk.get("severity", "medium"),
                        "message": risk.get("message", ""),
                        "required_evidence": rule["required_evidence"],
                        "source_basis": rule["source_basis"],
                        "suggested_contract": risk.get("suggested_contract", ""),
                        "excerpt": risk.get("excerpt", ""),
                    }
                )
                break
    return gate_risks


def research_gate_summary(gate_risks: list[dict]) -> list[dict]:
    summary: dict[str, dict] = {}
    for risk in gate_risks:
        gate = str(risk.get("gate", "unknown")) or "unknown"
        severity = str(risk.get("severity", "medium")) or "medium"
        current = summary.setdefault(
            gate,
            {
                "gate": gate,
                "count": 0,
                "max_severity": severity,
                "required_evidence": risk.get("required_evidence", []),
                "source_basis": risk.get("source_basis", []),
            },
        )
        current["count"] += 1
        if SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(str(current["max_severity"]), 0):
            current["max_severity"] = severity
    return [summary[gate] for gate in sorted(summary)]


def has_blocking_research_gate(gate_risks: list[dict], min_severity: str) -> bool:
    threshold = SEVERITY_RANK[min_severity]
    return any(SEVERITY_RANK.get(str(risk.get("severity", "medium")), 0) >= threshold for risk in gate_risks)


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
            window = "\n".join(lines[max(0, line_no - 4) : min(len(lines), line_no + 4)])
            if (
                PACK_VERB_TERMS.search(line)
                and PACK_ALL_TERMS.search(line)
                and not RELEVANCE_FILTER_TERMS.search(window)
            ):
                risks.append(
                    {
                        "path": str(path),
                        "line": line_no,
                        "kind": "context_stuffing",
                        "severity": "medium",
                        "message": "Pack-everything wording appears without nearby relevance, filtering, selection, or budget criteria; irrelevant and related-but-wrong context measurably degrades task accuracy.",
                        "suggested_contract": "State a relevance criterion per added block, audit related-but-non-answering distractors, order material to match consumer reasoning, and validate the packed shape.",
                        "excerpt": line.strip()[:220],
                    }
                )
            if HANDOFF_TERMS.search(line) and not HANDOFF_CONTRACT_TERMS.search(window):
                risks.append(
                    {
                        "path": str(path),
                        "line": line_no,
                        "kind": "handoff_without_contract",
                        "severity": "medium",
                        "message": "Agent/session handoff, delegation, or compaction is mentioned without a nearby typed contract, state shape, source refs, or verification step.",
                        "suggested_contract": "Use a typed handoff contract (goal, constraints, decisions, evidence refs, open risks, next action) and verify handed-off state before acting on it.",
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
            if (
                not RETRIEVAL_TERMS.search(line)
                and not CACHE_TERMS.search(line)
                and not FORMAT_CHANGE_TERMS.search(line)
            ):
                continue
        window = "\n".join(lines[max(0, line_no - 5) : min(len(lines), line_no + 5)])
        if (
            FORMAT_CHANGE_TERMS.search(line)
            and EQUIVALENCE_TERMS.search(window)
            and not FORMAT_VALIDATION_TERMS.search(window)
        ):
            risks.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "kind": "format_equivalence_assumption",
                    "severity": "medium",
                    "message": "Reformatting or rewriting is described as behavior-preserving without nearby task-level validation; formatting choices alone shift measured task accuracy.",
                    "suggested_contract": "Validate reformatted prompts/context with a task-level spot check, eval, or A/B on the actual consumer, and preserve behavior-critical wording verbatim or in a commitment ledger.",
                    "excerpt": line.strip()[:220],
                }
            )
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
    parser.add_argument(
        "--fail-on-research-gates",
        action="store_true",
        help="Exit 2 when research gate risks meet --fail-on-severity.",
    )
    parser.add_argument(
        "--fail-on-severity",
        choices=sorted(SEVERITY_RANK, key=SEVERITY_RANK.get),
        default="medium",
        help="Minimum research gate severity that should fail when --fail-on-research-gates is set.",
    )
    parser.add_argument(
        "--hot-token-budget",
        type=int,
        default=3000,
        help="Flag hot-path files above this token count (0 disables). Default anchors to documented reasoning degradation near 3K input tokens (arxiv:2402.14848).",
    )
    parser.add_argument("--commitment-ledger", default="", help="JSON or JSONL commitment atom ledger to validate.")
    parser.add_argument(
        "--fail-on-missing-commitments",
        action="store_true",
        help="Exit 3 when required commitment atoms are missing or malformed.",
    )
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
        if args.hot_token_budget > 0 and load_path == "hot" and not is_test_path(path):
            tokens = row_by_path.get(str(path), {}).get("tokens", 0)
            if tokens > args.hot_token_budget:
                context_risks.append(
                    {
                        "path": str(path),
                        "line": 0,
                        "kind": "oversized_hot_surface",
                        "severity": "medium" if tokens >= 2 * args.hot_token_budget else "low",
                        "message": (
                            f"Hot-path file measures {tokens} tokens against a {args.hot_token_budget}-token budget; "
                            "reasoning degradation is documented well below advertised context maximums."
                        ),
                        "suggested_contract": "Move conditional detail to references, keep directives and anchors hot, and validate behavior on the packed shape if the surface must stay large.",
                        "excerpt": "",
                    }
                )
    gate_risks = research_gate_risks(context_risks, compression_risks, contract_risks)
    gate_blocked = args.fail_on_research_gates and has_blocking_research_gate(gate_risks, args.fail_on_severity)
    commitment_validation = {
        "schema": "context_density.commitment_validation.v1",
        "ledger_schema": COMMITMENT_SCHEMA,
        "checked": 0,
        "passed": True,
        "missing_required": [],
        "malformed_atoms": [],
        "results": [],
    }
    if args.commitment_ledger:
        atoms = load_commitment_ledger(Path(args.commitment_ledger))
        commitment_validation = validate_commitment_atoms(atoms, collect_texts(args.paths))
    commitments_blocked = args.fail_on_missing_commitments and not commitment_validation["passed"]

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
        "research_gate_risks": gate_risks,
        "research_gate_summary": research_gate_summary(gate_risks),
        "commitment_validation": commitment_validation,
        "blocking": {
            "research_gates": gate_blocked,
            "fail_on_severity": args.fail_on_severity if args.fail_on_research_gates else "",
            "commitments": commitments_blocked,
        },
        "risk_counts": {
            "context": len(context_risks),
            "compression": len(compression_risks),
            "contract": len(contract_risks),
            "research_gates": len(gate_risks),
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if commitments_blocked:
        return 3
    return 2 if gate_blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
