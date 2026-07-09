#!/usr/bin/env python3
"""Run the repo-owned Unreal Linux lane inside Docker."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
import re
import shlex
import shutil
import tempfile
from pathlib import Path
import subprocess
import zipfile
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
from extensions.cesium.tools.engine_root_discovery import (
    discover_unreal_linux_archives,
    discover_unreal_linux_roots,
    public_engine_search_roots,
)
from extensions.cesium.tools import linux_docker_runner as docker_runner


DEFAULT_IMAGE = "cesium-linux-proof:ubuntu24.04"
DEFAULT_PLATFORM = "linux/amd64"
DEFAULT_PROFILE = ROOT / "tools" / "unreal_linux_profiles" / "ubuntu_24_04_ue58.env"
DEFAULT_STAGE_ROOT = Path(r"C:\tmp") / "cesium_unreal_linux"
DEFAULT_DOCKER_LOG_DIR = ROOT / "artifacts" / "reports" / "unreal_linux_docker"
DEFAULT_PRESERVE_ROOT = ROOT / "artifacts" / "preserved"
DEFAULT_CONTAINER_NAME_PREFIX = "cesium-unreal-linux-proof"
LANE_SCRIPT = "extensions/cesium/tools/unreal_linux_lane.py"
ARCHIVE_VERSION_PATTERN = re.compile(r"Linux_Unreal_Engine_(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
PLATFORM_SUPPORT_SOURCE = "/linux-platform-support"
PACKET_STOAT_PLUGIN_ROOT = (
    ROOT.parent
    / "Packet-Stoat"
    / "build"
    / "unreal_vendor_plugins"
    / "cesium"
    / "linux_docker_5_8"
    / "CesiumForUnreal"
)
PLATFORM_SUPPORT_SEARCH_ROOTS = (
    Path(r"C:\Users\Public\Unreal") / "Engine" / "Platforms" / "Linux",
    Path(r"C:\Program Files\Epic Games") / "Engine" / "Platforms" / "Linux",
)
DEFAULT_PLUGIN_ROOT = ROOT / "external" / "cesium" / "cesium-unreal"


def _now() -> str:
    return docker_runner.now()


def parse_env_file(path: Path) -> dict[str, str]:
    return docker_runner.parse_env_file(path)


def _resolve_path(raw: str, *, base: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path.resolve()


def _sanitize_label(value: str) -> str:
    return docker_runner.sanitize_label(value)


def resolved_container_name(engine_version: str | None, container_name: str | None = None) -> str:
    return docker_runner.resolved_container_name(
        DEFAULT_CONTAINER_NAME_PREFIX,
        identifier=engine_version,
        explicit=container_name,
    )


def _docker_log_path(command_name: str, engine_version: str | None) -> Path:
    return docker_runner.docker_log_path(
        DEFAULT_DOCKER_LOG_DIR,
        command_name=f"cesium_unreal_linux_{command_name}",
        identifier=engine_version,
    )


def cleanup_container(container_name: str) -> None:
    docker_runner.cleanup_container(container_name)


def _preserve_log(log_path: Path, *, preserve_root: Path, preserve_label: str, command_name: str) -> Path | None:
    return docker_runner.preserve_artifact(log_path, preserve_root=preserve_root, preserve_label=preserve_label, prefix=command_name)


def _run_command_with_logging(
    command: list[str],
    *,
    container_name: str,
    log_out: Path,
    log_mode: str,
    timeout_seconds: int,
    log_tail_lines: int,
) -> tuple[int, list[str], list[str], str]:
    return docker_runner.run_command_with_logging(
        command,
        log_out=log_out,
        log_mode=log_mode,
        timeout_seconds=timeout_seconds,
        log_tail_lines=log_tail_lines,
        container_name=container_name,
    )


def _tail(text: str, lines: int) -> list[str]:
    return docker_runner.tail_lines(text, lines)


def _container_lane_command(engine_version: str | None) -> list[str]:
    command = ["python3", "-m", "extensions.cesium.tools.unreal_linux_lane", "report"]
    if engine_version is not None:
        command.extend(["--engine-version", engine_version])
    return command


def _extract_archive_version(archive: Path) -> str | None:
    match = ARCHIVE_VERSION_PATTERN.search(archive.name)
    if match is not None:
        return match.group(1)
    return None


def _docker_base_args(image: str) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{ROOT}:/workspace",
        "-w",
        "/workspace",
        image,
    ]


def _docker_mount_args(image: str, ue_root: Path | None) -> list[str]:
    args = _docker_base_args(image)
    if ue_root is not None:
        args[3:3] = ["-v", f"{ue_root}:/ue"]
    return args


def _docker_archive_args(image: str, archive: Path) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{ROOT}:/workspace",
        "-v",
        f"{archive}:/ue.zip",
        "-w",
        "/workspace",
        image,
    ]


def _docker_archive_and_platform_args(
    image: str,
    archive: Path,
    platform_support_root: Path | None,
    plugin_root: Path | None = None,
) -> list[str]:
    args = _docker_archive_args(image, archive)
    if platform_support_root is not None:
        args[3:3] = ["-v", f"{platform_support_root}:/linux-platform-support:ro"]
    if plugin_root is not None:
        args[3:3] = ["-v", f"{plugin_root}:/plugin-source:ro"]
    return args


def _rewrite_plugin_command(command: list[str]) -> tuple[list[str], bool]:
    rewritten = list(command)
    for index, value in enumerate(rewritten):
        if value == "-Plugin=/workspace/external/cesium/cesium-unreal/CesiumForUnreal.uplugin":
            rewritten[index] = "-Plugin=/tmp/cesium-unreal/CesiumForUnreal.uplugin"
            return rewritten, True
    return rewritten, False


def _plugin_copy_script(source_container_path: str) -> list[str]:
    return [
        "rm -rf /tmp/cesium-unreal",
        "python3 - <<'PY'",
        "import shutil",
        "from pathlib import Path",
        "",
        f"source = Path({source_container_path!r})",
        "target = Path('/tmp/cesium-unreal')",
        "shutil.copytree(source, target, ignore=shutil.ignore_patterns('.git'))",
        "PY",
    ]


def _rewrite_staged_engine_command(command: list[str]) -> list[str]:
    rewritten: list[str] = []
    for value in command:
        rewritten.append(value.replace("/tmp/ue", "/ue"))
    return rewritten


def _docker_plugin_args(image: str, plugin_root: Path | None) -> list[str]:
    if plugin_root is None:
        return _docker_base_args(image)
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{plugin_root}:/plugin-source:ro",
        "-v",
        f"{ROOT}:/workspace",
        "-w",
        "/workspace",
        image,
    ]


def _run_docker(
    image: str,
    command: list[str],
    *,
    engine_version: str | None = None,
    container_name: str | None = None,
    docker_log_mode: str = "tee",
    timeout_seconds: int = 3600,
    log_tail_lines: int = 80,
    preserve: bool = False,
    preserve_label: str = "unreal-linux-docker",
    preserve_root: Path = DEFAULT_PRESERVE_ROOT,
) -> int:
    docker_args = _docker_base_args(image)
    resolved_container = resolved_container_name(engine_version, container_name)
    docker_args[3:3] = ["--name", resolved_container]
    log_path = _docker_log_path("report", engine_version)
    returncode, _, _, _ = _run_command_with_logging(
        [*docker_args, *command],
        container_name=resolved_container,
        log_out=log_path,
        log_mode=docker_log_mode,
        timeout_seconds=timeout_seconds,
        log_tail_lines=log_tail_lines,
    )
    if preserve:
        _preserve_log(log_path, preserve_root=preserve_root, preserve_label=preserve_label, command_name="report")
    return returncode


def _run_docker_with_ue_root(
    image: str,
    ue_root: Path,
    command: list[str],
    *,
    plugin_root: Path | None = None,
    engine_version: str | None = None,
    container_name: str | None = None,
    docker_log_mode: str = "tee",
    timeout_seconds: int = 3600,
    log_tail_lines: int = 80,
    preserve: bool = False,
    preserve_label: str = "unreal-linux-docker",
    preserve_root: Path = DEFAULT_PRESERVE_ROOT,
) -> int:
    container_command, plugin_needs_copy = _rewrite_plugin_command(command)
    script_lines = ["set -e"]
    if plugin_needs_copy:
        source_path = "/plugin-source" if plugin_root is not None else "/workspace/external/cesium/cesium-unreal"
        script_lines.extend(_plugin_copy_script(source_path))
    script_lines.append(shlex.join(container_command))
    docker_args = _docker_mount_args(image, ue_root)
    resolved_container = resolved_container_name(engine_version, container_name)
    docker_args[3:3] = ["--name", resolved_container]
    if plugin_root is not None:
        docker_args[3:3] = ["-v", f"{plugin_root}:/plugin-source:ro"]
    log_path = _docker_log_path("report" if command and "report" in command else "build", engine_version)
    returncode, _, _, _ = _run_command_with_logging(
        [*docker_args, "bash", "-lc", "\n".join(script_lines)],
        container_name=resolved_container,
        log_out=log_path,
        log_mode=docker_log_mode,
        timeout_seconds=timeout_seconds,
        log_tail_lines=log_tail_lines,
    )
    if preserve:
        _preserve_log(log_path, preserve_root=preserve_root, preserve_label=preserve_label, command_name=log_path.stem)
    return returncode


def _run_docker_with_archive(
    image: str,
    archive: Path,
    command: list[str],
    *,
    linux_platform_support_root: Path | None = None,
    plugin_root: Path | None = None,
    engine_version: str | None = None,
    container_name: str | None = None,
    docker_log_mode: str = "tee",
    timeout_seconds: int = 3600,
    log_tail_lines: int = 80,
    preserve: bool = False,
    preserve_label: str = "unreal-linux-docker",
    preserve_root: Path = DEFAULT_PRESERVE_ROOT,
) -> int:
    container_command, plugin_needs_copy = _rewrite_plugin_command(command)
    staged_root = _stage_unreal_linux_archive(archive, engine_version=_extract_archive_version(archive))
    if linux_platform_support_root is not None:
        support_target = staged_root / "Engine" / "Config" / "Linux"
        if support_target.exists():
            shutil.rmtree(support_target)
        support_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(linux_platform_support_root, support_target)
    container_command = _rewrite_staged_engine_command(container_command)
    script_lines = ["set -e"]
    if plugin_needs_copy:
        source_path = "/plugin-source" if plugin_root is not None else "/workspace/external/cesium/cesium-unreal"
        script_lines.extend(_plugin_copy_script(source_path))
    script_lines.append(shlex.join(container_command))
    container_script = "\n".join(script_lines)
    docker_args = _docker_mount_args(image, staged_root)
    resolved_container = resolved_container_name(engine_version, container_name)
    docker_args[3:3] = ["--name", resolved_container]
    if plugin_root is not None:
        docker_args[3:3] = ["-v", f"{plugin_root}:/plugin-source:ro"]
    log_path = _docker_log_path("build" if "BuildPlugin" in container_script else "report", engine_version)
    returncode, _, _, _ = _run_command_with_logging(
        [*docker_args, "bash", "-lc", container_script],
        container_name=resolved_container,
        log_out=log_path,
        log_mode=docker_log_mode,
        timeout_seconds=timeout_seconds,
        log_tail_lines=log_tail_lines,
    )
    if preserve:
        _preserve_log(log_path, preserve_root=preserve_root, preserve_label=preserve_label, command_name=log_path.stem)
    return returncode


def _resolve_ue_root(explicit_root: Path | None, *, engine_version: str | None = None) -> Path | None:
    if explicit_root is not None:
        return explicit_root
    candidates = discover_unreal_linux_roots()
    if engine_version is not None:
        preferred = [candidate for candidate in candidates if engine_version in candidate.name]
        if preferred:
            return preferred[0]
    if candidates:
        return candidates[-1]
    return None


def _select_unreal_linux_archive(engine_version: str | None = None) -> Path | None:
    archives = discover_unreal_linux_archives()
    if not archives:
        return None
    if engine_version is not None:
        preferred = [archive for archive in archives if engine_version in archive.name]
        if preferred:
            return preferred[0]
    return archives[-1]


def _stage_unreal_linux_archive(archive: Path, *, engine_version: str | None = None) -> Path:
    version = engine_version or _extract_archive_version(archive) or "unknown"
    stage_root = DEFAULT_STAGE_ROOT / f"ue{version}-linux"
    stage_root.parent.mkdir(parents=True, exist_ok=True)
    if stage_root.exists():
        try:
            shutil.rmtree(stage_root)
        except OSError:
            stage_root = Path(tempfile.mkdtemp(prefix="ue-", dir=str(DEFAULT_STAGE_ROOT.parent)))
    stage_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            extracted_path = stage_root / member.filename
            if member.is_dir():
                extracted_path.mkdir(parents=True, exist_ok=True)
                continue
            extracted_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as source, extracted_path.open("wb") as target:
                shutil.copyfileobj(source, target)
    return stage_root


def _resolve_or_stage_ue_root(explicit_root: Path | None, *, engine_version: str | None = None) -> Path | None:
    resolved = _resolve_ue_root(explicit_root, engine_version=engine_version)
    if resolved is not None:
        return resolved
    archive = _select_unreal_linux_archive(engine_version)
    if archive is None:
        return None
    return _stage_unreal_linux_archive(archive, engine_version=engine_version)


def _resolve_ue_root_with_source(
    explicit_root: Path | None,
    *,
    engine_version: str | None = None,
) -> tuple[Path | None, str, Path | None]:
    if explicit_root is not None:
        return explicit_root, "manual --ue-root", None
    resolved = _resolve_ue_root(None, engine_version=engine_version)
    if resolved is not None:
        return resolved, "existing discovered root", None
    archive = _select_unreal_linux_archive(engine_version)
    if archive is None:
        return None, "no root or archive discovered", None
    return None, "staged zip from C:\\Users\\Public\\Unreal", archive


def _resolve_linux_platform_support_root(explicit_root: Path | None) -> Path | None:
    if explicit_root is not None:
        return explicit_root
    for candidate in PLATFORM_SUPPORT_SEARCH_ROOTS:
        if candidate.is_dir():
            return candidate
    return None


def _discovered_support_context() -> dict[str, list[Path]]:
    return {
        "search_roots": [candidate for candidate in PLATFORM_SUPPORT_SEARCH_ROOTS],
        "discovered_roots": _discover_linux_platform_support_roots(),
        "public_archives": discover_unreal_linux_archives(),
    }


def _plugin_root_has_third_party_include(path: Path) -> bool:
    return (path / "Source" / "ThirdParty" / "include").is_dir()


def _resolve_plugin_root(explicit_root: Path | None = None) -> Path:
    candidates: list[Path] = []
    if explicit_root is not None:
        candidates.append(explicit_root)
    env_override = os.environ.get("CESIUM_UNREAL_PLUGIN_ROOT", "").strip()
    if env_override:
        candidates.append(Path(env_override).expanduser())
    candidates.append(DEFAULT_PLUGIN_ROOT)
    candidates.append(PACKET_STOAT_PLUGIN_ROOT)
    for candidate in candidates:
        if candidate.is_dir() and _plugin_root_has_third_party_include(candidate):
            return candidate.resolve()
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return DEFAULT_PLUGIN_ROOT.resolve()


def _discover_linux_platform_support_roots() -> list[Path]:
    return [candidate for candidate in PLATFORM_SUPPORT_SEARCH_ROOTS if candidate.is_dir()]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    subparsers = parser.add_subparsers(dest="command", required=True)

    report = subparsers.add_parser("report")
    report.add_argument("--image", default="")
    report.add_argument("--engine-version", choices=("5.7", "5.8"))
    report.add_argument("--ue-root", type=Path)
    report.add_argument("--linux-platform-support-root", type=Path)
    report.add_argument("--plugin-root", type=Path)
    report.add_argument("--docker-log-mode", choices=("capture", "tee"), default="tee")
    report.add_argument("--log-tail-lines", type=int, default=80)
    report.add_argument("--timeout-seconds", type=int, default=3600)
    report.add_argument("--container-name")
    report.add_argument("--preserve", action="store_true")
    report.add_argument("--preserve-label", default="unreal-linux-docker")
    report.add_argument("--preserve-root", type=Path, default=DEFAULT_PRESERVE_ROOT)

    build = subparsers.add_parser("build")
    build.add_argument("--image", default="")
    build.add_argument("--engine-version", choices=("5.7", "5.8"))
    build.add_argument("--ue-root", type=Path)
    build.add_argument("--linux-platform-support-root", type=Path)
    build.add_argument("--plugin-root", type=Path)
    build.add_argument("--docker-log-mode", choices=("capture", "tee"), default="tee")
    build.add_argument("--log-tail-lines", type=int, default=80)
    build.add_argument("--timeout-seconds", type=int, default=3600)
    build.add_argument("--container-name")
    build.add_argument("--preserve", action="store_true")
    build.add_argument("--preserve-label", default="unreal-linux-docker")
    build.add_argument("--preserve-root", type=Path, default=DEFAULT_PRESERVE_ROOT)

    build_plan = subparsers.add_parser("build-plan")
    build_plan.add_argument("--image", default="")
    build_plan.add_argument("--engine-version", choices=("5.7", "5.8"))
    build_plan.add_argument("--ue-root", type=Path)
    build_plan.add_argument("--linux-platform-support-root", type=Path)
    build_plan.add_argument("--plugin-root", type=Path)
    build_plan.add_argument("--docker-log-mode", choices=("capture", "tee"), default="tee")
    build_plan.add_argument("--log-tail-lines", type=int, default=80)
    build_plan.add_argument("--timeout-seconds", type=int, default=3600)
    build_plan.add_argument("--container-name")
    build_plan.add_argument("--preserve", action="store_true")
    build_plan.add_argument("--preserve-label", default="unreal-linux-docker")
    build_plan.add_argument("--preserve-root", type=Path, default=DEFAULT_PRESERVE_ROOT)

    return parser.parse_args(argv)


def _print_build_plan(engine_version: str | None, *, image: str = DEFAULT_IMAGE) -> None:
    command = _container_lane_command(engine_version)
    print("Docker Unreal Linux build plan")
    print(f"container: {image}")
    print("mount: <repo-root>:/workspace")
    print("workdir: /workspace")
    print("lane:")
    print("  -", " ".join(command))
    print("public search roots:")
    for root in public_engine_search_roots()["unreal"]:
        print(f"  - {root}")
    print("linux platform support search roots:")
    for root in PLATFORM_SUPPORT_SEARCH_ROOTS:
        print(f"  - {root}")
    archives = discover_unreal_linux_archives()
    if archives:
        print("public Unreal archives:")
        for archive in archives:
            print(f"  - {archive}")
    print(f"staging root: {DEFAULT_STAGE_ROOT}")
    print("source options:")
    print("  - manual --ue-root")
    print("  - existing discovered root")
    print("  - staged zip from C:\\Users\\Public\\Unreal")
    print(f"plugin root default: {DEFAULT_PLUGIN_ROOT}")
    print("follow-up: mount a Linux Unreal Engine root into the container or let the lane stage a public zip, then run the same lane against the real engine toolchain before treating the build as green.")


def _print_build_request(
    engine_version: str | None,
    ue_root: Path,
    *,
    image: str = DEFAULT_IMAGE,
    archive: Path | None = None,
    linux_platform_support_root: Path | None = None,
) -> None:
    command = _container_lane_command(engine_version)
    print("Docker Unreal Linux build request")
    print(f"ue_root: {ue_root}")
    if archive is not None:
        print(f"archive: {archive}")
    print(f"container: {image}")
    print("mount: <repo-root>:/workspace")
    print(f"mount: {ue_root}:/ue")
    print("workdir: /workspace")
    print("lane:")
    print("  -", " ".join(command))
    print("preflight: expect /ue/Engine/Build/BatchFiles/Linux/SetupEnvironment.sh, dotnet, and clang++ to be present before BuildPlugin can succeed.")
    print("public search roots:")
    for root in public_engine_search_roots()["unreal"]:
        print(f"  - {root}")
    print("linux platform support search roots:")
    for root in PLATFORM_SUPPORT_SEARCH_ROOTS:
        print(f"  - {root}")
    archives = discover_unreal_linux_archives()
    if archives:
        print("public Unreal archives:")
        for archive in archives:
            print(f"  - {archive}")
    support_root = linux_platform_support_root or _resolve_linux_platform_support_root(None)
    if support_root is not None:
        print(f"linux platform support root: {support_root}")
    if not _has_linux_platform_support(ue_root) and support_root is None:
        print("platform support: missing Engine/Platforms/Linux/Config/DataDrivenPlatformInfo.ini and SDK.json")


def _has_linux_build_prereqs(ue_root: Path) -> bool:
    required_paths = [
        ue_root / "Engine" / "Build" / "BatchFiles" / "Linux" / "SetupEnvironment.sh",
    ]
    return all(path.is_file() for path in required_paths)


def _linux_platform_support_paths(ue_root: Path) -> list[Path]:
    return [
        ue_root / "Engine" / "Config" / "Linux" / "DataDrivenPlatformInfo.ini",
        ue_root / "Engine" / "Config" / "Linux" / "Linux_SDK.json",
    ]


def _has_linux_platform_support(ue_root: Path) -> bool:
    return all(path.is_file() for path in _linux_platform_support_paths(ue_root))


def _archive_has_linux_platform_support(archive: Path) -> bool:
    with zipfile.ZipFile(archive) as zf:
        entries = {member.filename for member in zf.infolist()}
    return {
        "Engine/Config/Linux/DataDrivenPlatformInfo.ini",
        "Engine/Config/Linux/Linux_SDK.json",
    }.issubset(entries) or {
        "Engine/Platforms/Linux/Config/DataDrivenPlatformInfo.ini",
        "Engine/Platforms/Linux/Config/SDK.json",
    }.issubset(entries)


def _archive_has_linux_platform_support_tree(archive: Path) -> bool:
    with zipfile.ZipFile(archive) as zf:
        entries = {member.filename for member in zf.infolist()}
    return {
        "Engine/Config/Linux/DataDrivenPlatformInfo.ini",
        "Engine/Config/Linux/Linux_SDK.json",
    }.issubset(entries)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    profile_path = args.profile.expanduser().resolve()
    values = dict(os.environ)
    values.update(parse_env_file(profile_path))
    image = args.image or values.get("UE_LINUX_IMAGE") or DEFAULT_IMAGE
    linux_platform_support_root = _resolve_linux_platform_support_root(getattr(args, "linux_platform_support_root", None))
    plugin_root = _resolve_plugin_root(getattr(args, "plugin_root", None))
    if args.command == "report":
        resolved_ue_root, source, archive = _resolve_ue_root_with_source(args.ue_root, engine_version=args.engine_version)
        support_context = _discovered_support_context()
        if resolved_ue_root is not None and not _has_linux_build_prereqs(resolved_ue_root):
            _print_build_request(
                args.engine_version,
                resolved_ue_root,
                image=image,
                archive=archive,
                linux_platform_support_root=linux_platform_support_root,
            )
            print(f"selected source: {source}")
            print("discovered linux platform support roots:")
            for root in support_context["discovered_roots"]:
                print(f"  - {root}")
            if support_context["public_archives"]:
                print("public Unreal archives:")
                for item in support_context["public_archives"]:
                    print(f"  - {item}")
            return 2
        if archive is not None:
            if not _archive_has_linux_platform_support(archive) and linux_platform_support_root is None:
                _print_build_request(
                    args.engine_version,
                    Path(r"C:\Users\Public\Unreal"),
                    image=image,
                    archive=archive,
                    linux_platform_support_root=linux_platform_support_root,
                )
                print(f"selected source: {source}")
                print("blocker: the public Unreal Linux archive does not include Engine/Platforms/Linux platform support files")
                print("discovered linux platform support roots:")
                for root in support_context["discovered_roots"]:
                    print(f"  - {root}")
                if support_context["public_archives"]:
                    print("public Unreal archives:")
                    for item in support_context["public_archives"]:
                        print(f"  - {item}")
                return 2
            print(f"selected source: {source}")
            print("discovered linux platform support roots:")
            for root in support_context["discovered_roots"]:
                print(f"  - {root}")
            if support_context["public_archives"]:
                print("public Unreal archives:")
                for item in support_context["public_archives"]:
                    print(f"  - {item}")
            return _run_docker_with_archive(
                image,
                archive,
                _container_lane_command(args.engine_version),
                linux_platform_support_root=linux_platform_support_root,
                plugin_root=plugin_root,
                engine_version=args.engine_version,
                container_name=args.container_name or values.get("CONTAINER_NAME"),
                docker_log_mode=args.docker_log_mode,
                timeout_seconds=args.timeout_seconds,
                log_tail_lines=args.log_tail_lines,
                preserve=args.preserve,
                preserve_label=args.preserve_label,
                preserve_root=args.preserve_root.expanduser().resolve(),
            )
        command = _container_lane_command(args.engine_version)
        if resolved_ue_root is not None:
            print(f"selected source: {source}")
            print("discovered linux platform support roots:")
            for root in support_context["discovered_roots"]:
                print(f"  - {root}")
            if support_context["public_archives"]:
                print("public Unreal archives:")
                for item in support_context["public_archives"]:
                    print(f"  - {item}")
            return _run_docker_with_ue_root(
                image,
                resolved_ue_root,
                command,
                plugin_root=plugin_root,
                engine_version=args.engine_version,
                container_name=args.container_name or values.get("CONTAINER_NAME"),
                docker_log_mode=args.docker_log_mode,
                timeout_seconds=args.timeout_seconds,
                log_tail_lines=args.log_tail_lines,
                preserve=args.preserve,
                preserve_label=args.preserve_label,
                preserve_root=args.preserve_root.expanduser().resolve(),
            )
        return _run_docker(
            image,
            command,
            engine_version=args.engine_version,
            container_name=args.container_name or values.get("CONTAINER_NAME"),
            docker_log_mode=args.docker_log_mode,
            timeout_seconds=args.timeout_seconds,
            log_tail_lines=args.log_tail_lines,
            preserve=args.preserve,
            preserve_label=args.preserve_label,
            preserve_root=args.preserve_root.expanduser().resolve(),
        )
    if args.command == "build":
        resolved_ue_root, source, archive = _resolve_ue_root_with_source(args.ue_root, engine_version=args.engine_version)
        if resolved_ue_root is None or not _has_linux_build_prereqs(resolved_ue_root):
            if archive is not None:
                if not _archive_has_linux_platform_support_tree(archive) and linux_platform_support_root is None:
                    _print_build_request(args.engine_version, Path(r"C:\Users\Public\Unreal"), image=image, archive=archive)
                    print(f"selected source: {source}")
                    print("blocker: the public Unreal Linux archive does not include Engine/Config/Linux platform-support files")
                    return 2
                print(f"selected source: {source}")
                return _run_docker_with_archive(
                    image,
                    archive,
                    [
                        "/tmp/ue/Engine/Build/BatchFiles/RunUAT.sh",
                        "BuildPlugin",
                        "-Plugin=/workspace/external/cesium/cesium-unreal/CesiumForUnreal.uplugin",
                        f"-Package=/workspace/artifacts/unreal-linux/CesiumForUnreal-{args.engine_version or 'unknown'}",
                        "-CreateSubFolder",
                        "-TargetPlatforms=Linux",
                    ],
                    linux_platform_support_root=linux_platform_support_root,
                    plugin_root=plugin_root,
                    engine_version=args.engine_version,
                    container_name=args.container_name or values.get("CONTAINER_NAME"),
                    docker_log_mode=args.docker_log_mode,
                    timeout_seconds=args.timeout_seconds,
                    log_tail_lines=args.log_tail_lines,
                    preserve=args.preserve,
                    preserve_label=args.preserve_label,
                    preserve_root=args.preserve_root.expanduser().resolve(),
                )
            if resolved_ue_root is None:
                resolved_ue_root = args.ue_root if args.ue_root is not None else Path(r"C:\Users\Public\Unreal")
            _print_build_request(
                args.engine_version,
                resolved_ue_root,
                image=image,
                archive=archive,
                linux_platform_support_root=linux_platform_support_root,
            )
            print(f"selected source: {source}")
            return 2
        print(f"selected source: {source}")
        command = [
            "/ue/Engine/Build/BatchFiles/RunUAT.sh",
            "BuildPlugin",
            f"-Plugin=/workspace/external/cesium/cesium-unreal/CesiumForUnreal.uplugin",
            f"-Package=/workspace/artifacts/unreal-linux/CesiumForUnreal-{args.engine_version or 'unknown'}",
            "-CreateSubFolder",
            "-TargetPlatforms=Linux",
        ]
        return _run_docker_with_ue_root(
            image,
            resolved_ue_root,
            command,
            plugin_root=plugin_root,
            engine_version=args.engine_version,
            container_name=args.container_name or values.get("CONTAINER_NAME"),
            docker_log_mode=args.docker_log_mode,
            timeout_seconds=args.timeout_seconds,
            log_tail_lines=args.log_tail_lines,
            preserve=args.preserve,
            preserve_label=args.preserve_label,
            preserve_root=args.preserve_root.expanduser().resolve(),
        )
    if args.command == "build-plan":
        resolved_ue_root, source, archive = _resolve_ue_root_with_source(args.ue_root, engine_version=args.engine_version)
        discovered_support = _discover_linux_platform_support_roots()
        if resolved_ue_root is not None:
            _print_build_request(
                args.engine_version,
                resolved_ue_root,
                image=image,
                archive=archive,
                linux_platform_support_root=linux_platform_support_root,
            )
            print(f"selected source: {source}")
        else:
            _print_build_plan(args.engine_version, image=image)
            if linux_platform_support_root is not None:
                print(f"linux platform support root: {linux_platform_support_root}")
        if discovered_support:
            print("discovered linux platform support roots:")
            for root in discovered_support:
                print(f"  - {root}")
        else:
            print("discovered linux platform support roots: none")
        return 0
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
