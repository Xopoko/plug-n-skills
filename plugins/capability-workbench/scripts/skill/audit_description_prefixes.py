#!/usr/bin/env python3
"""Audit SKILL.md description prefixes for catalog-pressure resilience.

The audit normalizes Unicode, letter case, and whitespace before comparing the
first N characters of each description. Generic lead-ins and malformed
frontmatter are errors. Prefix collisions and long descriptions are advisory
unless ``--strict`` is supplied.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import yaml


SCHEMA = "capability.skill_description_prefix_audit.v1"
DEFAULT_PREFIX_WIDTH = 40
DEFAULT_MAX_DESCRIPTION_CHARS = 240
GENERIC_LEAD_INS = (
    "Use when",
    "Use for",
    "Use this",
    "Use whenever",
    "Help with",
    "Agent skills for",
    "This skill",
)


class FrontmatterError(ValueError):
    """Raised when a SKILL.md frontmatter block cannot be audited."""


def positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def normalize_description(description: str) -> str:
    """Return the catalog-comparison form of a description."""

    unicode_normalized = unicodedata.normalize("NFKC", description)
    return " ".join(unicode_normalized.split()).casefold()


def generic_lead_in(normalized_description: str) -> str | None:
    """Return the canonical generic lead-in matched at a word boundary."""

    for lead_in in sorted(GENERIC_LEAD_INS, key=len, reverse=True):
        normalized_lead_in = normalize_description(lead_in)
        if normalized_description == normalized_lead_in:
            return lead_in
        if not normalized_description.startswith(normalized_lead_in):
            continue
        next_character = normalized_description[len(normalized_lead_in)]
        if not (next_character.isalnum() or next_character == "_"):
            return lead_in
    return None


def issue(
    severity: str,
    code: str,
    message: str,
    *,
    path: Path | None = None,
    paths: Iterable[Path] | None = None,
    **details: Any,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if path is not None:
        finding["path"] = str(path)
    if paths is not None:
        finding["paths"] = [str(item) for item in paths]
    finding.update(details)
    return finding


def discover_skill_files(raw_roots: list[str]) -> tuple[list[Path], list[dict[str, Any]]]:
    discovered: dict[str, Path] = {}
    errors: list[dict[str, Any]] = []

    for raw_root in raw_roots:
        candidate = Path(raw_root).expanduser()
        try:
            root = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            errors.append(
                issue(
                    "error",
                    "input_error",
                    f"root does not exist or cannot be resolved: {exc}",
                    path=candidate.absolute(),
                )
            )
            continue

        if root.is_file():
            if root.name != "SKILL.md":
                errors.append(
                    issue(
                        "error",
                        "input_error",
                        "file roots must be named SKILL.md",
                        path=root,
                    )
                )
                continue
            discovered[str(root)] = root
            continue

        if not root.is_dir():
            errors.append(
                issue(
                    "error",
                    "input_error",
                    "root is neither a file nor a directory",
                    path=root,
                )
            )
            continue

        try:
            matches = sorted(root.rglob("SKILL.md"), key=lambda item: str(item).casefold())
        except OSError as exc:
            errors.append(
                issue(
                    "error",
                    "input_error",
                    f"cannot scan root: {exc}",
                    path=root,
                )
            )
            continue
        for match in matches:
            if not match.is_file():
                continue
            try:
                resolved = match.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                errors.append(
                    issue(
                        "error",
                        "input_error",
                        f"SKILL.md cannot be resolved: {exc}",
                        path=match.absolute(),
                    )
                )
                continue
            discovered[str(resolved)] = resolved

    paths = sorted(discovered.values(), key=lambda item: str(item).casefold())
    if not paths and not errors:
        errors.append(
            issue(
                "error",
                "no_skill_files",
                "no SKILL.md files were found under the supplied roots",
            )
        )
    return paths, errors


def read_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise FrontmatterError(f"cannot read UTF-8 text: {exc}") from exc

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("missing opening YAML frontmatter delimiter")

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing_index is None:
        raise FrontmatterError("missing closing YAML frontmatter delimiter")

    frontmatter_text = "\n".join(lines[1:closing_index])
    try:
        payload = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = ""
        if mark is not None:
            location = f" at line {mark.line + 2}, column {mark.column + 1}"
        raise FrontmatterError(f"invalid YAML{location}") from exc

    if not isinstance(payload, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return payload


def parse_skill(path: Path, prefix_width: int) -> dict[str, Any]:
    frontmatter = read_frontmatter(path)
    description = frontmatter.get("description")
    if not isinstance(description, str):
        raise FrontmatterError("frontmatter description must be a string")
    if not description.strip():
        raise FrontmatterError("frontmatter description must not be empty")

    normalized = normalize_description(description)
    if not normalized:
        raise FrontmatterError("frontmatter description is empty after normalization")

    raw_name = frontmatter.get("name")
    name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else path.parent.name
    return {
        "name": name,
        "path": str(path),
        "description_chars": len(description),
        "normalized_prefix": normalized[:prefix_width],
        "generic_lead_in": generic_lead_in(normalized),
    }


def audit(
    roots: list[str],
    *,
    prefix_width: int,
    max_description_chars: int,
    strict: bool,
) -> dict[str, Any]:
    paths, errors = discover_skill_files(roots)
    warnings: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []
    overlong_descriptions = 0

    for path in paths:
        try:
            skill = parse_skill(path, prefix_width)
        except FrontmatterError as exc:
            errors.append(issue("error", "parse_error", str(exc), path=path))
            continue

        skills.append(skill)
        lead_in = skill["generic_lead_in"]
        if lead_in is not None:
            errors.append(
                issue(
                    "error",
                    "generic_lead_in",
                    f"description begins with generic lead-in {lead_in!r}",
                    path=path,
                    lead_in=lead_in,
                )
            )

        if skill["description_chars"] > max_description_chars:
            overlong_descriptions += 1
            severity = "error" if strict else "warning"
            finding = issue(
                severity,
                "description_too_long",
                (
                    f"description has {skill['description_chars']} characters; "
                    f"advisory maximum is {max_description_chars}"
                ),
                path=path,
                description_chars=skill["description_chars"],
                max_description_chars=max_description_chars,
            )
            (errors if strict else warnings).append(finding)

    prefix_groups: dict[str, list[dict[str, Any]]] = {}
    for skill in skills:
        prefix_groups.setdefault(skill["normalized_prefix"], []).append(skill)

    collisions: list[dict[str, Any]] = []
    for prefix, members in sorted(prefix_groups.items()):
        if len(members) < 2:
            continue
        member_paths = [Path(member["path"]) for member in members]
        collision = {
            "normalized_prefix": prefix,
            "paths": [str(path) for path in member_paths],
            "names": [member["name"] for member in members],
        }
        collisions.append(collision)
        severity = "error" if strict else "warning"
        finding = issue(
            severity,
            "prefix_collision",
            f"{len(members)} descriptions share the same normalized prefix",
            paths=member_paths,
            normalized_prefix=prefix,
            names=collision["names"],
        )
        (errors if strict else warnings).append(finding)

    generic_count = sum(1 for skill in skills if skill["generic_lead_in"] is not None)
    summary = {
        "skill_files": len(paths),
        "parsed_skills": len(skills),
        "errors": len(errors),
        "warnings": len(warnings),
        "generic_lead_ins": generic_count,
        "prefix_collisions": len(collisions),
        "overlong_descriptions": overlong_descriptions,
    }
    return {
        "schema": SCHEMA,
        "valid": not errors,
        "input": {
            "roots": roots,
            "prefix_width": prefix_width,
            "max_description_chars": max_description_chars,
            "strict": strict,
        },
        "generic_lead_ins": list(GENERIC_LEAD_INS),
        "summary": summary,
        "skills": skills,
        "collisions": collisions,
        "errors": errors,
        "warnings": warnings,
    }


def print_text_report(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print("Skill description prefix audit")
    for finding in [*payload["errors"], *payload["warnings"]]:
        location = finding.get("path")
        if location is None and finding.get("paths"):
            location = ", ".join(finding["paths"])
        suffix = f" ({location})" if location else ""
        print(
            f"{finding['severity'].upper()} [{finding['code']}] "
            f"{finding['message']}{suffix}"
        )
    if not payload["errors"] and not payload["warnings"]:
        print("OK no prefix-resilience findings")
    print(
        "SUMMARY "
        f"files={summary['skill_files']} parsed={summary['parsed_skills']} "
        f"errors={summary['errors']} warnings={summary['warnings']} "
        f"collisions={summary['prefix_collisions']}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="+",
        help="One or more SKILL.md files or directories to scan recursively.",
    )
    parser.add_argument(
        "--prefix-width",
        type=positive_int,
        default=DEFAULT_PREFIX_WIDTH,
        help=f"Normalized prefix width (default: {DEFAULT_PREFIX_WIDTH}).",
    )
    parser.add_argument(
        "--max-description-chars",
        type=positive_int,
        default=DEFAULT_MAX_DESCRIPTION_CHARS,
        help=(
            "Advisory description length limit "
            f"(default: {DEFAULT_MAX_DESCRIPTION_CHARS})."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Promote prefix collisions and description-length advisories to errors.",
    )
    parser.add_argument("--json", action="store_true", help="Emit a JSON report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)
    payload = audit(
        args.roots,
        prefix_width=args.prefix_width,
        max_description_chars=args.max_description_chars,
        strict=args.strict,
    )
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print_text_report(payload)
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
