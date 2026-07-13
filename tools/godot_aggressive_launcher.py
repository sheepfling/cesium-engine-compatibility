#!/usr/bin/env python3
"""Aggressively launch the Godot visual-proof scene across installed versions."""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
import re
from pathlib import Path
import platform
import subprocess
import shutil
import sys
import uuid
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extensions.cesium.tools import engine_root_discovery
from tools import build_cesium_visual_proof, compare_cesium_visual_proof, godot_versioning


PROJECT_DIR = ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "godot_aggressive_launcher"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "godot_aggressive_launcher.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "godot_aggressive_launcher.md"
DEFAULT_LOG_DIR = DEFAULT_OUT_DIR / "logs"
DEFAULT_SCENE = "res://scenes/Main.tscn"
DEFAULT_CAPTURE_ROOT = ROOT / "extensions" / "cesium" / "examples" / "godot" / "CesiumVanillaExample" / "build" / "godot" / "CesiumVanillaExample" / "visual_proof"
DEFAULT_RUNTIME_ROOT = DEFAULT_OUT_DIR / "_work" / "runtime"
DEFAULT_HEALTH_ROOT = DEFAULT_OUT_DIR / "_work" / "health"
VISUAL_PROOF_MANIFEST = "visual_proof_manifest.json"
STALE_EXTENSION_ENTRY = "res://CesiumVanillaExample.gdextension"
HEALTH_PROBE_SCRIPT = "res://scripts/StartupHealthProbe.gd"
EXPECTED_PNGS = (
    "proxy_overview.png",
    "proxy_oblique.png",
    "proxy_close.png",
    "cesium_overview.png",
    "cesium_oblique.png",
    "cesium_close.png",
)
DEFAULT_ORPHAN_CLEANUP_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class Attempt:
    version: str
    executable: Path
    strategy: str
    proof_variants: tuple[str, ...] = ("proxy", "cesium")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _windows_error_mode() -> None:
    if os.name != "nt":
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    mode = 0x0001 | 0x0002 | 0x8000
    previous = int(kernel32.SetErrorMode(mode))
    kernel32.SetErrorMode(previous | mode)


def _repo_alias_root(root: Path) -> Path:
    resolved = root.resolve()
    if platform.system().lower() != "windows":
        return resolved
    alias_root = Path(os.environ.get("TEMP", str(Path.home() / "AppData" / "Local" / "Temp"))) / "cesium_godot" / "repo"
    alias_root.parent.mkdir(parents=True, exist_ok=True)
    if alias_root.exists() or alias_root.is_symlink():
        return alias_root
    try:
        alias_root.symlink_to(resolved, target_is_directory=True)
        return alias_root
    except OSError:
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(alias_root), str(resolved)],
                check=True,
                capture_output=True,
                text=True,
            )
            if alias_root.exists():
                return alias_root
        except (OSError, subprocess.SubprocessError):
            pass
    return resolved


def _ignore_staged_project(directory: str, names: list[str]) -> set[str]:
    # Never clone generated editor state into a staged runtime. Godot's
    # Windows cache can contain stale paths or transient files that disappear
    # during copytree, making an otherwise valid proof run fail before launch.
    ignored = {".godot", "Library", "Logs", "Temp", "UserSettings", "build", "Build"}
    if Path(directory).name == "build":
        ignored.update(names)
    return {name for name in names if name in ignored}


def _stage_godot_metadata(project_dir: Path, staged_dir: Path) -> None:
    source_godot = project_dir / ".godot"
    if not source_godot.is_dir():
        return
    staged_godot = staged_dir / ".godot"
    staged_godot.mkdir(parents=True, exist_ok=True)
    extension_list = source_godot / "extension_list.cfg"
    if extension_list.is_file():
        shutil.copy2(extension_list, staged_godot / "extension_list.cfg")
    gdignore = source_godot / ".gdignore"
    if gdignore.is_file():
        shutil.copy2(gdignore, staged_godot / ".gdignore")


def _resolve_cesium_addon_root() -> Path | None:
    candidates = [
        ROOT / "external" / "cesium" / "3D-Tiles-For-Godot" / "godot3dtiles" / "addons" / "cesium_godot",
        PROJECT_DIR / "addons" / "cesium_godot",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return None


def _stage_cesium_addon(project_dir: Path, staged_dir: Path) -> Path | None:
    addon_root = _resolve_cesium_addon_root()
    if addon_root is None:
        return None
    destination = staged_dir / "addons" / "cesium_godot"
    if destination.exists() or destination.is_symlink():
        _remove_existing_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(addon_root, destination)
    editor_plugin = destination / "cesium_godot.gd"
    _write_text(
        editor_plugin,
        """
@tool
extends EditorPlugin

class_name CesiumGodotEditorTool

func _enter_tree() -> void:
    print("Enabled Cesium plugin")

func _exit_tree() -> void:
    print("Disabled Cesium plugin")
""".strip()
        + "\n",
    )
    return destination


def _strip_editor_plugins(project_file: Path) -> None:
    if not project_file.is_file():
        return
    lines = project_file.read_text(encoding="utf-8").splitlines()
    cleaned: list[str] = []
    skip_plugins = False
    for line in lines:
        if line.strip() == "[editor_plugins]":
            skip_plugins = True
            continue
        if skip_plugins and line.startswith("[") and line.strip() != "[editor_plugins]":
            skip_plugins = False
        if skip_plugins:
            continue
        cleaned.append(line)
    project_file.write_text("\n".join(cleaned).rstrip() + "\n", encoding="utf-8")


def _remove_staged_editor_plugin(staged_dir: Path) -> None:
    plugin_cfg = staged_dir / "addons" / "cesium_godot" / "plugin.cfg"
    if plugin_cfg.is_file():
        plugin_cfg.unlink()


def _remove_existing_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _stage_project_dir(project_dir: Path, runtime_root: Path) -> Path:
    staged_dir = runtime_root / "project" / project_dir.name
    if staged_dir.exists() or staged_dir.is_symlink():
        _remove_existing_path(staged_dir)
    staged_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project_dir, staged_dir, ignore=_ignore_staged_project)
    return staged_dir


def _stage_proxy_project_dir(project_dir: Path, runtime_root: Path) -> Path:
    staged_dir = runtime_root / "proxy" / "project" / project_dir.name
    if staged_dir.exists() or staged_dir.is_symlink():
        _remove_existing_path(staged_dir)
    staged_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(project_dir, staged_dir, ignore=_ignore_staged_project)
    _remove_existing_path(staged_dir / "addons")
    _remove_existing_path(staged_dir / ".godot")
    return staged_dir


def _gdextension_library_path(project_dir: Path) -> Path | None:
    gdextension = project_dir / "addons" / "cesium_godot" / "Godot3DTiles.gdextension"
    if not gdextension.is_file():
        return None
    text = gdextension.read_text(encoding="utf-8")
    match = re.search(r"^windows\.release\.x86_64\s*=\s*\"(res://[^\"]+)\"", text, re.MULTILINE)
    if match is None:
        match = re.search(r"^windows\.debug\.x86_64\s*=\s*\"(res://[^\"]+)\"", text, re.MULTILINE)
    if match is None:
        return None
    relative = match.group(1).removeprefix("res://")
    return project_dir / relative.replace("/", "\\")


def _stage_import_dir(staged_project_dir: Path, runtime_root: Path) -> Path:
    import_dir = runtime_root / "import" / staged_project_dir.name
    if import_dir.exists():
        _remove_existing_path(import_dir)
    import_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        staged_project_dir,
        import_dir,
        ignore=shutil.ignore_patterns(".godot", "addons"),
    )
    project_file = import_dir / "project.godot"
    if project_file.is_file():
        lines = project_file.read_text(encoding="utf-8").splitlines()
        cleaned: list[str] = []
        skip_plugins = False
        for line in lines:
            if line.strip() == "[editor_plugins]":
                skip_plugins = True
                continue
            if skip_plugins and line.startswith("[") and line.strip() != "[editor_plugins]":
                skip_plugins = False
            if skip_plugins:
                continue
            cleaned.append(line)
        project_file.write_text("\n".join(cleaned).rstrip() + "\n", encoding="utf-8")
    return import_dir


def _stage_cesium_smoke_project(project_dir: Path, runtime_root: Path) -> Path:
    smoke_root = runtime_root / "cesium_smoke"
    staged_dir = _stage_project_dir(project_dir, smoke_root)
    _stage_cesium_addon(project_dir, staged_dir)
    _remove_existing_path(staged_dir / ".godot")
    _strip_editor_plugins(staged_dir / "project.godot")
    _stage_godot_metadata(project_dir, staged_dir)
    _sanitize_project_extension_cache(staged_dir)
    return staged_dir


def _write_godot_smoke_script(project_dir: Path) -> Path:
    script_path = project_dir / "run_cesium_example_smoke.gd"
    _write_text(
        script_path,
        """
extends SceneTree

func _init() -> void:
    var report_path := OS.get_environment("FASTDIS_CESIUM_EXAMPLE_REPORT")
    var addon_root := "res://addons/cesium_godot"
    var descriptor_path := addon_root + "/Godot3DTiles.gdextension"
    var plugin_cfg_path := addon_root + "/plugin.cfg"
    print("starting cesium smoke probe")
    var descriptor_present := FileAccess.file_exists(descriptor_path)
    var plugin_cfg_present := FileAccess.file_exists(plugin_cfg_path)
    var georeference_class_present := ClassDB.class_exists("CesiumGeoreference")
    var status := "pass" if descriptor_present and plugin_cfg_present and georeference_class_present else "fail"
    var payload := {
        "status": status,
        "descriptor_present": descriptor_present,
        "plugin_cfg_present": plugin_cfg_present,
        "georeference_class_present": georeference_class_present,
        "descriptor_path": descriptor_path,
        "plugin_cfg_path": plugin_cfg_path
    }
    print(JSON.stringify(payload))
    if report_path != "":
        var file := FileAccess.open(report_path, FileAccess.WRITE)
        if file != null:
            file.store_string(JSON.stringify(payload, "  "))
            file.store_string("\\n")
    quit(0 if status == "pass" else 3)
""".strip()
        + "\n",
    )
    return script_path


def _smoke_probe_command(
    executable: Path,
    project_dir: Path,
    script_path: Path,
    native_target: str,
    *,
    diagnostic_crash_dumps: bool = False,
) -> list[str]:
    command = [
        str(executable),
        *(["--disable-crash-handler"] if diagnostic_crash_dumps else []),
    ]
    if native_target == "windows":
        command.extend(["--audio-driver", "Dummy", "--rendering-driver", "opengl3"])
    else:
        command.extend(["--headless", "--audio-driver", "Dummy"])
    command.extend([
        "--path",
        str(project_dir),
        "--script",
        str(script_path),
    ])
    return command


def _stage_health_probe_project(runtime_root: Path) -> Path:
    health_root = DEFAULT_HEALTH_ROOT.resolve()
    project_dir = health_root / "project" / "startup_health"
    if project_dir.exists():
        _remove_existing_path(project_dir)
    project_dir.parent.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        PROJECT_DIR / "scripts" / "StartupHealthProbe.gd",
        scripts_dir / "StartupHealthProbe.gd",
    )
    (project_dir / "project.godot").write_text(
        "\n".join(
            [
                '; Engine configuration file.',
                '; It is best edited using the editor UI.',
                "",
                "[application]",
                'config/name="Cesium Startup Health Probe"',
                'run/main_scene=""',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return project_dir


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--scene", default=DEFAULT_SCENE)
    parser.add_argument("--capture-root", type=Path, default=DEFAULT_CAPTURE_ROOT)
    parser.add_argument("--native-target", choices=("windows", "linux", "mac"), default="windows")
    parser.add_argument("--godot-selector", help="Optional Godot version selector such as 4.7-stable..4.8-dev1")
    parser.add_argument("--max-versions", type=int, default=0, help="Optional cap on how many installed versions to try")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--diagnostic-crash-dumps", action="store_true", help="Disable Godot's crash handler to favor direct dumps/logging.")
    parser.add_argument("--split-proof-lanes", action="store_true", help="Run proxy-earth and Cesium-earth as separate proof lanes.")
    parser.add_argument("--run-timeout-seconds", type=float, default=None, help="Optional timeout for each Godot launch, in seconds.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _slug(value: str) -> str:
    return value.replace(".", "_").replace("-", "_")


def _discover_versions(native_target: str) -> list[dict[str, object]]:
    if native_target == "windows":
        return engine_root_discovery.discover_godot_windows_versions()
    if native_target == "linux":
        return engine_root_discovery.discover_godot_linux_versions()
    return engine_root_discovery.discover_godot_macos_versions()


def _ordered_versions(
    native_target: str,
    selector: str | None = None,
    limit: int | None = None,
) -> list[dict[str, object]]:
    rows = _discover_versions(native_target)
    versions = [str(row.get("version") or "") for row in rows if str(row.get("version") or "")]
    ordered = godot_versioning.select_versions(versions, selector, limit=limit)
    ordered_rows: list[dict[str, object]] = []
    for version in ordered:
        for row in rows:
            if str(row.get("version") or "") == version:
                ordered_rows.append(row)
                break
    return ordered_rows


def _pick_executables(install: dict[str, object]) -> list[tuple[str, Path]]:
    executables: list[tuple[str, Path]] = []
    console = install.get("console_executable")
    executable = install.get("executable")
    if isinstance(console, Path) and console.is_file():
        executables.append(("console", console))
    if isinstance(executable, Path) and executable.is_file():
        if not executables or executables[-1][1] != executable:
            executables.append(("gui", executable))
    return executables


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    system = platform.system().lower()
    if system == "darwin":
        runtime_root = DEFAULT_RUNTIME_ROOT
        home = runtime_root / "Home"
        cache = home / ".cache"
        config = home / ".config"
        data = home / ".local" / "share"
        temp_dir = runtime_root / "Temp"
        for path in (home, cache, config, data, temp_dir):
            path.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home)
        env["CFFIXED_USER_HOME"] = str(home)
        env["TMPDIR"] = str(temp_dir)
        env["XDG_CACHE_HOME"] = str(cache)
        env["XDG_CONFIG_HOME"] = str(config)
        env["XDG_DATA_HOME"] = str(data)
        return env
    if system != "windows":
        return env
    runtime_root = DEFAULT_RUNTIME_ROOT
    user_profile = runtime_root / "UserProfile"
    localappdata = runtime_root / "LocalAppData"
    appdata = runtime_root / "RoamingAppData"
    temp_dir = runtime_root / "Temp"
    godot_user_dir = runtime_root / "GodotUser"
    for path in (user_profile, localappdata, appdata, temp_dir, godot_user_dir):
        path.mkdir(parents=True, exist_ok=True)
    (godot_user_dir / "logs").mkdir(parents=True, exist_ok=True)
    # Godot resolves user:// on Windows below APPDATA/Godot/app_userdata.
    # Create the project cache parent before Vulkan initializes its RD shaders;
    # otherwise the renderer emits cache-write errors and can lose tile frames.
    for project_name in ("CesiumVanillaExample", "Cesium Startup Health Probe"):
        (appdata / "Godot" / "app_userdata" / project_name / "shader_cache").mkdir(
            parents=True,
            exist_ok=True,
        )
    env["USERPROFILE"] = str(user_profile)
    env["HOMEDRIVE"] = "C:"
    env["HOMEPATH"] = "\\"
    env["HOME"] = str(user_profile)
    env["LOCALAPPDATA"] = str(localappdata)
    env["APPDATA"] = str(appdata)
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["GODOT_USER_DIR"] = str(godot_user_dir)
    return env


def _ion_token_configured(env: dict[str, str]) -> bool:
    return any(
        str(env.get(name) or "").strip()
        for name in ("CESIUM_ION_ACCESS_TOKEN", "CESIUM_ION_TOKEN", "CESIUMION_TOKEN")
    )


def _cleanup_orphan_godot_processes(
    markers: list[str],
    *,
    log_path: Path | None = None,
    timeout_s: float = DEFAULT_ORPHAN_CLEANUP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    if platform.system().lower() != "windows":
        return {"supported": False, "matches": [], "killed": [], "success": True}
    markers = [marker for marker in markers if marker]
    if not markers:
        return {"supported": True, "matches": [], "killed": [], "success": True}
    powershell = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    marker_literal = "@(" + ", ".join("'" + marker.replace("'", "''") + "'" for marker in markers) + ")"
    script = f"""
$markers = {marker_literal}
$matches = Get-CimInstance Win32_Process | Where-Object {{
    $hit = $false
    foreach ($marker in $markers) {{
        if ($marker -and $_.CommandLine.Contains($marker)) {{
            $hit = $true
            break
        }}
    }}
    $_.Name -like 'Godot*.exe' -and
    $_.CommandLine -and
    $hit
}}
$rows = @()
foreach ($match in $matches) {{
    $rows += [pscustomobject]@{{
        pid = [int]$match.ProcessId
        name = [string]$match.Name
        command_line = [string]$match.CommandLine
    }}
}}
foreach ($row in $rows) {{
    Stop-Process -Id $row.pid -Force -ErrorAction SilentlyContinue
}}
if ($rows.Count -gt 0) {{
    $rows | ConvertTo-Json -Compress -Depth 4
}} else {{
    '[]'
}}
""".strip()
    try:
        completed = subprocess.run(
            [str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=dict(os.environ),
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                f"orphan cleanup timed out after {timeout_s} seconds\n{(exc.stdout or '').strip()}\n{(exc.stderr or '').strip()}\n",
                encoding="utf-8",
            )
        return {
            "supported": True,
            "matches": [],
            "killed": [],
            "success": False,
            "timed_out": True,
            "timeout_seconds": timeout_s,
        }
    stdout = (completed.stdout or "").strip()
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(stdout + ("\n" if stdout and not stdout.endswith("\n") else ""), encoding="utf-8")
    if completed.returncode != 0:
        return {
            "supported": True,
            "matches": [],
            "killed": [],
            "success": False,
            "timed_out": False,
            "returncode": completed.returncode,
            "stderr": completed.stderr.strip(),
        }
    try:
        parsed = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        parsed = []
    if isinstance(parsed, dict):
        parsed = [parsed]
    killed = [
        {
            "pid": int(entry.get("pid", 0)),
            "name": str(entry.get("name") or ""),
            "command_line": str(entry.get("command_line") or ""),
        }
        for entry in parsed
        if isinstance(entry, dict)
    ]
    return {
        "supported": True,
        "matches": killed,
        "killed": [entry["pid"] for entry in killed],
        "success": True,
        "timed_out": False,
        "returncode": completed.returncode,
    }


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    if platform.system().lower() == "windows":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=dict(os.environ),
            check=False,
            timeout=10.0,
        )
        return
    try:
        proc.terminate()
    except OSError:
        pass


def _cleanup_markers_for_run(
    launch_tag: str | None,
    *,
    runtime_root: Path,
    project_dir: Path,
    health_project_dir: Path,
    staged_project_dir: Path,
    proxy_project_dir: Path | None = None,
    smoke_project_dir: Path | None = None,
    staged_import_dir: Path | None = None,
    proxy_import_dir: Path | None = None,
    capture_root: Path | None = None,
) -> list[str]:
    markers = [
        launch_tag,
        str(runtime_root),
        str(health_project_dir),
        str(staged_project_dir),
        str(project_dir),
    ]
    for optional_path in (proxy_project_dir, smoke_project_dir, staged_import_dir, proxy_import_dir, capture_root):
        if optional_path is not None:
            markers.append(str(optional_path))
    return [marker for marker in markers if marker]


def _sanitize_project_extension_cache(project_dir: Path) -> list[str]:
    extension_list = project_dir / ".godot" / "extension_list.cfg"
    if not extension_list.is_file():
        return []
    lines = extension_list.read_text(encoding="utf-8").splitlines()
    removed = [line for line in lines if line.strip() == STALE_EXTENSION_ENTRY]
    if not removed:
        return []
    kept = [line for line in lines if line.strip() and line.strip() != STALE_EXTENSION_ENTRY]
    if kept:
        extension_list.write_text("\n".join(kept) + "\n", encoding="utf-8")
    else:
        extension_list.unlink()
    return removed


def _capture_paths(capture_root: Path) -> list[Path]:
    return [capture_root / name for name in EXPECTED_PNGS]


def _capture_paths_for_variants(capture_root: Path, proof_variants: tuple[str, ...]) -> list[Path]:
    allowed = [variant for variant in proof_variants if variant]
    if not allowed:
        return _capture_paths(capture_root)
    return [capture_root / name for name in EXPECTED_PNGS if any(name.startswith(f"{variant}_") for variant in allowed)]


def _clear_capture_root(capture_root: Path) -> None:
    """Remove only this lane's generated proof files, never the project."""
    for path in [*_capture_paths(capture_root), _manifest_path(capture_root)]:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            # A locked stale artifact must not be mistaken for fresh evidence.
            continue


def _post_proof_native_shutdown_crash(result: dict[str, Any], capture_paths: list[Path], variant: str) -> bool:
    """Recognize evidence completed before the known native shutdown crash."""
    if result.get("exit_code") != 3221225477:
        return False
    if not all(path.is_file() for path in capture_paths):
        return False
    output = "\n".join(str(line) for line in result.get("stdout_tail", []))
    return f"PROOF_READY variant={variant}" in output and f"captured {variant}_close" in output


def _sync_capture_variants(source_root: Path, target_root: Path, proof_variants: tuple[str, ...]) -> None:
    if source_root == target_root:
        return
    source_paths = _capture_paths_for_variants(source_root, proof_variants)
    target_paths = _capture_paths_for_variants(target_root, proof_variants)
    for source_path, target_path in zip(source_paths, target_paths, strict=False):
        if not source_path.is_file():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)


def _attempt_capture_root(runtime_root: Path, lane: str, attempt: Attempt) -> Path:
    """Give every engine/version/strategy attempt an isolated output folder."""
    root = runtime_root / "attempt_captures" / lane / _slug(attempt.version) / attempt.strategy
    root.mkdir(parents=True, exist_ok=True)
    return root


def _manifest_path(capture_root: Path) -> Path:
    return capture_root / VISUAL_PROOF_MANIFEST


def _emit_visual_proof_manifest(
    capture_root: Path,
    *,
    engine: str,
    host: str,
    native_target: str,
    architecture: str | None,
    version: str | None,
    requested_selector: str | None,
    project_dir: Path,
    proof_variants: tuple[str, ...],
    capture_paths: list[Path],
) -> None:
    manifest = {
        "schema": "cesium.visual_proof_manifest.v1",
        "engine": engine,
        "host": host,
        "native_target": native_target,
        "architecture": architecture,
        "version": version,
        "requested_selector": requested_selector,
        "project_dir": str(project_dir),
        "capture_root": str(capture_root),
        "capture_variants": list(proof_variants),
        "shot_names": list(build_cesium_visual_proof.canonical_shot_names()),
        "camera_shots": [
            {
                "name": shot.name,
                "camera_position": list(shot.camera_position),
                "look_at": list(shot.look_at),
                "up": list(shot.up),
                "fov_degrees": shot.fov_degrees,
            }
            for shot in build_cesium_visual_proof.CAMERA_SHOTS
        ],
        "capture_paths": [str(path) for path in capture_paths],
    }
    capture_root.mkdir(parents=True, exist_ok=True)
    _write_text(_manifest_path(capture_root), json.dumps(manifest, indent=2) + "\n")


def _launch_flags(native_target: str, *, diagnostic_crash_dumps: bool = False) -> list[str]:
    flags: list[str] = []
    if diagnostic_crash_dumps:
        flags.append("--disable-crash-handler")
    if native_target == "windows":
        # Cesium's Windows GDExtension targets Godot Forward+; forcing the
        # OpenGL compatibility driver causes shader initialization failures
        # and prevents the tileset from producing renderable tile nodes.
        flags.extend(["--audio-driver", "Dummy", "--rendering-driver", "vulkan"])
        return flags
    flags.extend(["--audio-driver", "Dummy"])
    return flags


def _launch_tag_arg(launch_tag: str | None) -> list[str]:
    if not launch_tag:
        return []
    return ["--fastdis-launch-tag", launch_tag]


def _import_probe_command(
    executable: Path,
    project_dir: Path,
    *,
    launch_tag: str | None = None,
    diagnostic_crash_dumps: bool = False,
) -> list[str]:
    return [
        str(executable),
        *(["--disable-crash-handler"] if diagnostic_crash_dumps else []),
        *_launch_tag_arg(launch_tag),
        "--headless",
        "--audio-driver",
        "Dummy",
        "--path",
        str(project_dir),
        "--import",
        "--quit",
    ]


def _health_probe_command(
    executable: Path,
    project_dir: Path,
    native_target: str,
    *,
    launch_tag: str | None = None,
) -> list[str]:
    return [
        str(executable),
        *_launch_flags(native_target),
        *_launch_tag_arg(launch_tag),
        "--path",
        str(project_dir),
        "--headless",
        "-s",
        HEALTH_PROBE_SCRIPT,
    ]


def _attempt_command(
    executable: Path,
    project_dir: Path,
    scene: str,
    capture_root: Path,
    native_target: str,
    *,
    proof_variants: tuple[str, ...] = ("proxy", "cesium"),
    launch_tag: str | None = None,
    diagnostic_crash_dumps: bool = False,
) -> list[str]:
    return [
        str(executable),
        *_launch_flags(native_target, diagnostic_crash_dumps=diagnostic_crash_dumps),
        *_launch_tag_arg(launch_tag),
        "--path",
        str(project_dir),
        "--scene",
        scene,
        "--capture-root",
        str(capture_root),
        "--proof-variants",
        ",".join(proof_variants),
    ]


def _run_command(
    *,
    command: list[str],
    env: dict[str, str],
    log_path: Path,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    creationflags = 0
    if platform.system().lower() == "windows":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    stdout_path = log_path.with_suffix(log_path.suffix + ".stdout")
    stderr_path = log_path.with_suffix(log_path.suffix + ".stderr")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    timed_out = False
    returncode: int | None = None
    fallback_stdout = ""
    fallback_stderr = ""
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as stderr_file:
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
            creationflags=creationflags,
        )
        if hasattr(proc, "wait"):
            try:
                proc.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                _terminate_process_tree(proc)
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    pass
        else:
            # Keep lightweight process doubles compatible with the launcher tests.
            try:
                fallback_stdout, fallback_stderr = proc.communicate(timeout=timeout_s)
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                fallback_stdout = str(exc.output or "")
                fallback_stderr = str(exc.stderr or "")
                _terminate_process_tree(proc)
                tail_stdout, tail_stderr = proc.communicate(timeout=5.0)
                fallback_stdout += tail_stdout or ""
                fallback_stderr += tail_stderr or ""
        returncode = proc.returncode
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    stdout = stdout or fallback_stdout
    stderr = stderr or fallback_stderr
    for path in (stdout_path, stderr_path):
        try:
            path.unlink()
        except OSError:
            pass
    combined_output = "\n".join(part for part in [stdout, stderr] if part)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(combined_output + ("\n" if combined_output and not combined_output.endswith("\n") else ""), encoding="utf-8")
    return {
        "command": command,
        "log_path": str(log_path),
        "exit_code": returncode,
        "stdout_tail": _tail_lines(stdout or ""),
        "stderr_tail": _tail_lines(stderr or ""),
        "timed_out": timed_out,
        "success": (returncode == 0) and not timed_out,
    }


def _tail_lines(text: str, limit: int = 80) -> list[str]:
    rows = [line for line in text.splitlines() if line.strip()]
    return rows[-max(1, limit):]


def _build_attempts(args: argparse.Namespace) -> list[Attempt]:
    ordered = _ordered_versions(args.native_target, args.godot_selector, args.max_versions or None)
    attempts: list[Attempt] = []
    for row in ordered:
        version = str(row.get("version") or "")
        for strategy, executable in _pick_executables(row):
            attempts.append(Attempt(version=version, executable=executable, strategy=strategy))
    return attempts


def _run_attempt(
    *,
    attempt: Attempt,
    args: argparse.Namespace,
    env: dict[str, str],
    log_path: Path,
) -> dict[str, Any]:
    command = _attempt_command(
        attempt.executable,
        args.project_dir,
        args.scene,
        args.capture_root,
        args.native_target,
        launch_tag=getattr(args, "launch_tag", None),
        proof_variants=attempt.proof_variants,
        diagnostic_crash_dumps=args.diagnostic_crash_dumps,
    )
    result = _run_command(command=command, env=env, log_path=log_path, timeout_s=args.run_timeout_seconds)
    capture_paths = _capture_paths_for_variants(args.capture_root, attempt.proof_variants)
    capture_exists = all(path.is_file() for path in capture_paths)
    shutdown_crash = _post_proof_native_shutdown_crash(result, capture_paths, attempt.proof_variants[0])
    return {
        "version": attempt.version,
        "strategy": attempt.strategy,
        "proof_variants": list(attempt.proof_variants),
        "executable": str(attempt.executable),
        **result,
        "capture_root": str(args.capture_root),
        "capture_paths": [str(path) for path in capture_paths],
        "capture_exists": capture_exists,
        "native_shutdown_crash_after_proof": shutdown_crash,
        "success": (result["success"] or shutdown_crash) and capture_exists,
    }


def _run_health_probe(
    *,
    executable: Path,
    project_dir: Path,
    native_target: str,
    env: dict[str, str],
    log_path: Path,
    timeout_s: float | None = None,
    launch_tag: str | None = None,
) -> dict[str, Any]:
    command = _health_probe_command(executable, project_dir, native_target, launch_tag=launch_tag)
    result = _run_command(command=command, env=env, log_path=log_path, timeout_s=timeout_s)
    return {
        "executable": str(executable),
        **result,
        "startup_ok": result["success"],
    }


def _run_import_probe(
    *,
    executable: Path,
    project_dir: Path,
    env: dict[str, str],
    log_path: Path,
    timeout_s: float | None = None,
    launch_tag: str | None = None,
    diagnostic_crash_dumps: bool = False,
) -> dict[str, Any]:
    command = _import_probe_command(
        executable,
        project_dir,
        launch_tag=launch_tag,
        diagnostic_crash_dumps=diagnostic_crash_dumps,
    )
    result = _run_command(command=command, env=env, log_path=log_path, timeout_s=timeout_s)
    return {
        "executable": str(executable),
        **result,
        "import_ok": result["success"],
    }


def _run_cesium_smoke_probe(
    *,
    executable: Path,
    project_dir: Path,
    env: dict[str, str],
    log_path: Path,
    timeout_s: float | None = None,
    launch_tag: str | None = None,
    diagnostic_crash_dumps: bool = False,
) -> dict[str, Any]:
    capture_root = project_dir / "build" / "godot" / project_dir.name / "visual_proof"
    command = _attempt_command(
        executable,
        project_dir,
        DEFAULT_SCENE,
        capture_root,
        "windows",
        launch_tag=launch_tag,
        diagnostic_crash_dumps=diagnostic_crash_dumps,
        proof_variants=("cesium",),
    )
    result = _run_command(command=command, env=env, log_path=log_path, timeout_s=timeout_s)
    fallback_to_proxy = any(
        "falling back to proxy earth" in line.lower() for line in result["stdout_tail"] + result["stderr_tail"]
    )
    capture_paths = _capture_paths_for_variants(capture_root, ("cesium",))
    capture_exists = all(path.is_file() for path in capture_paths)
    shutdown_crash = _post_proof_native_shutdown_crash(result, capture_paths, "cesium")
    return {
        "executable": str(executable),
        "capture_root": str(capture_root),
        **result,
        "capture_paths": [str(path) for path in capture_paths],
        "capture_exists": capture_exists,
        "fallback_to_proxy": fallback_to_proxy,
        "native_shutdown_crash_after_proof": shutdown_crash,
        "smoke_ok": (result["success"] or shutdown_crash) and capture_exists and not fallback_to_proxy,
    }


def _run_cesium_smoke_attempt(
    *,
    attempt: Attempt,
    project_dir: Path,
    env: dict[str, str],
    log_path: Path,
    timeout_s: float | None = None,
    launch_tag: str | None = None,
    diagnostic_crash_dumps: bool = False,
) -> dict[str, Any]:
    result = _run_cesium_smoke_probe(
        executable=attempt.executable,
        project_dir=project_dir,
        env=env,
        log_path=log_path,
        timeout_s=timeout_s,
        launch_tag=launch_tag,
        diagnostic_crash_dumps=diagnostic_crash_dumps,
    )
    return {
        "version": attempt.version,
        "strategy": attempt.strategy,
        "executable": str(attempt.executable),
        **result,
    }


def _run_visual_proof_compare(capture_root: Path) -> dict[str, Any]:
    payload = compare_cesium_visual_proof.build_payload(scan_roots=[capture_root], strict_missing=True)
    # The launcher owns one engine lane. The global comparator intentionally
    # reports ``partial`` when only one engine is present because it cannot
    # perform cross-engine comparisons yet. Do not turn that expected scope
    # difference into a launcher failure when this root has both variants,
    # every camera shot, and no image-quality findings.
    if payload.get("status") == "partial":
        summary = payload.get("summary")
        if isinstance(summary, dict):
            expected_sample_count = len(build_cesium_visual_proof.canonical_capture_variants()) * len(build_cesium_visual_proof.CAMERA_SHOTS)
            if (
                summary.get("sample_count") == expected_sample_count
                and summary.get("quality_issue_count") == 0
                and not summary.get("variant_missing")
            ):
                payload["status"] = "pass"
                payload["comparison_scope"] = "engine-local"
                payload["scope_note"] = "Global cross-engine comparisons run in the Windows audit packet."
    return payload


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Godot Aggressive Launcher",
        "",
        f"- status: `{payload['status']}`",
        f"- requested_selector: `{payload.get('requested_selector') or 'none'}`",
        f"- launch_tag: `{payload.get('launch_tag') or 'none'}`",
        f"- capture_root: `{payload.get('capture_root')}`",
        f"- project_dir: `{payload.get('project_dir')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- staged_project_dir: `{payload.get('staged_project_dir')}`",
        f"- attempts: `{len(payload.get('attempts', []))}`",
        f"- successful_attempt: `{payload.get('successful_attempt_index')}`",
    ]
    bootstrap = payload.get("bootstrap")
    if isinstance(bootstrap, dict):
        lines.extend([
            "",
            "## Bootstrap",
            "",
            f"- runtime_root: `{bootstrap.get('runtime_root')}`",
            f"- staged_project_dir: `{bootstrap.get('staged_project_dir')}`",
            f"- isolated: `{bootstrap.get('isolated')}`",
        ])
    import_probe = payload.get("import_probe")
    if isinstance(import_probe, dict):
        lines.extend([
            "",
            "## Import Probe",
            "",
            f"- executable: `{import_probe.get('executable')}`",
            f"- exit_code: `{import_probe.get('exit_code')}`",
            f"- success: `{import_probe.get('success')}`",
            f"- log_path: `{import_probe.get('log_path')}`",
        ])
    startup_health = payload.get("startup_health")
    if isinstance(startup_health, dict):
        lines.extend([
            "",
            "## Startup Health",
            "",
            f"- executable: `{startup_health.get('executable')}`",
            f"- exit_code: `{startup_health.get('exit_code')}`",
            f"- success: `{startup_health.get('success')}`",
            f"- log_path: `{startup_health.get('log_path')}`",
        ])
    for section_name in ("orphan_cleanup_preflight", "orphan_cleanup_postflight"):
        cleanup = payload.get(section_name)
        if isinstance(cleanup, dict):
            lines.extend([
                "",
                f"## {section_name.replace('_', ' ').title()}",
                "",
                f"- supported: `{cleanup.get('supported')}`",
                f"- success: `{cleanup.get('success')}`",
                f"- killed: `{cleanup.get('killed')}`",
            ])
    if payload.get("attempts"):
        lines.extend(["", "## Attempts", ""])
        for attempt in payload["attempts"]:
            if not isinstance(attempt, dict):
                continue
            lines.append(f"### {attempt.get('version')} / {attempt.get('strategy')}")
            lines.append(f"- executable: `{attempt.get('executable')}`")
            lines.append(f"- exit_code: `{attempt.get('exit_code')}`")
            lines.append(f"- success: `{attempt.get('success')}`")
            lines.append(f"- log_path: `{attempt.get('log_path')}`")
            if attempt.get("capture_paths"):
                lines.append("- capture_paths:")
                for path in attempt["capture_paths"]:
                    lines.append(f"  - `{path}`")
    if payload.get("next_steps"):
        lines.extend(["", "## Next Steps", ""])
        for step in payload["next_steps"]:
            lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def _write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(_render_markdown(payload), encoding="utf-8")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = _repo_alias_root(args.project_dir.expanduser())
    runtime_root = DEFAULT_RUNTIME_ROOT.resolve()
    launch_tag = f"cesium-godot-{uuid.uuid4().hex}"
    health_project_dir = _stage_health_probe_project(runtime_root)
    if args.split_proof_lanes:
        proxy_project_dir = _stage_proxy_project_dir(project_dir, runtime_root)
        staged_project_dir = _stage_project_dir(project_dir, runtime_root)
        _stage_cesium_addon(project_dir, staged_project_dir)
        _strip_editor_plugins(proxy_project_dir / "project.godot")
        _remove_existing_path(staged_project_dir / ".godot")
        _strip_editor_plugins(staged_project_dir / "project.godot")
        _stage_godot_metadata(project_dir, staged_project_dir)
        smoke_project_dir = _stage_cesium_smoke_project(project_dir, runtime_root)
        proxy_import_dir = _stage_import_dir(proxy_project_dir, runtime_root / "proxy")
        staged_import_dir = _stage_import_dir(staged_project_dir, runtime_root)
        capture_root = args.capture_root.expanduser().resolve()
        if capture_root == DEFAULT_CAPTURE_ROOT.resolve():
            capture_root = staged_project_dir / "build" / "godot" / "CesiumVanillaExample" / "visual_proof"
        _clear_capture_root(capture_root)
        sanitized_extension_entries = _sanitize_project_extension_cache(staged_project_dir)
        ordered_attempts = _build_attempts(args)
        proxy_attempts = [
            Attempt(version=attempt.version, executable=attempt.executable, strategy=attempt.strategy, proof_variants=("proxy",))
            for attempt in ordered_attempts
        ]
        cesium_attempts = [
            Attempt(version=attempt.version, executable=attempt.executable, strategy=attempt.strategy, proof_variants=("cesium",))
            for attempt in ordered_attempts
        ]
        ordered_versions: list[str] = []
        for attempt in proxy_attempts + cesium_attempts:
            if attempt.version in ordered_versions:
                continue
            ordered_versions.append(attempt.version)
        payload: dict[str, Any] = {
            "schema": "cesium.godot_aggressive_launcher.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "project_dir": str(project_dir),
            "runtime_root": str(runtime_root),
            "health_project_dir": str(health_project_dir),
            "staged_project_dir": str(staged_project_dir),
            "staged_import_dir": str(staged_import_dir),
            "proxy_project_dir": str(proxy_project_dir),
            "smoke_project_dir": str(smoke_project_dir),
            "proxy_import_dir": str(proxy_import_dir),
            "diagnostic_crash_dumps": args.diagnostic_crash_dumps,
            "split_proof_lanes": True,
            "bootstrap": {
                "runtime_root": str(runtime_root),
                "health_project_dir": str(health_project_dir),
                "staged_project_dir": str(staged_project_dir),
                "staged_import_dir": str(staged_import_dir),
                "proxy_project_dir": str(proxy_project_dir),
                "smoke_project_dir": str(smoke_project_dir),
                "proxy_import_dir": str(proxy_import_dir),
                "isolated": True,
            },
            "scene": args.scene,
            "capture_root": str(capture_root),
            "native_target": args.native_target,
            "capture_paths": [str(path) for path in _capture_paths(capture_root)],
            "requested_selector": args.godot_selector,
            "installed_versions_order": ordered_versions,
            "sanitized_extension_entries": sanitized_extension_entries,
            "startup_health": None,
            "cesium_smoke_probe": None,
            "attempts": [],
            "proxy_attempts": [],
            "cesium_attempts": [],
            "successful_attempt_index": None,
            "orphan_cleanup_preflight": None,
            "orphan_cleanup_postflight": None,
            "status": "dry-run" if args.dry_run else "needs-attention",
            "next_steps": [
                f"Use the newest installed {args.native_target.title()} Godot version first, then fall through to older installs if the scene fails.",
                "Keep the console binary as the preferred launcher and fall back to the GUI binary when needed.",
            "Use the capture root from the report so repeated runs land in a stable proof folder.",
            ],
        }
        if args.dry_run:
            first_attempt = proxy_attempts[0] if proxy_attempts else (cesium_attempts[0] if cesium_attempts else None)
            first_executable = first_attempt.executable if first_attempt else None
            payload["startup_health"] = {
                "executable": str(first_executable) if first_executable else None,
                "command": _health_probe_command(
                    first_executable,
                    health_project_dir,
                    args.native_target,
                    launch_tag=launch_tag,
                )
                if first_executable
                else None,
                "log_path": str(args.log_dir / "startup_health_probe.log"),
                "exit_code": None,
                "stdout_tail": [],
                "stderr_tail": [],
                "startup_ok": False,
                "success": False,
            }
            payload["import_probe"] = {
                "executable": str(first_executable) if first_executable else None,
                "command": _import_probe_command(
                    first_executable,
                    proxy_import_dir,
                    launch_tag=launch_tag,
                    diagnostic_crash_dumps=args.diagnostic_crash_dumps,
                )
                if first_executable
                else None,
                "log_path": str(args.log_dir / "proxy_import_probe.log"),
                "exit_code": None,
                "stdout_tail": [],
                "stderr_tail": [],
                "import_ok": False,
                "success": False,
            }
            payload["import_probe_cesium"] = {
                "executable": str(first_executable) if first_executable else None,
                "command": _import_probe_command(
                    first_executable,
                    staged_import_dir,
                    launch_tag=launch_tag,
                    diagnostic_crash_dumps=args.diagnostic_crash_dumps,
                )
                if first_executable
                else None,
                "log_path": str(args.log_dir / "cesium_import_probe.log"),
                "exit_code": None,
                "stdout_tail": [],
                "stderr_tail": [],
                "import_ok": False,
                "success": False,
            }
            payload["proxy_attempts"] = [
                {
                    "version": attempt.version,
                    "strategy": attempt.strategy,
                    "proof_variants": list(attempt.proof_variants),
                    "executable": str(attempt.executable),
                    "command": _attempt_command(
                        attempt.executable,
                        proxy_project_dir,
                        args.scene,
                        capture_root,
                        args.native_target,
                        launch_tag=launch_tag,
                        proof_variants=attempt.proof_variants,
                        diagnostic_crash_dumps=args.diagnostic_crash_dumps,
                    ),
                    "log_path": str(args.log_dir / f"proxy_{_slug(attempt.version)}_{attempt.strategy}.log"),
                    "exit_code": None,
                    "stdout_tail": [],
                    "stderr_tail": [],
                    "capture_root": str(capture_root),
                    "capture_paths": [str(path) for path in _capture_paths_for_variants(capture_root, attempt.proof_variants)],
                    "capture_exists": False,
                    "success": False,
                }
                for attempt in proxy_attempts
            ]
            payload["cesium_attempts"] = [
                {
                    "version": attempt.version,
                    "strategy": attempt.strategy,
                    "proof_variants": list(attempt.proof_variants),
                    "executable": str(attempt.executable),
                    "command": _attempt_command(
                        attempt.executable,
                        staged_project_dir,
                        args.scene,
                        capture_root,
                        args.native_target,
                        launch_tag=launch_tag,
                        proof_variants=attempt.proof_variants,
                        diagnostic_crash_dumps=args.diagnostic_crash_dumps,
                    ),
                    "log_path": str(args.log_dir / f"cesium_{_slug(attempt.version)}_{attempt.strategy}.log"),
                    "exit_code": None,
                    "stdout_tail": [],
                    "stderr_tail": [],
                    "capture_root": str(capture_root),
                    "capture_paths": [str(path) for path in _capture_paths_for_variants(capture_root, attempt.proof_variants)],
                    "capture_exists": False,
                    "success": False,
                }
                for attempt in cesium_attempts
            ]
            payload["attempts"] = payload["proxy_attempts"] + payload["cesium_attempts"]
            return payload
        _windows_error_mode()
        env = _build_env()
        payload["cesium_token_configured"] = _ion_token_configured(env)
        cleanup_markers = _cleanup_markers_for_run(
            launch_tag,
            runtime_root=runtime_root,
            project_dir=project_dir,
            health_project_dir=health_project_dir,
            staged_project_dir=staged_project_dir,
            proxy_project_dir=proxy_project_dir,
            smoke_project_dir=smoke_project_dir,
            staged_import_dir=staged_import_dir,
            proxy_import_dir=proxy_import_dir,
            capture_root=capture_root,
        )
        payload["orphan_cleanup_preflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
        if proxy_attempts:
            startup_log_path = args.log_dir / "startup_health_probe.log"
            startup_result = _run_health_probe(
                executable=proxy_attempts[0].executable,
                project_dir=health_project_dir,
                native_target=args.native_target,
                env=env,
                log_path=startup_log_path,
                timeout_s=args.run_timeout_seconds,
                launch_tag=launch_tag,
            )
            payload["startup_health"] = startup_result
            if not startup_result["success"]:
                payload["status"] = "fail"
                payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
                payload["next_steps"] = [
                    "Fix the startup health probe before running the visual proof lanes.",
                    "Inspect the health probe log for shader-cache or extension-registration errors.",
                ]
                return payload

            proxy_import_log_path = args.log_dir / "proxy_import_probe.log"
            proxy_import_result = _run_import_probe(
                executable=proxy_attempts[0].executable,
                project_dir=proxy_import_dir,
                env=env,
                log_path=proxy_import_log_path,
                timeout_s=args.run_timeout_seconds,
                launch_tag=launch_tag,
                diagnostic_crash_dumps=args.diagnostic_crash_dumps,
            )
            payload["import_probe"] = proxy_import_result
            if not proxy_import_result["success"]:
                payload["status"] = "fail"
                payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
                payload["next_steps"] = [
                    "Fix the proxy import probe before running the proxy proof lane.",
                    "Inspect the import log for project-scaffold, cache, or addon registration errors.",
                ]
                return payload

            proxy_success_index: int | None = None
            for index, attempt in enumerate(proxy_attempts):
                log_path = args.log_dir / f"proxy_{_slug(attempt.version)}_{attempt.strategy}.log"
                attempt_capture_root = _attempt_capture_root(runtime_root, "proxy", attempt)
                lane_args = argparse.Namespace(
                    **{
                        **vars(args),
                        "project_dir": proxy_project_dir,
                        "capture_root": attempt_capture_root,
                        "launch_tag": launch_tag,
                    }
                )
                result = _run_attempt(attempt=attempt, args=lane_args, env=env, log_path=log_path)
                payload["proxy_attempts"].append(result)
                payload["attempts"].append(result)
                if result["success"] and proxy_success_index is None:
                    proxy_success_index = index
                    _sync_capture_variants(attempt_capture_root, capture_root, ("proxy",))
            if proxy_success_index is None:
                payload["status"] = "fail"
                payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
                payload["next_steps"] = [
                    "No proxy-earth proof lane completed successfully on Windows.",
                    "Inspect the proxy lane logs for scene bootstrap or screenshot errors.",
                ]
                return payload

            proxy_capture_root = proxy_project_dir / "build" / "godot" / "CesiumVanillaExample" / "visual_proof"
            _sync_capture_variants(proxy_capture_root, capture_root, ("proxy",))

            cesium_import_log_path = args.log_dir / "cesium_import_probe.log"
            cesium_import_result = _run_import_probe(
                executable=cesium_attempts[0].executable,
                project_dir=staged_import_dir,
                env=env,
                log_path=cesium_import_log_path,
                timeout_s=args.run_timeout_seconds,
                launch_tag=launch_tag,
                diagnostic_crash_dumps=args.diagnostic_crash_dumps,
            )
            payload["import_probe_cesium"] = cesium_import_result
            if not cesium_import_result["success"]:
                payload["status"] = "partial" if proxy_success_index is not None else "fail"
                payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
                payload["next_steps"] = [
                    "Fix the Cesium import probe before running the Cesium proof lane.",
                    "Inspect the import log for project-scaffold, cache, or addon registration errors.",
                ]
                return payload

            smoke_attempt_results: list[dict[str, Any]] = []
            smoke_success_index: int | None = None
            for index, attempt in enumerate(cesium_attempts):
                smoke_log_path = args.log_dir / f"cesium_smoke_{_slug(attempt.version)}_{attempt.strategy}.log"
                smoke_result = _run_cesium_smoke_attempt(
                    attempt=attempt,
                    project_dir=smoke_project_dir,
                    env=env,
                    log_path=smoke_log_path,
                    timeout_s=args.run_timeout_seconds,
                    diagnostic_crash_dumps=args.diagnostic_crash_dumps,
                )
                smoke_attempt_results.append(smoke_result)
                if smoke_result.get("smoke_ok") and smoke_success_index is None:
                    smoke_success_index = index
                    break
            payload["cesium_smoke_probe"] = {
                "attempts": smoke_attempt_results,
                "successful_attempt_index": smoke_success_index,
                "success": smoke_success_index is not None,
            }
            if smoke_success_index is None:
                payload["status"] = "partial" if proxy_success_index is not None else "fail"
                payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
                payload["next_steps"] = [
                    "Fix the Cesium smoke probe before running the Cesium proof lane.",
                    "Inspect the smoke log for plugin bootstrap or extension-registration errors.",
                ]
                return payload

            cesium_success_index: int | None = None
            for index, attempt in enumerate(cesium_attempts):
                log_path = args.log_dir / f"cesium_{_slug(attempt.version)}_{attempt.strategy}.log"
                attempt_capture_root = _attempt_capture_root(runtime_root, "cesium", attempt)
                lane_args = argparse.Namespace(
                    **{
                        **vars(args),
                        "project_dir": staged_project_dir,
                        "capture_root": attempt_capture_root,
                        "launch_tag": launch_tag,
                    }
                )
                result = _run_attempt(attempt=attempt, args=lane_args, env=env, log_path=log_path)
                payload["cesium_attempts"].append(result)
                payload["attempts"].append(result)
                if result["success"] and cesium_success_index is None:
                    cesium_success_index = index
                    _sync_capture_variants(attempt_capture_root, capture_root, ("cesium",))

            # The isolated smoke lane exits cleanly and has already captured
            # the Cesium views. Some Windows builds of the native extension
            # crash only while shutting down the full proof process after all
            # images are written. Preserve that evidence, but report the
            # shutdown defect instead of silently treating the failed attempt
            # as the source of the proof.
            if cesium_success_index is None and smoke_success_index is not None:
                smoke_result = smoke_attempt_results[smoke_success_index]
                smoke_capture_root = Path(str(smoke_result.get("capture_root") or ""))
                _sync_capture_variants(smoke_capture_root, capture_root, ("cesium",))
                cesium_capture_paths = _capture_paths_for_variants(capture_root, ("cesium",))
                if all(path.is_file() for path in cesium_capture_paths):
                    cesium_success_index = smoke_success_index
                    payload["cesium_proof_source"] = "isolated_smoke_probe"
                    payload["cesium_shutdown_warning"] = {
                        "status": "warning",
                        "message": "Full Cesium proof wrote all images but crashed during native shutdown; isolated smoke capture is authoritative.",
                        "failed_attempts": [
                            {
                                "strategy": result.get("strategy"),
                                "exit_code": result.get("exit_code"),
                                "capture_exists": result.get("capture_exists"),
                            }
                            for result in payload["cesium_attempts"]
                            if not result.get("success")
                        ],
                    }

            if cesium_success_index is not None:
                payload["successful_attempt_index"] = len(proxy_attempts) + cesium_success_index
                final_attempt = cesium_attempts[cesium_success_index]
                _emit_visual_proof_manifest(
                    capture_root,
                    engine="godot",
                    host=args.native_target,
                    native_target=args.native_target,
                    architecture="x86_64" if "64" in str(final_attempt.executable).lower() else None,
                    version=final_attempt.version,
                    requested_selector=args.godot_selector,
                    project_dir=staged_project_dir,
                    proof_variants=("proxy", "cesium"),
                    capture_paths=_capture_paths(capture_root),
                )
                visual_compare = _run_visual_proof_compare(capture_root)
                payload["visual_proof_compare"] = visual_compare
                if visual_compare.get("status") != "pass":
                    payload["status"] = "fail"
                    payload["next_steps"] = [
                        "The proof lane captured output, but the visual comparison gate failed.",
                        "Inspect the drift and quality findings in the compare report before trusting the lane.",
                    ]
                    payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
                    return payload
                payload["status"] = "pass"
                payload["next_steps"] = [
                    f"The first successful {args.native_target.title()} Godot install can be reused for visual proof on this host.",
                    "If you want a different version order, pass --godot-selector or lower --max-versions.",
                ]
            else:
                payload["successful_attempt_index"] = proxy_success_index
                payload["status"] = "partial"
                final_attempt = proxy_attempts[proxy_success_index]
                _emit_visual_proof_manifest(
                    capture_root,
                    engine="godot",
                    host=args.native_target,
                    native_target=args.native_target,
                    architecture="x86_64" if "64" in str(final_attempt.executable).lower() else None,
                    version=final_attempt.version,
                    requested_selector=args.godot_selector,
                    project_dir=proxy_project_dir,
                    proof_variants=("proxy",),
                    capture_paths=_capture_paths_for_variants(capture_root, ("proxy",)),
                )
                payload["next_steps"] = [
                    "Proxy-earth proof is green, but the Cesium lane still needs to be stabilized.",
                    "Inspect the Cesium proof logs and the Cesium plugin bootstrap path next.",
                ]
            payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
            return payload
    staged_project_dir = _stage_project_dir(project_dir, runtime_root)
    _stage_cesium_addon(project_dir, staged_project_dir)
    _remove_existing_path(staged_project_dir / ".godot")
    _strip_editor_plugins(staged_project_dir / "project.godot")
    _stage_godot_metadata(project_dir, staged_project_dir)
    smoke_project_dir = _stage_cesium_smoke_project(project_dir, runtime_root)
    staged_import_dir = _stage_import_dir(staged_project_dir, runtime_root)
    capture_root = args.capture_root.expanduser().resolve()
    if capture_root == DEFAULT_CAPTURE_ROOT.resolve():
        capture_root = staged_project_dir / "build" / "godot" / "CesiumVanillaExample" / "visual_proof"
    capture_paths = _capture_paths(capture_root)
    sanitized_extension_entries = _sanitize_project_extension_cache(staged_project_dir)
    attempts = _build_attempts(args)
    ordered_versions: list[str] = []
    for attempt in attempts:
        if attempt.version in ordered_versions:
            continue
        ordered_versions.append(attempt.version)
    payload: dict[str, Any] = {
        "schema": "cesium.godot_aggressive_launcher.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "project_dir": str(project_dir),
        "runtime_root": str(runtime_root),
        "health_project_dir": str(health_project_dir),
        "staged_project_dir": str(staged_project_dir),
        "staged_import_dir": str(staged_import_dir),
        "smoke_project_dir": str(smoke_project_dir),
        "diagnostic_crash_dumps": args.diagnostic_crash_dumps,
        "bootstrap": {
            "runtime_root": str(runtime_root),
            "health_project_dir": str(health_project_dir),
            "staged_project_dir": str(staged_project_dir),
            "staged_import_dir": str(staged_import_dir),
            "smoke_project_dir": str(smoke_project_dir),
            "isolated": True,
        },
        "scene": args.scene,
            "capture_root": str(capture_root),
            "native_target": args.native_target,
            "capture_paths": [str(path) for path in capture_paths],
            "requested_selector": args.godot_selector,
            "launch_tag": launch_tag,
            "installed_versions_order": ordered_versions,
        "sanitized_extension_entries": sanitized_extension_entries,
        "startup_health": None,
        "cesium_smoke_probe": None,
        "attempts": [],
        "successful_attempt_index": None,
        "orphan_cleanup_preflight": None,
        "orphan_cleanup_postflight": None,
        "status": "dry-run" if args.dry_run else "needs-attention",
        "next_steps": [
            f"Use the newest installed {args.native_target.title()} Godot version first, then fall through to older installs if the scene fails.",
            "Keep the console binary as the preferred launcher and fall back to the GUI binary when needed.",
            "Use the capture root from the report so repeated runs land in a stable proof folder.",
        ],
    }
    if args.dry_run:
        first_attempt = attempts[0] if attempts else None
        first_executable = first_attempt.executable if first_attempt else None
        payload["startup_health"] = {
            "executable": str(first_executable) if first_executable else None,
            "command": _health_probe_command(
                first_executable,
                health_project_dir,
                args.native_target,
                launch_tag=launch_tag,
            )
            if first_executable
            else None,
            "log_path": str(args.log_dir / "startup_health_probe.log"),
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "startup_ok": False,
            "success": False,
        }
        payload["import_probe"] = {
            "executable": str(first_executable) if first_executable else None,
            "command": _import_probe_command(
                first_executable,
                staged_import_dir,
                launch_tag=launch_tag,
                diagnostic_crash_dumps=args.diagnostic_crash_dumps,
            )
            if first_executable
            else None,
            "log_path": str(args.log_dir / "import_probe.log"),
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "import_ok": False,
            "success": False,
        }
        payload["attempts"] = [
            {
                "version": attempt.version,
                "strategy": attempt.strategy,
                "executable": str(attempt.executable),
                "command": _attempt_command(
                    attempt.executable,
                    staged_project_dir,
                    args.scene,
                    capture_root,
                    args.native_target,
                    launch_tag=launch_tag,
                    diagnostic_crash_dumps=args.diagnostic_crash_dumps,
                ),
                "log_path": str(args.log_dir / f"{_slug(attempt.version)}_{attempt.strategy}.log"),
                "exit_code": None,
                "stdout_tail": [],
                "stderr_tail": [],
                "capture_root": str(capture_root),
                "capture_paths": [str(path) for path in capture_paths],
                "capture_exists": False,
                "success": False,
            }
            for attempt in attempts
        ]
        return payload

    _windows_error_mode()
    env = _build_env()
    payload["cesium_token_configured"] = _ion_token_configured(env)
    cleanup_markers = _cleanup_markers_for_run(
        launch_tag,
        runtime_root=runtime_root,
        project_dir=project_dir,
        health_project_dir=health_project_dir,
        staged_project_dir=staged_project_dir,
        smoke_project_dir=smoke_project_dir,
        staged_import_dir=staged_import_dir,
        capture_root=capture_root,
    )
    payload["orphan_cleanup_preflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
    if attempts:
        import_log_path = args.log_dir / "import_probe.log"
        import_result = _run_import_probe(
            executable=attempts[0].executable,
            project_dir=staged_import_dir,
            env=env,
            log_path=import_log_path,
            timeout_s=args.run_timeout_seconds,
            launch_tag=launch_tag,
            diagnostic_crash_dumps=args.diagnostic_crash_dumps,
        )
        payload["import_probe"] = import_result
        if not import_result["success"]:
            payload["status"] = "fail"
            payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
            payload["next_steps"] = [
                "Fix the import probe before running the health probe or visual proof lane.",
                "Inspect the import log for project-scaffold, cache, or addon registration errors.",
            ]
            return payload

        startup_log_path = args.log_dir / "startup_health_probe.log"
        startup_result = _run_health_probe(
            executable=attempts[0].executable,
            project_dir=health_project_dir,
            native_target=args.native_target,
            env=env,
            log_path=startup_log_path,
            timeout_s=args.run_timeout_seconds,
            launch_tag=launch_tag,
        )
        payload["startup_health"] = startup_result
        if not startup_result["success"]:
            payload["status"] = "fail"
            payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
            payload["next_steps"] = [
                "Fix the startup health probe before running the visual proof lane.",
                "Inspect the health probe log for shader-cache or extension-registration errors.",
            ]
            return payload

        smoke_attempt_results: list[dict[str, Any]] = []
        smoke_success_index: int | None = None
        for index, attempt in enumerate(attempts):
            smoke_log_path = args.log_dir / f"cesium_smoke_{_slug(attempt.version)}_{attempt.strategy}.log"
            smoke_result = _run_cesium_smoke_attempt(
                attempt=attempt,
                project_dir=smoke_project_dir,
                env=env,
                log_path=smoke_log_path,
                timeout_s=args.run_timeout_seconds,
                launch_tag=launch_tag,
                diagnostic_crash_dumps=args.diagnostic_crash_dumps,
            )
            smoke_attempt_results.append(smoke_result)
            if smoke_result["success"] and smoke_success_index is None:
                smoke_success_index = index
                break
        payload["cesium_smoke_probe"] = {
            "attempts": smoke_attempt_results,
            "successful_attempt_index": smoke_success_index,
            "success": smoke_success_index is not None,
        }
        if smoke_success_index is None:
            payload["status"] = "fail"
            payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
            payload["next_steps"] = [
                "Fix the Cesium smoke probe before running the visual proof lane.",
                "Inspect the smoke log for plugin bootstrap or extension-registration errors.",
            ]
            return payload

    success_index: int | None = None
    for index, attempt in enumerate(attempts):
        log_path = args.log_dir / f"{_slug(attempt.version)}_{attempt.strategy}.log"
        attempt_args = argparse.Namespace(
            **{
                **vars(args),
                "project_dir": staged_project_dir,
                "capture_root": capture_root,
                "launch_tag": launch_tag,
            }
        )
        result = _run_attempt(attempt=attempt, args=attempt_args, env=env, log_path=log_path)
        payload["attempts"].append(result)
        if result["success"]:
            success_index = index
            break

    payload["successful_attempt_index"] = success_index
    payload["orphan_cleanup_postflight"] = _cleanup_orphan_godot_processes(cleanup_markers)
    if success_index is not None:
        final_attempt = attempts[success_index]
        _emit_visual_proof_manifest(
            capture_root,
            engine="godot",
            host=args.native_target,
            native_target=args.native_target,
            architecture="x86_64" if "64" in str(final_attempt.executable).lower() else None,
            version=final_attempt.version,
            requested_selector=args.godot_selector,
            project_dir=staged_project_dir,
            proof_variants=("proxy", "cesium"),
            capture_paths=_capture_paths(capture_root),
        )
        visual_compare = _run_visual_proof_compare(capture_root)
        payload["visual_proof_compare"] = visual_compare
        if visual_compare.get("status") != "pass":
            payload["status"] = "fail"
            payload["next_steps"] = [
                "The proof lane captured output, but the visual comparison gate failed.",
                "Inspect the drift and quality findings in the compare report before trusting the lane.",
            ]
            return payload
        payload["status"] = "pass"
        payload["next_steps"] = [
            f"The first successful {args.native_target.title()} Godot install can be reused for visual proof on this host.",
            "If you want a different version order, pass --godot-selector or lower --max-versions.",
        ]
    else:
        payload["status"] = "fail"
        payload["next_steps"] = [
            f"No {args.native_target.title()} Godot install completed the proof scene successfully.",
            "Try a different selector, or inspect the per-attempt logs under the report directory.",
        ]
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(args)
    _write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"pass", "dry-run"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
