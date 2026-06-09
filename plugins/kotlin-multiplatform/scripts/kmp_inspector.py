#!/usr/bin/env python3
"""Offline Kotlin Multiplatform project inspector.

This script reads Gradle/KMP project files and emits static diagnostics. It does
not execute Gradle, modify files, use the network, or load project code.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


BUILD_FILE_NAMES = ("build.gradle.kts", "build.gradle")
SETTINGS_FILE_NAMES = ("settings.gradle.kts", "settings.gradle")


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    file: str | None = None


@dataclass
class ModuleReport:
    name: str
    path: str
    build_file: str
    plugins: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    source_sets: list[str] = field(default_factory=list)
    classification: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class ReadinessArea:
    name: str
    score: int
    max_score: int
    verdict: str
    evidence: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass
class ProjectReport:
    root: str
    settings_files: list[str]
    gradle_wrapper_version: str | None
    version_catalog: str | None
    gradle_properties: dict[str, str]
    catalog_versions: dict[str, str]
    catalog_plugins: dict[str, str]
    modules: list[ModuleReport]
    diagnostics: list[Diagnostic]
    readiness: list[ReadinessArea]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="ignore")


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a Kotlin Multiplatform Gradle project.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "info", "none"),
        default="error",
        help="Return exit code 2 when diagnostics at or above this severity exist. Defaults to error.",
    )
    return parser.parse_args()


def parse_wrapper_version(root: Path) -> str | None:
    wrapper = root / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not wrapper.is_file():
        return None
    match = re.search(r"gradle-([0-9][^-\/]+)-", read_text(wrapper))
    return match.group(1) if match else None


def parse_version_catalog(root: Path) -> tuple[str | None, dict[str, str], dict[str, str]]:
    catalog = root / "gradle" / "libs.versions.toml"
    if not catalog.is_file():
        return None, {}, {}
    text = read_text(catalog)
    versions: dict[str, str] = {}
    plugins: dict[str, str] = {}
    section = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        section_match = re.fullmatch(r"\[([A-Za-z0-9_.-]+)\]", line)
        if section_match:
            section = section_match.group(1)
            continue
        if section == "versions":
            match = re.match(r"([A-Za-z0-9_.-]+)\s*=\s*\"([^\"]+)\"", line)
            if match:
                versions[match.group(1)] = match.group(2)
        elif section == "plugins":
            match = re.match(r"([A-Za-z0-9_.-]+)\s*=\s*\{[^}]*id\s*=\s*\"([^\"]+)\"", line)
            if match:
                plugins[match.group(1)] = match.group(2)
    return str(catalog), versions, plugins


def parse_gradle_properties(root: Path) -> dict[str, str]:
    path = root / "gradle.properties"
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def find_build_files(root: Path) -> list[Path]:
    ignored = {".gradle", "build", ".git", ".idea", ".kotlin"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.name not in BUILD_FILE_NAMES:
            continue
        if any(part in ignored for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return sorted(files)


def module_name(root: Path, build_file: Path) -> str:
    module_dir = build_file.parent
    if module_dir == root:
        return ":"
    return ":" + ":".join(module_dir.relative_to(root).parts)


def extract_plugin_ids(text: str, catalog_plugins: dict[str, str]) -> tuple[list[str], list[str]]:
    plugins: set[str] = set(re.findall(r"id\(\"([A-Za-z0-9_.-]+)\"\)", text))
    plugins.update(re.findall(r"id\s+['\"]([A-Za-z0-9_.-]+)['\"]", text))
    aliases = set(re.findall(r"alias\(libs\.plugins\.([A-Za-z0-9_.-]+)\)", text))
    for alias in aliases:
        plugins.add(catalog_plugins.get(alias.replace(".", "-"), ""))
        plugins.add(catalog_plugins.get(alias, ""))
    plugins.discard("")
    return sorted(plugins), sorted(aliases)


def source_sets(module_dir: Path) -> list[str]:
    src = module_dir / "src"
    if not src.is_dir():
        return []
    return sorted(path.name for path in src.iterdir() if path.is_dir())


def has_any(items: Iterable[str], needles: Iterable[str]) -> bool:
    joined = "\n".join(items)
    return any(needle in joined for needle in needles)


def classify(plugins: list[str], aliases: list[str], text: str) -> list[str]:
    labels: list[str] = []
    all_markers = plugins + aliases + [text]
    if has_any(all_markers, ["org.jetbrains.kotlin.multiplatform", "kotlin.multiplatform", "kotlinMultiplatform"]):
        labels.append("kmp")
    if has_any(all_markers, ["com.android.kotlin.multiplatform.library", "android.kotlin.multiplatform", "androidKmp"]):
        labels.append("android-kmp-library")
    if has_any(all_markers, ["com.android.application", "androidApplication"]):
        labels.append("android-application")
    if has_any(all_markers, ["com.android.library", "androidLibrary"]):
        labels.append("android-library")
    if has_any(all_markers, ["org.jetbrains.compose", "composeMultiplatform"]):
        labels.append("compose-multiplatform")
    if "native.cocoapods" in text or "cocoapods {" in text:
        labels.append("cocoapods")
    if "swiftPMDependencies" in text:
        labels.append("swiftpm")
    if has_any(all_markers, ["co.touchlab.kmmbridge", "kmmbridge"]):
        labels.append("kmmbridge")
    if has_any(all_markers, ["maven-publish", "com.vanniktech.maven.publish"]):
        labels.append("maven-publish")
    if has_any(all_markers, ["com.google.devtools.ksp", "ksp"]):
        labels.append("ksp")
    if has_any(all_markers, ["org.jetbrains.kotlin.kapt", "kapt"]):
        labels.append("kapt")
    return labels


def kt_imports_under(path: Path, max_files: int = 250) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    count = 0
    if not path.is_dir():
        return found
    for file_path in path.rglob("*.kt"):
        count += 1
        if count > max_files:
            break
        for line in read_text(file_path).splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                found.append((file_path, stripped))
    return found


def kt_files_under(path: Path, max_files: int = 250) -> list[Path]:
    if not path.is_dir():
        return []
    files: list[Path] = []
    for file_path in path.rglob("*.kt"):
        files.append(file_path)
        if len(files) >= max_files:
            break
    return files


def has_pattern_under(path: Path, pattern: str, max_files: int = 250) -> Path | None:
    regex = re.compile(pattern, re.M)
    for file_path in kt_files_under(path, max_files=max_files):
        if regex.search(read_text(file_path)):
            return file_path
    return None


def has_text_under(path: Path, pattern: str, max_files: int = 250) -> Path | None:
    return has_pattern_under(path, pattern, max_files=max_files)


def block_contains(text: str, block_name: str, pattern: str) -> bool:
    match = re.search(rf"{re.escape(block_name)}\s*\{{(?P<body>.*?)\n\s*\}}", text, re.S)
    return bool(match and re.search(pattern, match.group("body")))


def diagnose_module(root: Path, build_file: Path, catalog_plugins: dict[str, str]) -> ModuleReport:
    text = read_text(build_file)
    module_dir = build_file.parent
    plugins, aliases = extract_plugin_ids(text, catalog_plugins)
    sets = source_sets(module_dir)
    labels = classify(plugins, aliases, text)
    diagnostics: list[Diagnostic] = []
    build_rel = rel(root, build_file)

    def add(severity: str, code: str, message: str) -> None:
        diagnostics.append(Diagnostic(severity, code, message, build_rel))

    if "kmp" in labels and "android-application" in labels:
        add("error", "kmp_android_application_mixed", "KMP and Android application plugin are mixed in one module; split Android app shell for AGP 9+.")
    if "kmp" in labels and "android-library" in labels and "android-kmp-library" not in labels:
        add("warning", "legacy_android_library_plugin", "KMP module uses com.android.library; plan Android-KMP library plugin migration for AGP 9+.")
    if "android-kmp-library" in labels and re.search(r"(?m)^android\s*\{", text):
        add("error", "top_level_android_block", "Android-KMP library modules should configure Android inside kotlin { android { ... } }, not a top-level android block.")
    if "android-kmp-library" in labels and "src/main" in sets:
        add("warning", "legacy_android_source_layout", "KMP Android library has src/main; Android-KMP plugin expects KMP source-set layout such as src/androidMain.")
    if "android-kmp-library" in labels and (module_dir / "src" / "androidMain" / "res").is_dir() and "androidResources" not in text:
        add("warning", "android_resources_not_enabled", "src/androidMain/res exists but androidResources { enable = true } was not detected.")
    if "android-kmp-library" in labels:
        java_files = list((module_dir / "src").rglob("*.java")) if (module_dir / "src").is_dir() else []
        if java_files and "withJava" not in text:
            add("warning", "java_not_enabled", "Java files exist in a KMP Android library but withJava() was not detected.")
    if "androidUnitTest" in sets or "androidInstrumentedTest" in sets:
        add("info", "old_android_test_source_sets", "Android test source-set names may need host/device test migration for Android-KMP.")
    if "dependsOn(" in text and "applyDefaultHierarchyTemplate" not in text:
        add("warning", "manual_depends_on", "Manual source-set dependsOn edges can disable the default hierarchy template; verify this is intentional.")
    if "commonMain.dependencies" in text:
        common_block = re.search(r"commonMain\.dependencies\s*\{(?P<body>.*?)\n\s*\}", text, re.S)
        if common_block and re.search(r"androidx\.|com\.android\.", common_block.group("body")):
            add("warning", "common_android_dependency", "commonMain appears to contain Android/AndroidX dependencies; verify multiplatform target support.")
    if "debugImplementation" in text and "android-kmp-library" in labels:
        add("warning", "debug_implementation_in_android_kmp", "Android-KMP library plugin is single-variant; verify debugImplementation usage or use documented runtime classpath tooling pattern.")
    if "cocoapods" in labels and "swiftpm" in labels:
        add("info", "dual_cocoapods_swiftpm", "Both CocoaPods and SwiftPM are present; this is valid during a phased migration but should be temporary.")
    elif "cocoapods" in labels:
        add("info", "cocoapods_present", "CocoaPods integration present; consider SwiftPM migration only when requested and after inventory.")
    if "cocoapods" in labels and re.search(r"cocoapods\s*\{(?P<body>.*?)framework\s*\{", text, re.S):
        add("warning", "cocoapods_framework_configuration", "Framework configuration inside cocoapods { framework { ... } } should be migrated to binaries.framework when moving to current KMP layout.")
    if "kmp" in labels and "maven-publish" in text and "abiValidation" not in text:
        add("info", "published_library_without_abi_validation", "Published KMP library does not declare abiValidation; consider checkKotlinAbi/updateKotlinAbi release gates.")
    api_dependency_count = len(re.findall(r"\bapi\s*\(", text))
    if "kmp" in labels and api_dependency_count >= 8:
        add("info", "broad_api_exposure", f"Detected {api_dependency_count} api(...) dependencies; verify each dependency is part of the intended public ABI.")
    if ("commonTest" in sets or "commonTest.dependencies" in text) and not re.search(r"kotlin\s*\(\s*[\"']test[\"']\s*\)|kotlin-test|kotlin\.test", text):
        add("info", "common_test_without_kotlin_test", "commonTest exists but kotlin('test')/kotlin.test was not detected in this module; verify a convention plugin adds it.")
    if "swiftpm" in labels and not re.search(r"(?m)^\s*group\s*=", text):
        add("warning", "swiftpm_missing_module_group", "swiftPMDependencies requires modules to define group for generated package metadata.")
    if "XCFramework" in text and "bundleId" not in text:
        add("info", "xcframework_bundle_id_not_detected", "XCFramework export detected without binaryOption('bundleId', ...); verify bundle identifiers before Swift package export.")
    if "kmp" in labels and re.search(r"\bios(?:Arm64|SimulatorArm64|X64)\s*\(", text) and "isStatic" not in text and "framework" in text:
        add("info", "ios_framework_linkage_not_explicit", "iOS framework export detected without explicit isStatic; verify dynamic/static linkage is intentional for the app integration.")
    if "kmp" in labels and "swiftPMDependencies" in text and "Package.swift" not in text:
        add("info", "swiftpm_manifest_validation_needed", "SwiftPM export/import detected; validate generated Package.swift with swift package tools during release checks.")
    if "kmmbridge" in labels:
        add("info", "kmmbridge_present", "KMMBridge detected; verify artifact hosting, versioning, and iOS consumer workflow in release checks.")
        if "spm(" not in text and "cocoapods(" not in text:
            add("info", "kmmbridge_distribution_mode_not_detected", "KMMBridge plugin detected without obvious spm() or cocoapods() distribution mode.")
    if re.search(r"cinterops\.(creating|maybeCreate)|cinterops\s*\{", text):
        if "definitionFile" not in text and "src/nativeInterop/cinterop" not in text:
            add("warning", "cinterop_definition_not_detected", "cinterop configuration detected without definitionFile or conventional src/nativeInterop/cinterop path.")
        if not re.search(r"compilerOpts|includeDirs|headers?\(|linkerOpts", text):
            add("info", "cinterop_options_not_detected", "cinterop detected without compiler/include/header/linker options; verify native headers and link step explicitly.")
    if re.search(r"\bexport\s*\(", text):
        add("info", "native_binary_export_present", "Native binary export detected; verify exported dependencies are intentional public Swift/native API.")
    if re.search(r"transitiveExport\s*=\s*true", text):
        add("warning", "native_transitive_export_enabled", "transitiveExport=true can increase binary size and compile time; keep it only with an explicit API reason.")
    if "compose-multiplatform" in labels and not re.search(r"metricsDestination|reportsDestination|stabilityConfigurationFile|composeCompiler\s*\{", text):
        add("info", "compose_performance_reports_not_detected", "Compose module does not expose compiler metrics/reports in this build file; add a measured performance path before optimizing.")
    if "compose-multiplatform" in labels and ("commonTest" in sets or "jvmTest" in sets or "androidInstrumentedTest" in sets) and not re.search(r"ui-test|compose\.uiTest|runComposeUiTest", text):
        add("info", "compose_ui_test_dependency_not_detected", "Compose test source sets exist but Compose Multiplatform UI test dependency/API was not detected in this module.")
    common_imports = kt_imports_under(module_dir / "src" / "commonMain")
    for import_path, import_line in common_imports[:250]:
        if re.match(r"import (android|androidx|platform|java\.io|java\.nio|java\.util\.concurrent)\.", import_line):
            diagnostics.append(Diagnostic("warning", "platform_import_in_common", f"{import_line} in commonMain; verify it is portable.", rel(root, import_path)))
            break
    common_expect = has_pattern_under(module_dir / "src" / "commonMain", r"\bexpect\s+class\b")
    if common_expect:
        diagnostics.append(Diagnostic("info", "expect_class_in_common", "expect class found in commonMain; prefer interface injection or platform entry-point wiring when it keeps the API simpler.", rel(root, common_expect)))
    common_secret = has_text_under(module_dir / "src" / "commonMain", r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|bearer|secret).{0,100}[\"']")
    if common_secret:
        diagnostics.append(Diagnostic("warning", "possible_secret_literal_in_common", "Token/secret-like literal found in commonMain; keep secrets in platform-backed secure storage and inject redacted abstractions.", rel(root, common_secret)))
    common_secure_storage = has_text_under(module_dir / "src" / "commonMain", r"EncryptedSharedPreferences|KeychainSettings|NSUserDefaults|SharedPreferences")
    if common_secure_storage:
        diagnostics.append(Diagnostic("warning", "platform_storage_in_common", "Platform storage implementation appears in commonMain; keep secure storage behind platform source-set implementations.", rel(root, common_secure_storage)))
    common_println = has_text_under(module_dir / "src" / "commonMain", r"\bprintln\s*\(")
    if common_println:
        diagnostics.append(Diagnostic("info", "common_println_logging", "println logging found in commonMain; use the project's redaction-aware logging facade for production paths.", rel(root, common_println)))
    common_refresh_loop = has_text_under(module_dir / "src" / "commonMain", r"refreshTokens\s*\{")
    if common_refresh_loop and not has_text_under(module_dir / "src" / "commonMain", r"markAsRefreshTokenRequest|unauthenticated|skipAuth|NoAuth", max_files=250):
        diagnostics.append(Diagnostic("info", "token_refresh_loop_guard_not_detected", "Ktor bearer refreshTokens block detected without an obvious unauthenticated refresh-loop guard.", rel(root, common_refresh_loop)))
    for import_path, import_line in kt_imports_under(module_dir / "src" / "commonTest"):
        if re.match(r"import (org\.junit|androidx\.test|org\.robolectric)\.", import_line):
            diagnostics.append(Diagnostic("warning", "platform_test_import_in_common_test", f"{import_line} in commonTest; keep commonTest on kotlin.test and move platform-specific tests to platform source sets.", rel(root, import_path)))
            break

    return ModuleReport(
        name=module_name(root, build_file),
        path=rel(root, module_dir),
        build_file=build_rel,
        plugins=plugins,
        aliases=aliases,
        source_sets=sets,
        classification=labels,
        diagnostics=diagnostics,
    )


def diagnose_project_governance(root: Path, build_files: list[Path], modules: list[ModuleReport], gradle_properties: dict[str, str]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    settings_text = "\n".join(read_text(root / name) for name in SETTINGS_FILE_NAMES if (root / name).is_file())
    root_build_text = "\n".join(read_text(root / name) for name in BUILD_FILE_NAMES if (root / name).is_file())

    if settings_text:
        if "pluginManagement" not in settings_text:
            diagnostics.append(Diagnostic("info", "missing_plugin_management", "settings.gradle(.kts) does not declare pluginManagement; verify plugin resolution is centralized.", None))
        if "dependencyResolutionManagement" not in settings_text:
            diagnostics.append(Diagnostic("info", "missing_dependency_resolution_management", "settings.gradle(.kts) does not declare dependencyResolutionManagement; verify repositories are centralized.", None))
        elif "RepositoriesMode.FAIL_ON_PROJECT_REPOS" not in settings_text:
            diagnostics.append(Diagnostic("info", "project_repositories_not_blocked", "dependencyResolutionManagement does not use FAIL_ON_PROJECT_REPOS; module-local repositories may drift.", None))

    has_build_logic = (root / "build-logic").is_dir() or (root / "buildSrc").is_dir() or "includeBuild(\"build-logic\")" in settings_text
    non_root_builds = [path for path in build_files if path.parent != root]
    if len(non_root_builds) >= 4 and not has_build_logic:
        diagnostics.append(Diagnostic("info", "convention_build_logic_not_detected", "Multiple Gradle modules detected but no build-logic/buildSrc convention layer was found.", None))

    if "abiValidation" in root_build_text:
        diagnostics.append(Diagnostic("info", "abi_validation_configured", "Root build declares abiValidation; keep checkKotlinAbi in release verification for published libraries.", rel(root, root / "build.gradle.kts") if (root / "build.gradle.kts").is_file() else rel(root, root / "build.gradle")))

    for build_file in build_files:
        if build_file.parent == root:
            continue
        if re.search(r"(?m)^\s*repositories\s*\{", read_text(build_file)):
            diagnostics.append(Diagnostic("warning", "module_local_repositories", "Module-local repositories block detected; prefer centralized dependencyResolutionManagement.", rel(root, build_file)))
            break

    has_kmp = any("kmp" in module.classification for module in modules)
    has_native = any(
        re.search(r"\bios(?:Arm64|SimulatorArm64|X64)\s*\(|\bmacos(?:Arm64|X64)\s*\(|\blinuxX64\s*\(", read_text(root / module.build_file))
        for module in modules
        if (root / module.build_file).is_file()
    )
    has_compose = any("compose-multiplatform" in module.classification for module in modules)
    if has_kmp and not gradle_properties:
        diagnostics.append(Diagnostic("info", "missing_gradle_properties", "No gradle.properties found; verify Gradle/Kotlin/Native performance settings are not only local machine state.", None))
    if has_kmp and gradle_properties.get("org.gradle.caching") != "true":
        diagnostics.append(Diagnostic("info", "gradle_build_cache_not_enabled", "org.gradle.caching=true was not detected; verify build cache policy for CI and local KMP builds.", "gradle.properties" if gradle_properties else None))
    if has_kmp and gradle_properties.get("org.gradle.configuration-cache") != "true":
        diagnostics.append(Diagnostic("info", "gradle_configuration_cache_not_enabled", "org.gradle.configuration-cache=true was not detected; verify whether the project can use configuration cache.", "gradle.properties" if gradle_properties else None))
    if has_native and gradle_properties.get("kotlin.incremental.native") != "true":
        diagnostics.append(Diagnostic("info", "native_incremental_not_enabled", "kotlin.incremental.native=true was not detected for a Native-targeting KMP project.", "gradle.properties" if gradle_properties else None))
    if has_native and any(value == "noop" for key, value in gradle_properties.items() if key.startswith("kotlin.native.binary.gc")):
        diagnostics.append(Diagnostic("warning", "native_gc_disabled", "Kotlin/Native GC appears disabled; this can increase memory consumption and should be limited to controlled diagnostics.", "gradle.properties"))
    if has_compose and not any("baselineprofile" in module.plugins or "androidx.baselineprofile" in module.plugins for module in modules):
        diagnostics.append(Diagnostic("info", "baseline_profile_not_detected", "Compose app/performance surface detected without baseline profile plugin evidence; measure release startup before optimizing.", None))

    return diagnostics


def all_diagnostics(modules: list[ModuleReport], diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    items = list(diagnostics)
    for module in modules:
        items.extend(module.diagnostics)
    return items


def readiness_verdict(score: int, max_score: int) -> str:
    if max_score == 0:
        return "not-applicable"
    ratio = score / max_score
    if ratio >= 0.85:
        return "ready"
    if ratio >= 0.65:
        return "watch"
    return "blocked"


def score_area(name: str, max_score: int, diagnostics: list[Diagnostic], penalties: dict[str, int], evidence: list[str]) -> ReadinessArea:
    blockers: list[str] = []
    penalty = 0
    for item in diagnostics:
        if item.code not in penalties:
            continue
        penalty += penalties[item.code]
        if item.severity in {"error", "warning"}:
            blockers.append(f"{item.code}: {item.message}")
    score = max(0, max_score - penalty)
    return ReadinessArea(name, score, max_score, readiness_verdict(score, max_score), evidence, blockers[:8])


def score_readiness(
    settings: list[str],
    catalog_path: str | None,
    gradle_properties: dict[str, str],
    modules: list[ModuleReport],
    diagnostics: list[Diagnostic],
) -> list[ReadinessArea]:
    items = all_diagnostics(modules, diagnostics)
    classifications = {label for module in modules for label in module.classification}
    source_sets = {source_set for module in modules for source_set in module.source_sets}
    evidence_common = [
        f"modules={len(modules)}",
        f"kmp_modules={sum(1 for module in modules if 'kmp' in module.classification)}",
    ]
    if settings:
        evidence_common.append("settings=present")
    if catalog_path:
        evidence_common.append("version_catalog=present")
    if gradle_properties:
        evidence_common.append("gradle_properties=present")

    structure = score_area(
        "project-structure",
        20,
        items,
        {
            "missing_settings": 8,
            "missing_version_catalog": 3,
            "no_build_files": 8,
            "kmp_android_application_mixed": 12,
            "legacy_android_library_plugin": 4,
            "top_level_android_block": 10,
            "legacy_android_source_layout": 4,
            "manual_depends_on": 3,
        },
        evidence_common,
    )
    governance = score_area(
        "build-governance",
        20,
        items,
        {
            "missing_plugin_management": 3,
            "missing_dependency_resolution_management": 4,
            "project_repositories_not_blocked": 2,
            "convention_build_logic_not_detected": 3,
            "module_local_repositories": 5,
            "broad_api_exposure": 3,
            "common_android_dependency": 4,
        },
        evidence_common,
    )
    testing = score_area(
        "testing-quality",
        15,
        items,
        {
            "common_test_without_kotlin_test": 3,
            "platform_test_import_in_common_test": 5,
            "compose_ui_test_dependency_not_detected": 2,
            "old_android_test_source_sets": 1,
        },
        [f"test_source_sets={','.join(sorted(s for s in source_sets if s.endswith('Test')))}"],
    )
    interop = score_area(
        "ios-native-interop",
        15,
        items,
        {
            "swiftpm_missing_module_group": 5,
            "xcframework_bundle_id_not_detected": 2,
            "ios_framework_linkage_not_explicit": 2,
            "cinterop_definition_not_detected": 5,
            "cinterop_options_not_detected": 2,
            "native_transitive_export_enabled": 4,
            "platform_import_in_common": 4,
            "expect_class_in_common": 1,
        },
        [f"classifications={','.join(sorted(classifications))}"],
    )
    security = score_area(
        "security-privacy",
        15,
        items,
        {
            "possible_secret_literal_in_common": 8,
            "platform_storage_in_common": 6,
            "common_println_logging": 1,
            "token_refresh_loop_guard_not_detected": 2,
            "platform_import_in_common": 3,
        },
        ["commonMain_secret_scan=static"],
    )
    performance = score_area(
        "performance-observability",
        15,
        items,
        {
            "gradle_build_cache_not_enabled": 2,
            "gradle_configuration_cache_not_enabled": 2,
            "native_incremental_not_enabled": 2,
            "native_gc_disabled": 8,
            "baseline_profile_not_detected": 2,
            "compose_performance_reports_not_detected": 2,
            "native_transitive_export_enabled": 2,
        },
        ["performance_scan=gradle_and_static_source"],
    )
    publishing = score_area(
        "publishing-release",
        15,
        items,
        {
            "published_library_without_abi_validation": 4,
            "swiftpm_manifest_validation_needed": 2,
            "kmmbridge_distribution_mode_not_detected": 2,
            "native_binary_export_present": 1,
            "native_transitive_export_enabled": 3,
        },
        [f"publishing_markers={','.join(sorted(label for label in classifications if label in {'maven-publish', 'swiftpm', 'kmmbridge', 'cocoapods'}))}"],
    )
    return [structure, governance, testing, interop, security, performance, publishing]


def inspect_project(root: Path) -> ProjectReport:
    root = root.resolve()
    settings = [rel(root, root / name) for name in SETTINGS_FILE_NAMES if (root / name).is_file()]
    catalog_path, catalog_versions, catalog_plugins = parse_version_catalog(root)
    gradle_properties = parse_gradle_properties(root)
    build_files = find_build_files(root)
    modules = [diagnose_module(root, build_file, catalog_plugins) for build_file in build_files]
    diagnostics: list[Diagnostic] = diagnose_project_governance(root, build_files, modules, gradle_properties)
    if not settings:
        diagnostics.append(Diagnostic("warning", "missing_settings", "No settings.gradle(.kts) found.", None))
    if catalog_path is None:
        diagnostics.append(Diagnostic("info", "missing_version_catalog", "No gradle/libs.versions.toml found.", None))
    if not modules:
        diagnostics.append(Diagnostic("warning", "no_build_files", "No Gradle build files found.", None))
    return ProjectReport(
        root=str(root),
        settings_files=settings,
        gradle_wrapper_version=parse_wrapper_version(root),
        version_catalog=catalog_path,
        gradle_properties=gradle_properties,
        catalog_versions=catalog_versions,
        catalog_plugins=catalog_plugins,
        modules=modules,
        diagnostics=diagnostics,
        readiness=score_readiness(settings, catalog_path, gradle_properties, modules, diagnostics),
    )


def print_text(report: ProjectReport) -> None:
    print(f"KMP inspector report: {report.root}")
    print(f"Gradle wrapper: {report.gradle_wrapper_version or 'unknown'}")
    print(f"Version catalog: {report.version_catalog or 'not found'}")
    if report.catalog_versions:
        interesting = [
            key for key in report.catalog_versions
            if key.lower() in {"kotlin", "agp", "androidgradleplugin", "compose", "composemultiplatform", "ksp"}
        ]
        if interesting:
            print("Key versions:")
            for key in sorted(interesting):
                print(f"  {key}: {report.catalog_versions[key]}")
    if report.diagnostics:
        print("Project diagnostics:")
        for item in report.diagnostics:
            print(f"  [{item.severity}] {item.code}: {item.message}")
    if report.readiness:
        print("Readiness:")
        for area in report.readiness:
            print(f"  {area.name}: {area.score}/{area.max_score} {area.verdict}")
    for module in report.modules:
        print()
        print(f"{module.name} ({module.path})")
        print(f"  build: {module.build_file}")
        print(f"  classification: {', '.join(module.classification) or 'unclassified'}")
        print(f"  plugins: {', '.join(module.plugins) or 'none detected'}")
        print(f"  source sets: {', '.join(module.source_sets) or 'none detected'}")
        for item in module.diagnostics:
            location = f" ({item.file})" if item.file else ""
            print(f"  [{item.severity}] {item.code}: {item.message}{location}")


def main() -> int:
    args = parse_args()
    report = inspect_project(Path(args.root))
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print_text(report)
    if args.fail_on == "none":
        return 0
    severity_rank = {"info": 0, "warning": 1, "error": 2}
    threshold = severity_rank[args.fail_on]
    should_fail = any(severity_rank[diagnostic.severity] >= threshold for diagnostic in all_diagnostics(report.modules, report.diagnostics))
    return 2 if should_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
