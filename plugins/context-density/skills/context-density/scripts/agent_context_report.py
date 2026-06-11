#!/usr/bin/env python3
"""Read-only agent runtime context diagnostics.

This script is a portable runtime-context reporter for local files and
installed agent surfaces, without depending on a machine-local binary or Codex
app-server internals.

Supported commands:
  agents, brief/status, sources, skills, skill NAME, mcp, mcp --tools SERVER,
  export json|csv|markdown

Supported common options:
  --agent codex|claude|cursor, --agent-home PATH, --codex-home PATH, --project PATH,
  --usage, --no-usage, --no-introspect-mcp, --limit N, --json, --ndjson.

The script reads local files only and never mutates host-agent configuration.
MCP reports are config-only unless a future public schema-introspection surface
is added.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from token_count import count_text, load_encoder, read_text


DEFAULT_ENCODING = "o200k_base"
SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
CODEX_MCP_SECTION_RE = re.compile(r"^mcp_servers\.([A-Za-z0-9_-]+)(?:\.(env))?$")
SENSITIVE_KEY_RE = re.compile(
    r"\b(?:api[_-]?key|token|secret|password|credential|bearer|auth|private[_-]?key)\b",
    re.IGNORECASE,
)


SOURCE_TYPE_BASE_RUNTIME = "Base Runtime"
SOURCE_TYPE_USER_CONFIG = "User Instructions / Config"
SOURCE_TYPE_SKILLS_METADATA = "Skills Metadata"
SOURCE_TYPE_LOADED_SKILL_BODIES = "Loaded Skill Bodies"
SOURCE_TYPE_MCP_TOOL_SCHEMAS = "MCP Tool Schemas"
SOURCE_TYPE_PLUGINS = "Plugins"
SOURCE_TYPE_MEMORY_PROJECT_CONTEXT = "Memory / Project Context"

SOURCE_TYPE_ORDER = [
    SOURCE_TYPE_BASE_RUNTIME,
    SOURCE_TYPE_USER_CONFIG,
    SOURCE_TYPE_SKILLS_METADATA,
    SOURCE_TYPE_LOADED_SKILL_BODIES,
    SOURCE_TYPE_MCP_TOOL_SCHEMAS,
    SOURCE_TYPE_PLUGINS,
    SOURCE_TYPE_MEMORY_PROJECT_CONTEXT,
]


@dataclass(frozen=True)
class AgentEnvironment:
    id: str
    name: str
    home: Path
    installed: bool
    active: bool = False


@dataclass(frozen=True)
class SkillEntry:
    name: str
    metadataTokens: int
    bodyTokens: int
    totalTokens: int
    disabledTokens: int
    startupLoaded: bool
    onDemandLoaded: bool
    bodyReadCount: int
    bodySessionCount: int
    referenceReadCount: int
    referenceTokens: int
    path: str
    disabled: bool
    source: str
    description: str


@dataclass(frozen=True)
class SourceEntry:
    source: str
    type: str
    tokens: int
    disabledTokens: int
    startupLoaded: bool
    onDemandLoaded: bool
    path: str
    serverName: str | None = None
    pluginName: str | None = None
    skillName: str | None = None
    lines: int = 0
    detail: str = ""


@dataclass(frozen=True)
class McpToolEntry:
    name: str
    tokens: int
    nameTokens: int
    descriptionTokens: int
    inputSchemaTokens: int
    disabled: bool


@dataclass(frozen=True)
class McpServerEntry:
    name: str
    enabled: bool
    schemaTokens: int
    disabledTokens: int
    activeToolCount: int
    disabledToolCount: int
    configPath: str | None
    transport: str
    error: str | None
    tools: list[McpToolEntry] | None
    command: str | None = None
    url: str | None = None
    lines: int = 0


@dataclass(frozen=True)
class TokenUsage:
    inputTokens: int = 0
    cachedInputTokens: int = 0
    outputTokens: int = 0
    reasoningOutputTokens: int = 0
    totalTokens: int = 0


@dataclass(frozen=True)
class SessionSummary:
    id: str | None
    path: str
    latestUsage: TokenUsage | None
    cumulativeUsage: TokenUsage | None
    contextWindow: int | None
    modelCallCount: int


AGENT_HOMES = {
    "codex": ("CODEX_HOME", "~/.codex"),
    "claude": ("CLAUDE_HOME", "~/.claude"),
    "cursor": ("CURSOR_HOME", "~/.cursor"),
}
AGENT_NAMES = {"codex": "Codex", "claude": "Claude Code", "cursor": "Cursor"}


def default_home(agent: str) -> Path:
    env_var, fallback = AGENT_HOMES.get(agent, AGENT_HOMES["codex"])
    return Path(os.environ.get(env_var, fallback)).expanduser()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


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


def display_path(path: Path | str, env_home: Path, project: Path | None) -> str:
    raw = Path(path).expanduser()
    roots: list[tuple[Path, str]] = []
    if project is not None:
        roots.append((project, "."))
    roots.append((env_home, "$AGENT_HOME"))
    roots.append((Path.home(), "~"))
    for root, prefix in roots:
        try:
            rel = raw.resolve().relative_to(root.expanduser().resolve())
            return str(Path(prefix) / rel)
        except Exception:
            continue
    return str(path)


def abbreviate_home(path: Path | str) -> str:
    raw = Path(path).expanduser()
    try:
        rel = raw.resolve().relative_to(Path.home().resolve())
        return str(Path("~") / rel)
    except Exception:
        return str(path)


def scrub_url(url: str) -> str:
    """Strip credentials from a URL: drop userinfo, redact query values, drop fragment."""
    from urllib.parse import parse_qsl, urlsplit, urlunsplit

    try:
        parts = urlsplit(url)
    except ValueError:
        return "<redacted-url>"
    netloc = parts.hostname or ""
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    query = ""
    if parts.query:
        names = [name for name, _ in parse_qsl(parts.query, keep_blank_values=True)]
        query = "&".join(f"{name}=<redacted>" for name in names)
    return urlunsplit((parts.scheme, netloc, parts.path, query, ""))


def display_command(value: str | None, env_home: Path) -> str | None:
    if not value:
        return value
    if SENSITIVE_KEY_RE.search(value):
        return "<redacted-command>"
    home = str(Path.home())
    agent_home = str(env_home.expanduser())
    if value == agent_home:
        return "$AGENT_HOME"
    if value.startswith(agent_home + os.sep):
        return "$AGENT_HOME" + value[len(agent_home) :]
    if value == home:
        return "~"
    if value.startswith(home + os.sep):
        return "~" + value[len(home) :]
    return value


def count_lines(text: str) -> int:
    return text.count("\n") + (1 if text else 0)


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def emit(value: Any, *, ndjson: bool = False) -> None:
    if ndjson and isinstance(value, list):
        for item in value:
            print(json_dump(item))
        return
    print(json_dump(value))


def table(rows: list[list[str]], headers: list[str]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = [
        "  ".join(header.ljust(widths[i]) for i, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "..."


def iter_files_named(root: Path, name: str) -> Iterable[Path]:
    if not root.is_dir():
        return []
    return (path for path in root.rglob(name) if path.is_file())


def installed_agents(active_id: str | None = None) -> list[AgentEnvironment]:
    return [
        AgentEnvironment(
            id=agent,
            name=AGENT_NAMES[agent],
            home=default_home(agent),
            installed=default_home(agent).is_dir(),
            active=active_id == agent,
        )
        for agent in AGENT_HOMES
    ]


def resolve_agent(args: argparse.Namespace) -> AgentEnvironment:
    requested = getattr(args, "agent", None)
    if requested is None:
        installed = [agent for agent in AGENT_HOMES if default_home(agent).is_dir()]
        requested = installed[0] if installed else "codex"
    home = Path(args.agent_home or default_home(requested)).expanduser()
    return AgentEnvironment(
        id=requested,
        name=AGENT_NAMES.get(requested, requested),
        home=home,
        installed=home.is_dir(),
        active=True,
    )


def project_path(args: argparse.Namespace) -> Path | None:
    raw = getattr(args, "project", None)
    if raw is None:
        return None
    return Path(raw).expanduser().resolve()


def codex_config_files(agent_home: Path, project: Path | None) -> list[Path]:
    files = [agent_home / "config.toml"]
    if project is not None:
        files.append(project / ".codex" / "config.toml")
    return [path for path in files if path.is_file()]


def claude_config_files(agent_home: Path, project: Path | None) -> list[Path]:
    files = [
        agent_home / "CLAUDE.md",
        agent_home / "settings.json",
    ]
    if project is not None:
        files.extend(
            [
                project / "CLAUDE.md",
                project / ".claude" / "settings.json",
                project / ".mcp.json",
            ]
        )
    return [path for path in files if path.is_file()]


def config_files(env: AgentEnvironment, project: Path | None) -> list[Path]:
    if env.id == "claude":
        return claude_config_files(env.home, project)
    return codex_config_files(env.home, project)


def skill_roots(env: AgentEnvironment, project: Path | None) -> list[Path]:
    if env.id == "claude":
        roots = [
            env.home / "skills",
            env.home / "plugins" / "cache",
            Path.home() / ".agents" / "skills",
        ]
        if project is not None:
            roots.extend([project / ".claude" / "skills", project / ".agents" / "skills"])
        return roots
    roots = [
        env.home / "skills",
        env.home / "plugins" / "cache",
        Path.home() / ".agents" / "skills",
    ]
    if project is not None:
        roots.extend(
            [
                project / ".agents" / "skills",
                project / ".codex" / "skills",
                project / ".codex" / "plugins" / "cache",
            ]
        )
    return roots


def plugin_manifest_roots(env: AgentEnvironment, project: Path | None) -> list[Path]:
    roots = [env.home / "plugins" / "cache"]
    if project is not None:
        if env.id == "claude":
            roots.append(project / ".claude" / "plugins")
        else:
            roots.append(project / ".codex" / "plugins" / "cache")
    return roots


def memory_files(env: AgentEnvironment, project: Path | None) -> list[Path]:
    if env.id == "claude":
        files = [env.home / "CLAUDE.md"]
        if project is not None:
            files.extend([project / "CLAUDE.md", project / ".claude" / "CLAUDE.md"])
        return [path for path in files if path.is_file()]
    files = [env.home / "AGENTS.md", env.home / "memories" / "memory_summary.md"]
    if project is not None:
        files.extend(
            [
                project / "AGENTS.md",
                project / ".codex" / "AGENTS.md",
                project / ".codex" / "memories" / "memory_summary.md",
            ]
        )
    return [path for path in files if path.is_file()]


def skill_files(env: AgentEnvironment, project: Path | None) -> list[Path]:
    found: set[Path] = set()
    for root in skill_roots(env, project):
        if root.is_dir():
            found.update(root.rglob("SKILL.md"))
    return sorted(path for path in found if path.is_file())


def plugin_name_for_skill(path: Path) -> str | None:
    parts = path.parts
    if "cache" not in parts:
        return None
    try:
        cache_index = parts.index("cache")
        return parts[cache_index + 2]
    except Exception:
        return None


def skill_source(path: Path, env: AgentEnvironment) -> str:
    parts = path.parts
    if "plugins" in parts and "cache" in parts:
        try:
            cache_index = parts.index("cache")
            return f"plugin:{parts[cache_index + 1]}/{parts[cache_index + 2]}"
        except Exception:
            return "plugin-cache"
    try:
        path.resolve().relative_to((env.home / "skills" / ".system").resolve())
        return "system-skill"
    except Exception:
        pass
    try:
        path.resolve().relative_to((env.home / "skills").resolve())
        return "user-skill"
    except Exception:
        return "project-or-shared-skill"


def collect_skills(env: AgentEnvironment, project: Path | None, encoder: Any) -> list[SkillEntry]:
    result: list[SkillEntry] = []
    for path in skill_files(env, project):
        text = read_text(path)
        if text is None:
            continue
        fields, body = parse_frontmatter(text)
        name = normalize_text(fields.get("name") or path.parent.name)
        description = normalize_text(fields.get("description", ""))
        plugin = plugin_name_for_skill(path)
        display_name = f"{plugin}:{name}" if plugin else name
        startup_text = f"name: {display_name}\ndescription: {description}\nfile: {display_path(path, env.home, project)}\n"
        metadata_tokens = count_text(startup_text, encoder)
        body_tokens = count_text(body, encoder)
        result.append(
            SkillEntry(
                name=display_name,
                metadataTokens=metadata_tokens,
                bodyTokens=body_tokens,
                totalTokens=metadata_tokens + body_tokens,
                disabledTokens=0,
                startupLoaded=True,
                onDemandLoaded=True,
                bodyReadCount=0,
                bodySessionCount=0,
                referenceReadCount=0,
                referenceTokens=0,
                path=display_path(path, env.home, project),
                disabled=False,
                source=skill_source(path, env),
                description=description,
            )
        )
    result.sort(key=lambda item: (-item.totalTokens, item.name))
    return result


def collect_config_sources(env: AgentEnvironment, project: Path | None, encoder: Any) -> list[SourceEntry]:
    rows: list[SourceEntry] = []
    for path in config_files(env, project):
        text = read_text(path)
        if text is None:
            continue
        sanitized = "\n".join(sanitize_config_line(line) for line in text.splitlines())
        rows.append(
            SourceEntry(
                source=path.name,
                type=SOURCE_TYPE_USER_CONFIG,
                tokens=count_text(sanitized, encoder),
                disabledTokens=0,
                startupLoaded=True,
                onDemandLoaded=False,
                path=display_path(path, env.home, project),
                lines=count_lines(text),
            )
        )
    return rows


def collect_memory_sources(env: AgentEnvironment, project: Path | None, encoder: Any) -> list[SourceEntry]:
    rows: list[SourceEntry] = []
    for path in memory_files(env, project):
        text = read_text(path)
        if text is None:
            continue
        rows.append(
            SourceEntry(
                source=path.name,
                type=SOURCE_TYPE_MEMORY_PROJECT_CONTEXT,
                tokens=count_text(text, encoder),
                disabledTokens=0,
                startupLoaded=True,
                onDemandLoaded=False,
                path=display_path(path, env.home, project),
                lines=count_lines(text),
            )
        )
    return rows


def collect_plugin_sources(env: AgentEnvironment, project: Path | None, encoder: Any) -> list[SourceEntry]:
    rows: list[SourceEntry] = []
    marker = "/.claude-plugin/" if env.id == "claude" else "/.codex-plugin/"
    for root in plugin_manifest_roots(env, project):
        if not root.is_dir():
            continue
        for path in sorted(iter_files_named(root, "plugin.json")):
            normalized = path.as_posix()
            if marker not in normalized:
                continue
            text = read_text(path)
            if text is None:
                continue
            plugin = path.parent.parent.name
            rows.append(
                SourceEntry(
                    source=plugin,
                    type=SOURCE_TYPE_PLUGINS,
                    tokens=count_text(text, encoder),
                    disabledTokens=0,
                    startupLoaded=True,
                    onDemandLoaded=False,
                    path=display_path(path, env.home, project),
                    pluginName=plugin,
                    lines=count_lines(text),
                )
            )
    return rows


def sanitize_config_line(line: str) -> str:
    if "=" not in line:
        return line
    key, value = line.split("=", 1)
    if SENSITIVE_KEY_RE.search(key) or SENSITIVE_KEY_RE.search(value):
        return f"{key.rstrip()} = \"<redacted>\""
    return line


def strip_toml_comment(line: str) -> str:
    in_quote = False
    quote = ""
    out = []
    for char in line:
        if char in {"\"", "'"}:
            if not in_quote:
                in_quote = True
                quote = char
            elif quote == char:
                in_quote = False
        if char == "#" and not in_quote:
            break
        out.append(char)
    return "".join(out)


def unquote(value: str) -> str:
    value = value.strip()
    if (value.startswith("\"") and value.endswith("\"")) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def parse_inline_array(value: str) -> list[str]:
    value = value.strip()
    if not value.startswith("[") or not value.endswith("]"):
        return []
    inner = value[1:-1]
    result: list[str] = []
    current = []
    in_quote = False
    quote = ""
    for char in inner:
        if char in {"\"", "'"}:
            if not in_quote:
                in_quote = True
                quote = char
                continue
            if quote == char:
                in_quote = False
                continue
        if char == "," and not in_quote:
            item = unquote("".join(current).strip())
            if item:
                result.append(item)
            current = []
        else:
            current.append(char)
    item = unquote("".join(current).strip())
    if item:
        result.append(item)
    return result


def read_toml_sections(path: Path) -> list[tuple[str, int, list[str]]]:
    text = read_text(path)
    if text is None:
        return []
    sections: list[tuple[str, int, list[str]]] = []
    current = ""
    current_start = 1
    current_lines: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = SECTION_RE.match(line)
        if match:
            if current:
                sections.append((current, current_start, current_lines))
            current = match.group(1)
            current_start = line_no
            current_lines = [line]
            continue
        if current:
            current_lines.append(line)
    if current:
        sections.append((current, current_start, current_lines))
    return sections


def parse_codex_mcp_config(path: Path, env: AgentEnvironment, project: Path | None, encoder: Any) -> list[McpServerEntry]:
    grouped: dict[str, dict[str, Any]] = {}
    for section, start_line, lines in read_toml_sections(path):
        match = CODEX_MCP_SECTION_RE.match(section)
        if not match:
            continue
        name = match.group(1)
        is_env = match.group(2) == "env"
        group = grouped.setdefault(
            name,
            {
                "start": start_line,
                "lines": 0,
                "tokens": 0,
                "command": None,
                "url": None,
                "enabled": True,
                "enabled_tools": [],
                "disabled_tools": [],
            },
        )
        group["start"] = min(group["start"], start_line)
        group["lines"] += len(lines)
        sanitized = "\n".join(sanitize_config_line(line) for line in lines)
        group["tokens"] += count_text(sanitized, encoder)
        if is_env:
            continue
        for raw_line in lines:
            line = strip_toml_comment(raw_line).strip()
            if "=" not in line:
                continue
            key, value = [part.strip() for part in line.split("=", 1)]
            if key == "command":
                group["command"] = display_command(unquote(value), env.home)
            elif key == "url":
                group["url"] = unquote(value)
            elif key == "enabled":
                group["enabled"] = value.lower() != "false"
            elif key == "enabled_tools":
                group["enabled_tools"] = parse_inline_array(value)
            elif key == "disabled_tools":
                group["disabled_tools"] = parse_inline_array(value)
    servers: list[McpServerEntry] = []
    for name, values in grouped.items():
        enabled_tools = values["enabled_tools"]
        disabled_tools = values["disabled_tools"]
        listed_tools = sorted(set(enabled_tools + disabled_tools))
        tools = [
            McpToolEntry(
                name=tool,
                tokens=count_text(tool, encoder),
                nameTokens=count_text(tool, encoder),
                descriptionTokens=0,
                inputSchemaTokens=0,
                disabled=tool in disabled_tools,
            )
            for tool in listed_tools
        ]
        servers.append(
            McpServerEntry(
                name=name,
                enabled=bool(values["enabled"]),
                schemaTokens=int(values["tokens"]),
                disabledTokens=0,
                activeToolCount=max(0, len(listed_tools) - len(disabled_tools)),
                disabledToolCount=len(disabled_tools),
                configPath=f"{display_path(path, env.home, project)}:{values['start']}",
                transport="streamableHTTP" if values["url"] else "stdio",
                error="config-only; live MCP schema introspection is not implemented",
                tools=tools,
                command=values["command"],
                url=scrub_url(values["url"]) if values["url"] else None,
                lines=int(values["lines"]),
            )
        )
    return servers


def parse_claude_mcp_json(path: Path, env: AgentEnvironment, project: Path | None, encoder: Any) -> list[McpServerEntry]:
    text = read_text(path)
    if text is None:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    servers = data.get("mcpServers") or data.get("mcp_servers") or {}
    if not isinstance(servers, dict):
        return []
    result: list[McpServerEntry] = []
    for name, value in servers.items():
        if not isinstance(value, dict):
            continue
        disabled_tools = value.get("disabledTools") or value.get("disabled_tools") or []
        enabled_tools = value.get("enabledTools") or value.get("enabled_tools") or []
        if not isinstance(disabled_tools, list):
            disabled_tools = []
        if not isinstance(enabled_tools, list):
            enabled_tools = []
        listed_tools = sorted({str(item) for item in [*enabled_tools, *disabled_tools]})
        blob = json.dumps(redact_json(value), sort_keys=True)
        tools = [
            McpToolEntry(
                name=tool,
                tokens=count_text(tool, encoder),
                nameTokens=count_text(tool, encoder),
                descriptionTokens=0,
                inputSchemaTokens=0,
                disabled=tool in disabled_tools,
            )
            for tool in listed_tools
        ]
        result.append(
            McpServerEntry(
                name=str(name),
                enabled=bool(value.get("enabled", True)),
                schemaTokens=count_text(blob, encoder),
                disabledTokens=0,
                activeToolCount=max(0, len(listed_tools) - len(disabled_tools)),
                disabledToolCount=len(disabled_tools),
                configPath=display_path(path, env.home, project),
                transport="streamableHTTP" if value.get("url") else "stdio",
                error="config-only; live MCP schema introspection is not implemented",
                tools=tools,
                command=display_command(str(value["command"]), env.home) if value.get("command") else None,
                url=scrub_url(str(value["url"])) if value.get("url") else None,
                lines=count_lines(text),
            )
        )
    return result


def redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                result[key] = "<redacted>"
            else:
                result[key] = redact_json(item)
        return result
    if isinstance(value, list):
        return [redact_json(item) for item in value]
    if isinstance(value, str) and SENSITIVE_KEY_RE.search(value):
        return "<redacted>"
    return value


def collect_mcp(env: AgentEnvironment, project: Path | None, encoder: Any) -> list[McpServerEntry]:
    servers: dict[str, McpServerEntry] = {}
    if env.id == "claude":
        candidates = [Path.home() / ".claude.json"]
        if project is not None:
            candidates.extend([project / ".mcp.json", project / ".claude" / "settings.json"])
        for path in candidates:
            if path.is_file():
                for server in parse_claude_mcp_json(path, env, project, encoder):
                    servers[server.name] = server
    else:
        for path in codex_config_files(env.home, project):
            for server in parse_codex_mcp_config(path, env, project, encoder):
                servers[server.name] = server
    return sorted(servers.values(), key=lambda item: (-item.schemaTokens, item.name))


def sources_from_skills(skills: list[SkillEntry]) -> list[SourceEntry]:
    rows: list[SourceEntry] = []
    for skill in skills:
        rows.append(
            SourceEntry(
                source=skill.name,
                type=SOURCE_TYPE_SKILLS_METADATA,
                tokens=skill.metadataTokens,
                disabledTokens=0,
                startupLoaded=True,
                onDemandLoaded=False,
                path=skill.path,
                skillName=skill.name,
            )
        )
        rows.append(
            SourceEntry(
                source=skill.name,
                type=SOURCE_TYPE_LOADED_SKILL_BODIES,
                tokens=skill.bodyTokens,
                disabledTokens=0,
                startupLoaded=False,
                onDemandLoaded=True,
                path=skill.path,
                skillName=skill.name,
            )
        )
    return rows


def sources_from_mcp(servers: list[McpServerEntry]) -> list[SourceEntry]:
    return [
        SourceEntry(
            source=server.name,
            type=SOURCE_TYPE_MCP_TOOL_SCHEMAS,
            tokens=server.schemaTokens,
            disabledTokens=server.disabledTokens,
            startupLoaded=True,
            onDemandLoaded=False,
            path=server.configPath or "",
            serverName=server.name,
            lines=server.lines,
            detail=server.error or "",
        )
        for server in servers
    ]


def collect_sources(env: AgentEnvironment, project: Path | None, encoder: Any, skills: list[SkillEntry], mcp: list[McpServerEntry]) -> list[SourceEntry]:
    rows: list[SourceEntry] = []
    rows.extend(collect_config_sources(env, project, encoder))
    rows.extend(collect_memory_sources(env, project, encoder))
    rows.extend(collect_plugin_sources(env, project, encoder))
    rows.extend(sources_from_skills(skills))
    rows.extend(sources_from_mcp(mcp))
    rows.sort(key=lambda item: (-item.tokens, item.source))
    return rows


def usage_from_dict(data: dict[str, Any], *, claude: bool = False) -> TokenUsage:
    def as_int(value: Any) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0

    if claude:
        input_tokens = as_int(data.get("input_tokens"))
        cache_read = as_int(data.get("cache_read_input_tokens"))
        cache_create = as_int(data.get("cache_creation_input_tokens"))
        output = as_int(data.get("output_tokens"))
        total_input = input_tokens + cache_read + cache_create
        return TokenUsage(
            inputTokens=total_input,
            cachedInputTokens=cache_read,
            outputTokens=output,
            reasoningOutputTokens=0,
            totalTokens=total_input + output,
        )
    return TokenUsage(
        inputTokens=as_int(data.get("input_tokens")),
        cachedInputTokens=as_int(data.get("cached_input_tokens")),
        outputTokens=as_int(data.get("output_tokens")),
        reasoningOutputTokens=as_int(data.get("reasoning_output_tokens")),
        totalTokens=as_int(data.get("total_tokens")),
    )


def latest_session(env: AgentEnvironment, project: Path | None) -> SessionSummary | None:
    # PRIVACY INVARIANT: this reads conversation transcript files, but only
    # token-usage counters and session IDs may ever leave the parsers below.
    # Never extract or emit message content, tool calls, or file paths quoted
    # inside the transcript.
    if env.id == "claude":
        root = env.home / "projects"
        if not root.is_dir():
            return None
        candidates = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in candidates[:100]:
            parsed = parse_claude_session(path)
            if parsed is not None:
                return parsed
        return None

    root = env.home / "sessions"
    if not root.is_dir():
        return None
    candidates = sorted(root.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates[:100]:
        if "rollout" not in path.name:
            continue
        parsed = parse_codex_session(path)
        if parsed is not None:
            return parsed
    return None


def parse_codex_session(path: Path) -> SessionSummary | None:
    session_id: str | None = None
    context_window: int | None = None
    latest: TokenUsage | None = None
    cumulative: TokenUsage | None = None
    calls = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None
    for raw in lines:
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        payload = obj.get("payload") if isinstance(obj.get("payload"), dict) else {}
        if obj.get("type") == "session_meta":
            if isinstance(payload.get("id"), str):
                session_id = payload["id"]
            elif isinstance(payload.get("payload"), dict) and isinstance(payload["payload"].get("id"), str):
                session_id = payload["payload"]["id"]
        if obj.get("type") == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info") if isinstance(payload.get("info"), dict) else {}
            if isinstance(info.get("model_context_window"), int):
                context_window = info["model_context_window"]
            if isinstance(info.get("total_token_usage"), dict):
                cumulative = usage_from_dict(info["total_token_usage"])
            if isinstance(info.get("last_token_usage"), dict):
                latest = usage_from_dict(info["last_token_usage"])
                calls += 1
    if latest is None and cumulative is None:
        return None
    return SessionSummary(session_id, display_path(path, default_home("codex"), None), latest, cumulative, context_window, calls)


def parse_claude_session(path: Path) -> SessionSummary | None:
    session_id: str | None = None
    latest: TokenUsage | None = None
    calls = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None
    for raw in lines:
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if session_id is None and isinstance(obj.get("sessionId"), str):
            session_id = obj["sessionId"]
        message = obj.get("message") if isinstance(obj.get("message"), dict) else {}
        usage = message.get("usage") if isinstance(message.get("usage"), dict) else None
        if obj.get("type") == "assistant" and usage is not None:
            latest = usage_from_dict(usage, claude=True)
            calls += 1
    if latest is None:
        return None
    return SessionSummary(session_id, display_path(path, default_home("claude"), None), latest, latest, None, calls)


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    encoder, mode = load_encoder(args.encoding)
    env = resolve_agent(args)
    project = project_path(args)
    skills = collect_skills(env, project, encoder)
    mcp = collect_mcp(env, project, encoder)
    sources = collect_sources(env, project, encoder, skills, mcp)
    session = latest_session(env, project) if getattr(args, "usage", False) else None
    return {
        "encoder": encoder,
        "mode": mode,
        "env": env,
        "project": project,
        "skills": skills,
        "mcp": mcp,
        "sources": sources,
        "session": session,
    }


def limit_items(items: list[Any], limit: int | None) -> list[Any]:
    if limit is None:
        return items
    if limit < 0:
        return items
    return items[:limit]


def brief_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    sources: list[SourceEntry] = snapshot["sources"]
    session: SessionSummary | None = snapshot["session"]
    categories = []
    for source_type in SOURCE_TYPE_ORDER:
        rows = [row for row in sources if row.type == source_type]
        if not rows:
            continue
        categories.append(
            {
                "type": source_type,
                "tokens": sum(row.tokens for row in rows),
                "disabledTokens": sum(row.disabledTokens for row in rows),
                "rows": len(rows),
            }
        )
    latest = session.latestUsage if session else None
    cumulative = session.cumulativeUsage if session else None
    return {
        "startupTokens": sum(row.tokens for row in sources if row.startupLoaded),
        "onDemandTokens": sum(row.tokens for row in sources if row.onDemandLoaded),
        "disabledTokens": sum(row.disabledTokens for row in sources),
        "rowCount": len(sources),
        "disabledRowCount": len([row for row in sources if row.disabledTokens > 0]),
        "latestInputTokens": latest.inputTokens if latest else None,
        "latestCachedInputTokens": latest.cachedInputTokens if latest else None,
        "latestUncachedInputTokens": (latest.inputTokens - latest.cachedInputTokens) if latest else None,
        "cumulativeInputTokens": cumulative.inputTokens if cumulative else None,
        "contextWindow": session.contextWindow if session else None,
        "warningCount": len([row for row in sources if row.detail]),
        "categories": categories,
    }


def command_agents(args: argparse.Namespace) -> int:
    active = resolve_agent(args).id
    rows = [
        {
            "id": agent.id,
            "name": agent.name,
            "installed": agent.installed,
            "active": agent.id == active,
            "home": abbreviate_home(agent.home),
        }
        for agent in installed_agents(active)
    ]
    emit(rows, ndjson=args.ndjson)
    return 0


def command_brief(args: argparse.Namespace) -> int:
    snapshot = build_snapshot(args)
    payload = brief_payload(snapshot)
    if args.json or args.ndjson:
        emit(payload)
        return 0
    rows = [[item["type"], f"{item['tokens']:,}", str(item["rows"])] for item in payload["categories"]]
    print(f"{snapshot['env'].name} context report")
    print(f"mode: {snapshot['mode']}" + (f" ({args.encoding})" if snapshot["mode"] == "exact" else " (approx)"))
    print(f"startup tokens: {payload['startupTokens']:,}")
    print(f"on-demand tokens: {payload['onDemandTokens']:,}")
    if payload["latestInputTokens"] is not None:
        print(f"latest input tokens: {payload['latestInputTokens']:,}")
    print()
    print(table(rows, ["Category", "Tokens", "Rows"]))
    return 0


def command_sources(args: argparse.Namespace) -> int:
    snapshot = build_snapshot(args)
    rows = limit_items(snapshot["sources"], args.limit)
    payload = [source_payload(row) for row in rows]
    if args.json or args.ndjson:
        emit(payload, ndjson=args.ndjson)
        return 0
    print(table([[row["type"], row["source"], f"{row['tokens']:,}", truncate(row["path"], 96)] for row in payload], ["Type", "Source", "Tokens", "Path"]))
    return 0


def source_payload(row: SourceEntry) -> dict[str, Any]:
    return {
        "source": row.source,
        "type": row.type,
        "tokens": row.tokens,
        "disabledTokens": row.disabledTokens,
        "startupLoaded": row.startupLoaded,
        "onDemandLoaded": row.onDemandLoaded,
        "path": row.path,
        "serverName": row.serverName,
        "pluginName": row.pluginName,
        "skillName": row.skillName,
    }


def skill_payload(skill: SkillEntry) -> dict[str, Any]:
    data = asdict(skill)
    data.pop("source", None)
    data.pop("description", None)
    return data


def command_skills(args: argparse.Namespace) -> int:
    snapshot = build_snapshot(args)
    rows = limit_items(snapshot["skills"], args.limit)
    payload = [skill_payload(skill) for skill in rows]
    if args.json or args.ndjson:
        emit(payload, ndjson=args.ndjson)
        return 0
    print(table([[row["name"], f"{row['metadataTokens']:,}", f"{row['bodyTokens']:,}", truncate(row["path"], 92)] for row in payload], ["Skill", "Metadata", "Body", "Path"]))
    return 0


def command_skill(args: argparse.Namespace) -> int:
    snapshot = build_snapshot(args)
    needle = args.name.lower()
    matches = [
        skill
        for skill in snapshot["skills"]
        if needle == skill.name.lower() or needle in skill.name.lower() or needle in skill.path.lower()
    ]
    if not matches:
        print(json_dump({"ok": False, "error": f"Not found: skill {args.name}."}), file=sys.stderr)
        return 1
    payload = skill_payload(matches[0])
    if args.json or args.ndjson:
        emit(payload)
        return 0
    print(table([[key, str(value)] for key, value in payload.items()], ["Field", "Value"]))
    return 0


def mcp_payload(server: McpServerEntry, include_tools: bool = False) -> dict[str, Any]:
    data = {
        "name": server.name,
        "enabled": server.enabled,
        "schemaTokens": server.schemaTokens,
        "disabledTokens": server.disabledTokens,
        "activeToolCount": server.activeToolCount,
        "disabledToolCount": server.disabledToolCount,
        "configPath": server.configPath,
        "transport": server.transport,
        "error": server.error,
    }
    if include_tools:
        data["tools"] = [asdict(tool) for tool in server.tools or []]
    return data


def command_mcp(args: argparse.Namespace) -> int:
    snapshot = build_snapshot(args)
    servers: list[McpServerEntry] = snapshot["mcp"]
    if args.tools:
        matches = [server for server in servers if server.name == args.tools]
        if not matches:
            print(json_dump({"ok": False, "error": f"Not found: MCP server {args.tools}."}), file=sys.stderr)
            return 1
        payload: Any = mcp_payload(matches[0], include_tools=True)
    else:
        payload = [mcp_payload(server, include_tools=False) for server in limit_items(servers, args.limit)]
    if args.json or args.ndjson:
        emit(payload, ndjson=args.ndjson and isinstance(payload, list))
        return 0
    if isinstance(payload, list):
        print(table([[row["name"], f"{row['schemaTokens']:,}", str(row["activeToolCount"]), str(row["disabledToolCount"]), row["configPath"] or ""] for row in payload], ["Server", "Tokens", "Active", "Disabled", "Config"]))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("\nNote: config-only; live MCP schema introspection is not implemented.")
    return 0


def command_export(args: argparse.Namespace) -> int:
    snapshot = build_snapshot(args)
    rows = [source_payload(row) for row in snapshot["sources"]]
    if args.export_format == "json":
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if args.export_format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0].keys()) if rows else ["source", "type", "tokens"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return 0
    lines = ["| Type | Source | Tokens | Startup | On-demand | Path |", "| --- | --- | ---: | --- | --- | --- |"]
    for row in rows:
        lines.append(
            f"| {row['type']} | `{row['source']}` | {row['tokens']:,} | "
            f"{'yes' if row['startupLoaded'] else 'no'} | {'yes' if row['onDemandLoaded'] else 'no'} | `{row['path']}` |"
        )
    print("\n".join(lines))
    return 0


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agent", choices=("codex", "claude", "cursor"), default=None)
    parser.add_argument("--agent-home", "--codex-home", dest="agent_home", default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--encoding", default=DEFAULT_ENCODING)
    parser.add_argument("--usage", dest="usage", action="store_true")
    parser.add_argument("--no-usage", dest="usage", action="store_false")
    parser.add_argument("--introspect-mcp", dest="introspect_mcp", action="store_true")
    parser.add_argument("--no-introspect-mcp", dest="introspect_mcp", action="store_false")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--ndjson", action="store_true")
    parser.set_defaults(usage=False, introspect_mcp=False)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    add_common(root)
    sub = root.add_subparsers(dest="command")

    agents = sub.add_parser("agents")
    add_common(agents)
    agents.set_defaults(func=command_agents)

    for name in ("brief", "status"):
        brief = sub.add_parser(name)
        add_common(brief)
        brief.add_argument("--limit", type=int, default=None)
        brief.set_defaults(func=command_brief)

    sources = sub.add_parser("sources")
    add_common(sources)
    sources.add_argument("--limit", type=int, default=None)
    sources.set_defaults(func=command_sources)

    skills = sub.add_parser("skills")
    add_common(skills)
    skills.add_argument("--limit", type=int, default=None)
    skills.set_defaults(func=command_skills)

    skill = sub.add_parser("skill")
    add_common(skill)
    skill.add_argument("name")
    skill.set_defaults(func=command_skill)

    mcp = sub.add_parser("mcp")
    add_common(mcp)
    mcp.add_argument("--limit", type=int, default=None)
    mcp.add_argument("--tools", default=None)
    mcp.set_defaults(func=command_mcp)

    export = sub.add_parser("export")
    add_common(export)
    export.add_argument("export_format", choices=("json", "csv", "markdown"))
    export.set_defaults(func=command_export)

    return root


def main() -> int:
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    p = parser()
    args = p.parse_args()
    if args.command is None:
        args.command = "brief"
        args.func = command_brief
    if getattr(args, "introspect_mcp", False):
        print("warning: MCP introspection is not implemented; using config-only MCP data", file=sys.stderr)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
