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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plugin_catalog  # noqa: E402


ENCODING_NAME = "o200k_base"


@dataclass(frozen=True)
class SkillReport:
    plugin: str
    skill: str
    path: str
    description: str
    source_routing_tokens: int
    published_url_routing_tokens: int | None
    body_tokens: int


@dataclass(frozen=True)
class PluginReport:
    name: str
    description: str
    skill_count: int
    reference_count: int
    script_count: int
    source_routing_tokens: int
    published_url_routing_tokens: int | None
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


def routing_metadata_text(
    plugin_name: str,
    skill_name: str,
    description: str,
    source_path: str,
) -> str:
    """Serialize the comparable, source-relative routing estimate input."""

    return (
        f"name: {plugin_name}:{skill_name}\n"
        f"description: {description}\n"
        f"file: {source_path}\n"
    )


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


def count_named_support_files(plugin_dir: Path, directory_name: str) -> int:
    """Count files below every support directory, including skill-local ones."""

    files: set[Path] = set()
    for directory in plugin_dir.rglob(directory_name):
        if not directory.is_dir() or directory.name != directory_name:
            continue
        files.update(
            child
            for child in directory.rglob("*")
            if child.is_file()
            and child.suffix != ".pyc"
            and "__pycache__" not in child.parts
        )
    return len(files)


def collect_reports(root: Path, encoder: Any) -> tuple[list[PluginReport], list[SkillReport]]:
    skill_reports: list[SkillReport] = []
    plugin_reports: list[PluginReport] = []
    catalog = (
        plugin_catalog.validate_catalog(root)
        if (root / plugin_catalog.LOCKFILE_NAME).is_file()
        else {"plugins": []}
    )
    first_party = {item["name"]: item for item in catalog["plugins"]}

    for plugin_name in plugin_order(root):
        plugin_dir = root / "plugins" / plugin_name
        if not plugin_dir.is_dir():
            plugin = first_party.get(plugin_name)
            if plugin is None:
                continue
            receipt = plugin_catalog.receipt_for(root, plugin)
            plugin_skill_reports: list[SkillReport] = []
            for item in receipt["skills"]["items"]:
                description = normalize_text(item["description"])
                source_path = item["path"]
                plugin_skill_reports.append(
                    SkillReport(
                        plugin=plugin_name,
                        skill=item["name"],
                        path=source_path,
                        description=description,
                        source_routing_tokens=count_tokens(
                            encoder,
                            routing_metadata_text(
                                plugin_name,
                                item["name"],
                                description,
                                source_path,
                            ),
                        ),
                        published_url_routing_tokens=item["startupTokens"],
                        body_tokens=item["bodyTokens"],
                    )
                )
            skill_reports.extend(plugin_skill_reports)
            plugin_reports.append(
                PluginReport(
                    name=plugin_name,
                    description=normalize_text(plugin["description"]),
                    skill_count=receipt["skills"]["count"],
                    reference_count=receipt["counts"]["references"],
                    script_count=receipt["counts"]["scripts"],
                    source_routing_tokens=sum(
                        skill.source_routing_tokens
                        for skill in plugin_skill_reports
                    ),
                    published_url_routing_tokens=receipt["tokens"]["startup"],
                    body_tokens=receipt["tokens"]["body"],
                )
            )
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
            rel_path = skill_path.relative_to(plugin_dir).as_posix()
            report = SkillReport(
                plugin=plugin_name,
                skill=skill_name,
                path=rel_path,
                description=description,
                source_routing_tokens=count_tokens(
                    encoder,
                    routing_metadata_text(
                        plugin_name,
                        skill_name,
                        description,
                        rel_path,
                    ),
                ),
                published_url_routing_tokens=None,
                body_tokens=count_tokens(encoder, body),
            )
            plugin_skills.append(report)
            skill_reports.append(report)

        plugin_reports.append(
            PluginReport(
                name=plugin_name,
                description=normalize_text(plugin_description),
                skill_count=len(plugin_skills),
                reference_count=count_named_support_files(
                    plugin_dir, "references"
                ),
                script_count=count_named_support_files(plugin_dir, "scripts"),
                source_routing_tokens=sum(
                    skill.source_routing_tokens for skill in plugin_skills
                ),
                published_url_routing_tokens=None,
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


def fmt_optional_tokens(value: int | None) -> str:
    return "-" if value is None else fmt_int(value)


def render_markdown(plugin_reports: list[PluginReport], skill_reports: list[SkillReport]) -> str:
    source_routing_total = sum(
        plugin.source_routing_tokens for plugin in plugin_reports
    )
    published_url_routing_total = sum(
        plugin.published_url_routing_tokens or 0 for plugin in plugin_reports
    )
    published_url_skill_count = sum(
        1
        for skill in skill_reports
        if skill.published_url_routing_tokens is not None
    )
    body_total = sum(plugin.body_tokens for plugin in plugin_reports)
    reference_total = sum(plugin.reference_count for plugin in plugin_reports)
    script_total = sum(plugin.script_count for plugin in plugin_reports)

    lines: list[str] = []
    lines.extend(
        [
            "## Token Efficiency",
            "",
            "This collection is structured for progressive disclosure: lightweight",
            "routing metadata is kept separate from each `SKILL.md` instruction",
            "body.",
            "",
            "These estimates are generated with `scripts/token-report.py` using",
            f"`tiktoken` and the `{ENCODING_NAME}` encoding. Different agents may",
            "serialize, filter, truncate, or load skills differently. These are",
            "static source measurements, not evidence of what a host injects into",
            "a prompt or makes visible to a model at runtime.",
            "",
            "| Metric | Count | Tokens | Notes |",
            "| --- | ---: | ---: | --- |",
            f"| Plugin packs | {fmt_int(len(plugin_reports))} | - | Local packages plus immutable standalone first-party catalog entries. |",
            f"| Skill entrypoints | {fmt_int(len(skill_reports))} | - | `SKILL.md` files catalogued in local source or immutable receipts. |",
            f"| Reference files | {fmt_int(reference_total)} | - | Longer ledgers, contracts, scorecards, and source notes. |",
            f"| Script/support files | {fmt_int(script_total)} | - | All regular files below `scripts/`, including helpers, templates, and manifests. |",
            f"| Source-relative routing estimate | {fmt_int(len(skill_reports))} skills | {fmt_int(source_routing_total)} | Skill name, description, and plugin-relative `skills/.../SKILL.md` path; comparable across local and standalone sources. |",
            f"| Published first-party URL locator snapshot | {fmt_int(published_url_skill_count)} skills | {fmt_int(published_url_routing_total)} | Receipt values that serialize immutable GitHub blob URLs; preserved separately and not added to the source-relative total. |",
            f"| Skill body source estimate | {fmt_int(len(skill_reports))} skills | {fmt_int(body_total)} | Body text after frontmatter; not proof that a host loads it, or when. |",
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
            "Token columns are static source estimates. `Published URL routing`",
            "appears only for standalone first-party receipts and preserves their",
            "immutable GitHub locator snapshot.",
            "",
            "| Plugin | Skills | Refs | Script/support files | Source routing | Published URL routing | Body source |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
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
                    fmt_int(plugin.source_routing_tokens),
                    fmt_optional_tokens(plugin.published_url_routing_tokens),
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
            "Each row separates the comparable source-relative routing estimate",
            "from the publication receipt's URL-locator snapshot and body source",
            "size. None is a runtime prompt measurement.",
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
                "| Skill | Source routing | Published URL routing | Body source | Description |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for skill in plugin_skills:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{markdown_escape(skill.skill)}`",
                        fmt_int(skill.source_routing_tokens),
                        fmt_optional_tokens(skill.published_url_routing_tokens),
                        fmt_int(skill.body_tokens),
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
