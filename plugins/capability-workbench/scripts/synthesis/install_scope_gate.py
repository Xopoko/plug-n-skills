#!/usr/bin/env python3
"""Validate the intended delivery and installation surface for agent capabilities."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VALID_ARTIFACTS = {"skill", "plugin", "mcp", "mixed", "report"}
VALID_SCOPES = {"global-codex", "repo-local", "workspace-snapshot", "reference-only"}
VALID_INSTALL_STATES = {"planned", "delivered", "installed", "not-applicable", "partial"}
VALID_LOCAL_EVIDENCE_SOURCES = {
    "latest_user_message",
    "repo_instructions",
    "workspace_profile",
    "explicit_path",
}
LOCAL_SCOPE_PHRASES = {
    "in this repo",
    "current repo",
    "repo-local",
    "project-local",
    "local repository",
    "inside this repo",
    "inside current repo",
    "do not install globally",
    "don't install globally",
    "not globally",
    "no global install",
    "local-only",
    "workspace draft",
    "reference-only",
    "no-install",
    # Russian local-scope aliases are escaped to keep the source tree ASCII-only.
    "\u0432 \u044d\u0442\u043e\u043c \u0440\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u0438",
    "\u0432 \u0442\u0435\u043a\u0443\u0449\u0435\u043c \u0440\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u0438",
    "\u0432 \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e\u043c \u0440\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u0438",
    "\u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e \u0432 \u0440\u0435\u043f\u043e\u0437\u0438\u0442\u043e\u0440\u0438\u0438",
    "\u0432 \u044d\u0442\u043e\u043c \u043f\u0440\u043e\u0435\u043a\u0442\u0435",
    "\u0432 \u0442\u0435\u043a\u0443\u0449\u0435\u043c \u043f\u0440\u043e\u0435\u043a\u0442\u0435",
    "\u0442\u043e\u043b\u044c\u043a\u043e \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e",
    "\u043d\u0435 \u0443\u0441\u0442\u0430\u043d\u0430\u0432\u043b\u0438\u0432\u0430\u0439 \u0433\u043b\u043e\u0431\u0430\u043b\u044c\u043d\u043e",
    "\u043d\u0435 \u0441\u0442\u0430\u0432\u044c \u0433\u043b\u043e\u0431\u0430\u043b\u044c\u043d\u043e",
    "\u0431\u0435\u0437 \u0433\u043b\u043e\u0431\u0430\u043b\u044c\u043d\u043e\u0439 \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438",
    "\u043b\u043e\u043a\u0430\u043b\u044c\u043d\u044b\u0439 \u0447\u0435\u0440\u043d\u043e\u0432\u0438\u043a",
}
REPO_PROFILE_PHRASES = {
    "plugin source repository",
    "skill source repository",
    "capability source repository",
    "repo instructions",
    "agents.md",
    "agentrules",
    "plugin repository",
    "skills directory",
    "plugins directory",
}


TEMPLATE = {
    "schema": "codex.install_scope.v1",
    "target": "",
    "artifact_type": "skill",
    "mode": "new-skill",
    "install_scope": "repo-local",
    "destination_path": "./plugins/<plugin-name> or ./skills/<skill-name>",
    "marketplace_path": "",
    "install_required": False,
    "install_state": "planned",
    "explicit_local_request": False,
    "local_request_evidence": [
        {
            "source": "workspace_profile",
            "quote": "current repository contains plugin/skill source for this task",
            "matched_phrase": "plugin source repository",
        }
    ],
    "validation": [],
    "notes": "",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"invalid_json:{path}:{exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("ledger_must_be_object")
    return data


def non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and any(value)


def validate_local_scope_evidence(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list) or not value:
        return ["repo_local_requires_surface_evidence"]

    has_valid_evidence = False
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"local_request_evidence_{index}_must_be_object")
            continue
        source = item.get("source")
        quote = item.get("quote")
        matched = item.get("matched_phrase")
        if source not in VALID_LOCAL_EVIDENCE_SOURCES:
            errors.append(f"local_request_evidence_{index}_source_must_be_valid_surface_source")
        if not isinstance(quote, str) or not quote.strip():
            errors.append(f"local_request_evidence_{index}_requires_quote")
        if not isinstance(matched, str) or not matched.strip():
            errors.append(f"local_request_evidence_{index}_requires_matched_phrase")
            continue
        phrase = matched.strip().lower()
        quote_text = quote.lower() if isinstance(quote, str) else ""

        if source == "latest_user_message":
            if phrase not in LOCAL_SCOPE_PHRASES:
                errors.append(f"local_request_evidence_{index}_matched_phrase_not_allowed")
                continue
            if phrase in quote_text:
                has_valid_evidence = True
            else:
                errors.append(f"local_request_evidence_{index}_phrase_must_appear_in_quote")
            continue

        allowed_repo_phrase = phrase in REPO_PROFILE_PHRASES or "repo" in phrase or "repository" in phrase
        if not allowed_repo_phrase:
            errors.append(f"local_request_evidence_{index}_matched_phrase_not_allowed")
            continue
        if quote_text:
            has_valid_evidence = True

    if not has_valid_evidence:
        errors.append("repo_local_requires_user_repo_or_workspace_surface_evidence")
    return errors


def looks_like_global_skill_path(path: str) -> bool:
    return "${CODEX_HOME" in path or "/.codex/skills/" in path or path.endswith("/.codex/skills")


def looks_like_global_plugin_path(path: str) -> bool:
    return (
        path.startswith("$HOME/plugins/")
        or path.startswith("~/plugins/")
        or re.match(r"^/Users/[^/]+/plugins/[^/]+", path) is not None
    )


def validate(data: dict[str, Any], final: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("schema") != "codex.install_scope.v1":
        errors.append("schema_must_be_codex.install_scope.v1")

    artifact = data.get("artifact_type")
    scope = data.get("install_scope")
    install_state = data.get("install_state")
    destination = data.get("destination_path")
    marketplace = data.get("marketplace_path")
    install_required = data.get("install_required", True)

    if artifact not in VALID_ARTIFACTS:
        errors.append("invalid_artifact_type")
    if scope not in VALID_SCOPES:
        errors.append("invalid_install_scope")
    if install_state not in VALID_INSTALL_STATES:
        errors.append("invalid_install_state")
    if not isinstance(install_required, bool):
        errors.append("install_required_must_be_boolean")
    if final and install_state == "planned":
        errors.append("final_install_state_cannot_be_planned")

    if scope == "global-codex":
        if not destination:
            errors.append("global_codex_requires_destination_path")
        elif artifact == "skill" and not looks_like_global_skill_path(str(destination)):
            errors.append("global_skill_destination_must_be_codex_home_skills")
        elif artifact in {"plugin", "mixed"} and not looks_like_global_plugin_path(str(destination)):
            errors.append("global_plugin_destination_should_be_user_plugins_path")
        if artifact in {"plugin", "mixed"} and not marketplace:
            errors.append("global_plugin_requires_marketplace_path")
        if artifact == "mcp":
            warnings.append("mcp_global_install_requires_codex_global_config_or_marketplace_plugin_not_repo_mcp_json")
        if final and install_required and install_state != "installed":
            errors.append("final_global_codex_install_requires_installed_state")

    if scope == "repo-local":
        errors.extend(validate_local_scope_evidence(data.get("local_request_evidence")))
        if not destination:
            errors.append("repo_local_requires_destination_path")
        if final and install_required and install_state != "installed":
            errors.append("final_repo_local_required_install_requires_installed_state")
        if final and not install_required and install_state not in {"delivered", "not-applicable"}:
            errors.append("final_repo_local_source_requires_delivered_or_not_applicable_state")

    if scope == "workspace-snapshot":
        if install_required:
            errors.append("workspace_snapshot_cannot_satisfy_required_install")
        if not data.get("snapshot_reason"):
            warnings.append("workspace_snapshot_should_record_snapshot_reason")

    if scope == "reference-only":
        if install_required:
            errors.append("reference_only_cannot_satisfy_required_install")
        if install_state != "not-applicable":
            errors.append("reference_only_install_state_must_be_not_applicable")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate target delivery and install scope for Workbench outputs.")
    parser.add_argument("ledger", nargs="?", help="Path to install-scope.json")
    parser.add_argument("--template", action="store_true", help="Print an install-scope contract template.")
    parser.add_argument("--final", action="store_true", help="Require final installed state where applicable.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result.")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(TEMPLATE, indent=2, ensure_ascii=False))
        return 0
    if not args.ledger:
        parser.error("ledger path is required unless --template is used")

    path = Path(args.ledger)
    data = load_json(path)
    errors, warnings = validate(data, final=args.final)
    result = {
        "schema": "codex.install_scope_gate.result.v1",
        "path": str(path),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "install_scope": data.get("install_scope"),
        "artifact_type": data.get("artifact_type"),
        "install_state": data.get("install_state"),
        "final": args.final,
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
