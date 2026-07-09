#!/usr/bin/env python3
"""Shared engine-root discovery helpers for public alternate install paths."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path


PUBLIC_UNREAL_ROOT = Path(r"C:\Users\Public\Unreal")
PUBLIC_GODOT_ROOT = Path(r"C:\Users\Public\Godot")
PUBLIC_UNITY_ROOT = Path(r"C:\Users\Public\Unity")
PROGRAM_FILES_EPIC_GAMES = Path(r"C:\Program Files\Epic Games")
PROGRAM_FILES_UNITY = Path(r"C:\Program Files\Unity\Hub\Editor")
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
    for unreal_root in [PUBLIC_UNREAL_ROOT, *_configured_roots("FASTDIS_UNREAL_ROOTS")]:
        public_linux_root = unreal_root / "engines" / "linux"
        if public_linux_root.is_dir():
            for child in sorted(public_linux_root.iterdir()):
                if child.is_dir() and _is_unreal_linux_root(child):
                    candidates.append(child)
    if PROGRAM_FILES_EPIC_GAMES.is_dir():
        for child in sorted(PROGRAM_FILES_EPIC_GAMES.iterdir()):
            if child.is_dir() and child.name.startswith("UE_") and _is_unreal_linux_root(child):
                candidates.append(child)
    return candidates


def discover_unreal_linux_archives() -> list[Path]:
    archives: list[Path] = []
    for unreal_root in [PUBLIC_UNREAL_ROOT, *_configured_roots("FASTDIS_UNREAL_ROOTS")]:
        public_linux_root = unreal_root / "engines" / "linux"
        if not public_linux_root.is_dir():
            continue
        archives.extend(
            path for path in sorted(public_linux_root.iterdir()) if path.is_file() and path.suffix.lower() == ".zip"
        )
    return archives


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
    godot_roots = [PUBLIC_GODOT_ROOT, *_configured_godot_roots()]
    if platform.system().lower() == "darwin":
        godot_roots.extend(_macos_godot_roots())
    return {
        "unreal": _unique_paths([PUBLIC_UNREAL_ROOT, *_configured_roots("FASTDIS_UNREAL_ROOTS"), PROGRAM_FILES_EPIC_GAMES]),
        "godot": _unique_paths(godot_roots),
        "unity": _unique_paths([PUBLIC_UNITY_ROOT, PROGRAM_FILES_UNITY]),
    }
