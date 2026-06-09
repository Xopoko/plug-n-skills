#!/usr/bin/env python3
"""Check basic SDD artifact traceability without external dependencies."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REQ_ID_RE = re.compile(r"\b(?:FR|NFR|REQ|SC|US|AC)-\d{3,}\b", re.IGNORECASE)
REQ_DEF_RE = re.compile(r"^\s*[-*]\s*\*\*((?:FR|NFR|REQ|SC|US|AC)-\d{3,})\*\*", re.IGNORECASE | re.MULTILINE)
OPEN_SPEC_REQ_RE = re.compile(r"^### Requirement:\s*(.+?)\s*$", re.MULTILINE)
KIRO_REQ_RE = re.compile(r"^### Requirement\s+(\d+):\s*(.+?)\s*$", re.MULTILINE)
TASK_RE = re.compile(r"^\s*-\s*\[(?P<done>[ xX])\]\s*(?P<body>.+)$", re.MULTILINE)
TASK_ID_RE = re.compile(r"^(?:\s*\**(?:T|TASK-)\d{3,}\**|\s*\d+(?:\.\d+)*)\b", re.IGNORECASE)
EVIDENCE_ID_RE = re.compile(r"\b(?:EV|EVIDENCE|PROOF)-\d{3,}\b", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(
    r"NEEDS CLARIFICATION|TO VERIFY|TODO|TKTK|\?\?\?|\{\{[^}]+\}\}|\[[A-Z _-]*PLACEHOLDER[A-Z _-]*\]",
    re.IGNORECASE,
)
VERIFY_RE = re.compile(
    r"\b(test|tests|verify|verification|validate|validation|check|build|typecheck|lint|smoke|quickstart|reproduce|assert)\b",
    re.IGNORECASE,
)
EVIDENCE_WORD_RE = re.compile(r"\b(evidence|proof|verified|passed|failed|result|outcome|ran|run|log|report)\b", re.IGNORECASE)
SELF_JUDGE_RE = re.compile(
    r"\b(llm self[- ]?(?:review|judge|evaluation)|model confidence|ai says|llm says|chatgpt says|"
    r"llm-as-a-judge|llm judge|model judged|agent summary)\b",
    re.IGNORECASE,
)
PATH_RE = re.compile(r"\b(?:src|app|lib|tests?|packages?|backend|frontend|ios|android|api|docs|scripts)/[^\s,;:)]+")
EVIDENCE_FILE_NAMES = (
    "evidence.md",
    "validation.md",
    "proof.md",
    "verification.md",
    "test-results.md",
    "audit.md",
)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="replace")


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def load_feature_json(root: Path) -> Path | None:
    feature_json = root / ".specify" / "feature.json"
    if not feature_json.is_file():
        return None
    try:
        payload = json.loads(feature_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = payload.get("feature_directory")
    if isinstance(value, str) and value.strip():
        candidate = root / value
        if candidate.exists():
            return candidate
    return None


def find_feature_dir(root: Path, explicit: str | None) -> Path | None:
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate.resolve()

    from_feature_json = load_feature_json(root)
    if from_feature_json is not None:
        return from_feature_json.resolve()

    if any((root / name).is_file() for name in ("spec.md", "requirements.md", "bugfix.md", "tasks.md")):
        return root.resolve()

    candidates: list[Path] = []
    for base in ("specs", ".kiro/specs", ".spec-flow/active", ".sdd", "openspec/changes"):
        base_path = root / base
        if not base_path.is_dir():
            continue
        for child in base_path.iterdir():
            if child.is_dir() and any((child / name).is_file() for name in ("spec.md", "requirements.md", "bugfix.md", "tasks.md")):
                candidates.append(child)
    if not candidates:
        return None
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0].resolve()


def choose_artifacts(feature_dir: Path) -> dict[str, Path | list[Path] | None]:
    spec = None
    for name in ("spec.md", "requirements.md", "bugfix.md"):
        candidate = feature_dir / name
        if candidate.is_file():
            spec = candidate
            break
    design = None
    for name in ("plan.md", "design.md"):
        candidate = feature_dir / name
        if candidate.is_file():
            design = candidate
            break
    tasks = feature_dir / "tasks.md" if (feature_dir / "tasks.md").is_file() else None
    quickstart = feature_dir / "quickstart.md" if (feature_dir / "quickstart.md").is_file() else None
    evidence = [feature_dir / name for name in EVIDENCE_FILE_NAMES if (feature_dir / name).is_file()]
    return {"spec": spec, "design": design, "tasks": tasks, "quickstart": quickstart, "evidence": evidence}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def extract_requirements(spec_text: str) -> list[dict[str, str]]:
    seen: set[str] = set()
    requirements: list[dict[str, str]] = []
    for match in REQ_ID_RE.finditer(spec_text):
        req_id = match.group(0).upper()
        if req_id not in seen:
            seen.add(req_id)
            requirements.append({"id": req_id, "kind": "id", "label": req_id})
    for match in OPEN_SPEC_REQ_RE.finditer(spec_text):
        label = match.group(1).strip()
        key = f"REQ:{label}"
        if key not in seen:
            seen.add(key)
            requirements.append({"id": key, "kind": "heading", "label": label, "slug": slug(label)})
    for match in KIRO_REQ_RE.finditer(spec_text):
        number = match.group(1).strip()
        label = match.group(2).strip()
        key = f"REQNUM:{number}"
        if key not in seen:
            seen.add(key)
            requirements.append({"id": number, "kind": "number", "label": label, "slug": slug(label)})
    return requirements


def extract_tasks(tasks_text: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    lines = tasks_text.splitlines()
    for index, line in enumerate(lines):
        match = TASK_RE.match(line)
        if not match:
            continue
        body = match.group("body").strip()
        window = "\n".join(lines[index : min(index + 4, len(lines))])
        task_id_match = TASK_ID_RE.search(body)
        refs = sorted({item.upper() for item in REQ_ID_RE.findall(body)})
        evidence_refs = sorted({item.upper() for item in EVIDENCE_ID_RE.findall(window)})
        tasks.append(
            {
                "line": index + 1,
                "done": match.group("done").lower() == "x",
                "body": body,
                "task_id": task_id_match.group(0).strip().strip("*").rstrip(".") if task_id_match else None,
                "refs": refs,
                "evidence_refs": evidence_refs,
                "has_verification": bool(VERIFY_RE.search(window)),
                "has_inline_evidence": bool(VERIFY_RE.search(window) and EVIDENCE_WORD_RE.search(window)),
                "has_path": bool(PATH_RE.search(body)),
            }
        )
    return tasks


def artifact_value(value: Path | list[Path] | None) -> str | list[str] | None:
    if isinstance(value, list):
        return [item.as_posix() for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    return None


def check(root: Path, feature_dir_arg: str | None) -> dict[str, Any]:
    root = root.resolve()
    feature_dir = find_feature_dir(root, feature_dir_arg)
    findings: list[dict[str, str]] = []

    if feature_dir is None:
        return {
            "schema": "sdd.traceability_check.v1",
            "root": root.as_posix(),
            "feature_dir": None,
            "status": "FAIL",
            "findings": [
                {
                    "severity": "FAIL",
                    "code": "NO_FEATURE_DIR",
                    "message": "No active SDD feature directory was found.",
                }
            ],
            "counts": {},
        }

    artifacts = choose_artifacts(feature_dir)
    spec_path = artifacts["spec"]
    design_path = artifacts["design"]
    tasks_path = artifacts["tasks"]
    quickstart_path = artifacts["quickstart"]
    evidence_paths = artifacts["evidence"] if isinstance(artifacts["evidence"], list) else []

    if spec_path is None:
        findings.append({"severity": "FAIL", "code": "MISSING_SPEC", "message": "Missing spec.md, requirements.md, or bugfix.md."})
        spec_text = ""
    else:
        spec_text = read(spec_path)

    if design_path is None:
        findings.append({"severity": "WARN", "code": "MISSING_DESIGN", "message": "Missing plan.md or design.md."})
        design_text = ""
    else:
        design_text = read(design_path)

    if tasks_path is None:
        findings.append({"severity": "FAIL", "code": "MISSING_TASKS", "message": "Missing tasks.md."})
        tasks_text = ""
    else:
        tasks_text = read(tasks_path)

    evidence_texts = [(f"evidence:{path.name}", path, read(path)) for path in evidence_paths]
    evidence_text = "\n\n".join(text for _, _, text in evidence_texts)
    evidence_blob = evidence_text.upper()

    for label, path, text in (
        ("spec", spec_path, spec_text),
        ("design", design_path, design_text),
        ("tasks", tasks_path, tasks_text),
        *evidence_texts,
    ):
        if path is not None and PLACEHOLDER_RE.search(text):
            findings.append(
                {
                    "severity": "WARN",
                    "code": "UNRESOLVED_MARKER",
                    "message": f"{label} contains clarification, TODO, placeholder, or verification marker.",
                    "path": rel(path, root),
                }
            )
        if path is not None and SELF_JUDGE_RE.search(text):
            findings.append(
                {
                    "severity": "WARN",
                    "code": "LLM_SELF_JUDGE_MENTION",
                    "message": f"{label} mentions LLM self-review or model judgment; ensure it is advisory, not sole proof.",
                    "path": rel(path, root),
                }
            )

    requirements = extract_requirements(spec_text)
    if spec_path is not None and spec_text.strip() and not requirements:
        findings.append(
            {
                "severity": "WARN",
                "code": "SPEC_WITHOUT_STABLE_REQUIREMENTS",
                "message": "Spec has no recognized requirement IDs or requirement headings.",
                "path": rel(spec_path, root),
            }
        )
    requirement_ids = {item["id"] for item in requirements if item["kind"] == "id"}
    declared_req_ids = [item.upper() for item in REQ_DEF_RE.findall(spec_text)]
    duplicate_ids = sorted({item for item in declared_req_ids if declared_req_ids.count(item) > 1})
    for req_id in duplicate_ids:
        findings.append({"severity": "WARN", "code": "DUPLICATE_REQ_ID", "message": f"{req_id} appears multiple times; ensure this is intentional."})

    tasks = extract_tasks(tasks_text)
    task_ids = [task["task_id"].upper() for task in tasks if task["task_id"]]
    duplicate_task_ids = sorted({item for item in task_ids if task_ids.count(item) > 1})
    for task_id in duplicate_task_ids:
        findings.append({"severity": "FAIL", "code": "DUPLICATE_TASK_ID", "message": f"{task_id} appears multiple times."})

    for task in tasks:
        if not task["task_id"]:
            findings.append({"severity": "FAIL", "code": "TASK_WITHOUT_ID", "message": f"Task at line {task['line']} has no T### ID."})
        if not task["has_verification"]:
            findings.append({"severity": "WARN", "code": "TASK_WITHOUT_VERIFICATION", "message": f"Task {task.get('task_id') or 'at line ' + str(task['line'])} has no nearby verification wording."})
        if not task["has_path"] and not any(word in task["body"].lower() for word in ("setup", "research", "validate", "quickstart", "review", "document")):
            findings.append({"severity": "WARN", "code": "TASK_WITHOUT_PATH", "message": f"Task {task.get('task_id') or 'at line ' + str(task['line'])} has no concrete file path."})
        task_id = (task.get("task_id") or "").upper()
        has_evidence_ledger_ref = bool(task_id and task_id in evidence_blob) or any(ref in evidence_blob for ref in task.get("evidence_refs", []))
        if task["done"] and not (task["has_inline_evidence"] or has_evidence_ledger_ref):
            findings.append(
                {
                    "severity": "FAIL",
                    "code": "COMPLETED_TASK_WITHOUT_EVIDENCE",
                    "message": f"Completed task {task.get('task_id') or 'at line ' + str(task['line'])} has no inline outcome or evidence-ledger reference.",
                }
            )

    task_blob = tasks_text.upper()
    requirements_with_task_refs = 0
    for req in requirements:
        if req["kind"] == "id":
            if req["id"] not in task_blob:
                findings.append({"severity": "WARN", "code": "REQ_WITHOUT_TASK", "message": f"{req['id']} is not referenced by tasks.md."})
            else:
                requirements_with_task_refs += 1
        elif req["kind"] == "number":
            numeric_ref = re.compile(rf"\b{re.escape(req['id'])}(?:\.\d+)?\b")
            if numeric_ref.search(tasks_text) is None:
                findings.append({"severity": "WARN", "code": "REQ_WITHOUT_TASK", "message": f"Requirement {req['id']} is not referenced by tasks.md."})
            else:
                requirements_with_task_refs += 1
        else:
            words = [part for part in req.get("slug", "").split("-") if len(part) > 3]
            if words and not all(word.upper() in task_blob for word in words[:3]):
                findings.append({"severity": "WARN", "code": "REQ_WITHOUT_TASK", "message": f"Requirement heading '{req['label']}' is not clearly referenced by tasks.md."})
            else:
                requirements_with_task_refs += 1

    known_refs = requirement_ids
    for task in tasks:
        for ref in task["refs"]:
            if known_refs and ref not in known_refs:
                findings.append({"severity": "WARN", "code": "TASK_UNKNOWN_REQ_REF", "message": f"Task {task.get('task_id') or task['line']} references unknown {ref}."})

    if quickstart_path is None:
        findings.append({"severity": "WARN", "code": "MISSING_QUICKSTART", "message": "No quickstart.md found; completion may rely on task-local verification only."})

    if any(task["done"] for task in tasks) and not evidence_paths:
        findings.append(
            {
                "severity": "WARN",
                "code": "MISSING_EVIDENCE_LEDGER",
                "message": "Completed tasks exist but no evidence.md, validation.md, proof.md, verification.md, test-results.md, or audit.md was found.",
            }
        )

    severity_order = {"FAIL": 2, "WARN": 1}
    worst = max((severity_order.get(item["severity"], 0) for item in findings), default=0)
    status = "FAIL" if worst == 2 else "WARN" if worst == 1 else "PASS"

    return {
        "schema": "sdd.traceability_check.v1",
        "root": root.as_posix(),
        "feature_dir": feature_dir.as_posix(),
        "status": status,
        "artifacts": {key: artifact_value(value) for key, value in artifacts.items()},
        "counts": {
            "requirements": len(requirements),
            "requirements_with_task_refs": requirements_with_task_refs,
            "tasks": len(tasks),
            "task_requirement_edges": sum(len(task["refs"]) for task in tasks),
            "tasks_with_verification": sum(1 for task in tasks if task["has_verification"]),
            "tasks_with_inline_evidence": sum(1 for task in tasks if task["has_inline_evidence"]),
            "tasks_with_path": sum(1 for task in tasks if task["has_path"]),
            "completed_tasks": sum(1 for task in tasks if task["done"]),
            "evidence_files": len(evidence_paths),
            "findings": len(findings),
            "failures": sum(1 for item in findings if item["severity"] == "FAIL"),
            "warnings": sum(1 for item in findings if item["severity"] == "WARN"),
        },
        "findings": findings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check SDD artifact traceability.")
    parser.add_argument("path", nargs="?", default=".", help="Repository or feature path")
    parser.add_argument("--feature-dir", help="Feature directory relative to path or absolute")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = check(Path(args.path), args.feature_dir)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"SDD traceability: {payload['status']}")
    print(f"Feature: {payload.get('feature_dir')}")
    for finding in payload.get("findings", [])[:20]:
        print(f"- {finding['severity']} {finding['code']}: {finding['message']}")


if __name__ == "__main__":
    main()
