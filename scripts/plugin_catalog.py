#!/usr/bin/env python3
"""Strict, commit-pinned catalog for standalone first-party plugins."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lockfile_json  # noqa: E402

LOCKFILE_NAME = "first-party-plugins.lock.json"
TOP_KEYS = {"schemaVersion", "publishers", "plugins"}
PUBLISHER_KEYS = {"id", "displayName", "githubOwner", "homepage"}
PLUGIN_KEYS = {"name", "displayName", "publisher", "description", "source", "manifest", "license", "selection", "receipt"}
SOURCE_KEYS = {"provider", "repository", "commit", "tree"}
MANIFEST_KEYS = {"version", "codexSha256", "claudeSha256"}
SELECTION_KEYS = {"default"}
RECEIPT_KEYS = {"schemaVersion", "name", "source", "version", "manifest", "license", "verifiedAt", "skills", "counts", "tokens", "icons"}
SKILLS_KEYS = {"count", "items"}
SKILL_KEYS = {"name", "path", "description", "startupTokens", "bodyTokens"}
COUNTS_KEYS = {"references", "scripts"}
TOKENS_KEYS = {"encoding", "startup", "body"}
ICONS_KEYS = {"composerIcon", "logo", "brandColor", "sha256", "catalogAsset"}
NAME_RE = lockfile_json.KEBAB_CASE_RE
OWNER_RE = lockfile_json.GITHUB_OWNER_RE
REPOSITORY_RE = lockfile_json.GITHUB_REPOSITORY_RE
SHA_RE = lockfile_json.SHA1_RE
SHA256_RE = lockfile_json.SHA256_RE
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


class CatalogError(RuntimeError):
    pass


class ValidationError(CatalogError):
    pass


class SourceError(CatalogError):
    pass


def _fail(location: str, message: str) -> None:
    raise ValidationError(f"{location}: {message}")


def load_json(path: Path, location: str) -> dict[str, Any]:
    try:
        return lockfile_json.load_object(path, location)
    except lockfile_json.StrictJsonError as exc:
        raise ValidationError(str(exc)) from exc


def _object(value: Any, location: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(location, "must be an object")
    missing, unknown = sorted(keys - set(value)), sorted(set(value) - keys)
    if missing or unknown:
        parts = (["missing keys " + ", ".join(missing)] if missing else []) + (["unknown keys " + ", ".join(unknown)] if unknown else [])
        _fail(location, "; ".join(parts))
    return value


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        _fail(location, "must be a nonempty trimmed string")
    return value


def _safe_path(value: Any, location: str) -> str:
    raw = _string(value, location)
    if "\\" in raw:
        _fail(location, "must use POSIX separators")
    path = PurePosixPath(raw)
    if path.is_absolute() or raw != path.as_posix() or any(part in {"", ".", ".."} for part in path.parts):
        _fail(location, "must be a normalized relative path")
    return raw


def _sha(value: Any, location: str, pattern: re.Pattern[str]) -> str:
    raw = _string(value, location)
    if not pattern.fullmatch(raw):
        _fail(location, "has invalid immutable digest syntax")
    return raw


def _receipt(root: Path, plugin: dict[str, Any], location: str) -> dict[str, Any]:
    relative = _safe_path(plugin["receipt"], f"{location}.receipt")
    if not relative.startswith("docs/first-party-plugins/") or not relative.endswith(".json"):
        _fail(f"{location}.receipt", "must be a JSON file below docs/first-party-plugins")
    path = root.joinpath(*PurePosixPath(relative).parts)
    if not path.is_file() or path.is_symlink():
        _fail(f"{location}.receipt", "must name an existing regular file")
    receipt = _object(load_json(path, f"{location}.receipt payload"), f"{location}.receipt payload", RECEIPT_KEYS)
    if receipt["schemaVersion"] != 1 or type(receipt["schemaVersion"]) is not int:
        _fail(f"{location}.receipt.schemaVersion", "must be integer 1")
    expected = {
        "name": plugin["name"], "source": plugin["source"], "version": plugin["manifest"]["version"],
        "manifest": {"codexSha256": plugin["manifest"]["codexSha256"], "claudeSha256": plugin["manifest"]["claudeSha256"]},
        "license": plugin["license"],
    }
    for key, value in expected.items():
        if receipt[key] != value:
            _fail(f"{location}.receipt.{key}", "does not match the lockfile")
    verified = _string(receipt["verifiedAt"], f"{location}.receipt.verifiedAt")
    try:
        if date.fromisoformat(verified).isoformat() != verified:
            raise ValueError
    except ValueError as exc:
        raise ValidationError(f"{location}.receipt.verifiedAt: must use a real YYYY-MM-DD date") from exc
    skills = _object(receipt["skills"], f"{location}.receipt.skills", SKILLS_KEYS)
    if type(skills["count"]) is not int or skills["count"] < 0 or not isinstance(skills["items"], list) or skills["count"] != len(skills["items"]):
        _fail(f"{location}.receipt.skills", "count must equal the nonnegative items length")
    seen: set[str] = set()
    for index, raw in enumerate(skills["items"]):
        item = _object(raw, f"{location}.receipt.skills.items[{index}]", SKILL_KEYS)
        name = _string(item["name"], f"{location}.receipt.skills.items[{index}].name")
        path_value = _safe_path(item["path"], f"{location}.receipt.skills.items[{index}].path")
        if name in seen or path_value != f"skills/{name}/SKILL.md":
            _fail(f"{location}.receipt.skills.items[{index}]", "must be unique and use skills/NAME/SKILL.md")
        _string(item["description"], f"{location}.receipt.skills.items[{index}].description")
        for key in ("startupTokens", "bodyTokens"):
            if type(item[key]) is not int or item[key] < 0:
                _fail(f"{location}.receipt.skills.items[{index}].{key}", "must be a nonnegative integer")
        seen.add(name)
    counts = _object(receipt["counts"], f"{location}.receipt.counts", COUNTS_KEYS)
    if any(type(counts[key]) is not int or counts[key] < 0 for key in COUNTS_KEYS):
        _fail(f"{location}.receipt.counts", "values must be nonnegative integers")
    tokens = _object(receipt["tokens"], f"{location}.receipt.tokens", TOKENS_KEYS)
    if tokens["encoding"] != "o200k_base":
        _fail(f"{location}.receipt.tokens.encoding", "must equal 'o200k_base'")
    if any(type(tokens[key]) is not int or tokens[key] < 0 for key in ("startup", "body")):
        _fail(f"{location}.receipt.tokens", "startup and body must be nonnegative integers")
    expected_tokens = {
        "startup": sum(item["startupTokens"] for item in skills["items"]),
        "body": sum(item["bodyTokens"] for item in skills["items"]),
    }
    if any(tokens[key] != expected_tokens[key] for key in expected_tokens):
        _fail(f"{location}.receipt.tokens", "totals must equal the skill item snapshots")
    icons = _object(receipt["icons"], f"{location}.receipt.icons", ICONS_KEYS)
    for key in ("composerIcon", "logo", "brandColor"):
        if icons[key] is not None and (not isinstance(icons[key], str) or not icons[key]):
            _fail(f"{location}.receipt.icons.{key}", "must be null or a nonempty string")
    _sha(icons["sha256"], f"{location}.receipt.icons.sha256", SHA256_RE)
    catalog_asset = _safe_path(icons["catalogAsset"], f"{location}.receipt.icons.catalogAsset")
    if not catalog_asset.startswith("assets/first-party-plugins/") or not catalog_asset.endswith(".png"):
        _fail(f"{location}.receipt.icons.catalogAsset", "must be a PNG below assets/first-party-plugins")
    snapshot = root.joinpath(*PurePosixPath(catalog_asset).parts)
    if not snapshot.is_file() or snapshot.is_symlink():
        _fail(f"{location}.receipt.icons.catalogAsset", "must name an existing regular file")
    if _digest(snapshot) != icons["sha256"]:
        _fail(f"{location}.receipt.icons.catalogAsset", "does not match icons.sha256")
    return receipt


def receipt_for(root: Path | str, plugin: dict[str, Any]) -> dict[str, Any]:
    """Return a validated repository-owned receipt for one catalog entry."""

    resolved = Path(root).resolve()
    return _receipt(resolved, plugin, f"plugin {plugin['name']}")


def validate_catalog(root: Path | str, lock_path: Path | str | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    path = root / LOCKFILE_NAME if lock_path is None else Path(lock_path)
    if not path.is_absolute():
        path = root / path
    payload = _object(load_json(path, "lockfile"), "lockfile", TOP_KEYS)
    if payload["schemaVersion"] != 1 or type(payload["schemaVersion"]) is not int:
        _fail("lockfile.schemaVersion", "must be integer 1")
    if not isinstance(payload["publishers"], list) or not isinstance(payload["plugins"], list):
        _fail("lockfile", "publishers and plugins must be arrays")
    publishers: set[str] = set()
    owners: dict[str, str] = {}
    for index, raw in enumerate(payload["publishers"]):
        loc = f"lockfile.publishers[{index}]"
        item = _object(raw, loc, PUBLISHER_KEYS)
        identifier = _string(item["id"], f"{loc}.id")
        owner = _string(item["githubOwner"], f"{loc}.githubOwner")
        if not NAME_RE.fullmatch(identifier) or identifier in publishers:
            _fail(f"{loc}.id", "must be unique lowercase kebab-case")
        if not OWNER_RE.fullmatch(owner):
            _fail(f"{loc}.githubOwner", "must be a GitHub owner")
        _string(item["displayName"], f"{loc}.displayName")
        homepage = _string(item["homepage"], f"{loc}.homepage")
        if not homepage.startswith("https://"):
            _fail(f"{loc}.homepage", "must be an HTTPS URL")
        publishers.add(identifier); owners[identifier] = owner.lower()
    names: set[str] = set()
    for index, raw in enumerate(payload["plugins"]):
        loc = f"lockfile.plugins[{index}]"
        plugin = _object(raw, loc, PLUGIN_KEYS)
        name = _string(plugin["name"], f"{loc}.name")
        if not NAME_RE.fullmatch(name) or name in names:
            _fail(f"{loc}.name", "must be unique lowercase kebab-case")
        names.add(name)
        _string(plugin["displayName"], f"{loc}.displayName"); _string(plugin["description"], f"{loc}.description")
        publisher = _string(plugin["publisher"], f"{loc}.publisher")
        if publisher not in publishers:
            _fail(f"{loc}.publisher", "must reference a declared publisher")
        source = _object(plugin["source"], f"{loc}.source", SOURCE_KEYS)
        if source["provider"] != "github": _fail(f"{loc}.source.provider", "must equal 'github'")
        repository = _string(source["repository"], f"{loc}.source.repository")
        if not REPOSITORY_RE.fullmatch(repository) or repository.split("/", 1)[0].lower() != owners[publisher]:
            _fail(f"{loc}.source.repository", "must be publisher-owned GitHub owner/repo")
        _sha(source["commit"], f"{loc}.source.commit", SHA_RE); _sha(source["tree"], f"{loc}.source.tree", SHA_RE)
        manifest = _object(plugin["manifest"], f"{loc}.manifest", MANIFEST_KEYS)
        if not SEMVER_RE.fullmatch(_string(manifest["version"], f"{loc}.manifest.version")):
            _fail(f"{loc}.manifest.version", "must be strict semver")
        _sha(manifest["codexSha256"], f"{loc}.manifest.codexSha256", SHA256_RE); _sha(manifest["claudeSha256"], f"{loc}.manifest.claudeSha256", SHA256_RE)
        if plugin["license"] != "MIT": _fail(f"{loc}.license", "must equal 'MIT'")
        selection = _object(plugin["selection"], f"{loc}.selection", SELECTION_KEYS)
        if type(selection["default"]) is not bool: _fail(f"{loc}.selection.default", "must be boolean")
        _receipt(root, plugin, loc)
    return payload


def select_plugins(payload: dict[str, Any], names: Sequence[str] | None) -> list[dict[str, Any]]:
    plugins = payload["plugins"]
    if not names:
        return list(plugins)
    by_name = {item["name"]: item for item in plugins}
    unknown = sorted(set(names) - set(by_name))
    if unknown: raise SourceError("unknown first-party plugin: " + ", ".join(unknown))
    return [by_name[name] for name in names]


def default_plugin_names(payload: dict[str, Any]) -> list[str]:
    """Return catalog-ordered entries explicitly enabled for opt-in inclusion."""

    return [item["name"] for item in payload["plugins"] if item["selection"]["default"]]


def _git(args: Sequence[str], cwd: Path | None = None) -> str:
    environment = os.environ.copy()
    environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"})
    result = subprocess.run(["git", *args], cwd=cwd, env=environment, text=True, encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise SourceError(f"git {' '.join(args[:2])} failed: {detail[-1] if detail else 'unknown error'}")
    return result.stdout.strip()


def _git_bytes(args: Sequence[str], cwd: Path) -> bytes:
    environment = os.environ.copy()
    environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"})
    result = subprocess.run(["git", *args], cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
        raise SourceError(f"git {' '.join(args[:2])} failed: {detail[-1] if detail else 'unknown error'}")
    return result.stdout


def github_url(plugin: dict[str, Any]) -> str:
    return f"https://github.com/{plugin['source']['repository']}.git"


def _frontmatter_description_and_body(text: str) -> tuple[str, str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        raise SourceError("skill is missing YAML frontmatter")
    end = normalized.find("\n---", 4)
    if end < 0:
        raise SourceError("skill has unterminated YAML frontmatter")
    frontmatter = normalized[4:end]
    body_start = normalized.find("\n", end + 4)
    body = normalized[body_start + 1 :] if body_start >= 0 else ""
    lines = frontmatter.splitlines()
    description = ""
    for index, line in enumerate(lines):
        match = re.match(r"^description:(?:\s*(.*))?$", line)
        if not match:
            continue
        value = (match.group(1) or "").strip()
        if value in {">", ">-", "|", "|-"}:
            block: list[str] = []
            for continuation in lines[index + 1 :]:
                if re.match(r"^[A-Za-z0-9_-]+:", continuation):
                    break
                block.append(continuation.strip())
            description = (" " if value.startswith(">") else "\n").join(part for part in block if part)
        else:
            description = value.strip("'\"")
        break
    if not description:
        raise SourceError("skill frontmatter is missing a description")
    return re.sub(r"\s+", " ", description).strip(), body


def generate_receipt(root: Path | str, name: str, source: Path | str) -> Path:
    """Generate a strict receipt and catalog icon from an exact local checkout."""

    root = Path(root).resolve()
    source = Path(source).resolve()
    lock = load_json(root / LOCKFILE_NAME, "lockfile")
    raw_plugins = lock.get("plugins")
    if not isinstance(raw_plugins, list):
        raise ValidationError("lockfile.plugins: must be an array")
    matches = [item for item in raw_plugins if isinstance(item, dict) and item.get("name") == name]
    if len(matches) != 1:
        raise SourceError(f"{name}: lockfile must contain exactly one plugin entry")
    plugin = matches[0]
    _inspect_git_identity(source, plugin)
    tracked = _git(["ls-tree", "-r", "--name-only", plugin["source"]["commit"]], source).splitlines()
    if any("__pycache__" in PurePosixPath(path).parts or path.endswith(".pyc") for path in tracked):
        raise SourceError(f"{name}: tracked generated Python files are forbidden")

    def blob(path: str) -> bytes:
        return _git_bytes(["show", f"{plugin['source']['commit']}:{path}"], source)

    for path, key in ((".codex-plugin/plugin.json", "codexSha256"), (".claude-plugin/plugin.json", "claudeSha256")):
        if hashlib.sha256(blob(path)).hexdigest() != plugin["manifest"][key]:
            raise SourceError(f"{name}: {key} mismatch")
    codex = json.loads(blob(".codex-plugin/plugin.json").decode("utf-8"), object_pairs_hook=_pairs)
    claude = json.loads(blob(".claude-plugin/plugin.json").decode("utf-8"), object_pairs_hook=_pairs)
    for label, manifest in (("Codex", codex), ("Claude", claude)):
        if manifest.get("name") != name or manifest.get("version") != plugin["manifest"]["version"] or manifest.get("license") != "MIT":
            raise SourceError(f"{name}: {label} manifest identity mismatch")

    try:
        import tiktoken
    except ImportError as exc:
        raise SourceError("receipt generation requires tiktoken") from exc
    encoder = tiktoken.get_encoding("o200k_base")
    skill_paths = sorted(
        (path for path in tracked if re.fullmatch(r"skills/[^/]+/SKILL\.md", path)),
        key=lambda path: PurePosixPath(path).parent.name,
    )
    items: list[dict[str, Any]] = []
    for path in skill_paths:
        skill_name = PurePosixPath(path).parent.name
        description, body = _frontmatter_description_and_body(blob(path).decode("utf-8"))
        published_path = f"https://github.com/{plugin['source']['repository']}/blob/{plugin['source']['commit']}/{path}"
        startup_text = f"name: {name}:{skill_name}\ndescription: {description}\nfile: {published_path}\n"
        items.append({
            "name": skill_name,
            "path": path,
            "description": description,
            "startupTokens": len(encoder.encode(startup_text)),
            "bodyTokens": len(encoder.encode(body)),
        })

    interface = codex.get("interface") if isinstance(codex.get("interface"), dict) else {}
    icon_relative = interface.get("logo") or interface.get("composerIcon")
    if not isinstance(icon_relative, str) or not icon_relative.startswith("./"):
        raise SourceError(f"{name}: manifest must expose a relative icon")
    icon_bytes = blob(icon_relative[2:])
    icon_hash = hashlib.sha256(icon_bytes).hexdigest()
    catalog_relative = f"assets/first-party-plugins/{name}.png"
    catalog_path = root.joinpath(*PurePosixPath(catalog_relative).parts)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_icon = catalog_path.with_suffix(".tmp")
    temporary_icon.write_bytes(icon_bytes)
    os.replace(temporary_icon, catalog_path)

    def support_count(folder: str) -> int:
        return sum(1 for path in tracked if folder in PurePosixPath(path).parts)

    receipt = {
        "schemaVersion": 1,
        "name": name,
        "source": plugin["source"],
        "version": plugin["manifest"]["version"],
        "manifest": {key: plugin["manifest"][key] for key in ("codexSha256", "claudeSha256")},
        "license": "MIT",
        "verifiedAt": date.today().isoformat(),
        "skills": {"count": len(items), "items": items},
        "counts": {"references": support_count("references"), "scripts": support_count("scripts")},
        "tokens": {
            "encoding": "o200k_base",
            "startup": sum(item["startupTokens"] for item in items),
            "body": sum(item["bodyTokens"] for item in items),
        },
        "icons": {
            "composerIcon": interface.get("composerIcon"),
            "logo": interface.get("logo"),
            "brandColor": interface.get("brandColor"),
            "sha256": icon_hash,
            "catalogAsset": catalog_relative,
        },
    }
    receipt_path = root.joinpath(*PurePosixPath(plugin["receipt"]).parts)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_receipt = receipt_path.with_suffix(".tmp")
    temporary_receipt.write_text(json.dumps(receipt, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    os.replace(temporary_receipt, receipt_path)
    _receipt(root, plugin, f"plugin {name}")
    return receipt_path


def materialized_path(
    root: Path | str,
    plugin: dict[str, Any],
    cache_root: Path | str | None = None,
) -> Path:
    base = Path(cache_root).expanduser().resolve() if cache_root else Path(root).resolve() / ".agents" / "first-party-sources"
    return base / plugin["name"] / plugin["source"]["commit"]


def _validated_cache_target(
    root: Path, plugin: dict[str, Any], cache_root: Path | str | None
) -> Path:
    base_input = Path(cache_root).expanduser() if cache_root else root / ".agents" / "first-party-sources"
    if base_input.is_symlink():
        raise SourceError(f"{plugin['name']}: cache root must not be a symbolic link")
    base = base_input.resolve()
    plugin_parent = base / plugin["name"]
    if plugin_parent.is_symlink():
        raise SourceError(f"{plugin['name']}: cache plugin directory must not be a symbolic link")
    target = plugin_parent / plugin["source"]["commit"]
    if target.parent.resolve(strict=False) != plugin_parent.resolve(strict=False):
        raise SourceError(f"{plugin['name']}: unsafe cache target")
    return target


def _inspect_git_identity(repo: Path, plugin: dict[str, Any]) -> None:
    commit = _git(["rev-parse", "HEAD^{commit}"], repo)
    tree = _git(["rev-parse", "HEAD^{tree}"], repo)
    if commit != plugin["source"]["commit"]: raise SourceError(f"{plugin['name']}: commit mismatch; expected {plugin['source']['commit']}, got {commit}")
    if tree != plugin["source"]["tree"]: raise SourceError(f"{plugin['name']}: tree mismatch; expected {plugin['source']['tree']}, got {tree}")
    entries = _git(["ls-tree", "-r", commit], repo).splitlines()
    if any(line.startswith("120000 ") for line in entries): raise SourceError(f"{plugin['name']}: symbolic links are forbidden")
    if any(line.startswith("160000 ") for line in entries): raise SourceError(f"{plugin['name']}: submodules are forbidden")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_files(root: Path, folder: str) -> int:
    files: set[Path] = set()
    for base in root.rglob(folder):
        if not base.is_dir() or base.name != folder:
            continue
        files.update(
            path
            for path in base.rglob("*")
            if path.is_file()
            and path.suffix != ".pyc"
            and "__pycache__" not in path.parts
        )
    return len(files)


def verify_plugin_tree(root: Path, plugin: dict[str, Any], receipt: dict[str, Any], validator: Path | None = None) -> None:
    _inspect_git_identity(root, plugin)
    codex_path, claude_path = root / ".codex-plugin" / "plugin.json", root / ".claude-plugin" / "plugin.json"
    for path, key in ((codex_path, "codexSha256"), (claude_path, "claudeSha256")):
        if not path.is_file() or _digest(path) != plugin["manifest"][key]: raise SourceError(f"{plugin['name']}: {key} mismatch")
    codex, claude = load_json(codex_path, "Codex manifest"), load_json(claude_path, "Claude manifest")
    for label, manifest in (("Codex", codex), ("Claude", claude)):
        if manifest.get("name") != plugin["name"]: raise SourceError(f"{plugin['name']}: {label} manifest name mismatch")
        if manifest.get("version") != plugin["manifest"]["version"]: raise SourceError(f"{plugin['name']}: {label} manifest version mismatch")
        if manifest.get("license") != "MIT": raise SourceError(f"{plugin['name']}: {label} manifest license mismatch")
    skills = [{"name": path.parent.name, "path": path.relative_to(root).as_posix()} for path in sorted((root / "skills").glob("*/SKILL.md"))] if (root / "skills").is_dir() else []
    receipt_skills = [{"name": item["name"], "path": item["path"]} for item in receipt["skills"]["items"]]
    if receipt["skills"]["count"] != len(skills) or receipt_skills != skills: raise SourceError(f"{plugin['name']}: receipt skills mismatch")
    actual_counts = {"references": _count_files(root, "references"), "scripts": _count_files(root, "scripts")}
    if receipt["counts"] != actual_counts: raise SourceError(f"{plugin['name']}: receipt counts mismatch")
    interface = codex.get("interface") if isinstance(codex.get("interface"), dict) else {}
    actual_icons = {key: interface.get(key) for key in ("composerIcon", "logo", "brandColor")}
    expected_icons = {key: receipt["icons"][key] for key in actual_icons}
    if expected_icons != actual_icons: raise SourceError(f"{plugin['name']}: receipt icon metadata mismatch")
    icon_relative = actual_icons.get("logo") or actual_icons.get("composerIcon")
    if not isinstance(icon_relative, str) or not icon_relative.startswith("./"):
        raise SourceError(f"{plugin['name']}: receipt requires a relative plugin icon")
    icon_path = root.joinpath(*PurePosixPath(icon_relative[2:]).parts)
    if not icon_path.is_file() or icon_path.is_symlink() or _digest(icon_path) != receipt["icons"]["sha256"]:
        raise SourceError(f"{plugin['name']}: receipt icon hash mismatch")
    validator = validator or Path(__file__).resolve().parents[1] / "plugins" / "capability-workbench" / "scripts" / "plugin" / "validate_plugin.py"
    result = subprocess.run([os.fspath(Path(os.sys.executable)), os.fspath(validator), os.fspath(root)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode: raise SourceError(f"{plugin['name']}: generic plugin validation failed: {(result.stdout or result.stderr).strip()}")


def _fetch_to(destination: Path, plugin: dict[str, Any], repository_url: str) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    _git(["init", "--quiet"], destination)
    _git(["config", "core.autocrlf", "false"], destination)
    _git(["config", "core.eol", "lf"], destination)
    _git(["remote", "add", "origin", repository_url], destination)
    _git(["fetch", "--quiet", "--depth", "1", "origin", plugin["source"]["commit"]], destination)
    commit = _git(["rev-parse", "FETCH_HEAD^{commit}"], destination)
    tree = _git(["rev-parse", "FETCH_HEAD^{tree}"], destination)
    if commit != plugin["source"]["commit"] or tree != plugin["source"]["tree"]:
        raise SourceError(f"{plugin['name']}: fetched source does not match pinned commit/tree")
    entries = _git(["ls-tree", "-r", commit], destination).splitlines()
    if any(line.startswith("120000 ") for line in entries): raise SourceError(f"{plugin['name']}: symbolic links are forbidden")
    if any(line.startswith("160000 ") for line in entries): raise SourceError(f"{plugin['name']}: submodules are forbidden")
    _git(["checkout", "--quiet", "--detach", commit], destination)


def materialize(root: Path | str, name: str, *, offline: bool = False, cache_root: Path | str | None = None, repository_url_resolver: Callable[[dict[str, Any]], str] = github_url, validator: Path | None = None) -> Path:
    root = Path(root).resolve(); payload = validate_catalog(root); plugin = select_plugins(payload, [name])[0]
    receipt = _receipt(root, plugin, f"plugin {name}")
    target = _validated_cache_target(root, plugin, cache_root)
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            try: verify_plugin_tree(target, plugin, receipt, validator); return target
            except CatalogError:
                if offline: raise SourceError(f"{name}: offline cache is present but invalid")
                shutil.rmtree(target)
        else:
            if offline: raise SourceError(f"{name}: offline cache is present but invalid")
            target.unlink()
    if offline: raise SourceError(f"{name}: offline cache miss")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=target.parent))
    try:
        _fetch_to(temp, plugin, repository_url_resolver(plugin))
        verify_plugin_tree(temp, plugin, receipt, validator)
        os.replace(temp, target)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True); raise
    return target


def checkout(root: Path | str, name: str, destination: Path | str, *, cache_root: Path | str | None = None, repository_url_resolver: Callable[[dict[str, Any]], str] = github_url, validator: Path | None = None) -> Path:
    root = Path(root).resolve(); destination = Path(destination).resolve(); payload = validate_catalog(root); plugin = select_plugins(payload, [name])[0]; receipt = _receipt(root, plugin, f"plugin {name}")
    if destination.exists() and not destination.is_dir():
        raise SourceError(f"{name}: destination exists and is not a directory")
    if destination.exists() and any(destination.iterdir()):
        try: verify_plugin_tree(destination, plugin, receipt, validator); return destination
        except CatalogError as exc: raise SourceError(f"{name}: destination is nonempty and does not match the pin") from exc
    source = materialize(root, name, cache_root=cache_root, repository_url_resolver=repository_url_resolver, validator=validator)
    if destination.exists(): destination.rmdir()
    _git(["clone", "--quiet", "--no-checkout", os.fspath(source), os.fspath(destination)])
    _git(["config", "core.autocrlf", "false"], destination)
    _git(["config", "core.eol", "lf"], destination)
    _git(["checkout", "--quiet", "--detach", plugin["source"]["commit"]], destination)
    verify_plugin_tree(destination, plugin, receipt, validator)
    mapping = root / ".agents" / "first-party-workspaces.json"; mapping.parent.mkdir(parents=True, exist_ok=True)
    current = load_json(mapping, "workspace map") if mapping.is_file() else {"schemaVersion": 1, "workspaces": {}}
    if set(current) != {"schemaVersion", "workspaces"} or current["schemaVersion"] != 1 or not isinstance(current["workspaces"], dict): raise SourceError("invalid .agents/first-party-workspaces.json")
    current["workspaces"][name] = {"path": os.fspath(destination), "commit": plugin["source"]["commit"]}
    temporary = mapping.with_suffix(".tmp"); temporary.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8"); os.replace(temporary, mapping)
    return destination


def verify_remote(
    plugin: dict[str, Any],
    repository_url_resolver: Callable[[dict[str, Any]], str] = github_url,
    *,
    catalog_root: Path | str | None = None,
    validator: Path | None = None,
) -> dict[str, str]:
    with tempfile.TemporaryDirectory() as raw:
        repo = Path(raw)
        _fetch_to(repo, plugin, repository_url_resolver(plugin))
        if catalog_root is None:
            _inspect_git_identity(repo, plugin)
        else:
            verify_plugin_tree(
                repo,
                plugin,
                receipt_for(catalog_root, plugin),
                validator,
            )
    return {"name": plugin["name"], "commit": plugin["source"]["commit"], "tree": plugin["source"]["tree"]}
