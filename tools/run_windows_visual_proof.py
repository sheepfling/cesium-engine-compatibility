#!/usr/bin/env python3
"""Execute the Windows visual-proof lanes for Unreal, Unity, and Godot."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import shutil
import tempfile
import time
import zipfile
from typing import Any

from tools import (
    build_cesium_visual_proof,
    build_godot_visual_proof,
    build_unity_example,
    build_unity_visual_proof,
    build_unreal_visual_proof,
    compare_cesium_visual_proof,
    godot_aggressive_launcher,
    unity_env,
    validate_visual_proof_roots,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "windows_visual_proof_run"
DEFAULT_JSON_OUT = DEFAULT_OUT_DIR / "windows_visual_proof_run.json"
DEFAULT_MD_OUT = DEFAULT_OUT_DIR / "windows_visual_proof_run.md"
DEFAULT_LOG_DIR = DEFAULT_OUT_DIR / "logs"
DEFAULT_WORK_ROOT = Path(os.environ.get("TEMP", r"C:\Users\peanu\AppData\Local\Temp")) / "cwvpr"
UNREAL_NORMALIZED_CAPTURE_ROOT = ROOT / "artifacts" / "reports" / "cesium_visual_proof" / "unreal" / "windows" / "x86_64"
UNITY_NORMALIZED_CAPTURE_ROOT = ROOT / "artifacts" / "reports" / "cesium_visual_proof" / "unity" / "windows" / "x86_64"
GODOT_NORMALIZED_CAPTURE_ROOT = ROOT / "artifacts" / "reports" / "cesium_visual_proof" / "godot" / "windows" / "x86_64"
UNREAL_PROJECT_ALIAS_ROOT = DEFAULT_WORK_ROOT / "unreal" / "project_alias"
UNREAL_CESIUM_PACKAGE_CACHE = ROOT / ".tmp" / "cesium-unreal-packages"
UNREAL_CESIUM_PACKAGE_ZIPS = {
    "5.7": UNREAL_CESIUM_PACKAGE_CACHE / "CesiumForUnreal-57-main.zip",
    "5.8": UNREAL_CESIUM_PACKAGE_CACHE / "CesiumForUnreal-58-main.zip",
}
WINDOWS_CESIUM_NATIVE_SOURCE_ROOTS = [
    ROOT / "external" / "cesium" / "3D-Tiles-For-Godot" / "cesium_godot" / "native",
]
WINDOWS_CESIUM_DEPENDENCY_SOURCE_ROOTS = [
    ROOT / ".tmp" / "ezvcpkg",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--unity-version", help="Optional Unity version prefix to build with.")
    parser.add_argument("--godot-selector", help="Optional Godot version selector passed to the aggressive launcher.")
    parser.add_argument("--godot-max-versions", type=int, default=1)
    parser.add_argument(
        "--engines",
        default="unreal,unity,godot",
        help="Comma-separated lanes to execute; default runs all three Windows engines.",
    )
    parser.add_argument(
        "--unreal-versions",
        help="Comma-separated Unreal versions to prove sequentially, for example 5.7,5.8.",
    )
    parser.add_argument(
        "--unreal-max-parallel-actions",
        type=int,
        default=2,
        help="Cap UnrealBuildTool parallel actions; lower values reduce memory pressure on proof hosts.",
    )
    return parser.parse_args(argv)


def _tail_lines(text: str, limit: int = 80) -> list[str]:
    rows = [line for line in text.splitlines() if line.strip()]
    return rows[-max(1, limit):]


def _write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def _windows_runtime_env(work_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    user_profile = work_root / "UserProfile"
    localappdata = work_root / "LocalAppData"
    appdata = work_root / "RoamingAppData"
    programdata = work_root / "ProgramData"
    temp_dir = work_root / "Temp"
    for path in (user_profile, localappdata, appdata, programdata, temp_dir):
        path.mkdir(parents=True, exist_ok=True)
    env["USERPROFILE"] = str(user_profile)
    env["HOMEDRIVE"] = "C:"
    env["HOMEPATH"] = "\\"
    env["HOME"] = str(user_profile)
    env["LOCALAPPDATA"] = str(localappdata)
    env["APPDATA"] = str(appdata)
    env["PROGRAMDATA"] = str(programdata)
    env["ALLUSERSPROFILE"] = str(programdata)
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    if os.name == "nt":
        # UE 5.7+ rejects DDC roots longer than 119 characters. Keep this
        # host-only cache outside the long repository/temp path hierarchy.
        ddc_root = Path(tempfile.gettempdir()) / "ue_ddc" / work_root.name / "ddc"
        ddc_root.mkdir(parents=True, exist_ok=True)
        env["UE-LocalDataCachePath"] = str(ddc_root)
        uba_root = Path(tempfile.gettempdir()) / "ue_uba" / work_root.name
        uba_root.mkdir(parents=True, exist_ok=True)
        env["UBA_ROOT"] = str(uba_root)
    return env


def _visual_compare_gate_passes(compare_result: dict[str, Any] | None) -> bool:
    """Accept a fresh targeted packet without weakening image quality checks."""
    if not isinstance(compare_result, dict):
        return False
    if compare_result.get("status") == "pass":
        return True
    if compare_result.get("status") != "partial":
        return False
    quality = compare_result.get("quality") or []
    if any(item.get("flags") for item in quality if isinstance(item, dict)):
        return False
    if compare_result.get("findings"):
        return False
    missing = compare_result.get("canonical_missing") or []
    return bool(missing) and all("only one canonical sample present" in str(item) for item in missing)


def _split_command(command: str) -> list[str]:
    return shlex.split(command, posix=False)


def _alias_project_dir(project_dir: Path, alias_root: Path) -> Path:
    resolved = project_dir.resolve()
    alias_root = Path(alias_root)
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


def _replace_path_with_directory_link(destination: Path, source: Path) -> str:
    if destination.exists() or destination.is_symlink():
        try:
            if destination.resolve() == source.resolve():
                return "existing"
        except OSError:
            pass
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination, ignore_errors=True)
        else:
            try:
                destination.unlink()
            except OSError:
                pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.symlink_to(source, target_is_directory=True)
        return "symlink"
    except OSError:
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(destination), str(source)],
                check=True,
                capture_output=True,
                text=True,
            )
            if destination.exists():
                return "junction"
        except (OSError, subprocess.SubprocessError):
            pass
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return "copied"


def _ensure_unreal_third_party_include_bridge(build_root: Path, plugin_root: Path) -> dict[str, Any]:
    source_include_root = plugin_root / "Source" / "ThirdParty" / "include"
    if (source_include_root / "CesiumAsync" / "AsyncSystem.h").is_file():
        return {
            "status": "present",
            "source": str(source_include_root),
            "destination": str(source_include_root),
            "mode": "existing",
        }

    engine_root = build_root / "Engine"
    glm_source = None
    if engine_root.is_dir():
        for match in engine_root.rglob("glm.hpp"):
            if match.name == "glm.hpp" and match.parent.name == "glm":
                glm_source = match.parent
                break
    if glm_source is None:
        return {
            "status": "missing",
            "source": None,
            "destination": str(source_include_root),
            "mode": "unavailable",
            "reason": "No Cesium Unreal ThirdParty include root or fallback glm include directory was discovered.",
        }

    glm_destination = source_include_root / "glm"
    mode = _replace_path_with_directory_link(glm_destination, glm_source)
    return {
        "status": "present",
        "source": str(glm_source),
        "destination": str(glm_destination),
        "mode": mode,
    }


def _stage_unreal_release_third_party(plugin_root: Path, unreal_version: str | None) -> dict[str, Any]:
    """Stage the UE-specific native archives from an official Cesium package.

    The source plugin is kept in the project so the checked-in proof harness is
    compiled, but its native archives must come from the matching UE release.
    """
    package_zip = UNREAL_CESIUM_PACKAGE_ZIPS.get(unreal_version or "")
    if package_zip is None:
        return {"status": "not_requested", "mode": "workspace_sources"}
    if not package_zip.is_file():
        return {
            "status": "missing",
            "mode": "package_unavailable",
            "package_zip": str(package_zip),
            "reason": "Download the official Cesium for Unreal package for the selected UE version.",
        }

    extract_root = UNREAL_CESIUM_PACKAGE_CACHE / package_zip.stem
    package_plugin = extract_root / "CesiumForUnreal"
    marker = extract_root / ".extracted"
    if not marker.is_file() or not package_plugin.is_dir():
        if extract_root.exists():
            shutil.rmtree(extract_root, ignore_errors=True)
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(package_zip) as archive:
            archive.extractall(extract_root)
        marker.touch()

    source_third_party = package_plugin / "Source" / "ThirdParty"
    destination_third_party = plugin_root / "Source" / "ThirdParty"
    if not source_third_party.is_dir():
        return {
            "status": "missing",
            "mode": "package_invalid",
            "package_zip": str(package_zip),
            "reason": "The Cesium package has no Source/ThirdParty directory.",
        }
    if destination_third_party.exists():
        shutil.rmtree(destination_third_party, ignore_errors=True)
    shutil.copytree(source_third_party, destination_third_party)
    # The release package carries the engine-specific compatibility metadata.
    # Without it Unreal may refuse to load the otherwise compatible module.
    package_descriptor = package_plugin / "CesiumForUnreal.uplugin"
    if package_descriptor.is_file():
        shutil.copy2(package_descriptor, plugin_root / package_descriptor.name)
    return {
        "status": "present",
        "mode": "official_package",
        "package_zip": str(package_zip),
        "package_plugin": str(package_plugin),
        "source": str(source_third_party),
        "destination": str(destination_third_party),
        "descriptor": str(package_descriptor),
    }


def _ensure_unreal_windows_lib_bridge(plugin_root: Path) -> dict[str, Any]:
    destination = plugin_root / "Source" / "ThirdParty" / "lib" / "Windows-AMD64-Release"
    destination.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    candidates: list[Path] = []
    for root in WINDOWS_CESIUM_NATIVE_SOURCE_ROOTS:
        if root.is_dir():
            for lib in root.rglob("*.lib"):
                if (
                    lib.parent.name.lower() == "release"
                    and ".windows.editor.dev.x86_64.lib" in lib.name.lower()
                ):
                    candidates.append(lib)

    for root in WINDOWS_CESIUM_DEPENDENCY_SOURCE_ROOTS:
        if not root.is_dir():
            continue
        for lib in root.rglob("*.lib"):
            # The Cesium native archives are built in release mode. Avoid
            # accidentally mixing in vcpkg debug archives with them.
            if not lib.stem.lower().endswith("d") and "\\debug\\" not in str(lib).lower():
                candidates.append(lib)

    # Remove stale generic Cesium archives from older runs. The Windows editor
    # archives carry the ABI-specific suffix and must be the only Cesium
    # native variant presented to UBT.
    for stale in destination.glob("Cesium*.lib"):
        if ".windows.editor.dev.x86_64.lib" not in stale.name.lower():
            stale.unlink()

    seen_names: set[str] = set()
    for lib in sorted(candidates, key=lambda item: (item.name.lower(), str(item).lower())):
        if lib.name in seen_names:
            continue
        seen_names.add(lib.name)
        target = destination / lib.name
        if target.exists():
            continue
        shutil.copy2(lib, target)
        copied.append(str(target))

    existing_libs = sorted(destination.glob("*.lib"))
    if existing_libs:
        return {
            "status": "present",
            "source": [
                *[str(root) for root in WINDOWS_CESIUM_NATIVE_SOURCE_ROOTS if root.is_dir()],
                *[str(root) for root in WINDOWS_CESIUM_DEPENDENCY_SOURCE_ROOTS if root.is_dir()],
            ],
            "destination": str(destination),
            "mode": "copied" if copied else "existing",
            "count": len(existing_libs),
            "files": copied,
        }

    return {
        "status": "missing",
        "source": [str(root) for root in WINDOWS_CESIUM_NATIVE_SOURCE_ROOTS],
        "destination": str(destination),
        "mode": "unavailable",
        "reason": "No Windows Cesium native release libraries were discovered in the workspace.",
    }


def _invalidate_unreal_plugin_build_artifacts(plugin_root: Path) -> None:
    """Drop generated UBT response files after changing staged libraries."""
    for relative in ("Intermediate/Build", "Binaries/Win64"):
        generated = plugin_root / Path(relative)
        if generated.is_dir():
            shutil.rmtree(generated, ignore_errors=True)


def _prepare_unreal_generated_state(
    project_dir: Path,
    work_root: Path,
    unreal_version: str | None,
) -> dict[str, Any]:
    """Keep Unreal's generated headers isolated when switching engine versions.

    The checked-in example is shared by the 5.7 and 5.8 lanes, but UHT output
    is not. A stale Intermediate tree can make a newer UBT compile against
    headers emitted by an older engine. Clean only generated project state on
    the first run for a version, then retain incremental builds for reruns.
    """
    marker = work_root / ".unreal-generated-state-version"
    expected = unreal_version or "default"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == expected:
        return {"status": "reused", "version": expected, "cleaned": []}

    generated_names = ("Intermediate", "Binaries", "Saved", "DerivedDataCache")
    cleaned: list[str] = []
    for name in generated_names:
        generated = project_dir / name
        if generated.is_dir() and not generated.is_symlink():
            shutil.rmtree(generated, ignore_errors=True)
            cleaned.append(name)
    work_root.mkdir(parents=True, exist_ok=True)
    marker.write_text(expected + "\n", encoding="utf-8")
    return {"status": "reset", "version": expected, "cleaned": cleaned}


def _terminate_process_tree(proc: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10.0,
            )
        except subprocess.TimeoutExpired:
            pass
        return
    proc.kill()


def _run_process(
    command: list[str] | str,
    *,
    cwd: Path,
    env: dict[str, str] | None,
    timeout_seconds: float,
    log_path: Path,
) -> dict[str, Any]:
    args: list[str] | str
    if isinstance(command, str):
        args = command
    else:
        args = [str(part) for part in command]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    stdout_path = log_path.with_suffix(log_path.suffix + ".stdout")
    stderr_path = log_path.with_suffix(log_path.suffix + ".stderr")
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_file, stderr_path.open(
        "w", encoding="utf-8", errors="replace"
    ) as stderr_file:
        proc = subprocess.Popen(
            args,
            cwd=str(cwd),
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=creationflags,
        )
        timed_out = False
        marker_success = False
        is_unreal = "unrealeditor" in str(args).lower()
        deadline = time.monotonic() + timeout_seconds
        while proc.poll() is None:
            if is_unreal:
                live_output = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
                if "**** TEST COMPLETE. EXIT CODE: 0 ****" in live_output:
                    marker_success = True
                    # The editor has already completed the proof. Avoid a
                    # recursive taskkill here because Unreal's helper
                    # processes can make that cleanup command wait; the
                    # normal timeout path still uses bounded tree cleanup.
                    try:
                        proc.kill()
                    except OSError:
                        pass
                    break
            if time.monotonic() >= deadline:
                timed_out = True
                _terminate_process_tree(proc)
                break
            time.sleep(0.25)
        if proc.poll() is None:
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                pass
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.is_file() else ""
    for path in (stdout_path, stderr_path):
        try:
            path.unlink()
        except OSError:
            pass
    log_path.write_text((stdout or "") + ("\n" if stdout and stderr else "") + (stderr or ""), encoding="utf-8")
    return {
        "command": [args] if isinstance(args, str) else args,
        "returncode": proc.returncode,
        "timed_out": timed_out,
        "stdout_tail": _tail_lines(stdout or ""),
        "stderr_tail": _tail_lines(stderr or ""),
        "log_path": str(log_path),
        "success": (proc.returncode == 0 or marker_success) and not timed_out,
        "completed_by_marker": marker_success,
    }


def _normalize_capture(
    engine: str,
    source_root: Path,
    capture_root: Path,
    *,
    native_target: str = "windows",
    architecture: str = "x86_64",
) -> dict[str, Any]:
    if not source_root.exists():
        return {
            "status": "missing",
            "engine": engine,
            "source_root": str(source_root),
            "capture_root": str(capture_root),
            "manifest_path": str(capture_root / "visual_proof_manifest.json"),
            "missing": [str(source_root)],
        }
    return build_cesium_visual_proof.normalize_visual_proof_capture(
        engine,
        source_root,
        capture_root,
        host="windows",
        native_target=native_target,
        architecture=architecture,
        overwrite=True,
    )


def _clear_generated_capture_root(root: Path) -> None:
    """Remove only generated proof frames, never project or source files."""
    root.mkdir(parents=True, exist_ok=True)
    for path in root.glob("*.png"):
        try:
            path.unlink()
        except OSError:
            pass
    manifest = root / "visual_proof_manifest.json"
    if manifest.is_file():
        try:
            manifest.unlink()
        except OSError:
            pass


def _compare_roots(scan_roots: list[Path]) -> dict[str, Any]:
    return compare_cesium_visual_proof.build_payload(scan_roots=scan_roots, strict_missing=True)


def _validate_root_contract(root: Path) -> dict[str, Any]:
    return validate_visual_proof_roots.validate_root(root)


def _unreal_build_log_backup_denied(build_result: dict[str, Any]) -> bool:
    if build_result.get("success") is True:
        return False
    text = "\n".join(
        [
            *(str(line) for line in build_result.get("stdout_tail", []) or []),
            *(str(line) for line in build_result.get("stderr_tail", []) or []),
        ]
    )
    return "BackupLogFile" in text and "Access to the path is denied" in text


def _discover_unity_player_executable() -> Path | None:
    explicit = os.environ.get("CESIUM_UNITY_PROOF_PLAYER", "").strip()
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file() and _unity_player_has_runtime_harness(candidate):
            return candidate
    candidates = [
        path
        for path in (ROOT / "artifacts" / "reports" / "unity_example_build").rglob("CesiumVanillaExample.exe")
        if path.is_file()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _unity_player_has_runtime_harness(player_path: Path) -> bool:
    data_dir = player_path.parent / "CesiumVanillaExample_Data" / "Managed"
    if not data_dir.is_dir():
        return False
    return (data_dir / "Assembly-CSharp.dll").is_file() or (data_dir / "Assembly-CSharp-firstpass.dll").is_file()


def _unreal_payload() -> dict[str, Any]:
    return build_unreal_visual_proof.build_payload()


def _unity_payload() -> dict[str, Any]:
    return build_unity_visual_proof.build_payload()


def _godot_payload() -> dict[str, Any]:
    return build_godot_visual_proof.build_payload()


def _run_unity_lane(args: argparse.Namespace, work_root: Path) -> dict[str, Any]:
    report = _unity_payload()
    install = unity_env.resolve_install(args.unity_version)
    result: dict[str, Any] = {
        "engine": "unity",
        "report": report,
        "status": "skipped",
        "reason": "No Unity editor was discovered.",
        "build": None,
        "run": None,
        "normalize": None,
        "normalized_capture_root": str(UNITY_NORMALIZED_CAPTURE_ROOT),
        "raw_capture_root": None,
        "compare": None,
    }
    if install is None or install.editor_path is None:
        return result

    build_work_root = work_root / "unity_build"
    log_dir = args.log_dir.resolve() / "unity"
    fallback_player = _discover_unity_player_executable()
    explicit_fallback = os.environ.get("CESIUM_UNITY_PROOF_PLAYER", "").strip()
    if explicit_fallback and fallback_player is not None:
        build_result = {
            "status": "skipped",
            "reason": "Explicit CESIUM_UNITY_PROOF_PLAYER supplied; editor build intentionally bypassed.",
            "output_path": str(fallback_player),
        }
        result["build"] = build_result
        player_path = fallback_player
        result["player_fallback"] = str(fallback_player)
    else:
        build_args = argparse.Namespace(
            unity_version=install.version,
            build_target="windows",
            project_dir=Path(report["example_project"]).parent,
            out_dir=build_work_root,
            json_out=build_work_root / "unity_example_build.json",
            md_out=build_work_root / "unity_example_build.md",
            log_out=build_work_root / "unity_example_build.log",
            dry_run=False,
            preserve=False,
        )
        build_result = build_unity_example.run_build(build_args)
        result["build"] = build_result
        player_path = Path(str(build_result.get("output_path") or ""))
        if build_result.get("status") != "pass" or not player_path.is_file():
            if fallback_player is not None and _unity_player_has_runtime_harness(fallback_player):
                player_path = fallback_player
                result["player_fallback"] = str(fallback_player)
            else:
                result["status"] = "fail"
                result["reason"] = "Unity example build did not complete successfully, and no proof-capable fallback player was available."
                return result

    if not player_path.is_file():
        result["status"] = "fail"
        result["reason"] = "Unity player executable was not produced."
        return result

    run_env = _windows_runtime_env(work_root / "unity_player_runtime")
    _clear_generated_capture_root(UNITY_NORMALIZED_CAPTURE_ROOT)
    run_result = _run_process(
        [
            str(player_path),
            "-screen-fullscreen",
            "0",
            "-screen-width",
            "1280",
            "-screen-height",
            "720",
            "-logFile",
            str(log_dir / "unity_player.log"),
        ],
        cwd=player_path.parent,
        env=run_env,
        timeout_seconds=args.timeout_seconds,
        log_path=log_dir / "unity_player_process.log",
    )
    result["run"] = run_result
    raw_capture_root = player_path.parent / "build" / "unity" / "CesiumVanillaExample" / "visual_proof"
    result["raw_capture_root"] = str(raw_capture_root)
    normalize_result = _normalize_capture("unity", raw_capture_root, UNITY_NORMALIZED_CAPTURE_ROOT)
    result["normalize"] = normalize_result
    validation_result = _validate_root_contract(UNITY_NORMALIZED_CAPTURE_ROOT)
    result["validate"] = validation_result
    compare_result = _compare_roots([UNITY_NORMALIZED_CAPTURE_ROOT])
    result["compare"] = compare_result
    result["status"] = "pass" if run_result["success"] and normalize_result.get("status") == "pass" and validation_result.get("status") == "pass" and _visual_compare_gate_passes(compare_result) else "fail"
    if not run_result["success"]:
        result["reason"] = "Unity player did not exit cleanly."
    elif normalize_result.get("status") != "pass":
        result["reason"] = "Unity capture normalization did not complete cleanly."
    elif validation_result.get("status") != "pass":
        result["reason"] = "Unity visual-proof manifest/content contract failed."
    elif not _visual_compare_gate_passes(compare_result):
        result["reason"] = "Unity visual comparison gate failed."
    else:
        result["reason"] = None
    return result


def _run_godot_lane(args: argparse.Namespace, work_root: Path) -> dict[str, Any]:
    report = _godot_payload()
    result: dict[str, Any] = {
        "engine": "godot",
        "report": report,
        "status": "skipped",
        "reason": "No Windows Godot install was discovered.",
        "launcher": None,
        "normalize": None,
        "normalized_capture_root": str(GODOT_NORMALIZED_CAPTURE_ROOT),
        "raw_capture_root": None,
        "compare": None,
    }
    editor = report.get("editor_discovery", {}) if isinstance(report.get("editor_discovery"), dict) else {}
    if not isinstance(editor, dict) or editor.get("status") != "present":
        return result

    launcher_args = argparse.Namespace(
        project_dir=Path(str(report["example_project"])).parent,
        scene="res://scenes/Main.tscn",
        capture_root=work_root / "godot_capture",
        native_target="windows",
        godot_selector=args.godot_selector,
        max_versions=args.godot_max_versions,
        json_out=args.log_dir.resolve() / "godot" / "godot_aggressive_launcher.json",
        md_out=args.log_dir.resolve() / "godot" / "godot_aggressive_launcher.md",
        log_dir=args.log_dir.resolve() / "godot" / "logs",
        diagnostic_crash_dumps=True,
        split_proof_lanes=True,
        run_timeout_seconds=args.timeout_seconds,
        dry_run=False,
    )
    _clear_generated_capture_root(GODOT_NORMALIZED_CAPTURE_ROOT)
    if launcher_args.capture_root.exists():
        _clear_generated_capture_root(launcher_args.capture_root)
    launcher_result = godot_aggressive_launcher.build_payload(launcher_args)
    result["launcher"] = launcher_result
    raw_capture_root = Path(str(launcher_result.get("capture_root") or launcher_args.capture_root))
    result["raw_capture_root"] = str(raw_capture_root)
    normalize_result = _normalize_capture("godot", raw_capture_root, GODOT_NORMALIZED_CAPTURE_ROOT)
    result["normalize"] = normalize_result
    validation_result = _validate_root_contract(GODOT_NORMALIZED_CAPTURE_ROOT)
    result["validate"] = validation_result
    compare_result = _compare_roots([GODOT_NORMALIZED_CAPTURE_ROOT])
    result["compare"] = compare_result
    result["status"] = "pass" if launcher_result.get("status") == "pass" and normalize_result.get("status") == "pass" and validation_result.get("status") == "pass" and _visual_compare_gate_passes(compare_result) else "fail"
    if launcher_result.get("status") != "pass":
        result["reason"] = "Godot aggressive launcher did not complete successfully."
    elif normalize_result.get("status") != "pass":
        result["reason"] = "Godot capture normalization did not complete cleanly."
    elif validation_result.get("status") != "pass":
        result["reason"] = "Godot visual-proof manifest/content contract failed."
    elif not _visual_compare_gate_passes(compare_result):
        result["reason"] = "Godot visual comparison gate failed."
    else:
        result["reason"] = None
    return result


def _run_unreal_lane_single(args: argparse.Namespace, work_root: Path) -> dict[str, Any]:
    unreal_version = getattr(args, "unreal_version", None)
    report = (
        build_unreal_visual_proof.build_payload(version=unreal_version)
        if unreal_version
        else build_unreal_visual_proof.build_payload()
    )
    normalized_capture_root = (
        UNREAL_NORMALIZED_CAPTURE_ROOT / f"ue_{unreal_version}" / "x86_64"
        if unreal_version
        else UNREAL_NORMALIZED_CAPTURE_ROOT
    )
    log_suffix = f"_ue_{unreal_version.replace('.', '_')}" if unreal_version else ""
    result: dict[str, Any] = {
        "engine": "unreal",
        "engine_version": unreal_version,
        "report": report,
        "status": "skipped",
        "reason": "No Unreal Windows editor was discovered.",
        "build": None,
        "run": None,
        "normalize": None,
        "normalized_capture_root": str(normalized_capture_root),
        "raw_capture_root": str(build_cesium_visual_proof.UNREAL_RAW_CAPTURE_ROOT),
        "compare": None,
    }
    launcher_command = report.get("launcher_command")
    editor = report.get("editor_discovery", {}) if isinstance(report.get("editor_discovery"), dict) else {}
    if not launcher_command or not isinstance(editor, dict) or editor.get("status") != "present":
        return result

    build_root = Path(str(editor.get("selected_root") or ""))
    project_dir = Path(
        str(
            report.get("example_project")
            or (ROOT / "extensions" / "cesium" / "examples" / "unreal" / "CesiumVanillaExample" / "CesiumVanillaExample.uproject")
        )
    ).parent
    project_dir = _alias_project_dir(project_dir, UNREAL_PROJECT_ALIAS_ROOT / project_dir.name)
    result["generated_state"] = _prepare_unreal_generated_state(
        project_dir=project_dir,
        work_root=work_root,
        unreal_version=unreal_version,
    )
    plugin_root = project_dir / "Plugins" / "CesiumForUnreal"
    # Plugin UHT output is version-specific even when the project marker says
    # the same engine version. Always remove it before a lane build so a prior
    # run that was interrupted after switching engines cannot poison this lane.
    _invalidate_unreal_plugin_build_artifacts(plugin_root)
    result["generated_state"]["plugin_artifacts_reset"] = True
    result["third_party_bridge"] = _ensure_unreal_third_party_include_bridge(build_root, plugin_root)
    package_bridge = _stage_unreal_release_third_party(plugin_root, unreal_version)
    result["cesium_release_package"] = package_bridge
    if package_bridge.get("status") == "present":
        result["third_party_lib_bridge"] = {
            "status": "present",
            "source": package_bridge["source"],
            "destination": str(plugin_root / "Source" / "ThirdParty" / "lib" / "Windows-AMD64-Release"),
            "mode": "official_package",
            "count": len(list((plugin_root / "Source" / "ThirdParty" / "lib" / "Windows-AMD64-Release").glob("*.lib"))),
        }
    else:
        result["third_party_lib_bridge"] = _ensure_unreal_windows_lib_bridge(plugin_root)
        if package_bridge.get("status") == "missing":
            result["status"] = "fail"
            result["reason"] = package_bridge.get("reason", "Cesium release package was unavailable.")
            return result
    # Let UnrealBuildTool perform its normal incremental source check. The
    # prior unconditional deletion of Intermediate/Build forced every proof
    # rerun to rebuild the entire Cesium plugin and made camera-only iteration
    # unnecessarily fragile on memory-constrained hosts.
    project_file = project_dir / "CesiumVanillaExample.uproject"
    build_bat = build_root / "Engine" / "Build" / "BatchFiles" / "Build.bat"
    build_result: dict[str, Any] | None = None
    if build_bat.is_file():
        ubt_log_dir = args.log_dir.resolve() / "unreal"
        ubt_log_dir.mkdir(parents=True, exist_ok=True)
        build_result = _run_process(
            [
                str(build_bat),
                "CesiumVanillaExampleEditor",
                "Win64",
                "Development",
                f"-Project={project_file}",
                "-WaitMutex",
                "-NoHotReloadFromIDE",
                "-NoUBA",
                "-NoXGE",
                "-NoFASTBuild",
                "-NoSNDBS",
                f"-MaxParallelActions={max(1, int(getattr(args, 'unreal_max_parallel_actions', 2)))}",
            f"-Log={ubt_log_dir / f'unreal_build_tool{log_suffix}.log'}",
            ],
            cwd=ROOT,
            env=_windows_runtime_env(work_root / "unreal_build_runtime"),
            timeout_seconds=max(300.0, args.timeout_seconds),
            log_path=args.log_dir.resolve() / "unreal" / f"unreal_build{log_suffix}.log",
        )
        result["build"] = build_result
        if not build_result.get("success"):
            if _unreal_build_log_backup_denied(build_result):
                result["build_warning"] = "UnrealBuildTool log backup was denied under ProgramData; continuing because the editor binary is already present."
            else:
                result["status"] = "fail"
                result["reason"] = "Unreal project build did not complete successfully."
                return result
    else:
            result["build"] = {
            "status": "missing",
            "reason": "Unreal Build.bat was not found for the selected editor root.",
            "path": str(build_bat),
        }

    launcher_commands = report.get("launcher_commands")
    if not isinstance(launcher_commands, list) or not launcher_commands:
        launcher_commands = [launcher_command]

    shader_work_dir = work_root / "unreal_shader_working"
    shader_work_dir.mkdir(parents=True, exist_ok=True)
    ddc_root = Path(tempfile.gettempdir()) / "ue_ddc" / work_root.name / "ddc"
    ddc_root.mkdir(parents=True, exist_ok=True)
    run_results: list[dict[str, Any]] = []
    _clear_generated_capture_root(normalized_capture_root)
    _clear_generated_capture_root(Path(str(report.get("raw_capture_root") or build_cesium_visual_proof.UNREAL_RAW_CAPTURE_ROOT)))
    for index, command_text in enumerate(launcher_commands):
        unreal_editor_log = args.log_dir / "unreal" / (
            f"unreal_editor_abs{log_suffix}.log" if len(launcher_commands) == 1 else f"unreal_editor_abs{log_suffix}_{index}.log"
        )
        # Build and launch the same isolated project. Launching the source
        # path after compiling its alias can load stale binaries from Saved/.
        source_project_value = report.get("example_project")
        source_project_file = Path(str(source_project_value)) if source_project_value else None
        launcher_project_command = str(command_text)
        if source_project_file is not None:
            launcher_project_command = launcher_project_command.replace(
                str(source_project_file), str(project_file)
            )
        launcher_command_runtime = (
            f'{launcher_project_command} -ShaderWorkingDir="{shader_work_dir}" '
            f'-LocalDataCachePath="{ddc_root}" '
            f'-abslog="{unreal_editor_log}" -forcelogflush'
        )
        run_result = _run_process(
            launcher_command_runtime,
            cwd=project_dir,
            env=_windows_runtime_env(work_root / "unreal_runtime"),
            timeout_seconds=args.timeout_seconds,
            log_path=args.log_dir / "unreal" / f"unreal_visual_proof{log_suffix}_{index}.log",
        )
        run_result["abslog_path"] = str(unreal_editor_log)
        run_result["launcher_command"] = command_text
        # Unreal can return a nonzero OS status while its automation worker
        # has already reported a successful test session in the absolute log.
        # Reconcile that engine-level result without hiding genuine timeouts or
        # missing test completion markers.
        if not run_result.get("success") and not run_result.get("timed_out"):
            try:
                abslog_text = unreal_editor_log.read_text(encoding="utf-8", errors="replace")
            except OSError:
                abslog_text = ""
            if "**** TEST COMPLETE. EXIT CODE: 0 ****" in abslog_text:
                run_result["success"] = True
                run_result["completed_by_abslog_marker"] = True
        run_results.append(run_result)
        if not run_result["success"]:
            break

    overall_run_success = bool(run_results) and all(run_result["success"] for run_result in run_results)
    result["runs"] = run_results
    result["run"] = {
        "command": run_results[-1]["command"] if run_results else None,
        "returncode": run_results[-1]["returncode"] if run_results else None,
        "timed_out": any(run_result["timed_out"] for run_result in run_results),
        "success": overall_run_success,
        "abslog_path": run_results[-1].get("abslog_path") if run_results else None,
        "launcher_command": run_results[-1].get("launcher_command") if run_results else None,
    }
    raw_capture_root = Path(str(report.get("raw_capture_root") or build_cesium_visual_proof.UNREAL_RAW_CAPTURE_ROOT))
    normalize_result = _normalize_capture("unreal", raw_capture_root, normalized_capture_root)
    result["normalize"] = normalize_result
    validation_result = _validate_root_contract(normalized_capture_root)
    result["validate"] = validation_result
    compare_result = _compare_roots([normalized_capture_root])
    result["compare"] = compare_result
    compare_gate_pass = _visual_compare_gate_passes(compare_result)
    result["status"] = "pass" if overall_run_success and normalize_result.get("status") == "pass" and validation_result.get("status") == "pass" and compare_gate_pass else "fail"
    if not overall_run_success:
        result["reason"] = "Unreal automation commands did not complete successfully."
    elif normalize_result.get("status") != "pass":
        result["reason"] = "Unreal capture normalization did not complete cleanly."
    elif validation_result.get("status") != "pass":
        result["reason"] = "Unreal visual-proof manifest/content contract failed."
    elif not compare_gate_pass:
        result["reason"] = "Unreal visual comparison gate failed."
    else:
        result["reason"] = None
    return result


def _run_unreal_lane(args: argparse.Namespace, work_root: Path) -> dict[str, Any]:
    raw_versions = getattr(args, "unreal_versions", None)
    if not raw_versions:
        return _run_unreal_lane_single(args, work_root)

    versions = [item.strip() for item in str(raw_versions).split(",") if item.strip()]
    version_results: list[dict[str, Any]] = []
    for version in versions:
        version_args = argparse.Namespace(**vars(args))
        version_args.unreal_version = version
        version_results.append(_run_unreal_lane_single(version_args, work_root / f"unreal_{version.replace('.', '_')}"))

    roots = [Path(item["normalized_capture_root"]) for item in version_results]
    all_pass = bool(version_results) and all(item.get("status") == "pass" for item in version_results)
    return {
        "engine": "unreal",
        "status": "pass" if all_pass else "fail",
        "reason": "One or more requested Unreal version lanes failed." if not all_pass else None,
        "requested_versions": versions,
        "version_results": version_results,
        "normalized_capture_roots": [str(root) for root in roots],
        "normalized_capture_root": str(roots[0]) if roots else str(UNREAL_NORMALIZED_CAPTURE_ROOT),
        "report": {
            "status": "commandable" if version_results else "planned",
            "engine_versions": versions,
        },
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    work_root = DEFAULT_WORK_ROOT
    work_root.mkdir(parents=True, exist_ok=True)
    selected_engines = {
        item.strip().lower()
        for item in str(getattr(args, "engines", "unreal,unity,godot")).split(",")
        if item.strip()
    }
    unknown_engines = selected_engines - {"unreal", "unity", "godot"}
    if unknown_engines:
        raise ValueError(f"Unknown Windows proof engine(s): {', '.join(sorted(unknown_engines))}")
    result_unity = (
        _run_unity_lane(args, work_root)
        if "unity" in selected_engines
        else {"engine": "unity", "status": "skipped", "reason": "Lane not selected.", "report": {"status": "skipped"}, "normalize": None, "compare": None}
    )
    result_godot = (
        _run_godot_lane(args, work_root)
        if "godot" in selected_engines
        else {"engine": "godot", "status": "skipped", "reason": "Lane not selected.", "report": {"status": "skipped"}, "normalize": None, "compare": None}
    )
    result_unreal = (
        _run_unreal_lane(args, work_root)
        if "unreal" in selected_engines
        else {"engine": "unreal", "status": "skipped", "reason": "Lane not selected.", "report": {"status": "skipped"}, "normalize": None, "compare": None}
    )
    roots: list[Path] = []
    unreal_versions = result_unreal.get("version_results", [])
    if unreal_versions:
        for version_result in unreal_versions:
            if isinstance(version_result.get("normalize"), dict) and version_result["normalize"].get("status") == "pass":
                roots.append(Path(version_result["normalized_capture_root"]))
    elif isinstance(result_unreal.get("normalize"), dict) and result_unreal["normalize"].get("status") == "pass":
        roots.append(Path(result_unreal["normalized_capture_root"]))
    if isinstance(result_unity.get("normalize"), dict) and result_unity["normalize"].get("status") == "pass":
        roots.append(Path(result_unity["normalized_capture_root"]))
    if isinstance(result_godot.get("normalize"), dict) and result_godot["normalize"].get("status") == "pass":
        roots.append(Path(result_godot["normalized_capture_root"]))
    compare_payload = _compare_roots([root for root in roots if root.exists()])
    engine_results = [result_unreal, result_unity, result_godot]
    selected_results = [result for result in engine_results if result.get("status") != "skipped" or result.get("reason") != "Lane not selected."]
    any_pass = any(result.get("status") == "pass" for result in selected_results)
    all_pass = bool(selected_results) and all(result.get("status") == "pass" for result in selected_results)
    overall_status = "pass" if all_pass and _visual_compare_gate_passes(compare_payload) else ("partial" if any_pass else "fail")
    return {
        "schema": "cesium.windows_visual_proof_run.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": overall_status,
        "selected_engines": sorted(selected_engines),
        "engine_results": engine_results,
        "comparison": compare_payload,
        "normalized_capture_roots": [str(root) for root in roots],
        "source_packets": {
            "unreal_visual_proof": {
                "status": result_unreal["report"].get("status"),
                "path": "artifacts/reports/unreal_visual_proof/unreal_visual_proof.json",
            },
            "unity_visual_proof": {
                "status": result_unity["report"].get("status"),
                "path": "artifacts/reports/unity_visual_proof/unity_visual_proof.json",
            },
            "godot_visual_proof": {
                "status": result_godot["report"].get("status"),
                "path": "artifacts/reports/godot_visual_proof/godot_visual_proof.json",
            },
            "visual_proof_compare": {
                "status": compare_payload.get("status"),
                "path": "artifacts/reports/cesium_visual_proof_compare/cesium_visual_proof_compare.json",
            },
        },
        "next_steps": [
            "Use the engine-side runner results to fix whichever lane is failing first.",
            "Keep the normalized capture roots stable so the compare gate stays deterministic.",
            "Re-run the execution packet after any engine or plugin fix to prove the drift is gone.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Windows Visual Proof Run",
        "",
        f"- status: `{payload['status']}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Engine Results",
        "",
    ]
    for result in payload.get("engine_results", []):
        lines.append(f"### {result['engine']}")
        lines.append(f"- status: `{result.get('status')}`")
        if result.get("reason"):
            lines.append(f"- reason: `{result.get('reason')}`")
        if result.get("raw_capture_root"):
            lines.append(f"- raw_capture_root: `{result.get('raw_capture_root')}`")
        if result.get("normalized_capture_root"):
            lines.append(f"- normalized_capture_root: `{result.get('normalized_capture_root')}`")
        if result.get("run") is not None:
            run = result["run"]
            lines.append(f"- returncode: `{run.get('returncode')}`")
            lines.append(f"- timed_out: `{run.get('timed_out')}`")
        if result.get("build") is not None:
            build = result["build"]
            lines.append(f"- build_status: `{build.get('status')}`")
            lines.append(f"- build_output: `{build.get('output_path')}`")
        if result.get("normalize") is not None:
            lines.append(f"- normalize_status: `{result['normalize'].get('status')}`")
        if result.get("compare") is not None:
            lines.append(f"- compare_status: `{result['compare'].get('status')}`")
    lines.extend(["", "## Comparison", ""])
    lines.append(f"- status: `{payload['comparison'].get('status')}`")
    lines.append(f"- sample_count: `{payload['comparison'].get('summary', {}).get('sample_count')}`")
    lines.append(f"- missing_engines: `{payload['comparison'].get('summary', {}).get('missing_engines')}`")
    lines.extend(["", "## Source Packets", ""])
    for name, report in payload.get("source_packets", {}).items():
        if isinstance(report, dict):
            lines.append(f"- `{name}`: `{report.get('status')}` -> `{report.get('path')}`")
    lines.extend(["", "## Next Steps", ""])
    for step in payload.get("next_steps", []):
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    payload = build_payload(args)
    _write_report(payload, args.json_out, args.md_out)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
