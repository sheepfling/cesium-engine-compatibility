#!/usr/bin/env python3
"""Discover Unity installs and host metadata for Cesium Unity workflows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
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
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        return [Path(os.environ.get("PUBLIC", r"C:\Users\Public")) / "Unity", program_files / "Unity" / "Hub" / "Editor"]
    return [Path(os.environ.get("PUBLIC", str(Path.home() / "Public"))) / "Unity", Path.home() / "Unity" / "Hub" / "Editor", Path("/opt/Unity/Hub/Editor")]


def configured_roots() -> list[Path]:
    return _split_configured_paths(os.environ.get("FASTDIS_UNITY_ROOTS"))


def default_scan_roots() -> list[Path]:
    return _platform_roots()


def scan_roots() -> list[Path]:
    return configured_roots() + default_scan_roots()


def unity_hub_candidates() -> list[Path]:
    """Return likely Unity Hub desktop executables without requiring Hub on PATH."""
    if platform.system().lower() != "windows":
        return []
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    public_root = Path(os.environ.get("PUBLIC", r"C:\Users\Public"))
    candidates = [
        Path(os.environ.get("UNITY_HUB_PATH", "")),
        program_files / "Unity Hub" / "Unity Hub.exe",
        local_appdata / "Programs" / "Unity Hub" / "Unity Hub.exe",
        public_root / "Unity Hub" / "Unity Hub.exe",
    ]
    result: list[Path] = []
    for candidate in candidates:
        if str(candidate) and candidate.is_file() and candidate not in result:
            result.append(candidate.resolve())
    return result


def _license_status(output: str, exit_code: int | None) -> tuple[str, list[str]]:
    lowered = output.lower()
    blocked_markers = (
        "no valid unity editor license",
        "no valid license",
        "license is not active",
        "unable to activate unity",
        "serial number is not valid",
        "headless entitlement was unavailable",
    )
    available_markers = (
        "license type: personal",
        "license type: professional",
        "license type: plus",
        "license successfully returned",
        "licensed to",
        "product: unity personal",
        "successfully updated license",
    )
    blocked = [marker for marker in blocked_markers if marker in lowered]
    available = [marker for marker in available_markers if marker in lowered]
    if blocked:
        return "blocked", blocked
    # Unity can prove licensing before returning non-zero for later project
    # compilation errors. Keep license readiness independent from build health.
    if available:
        return "available", available
    return "unknown", []


def probe_unity_license(
    install: UnityInstall | None,
    *,
    project_dir: Path | None = None,
    log_path: Path | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    """Run a short, non-destructive Unity probe and classify license readiness."""
    if install is None or not install.editor_path:
        return {"status": "missing-editor", "command": None, "exit_code": None, "signals": []}
    if platform.system().lower() != "windows":
        return {"status": "not-run", "reason": "Unity desktop licensing probe is currently Windows-specific."}
    destination = (log_path or work_root() / "unity_license_probe.log").expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [str(install.editor_path), "-batchmode", "-nographics", "-quit", "-logFile", str(destination)]
    if project_dir is not None:
        command.extend(["-projectPath", str(project_dir)])
    try:
        completed = subprocess.run(
            command,
            cwd=str(project_dir) if project_dir else None,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = "\n".join((completed.stdout or "", completed.stderr or ""))
        if destination.is_file():
            output += "\n" + destination.read_text(encoding="utf-8", errors="replace")
        status, signals = _license_status(output, completed.returncode)
        return {
            "status": status,
            "command": command,
            "exit_code": completed.returncode,
            "signals": signals,
            "log_path": str(destination),
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "command": command, "exit_code": None, "signals": ["license probe timed out"], "log_path": str(destination)}
    except OSError as exc:
        return {"status": "error", "command": command, "exit_code": None, "signals": [str(exc)], "log_path": str(destination)}


def ensure_unity_hub_open(*, settle_seconds: float = 8.0) -> dict[str, object]:
    """Open Unity Hub visibly and leave it running for interactive activation."""
    candidates = unity_hub_candidates()
    if not candidates:
        return {"status": "missing", "executable": None, "settled": False, "candidates": []}
    executable = candidates[0]
    creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    try:
        process = subprocess.Popen([str(executable)], cwd=str(executable.parent), creationflags=creationflags)
        deadline = time.monotonic() + max(0.0, settle_seconds)
        while time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.25)
        process_alive = process.poll() is None
        attached_existing = False
        if not process_alive:
            try:
                tasklist = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq Unity Hub.exe"],
                    capture_output=True,
                    text=True,
                    timeout=5.0,
                    check=False,
                )
                attached_existing = "Unity Hub.exe" in (tasklist.stdout or "")
            except (OSError, subprocess.TimeoutExpired):
                attached_existing = False
        settled = process_alive or attached_existing
        return {
            "status": "opened" if process_alive else ("attached" if attached_existing else "exited"),
            "executable": str(executable),
            "pid": process.pid,
            "settled": settled,
            "candidates": [str(path) for path in candidates],
            "settle_seconds": settle_seconds,
            "left_running": settled,
            "attached_existing": attached_existing,
        }
    except OSError as exc:
        return {"status": "error", "executable": str(executable), "settled": False, "candidates": [str(path) for path in candidates], "error": str(exc)}


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
