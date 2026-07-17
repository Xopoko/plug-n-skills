#!/usr/bin/env python3
"""Estimate Codex model-visible skill metadata pressure for a concrete inventory.

The core phases and cost model mirror the pinned openai/codex renderer. Path
alias selection and cross-scope ordering depend on host discovery state, so the
audit deliberately uses absolute locators and reports that conservative bound.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA = "capability.codex_skill_catalog_audit.v1"
CODEX_SOURCE_SNAPSHOT = "315195492c80fdade38e917c18f9584efd599304"
METADATA_CONTEXT_PERCENT = 2
DEFAULT_METADATA_CHAR_BUDGET = 8_000
MAX_DESCRIPTION_CHARS = 1_024
TRUNCATION_SUFFIX = "..."
APPROX_BYTES_PER_TOKEN = 4
DESCRIPTION_WARNING_THRESHOLD = 100
MAX_SCAN_DEPTH = 6
MAX_SCAN_DIRECTORIES = 2_000
MAX_SCAN_ENTRIES = 20_000
PLUGIN_MANIFEST_PATHS = (
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
)


class AuditInputError(ValueError):
    """Raised when an inventory cannot be audited deterministically."""


@dataclass(frozen=True)
class Budget:
    mode: str
    limit: int

    def cost(self, text: str) -> int:
        if self.mode == "approx_tokens":
            return approx_tokens_from_bytes(len(text.encode("utf-8")))
        return len(text)

    def cost_from_counts(self, chars: int, bytes_count: int) -> int:
        if self.mode == "approx_tokens":
            return approx_tokens_from_bytes(bytes_count)
        return chars


@dataclass(frozen=True)
class SkillRecord:
    base_name: str
    name: str
    namespace: str | None
    raw_description: str
    source_description: str
    catalog_description: str
    path: Path
    explicit_only: bool


@dataclass(frozen=True)
class RenderedSkill:
    record: SkillRecord
    included: bool
    visible_description: str


def approx_tokens_from_bytes(bytes_count: int) -> int:
    return (bytes_count + APPROX_BYTES_PER_TOKEN - 1) // APPROX_BYTES_PER_TOKEN


def positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def strip_yaml_comment(value: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if in_double and char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            if index == 0 or value[index - 1].isspace():
                return value[:index].rstrip()
    return value


def parse_yaml_scalar(raw: str) -> Any:
    value = strip_yaml_comment(raw)
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return json.loads(value)
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def leading_spaces(line: str) -> int:
    prefix = line[: len(line) - len(line.lstrip(" "))]
    if "\t" in prefix:
        raise AuditInputError("tabs are not supported in YAML indentation")
    return len(prefix)


def consume_yaml_block(
    lines: list[str], start: int, parent_indent: int, marker: str
) -> tuple[str, int]:
    parts: list[str] = []
    block_indent: int | None = None
    index = start
    while index < len(lines):
        raw_line = lines[index]
        if not raw_line.strip():
            parts.append("")
            index += 1
            continue
        indent = leading_spaces(raw_line)
        if indent <= parent_indent:
            break
        if block_indent is None:
            block_indent = indent
        parts.append(raw_line[min(block_indent, len(raw_line)) :])
        index += 1
    if marker.startswith(">"):
        return " ".join(part.strip() for part in parts if part.strip()), index
    return "\n".join(parts), index


def parse_simple_yaml_mapping(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            index += 1
            continue
        indent = leading_spaces(raw_line)
        if stripped.startswith("- ") or ":" not in stripped:
            raise AuditInputError("unsupported YAML shape")
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        if not key:
            raise AuditInputError("empty YAML key")
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise AuditInputError("invalid YAML indentation")
        current = stack[-1][1]
        value = raw_value.strip()
        if not value:
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
            index += 1
            continue
        if value in {">", ">-", ">+", "|", "|-", "|+"}:
            block, index = consume_yaml_block(lines, index + 1, indent, value)
            current[key] = block
            continue
        current[key] = parse_yaml_scalar(value)
        index += 1
    return root


def load_yaml_mapping(text: str, label: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        payload = parse_simple_yaml_mapping(text)
    else:
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise AuditInputError(f"{label}: invalid YAML") from exc
    if not isinstance(payload, dict):
        raise AuditInputError(f"{label}: expected a YAML mapping")
    return payload


def skill_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditInputError(f"{path}: cannot read SKILL.md") from exc
    if not text.startswith("---\n"):
        raise AuditInputError(f"{path}: missing YAML frontmatter")
    end = text.find("\n---", 4)
    if end == -1:
        raise AuditInputError(f"{path}: unclosed YAML frontmatter")
    return load_yaml_mapping(text[4:end], str(path))


def openai_explicit_only(skill_dir: Path) -> bool:
    path = skill_dir / "agents" / "openai.yaml"
    if not path.is_file():
        return False
    try:
        payload = load_yaml_mapping(path.read_text(encoding="utf-8"), str(path))
    except OSError as exc:
        raise AuditInputError(f"{path}: cannot read agent metadata") from exc
    policy = payload.get("policy")
    if policy is None:
        return False
    if not isinstance(policy, dict):
        raise AuditInputError(f"{path}: policy must be a mapping")
    value = policy.get("allow_implicit_invocation")
    if value is not None and not isinstance(value, bool):
        raise AuditInputError(
            f"{path}: policy.allow_implicit_invocation must be a boolean"
        )
    return value is False


def cap_description(description: str) -> str:
    if len(description) <= MAX_DESCRIPTION_CHARS:
        return description
    prefix_chars = MAX_DESCRIPTION_CHARS - len(TRUNCATION_SUFFIX)
    return description[:prefix_chars] + TRUNCATION_SUFFIX


def normalize_single_line(raw: str) -> str:
    return " ".join(raw.split())


def nearest_codex_plugin_namespace(skill_path: Path) -> str | None:
    for directory in (skill_path.parent, *skill_path.parent.parents):
        manifest = next(
            (
                directory / relative_path
                for relative_path in PLUGIN_MANIFEST_PATHS
                if (directory / relative_path).is_file()
            ),
            None,
        )
        if manifest is None:
            continue
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        name = payload.get("name", "")
        if not isinstance(name, str):
            continue
        return name if name.strip() else directory.name
    return None


def discover_skill_files(inputs: list[str]) -> list[Path]:
    found: set[Path] = set()
    for raw in inputs:
        path = Path(raw).expanduser()
        if not path.exists():
            raise AuditInputError(f"{path}: input path does not exist")
        if path.is_file():
            if path.name != "SKILL.md":
                raise AuditInputError(f"{path}: file input must be named SKILL.md")
            found.add(path.resolve())
            continue
        pending = [(path, 0)]
        visited: set[Path] = set()
        directories_scanned = 0
        entries_scanned = 0
        while pending:
            directory, depth = pending.pop()
            resolved_directory = directory.resolve()
            if resolved_directory in visited:
                continue
            visited.add(resolved_directory)
            directories_scanned += 1
            if directories_scanned > MAX_SCAN_DIRECTORIES:
                raise AuditInputError(
                    f"{path}: scan exceeded {MAX_SCAN_DIRECTORIES} directories"
                )
            try:
                entries = sorted(directory.iterdir(), reverse=True)
            except OSError as exc:
                raise AuditInputError(f"{directory}: cannot scan directory") from exc
            entries_scanned += len(entries)
            if entries_scanned > MAX_SCAN_ENTRIES:
                raise AuditInputError(
                    f"{path}: scan exceeded {MAX_SCAN_ENTRIES} entries"
                )
            for entry in entries:
                if entry.name == "SKILL.md" and entry.is_file():
                    found.add(entry.resolve())
                    continue
                if (
                    depth < MAX_SCAN_DEPTH
                    and not entry.name.startswith(".")
                    and entry.is_dir()
                ):
                    pending.append((entry, depth + 1))
    if not found:
        raise AuditInputError("no SKILL.md files found in the supplied paths")
    return sorted(found, key=lambda path: path.as_posix())


def load_records(inputs: list[str]) -> list[SkillRecord]:
    records: list[SkillRecord] = []
    for path in discover_skill_files(inputs):
        frontmatter = skill_frontmatter(path)
        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if not isinstance(name, str) or not name.strip():
            raise AuditInputError(f"{path}: name must be a non-empty string")
        if not isinstance(description, str) or not description.strip():
            raise AuditInputError(f"{path}: description must be a non-empty string")
        base_name = normalize_single_line(name)
        raw_description = description
        source_description = normalize_single_line(description)
        namespace = nearest_codex_plugin_namespace(path)
        qualified_name = f"{namespace}:{base_name}" if namespace else base_name
        records.append(
            SkillRecord(
                base_name=base_name,
                name=qualified_name,
                namespace=namespace,
                raw_description=raw_description,
                source_description=source_description,
                catalog_description=cap_description(source_description),
                path=path,
                explicit_only=openai_explicit_only(path.parent),
            )
        )
    return records


def render_line(record: SkillRecord, description: str) -> str:
    locator = record.path.as_posix()
    if description:
        return f"- {record.name}: {description} (file: {locator})"
    return f"- {record.name}: (file: {locator})"


def line_cost(budget: Budget, line: str) -> int:
    return budget.cost(f"{line}\n")


def description_extra_costs(record: SkillRecord, budget: Budget) -> list[int]:
    minimum = f"{render_line(record, '')}\n"
    minimum_chars = len(minimum)
    minimum_bytes = len(minimum.encode("utf-8"))
    minimum_cost = budget.cost_from_counts(minimum_chars, minimum_bytes)
    costs = [0]
    prefix_chars = 0
    prefix_bytes = 0
    for char in record.catalog_description:
        prefix_chars += 1
        prefix_bytes += len(char.encode("utf-8"))
        rendered_chars = minimum_chars + prefix_chars + 1
        rendered_bytes = minimum_bytes + prefix_bytes + 1
        costs.append(
            budget.cost_from_counts(rendered_chars, rendered_bytes) - minimum_cost
        )
    return costs


def render_with_budget(
    records: list[SkillRecord], budget: Budget
) -> tuple[str, list[RenderedSkill], int, int]:
    implicit = sorted(
        (record for record in records if not record.explicit_only),
        key=lambda record: (record.name, record.path.as_posix()),
    )
    full_cost = sum(
        line_cost(budget, render_line(record, record.catalog_description))
        for record in implicit
    )
    minimum_cost = sum(
        line_cost(budget, render_line(record, "")) for record in implicit
    )
    if not implicit:
        return "no_implicit_skills", [], full_cost, minimum_cost
    if full_cost <= budget.limit:
        return (
            "full_metadata_visible",
            [RenderedSkill(record, True, record.catalog_description) for record in implicit],
            full_cost,
            minimum_cost,
        )
    if minimum_cost <= budget.limit:
        extra_costs = [description_extra_costs(record, budget) for record in implicit]
        allocations = [0] * len(implicit)
        current_costs = [0] * len(implicit)
        remaining = budget.limit - minimum_cost
        while True:
            changed = False
            for index, record in enumerate(implicit):
                if allocations[index] >= len(record.catalog_description):
                    continue
                next_chars = allocations[index] + 1
                next_cost = extra_costs[index][next_chars]
                delta = next_cost - current_costs[index]
                if delta <= remaining:
                    allocations[index] = next_chars
                    current_costs[index] = next_cost
                    remaining -= delta
                    changed = True
            if not changed:
                break
        rendered = [
            RenderedSkill(record, True, record.catalog_description[: allocations[index]])
            for index, record in enumerate(implicit)
        ]
        return "descriptions_shortened", rendered, full_cost, minimum_cost

    rendered: list[RenderedSkill] = []
    used = 0
    for record in implicit:
        cost = line_cost(budget, render_line(record, ""))
        included = used + cost <= budget.limit
        if included:
            used += cost
        rendered.append(RenderedSkill(record, included, ""))
    return "skills_omitted", rendered, full_cost, minimum_cost


def build_budget(
    context_window: int | None, metadata_token_cap: int | None
) -> tuple[Budget, int | None]:
    if context_window is None:
        if metadata_token_cap is not None:
            raise AuditInputError(
                "--metadata-token-cap requires --context-window token mode"
            )
        return Budget("characters", DEFAULT_METADATA_CHAR_BUDGET), None
    percent_limit = max(context_window * METADATA_CONTEXT_PERCENT // 100, 1)
    effective = (
        min(percent_limit, metadata_token_cap)
        if metadata_token_cap is not None
        else percent_limit
    )
    return Budget("approx_tokens", effective), percent_limit


def audit_payload(
    inputs: list[str], context_window: int | None, metadata_token_cap: int | None
) -> dict[str, Any]:
    records = load_records(inputs)
    budget, percent_limit = build_budget(context_window, metadata_token_cap)
    state, rendered, full_cost, minimum_cost = render_with_budget(records, budget)
    rendered_by_path = {row.record.path: row for row in rendered}
    name_counts: dict[str, int] = {}
    for record in records:
        name_counts[record.name] = name_counts.get(record.name, 0) + 1
    ambiguous_names = sorted(
        name for name, count in name_counts.items() if count > 1
    )
    implicit_records = [record for record in records if not record.explicit_only]
    included_count = sum(row.included for row in rendered)
    omitted_count = len(rendered) - included_count
    budget_removed = sum(
        len(row.record.catalog_description) - len(row.visible_description)
        for row in rendered
    )
    truncated_count = sum(
        len(row.visible_description) < len(row.record.catalog_description)
        for row in rendered
    )
    average_removed = (
        (budget_removed + len(implicit_records) - 1) // len(implicit_records)
        if implicit_records and budget_removed
        else 0
    )
    warning_kind: str | None = None
    if omitted_count:
        warning_kind = "skills_omitted"
    elif average_removed > DESCRIPTION_WARNING_THRESHOLD:
        warning_kind = "descriptions_shortened"

    visible_cost = sum(
        line_cost(budget, render_line(row.record, row.visible_description))
        for row in rendered
        if row.included
    )
    if visible_cost > budget.limit:
        raise RuntimeError("internal error: rendered metadata exceeds budget")

    rows = []
    for record in sorted(records, key=lambda item: (item.name, item.path.as_posix())):
        rendered_row = rendered_by_path.get(record.path)
        rows.append(
            {
                "name": record.name,
                "base_name": record.base_name,
                "namespace": record.namespace,
                "path": record.path.as_posix(),
                "explicit_only": record.explicit_only,
                "explicit_resolution_eligible": name_counts[record.name] == 1,
                "included_in_implicit_catalog": (
                    rendered_row.included if rendered_row is not None else False
                ),
                "raw_description_chars": len(record.raw_description),
                "source_description_chars": len(record.source_description),
                "catalog_description_chars": len(record.catalog_description),
                "visible_description_chars": (
                    len(rendered_row.visible_description)
                    if rendered_row is not None
                    else 0
                ),
                "description_prefix": (
                    rendered_row.visible_description if rendered_row is not None else ""
                ),
            }
        )

    return {
        "schema": SCHEMA,
        "valid": True,
        "source_model": {
            "codex_source_snapshot": CODEX_SOURCE_SNAPSHOT,
            "metadata_context_percent": METADATA_CONTEXT_PERCENT,
            "fallback_character_budget": DEFAULT_METADATA_CHAR_BUDGET,
            "maximum_description_characters": MAX_DESCRIPTION_CHARS,
            "approximate_bytes_per_token": APPROX_BYTES_PER_TOKEN,
            "description_warning_threshold_average_removed_chars": DESCRIPTION_WARNING_THRESHOLD,
            "maximum_scan_depth": MAX_SCAN_DEPTH,
            "maximum_scan_directories": MAX_SCAN_DIRECTORIES,
            "maximum_scan_entries": MAX_SCAN_ENTRIES,
            "path_model": "conservative_absolute_locators_without_alias_selection",
            "scope_model": "single_scope_name_then_path_order",
            "discovery_model": "recursive_exact_filename_hidden_descendants_skipped",
        },
        "input": {
            "paths": inputs,
            "context_window": context_window,
            "metadata_token_cap": metadata_token_cap,
            "budget_mode": budget.mode,
            "budget_limit": budget.limit,
            "two_percent_limit": percent_limit,
        },
        "summary": {
            "state": state,
            "discovered_skills": len(records),
            "enabled_inventory_skills_assumed": len(records),
            "ambiguous_explicit_skill_names": ambiguous_names,
            "ambiguous_explicit_skill_name_count": len(ambiguous_names),
            "implicit_catalog_skills": len(implicit_records),
            "explicit_only_skills_excluded": len(records) - len(implicit_records),
            "included_skills": included_count,
            "omitted_skills": omitted_count,
            "all_implicit_skill_names_visible": omitted_count == 0,
            "full_metadata_cost": full_cost,
            "minimum_name_path_cost": minimum_cost,
            "visible_metadata_cost": visible_cost,
            "remaining_metadata_budget": budget.limit - visible_cost,
            "budget_truncated_description_count": truncated_count,
            "budget_truncated_description_chars": budget_removed,
            "average_budget_truncated_description_chars": average_removed,
            "codex_thread_warning_expected": warning_kind is not None,
            "codex_thread_warning_kind": warning_kind,
        },
        "skills": rows,
        "caveats": [
            "Only supplied paths are modeled; a host-wide visibility claim requires every enabled implicitly invocable skill across system, admin, repo, and user scopes.",
            "Every discovered skill is treated as enabled; omit disabled paths from the supplied inventory. Explicit resolution is eligible only for unique qualified names.",
            "Codex may replace absolute paths with root aliases and preserve more metadata than this conservative path model.",
            "Actual hard-omission order ranks System, Admin, Repo, then User before name and path; this audit models one scope.",
            "Directory symlink traversal is followed with cycle detection; Codex symlink policy varies by skill scope.",
            "Host or app-server surfaces may impose a tighter cap; pass --metadata-token-cap when that cap is known.",
        ],
        "errors": [],
    }


def invalid_payload(message: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "valid": False,
        "errors": [message],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        help="Skill folders, plugin roots, skill roots, or SKILL.md files to audit.",
    )
    parser.add_argument(
        "--context-window",
        type=positive_int,
        help="Model context window in tokens. Omit to model the 8,000-character fallback.",
    )
    parser.add_argument(
        "--metadata-token-cap",
        type=positive_int,
        help="Optional tighter host metadata cap, applied after the 2 percent calculation.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the typed JSON audit.")
    args = parser.parse_args()

    try:
        payload = audit_payload(
            args.paths,
            context_window=args.context_window,
            metadata_token_cap=args.metadata_token_cap,
        )
    except AuditInputError as exc:
        payload = invalid_payload(str(exc))
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"invalid: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    summary = payload["summary"]
    audit_input = payload["input"]
    print(
        f"state={summary['state']} skills={summary['implicit_catalog_skills']} "
        f"included={summary['included_skills']} omitted={summary['omitted_skills']} "
        f"budget={audit_input['budget_limit']}:{audit_input['budget_mode']} "
        f"full={summary['full_metadata_cost']} minimum={summary['minimum_name_path_cost']}"
    )
    print(
        "all_names_visible="
        f"{int(summary['all_implicit_skill_names_visible'])} "
        f"truncated_descriptions={summary['budget_truncated_description_count']} "
        f"warning_expected={int(summary['codex_thread_warning_expected'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
