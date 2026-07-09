#!/usr/bin/env python3
"""Discover Unity installs and host metadata for Cesium Unity workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import platform
import re
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_UNITY_ROOT = Path(r"C:\Users\Public\Unity")
PROGRAM_FILES_UNITY = Path(r"C:\Program Files\Unity\Hub\Editor")
UNITY_CHANNEL_RANK = {
    "p": 4,
    "f": 3,
    "rc": 2,
    "b": 1,
    "a": 0,
}


@dataclass(frozen=True)
class UnityInstall:
    version: str
    install_root: str
    editor_path: str | None
    editor_app_path: str | None
    source: str
    quirks: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _split_configured_paths(value: str | None) -> list[Path]:
    if not value:
        return []
    paths: list[Path] = []
    for raw_part in value.split(os.pathsep):
        part = raw_part.strip().strip('"')
        if not part:
            continue
        paths.append(Path(os.path.expandvars(part)).expanduser())
    return paths


def _default_work_root() -> Path:
    system = platform.system().lower()
    if system == "windows":
        return Path(tempfile.gettempdir()) / "fastdis_unity"
    return Path(tempfile.gettempdir()) / "fastdis_unity"


def work_root() -> Path:
    override = os.environ.get("FASTDIS_UNITY_WORK_ROOT")
    if override:
        return Path(override).expanduser()
    return _default_work_root()


def version_kind(value: str | None) -> str:
    parsed = _parse_unity_version(value)
    if parsed is None:
        return "unknown"
    if bool(parsed["stable_like"]):
        return "stable"
    return f"prerelease:{parsed['channel']}"


def _parse_unity_version(value: str | None) -> dict[str, object] | None:
    if not value:
        return None
    normalized = value.strip()
    match = re.search(
        r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?P<channel>rc|[abfp])(?P<num>\d+)",
        normalized,
        re.IGNORECASE,
    )
    if match:
        channel = match.group("channel").lower()
        return {
            "base": (int(match.group("major")), int(match.group("minor")), int(match.group("patch"))),
            "channel": channel,
            "channel_number": int(match.group("num")),
            "stable_like": channel in {"f", "p"},
        }
    fallback = re.search(r"(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?", normalized)
    if not fallback:
        return None
    return {
        "base": (int(fallback.group("major")), int(fallback.group("minor")), int(fallback.group("patch") or "0")),
        "channel": "f",
        "channel_number": 0,
        "stable_like": True,
    }


def _version_suffix(version: str | None) -> str | None:
    if version is None:
        return None
    normalized = version.strip()
    if not normalized:
        return None
    return normalized.replace(".", "_").replace("-", "_")


def _versioned_keys(base: str, version: str | None) -> list[str]:
    suffix = _version_suffix(version)
    keys: list[str] = []
    if suffix:
        keys.append(f"{base}_{suffix}")
    keys.append(base)
    return keys


def _normalize_editor_path(candidate: str | Path | None) -> Path | None:
    if candidate is None:
        return None
    path = Path(candidate).expanduser()
    if not path.exists():
        return None
    if path.is_file():
        return path.resolve()
    if path.suffix == ".app":
        executable = path / "Contents" / "MacOS" / "Unity"
        if executable.is_file():
            return executable.resolve()
    executable = path / "Editor" / ("Unity.exe" if platform.system().lower() == "windows" else "Unity")
    if executable.is_file():
        return executable.resolve()
    executable = path / "Unity.app" / "Contents" / "MacOS" / "Unity"
    if executable.is_file():
        return executable.resolve()
    return None


def _install_root_from_editor(editor_path: Path) -> Path | None:
    for parent in editor_path.parents:
        if parent.name == "Unity.app":
            return parent.parent.resolve()
        if parent.name == "Editor" and re.match(r"\d", parent.parent.name):
            return parent.parent.resolve()
        if re.match(r"\d{4}\.\d+\.", parent.name):
            return parent.resolve()
    return None


def _editor_paths_for_root(root: Path) -> tuple[Path | None, Path | None]:
    if platform.system().lower() == "darwin":
        app = root / "Unity.app"
        editor = _normalize_editor_path(app)
        return editor, app.resolve() if app.is_dir() else None
    candidates = [
        root / "Editor" / "Unity.exe",
        root / "Editor" / "Unity",
        root / "Unity.exe",
        root / "Unity",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve(), None
    return None, None


def _platform_roots() -> list[Path]:
    system = platform.system().lower()
    if system == "darwin":
        return [Path("/Applications/Unity/Hub/Editor"), Path.home() / "Applications" / "Unity" / "Hub" / "Editor"]
    if system == "windows":
        return [PUBLIC_UNITY_ROOT, Path("C:/Program Files/Unity/Hub/Editor"), Path("D:/Unity/Hub/Editor")]
    return [PUBLIC_UNITY_ROOT, Path.home() / "Unity" / "Hub" / "Editor", Path("/opt/Unity/Hub/Editor")]


def configured_roots() -> list[Path]:
    return _split_configured_paths(os.environ.get("FASTDIS_UNITY_ROOTS"))


def default_scan_roots() -> list[Path]:
    return _platform_roots()


def scan_roots() -> list[Path]:
    return configured_roots() + default_scan_roots()


def _version_from_root(root: Path) -> str:
    return root.name


def _unity_resolution_key(install: UnityInstall) -> tuple[int, int, int, int, int, int]:
    parsed = _parse_unity_version(install.version)
    if parsed is None:
        return (0, -1, -1, -1, -1, -1)
    major, minor, patch = parsed["base"]
    channel = str(parsed["channel"])
    stable_bias = 1 if bool(parsed["stable_like"]) else 0
    return (
        stable_bias,
        major,
        minor,
        patch,
        UNITY_CHANNEL_RANK.get(channel, -1),
        int(parsed["channel_number"]),
    )


def _install_from_root(root: Path, source: str) -> UnityInstall | None:
    if not root.exists():
        return None
    editor, app = _editor_paths_for_root(root)
    if editor is None and app is None:
        return None
    quirks: list[str] = []
    if editor is None:
        quirks.append("missing-editor-executable")
    return UnityInstall(
        version=_version_from_root(root),
        install_root=str(root.resolve()),
        editor_path=str(editor) if editor else None,
        editor_app_path=str(app) if app else None,
        source=source,
        quirks=tuple(quirks),
    )


def env_install(version: str | None = None) -> UnityInstall | None:
    for key in _versioned_keys("FASTDIS_UNITY_EDITOR", version):
        editor = _normalize_editor_path(os.environ.get(key))
        if editor is None:
            continue
        root = _install_root_from_editor(editor) or editor.parent
        return UnityInstall(
            version=version or _version_from_root(root),
            install_root=str(root),
            editor_path=str(editor),
            editor_app_path=str(root / "Unity.app") if (root / "Unity.app").is_dir() else None,
            source=f"env:{key}",
            quirks=(),
        )
    for key in _versioned_keys("FASTDIS_UNITY_EDITOR_DIR", version):
        candidate = os.environ.get(key)
        if not candidate:
            continue
        install = _install_from_root(Path(candidate).expanduser(), f"env:{key}")
        if install is not None:
            return install
    return None


def discover_installs() -> list[UnityInstall]:
    installs: dict[str, UnityInstall] = {}
    env = env_install(None)
    if env is not None:
        installs[env.install_root] = env
    path_editor = shutil.which("unity") or shutil.which("Unity") or shutil.which("Unity.exe")
    if path_editor:
        editor = Path(path_editor).resolve()
        root = _install_root_from_editor(editor) or editor.parent
        installs[str(root)] = UnityInstall(
            version=_version_from_root(root),
            install_root=str(root),
            editor_path=str(editor),
            editor_app_path=str(root / "Unity.app") if (root / "Unity.app").is_dir() else None,
            source="PATH",
            quirks=(),
        )
    for base in scan_roots():
        if not base.is_dir():
            continue
        install = _install_from_root(base, f"scan:{base}")
        if install is not None:
            installs.setdefault(install.install_root, install)
        if install is not None and install.install_root == str(base.resolve()):
            continue
        for root in sorted(path for path in base.iterdir() if path.is_dir()):
            install = _install_from_root(root, f"scan:{base}")
            if install is not None:
                installs.setdefault(install.install_root, install)
    return sorted(installs.values(), key=_unity_resolution_key, reverse=True)


def _preferred_install(installs: list[UnityInstall]) -> UnityInstall | None:
    for install in installs:
        if install.editor_path is not None:
            return install
    return installs[0] if installs else None


def recommended_editor_overrides(install: UnityInstall | None) -> dict[str, str]:
    if install is None or install.editor_path is None:
        return {}
    overrides = {"FASTDIS_UNITY_EDITOR": install.editor_path}
    if install.install_root:
        overrides["FASTDIS_UNITY_EDITOR_DIR"] = install.install_root
    return overrides


def resolve_install(version: str | None = None) -> UnityInstall | None:
    env = env_install(version)
    if env is not None:
        return env
    installs = discover_installs()
    if version:
        for install in installs:
            if install.version == version or install.version.startswith(version):
                return install
        return None
    return _preferred_install(installs)


def describe_host() -> dict[str, object]:
    current_work_root = work_root()
    discovered = discover_installs()
    preferred = _preferred_install(discovered)
    installs = []
    for install in discovered:
        row = install.to_dict()
        row["version_kind"] = version_kind(install.version)
        installs.append(row)
    default_install = None
    if preferred:
        default_install = preferred.to_dict()
        default_install["version_kind"] = version_kind(preferred.version)
    return {
        "platform": platform.system(),
        "arch": platform.machine(),
        "repo_root": str(ROOT),
        "work_root": str(current_work_root),
        "work_root_has_spaces": " " in str(current_work_root),
        "installs": installs,
        "default_install": default_install,
        "recommended_editor_overrides": recommended_editor_overrides(preferred),
        "public_roots": [str(path) for path in scan_roots()],
    }
