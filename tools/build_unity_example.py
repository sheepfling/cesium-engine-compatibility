#!/usr/bin/env python3
"""Build the repo-owned Cesium Unity example project with a local Unity editor."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any

from tools import unity_env


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DIR = ROOT / "extensions" / "cesium" / "examples" / "unity" / "CesiumVanillaExample"
UNITY_PACKAGE_ROOT = ROOT / "external" / "cesium" / "cesium-unity"
REINTEROP_BUILD_OUTPUT_DIR = UNITY_PACKAGE_ROOT / "Reinterop~" / "bin" / "Debug" / "netstandard2.0"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "reports" / "unity_example_build"
DEFAULT_LOG_ROOT = ROOT / "artifacts" / "reports" / "unity_example_build" / "logs"
DEFAULT_BUILD_ROOT = PROJECT_DIR / "build" / "unity" / "CesiumVanillaExample"
BUILD_TARGETS = ("windows", "linux", "mac")
NODE_SYSTEM_CA_FLAG = "--use-system-ca"
REINTEROP_DEPENDENCY_DLLS = {
    "Microsoft.CodeAnalysis.Common": "Microsoft.CodeAnalysis.dll",
    "Microsoft.CodeAnalysis.CSharp": "Microsoft.CodeAnalysis.CSharp.dll",
    "System.Collections.Immutable": "System.Collections.Immutable.dll",
    "System.Text.Encoding.CodePages": "System.Text.Encoding.CodePages.dll",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unity-version", help="Unity editor version prefix to select, for example 6000.5")
    parser.add_argument("--build-target", choices=BUILD_TARGETS, default="windows")
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--log-out", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preserve", action="store_true")
    return parser.parse_args(argv)


def _slug(value: str) -> str:
    return value.replace(".", "_").replace("-", "_")


def _build_output_path(project_dir: Path, build_target: str) -> Path:
    base = project_dir / "build" / "unity" / "CesiumVanillaExample"
    if build_target == "windows":
        return base / "windows" / "CesiumVanillaExample.exe"
    if build_target == "linux":
        return base / "linux" / "CesiumVanillaExample.x86_64"
    return base / "mac" / "CesiumVanillaExample.app"


def _staged_project_dir(stage_root: Path, unity_version: str, stage_token: str) -> Path:
    return stage_root / _slug(unity_version) / stage_token / "CesiumVanillaExample"


def _prepare_project_dir(source_dir: Path, staged_dir: Path) -> Path:
    def _ignore(directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        if Path(directory).resolve() == source_dir.resolve():
            ignored.update({"Library", "Logs", "Temp", "UserSettings", "Build", "build"})
        if Path(directory).name == "Packages":
            ignored.add("packages-lock.json")
        return {name for name in names if name in ignored}

    shutil.copytree(source_dir, staged_dir, ignore=_ignore)
    return staged_dir


def _staged_package_root(project_dir: Path) -> Path:
    return project_dir / "Packages" / UNITY_PACKAGE_ROOT.name


def _copy_package_tree(source_root: Path, destination_root: Path) -> None:
    allowed_dirs = {"Build~", "Editor", "Reinterop~", "Source", "native~"}
    destination_root.mkdir(parents=True, exist_ok=True)
    for entry in source_root.iterdir():
        if entry.is_dir():
            if entry.name not in allowed_dirs:
                continue
            destination = destination_root / entry.name
            if destination.exists() or destination.is_symlink():
                if destination.is_dir() and not destination.is_symlink():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                if os.name == "nt":
                    completed = subprocess.run(
                        ["cmd", "/c", "mklink", "/J", str(destination), str(entry)],
                        capture_output=True,
                        text=True,
                    )
                    if completed.returncode == 0:
                        continue
                else:
                    os.symlink(entry, destination, target_is_directory=True)
                continue
            except (OSError, subprocess.SubprocessError):
                pass

            def _ignore(directory: str, names: list[str]) -> set[str]:
                ignored: set[str] = {".git", ".vs", "bin", "obj"}
                if Path(directory).name == "Packages":
                    ignored.add("packages-lock.json")
                return {name for name in names if name in ignored}

            shutil.copytree(entry, destination, ignore=_ignore, dirs_exist_ok=True)
            continue
        shutil.copy2(entry, destination_root / entry.name)


def _stage_prebuilt_native_library(package_root: Path, native_build_root: Path) -> str | None:
    if os.environ.get("CESIUM_UNITY_USE_PREBUILT_NATIVE", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    source = Path(
        os.environ.get(
            "CESIUM_UNITY_NATIVE_DLL",
            str(native_build_root / "build-Standalone" / "RelWithDebInfo" / "CesiumForUnityNative.dll"),
        )
    )
    if not source.is_file():
        return None
    destination = package_root / "Plugins" / "Standalone" / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return str(destination)


def _native_library_status(package_root: Path) -> dict[str, Any]:
    """Distinguish a real native bridge from Unity's build placeholder."""
    library = package_root / "Plugins" / "Standalone" / "CesiumForUnityNative.dll"
    exists = library.is_file()
    size = library.stat().st_size if exists else 0
    placeholder = exists and size < 1024 * 1024
    return {
        "path": str(library),
        "exists": exists,
        "size_bytes": size,
        "placeholder": placeholder,
        "valid": exists and not placeholder,
    }


def _rewrite_project_version(project_dir: Path, unity_version: str) -> None:
    version_file = project_dir / "ProjectSettings" / "ProjectVersion.txt"
    if not version_file.is_file():
        return
    lines = version_file.read_text(encoding="utf-8").splitlines()
    rewritten: list[str] = []
    seen_version = False
    seen_revision = False
    for line in lines:
        if line.startswith("m_EditorVersion:"):
            rewritten.append(f"m_EditorVersion: {unity_version}")
            seen_version = True
            continue
        if line.startswith("m_EditorVersionWithRevision:"):
            rewritten.append(f"m_EditorVersionWithRevision: {unity_version} (aligned)")
            seen_revision = True
            continue
        rewritten.append(line)
    if not seen_version:
        rewritten.append(f"m_EditorVersion: {unity_version}")
    if not seen_revision:
        rewritten.append(f"m_EditorVersionWithRevision: {unity_version} (aligned)")
    version_file.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def _rewrite_local_package_manifest(project_dir: Path, package_root: Path | None = None) -> None:
    manifest_path = project_dir / "Packages" / "manifest.json"
    if not manifest_path.is_file():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict):
        return
    package_key = "com.cesium.unity"
    package_path = package_root or (ROOT / "external" / "cesium" / "cesium-unity")
    relative_package_path = os.path.relpath(package_path, start=manifest_path.parent).replace("\\", "/")
    current_value = dependencies.get(package_key)
    if isinstance(current_value, str) and current_value.startswith("file:"):
        dependencies[package_key] = f"file:{relative_package_path}"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _stage_reinterop_artifacts(package_root: Path, *, source_dir: Path | None = None) -> list[str]:
    source_dir = source_dir or REINTEROP_BUILD_OUTPUT_DIR
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Reinterop build output was not found at {source_dir}")

    staged: list[str] = []
    for artifact in sorted(source_dir.iterdir()):
        if not artifact.is_file():
            continue
        if artifact.suffix.lower() not in {".dll", ".pdb"}:
            continue
        shutil.copy2(artifact, package_root / artifact.name)
        staged.append(artifact.name)

    reinterop_root = source_dir.parents[2]
    deps_json = reinterop_root / "obj" / "Debug" / "netstandard2.0" / "Reinterop.deps.json"
    if deps_json.is_file():
        shutil.copy2(deps_json, package_root / deps_json.name)
        staged.append(deps_json.name)
    return staged


def _stage_reinterop_dependency_dlls(
    package_root: Path,
    *,
    deps_json_path: Path | None = None,
    nuget_root: Path | None = None,
) -> list[str]:
    deps_json_path = deps_json_path or (
        REINTEROP_BUILD_OUTPUT_DIR.parents[2] / "obj" / "Debug" / "netstandard2.0" / "Reinterop.deps.json"
    )
    nuget_root = nuget_root or (Path.home() / ".nuget" / "packages")
    if not deps_json_path.is_file() or not nuget_root.is_dir():
        return []

    try:
        deps = json.loads(deps_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    libraries = deps.get("libraries")
    if not isinstance(libraries, dict):
        return []

    staged: list[str] = []
    for library_key, dll_name in REINTEROP_DEPENDENCY_DLLS.items():
        matching_key = next((key for key in libraries if key.startswith(f"{library_key}/")), None)
        if matching_key is None:
            continue
        try:
            package_name, version = matching_key.split("/", 1)
        except ValueError:
            continue
        source_dll = nuget_root / package_name.lower() / version / "lib" / "netstandard2.0" / dll_name
        if not source_dll.is_file():
            continue
        shutil.copy2(source_dll, package_root / source_dll.name)
        staged.append(source_dll.name)
        source_pdb = source_dll.with_suffix(".pdb")
        if source_pdb.is_file():
            shutil.copy2(source_pdb, package_root / source_pdb.name)

    immutable_dll = nuget_root / "system.collections.immutable" / "5.0.0" / "lib" / "netstandard2.0" / "System.Collections.Immutable.dll"
    if immutable_dll.is_file() and immutable_dll.name not in staged:
        shutil.copy2(immutable_dll, package_root / immutable_dll.name)
        staged.append(immutable_dll.name)
    return staged


def _touch_reinterop_sources(package_root: Path) -> list[str]:
    touched: list[str] = []
    for relative in ("Source/Runtime/ConfigureReinterop.cs", "Source/Editor/ConfigureReinteropEditor.cs"):
        path = package_root / relative
        if not path.is_file():
            continue
        os.utime(path, None)
        touched.append(str(path))
    return touched


def _build_command(editor: str, project_dir: Path, *, build_target: str, log_out: Path) -> list[str]:
    return [
        editor,
        "-batchmode",
        "-nographics",
        "-accept-apiupdate",
        "-quit",
        "-projectPath",
        str(project_dir),
        "-executeMethod",
        "CesiumExample.CesiumExampleBuild.BuildFromCommandLine",
        "-cesiumBuildTarget",
        build_target,
        "-logFile",
        str(log_out),
    ]


def _append_node_system_ca_flag(value: str | None) -> str:
    if not value:
        return NODE_SYSTEM_CA_FLAG
    parts = value.split()
    if NODE_SYSTEM_CA_FLAG in parts:
        return value
    return f"{value} {NODE_SYSTEM_CA_FLAG}"


def _short_temp_root(name: str) -> Path:
    """Return a short, writable temp anchor for Windows toolchain paths."""
    return Path(tempfile.gettempdir()) / name


def _build_env(runtime_root: Path, native_build_root: Path) -> dict[str, str]:
    runtime_root = runtime_root.resolve()
    native_build_root = native_build_root.resolve()
    env = dict(os.environ)
    env["NODE_OPTIONS"] = _append_node_system_ca_flag(env.get("NODE_OPTIONS"))
    use_host_license = env.get("CESIUM_UNITY_USE_HOST_LICENSE", "1").strip().lower() not in {"0", "false", "no", "off"}
    # Unity 6000.3.x can try to write licensing/config files under the user's
    # LocalAppData tree. Keep the editor isolated to a writable runtime profile
    # so older installs do not inherit a blocked host profile path.
    user_profile = runtime_root / "UserProfile"
    localappdata = runtime_root / "LocalAppData"
    appdata = runtime_root / "RoamingAppData"
    temp_dir = runtime_root / "Temp"
    ezvcpkg_root = Path(env.get("EZVCPKG_BASEDIR", str(_short_temp_root("cesium-ezvcpkg"))))
    unity_logs_dir = runtime_root / "UnityLogs"
    upm_cache_root = runtime_root / "UPMCache"
    upm_config_root = runtime_root / "UPMConfig"
    upm_npm_cache_path = runtime_root / "UPMNpmCache"
    upm_packages_cache_path = runtime_root / "UPMPackagesCache"
    upm_global_config_file = upm_config_root / "upmconfig.toml"
    upm_user_config_file = upm_config_root / ".upmconfig.toml"
    for path in (user_profile, localappdata, appdata, temp_dir, unity_logs_dir, ezvcpkg_root):
        path.mkdir(parents=True, exist_ok=True)
    for path in (upm_cache_root, upm_config_root, upm_npm_cache_path, upm_packages_cache_path):
        path.mkdir(parents=True, exist_ok=True)
    upm_config_text = f'cacheRoot = "{upm_cache_root.as_posix()}"\n'
    upm_global_config_file.write_text(upm_config_text, encoding="utf-8")
    upm_user_config_file.write_text(upm_config_text, encoding="utf-8")
    if not use_host_license:
        env["USERPROFILE"] = str(user_profile)
        env["HOMEDRIVE"] = "C:"
        env["HOMEPATH"] = "\\"
        env["HOME"] = str(user_profile)
        env["LOCALAPPDATA"] = str(localappdata)
        env["APPDATA"] = str(appdata)
    env["TEMP"] = str(temp_dir)
    env["TMP"] = str(temp_dir)
    env["EZVCPKG_BASEDIR"] = str(ezvcpkg_root)
    if env.get("CESIUM_BUILD_NATIVE_BEFORE_PLAYER", "").strip() == "1":
        # Cesium-native generates headers consumed by the same build graph.
        # Serial proof builds avoid a generator/compile race on Windows.
        env.setdefault("CESIUM_NATIVE_BUILD_PARALLEL", "1")
    env["CESIUM_NATIVE_BUILD_ROOT"] = str(native_build_root)
    env["UNITY_LOGS_DIR"] = str(unity_logs_dir)
    env["UPM_CACHE_ROOT"] = str(upm_cache_root)
    env["UPM_CACHE_PATH"] = str(upm_packages_cache_path)
    env["UPM_GLOBAL_CONFIG_FILE"] = str(upm_global_config_file)
    env["UPM_USER_CONFIG_FILE"] = str(upm_user_config_file)
    env["UPM_CONFIG_ROOT"] = str(upm_config_root)
    env["UPM_NPM_CACHE_PATH"] = str(upm_npm_cache_path)
    return env


def _run_unity_with_progress(
    command: list[str],
    runtime_root: Path,
    native_build_root: Path,
) -> tuple[int, str, str, bool, Path]:
    """Run Unity while recording native-build progress and enforcing cleanup."""
    runtime_root.mkdir(parents=True, exist_ok=True)
    progress_path = runtime_root / "unity_build_progress.jsonl"
    stdout_path = runtime_root / "unity.stdout.log"
    stderr_path = runtime_root / "unity.stderr.log"
    timeout_s = float(os.environ.get("CESIUM_UNITY_BUILD_TIMEOUT_S", "1800"))
    started = time.monotonic()
    last_snapshot = 0.0
    timed_out = False

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            text=True,
            stdout=stdout_file,
            stderr=stderr_file,
            env=_build_env(runtime_root, native_build_root),
        )
        while process.poll() is None:
            now = time.monotonic()
            if now - last_snapshot >= 15.0:
                native_logs = sorted(native_build_root.glob("build-*/build.log"))
                native_log = native_logs[-1] if native_logs else None
                tail: list[str] = []
                size = 0
                if native_log and native_log.is_file():
                    size = native_log.stat().st_size
                    tail = native_log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
                with progress_path.open("a", encoding="utf-8") as progress_file:
                    progress_file.write(
                        json.dumps(
                            {
                                "timestamp": datetime.now(UTC).isoformat(),
                                "elapsed_seconds": round(now - started, 1),
                                "pid": process.pid,
                                "native_log": str(native_log) if native_log else None,
                                "native_log_size_bytes": size,
                                "native_log_tail": tail,
                                "timed_out": False,
                            }
                        )
                        + "\n"
                    )
                last_snapshot = now
            if now - started >= timeout_s:
                timed_out = True
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    process.kill()
                process.wait(timeout=30)
                with progress_path.open("a", encoding="utf-8") as progress_file:
                    progress_file.write(
                        json.dumps(
                            {
                                "timestamp": datetime.now(UTC).isoformat(),
                                "elapsed_seconds": round(now - started, 1),
                                "pid": process.pid,
                                "timed_out": True,
                            }
                        )
                        + "\n"
                    )
                break
            time.sleep(1.0)

    return (
        process.returncode if process.returncode is not None else 124,
        stdout_path.read_text(encoding="utf-8", errors="replace"),
        stderr_path.read_text(encoding="utf-8", errors="replace"),
        timed_out,
        progress_path,
    )


def _tail_lines(text: str, limit: int = 80) -> list[str]:
    rows = [line for line in text.splitlines() if line.strip()]
    return rows[-max(1, limit):]


def _failure_signals(build_log_tail: list[str]) -> list[str]:
    signals: list[str] = []
    if any("Failed to resolve packages:" in line for line in build_log_tail):
        signals.append("Package Manager tried to write under the installed editor tree and hit EPERM.")
    if any("Unable to retrieve BIOS serial number" in line for line in build_log_tail):
        signals.append("Unity licensing still hits BIOS lookup denial and mutex contention on this host.")
    if any("No valid Unity Editor license found" in line for line in build_log_tail):
        signals.append("Unity batchmode build is blocked by a missing local Editor license on this host.")
    if any("com.unity.editor.headless" in line for line in build_log_tail):
        signals.append("Unity licensing client reported the headless entitlement was unavailable.")
    if any("production.json" in line and "denied" in line for line in build_log_tail):
        signals.append("Unity licensing client cannot read the host production.json configuration; terminate and retry only after the license profile is repaired.")
    return signals


def _stop_stale_unity_licensing_clients() -> None:
    # Older Unity sessions can leave behind the editor, Hub, and licensing
    # client processes that keep the global mutex and prevent a fresh batchmode
    # run from progressing.
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-Process 'Unity Hub','Unity.Licensing.Client','Unity' -ErrorAction SilentlyContinue | Stop-Process -Force",
        ],
        cwd=ROOT,
    )


def _write_report(payload: dict[str, Any], json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Cesium Unity Example Build",
        "",
        f"- status: `{payload['status']}`",
        f"- unity_version: `{payload['unity_version']}`",
        f"- build_target: `{payload['build_target']}`",
        f"- editor_path: `{payload['editor_path']}`",
        f"- project_dir: `{payload['project_dir']}`",
        f"- output_path: `{payload['output_path']}`",
        f"- log_out: `{payload['log_out']}`",
        f"- exit_code: `{payload.get('exit_code')}`",
    ]
    if payload.get("stdout_tail"):
        lines.extend(["", "## Stdout Tail", ""])
        for line in payload["stdout_tail"]:
            lines.append(f"- {line}")
    if payload.get("stderr_tail"):
        lines.extend(["", "## Stderr Tail", ""])
        for line in payload["stderr_tail"]:
            lines.append(f"- {line}")
    if payload.get("build_log_tail"):
        lines.extend(["", "## Build Log Tail", ""])
        for line in payload["build_log_tail"]:
            lines.append(f"- {line}")
    if payload.get("failure_signals"):
        lines.extend(["", "## Failure Signals", ""])
        for signal in payload["failure_signals"]:
            lines.append(f"- {signal}")
    if payload.get("detail"):
        lines.extend(["", "## Detail", "", str(payload["detail"])])
    return "\n".join(lines) + "\n"


def _default_report_paths(out_dir: Path, unity_version: str, build_target: str) -> tuple[Path, Path, Path]:
    stem = f"unity_example_build_{_slug(unity_version)}_{build_target}"
    return (
        out_dir / f"{stem}.json",
        out_dir / f"{stem}.md",
        DEFAULT_LOG_ROOT / f"{stem}.log",
    )


def run_build(args: argparse.Namespace) -> dict[str, Any]:
    install = unity_env.resolve_install(args.unity_version)
    if install is None or install.editor_path is None:
        return {
            "schema": "cesium.unity_example_build.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "needs-attention",
            "detail": "No suitable Unity editor install was discovered.",
            "unity_version": args.unity_version,
            "build_target": args.build_target,
            "project_dir": str(args.project_dir),
            "editor_path": None,
            "output_path": str(_build_output_path(args.project_dir, args.build_target)),
            "log_out": None,
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "build_log_tail": [],
            "failure_signals": [],
        }

    json_out, md_out, log_out = _default_report_paths(args.out_dir, install.version, args.build_target)
    if args.json_out is not None:
        json_out = args.json_out
    if args.md_out is not None:
        md_out = args.md_out
    if args.log_out is not None:
        log_out = args.log_out

    stage_token = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    stage_root = Path(
        os.environ.get(
            "CESIUM_UNITY_STAGE_ROOT",
            str(_short_temp_root("c")),
        )
    ).resolve()
    staged_project_dir = _staged_project_dir(stage_root, install.version, stage_token)
    runtime_root = stage_root / _slug(install.version) / stage_token / "runtime"
    output_path = _build_output_path(staged_project_dir, args.build_target)
    command = _build_command(install.editor_path, staged_project_dir, build_target=args.build_target, log_out=log_out)
    if args.dry_run:
        payload = {
            "schema": "cesium.unity_example_build.v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "dry-run",
            "detail": "not executed; use without --dry-run to run the Unity example build",
            "unity_version": install.version,
            "build_target": args.build_target,
            "project_dir": str(args.project_dir),
            "staged_project_dir": str(staged_project_dir),
            "staged_package_root": str(_staged_package_root(staged_project_dir)),
            "stage_token": stage_token,
            "editor_path": install.editor_path,
            "reinterop_stage_source_dir": str(REINTEROP_BUILD_OUTPUT_DIR),
            "reinterop_staged_files": [],
            "reinterop_dependency_files": [],
            "reinterop_touched_files": [],
            "command": command,
            "output_path": str(output_path),
            "log_out": str(log_out),
            "exit_code": None,
            "stdout_tail": [],
            "stderr_tail": [],
            "build_log_tail": [],
            "failure_signals": [],
        }
        _write_report(payload, json_out, md_out)
        return payload

    _stop_stale_unity_licensing_clients()
    _prepare_project_dir(args.project_dir, staged_project_dir)
    _rewrite_project_version(staged_project_dir, install.version)
    staged_package_root = _staged_package_root(staged_project_dir)
    _copy_package_tree(UNITY_PACKAGE_ROOT, staged_package_root)
    reinterop_staged_files = _stage_reinterop_artifacts(staged_package_root)
    reinterop_dependency_files = _stage_reinterop_dependency_dlls(staged_package_root)
    reinterop_touched_files = _touch_reinterop_sources(staged_package_root)
    _rewrite_local_package_manifest(staged_project_dir, staged_package_root)
    log_out.parent.mkdir(parents=True, exist_ok=True)
    native_build_root = Path(
        os.environ.get(
            "CESIUM_UNITY_NATIVE_BUILD_ROOT",
            str(_short_temp_root("cesium-unity-native") / args.build_target),
        )
    )
    prebuilt_native_library = _stage_prebuilt_native_library(staged_package_root, native_build_root)
    exit_code, stdout_text, stderr_text, timed_out, progress_path = _run_unity_with_progress(
        command,
        runtime_root,
        native_build_root,
    )
    build_log_text = log_out.read_text(encoding="utf-8", errors="replace") if log_out.is_file() else ""
    build_exists = output_path.is_file() or output_path.is_dir()
    native_status = _native_library_status(staged_package_root)
    native_required = os.environ.get("CESIUM_BUILD_NATIVE_BEFORE_PLAYER", "").strip() == "1"
    native_ok = not native_required or native_status["valid"]
    status = "pass" if exit_code == 0 and build_exists and native_ok else "fail"
    detail = "Unity example build completed" if status == "pass" else "Unity example build failed"
    payload = {
        "schema": "cesium.unity_example_build.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "detail": detail,
        "unity_version": install.version,
        "build_target": args.build_target,
        "project_dir": str(args.project_dir),
        "staged_project_dir": str(staged_project_dir),
        "staged_package_root": str(staged_package_root),
        "stage_token": stage_token,
        "editor_path": install.editor_path,
        "reinterop_stage_source_dir": str(REINTEROP_BUILD_OUTPUT_DIR),
        "reinterop_staged_files": reinterop_staged_files,
        "reinterop_dependency_files": reinterop_dependency_files,
        "reinterop_touched_files": reinterop_touched_files,
        "prebuilt_native_library": prebuilt_native_library,
        "command": command,
        "output_path": str(output_path),
        "output_exists": build_exists,
        "output_size_bytes": output_path.stat().st_size if output_path.is_file() else None,
        "native_required": native_required,
        "native_library": native_status,
        "log_out": str(log_out),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "progress_log": str(progress_path),
        "stdout_tail": _tail_lines(stdout_text),
        "stderr_tail": _tail_lines(stderr_text),
        "build_log_tail": _tail_lines(build_log_text),
        "failure_signals": _failure_signals(_tail_lines(build_log_text)),
    }
    _write_report(payload, json_out, md_out)
    if args.preserve:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.parent.mkdir(parents=True, exist_ok=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_build(args)
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] in {"pass", "dry-run"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
