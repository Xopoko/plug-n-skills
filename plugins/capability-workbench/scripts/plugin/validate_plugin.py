#!/usr/bin/env python3
"""Validate a generated plugin against the plugin ingestion contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

try:
    import yaml
except Exception:  # pragma: no cover - import environment issue.
    yaml = None  # type: ignore[assignment]
else:
    if not hasattr(yaml, "safe_load") or not hasattr(yaml, "YAMLError"):
        yaml = None  # type: ignore[assignment]


TODO_MARKER = "[TODO:"
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
HEX_COLOR_RE = re.compile(r"^#[0-9A-F]{6}$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a local plugin manifest and skills (codex + claude manifests)."
    )
    parser.add_argument("plugin_path", help="Path to the plugin root directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plugin_root = Path(args.plugin_path).expanduser().resolve()
    errors = validate_plugin(plugin_root)
    if errors:
        print("Plugin validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)
    print(f"Plugin validation passed: {plugin_root}")


def validate_plugin(plugin_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    manifest = load_json_object(manifest_path, errors)
    if manifest is None:
        return errors

    reject_todo_markers(manifest, "$", errors)
    validate_manifest_shape(plugin_root, manifest, errors)
    validate_manifest_consistency(plugin_root, manifest, errors)
    return errors


def validate_manifest_consistency(
    plugin_root: Path,
    codex_manifest: dict[str, Any],
    errors: list[str],
) -> None:
    """When both .codex-plugin and .claude-plugin manifests exist, shared fields must match."""
    claude_path = plugin_root / ".claude-plugin" / "plugin.json"
    if not claude_path.is_file():
        return
    try:
        claude_manifest = json.loads(claude_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("`.claude-plugin/plugin.json` must be valid JSON")
        return
    if not isinstance(claude_manifest, dict):
        errors.append("`.claude-plugin/plugin.json` must contain a JSON object")
        return

    for field in ("name", "description", "license"):
        codex_value = codex_manifest.get(field)
        claude_value = claude_manifest.get(field)
        if codex_value != claude_value:
            errors.append(
                f"manifest field `{field}` differs between `.codex-plugin` and `.claude-plugin`"
            )

    codex_version = str(codex_manifest.get("version", "")).split("+", 1)[0]
    claude_version = str(claude_manifest.get("version", "")).split("+", 1)[0]
    if codex_version != claude_version:
        errors.append(
            "manifest base `version` differs between `.codex-plugin` and `.claude-plugin`"
        )

    codex_author = codex_manifest.get("author")
    claude_author = claude_manifest.get("author")
    codex_author_name = codex_author.get("name") if isinstance(codex_author, dict) else codex_author
    claude_author_name = claude_author.get("name") if isinstance(claude_author, dict) else claude_author
    if codex_author_name != claude_author_name:
        errors.append(
            "manifest `author` name differs between `.codex-plugin` and `.claude-plugin`"
        )

    codex_keywords = codex_manifest.get("keywords")
    claude_keywords = claude_manifest.get("keywords")
    if isinstance(codex_keywords, list) and isinstance(claude_keywords, list):
        if set(codex_keywords) != set(claude_keywords):
            errors.append(
                "manifest `keywords` differ between `.codex-plugin` and `.claude-plugin`"
            )


def load_json_object(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append("missing `.codex-plugin/plugin.json`")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append("unable to read `.codex-plugin/plugin.json`")
        return None
    except json.JSONDecodeError:
        errors.append("`.codex-plugin/plugin.json` must be valid JSON")
        return None
    if not isinstance(payload, dict):
        errors.append("`.codex-plugin/plugin.json` must contain a JSON object")
        return None
    return payload


def reject_todo_markers(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, str):
        if TODO_MARKER in value:
            errors.append(f"{path} still contains a `[TODO: ...]` placeholder")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            reject_todo_markers(item, f"{path}[{index}]", errors)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            reject_todo_markers(item, f"{path}.{key}", errors)


def validate_manifest_shape(
    plugin_root: Path,
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    allowed_keys = {
        "id",
        "name",
        "version",
        "description",
        "skills",
        "apps",
        "mcpServers",
        "interface",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
    }
    for key in sorted(set(manifest) - allowed_keys):
        errors.append(f"plugin.json field `{key}` is not accepted by plugin validation")

    validate_optional_non_empty_string(manifest, "id", errors)
    require_non_empty_string(manifest, "name", errors)
    version = require_non_empty_string(manifest, "version", errors)
    if version is not None and SEMVER_RE.fullmatch(version) is None:
        errors.append("plugin.json field `version` must be strict semver")
    require_non_empty_string(manifest, "description", errors)

    author = require_object(manifest, "author", errors)
    if author is not None:
        reject_unknown_fields(author, {"name", "email", "url"}, "author", errors)
        require_non_empty_string(author, "name", errors, prefix="author")
        validate_optional_non_empty_string(author, "email", errors, prefix="author")
        validate_optional_https_url(author, "url", errors, prefix="author")

    validate_optional_contract_path(manifest, "skills", "skills", errors)
    validate_optional_contract_path(manifest, "apps", ".app.json", errors)
    mcp_manifest_path = validate_optional_mcp_contract_path(
        plugin_root, manifest, errors
    )

    if manifest.get("apps") is not None:
        validate_app_manifest(
            plugin_root / ".app.json",
            errors,
        )
    if mcp_manifest_path is not None:
        validate_mcp_manifest(
            mcp_manifest_path,
            errors,
        )
    validate_skill_manifests(plugin_root, errors)

    interface = require_object(manifest, "interface", errors)
    if interface is None:
        return
    reject_unknown_fields(
        interface,
        {
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "capabilities",
            "websiteURL",
            "privacyPolicyURL",
            "termsOfServiceURL",
            "brandColor",
            "composerIcon",
            "logo",
            "screenshots",
            "defaultPrompt",
            "default_prompt",
        },
        "interface",
        errors,
    )
    for field in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
    ):
        require_non_empty_string(interface, field, errors, prefix="interface")
    if "defaultPrompt" not in interface and "default_prompt" not in interface:
        errors.append(
            "plugin.json field `interface.defaultPrompt` or `interface.default_prompt` is required"
        )
    capabilities = interface.get("capabilities")
    if not isinstance(capabilities, list) or not all(
        isinstance(value, str) and value.strip() for value in capabilities
    ):
        errors.append("plugin.json field `interface.capabilities` must be an array of strings")
    for field in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
        validate_optional_https_url(interface, field, errors, prefix="interface")
    brand_color = interface.get("brandColor")
    if brand_color is not None and (
        not isinstance(brand_color, str) or HEX_COLOR_RE.fullmatch(brand_color) is None
    ):
        errors.append("plugin.json field `interface.brandColor` must use `#RRGGBB`")
    for field in ("composerIcon", "logo"):
        validate_optional_asset_path(plugin_root, plugin_root, interface, field, errors)
    screenshots = interface.get("screenshots", [])
    if not isinstance(screenshots, list):
        errors.append("plugin.json field `interface.screenshots` must be an array")
    else:
        for index, raw_path in enumerate(screenshots):
            validate_asset_path(
                plugin_root,
                plugin_root,
                raw_path,
                f"interface.screenshots[{index}]",
                errors,
            )


def require_object(
    payload: dict[str, Any],
    key: str,
    errors: list[str],
) -> dict[str, Any] | None:
    value = payload.get(key)
    if not isinstance(value, dict):
        errors.append(f"plugin.json field `{key}` must be an object")
        return None
    return value


def require_non_empty_string(
    payload: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> str | None:
    value = payload.get(key)
    field = f"{prefix}.{key}" if prefix is not None else key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"plugin.json field `{field}` must be a non-empty string")
        return None
    return value


def validate_optional_non_empty_string(
    payload: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> None:
    value = payload.get(key)
    if value is None:
        return
    field = f"{prefix}.{key}" if prefix is not None else key
    if not isinstance(value, str) or not value.strip():
        errors.append(f"plugin.json field `{field}` must be a non-empty string")


def reject_unknown_fields(
    payload: dict[str, Any],
    allowed_keys: set[str],
    prefix: str,
    errors: list[str],
) -> None:
    for key in sorted(set(payload) - allowed_keys):
        errors.append(f"plugin.json field `{prefix}.{key}` is not accepted by plugin validation")


def validate_optional_https_url(
    payload: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str,
) -> None:
    value = payload.get(key)
    if value is None:
        return
    parsed = urlparse(value) if isinstance(value, str) else None
    if parsed is None or parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"plugin.json field `{prefix}.{key}` must be an absolute `https://` URL")


def validate_optional_contract_path(
    payload: dict[str, Any],
    key: str,
    expected: str,
    errors: list[str],
) -> None:
    value = payload.get(key)
    if value is None:
        return
    normalized = normalize_contract_path(value) if isinstance(value, str) else None
    if normalized != expected:
        errors.append(f"plugin.json field `{key}` must resolve to `{expected}`")


def normalize_contract_path(raw_path: str) -> str | None:
    path = Path(raw_path)
    if path.is_absolute():
        return None
    normalized = path.as_posix().rstrip("/")
    return normalized or None


def validate_optional_mcp_contract_path(
    plugin_root: Path,
    payload: dict[str, Any],
    errors: list[str],
) -> Path | None:
    value = payload.get("mcpServers")
    if value is None:
        return None
    normalized = normalize_contract_path(value) if isinstance(value, str) else None
    allowed = {".mcp.json", ".codex-mcp.json"}
    if normalized not in allowed:
        errors.append(
            "plugin.json field `mcpServers` must resolve to `.mcp.json` or "
            "`.codex-mcp.json`"
        )
        return None
    path = plugin_root / normalized
    if path.is_symlink():
        errors.append(
            "plugin.json field `mcpServers` must not resolve through a symlink"
        )
        return None
    try:
        path.resolve(strict=False).relative_to(plugin_root.resolve())
    except ValueError:
        errors.append("plugin.json field `mcpServers` escapes the plugin root")
        return None
    return path


def validate_app_manifest(path: Path, errors: list[str]) -> None:
    payload = load_companion_json_object(path, "`.app.json`", errors)
    if payload is None:
        return
    reject_companion_unknown_fields(payload, {"apps"}, "`.app.json`", errors)
    apps = payload.get("apps")
    if not isinstance(apps, dict):
        errors.append("`.app.json` field `apps` must be an object")
        return
    for key, value in apps.items():
        if not isinstance(value, dict):
            errors.append(f"`.app.json` app `{key}` must be an object")
            continue
        reject_companion_unknown_fields(value, {"id"}, f"`.app.json` app `{key}`", errors)
        app_id = value.get("id")
        if not isinstance(app_id, str) or not app_id.strip():
            errors.append(f"`.app.json` app `{key}` field `id` must be a non-empty string")


def validate_mcp_manifest(path: Path, errors: list[str]) -> None:
    label = f"`{path.name}`"
    payload = load_companion_json_object(path, label, errors)
    if payload is None:
        return
    reject_companion_unknown_fields(payload, {"mcpServers"}, label, errors)
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        errors.append(f"{label} field `mcpServers` must be an object")
        return
    for key, value in servers.items():
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{label} server names must be non-empty strings")
        if not isinstance(value, dict):
            errors.append(f"{label} server `{key}` must be an object")


def load_companion_json_object(
    path: Path,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"{label} is required when its plugin.json field is present")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append(f"{label} must contain valid JSON")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must contain a JSON object")
        return None
    return payload


def reject_companion_unknown_fields(
    payload: dict[str, Any],
    allowed_keys: set[str],
    prefix: str,
    errors: list[str],
) -> None:
    for key in sorted(set(payload) - allowed_keys):
        errors.append(f"{prefix} field `{key}` is not accepted by plugin validation")


def validate_skill_manifests(plugin_root: Path, errors: list[str]) -> None:
    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        return
    for skill_root in sorted(skills_root.iterdir(), key=lambda path: path.name):
        if skill_root.name.startswith(".") or not skill_root.is_dir():
            continue
        validate_skill_manifest(skill_root, errors)


def validate_skill_manifest(skill_root: Path, errors: list[str]) -> None:
    skill_md_path = skill_root / "SKILL.md"
    if not skill_md_path.is_file():
        errors.append(f"skill `{skill_root.name}` is missing `SKILL.md`")
        return
    try:
        contents = skill_md_path.read_text(encoding="utf-8")
    except OSError:
        errors.append(f"unable to read skill `{skill_root.name}`")
        return
    if not contents.startswith("---\n"):
        errors.append(f"skill `{skill_root.name}` must start with YAML frontmatter")
        return
    frontmatter_end = contents.find("\n---", 4)
    if frontmatter_end == -1:
        errors.append(f"skill `{skill_root.name}` frontmatter is not closed")
        return
    frontmatter = load_yaml_mapping(
        contents[4:frontmatter_end],
        f"skill `{skill_root.name}` frontmatter",
        errors,
    )
    if frontmatter is None:
        return
    skill_name = frontmatter.get("name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        errors.append(f"skill `{skill_root.name}` frontmatter field `name` must be non-empty")
    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(
            f"skill `{skill_root.name}` frontmatter field `description` must be non-empty"
        )
    disable_model_invocation = frontmatter.get("disable-model-invocation")
    if disable_model_invocation is None:
        disable_model_invocation = frontmatter.get("disable_model_invocation")
    if disable_model_invocation not in (None, False):
        errors.append(
            f"skill `{skill_root.name}` frontmatter field `disable-model-invocation` must be false"
        )
    agent_yaml_path = skill_root / "agents" / "openai.yaml"
    if agent_yaml_path.is_file():
        validate_skill_agent_manifest(
            plugin_root=skill_root.parent.parent,
            skill_root=skill_root,
            agent_yaml_path=agent_yaml_path,
            errors=errors,
        )


def validate_skill_agent_manifest(
    *,
    plugin_root: Path,
    skill_root: Path,
    agent_yaml_path: Path,
    errors: list[str],
) -> None:
    try:
        raw_yaml = agent_yaml_path.read_text(encoding="utf-8")
    except OSError:
        errors.append(f"unable to read skill `{skill_root.name}` agent YAML")
        return

    payload = load_yaml_mapping(
        raw_yaml,
        f"skill `{skill_root.name}` agent YAML",
        errors,
    )
    if payload is None:
        return

    reject_skill_agent_unknown_fields(
        payload,
        {"interface", "policy", "dependencies"},
        skill_root,
        errors,
    )
    interface = payload.get("interface")
    if not isinstance(interface, dict):
        errors.append(f"skill `{skill_root.name}` agent field `interface` must be an object")
        return
    reject_skill_agent_unknown_fields(
        interface,
        {
            "display_name",
            "short_description",
            "icon_small",
            "icon_large",
            "brand_color",
            "default_prompt",
        },
        skill_root,
        errors,
        prefix="interface",
    )
    for field in ("display_name", "short_description"):
        value = interface.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(
                f"skill `{skill_root.name}` agent field `interface.{field}` must be non-empty"
            )
    for field in ("icon_small", "icon_large"):
        validate_optional_asset_path(
            skill_root,
            plugin_root,
            interface,
            field,
            errors,
            prefix=f"skill `{skill_root.name}` agent field `interface",
        )
    brand_color = interface.get("brand_color")
    if brand_color is not None and (
        not isinstance(brand_color, str) or HEX_COLOR_RE.fullmatch(brand_color) is None
    ):
        errors.append(
            f"skill `{skill_root.name}` agent field `interface.brand_color` must use `#RRGGBB`"
        )
    default_prompt = interface.get("default_prompt")
    if default_prompt is not None and (
        not isinstance(default_prompt, str) or not default_prompt.strip()
    ):
        errors.append(
            f"skill `{skill_root.name}` agent field `interface.default_prompt` must be non-empty"
        )

    policy = payload.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            errors.append(f"skill `{skill_root.name}` agent field `policy` must be an object")
        else:
            reject_skill_agent_unknown_fields(
                policy,
                {"allow_implicit_invocation"},
                skill_root,
                errors,
                prefix="policy",
            )
            allow_implicit_invocation = policy.get("allow_implicit_invocation")
            if allow_implicit_invocation is not None and not isinstance(
                allow_implicit_invocation,
                bool,
            ):
                errors.append(
                    f"skill `{skill_root.name}` agent field "
                    "`policy.allow_implicit_invocation` must be a boolean"
                )

    dependencies = payload.get("dependencies")
    if dependencies is not None:
        if not isinstance(dependencies, dict):
            errors.append(
                f"skill `{skill_root.name}` agent field `dependencies` must be an object"
            )
        else:
            reject_skill_agent_unknown_fields(
                dependencies,
                {"tools"},
                skill_root,
                errors,
                prefix="dependencies",
            )


def reject_skill_agent_unknown_fields(
    payload: dict[str, Any],
    allowed_keys: set[str],
    skill_root: Path,
    errors: list[str],
    *,
    prefix: str | None = None,
) -> None:
    for key in sorted(set(payload) - allowed_keys):
        field = f"{prefix}.{key}" if prefix is not None else key
        errors.append(
            f"skill `{skill_root.name}` agent field `{field}` is not accepted by plugin validation"
        )


def load_yaml_mapping(text: str, label: str, errors: list[str]) -> dict[str, Any] | None:
    if yaml is not None:
        try:
            payload = yaml.safe_load(text)
        except yaml.YAMLError:
            errors.append(f"{label} must be valid YAML")
            return None
    else:
        try:
            payload = parse_simple_yaml_mapping(text)
        except ValueError:
            errors.append(f"{label} must be valid YAML")
            return None

    if not isinstance(payload, dict):
        errors.append(f"{label} must be an object")
        return None
    return payload


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
        indent = count_indent(raw_line)
        if stripped.startswith("- "):
            raise ValueError("sequence YAML is not supported by the fallback parser")
        if ":" not in stripped:
            raise ValueError("expected key-value YAML")
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        if not key:
            raise ValueError("empty YAML key")

        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError("invalid YAML indentation")
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
        current[key] = parse_simple_yaml_scalar(value)
        index += 1
    return root


def count_indent(line: str) -> int:
    indent = len(line) - len(line.lstrip(" "))
    if "\t" in line[:indent]:
        raise ValueError("tabs are not supported in YAML indentation")
    return indent


def consume_yaml_block(
    lines: list[str],
    start: int,
    parent_indent: int,
    marker: str,
) -> tuple[str, int]:
    parts: list[str] = []
    block_indent: int | None = None
    index = start
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped:
            parts.append("")
            index += 1
            continue
        indent = count_indent(raw_line)
        if indent <= parent_indent:
            break
        if block_indent is None:
            block_indent = indent
        parts.append(raw_line[min(block_indent, len(raw_line)):])
        index += 1

    if marker.startswith(">"):
        value = " ".join(part.strip() for part in parts if part.strip())
    else:
        value = "\n".join(parts)
    return value, index


def parse_simple_yaml_scalar(value: str) -> Any:
    value = strip_yaml_comment(value)
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


def validate_optional_asset_path(
    base_dir: Path,
    allowed_root: Path,
    payload: dict[str, Any],
    key: str,
    errors: list[str],
    *,
    prefix: str = "interface",
) -> None:
    raw_path = payload.get(key)
    if raw_path is None:
        return
    validate_asset_path(base_dir, allowed_root, raw_path, f"{prefix}.{key}", errors)


def validate_asset_path(
    base_dir: Path,
    allowed_root: Path,
    raw_path: Any,
    field: str,
    errors: list[str],
) -> None:
    label = field if field.startswith("skill `") else f"plugin.json field `{field}`"
    if not isinstance(raw_path, str) or not raw_path.strip():
        errors.append(f"{label} must be a non-empty relative path")
        return
    candidate = PurePosixPath(raw_path.replace("\\", "/"))
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        errors.append(f"{label} must stay inside the plugin archive")
        return
    resolved_path = (base_dir / candidate.as_posix()).resolve()
    if not resolved_path.is_relative_to(allowed_root.resolve()):
        errors.append(f"{label} must stay inside the plugin archive")
        return
    if not resolved_path.is_file():
        errors.append(f"{label} points to a missing file")


if __name__ == "__main__":
    main()
