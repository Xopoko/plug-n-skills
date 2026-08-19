#!/usr/bin/env python3
"""Validate repository-level quality gates for Plug'n Skills."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plugin_catalog  # noqa: E402


LOCAL_PLUGIN_NAMES = [
    "agent-harness",
    "windows-host-operations",
    "capability-workbench",
    "context-density",
    "i-have-adhd",
    "git-workflows",
    "engineering-hygiene",
    "scientific-research",
    "technology-intelligence",
    "design-intelligence",
    "architecture-intelligence",
    "spec-driven-development",
    "kotlin-multiplatform",
    "tauri",
    "pixijs",
    "game-design-intelligence",
]
CATALOG_WEBSITE_URL = "https://github.com/Xopoko/plug-n-skills"

TEXT_EXTENSIONS = {
    "",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_DIR_NAMES = {
    ".git",
    ".agents",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".tox",
    ".venv",
    "venv",
}
ROOT_SCRATCH_DIRS = {
    "research",
    "skill-synthesis",
    "tmp",
    "temp",
    "output",
    "scratch",
    "reports",
}
PLUGIN_SCRATCH_DIRS = {
    "research",
    "synthesis",
    "tmp",
    "temp",
    "output",
    "scratch",
    "reports",
}
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
LOCAL_PATH_RE = re.compile("/" + "Users/" + r"[A-Za-z0-9._-]+/")
LOCAL_PROJECT_PATH_RE = re.compile(r"~/" + "Projects/")
SECRET_PATTERNS = [
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]
PRIVATE_PROJECT_TERMS = [
    "B2" + "Broker",
    "B2" + "Core",
    "Movie" + "Swipe",
    "Kino" + "Cue",
    "Ton" + "go",
    "Codex" + "Quest",
    "Philo" + "script",
    "Rybo" + "ria",
    "Sc" + "out",
    "Pre" + "ply",
    "Carp" + "Fishing",
    ".codex" + "-care",
]
PRIVATE_PROJECT_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(term) for term in PRIVATE_PROJECT_TERMS if not term.startswith("."))
    + r"|PAN-\d+)\b|"
    + re.escape(".codex" + "-care")
)
GRANDIOSE_TERMS = [
    "best-" + "of-breed",
    "world-" + "class",
    "revolution" + "ary",
    "unparallel" + "ed",
    "unmatch" + "ed",
    "ulti" + "mate",
    "strong" + "est",
    "exhaust" + "ive",
]
GRANDIOSE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in GRANDIOSE_TERMS) + r")\b",
    re.IGNORECASE,
)
PRIVATE_ORG_WORDS = [
    "comp" + "any",
    "comp" + "anies",
    "custom" + "er",
    "custom" + "ers",
]
PRIVATE_ORG_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in PRIVATE_ORG_WORDS) + r")\b",
    re.IGNORECASE,
)
LEGACY_BRAND_TERMS = [
    "Xopoko/" + "plugins",
    "github.com/Xopoko/" + "plugins",
    "xopoko-" + "plugins",
    "Xopoko/" + "power" + "packs",
    "github.com/Xopoko/" + "power" + "packs",
    "xopoko-" + "power" + "packs",
    "# Agent " + "Plugins",
    "Agent " + "Plugins collection",
    "Agent " + "Plugin Collection",
    "# Agent " + "Power" + "packs",
    "Agent " + "Power" + "packs",
    "power" + "packs",
    "Power" + "packs",
    "power" + "pack",
    "Power" + "pack",
]
LEGACY_BRAND_RE = re.compile(
    r"(?:" + "|".join(re.escape(term) for term in LEGACY_BRAND_TERMS) + r")"
)
PRIVATE_TOOL_TERMS = [
    "codex-" + "token-" + "lens",
    "Codex" + "Token" + "Lens",
]
PRIVATE_TOOL_RE = re.compile(
    r"(?:" + "|".join(re.escape(term) for term in PRIVATE_TOOL_TERMS) + r")"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> None:
    root = repo_root()
    errors: list[str] = []
    validate_helper = root / "plugins" / "capability-workbench" / "scripts" / "plugin" / "validate_plugin.py"
    external_dependency_helper = root / "scripts" / "external-dependencies.py"
    if not validate_helper.is_file():
        errors.append(f"missing validator: {validate_helper}")
    if not external_dependency_helper.is_file():
        errors.append(f"missing validator: {external_dependency_helper}")
    try:
        first_party_catalog = plugin_catalog.validate_catalog(root)
    except plugin_catalog.CatalogError as exc:
        errors.append(f"First-party plugin catalog validation failed: {exc}")
        first_party_catalog = {"plugins": []}
    first_party_plugins = {
        item["name"]: item for item in first_party_catalog["plugins"]
    }
    manifest_plugin_names = {
        path.parent.parent.name
        for path in (root / "plugins").glob("*/.codex-plugin/plugin.json")
    }
    unexpected_plugins = sorted(manifest_plugin_names - set(LOCAL_PLUGIN_NAMES))
    if unexpected_plugins:
        errors.append(
            "unexpected manifest-bearing plugin directories: "
            + ", ".join(unexpected_plugins)
        )

    for name in LOCAL_PLUGIN_NAMES:
        plugin_dir = root / "plugins" / name
        if not plugin_dir.is_dir():
            errors.append(f"missing plugin directory: plugins/{name}")
            continue
        manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
        manifest = load_json(manifest_path, errors)
        if manifest is not None:
            validate_manifest_metadata(name, manifest, errors)
        claude_path = plugin_dir / ".claude-plugin" / "plugin.json"
        claude_manifest = load_json(claude_path, errors)
        if claude_manifest is not None:
            if claude_manifest.get("name") != name:
                errors.append(f"plugins/{name}/.claude-plugin/plugin.json: name must match directory")
            if claude_manifest.get("license") != "MIT":
                errors.append(f"plugins/{name}/.claude-plugin/plugin.json: license must be MIT")
            if manifest is not None and claude_manifest.get("name") != manifest.get("name"):
                errors.append(f"plugins/{name}: claude/codex manifest name mismatch")
        if validate_helper.is_file():
            result = subprocess.run(
                [sys.executable, str(validate_helper), str(plugin_dir)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode != 0:
                errors.append(
                    f"Codex plugin validation failed for {name}:\n{result.stdout}{result.stderr}"
                )

    if external_dependency_helper.is_file():
        result = subprocess.run(
            [
                sys.executable,
                str(external_dependency_helper),
                "--root",
                str(root),
                "validate",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            errors.append(
                "External dependency validation failed:\n"
                f"{result.stdout}{result.stderr}"
            )

    for name in first_party_plugins:
        if (root / "plugins" / name).exists():
            errors.append(
                f"plugins/{name}: standalone first-party plugin must not be vendored"
            )

    errors.extend(validate_marketplace(root, LOCAL_PLUGIN_NAMES, first_party_plugins))
    errors.extend(validate_capability_workbench_surface(root))
    errors.extend(validate_agent_harness_surface(root))
    errors.extend(validate_technology_intelligence_surface(root))
    errors.extend(validate_architecture_intelligence_surface(root))
    errors.extend(scan_files(root))

    if errors:
        print("Repository validation failed:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("Repository validation passed")


def load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"missing JSON file: {path.relative_to(repo_root())}")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path.relative_to(repo_root())}: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"JSON file must contain an object: {path.relative_to(repo_root())}")
        return None
    return payload


def validate_manifest_metadata(name: str, manifest: dict[str, Any], errors: list[str]) -> None:
    rel = f"plugins/{name}/.codex-plugin/plugin.json"
    if manifest.get("name") != name:
        errors.append(f"{rel}: manifest name must match directory")
    if manifest.get("license") != "MIT":
        errors.append(f"{rel}: license must be MIT")
    repository = manifest.get("repository")
    if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
        errors.append(f"{rel}: repository must be a GitHub URL")
    author = manifest.get("author")
    if isinstance(author, dict):
        author_name = author.get("name")
        if isinstance(author_name, str) and "Local" in author_name:
            errors.append(f"{rel}: author name should not include local-only branding")
    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append(f"{rel}: interface must be an object")
    else:
        if interface.get("websiteURL") != CATALOG_WEBSITE_URL:
            errors.append(
                f"{rel}: interface.websiteURL must be {CATALOG_WEBSITE_URL}"
            )
        developer = interface.get("developerName")
        if isinstance(developer, str) and "Local" in developer:
            errors.append(f"{rel}: developerName should not include local-only branding")


def validate_marketplace(
    root: Path,
    local_names: list[str],
    first_party: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    path = root / ".claude-plugin" / "marketplace.json"
    data = load_json(path, errors)
    if data is None:
        return errors
    expected_schema = "https://json.schemastore.org/claude-code-marketplace.json"
    if data.get("$schema") != expected_schema:
        errors.append(
            f".claude-plugin/marketplace.json: $schema must be {expected_schema}"
        )
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        errors.append(".claude-plugin/marketplace.json: 'plugins' must be an array")
        return errors
    listed = []
    for entry in plugins:
        name = entry.get("name") if isinstance(entry, dict) else None
        src = entry.get("source") if isinstance(entry, dict) else None
        if not isinstance(name, str):
            errors.append(".claude-plugin/marketplace.json: entry missing 'name'")
            continue
        listed.append(name)
        if name in first_party:
            plugin = first_party[name]
            expected_source = {
                "source": "github",
                "repo": plugin["source"]["repository"],
                "sha": plugin["source"]["commit"],
            }
            if src != expected_source:
                errors.append(
                    f".claude-plugin/marketplace.json: first-party source mismatch for {name}"
                )
            if entry.get("description") != plugin["description"]:
                errors.append(
                    f".claude-plugin/marketplace.json: description mismatch for {name}"
                )
            if entry.get("version") != plugin["manifest"]["version"]:
                errors.append(
                    f".claude-plugin/marketplace.json: version mismatch for {name}"
                )
        else:
            expected_source = f"./plugins/{name}"
            if src != expected_source or not (root / "plugins" / name).is_dir():
                errors.append(f".claude-plugin/marketplace.json: bad source for {name}")
            if not (root / "plugins" / name / ".claude-plugin" / "plugin.json").is_file():
                errors.append(f".claude-plugin/marketplace.json: {name} lacks a Claude manifest")
    if set(listed) != set(local_names) | set(first_party):
        errors.append(".claude-plugin/marketplace.json: plugin set does not match local plus first-party catalog")
    if len(listed) != len(set(listed)):
        errors.append(".claude-plugin/marketplace.json: plugin names must be unique")
    return errors


def validate_capability_workbench_surface(root: Path) -> list[str]:
    """Keep flagship positioning and artifact-evaluation ownership coherent."""
    errors: list[str] = []
    plugin = root / "plugins" / "capability-workbench"
    skill = plugin / "skills" / "capability-evaluation" / "SKILL.md"
    metadata = skill.parent / "agents" / "openai.yaml"
    reference = plugin / "references" / "capability-evaluation.md"
    validator = plugin / "scripts" / "evaluation" / "validate_capability_evaluation.py"
    router = plugin / "skills" / "capability-workbench" / "SKILL.md"
    plugin_readme = plugin / "README.md"
    dashboard_script = root / "scripts" / "render_plugin_dashboard_header.py"

    for path in (skill, metadata, reference, validator, router, plugin_readme):
        if not path.is_file():
            errors.append(
                "plugins/capability-workbench: missing agent-capability-engineering "
                f"surface {path.relative_to(plugin)}"
            )

    skill_text = skill.read_text(encoding="utf-8") if skill.is_file() else ""
    router_text = router.read_text(encoding="utf-8") if router.is_file() else ""
    readme_text = plugin_readme.read_text(encoding="utf-8") if plugin_readme.is_file() else ""
    dashboard_text = (
        dashboard_script.read_text(encoding="utf-8")
        if dashboard_script.is_file()
        else ""
    )
    for label, text, markers in (
        (
            "evaluation skill",
            skill_text,
            ("name: capability-evaluation", "baseline", "Agent Harness"),
        ),
        (
            "router",
            router_text,
            ("capability-evaluation", "Assure/evolve", "harness-level evaluation"),
        ),
        (
            "plugin README",
            readme_text,
            ("Agent Capability Engineering", "capability-evaluation", "Lifecycle"),
        ),
        (
            "dashboard renderer",
            dashboard_text,
            ("Engineer, evaluate, and govern agent capabilities.",),
        ),
    ):
        for marker in markers:
            if marker not in text:
                errors.append(
                    f"plugins/capability-workbench: {label} missing {marker!r}"
                )

    codex = load_json(plugin / ".codex-plugin" / "plugin.json", errors)
    claude = load_json(plugin / ".claude-plugin" / "plugin.json", errors)
    if codex is not None and claude is not None:
        for field in ("name", "version", "description", "author", "license", "keywords"):
            if codex.get(field) != claude.get(field):
                errors.append(
                    f"plugins/capability-workbench: manifest {field} mismatch"
                )
        description = codex.get("description", "")
        if "Artifact-first agent capability engineering" not in description:
            errors.append(
                "plugins/capability-workbench: manifest description lacks "
                "artifact-first positioning"
            )
        if "harness-level evaluation" not in description:
            errors.append(
                "plugins/capability-workbench: manifest description lacks "
                "Agent Harness evaluation boundary"
            )
        keywords = codex.get("keywords", [])
        for keyword in ("agent-capability-engineering", "behavioral-evaluation"):
            if keyword not in keywords:
                errors.append(
                    f"plugins/capability-workbench: missing manifest keyword {keyword}"
                )

        marketplace = load_json(root / ".claude-plugin" / "marketplace.json", errors)
        entries = marketplace.get("plugins", []) if marketplace else []
        entry = next(
            (
                item
                for item in entries
                if isinstance(item, dict) and item.get("name") == "capability-workbench"
            ),
            None,
        )
        if entry is None:
            errors.append(
                "plugins/capability-workbench: marketplace entry is missing"
            )
        elif entry.get("description") != description:
            errors.append(
                "plugins/capability-workbench: marketplace description must match manifest"
            )

    return errors


def validate_agent_harness_surface(root: Path) -> list[str]:
    """Keep the Agent Harness routes, contracts, and validator coherent."""
    errors: list[str] = []
    plugin = root / "plugins" / "agent-harness"
    router = plugin / "skills" / "agent-harness" / "SKILL.md"
    validator = plugin / "scripts" / "harness" / "validate_harness_artifact.py"
    skill_names = ("agent-harness-engineering", "agent-harness-evaluation")
    reference_names = (
        "agent-harness-contracts.md",
        "agent-harness-patterns.md",
        "agent-harness-evaluation.md",
        "agent-harness-landscape.md",
    )
    schema_names = (
        "agent_harness.design.v1",
        "agent_harness.evaluation_plan.v1",
        "agent_harness.run_result.v1",
        "agent_harness.run_result.v2",
    )
    credential_skill = plugin / "skills" / "credential-handoff" / "SKILL.md"
    credential_reference = plugin / "references" / "credential-handoff-contract.md"
    credential_helper = plugin / "scripts" / "credential_handoff.py"

    router_text = router.read_text(encoding="utf-8") if router.is_file() else ""
    for path in (credential_skill, credential_reference, credential_helper):
        if not path.is_file():
            errors.append(
                "plugins/agent-harness: missing credential handoff surface "
                f"{path.relative_to(plugin)}"
            )
    for marker in ("credential-handoff", "1Password", "native prompts"):
        if marker not in router_text:
            errors.append(
                "plugins/agent-harness/skills/agent-harness/SKILL.md: "
                f"missing credential route marker {marker!r}"
            )
    for name in skill_names:
        skill = plugin / "skills" / name / "SKILL.md"
        if not skill.is_file():
            errors.append(f"plugins/agent-harness: missing harness skill {name}")
            continue
        text = skill.read_text(encoding="utf-8")
        if "scripts/harness/validate_harness_artifact.py" not in text:
            errors.append(
                f"plugins/agent-harness/skills/{name}/SKILL.md: "
                "missing shared harness artifact validation command"
            )
        if name not in router_text:
            errors.append(
                f"plugins/agent-harness/skills/agent-harness/SKILL.md: "
                f"missing route for {name}"
            )

    if not validator.is_file():
        errors.append("plugins/agent-harness: missing harness artifact validator")
        validator_text = ""
    else:
        validator_text = validator.read_text(encoding="utf-8")

    for name in reference_names:
        path = plugin / "references" / name
        if not path.is_file():
            errors.append(f"plugins/agent-harness: missing harness reference {name}")

    contracts = plugin / "references" / "agent-harness-contracts.md"
    contracts_text = contracts.read_text(encoding="utf-8") if contracts.is_file() else ""
    for schema in schema_names:
        if schema not in contracts_text:
            errors.append(
                f"plugins/agent-harness/references/agent-harness-contracts.md: missing {schema}"
            )
        if schema not in validator_text:
            errors.append(
                f"plugins/agent-harness/scripts/harness/validate_harness_artifact.py: missing {schema}"
            )

    skill_schema_contracts = {
        "agent-harness-engineering": ("agent_harness.design.v1",),
        "agent-harness-evaluation": (
            "agent_harness.evaluation_plan.v1",
            "agent_harness.run_result.v1",
            "agent_harness.run_result.v2",
        ),
    }
    for skill_name, required_schemas in skill_schema_contracts.items():
        skill = plugin / "skills" / skill_name / "SKILL.md"
        text = skill.read_text(encoding="utf-8") if skill.is_file() else ""
        for schema in required_schemas:
            if schema not in text:
                errors.append(
                    f"plugins/agent-harness/skills/{skill_name}/SKILL.md: missing {schema}"
                )

    engineering_skill = plugin / "skills" / "agent-harness-engineering" / "SKILL.md"
    evaluation_skill = plugin / "skills" / "agent-harness-evaluation" / "SKILL.md"
    engineering_text = (
        engineering_skill.read_text(encoding="utf-8") if engineering_skill.is_file() else ""
    )
    evaluation_text = (
        evaluation_skill.read_text(encoding="utf-8") if evaluation_skill.is_file() else ""
    )
    reconfiguration_markers = (
        (router, router_text, ("hot swap", "concurrent runtime generations")),
        (
            engineering_skill,
            engineering_text,
            ("runtime reconfiguration", "runtime_reconfiguration"),
        ),
        (
            evaluation_skill,
            evaluation_text,
            ("concurrent generations", "runtime_reconfiguration"),
        ),
        (
            contracts,
            contracts_text,
            ("candidate_generation", "rollback_via_compare_and_swap"),
        ),
        (
            validator,
            validator_text,
            ("RECONFIGURATION_SCENARIO_CLASSES", "isolation_leak_count"),
        ),
    )
    for path, text, markers in reconfiguration_markers:
        for marker in markers:
            if marker not in text:
                errors.append(
                    f"{path.relative_to(root)}: missing runtime reconfiguration marker {marker!r}"
                )

    return errors


def validate_technology_intelligence_surface(root: Path) -> list[str]:
    """Bind the capability-first decision graph to its offline validator."""
    errors: list[str] = []
    plugin = root / "plugins" / "technology-intelligence"
    helper = plugin / "scripts" / "technology_intelligence.py"
    for relative in (
        "data/capabilities.v1.json",
        "data/interfaces.v1.json",
        "data/runtime-capability.schema.v1.json",
        "data/snapshot-manifest.v1.json",
    ):
        if not (plugin / relative).is_file():
            errors.append(f"plugins/technology-intelligence: missing {relative}")
    if not helper.is_file():
        errors.append("plugins/technology-intelligence: missing offline validator")
        return errors
    result = subprocess.run(
        [sys.executable, str(helper), "validate", "--json"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        errors.append(
            "plugins/technology-intelligence: capability model validation failed:\n"
            f"{result.stdout}{result.stderr}"
        )
    return errors


def validate_architecture_intelligence_surface(root: Path) -> list[str]:
    """Keep the AI-assisted code-architecture evidence path coherent."""
    errors: list[str] = []
    plugin = root / "plugins" / "architecture-intelligence"
    router = plugin / "skills" / "architecture-intelligence" / "SKILL.md"
    skill_name = "architecture-refactoring-strategy"
    skill = plugin / "skills" / skill_name / "SKILL.md"
    reference = plugin / "references" / "ai-assisted-code-architecture.md"
    fixture = plugin / "tests" / "fixtures" / f"{skill_name}-trigger-probes.json"
    contracts = plugin / "references" / "contracts.md"

    required_paths = (router, skill, reference, fixture, contracts)
    for path in required_paths:
        if not path.is_file():
            errors.append(
                "plugins/architecture-intelligence: missing AI-assisted "
                f"code-architecture surface {path.relative_to(plugin)}"
            )

    router_text = router.read_text(encoding="utf-8") if router.is_file() else ""
    skill_text = skill.read_text(encoding="utf-8") if skill.is_file() else ""
    reference_text = reference.read_text(encoding="utf-8") if reference.is_file() else ""
    contracts_text = contracts.read_text(encoding="utf-8") if contracts.is_file() else ""
    for label, text, markers in (
        (
            "router",
            router_text,
            ("AI-assisted code architecture", skill_name, "Agent Harness"),
        ),
        (
            "skill",
            skill_text,
            (
                "architecture of the application or library code",
                "one smallest behavior-preserving architecture slice",
                "review findings before mutation",
            ),
        ),
        (
            "reference",
            reference_text,
            (
                "2026-05-11",
                "2026-08-11",
                "AICA-10",
                "Beyond Correctness",
                "Source-Grounded Rubric",
            ),
        ),
        (
            "contracts",
            contracts_text,
            ("Optional `architecture_assessment` appendix",),
        ),
    ):
        for marker in markers:
            if marker not in text:
                errors.append(
                    "plugins/architecture-intelligence: "
                    f"AI-assisted code-architecture {label} missing {marker!r}"
                )

    if fixture.is_file():
        payload = load_json(fixture, errors)
        if payload is not None:
            if payload.get("schema") != "architecture_intelligence.trigger_probes.v1":
                errors.append(
                    "plugins/architecture-intelligence: invalid AI-assisted "
                    "trigger-probe schema"
                )
            if payload.get("skill") != skill_name:
                errors.append(
                    "plugins/architecture-intelligence: AI-assisted trigger "
                    "probes target the wrong skill"
                )
            if len(payload.get("should_trigger", [])) < 6:
                errors.append(
                    "plugins/architecture-intelligence: AI-assisted trigger "
                    "probes need at least six positive cases"
                )
            if len(payload.get("should_not_trigger", [])) < 4:
                errors.append(
                    "plugins/architecture-intelligence: AI-assisted trigger "
                    "probes need at least four near misses"
                )

    codex_manifest_path = plugin / ".codex-plugin" / "plugin.json"
    manifest = load_json(codex_manifest_path, errors)
    if manifest is not None:
        if "AI-assisted code architecture" not in manifest.get("description", ""):
            errors.append(
                "plugins/architecture-intelligence: Codex manifest does not publish "
                "AI-assisted code architecture"
            )
        if "ai-assisted-code-architecture" not in manifest.get("keywords", []):
            errors.append(
                "plugins/architecture-intelligence: Codex manifest is missing "
                "ai-assisted-code-architecture keyword"
            )

    return errors


def scan_files(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*"):
        if should_skip_scan(root, path):
            continue
        if path.name in {".DS_Store"} or path.suffix == ".pyc":
            errors.append(f"generated artifact must not be committed: {path.relative_to(root)}")
            continue
        if not path.is_file() or path.suffix not in TEXT_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root)
        if CYRILLIC_RE.search(text):
            errors.append(f"{rel}: contains Cyrillic characters")
        if LOCAL_PATH_RE.search(text) or LOCAL_PROJECT_PATH_RE.search(text):
            errors.append(f"{rel}: contains a machine-specific home path")
        if PRIVATE_PROJECT_RE.search(text):
            errors.append(f"{rel}: contains a private project or issue-key reference")
        if GRANDIOSE_RE.search(text):
            errors.append(f"{rel}: contains inflated publication wording")
        if PRIVATE_ORG_WORD_RE.search(text):
            errors.append(f"{rel}: contains private-organization wording")
        if LEGACY_BRAND_RE.search(text):
            errors.append(f"{rel}: contains legacy repository branding")
        if PRIVATE_TOOL_RE.search(text):
            errors.append(f"{rel}: contains a private local tool dependency")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{rel}: matches sensitive pattern {pattern.pattern}")
    return errors


def should_skip_scan(root: Path, path: Path) -> bool:
    rel = path.relative_to(root)
    parts = rel.parts
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    if parts and (
        parts[0] in ROOT_SCRATCH_DIRS
        or any(parts[0].startswith(prefix + "-") for prefix in ROOT_SCRATCH_DIRS)
    ):
        return True
    if len(parts) >= 2 and parts[0] == "docs" and parts[1] == "superpowers":
        return True
    if len(parts) >= 3 and parts[0] == "plugins" and parts[2] in PLUGIN_SCRATCH_DIRS:
        return True
    return False


if __name__ == "__main__":
    main()
