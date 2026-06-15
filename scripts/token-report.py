#!/usr/bin/env python3
"""Generate token-efficiency tables for the Plug'n Skills README."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ENCODING_NAME = "o200k_base"


@dataclass(frozen=True)
class SkillReport:
    plugin: str
    skill: str
    path: str
    description: str
    startup_tokens: int
    body_tokens: int


@dataclass(frozen=True)
class PluginReport:
    name: str
    description: str
    skill_count: int
    reference_count: int
    script_count: int
    startup_tokens: int
    body_tokens: int


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_encoder() -> Any:
    try:
        import tiktoken
    except ImportError as exc:
        raise SystemExit(
            "scripts/token-report.py requires tiktoken. Install it with "
            "`python3 -m pip install tiktoken`."
        ) from exc
    return tiktoken.get_encoding(ENCODING_NAME)


def count_tokens(encoder: Any, text: str) -> int:
    return len(encoder.encode(text))


def normalize_newlines(text: str) -> str:
    """Make token counts stable across Git checkouts with CRLF or LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def plugin_order(root: Path) -> list[str]:
    marketplace = root / ".claude-plugin" / "marketplace.json"
    if marketplace.is_file():
        data = json.loads(marketplace.read_text(encoding="utf-8"))
        plugins = data.get("plugins", [])
        if isinstance(plugins, list):
            names = [entry.get("name") for entry in plugins if isinstance(entry, dict)]
            return [name for name in names if isinstance(name, str)]
    return sorted(path.name for path in (root / "plugins").iterdir() if path.is_dir())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text

    frontmatter = text[4:end].strip("\n")
    body_start = text.find("\n", end + 4)
    body = text[body_start + 1 :] if body_start != -1 else ""
    return parse_simple_yaml(frontmatter), body


def parse_simple_yaml(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        match = re.match(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$", line)
        if not match:
            i += 1
            continue
        key, value = match.group(1), (match.group(2) or "").strip()
        if value in {">", ">-", "|", "|-"}:
            block: list[str] = []
            i += 1
            while i < len(lines):
                next_line = lines[i]
                if re.match(r"^[A-Za-z0-9_-]+:", next_line):
                    break
                block.append(next_line.strip())
                i += 1
            if value.startswith(">"):
                fields[key] = " ".join(part for part in block if part)
            else:
                fields[key] = "\n".join(block)
            continue
        fields[key] = value.strip("'\"")
        i += 1
    return fields


def count_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for child in path.rglob("*") if child.is_file() and child.suffix != ".pyc")


def collect_reports(root: Path, encoder: Any) -> tuple[list[PluginReport], list[SkillReport]]:
    skill_reports: list[SkillReport] = []
    plugin_reports: list[PluginReport] = []

    for plugin_name in plugin_order(root):
        plugin_dir = root / "plugins" / plugin_name
        if not plugin_dir.is_dir():
            continue
        manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
        manifest = read_json(manifest_path) if manifest_path.is_file() else {}
        plugin_description = str(manifest.get("description", ""))
        plugin_skills: list[SkillReport] = []

        for skill_path in sorted(plugin_dir.glob("skills/*/SKILL.md")):
            text = normalize_newlines(skill_path.read_text(encoding="utf-8"))
            fields, body = parse_frontmatter(text)
            skill_name = fields.get("name") or skill_path.parent.name
            description = normalize_text(fields.get("description", ""))
            rel_path = skill_path.relative_to(root).as_posix()
            startup_text = (
                f"name: {plugin_name}:{skill_name}\n"
                f"description: {description}\n"
                f"file: {rel_path}\n"
            )
            report = SkillReport(
                plugin=plugin_name,
                skill=skill_name,
                path=rel_path,
                description=description,
                startup_tokens=count_tokens(encoder, startup_text),
                body_tokens=count_tokens(encoder, body),
            )
            plugin_skills.append(report)
            skill_reports.append(report)

        plugin_reports.append(
            PluginReport(
                name=plugin_name,
                description=normalize_text(plugin_description),
                skill_count=len(plugin_skills),
                reference_count=count_files(plugin_dir / "references"),
                script_count=count_files(plugin_dir / "scripts"),
                startup_tokens=sum(skill.startup_tokens for skill in plugin_skills),
                body_tokens=sum(skill.body_tokens for skill in plugin_skills),
            )
        )

    return plugin_reports, skill_reports


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def markdown_escape(value: str) -> str:
    value = value.replace("\\", "\\\\")
    value = value.replace("|", "\\|")
    value = value.replace("\n", "<br>")
    return value


def fmt_int(value: int) -> str:
    return f"{value:,}"


def fmt_tokens(startup: int, body: int) -> str:
    return f"{fmt_int(startup)}/{fmt_int(body)}"


def render_markdown(plugin_reports: list[PluginReport], skill_reports: list[SkillReport]) -> str:
    startup_total = sum(plugin.startup_tokens for plugin in plugin_reports)
    body_total = sum(plugin.body_tokens for plugin in plugin_reports)
    reference_total = sum(plugin.reference_count for plugin in plugin_reports)
    script_total = sum(plugin.script_count for plugin in plugin_reports)

    lines: list[str] = []
    lines.extend(
        [
            "## Token Efficiency",
            "",
            "This collection is designed around progressive disclosure. Agents can",
            "route from lightweight metadata first, then load the selected",
            "`SKILL.md` body only for the chosen workflow.",
            "",
            "These estimates are generated with `scripts/token-report.py` using",
            f"`tiktoken` and the `{ENCODING_NAME}` encoding. Different agents may",
            "wrap metadata differently, so the exact number is less important than",
            "the split between always-visible routing metadata and on-demand skill",
            "instructions.",
            "",
            "| Metric | Count | Tokens | Notes |",
            "| --- | ---: | ---: | --- |",
            f"| Plugin packs | {fmt_int(len(plugin_reports))} | - | Installable packages under `plugins/`. |",
            f"| Skill entrypoints | {fmt_int(len(skill_reports))} | - | `SKILL.md` files exposed through plugin metadata. |",
            f"| Reference files | {fmt_int(reference_total)} | - | Longer ledgers, contracts, scorecards, and source notes. |",
            f"| Helper and validator scripts | {fmt_int(script_total)} | - | Deterministic plugin-local helpers. |",
            f"| Startup metadata | {fmt_int(len(skill_reports))} skills | {fmt_int(startup_total)} | Skill name, description, and file pointer for routing. |",
            f"| On-demand skill bodies | {fmt_int(len(skill_reports))} skills | {fmt_int(body_total)} | Instruction bodies after frontmatter, loaded only when selected. |",
            "",
            "Regenerate the report after skill edits:",
            "",
            "```bash",
            "python3 scripts/token-report.py",
            "```",
            "",
            "### Plugin Token Rollup",
            "",
            "Descriptions are split from the numeric rollup so GitHub does not",
            "compress long prose into narrow table cells.",
            "",
            "Token columns are `startup metadata / on-demand body`.",
            "",
            "| Plugin | Skills | Refs | Scripts | Startup | Body |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for plugin in plugin_reports:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{markdown_escape(plugin.name)}`",
                    fmt_int(plugin.skill_count),
                    fmt_int(plugin.reference_count),
                    fmt_int(plugin.script_count),
                    fmt_int(plugin.startup_tokens),
                    fmt_int(plugin.body_tokens),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "### Plugin Focus",
            "",
            "| Plugin | Description |",
            "| --- | --- |",
        ]
    )

    for plugin in plugin_reports:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{markdown_escape(plugin.name)}`",
                    markdown_escape(plugin.description),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "### Skill Token Index",
            "",
            "Token cells are shown as `startup/body`.",
        ]
    )

    skills_by_plugin: dict[str, list[SkillReport]] = {
        plugin.name: [] for plugin in plugin_reports
    }
    for skill in skill_reports:
        skills_by_plugin.setdefault(skill.plugin, []).append(skill)

    for plugin in plugin_reports:
        plugin_skills = skills_by_plugin.get(plugin.name, [])
        if not plugin_skills:
            continue
        lines.extend(
            [
                "",
                f"#### `{markdown_escape(plugin.name)}`",
                "",
                "| Skill | Tokens | Description |",
                "| --- | ---: | --- |",
            ]
        )
        for skill in plugin_skills:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{markdown_escape(skill.skill)}`",
                        fmt_tokens(
                            skill.startup_tokens,
                            skill.body_tokens,
                        ),
                        markdown_escape(skill.description),
                    ]
                )
                + " |"
            )

    return "\n".join(lines) + "\n"


def render_json(plugin_reports: list[PluginReport], skill_reports: list[SkillReport]) -> str:
    payload = {
        "encoding": ENCODING_NAME,
        "plugins": [plugin.__dict__ for plugin in plugin_reports],
        "skills": [
            {
                **{k: v for k, v in skill.__dict__.items() if k != "path"},
                "path": skill.path,
            }
            for skill in skill_reports
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"



README_SECTION_START = "## Token Efficiency"


def splice_readme(readme_text: str, rendered: str) -> str:
    """Replace the README's auto-generated token section with `rendered`.

    The managed region starts at README_SECTION_START and ends just before
    the next second-level heading. Raises ValueError when the markers are
    missing so callers fail loudly instead of appending duplicates.
    """
    start = readme_text.find(README_SECTION_START)
    if start == -1:
        raise ValueError(f"README has no '{README_SECTION_START}' section")
    end = readme_text.find("\n## ", start + len(README_SECTION_START))
    if end == -1:
        raise ValueError("README has no section after the token region")
    return readme_text[:start] + rendered.rstrip("\n") + "\n\n" + readme_text[end + 1:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format. Defaults to markdown.",
    )
    parser.add_argument(
        "--update-readme",
        action="store_true",
        help="Rewrite README.md's auto-generated token section in place.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if README.md's token section differs from a fresh render.",
    )
    args = parser.parse_args()

    root = repo_root()
    encoder = load_encoder()
    plugin_reports, skill_reports = collect_reports(root, encoder)
    if args.update_readme or args.check:
        readme = root / "README.md"
        rendered = render_markdown(plugin_reports, skill_reports)
        current_readme = normalize_newlines(readme.read_text(encoding="utf-8"))
        updated = splice_readme(current_readme, rendered)
        if args.check:
            if updated != current_readme:
                sys.stderr.write("README token section is stale; run "
                                 "scripts/token-report.py --update-readme\n")
                raise SystemExit(1)
            print("README token section is current")
            return
        readme.write_text(updated, encoding="utf-8")
        print("README token section updated")
        return
    if args.format == "json":
        sys.stdout.write(render_json(plugin_reports, skill_reports))
    else:
        sys.stdout.write(render_markdown(plugin_reports, skill_reports))


if __name__ == "__main__":
    main()
