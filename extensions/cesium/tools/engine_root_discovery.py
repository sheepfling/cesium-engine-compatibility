#!/usr/bin/env python3
"""Shared engine-root discovery helpers for public alternate install paths."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path


def public_share_root() -> Path:
    system = platform.system().lower()
    if system == "windows":
        return Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    if system == "darwin":
        return Path("/Users/Shared")
    return Path(os.environ.get("PUBLIC", str(Path.home() / "Public")))


def program_files_root(*parts: str) -> Path:
    base = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    return base.joinpath(*parts)


def unreal_public_root() -> Path:
    return public_share_root() / "Unreal"


def godot_public_root() -> Path:
    return public_share_root() / "Godot"


def unity_public_root() -> Path:
    return public_share_root() / "Unity"


PUBLIC_UNREAL_MAC_ROOT = Path("/Users/Shared/Epic Games")
PUBLIC_UNREAL_ROOT = unreal_public_root()
PUBLIC_GODOT_ROOT = godot_public_root()
PUBLIC_UNITY_ROOT = unity_public_root()
PROGRAM_FILES_EPIC_GAMES = program_files_root("Epic Games")
PROGRAM_FILES_UNITY = program_files_root("Unity", "Hub", "Editor")
MACOS_UNITY_ROOTS = [
    Path("/Applications/Unity/Hub/Editor"),
    Path.home() / "Applications" / "Unity" / "Hub" / "Editor",
]
GODOT_WINDOWS_VERSION_PATTERN = re.compile(r"^Godot_v(?P<version>\d+\.\d+(?:\.\d+)?(?:-[A-Za-z0-9]+)?)_win64\.exe$")
GODOT_LINUX_VERSION_PATTERN = re.compile(r"^Godot_v(?P<version>\d+\.\d+(?:\.\d+)?(?:-[A-Za-z0-9]+)?)_linux\.x86_64$")
GODOT_MACOS_VERSION_PATTERN = re.compile(r"^Godot_v(?P<version>\d+\.\d+(?:\.\d+)?(?:-[A-Za-z0-9]+)?)_macos(?:[._-][A-Za-z0-9]+)*$")


def _is_unreal_linux_root(path: Path) -> bool:
    return (path / "Engine" / "Build" / "BatchFiles" / "Linux" / "SetupEnvironment.sh").is_file()


def _configured_godot_roots() -> list[Path]:
    value = os.environ.get("FASTDIS_GODOT_ROOTS")
    if not value:
        return []
    roots: list[Path] = []
    for raw_part in value.split(os.pathsep):
        part = raw_part.strip().strip('"')
        if not part:
            continue
        roots.append(Path(part).expanduser())
    return roots


def _macos_godot_roots() -> list[Path]:
    if platform.system().lower() != "darwin":
        return []
    return [
        Path("/Applications"),
        Path.home() / "Applications",
        Path.home() / "Dev" / "Godot",
        Path("/usr/local/bin"),
        Path("/opt/homebrew/bin"),
    ]


def _configured_roots(env_var: str) -> list[Path]:
    value = os.environ.get(env_var)
    if not value:
        return []
    roots: list[Path] = []
    for raw_part in value.split(os.pathsep):
        part = raw_part.strip().strip('"')
        if not part:
            continue
        roots.append(Path(part).expanduser())
    return roots


def _unique_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        marker = str(path)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(path)
    return unique


def discover_unreal_linux_roots() -> list[Path]:
    candidates: list[Path] = []
    for unreal_root in [unreal_public_root(), *_configured_roots("FASTDIS_UNREAL_ROOTS")]:
        public_linux_root = unreal_root / "engines" / "linux"
        if public_linux_root.is_dir():
            for child in sorted(public_linux_root.iterdir()):
                if child.is_dir() and _is_unreal_linux_root(child):
                    candidates.append(child)
    program_files = program_files_root("Epic Games")
    if platform.system().lower() == "windows" and program_files.is_dir():
        for child in sorted(program_files.iterdir()):
            if child.is_dir() and child.name.startswith("UE_") and _is_unreal_linux_root(child):
                candidates.append(child)
    return candidates


def discover_unreal_linux_archives() -> list[Path]:
    archives: list[Path] = []
    for unreal_root in [unreal_public_root(), *_configured_roots("FASTDIS_UNREAL_ROOTS")]:
        public_linux_root = unreal_root / "engines" / "linux"
        if not public_linux_root.is_dir():
            continue
        archives.extend(
            path for path in sorted(public_linux_root.iterdir()) if path.is_file() and path.suffix.lower() == ".zip"
        )
    return archives


def discover_unreal_windows_editors() -> list[dict[str, object]]:
    if platform.system().lower() != "windows":
        return []
    candidates: list[dict[str, object]] = []
    roots = _unique_paths(
        [
            *public_engine_search_roots()["unreal"],
            PROGRAM_FILES_EPIC_GAMES,
        ]
    )
    # Prefer the render-capable editor binary for visual-proof lanes.
    exe_names = ("UnrealEditor.exe", "UnrealEditor-Cmd.exe")

    def _append(root: Path, executable: Path) -> None:
        candidates.append(
            {
                "root": root,
                "executable": executable,
                "command": str(executable),
            }
        )

    for base in roots:
        if not base.is_dir():
            continue
        direct_engine = base / "Engine" / "Binaries" / "Win64"
        for exe_name in exe_names:
            exe = direct_engine / exe_name
            if exe.is_file():
                _append(base, exe)
                break
        for child in sorted(base.iterdir()):
            if not child.is_dir() or not child.name.startswith("UE_"):
                continue
            engine_dir = child / "Engine" / "Binaries" / "Win64"
            for exe_name in exe_names:
                exe = engine_dir / exe_name
                if exe.is_file():
                    _append(child, exe)
                    break
    return candidates


def discover_godot_public_roots() -> dict[str, list[Path]]:
    roots: dict[str, list[Path]] = {"linux": [], "windows": []}
    for platform_name in roots:
        discovered: list[Path] = []
        for godot_root in [PUBLIC_GODOT_ROOT, *_configured_godot_roots()]:
            platform_root = godot_root / "engines" / platform_name
            if platform_root.is_dir():
                discovered.extend(path for path in sorted(platform_root.iterdir()) if path.exists())
        roots[platform_name] = discovered
    return roots


def discover_godot_windows_versions() -> list[dict[str, object]]:
    return _discover_godot_platform_versions("windows")


def discover_godot_linux_versions() -> list[dict[str, object]]:
    return _discover_godot_platform_versions("linux")


def discover_godot_macos_versions() -> list[dict[str, object]]:
    roots = _macos_godot_roots()
    roots.extend(_configured_godot_roots())
    rows: list[dict[str, object]] = []

    def _bundle_executable(bundle: Path) -> Path:
        executable_dir = bundle / "Contents" / "MacOS"
        if executable_dir.is_dir():
            files = [path for path in sorted(executable_dir.iterdir()) if path.is_file()]
            if files:
                return files[0]
        return executable_dir / bundle.stem

    def _append_row(install_root: Path, version: str, executable: Path) -> None:
        rows.append(
            {
                "version": version,
                "platform": "mac",
                "root": install_root,
                "executable": executable,
                "console_executable": executable,
            }
        )

    for platform_root in roots:
        if not platform_root.exists():
            continue
        if platform_root.is_dir():
            direct_match = GODOT_MACOS_VERSION_PATTERN.match(platform_root.name)
            if direct_match:
                executable = _bundle_executable(platform_root)
                if executable.exists():
                    _append_row(platform_root, direct_match.group("version"), executable)
            for child in sorted(platform_root.iterdir()):
                if child.is_file() and child.name.startswith("Godot"):
                    match = GODOT_MACOS_VERSION_PATTERN.match(child.stem)
                    if match:
                        _append_row(child.parent, match.group("version"), child)
                    continue
                if not child.is_dir():
                    continue
                if not child.name.endswith(".app"):
                    continue
                match = GODOT_MACOS_VERSION_PATTERN.match(child.stem)
                if not match:
                    continue
                executable = _bundle_executable(child)
                if executable.exists():
                    _append_row(child, match.group("version"), executable)
        elif platform_root.is_file() and platform_root.name.startswith("Godot"):
            match = GODOT_MACOS_VERSION_PATTERN.match(platform_root.stem)
            if match:
                _append_row(platform_root.parent, match.group("version"), platform_root)
    return rows


def _discover_godot_platform_versions(platform_name: str) -> list[dict[str, object]]:
    roots = [PUBLIC_GODOT_ROOT / "engines" / platform_name]
    configured_roots = _configured_godot_roots()
    roots.extend(root / "engines" / platform_name for root in configured_roots)
    roots.extend(configured_roots)
    pattern = GODOT_WINDOWS_VERSION_PATTERN if platform_name == "windows" else GODOT_LINUX_VERSION_PATTERN
    rows: list[dict[str, object]] = []

    def _append_row(install_root: Path, match: re.Match[str]) -> None:
        version = match.group("version")
        executable = install_root / install_root.name
        console_executable = (
            install_root / f"Godot_v{version}_win64_console.exe" if platform_name == "windows" else executable
        )
        rows.append(
            {
                "version": version,
                "platform": platform_name,
                "root": install_root,
                "executable": executable,
                "console_executable": console_executable,
            }
        )

    for platform_root in roots:
        if not platform_root.is_dir():
            continue
        direct_match = pattern.match(platform_root.name)
        if direct_match:
            executable = platform_root / platform_root.name
            if executable.is_file():
                _append_row(platform_root, direct_match)
        for child in sorted(platform_root.iterdir()):
            if not child.is_dir():
                continue
            match = pattern.match(child.name)
            if not match:
                continue
            executable = child / child.name
            if not executable.is_file():
                continue
            _append_row(child, match)
    return rows


def public_engine_search_roots() -> dict[str, list[Path]]:
    system = platform.system().lower()
    if system == "darwin":
        return {
            "unreal": _unique_paths([PUBLIC_UNREAL_MAC_ROOT, *_configured_roots("FASTDIS_UNREAL_ROOTS")]),
            "godot": _unique_paths([PUBLIC_GODOT_ROOT, *_configured_godot_roots(), *_macos_godot_roots()]),
            "unity": _unique_paths([*MACOS_UNITY_ROOTS, *_configured_roots("FASTDIS_UNITY_ROOTS")]),
        }
    if system == "windows":
        return {
            "unreal": _unique_paths([unreal_public_root(), *_configured_roots("FASTDIS_UNREAL_ROOTS"), program_files_root("Epic Games")]),
            "godot": _unique_paths([PUBLIC_GODOT_ROOT, *_configured_godot_roots()]),
            "unity": _unique_paths([unity_public_root(), program_files_root("Unity", "Hub", "Editor")]),
        }
    godot_roots = [PUBLIC_GODOT_ROOT, *_configured_godot_roots()]
    return {
        "unreal": _unique_paths([unreal_public_root(), *_configured_roots("FASTDIS_UNREAL_ROOTS")]),
        "godot": _unique_paths(godot_roots),
        "unity": _unique_paths([unity_public_root(), *_configured_roots("FASTDIS_UNITY_ROOTS")]),
    }
