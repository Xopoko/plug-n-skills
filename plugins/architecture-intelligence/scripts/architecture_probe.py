#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".build",
    "node_modules",
    "vendor",
    "build",
    "dist",
    "out",
    "target",
    ".next",
    ".nuxt",
    "DerivedData",
    ".gradle",
}
LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".c": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".h": "c-cpp-header",
    ".hpp": "cpp",
    ".sql": "sql",
}
MANIFEST_NAMES = {
    "package.json",
    "pnpm-workspace.yaml",
    "turbo.json",
    "nx.json",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "go.mod",
    "Cargo.toml",
    "Package.swift",
    "settings.gradle",
    "settings.gradle.kts",
    "build.gradle",
    "build.gradle.kts",
    "pom.xml",
    "composer.json",
    "Gemfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Dockerfile",
}
DEPLOYMENT_FILE_NAMES = {
    "Dockerfile": "container",
    "docker-compose.yml": "container-compose",
    "docker-compose.yaml": "container-compose",
    "compose.yml": "container-compose",
    "compose.yaml": "container-compose",
    "Chart.yaml": "helm",
    "values.yaml": "helm",
    "Procfile": "process-model",
    "serverless.yml": "serverless",
    "serverless.yaml": "serverless",
    "fly.toml": "paas",
    "render.yaml": "paas",
    "netlify.toml": "paas",
    "vercel.json": "paas",
}
CONFIG_FILE_RE = re.compile(r"(^|/)(config|configs|configuration|settings|env)(/|[-_.])|(^|/)\.env(?:[./-]|$)", re.IGNORECASE)
K8S_HINT_RE = re.compile(r"^\s*(apiVersion|kind):\s+", re.MULTILINE)
RUNTIME_SIGNAL_SKIP_RE = re.compile(
    r"(^|/)(tests?|__tests__|skills|references|\.codex-plugin|\.claude-plugin)(/|$)|(^|/)architecture_probe\.py$|(^|/)validate_architecture_intelligence\.py$",
    re.IGNORECASE,
)
TERRAFORM_SUFFIXES = {".tf", ".tfvars"}
RUNTIME_SIGNAL_GROUPS = {
    "observability": {
        "opentelemetry": re.compile(r"\b(openTelemetry|otel|opentelemetry)\b", re.IGNORECASE),
        "prometheus": re.compile(r"\bprometheus\b", re.IGNORECASE),
        "metrics": re.compile(r"\b(metrics?|meter|counter|histogram)\b", re.IGNORECASE),
        "tracing": re.compile(r"\b(tracing|traceId|spanId|distributed trace)\b", re.IGNORECASE),
        "logging": re.compile(r"\b(logger|logging|structured log)\b", re.IGNORECASE),
        "sentry": re.compile(r"\bsentry\b", re.IGNORECASE),
        "datadog": re.compile(r"\bdatadog\b", re.IGNORECASE),
    },
    "resilience": {
        "timeout": re.compile(r"\btimeouts?\b|timeout[_-]?(ms|seconds)?", re.IGNORECASE),
        "retry": re.compile(r"\bretr(?:y|ies)\b|retry[_-]?(policy|strategy)?", re.IGNORECASE),
        "circuit-breaker": re.compile(r"\bcircuit[-_ ]?breaker\b", re.IGNORECASE),
        "fallback": re.compile(r"\bfallback\b", re.IGNORECASE),
        "bulkhead": re.compile(r"\bbulkhead\b", re.IGNORECASE),
        "rate-limit": re.compile(r"\brate[-_ ]?limit", re.IGNORECASE),
        "health-check": re.compile(r"\bhealth(check)?\b|readinessProbe|livenessProbe", re.IGNORECASE),
    },
    "integration": {
        "http": re.compile(r"\b(fetch|axios|requests|NSURLSession|HttpClient|http client)\b", re.IGNORECASE),
        "grpc": re.compile(r"\bgrpc\b", re.IGNORECASE),
        "graphql": re.compile(r"\bgraphql\b", re.IGNORECASE),
        "queue": re.compile(r"\b(kafka|rabbitmq|sqs|pubsub|queue|topic|consumer|producer)\b", re.IGNORECASE),
        "cache": re.compile(r"\b(redis|memcached|cache)\b", re.IGNORECASE),
        "database": re.compile(r"\b(postgres|mysql|mongodb|sqlite|database|datasource)\b", re.IGNORECASE),
    },
}
OWNERSHIP_FILE_TYPES = {
    "CODEOWNERS": "codeowners",
    "OWNERS": "owners",
    "OWNERS_ALIASES": "owners-aliases",
    "MAINTAINERS": "maintainers",
    "GOVERNANCE.MD": "governance",
    "CONTRIBUTING.MD": "contributing",
}
OWNERSHIP_SOURCE_PATH_RE = re.compile(
    r"(^|/)(CODEOWNERS|OWNERS|OWNERS_ALIASES|MAINTAINERS|GOVERNANCE\.md|CONTRIBUTING\.md)$",
    re.IGNORECASE,
)
DOC_HINT_RE = re.compile(r"(architecture|adr|decision|c4|arc42|design-doc|rfc)", re.IGNORECASE)
TEST_HINT_RE = re.compile(r"(^|/)(test|tests|spec|specs|__tests__)(/|$)|(_test|\.test|\.spec)\.", re.IGNORECASE)
PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([A-Za-z_][\w.]*)\s+import|import\s+([A-Za-z_][\w.]*))", re.MULTILINE)
JS_IMPORT_RE = re.compile(r"(?:from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\))")
JVM_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_][\w.]*);?", re.MULTILINE)
SWIFT_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z_][\w]*)", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect conservative architecture facts from a repository.")
    parser.add_argument("path", nargs="?", default=".", help="Repository path to inspect.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown.")
    parser.add_argument("--max-files", type=int, default=6000, help="Maximum files to scan.")
    parser.add_argument("--git-history", action="store_true", help="Include git churn and co-change signals when available.")
    parser.add_argument("--git-commits", type=int, default=200, help="Maximum git commits to inspect for --git-history.")
    parser.add_argument("--policy", default="", help="Optional architecture_intelligence.policy.v1 JSON file.")
    return parser.parse_args()


def should_skip_dir(name: str) -> bool:
    return name in EXCLUDE_DIRS or name.endswith(".xcodeproj") or name.endswith(".xcworkspace")


def iter_files(root: Path, max_files: int) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not should_skip_dir(name)]
        for filename in filenames:
            path = Path(current) / filename
            files.append(path)
            if len(files) >= max_files:
                return files, True
    return files, truncated


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:200_000]
    except OSError:
        return ""


def top_component(relative_path: str) -> str:
    return relative_path.split("/", 1)[0]


def collect_imports(path: Path, text: str) -> list[str]:
    suffix = path.suffix.lower()
    imports: list[str] = []
    if suffix == ".py":
        for match in PY_IMPORT_RE.finditer(text):
            imports.append(next(group for group in match.groups() if group))
    elif suffix in {".js", ".jsx", ".ts", ".tsx"}:
        for match in JS_IMPORT_RE.finditer(text):
            imports.append(next(group for group in match.groups() if group))
    elif suffix in {".java", ".kt", ".kts"}:
        imports.extend(match.group(1) for match in JVM_IMPORT_RE.finditer(text))
    elif suffix == ".swift":
        imports.extend(match.group(1) for match in SWIFT_IMPORT_RE.finditer(text))
    return imports


def collect_git_history(root: Path, max_commits: int) -> dict[str, Any]:
    try:
        top_level_result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if top_level_result.returncode != 0:
            return {
                "available": False,
                "error": top_level_result.stderr.strip() or "not a git repository",
                "changed_files": [],
                "cochange_pairs": [],
            }
        git_root = Path(top_level_result.stdout.strip()).resolve()
        try:
            pathspec = root.resolve().relative_to(git_root).as_posix()
        except ValueError:
            pathspec = "."
        if not pathspec:
            pathspec = "."
        result = subprocess.run(
            [
                "git",
                "-C",
                str(git_root),
                "log",
                f"-n{max_commits}",
                "--name-only",
                "--pretty=format:__COMMIT__",
                "--",
                pathspec,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        return {"available": False, "error": str(exc), "changed_files": [], "cochange_pairs": []}
    if result.returncode != 0:
        return {
            "available": False,
            "error": result.stderr.strip() or "git log failed",
            "changed_files": [],
            "cochange_pairs": [],
        }

    commits: list[list[str]] = []
    current: list[str] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "__COMMIT__":
            if current:
                commits.append(current)
                current = []
            continue
        if pathspec != "." and line.startswith(pathspec + "/"):
            line = line[len(pathspec) + 1:]
        current.append(line)
    if current:
        commits.append(current)

    changed_files: Counter[str] = Counter()
    cochange_pairs: Counter[tuple[str, str]] = Counter()
    for files in commits:
        unique_files = sorted(set(files))
        changed_files.update(unique_files)
        components = sorted({top_component(path) for path in unique_files if "/" in path})
        for index, left in enumerate(components):
            for right in components[index + 1:]:
                cochange_pairs[(left, right)] += 1

    return {
        "available": True,
        "error": "",
        "commit_count": len(commits),
        "changed_files": [
            {"path": path, "count": count}
            for path, count in changed_files.most_common(30)
        ],
        "cochange_pairs": [
            {"left": left, "right": right, "count": count}
            for (left, right), count in cochange_pairs.most_common(30)
        ],
    }


def load_policy(path: str) -> dict[str, Any]:
    if not path:
        return {}
    policy_path = Path(path).expanduser()
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "schema": "architecture_intelligence.policy.v1",
            "_load_error": str(exc),
            "_policy_path": str(policy_path),
        }
    if not isinstance(payload, dict):
        return {
            "schema": "architecture_intelligence.policy.v1",
            "_load_error": "policy file must contain a JSON object",
            "_policy_path": str(policy_path),
        }
    payload["_policy_path"] = str(policy_path)
    return payload


def edge_present(report: dict[str, Any], source: str, target: str) -> bool:
    for edge in report.get("internal_edges", []):
        if edge.get("from") == source and edge.get("to") == target:
            return True
    return False


def canonical_cycle(path: list[str]) -> tuple[str, ...]:
    cycle = path[:-1] if len(path) > 1 and path[0] == path[-1] else path
    rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
    return min(rotations)


def find_cycles(internal_edges: Counter[tuple[str, str]], *, max_cycles: int = 20, max_depth: int = 8) -> list[dict[str, Any]]:
    adjacency: dict[str, set[str]] = {}
    for source, target in internal_edges:
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set())

    seen: set[tuple[str, ...]] = set()
    cycles: list[dict[str, Any]] = []

    def visit(start: str, current: str, path: list[str], visited: set[str]) -> None:
        if len(cycles) >= max_cycles:
            return
        for target in sorted(adjacency.get(current, set())):
            if target == start and len(path) > 1:
                key = canonical_cycle(path + [start])
                if key not in seen:
                    seen.add(key)
                    cycles.append({
                        "path": list(key) + [key[0]],
                        "length": len(key),
                        "evidence": "top-level static import cycle",
                    })
            elif target not in visited and len(path) < max_depth:
                visit(start, target, path + [target], visited | {target})

    for start in sorted(adjacency):
        visit(start, start, [start], {start})
        if len(cycles) >= max_cycles:
            break
    return cycles


def compute_structure_metrics(
    local_roots: set[str],
    internal_edges: Counter[tuple[str, str]],
) -> dict[str, Any]:
    incoming: dict[str, set[str]] = {name: set() for name in local_roots}
    outgoing: dict[str, set[str]] = {name: set() for name in local_roots}
    incoming_edge_counts: Counter[str] = Counter()
    outgoing_edge_counts: Counter[str] = Counter()

    for (source, target), count in internal_edges.items():
        outgoing.setdefault(source, set()).add(target)
        incoming.setdefault(target, set()).add(source)
        incoming.setdefault(source, set())
        outgoing.setdefault(target, set())
        outgoing_edge_counts[source] += count
        incoming_edge_counts[target] += count

    components = []
    for name in sorted(set(local_roots) | set(incoming) | set(outgoing)):
        afferent = len(incoming.get(name, set()))
        efferent = len(outgoing.get(name, set()))
        total = afferent + efferent
        instability = round(efferent / total, 3) if total else 0.0
        if total == 0:
            role = "isolated"
        elif afferent and not efferent:
            role = "stable"
        elif efferent and not afferent:
            role = "volatile"
        else:
            role = "balanced"
        components.append({
            "name": name,
            "afferent_coupling": afferent,
            "efferent_coupling": efferent,
            "incoming_edges": incoming_edge_counts[name],
            "outgoing_edges": outgoing_edge_counts[name],
            "instability": instability,
            "stability_role": role,
            "evidence": "top-level static imports",
        })

    cycles = find_cycles(internal_edges)
    return {
        "schema": "architecture_intelligence.structure_metrics.v1",
        "target": "repository",
        "observed_model_source": "architecture_probe.py static import graph",
        "components": sorted(
            components,
            key=lambda item: (
                item["efferent_coupling"] + item["afferent_coupling"],
                item["outgoing_edges"] + item["incoming_edges"],
                item["name"],
            ),
            reverse=True,
        ),
        "cycles": cycles,
        "summary": {
            "component_count": len(components),
            "internal_edge_count": sum(internal_edges.values()),
            "cycle_count": len(cycles),
            "max_efferent_coupling": max((item["efferent_coupling"] for item in components), default=0),
            "max_afferent_coupling": max((item["afferent_coupling"] for item in components), default=0),
        },
        "interpretation": {
            "summary": "Static structure metrics are warning signals for architecture review.",
            "limitations": "Top-level import metrics miss runtime calls, generated code, reflection, ownership, and domain intent.",
        },
        "next_actions": [
            "Inspect high fan-out components for change amplification.",
            "Review dependency cycles against intended architecture.",
        ],
    }


def append_limited(bucket: dict[str, set[str]], key: str, path: str, *, limit: int = 20) -> None:
    values = bucket.setdefault(key, set())
    if len(values) < limit:
        values.add(path)


def ownership_source_type(path: Path) -> str:
    name = path.name.upper()
    return OWNERSHIP_FILE_TYPES.get(name, "ownership-document")


def parse_codeowners(text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0]
        owners = [owner for owner in parts[1:] if owner and not owner.startswith("#")]
        if not owners:
            continue
        entries.append({
            "pattern": pattern,
            "owners": owners,
            "line": line_number,
        })
    return entries


def parse_owners_file(text: str) -> list[str]:
    owners: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("owners:"):
            values = re.split(r"[, ]+", line.split(":", 1)[1].strip())
            owners.extend(value for value in values if value)
            continue
        if ":" in line and not line.startswith("@"):
            continue
        owners.append(line)
    return owners


def normalized_codeowners_pattern(pattern: str) -> str:
    value = pattern.strip().lstrip("/")
    value = value.split("#", 1)[0].strip()
    while value.startswith("./"):
        value = value[2:]
    return value


def codeowners_pattern_matches_component(pattern: str, component: str) -> bool:
    normalized = normalized_codeowners_pattern(pattern)
    if not normalized:
        return False
    if normalized in {"*", "**", "/"}:
        return True
    if normalized.startswith(("**/", "*/")):
        normalized = normalized.split("/", 1)[1]
    first = normalized.split("/", 1)[0]
    first = first.rstrip("*")
    if not first or any(marker in first for marker in ("?", "[")):
        return normalized.startswith(component + "/") or normalized == component
    return first == component or normalized.startswith(component + "/")


def collect_ownership_topology(
    files: list[Path],
    root: Path,
    areas: set[str],
    internal_edges: Counter[tuple[str, str]],
    runtime_topology: dict[str, Any],
) -> dict[str, Any]:
    ownership_sources: list[dict[str, Any]] = []
    area_owners: dict[str, set[str]] = {area: set() for area in areas}
    area_evidence: dict[str, set[str]] = {area: set() for area in areas}
    source_owner_entries: list[dict[str, Any]] = []

    for path in files:
        relative = rel(path, root)
        if not OWNERSHIP_SOURCE_PATH_RE.search(relative):
            continue
        source_type = ownership_source_type(path)
        text = read_text(path)
        source_record = {
            "path": relative,
            "type": source_type,
            "evidence": "ownership or governance document detected",
            "confidence": "medium" if source_type in {"codeowners", "owners"} else "low",
        }
        ownership_sources.append(source_record)
        if source_type == "codeowners":
            for entry in parse_codeowners(text):
                source_owner_entries.append({
                    "source_path": relative,
                    "pattern": entry["pattern"],
                    "owners": entry["owners"],
                    "line": entry["line"],
                })
                for area in areas:
                    if codeowners_pattern_matches_component(entry["pattern"], area):
                        area_owners.setdefault(area, set()).update(entry["owners"])
                        area_evidence.setdefault(area, set()).add(f"{relative}:{entry['line']} {entry['pattern']}")
        elif source_type == "owners":
            owners = parse_owners_file(text)
            parent = Path(relative).parent.as_posix()
            target_area = top_component(parent) if parent not in {"", "."} else ""
            for owner in owners:
                source_owner_entries.append({
                    "source_path": relative,
                    "pattern": parent,
                    "owners": [owner],
                    "line": 0,
                })
            if target_area and target_area in areas:
                area_owners.setdefault(target_area, set()).update(owners)
                area_evidence.setdefault(target_area, set()).add(relative)

    area_records: list[dict[str, Any]] = []
    for area in sorted(areas):
        owners = sorted(area_owners.get(area, set()))
        area_records.append({
            "path": area,
            "owners": owners,
            "evidence": sorted(area_evidence.get(area, set()))[:12],
            "coverage": "owned" if owners else "unowned",
        })

    coordination_risks: list[dict[str, str]] = []
    cross_owned_edges = 0
    for (source, target), count in internal_edges.most_common(40):
        source_owners = area_owners.get(source, set())
        target_owners = area_owners.get(target, set())
        if not source_owners or not target_owners or source_owners & target_owners:
            continue
        cross_owned_edges += 1
        coordination_risks.append({
            "id": f"cross-owned-{source.lower().replace('_', '-')}-to-{target.lower().replace('_', '-')}",
            "severity": "P2",
            "evidence": (
                f"{source} -> {target} static import edge count {count}; "
                f"{source} owners={', '.join(sorted(source_owners))}; "
                f"{target} owners={', '.join(sorted(target_owners))}"
            ),
            "impact": "Architecture changes across this dependency may need coordination between different owner sets.",
            "recommendation": "Name the API or boundary contract and require review from both owner paths for architecture-changing work.",
            "confidence": "medium",
        })

    runtime_evidence_paths = {
        path
        for surface in runtime_topology.get("surfaces", [])
        for path in surface.get("evidence", [])
        if isinstance(path, str) and "/" in path
    }
    ownerless_runtime_or_code_surfaces = 0
    unowned = [item for item in area_records if item["coverage"] == "unowned"]
    for item in unowned[:8]:
        area = item["path"]
        has_runtime_evidence = any(top_component(path) == area for path in runtime_evidence_paths)
        if has_runtime_evidence:
            ownerless_runtime_or_code_surfaces += 1
        severity = "P2" if has_runtime_evidence else "P3"
        coordination_risks.append({
            "id": f"ownerless-{area.lower().replace('_', '-')}",
            "severity": severity,
            "evidence": f"No CODEOWNERS/OWNERS mapping detected for top-level area `{area}`.",
            "impact": "Architecture ownership or review path may be unclear for changes in this area.",
            "recommendation": "Confirm the responsible owner or document why this area is intentionally shared.",
            "confidence": "low",
        })

    if not ownership_sources:
        coordination_risks.insert(0, {
            "id": "no-ownership-sources",
            "severity": "P3",
            "evidence": "No CODEOWNERS, OWNERS, MAINTAINERS, GOVERNANCE.md, or CONTRIBUTING.md file was detected.",
            "impact": "Architecture review paths may be tribal knowledge rather than source-backed.",
            "recommendation": "Add an ownership or governance document for architecture-significant modules.",
            "confidence": "medium",
        })

    return {
        "schema": "architecture_intelligence.ownership_topology.v1",
        "target": "repository",
        "observed_model_source": "architecture_probe.py ownership document, static import, and runtime-surface scan",
        "ownership_sources": sorted(ownership_sources, key=lambda item: item["path"]),
        "areas": area_records,
        "coordination_risks": coordination_risks[:30],
        "summary": {
            "ownership_sources": len(ownership_sources),
            "owned_areas": sum(1 for item in area_records if item["coverage"] == "owned"),
            "unowned_areas": sum(1 for item in area_records if item["coverage"] == "unowned"),
            "cross_owned_edges": cross_owned_edges,
            "ownerless_runtime_or_code_surfaces": ownerless_runtime_or_code_surfaces,
        },
        "limitations": [
            "Ownership files can be stale, partial, or unenforced.",
            "CODEOWNERS matching is conservative and does not implement every GitHub pattern rule.",
            "The probe cannot infer actual team communication, availability, or review behavior.",
            "Static imports miss runtime calls, generated code, reflection, and service-level ownership.",
        ],
        "next_actions": [
            "Review cross-owned dependency edges against architecture intent.",
            "Add or update ownership docs for architecture-significant unowned areas.",
            "Turn confirmed ownership rules into CODEOWNERS review gates or architecture fitness functions.",
        ],
    }


def collect_runtime_topology(files: list[Path], root: Path) -> dict[str, Any]:
    deployment: dict[str, set[str]] = {}
    runtime_config: set[str] = set()
    signals: dict[str, dict[str, set[str]]] = {
        "observability": {},
        "resilience": {},
        "integration": {},
    }

    for path in files:
        relative = rel(path, root)
        file_kind = DEPLOYMENT_FILE_NAMES.get(path.name)
        if file_kind:
            append_limited(deployment, file_kind, relative)
        if path.suffix in TERRAFORM_SUFFIXES:
            append_limited(deployment, "infrastructure-as-code", relative)
        text = ""
        suffix = path.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            text = read_text(path)
            if K8S_HINT_RE.search(text) and re.search(r"\b(Deployment|Service|Ingress|StatefulSet|DaemonSet|Job|CronJob)\b", text):
                append_limited(deployment, "kubernetes", relative)
        if CONFIG_FILE_RE.search(relative):
            if len(runtime_config) < 40:
                runtime_config.add(relative)
        if RUNTIME_SIGNAL_SKIP_RE.search(relative):
            continue
        if suffix in LANGUAGES or suffix in {".json", ".yaml", ".yml", ".toml", ".tf", ".xml", ".properties", ".gradle", ".kts"} or path.name in MANIFEST_NAMES:
            text = text or read_text(path)
            for group, patterns in RUNTIME_SIGNAL_GROUPS.items():
                for name, pattern in patterns.items():
                    if pattern.search(text):
                        append_limited(signals[group], name, relative)

    surfaces: list[dict[str, Any]] = []
    for kind, paths in sorted(deployment.items()):
        surfaces.append({
            "type": "deployment",
            "name": kind,
            "evidence": sorted(paths),
            "confidence": "medium",
        })
    if runtime_config:
        surfaces.append({
            "type": "runtime-config",
            "name": "configuration-files",
            "evidence": sorted(runtime_config)[:40],
            "confidence": "low",
        })
    for group, grouped_signals in signals.items():
        for name, paths in sorted(grouped_signals.items()):
            surfaces.append({
                "type": group,
                "name": name,
                "evidence": sorted(paths),
                "confidence": "low",
            })

    hypotheses: list[dict[str, str]] = []
    if deployment:
        hypotheses.append({
            "id": "deployment-surface-present",
            "claim": "Deployment artifacts are present and should be reviewed as architecture evidence.",
            "evidence": ", ".join(sorted(next(iter(deployment.values())))) if deployment else "",
            "confidence": "medium",
            "validation": "Inspect deployment topology against runtime architecture intent.",
        })
    if signals["integration"]:
        hypotheses.append({
            "id": "runtime-integration-present",
            "claim": "Runtime integration signals are present and may define architecture coupling beyond source imports.",
            "evidence": ", ".join(sorted({path for paths in signals["integration"].values() for path in paths})[:5]),
            "confidence": "low",
            "validation": "Trace representative runtime calls and failure modes.",
        })
    if signals["observability"]:
        hypotheses.append({
            "id": "observability-surface-present",
            "claim": "Observability signals are present and should be checked for coverage of critical runtime paths.",
            "evidence": ", ".join(sorted({path for paths in signals["observability"].values() for path in paths})[:5]),
            "confidence": "low",
            "validation": "Verify metrics, logs, and traces cover critical architecture scenarios.",
        })

    gaps: list[dict[str, str]] = []
    if not signals["resilience"]:
        gaps.append({
            "attribute": "availability",
            "signal": "no timeout, retry, circuit-breaker, fallback, bulkhead, rate-limit, or health-check terms detected",
            "risk": "unknown",
        })
    if not signals["observability"]:
        gaps.append({
            "attribute": "operability",
            "signal": "no observability, tracing, logging, metrics, or telemetry terms detected",
            "risk": "unknown",
        })

    return {
        "schema": "architecture_intelligence.runtime_topology.v1",
        "target": "repository",
        "observed_model_source": "architecture_probe.py repository file and signal scan",
        "surfaces": surfaces,
        "topology_hypotheses": hypotheses,
        "quality_attribute_gaps": gaps,
        "summary": {
            "deployment_artifacts": sum(len(paths) for paths in deployment.values()),
            "runtime_config_files": len(runtime_config),
            "observability_signals": sum(len(paths) for paths in signals["observability"].values()),
            "resilience_signals": sum(len(paths) for paths in signals["resilience"].values()),
            "integration_signals": sum(len(paths) for paths in signals["integration"].values()),
        },
        "limitations": [
            "Signals are path and term based; they do not prove runtime behavior.",
            "The probe records file paths and signal names only, not configuration values.",
            "Production state, trace coverage, and failure behavior need project-specific evidence.",
        ],
        "next_actions": [
            "Map deployment artifacts to runtime components and ownership.",
            "Check resilience tactics against quality-attribute scenarios.",
            "Verify observability covers critical runtime paths.",
        ],
    }


def check_policy(root: Path, report: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    if not policy:
        return {
            "schema": "architecture_intelligence.policy_result.v1",
            "requested": False,
            "policy_path": "",
            "summary": {"pass": 0, "fail": 0, "unknown": 0},
            "checks": [],
        }

    checks: list[dict[str, str]] = []
    if policy.get("_load_error"):
        checks.append({
            "id": "policy-load",
            "type": "policy-load",
            "status": "unknown",
            "reason": str(policy["_load_error"]),
        })
    elif policy.get("schema") != "architecture_intelligence.policy.v1":
        checks.append({
            "id": "policy-schema",
            "type": "policy-schema",
            "status": "unknown",
            "reason": "policy schema must be architecture_intelligence.policy.v1",
        })

    for index, rule in enumerate(policy.get("forbidden_edges", []) or []):
        if not isinstance(rule, dict):
            checks.append({
                "id": f"forbidden-edge-{index + 1}",
                "type": "forbidden-edge",
                "status": "unknown",
                "reason": "rule must be an object",
            })
            continue
        source = str(rule.get("from", "")).strip()
        target = str(rule.get("to", "")).strip()
        present = bool(source and target and edge_present(report, source, target))
        checks.append({
            "id": f"forbidden-edge-{source}-to-{target}" if source and target else f"forbidden-edge-{index + 1}",
            "type": "forbidden-edge",
            "status": "fail" if present else "pass",
            "from": source,
            "to": target,
            "reason": str(rule.get("reason", "")),
        })

    for index, rule in enumerate(policy.get("required_edges", []) or []):
        if not isinstance(rule, dict):
            checks.append({
                "id": f"required-edge-{index + 1}",
                "type": "required-edge",
                "status": "unknown",
                "reason": "rule must be an object",
            })
            continue
        source = str(rule.get("from", "")).strip()
        target = str(rule.get("to", "")).strip()
        present = bool(source and target and edge_present(report, source, target))
        checks.append({
            "id": f"required-edge-{source}-to-{target}" if source and target else f"required-edge-{index + 1}",
            "type": "required-edge",
            "status": "pass" if present else "fail",
            "from": source,
            "to": target,
            "reason": str(rule.get("reason", "")),
        })

    for index, doc_path in enumerate(policy.get("required_documents", []) or []):
        relative = str(doc_path).strip()
        exists = bool(relative and (root / relative).is_file())
        checks.append({
            "id": f"required-document-{index + 1}",
            "type": "required-document",
            "status": "pass" if exists else "fail",
            "path": relative,
            "reason": "required architecture document",
        })

    summary = {
        "pass": sum(1 for check in checks if check.get("status") == "pass"),
        "fail": sum(1 for check in checks if check.get("status") == "fail"),
        "unknown": sum(1 for check in checks if check.get("status") == "unknown"),
    }
    return {
        "schema": "architecture_intelligence.policy_result.v1",
        "requested": True,
        "policy_path": str(policy.get("_policy_path", "")),
        "summary": summary,
        "checks": checks,
    }


def summarize(
    root: Path,
    max_files: int,
    *,
    include_git_history: bool = False,
    git_commits: int = 200,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    files, truncated = iter_files(root, max_files)
    language_counts: Counter[str] = Counter()
    top_dirs: Counter[str] = Counter()
    manifest_paths: list[str] = []
    doc_paths: list[str] = []
    test_paths: list[str] = []
    import_targets: Counter[str] = Counter()
    internal_edges: Counter[tuple[str, str]] = Counter()
    local_roots: set[str] = set()
    code_roots: set[str] = set()

    for path in files:
        relative = rel(path, root)
        component = top_component(relative)
        if "/" in relative:
            local_roots.add(component)
            top_dirs[component] += 1
        suffix = path.suffix.lower()
        if suffix in LANGUAGES:
            language_counts[LANGUAGES[suffix]] += 1
            if "/" in relative:
                code_roots.add(component)
        if path.name in MANIFEST_NAMES:
            manifest_paths.append(relative)
        if DOC_HINT_RE.search(relative):
            doc_paths.append(relative)
        if TEST_HINT_RE.search(relative):
            test_paths.append(relative)

    for path in files:
        if path.suffix.lower() not in LANGUAGES:
            continue
        source_component = top_component(rel(path, root))
        for target in collect_imports(path, read_text(path)):
            normalized = target.lstrip(".").split(".", 1)[0].split("/", 1)[0]
            if not normalized:
                continue
            import_targets[normalized] += 1
            if normalized in code_roots and normalized != source_component:
                internal_edges[(source_component, normalized)] += 1

    risks: list[dict[str, str]] = []
    if not doc_paths:
        risks.append({
            "id": "no-architecture-docs",
            "severity": "P3",
            "reason": "No architecture, ADR, RFC, C4, or decision document paths were detected.",
        })
    if not test_paths:
        risks.append({
            "id": "no-tests-detected",
            "severity": "P2",
            "reason": "No common test/spec file or directory names were detected.",
        })
    if len(language_counts) >= 5:
        risks.append({
            "id": "many-language-surfaces",
            "severity": "P3",
            "reason": "Five or more implementation language surfaces were detected; architecture ownership may be fragmented.",
        })
    for directory, count in top_dirs.most_common(5):
        if count >= 250:
            risks.append({
                "id": f"large-{directory.lower().replace('_', '-')}-surface",
                "severity": "P2",
                "reason": f"Top-level directory `{directory}` contains {count} scanned files.",
            })
    if not manifest_paths:
        risks.append({
            "id": "no-dependency-manifests",
            "severity": "P3",
            "reason": "No common dependency or build manifests were detected.",
        })
    git_history = (
        collect_git_history(root, git_commits)
        if include_git_history
        else {"available": False, "error": "not requested", "changed_files": [], "cochange_pairs": []}
    )
    if git_history.get("available") and git_history.get("cochange_pairs"):
        top_pair = git_history["cochange_pairs"][0]
        if int(top_pair["count"]) >= 5:
            risks.append({
                "id": "high-cochange-hotspot",
                "severity": "P2",
                "reason": (
                    f"`{top_pair['left']}` and `{top_pair['right']}` changed together "
                    f"{top_pair['count']} times in the inspected history."
                ),
            })

    structure_metrics = compute_structure_metrics(code_roots, internal_edges)
    if structure_metrics["summary"]["cycle_count"]:
        risks.append({
            "id": "dependency-cycle",
            "severity": "P2",
            "reason": f"{structure_metrics['summary']['cycle_count']} top-level dependency cycles were detected.",
        })
    high_fan_out = [
        item for item in structure_metrics["components"]
        if item["efferent_coupling"] >= 5
    ]
    if high_fan_out:
        risks.append({
            "id": "high-fan-out-component",
            "severity": "P3",
            "reason": f"`{high_fan_out[0]['name']}` depends on {high_fan_out[0]['efferent_coupling']} top-level components.",
        })
    runtime_topology = collect_runtime_topology(files, root)
    if runtime_topology["summary"]["integration_signals"] and not runtime_topology["summary"]["resilience_signals"]:
        risks.append({
            "id": "integration-without-resilience-signals",
            "severity": "P3",
            "reason": "Runtime integration signals were detected but no resilience terms were found.",
        })
    if runtime_topology["summary"]["deployment_artifacts"] and not runtime_topology["summary"]["observability_signals"]:
        risks.append({
            "id": "deployment-without-observability-signals",
            "severity": "P3",
            "reason": "Deployment artifacts were detected but no observability terms were found.",
        })
    ownership_topology = collect_ownership_topology(
        files,
        root,
        code_roots or local_roots,
        internal_edges,
        runtime_topology,
    )
    if ownership_topology["summary"]["cross_owned_edges"]:
        risks.append({
            "id": "cross-owned-dependency-edge",
            "severity": "P2",
            "reason": f"{ownership_topology['summary']['cross_owned_edges']} static dependency edges cross different owner sets.",
        })
    if ownership_topology["summary"]["unowned_areas"] and ownership_topology["summary"]["ownership_sources"]:
        risks.append({
            "id": "unowned-architecture-area",
            "severity": "P3",
            "reason": f"{ownership_topology['summary']['unowned_areas']} top-level areas have no detected ownership mapping.",
        })
    if not ownership_topology["summary"]["ownership_sources"]:
        risks.append({
            "id": "no-ownership-sources",
            "severity": "P3",
            "reason": "No CODEOWNERS, OWNERS, MAINTAINERS, GOVERNANCE.md, or CONTRIBUTING.md file was detected.",
        })

    report = {
        "schema": "architecture_intelligence.probe.v1",
        "root": str(root),
        "file_count": len(files),
        "truncated": truncated,
        "languages": [
            {"language": name, "files": count}
            for name, count in language_counts.most_common()
        ],
        "top_level_directories": [
            {"path": name, "files": count}
            for name, count in top_dirs.most_common(12)
        ],
        "manifests": sorted(manifest_paths)[:80],
        "architecture_documents": sorted(doc_paths)[:80],
        "test_surfaces": sorted(test_paths)[:80],
        "import_targets": [
            {"target": name, "count": count}
            for name, count in import_targets.most_common(30)
        ],
        "internal_edges": [
            {"from": source, "to": target, "count": count}
            for (source, target), count in internal_edges.most_common(40)
        ],
        "structure_metrics": structure_metrics,
        "runtime_topology": runtime_topology,
        "ownership_topology": ownership_topology,
        "git_history": git_history,
        "risks": risks,
    }
    policy_checks = check_policy(root, report, policy or {})
    report["policy_checks"] = policy_checks
    if policy_checks["summary"]["fail"]:
        risks.append({
            "id": "architecture-policy-failed",
            "severity": "P1",
            "reason": f"{policy_checks['summary']['fail']} architecture policy checks failed.",
        })
    if policy_checks["summary"]["unknown"]:
        risks.append({
            "id": "architecture-policy-unknown",
            "severity": "P2",
            "reason": f"{policy_checks['summary']['unknown']} architecture policy checks could not be evaluated.",
        })
    return report


def emit_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Architecture Probe",
        "",
        f"Files scanned: {report['file_count']}",
        f"Truncated: {str(report['truncated']).lower()}",
        "",
        "## Languages",
    ]
    for item in report["languages"] or [{"language": "none", "files": 0}]:
        lines.append(f"- {item['language']}: {item['files']}")
    lines.append("")
    lines.append("## Top Directories")
    for item in report["top_level_directories"][:10]:
        lines.append(f"- {item['path']}: {item['files']}")
    lines.append("")
    lines.append("## Manifests")
    for item in report["manifests"][:20]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Architecture Documents")
    for item in report["architecture_documents"][:20]:
        lines.append(f"- {item}")
    lines.append("")
    git_history = report.get("git_history", {})
    if git_history.get("available"):
        lines.append("## Git History")
        lines.append(f"Commits inspected: {git_history.get('commit_count', 0)}")
        lines.append("")
        lines.append("### Changed Files")
        for item in git_history.get("changed_files", [])[:10]:
            lines.append(f"- {item['path']}: {item['count']}")
        lines.append("")
        lines.append("### Co-Change Pairs")
        for item in git_history.get("cochange_pairs", [])[:10]:
            lines.append(f"- {item['left']} <-> {item['right']}: {item['count']}")
    lines.append("")
    structure_metrics = report.get("structure_metrics", {})
    if structure_metrics:
        lines.append("## Structure Metrics")
        summary = structure_metrics.get("summary", {})
        lines.append(
            f"Components: {summary.get('component_count', 0)}, "
            f"internal edges: {summary.get('internal_edge_count', 0)}, "
            f"cycles: {summary.get('cycle_count', 0)}"
        )
        for item in structure_metrics.get("components", [])[:10]:
            lines.append(
                f"- {item['name']}: Ca={item['afferent_coupling']}, "
                f"Ce={item['efferent_coupling']}, I={item['instability']}"
            )
        for item in structure_metrics.get("cycles", [])[:5]:
            lines.append(f"- cycle: {' -> '.join(item['path'])}")
        lines.append("")
    runtime_topology = report.get("runtime_topology", {})
    if runtime_topology:
        lines.append("## Runtime Topology")
        summary = runtime_topology.get("summary", {})
        lines.append(
            f"Deployment artifacts: {summary.get('deployment_artifacts', 0)}, "
            f"observability signals: {summary.get('observability_signals', 0)}, "
            f"resilience signals: {summary.get('resilience_signals', 0)}, "
            f"integration signals: {summary.get('integration_signals', 0)}"
        )
        for item in runtime_topology.get("surfaces", [])[:12]:
            lines.append(f"- {item['type']} / {item['name']}: {', '.join(item['evidence'][:3])}")
        lines.append("")
    ownership_topology = report.get("ownership_topology", {})
    if ownership_topology:
        lines.append("## Ownership Topology")
        summary = ownership_topology.get("summary", {})
        lines.append(
            f"Ownership sources: {summary.get('ownership_sources', 0)}, "
            f"owned areas: {summary.get('owned_areas', 0)}, "
            f"unowned areas: {summary.get('unowned_areas', 0)}, "
            f"cross-owned edges: {summary.get('cross_owned_edges', 0)}"
        )
        for item in ownership_topology.get("areas", [])[:10]:
            owners = ", ".join(item.get("owners", [])) or "unowned"
            lines.append(f"- {item['path']}: {owners}")
        for item in ownership_topology.get("coordination_risks", [])[:5]:
            lines.append(f"- {item['severity']} {item['id']}: {item['recommendation']}")
        lines.append("")
    policy_checks = report.get("policy_checks", {})
    if policy_checks.get("requested"):
        lines.append("## Policy Checks")
        summary = policy_checks.get("summary", {})
        lines.append(
            f"Pass: {summary.get('pass', 0)}, "
            f"fail: {summary.get('fail', 0)}, "
            f"unknown: {summary.get('unknown', 0)}"
        )
        for item in policy_checks.get("checks", [])[:20]:
            label = item.get("id", item.get("type", "check"))
            lines.append(f"- {item.get('status', 'unknown')} {label}: {item.get('reason', '')}")
        lines.append("")
    lines.append("## Risks")
    if report["risks"]:
        for risk in report["risks"]:
            lines.append(f"- {risk['severity']} {risk['id']}: {risk['reason']}")
    else:
        lines.append("- none detected by this conservative probe")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    report = summarize(
        root,
        args.max_files,
        include_git_history=args.git_history,
        git_commits=args.git_commits,
        policy=load_policy(args.policy),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(emit_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
